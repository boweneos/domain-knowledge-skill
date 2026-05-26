# PII Redaction via Presidio — v0.3.2 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Add **optional** content-level redaction of detected PII via Microsoft Presidio. Operator opts in per-ingest with `--redact-pii`. Without the flag, dks ingest behaviour is unchanged.

**Version:** 0.3.1 → 0.3.2 (minor — new optional dep, new flag, new field on NormalizedBlock).

**Tech:** `presidio-analyzer` + `presidio-anonymizer` + `spacy` as an OPTIONAL extra (`uv tool install --with presidio-analyzer --with presidio-anonymizer dks`). Spacy model `en_core_web_lg` downloaded once by the user.

---

## Architecture

### Optional dependency

In `pyproject.toml`:

```toml
[project.optional-dependencies]
redact = [
    "presidio-analyzer>=2.2",
    "presidio-anonymizer>=2.2",
    "spacy>=3.7",
]
```

dks core does NOT import Presidio. The redactor module lazily imports it; if Presidio isn't installed, `--redact-pii` errors with a helpful install hint.

### New module — `src/dks/redact.py`

```python
"""Optional PII redaction via Microsoft Presidio.

Presidio is an OPTIONAL dependency. Install with:
    uv tool install --with presidio-analyzer --with presidio-anonymizer dks
And download the spaCy model (once):
    python -m spacy download en_core_web_lg

If Presidio isn't installed, calling redact_text() raises ImportError with
a clear message; callers (CLI) should catch and re-message appropriately.
"""

def redact_text(text: str, *, entities: list[str] | None = None) -> str:
    """Return `text` with detected PII entities replaced by `[REDACTED:<TYPE>]`.

    `entities`: optional list of entity types to redact (PERSON, EMAIL_ADDRESS,
    PHONE_NUMBER, DATE_TIME, IP_ADDRESS, CREDIT_CARD, AU_TFN, AU_MEDICARE, AU_ABN, ...).
    Default: all Presidio-registered entities for English + Australia.

    Raises ImportError with install hint if Presidio isn't available.
    """
    ...
```

### NormalizedBlock gains a `redacted: bool = False` field

Persisted in frontmatter. When `--redact-pii` is used, blocks carry `redacted: True`. Downstream consumers (skills, lint) can see whether a block's content was modified at ingest.

### CLI integration

`dks ingest --redact-pii` runs `redact_text` on each item's content before normalizing. The redacted text becomes the block's `content`; the block carries `redacted=True`.

Order of operations within ingest:
1. Parse → items
2. Scan (regex, advisory) → emit WARN if findings (unchanged from v0.3.1)
3. **If `--redact-pii`:** redact each item's content → items with redacted content
4. Normalize → blocks (with `redacted=True` if step 3 ran)
5. Write

The classification flag is independent of `--redact-pii`. A common combo will be `--classification confidential --redact-pii` (mark it sensitive AND scrub PII), but they're orthogonal.

---

## Task 1 — Optional dependency + redact module

**Files:**
- `pyproject.toml` (modify — add `[project.optional-dependencies].redact`)
- `src/dks/redact.py` (new)
- `tests/test_redact.py` (new — conditional via `pytest.importorskip`)

`tests/test_redact.py`:

```python
"""Tests for the optional Presidio redaction. Skipped when Presidio isn't installed."""

import pytest

# Skip the whole module if Presidio isn't available
presidio_analyzer = pytest.importorskip("presidio_analyzer")
presidio_anonymizer = pytest.importorskip("presidio_anonymizer")

from dks.redact import redact_text


def test_redact_text_replaces_email():
    redacted = redact_text("Contact alice@example.com about claim.")
    assert "alice@example.com" not in redacted
    assert "[REDACTED:EMAIL_ADDRESS]" in redacted


def test_redact_text_replaces_person_name():
    redacted = redact_text("Customer John Smith reported the issue.")
    assert "John Smith" not in redacted
    assert "[REDACTED:PERSON]" in redacted


def test_redact_text_preserves_non_pii():
    text = "The claim filing window is 30 days per policy 3.2."
    redacted = redact_text(text)
    assert "30 days" in redacted
    assert "3.2" in redacted


def test_redact_text_empty_returns_empty():
    assert redact_text("") == ""


def test_redact_text_no_pii_unchanged():
    text = "Policy section about retention periods."
    assert redact_text(text) == text


def test_redact_text_handles_multiple_entities():
    text = "Email alice@example.com phoned 0412 345 678"
    redacted = redact_text(text)
    assert "alice@example.com" not in redacted
    assert "0412 345 678" not in redacted
    assert "[REDACTED:EMAIL_ADDRESS]" in redacted
```

`src/dks/redact.py`:

```python
"""Optional PII redaction via Microsoft Presidio.

This module is the integration point for `dks ingest --redact-pii`. It lazily
imports Presidio so that dks core works without the optional dependency
installed.
"""

from functools import lru_cache


def _missing_dep_message() -> str:
    return (
        "presidio is not installed. To enable --redact-pii:\n"
        "  uv tool install --with presidio-analyzer --with presidio-anonymizer dks\n"
        "  python -m spacy download en_core_web_lg\n"
        "Then re-run with --redact-pii."
    )


@lru_cache(maxsize=1)
def _get_analyzer():  # type: ignore[no-untyped-def]
    """Lazy-load Presidio analyzer. Cached so the spaCy model loads once per process."""
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(_missing_dep_message()) from e
    return AnalyzerEngine()


@lru_cache(maxsize=1)
def _get_anonymizer():  # type: ignore[no-untyped-def]
    try:
        from presidio_anonymizer import AnonymizerEngine  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(_missing_dep_message()) from e
    return AnonymizerEngine()


def redact_text(text: str, *, entities: list[str] | None = None) -> str:
    """Return `text` with detected PII entities replaced by `[REDACTED:<TYPE>]`.

    `entities`: optional list of Presidio entity types to redact (e.g.
    ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]). Default: all entities
    Presidio detects for English (plus Australian patterns Presidio supports
    natively: AU_TFN, AU_MEDICARE, AU_ABN).

    Raises ImportError with install hint if Presidio isn't available.
    """
    if not text:
        return text

    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()

    try:
        from presidio_anonymizer.entities import OperatorConfig  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(_missing_dep_message()) from e

    results = analyzer.analyze(text=text, entities=entities, language="en")
    if not results:
        return text

    # Default operator: replace with [REDACTED:<TYPE>]
    operators = {
        "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED:DEFAULT]"}),
    }
    # Per-entity replacements (override the default for known entity types)
    for entity_type in {r.entity_type for r in results}:
        operators[entity_type] = OperatorConfig(
            "replace", {"new_value": f"[REDACTED:{entity_type}]"}
        )

    anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    return anonymized.text
```

Commit:
```bash
git add pyproject.toml src/dks/redact.py tests/test_redact.py
git commit -m "feat: optional Presidio redactor — dks.redact module (v0.3.2 part 1)"
```

**Note:** the tests will be SKIPPED unless Presidio is installed locally. The implementer should install it locally before running tests to verify behaviour:

```bash
uv pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
uv run pytest tests/test_redact.py -v
```

If install fails or the model download is too slow/blocked, the tests skip cleanly and CI is unaffected. Document this in the report.

---

## Task 2 — NormalizedBlock.redacted field

**Files:**
- `src/dks/block.py` (modify)
- `tests/test_block.py` (extend)

Add to `NormalizedBlock`:

```python
class NormalizedBlock(BaseModel):
    source_file: str
    block_id: str
    locator: Locator
    block_type: BlockType = "text"
    content: str
    classification: Classification = "internal"
    redacted: bool = False
```

Tests:

```python
def test_normalized_block_default_redacted_is_false():
    block = NormalizedBlock(
        source_file="a.md",
        block_id="a.md#L1-1",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        block_type="text",
        content="x",
    )
    assert block.redacted is False


def test_normalized_block_redacted_persists_through_roundtrip():
    original = NormalizedBlock(
        source_file="a.md",
        block_id="a.md#L1-1",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        block_type="text",
        content="[REDACTED:PERSON] phoned in",
        classification="confidential",
        redacted=True,
    )
    md = to_markdown(original)
    parsed = parse_markdown(md)
    assert parsed.redacted is True
    assert parsed.content.startswith("[REDACTED:")
```

Commit:
```bash
git add src/dks/block.py tests/test_block.py
git commit -m "feat: NormalizedBlock.redacted field (v0.3.2 part 2)"
```

---

## Task 3 — `dks ingest --redact-pii` integration

**Files:**
- `src/dks/cli.py` (modify ingest)
- `tests/test_cli.py` (extend)

Update `dks ingest`:

```python
@app.command()
def ingest(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Source file to ingest."),  # noqa: B008
    root_dir: Path = typer.Option(  # noqa: B008
        Path("raw"), "--root", "-r",
        help="Directory the source path is relative to (for computing source_file).",
    ),
    write_global: bool = typer.Option(
        False, "--write-global",
        help="Force the write target to the global layer.",
    ),
    classification: Classification = typer.Option(
        "internal", "--classification",
        help="Sensitivity level: public | internal | confidential | restricted.",
    ),
    redact_pii: bool = typer.Option(
        False, "--redact-pii",
        help="Run Presidio to replace detected PII with [REDACTED:<TYPE>] before writing. Requires the 'redact' extra.",
    ),
) -> None:
    _reject_sensitive_global_write(classification, write_global)
    if not path.exists() or not path.is_file():
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(code=2)

    layers = _layers(ctx)
    write_layer = _resolve_write_layer(layers, write_global)

    try:
        source_file = str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        source_file = path.name

    try:
        parser = get_parser(path)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    items = parser(path)

    # Auto-scan (existing v0.3.1 behaviour)
    combined = "\n".join(item.content for item in items)
    scan_findings = scan_text(combined)
    if scan_findings:
        summary = ", ".join(f"{f.count} {f.pattern}" for f in scan_findings[:5])
        typer.echo(
            f"WARN: source contains PII-like patterns ({summary}); "
            f"consider --classification confidential or restricted",
            err=True,
        )

    # Redaction (new v0.3.2 behaviour)
    if redact_pii:
        try:
            from dks.redact import redact_text
            items = [item.model_copy(update={"content": redact_text(item.content)}) for item in items]
        except ImportError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=2) from e

    blocks = normalize(source_file=source_file, items=items, classification=classification)
    if redact_pii:
        blocks = [b.model_copy(update={"redacted": True}) for b in blocks]
    written = write_blocks(blocks, write_layer)
    typer.echo(f"wrote {len(written)} blocks to {write_layer.normalized_dir}/{source_file}/")
```

Tests:

```python
def test_ingest_redact_pii_without_presidio_errors(tmp_path, monkeypatch):
    # Force ImportError by stubbing dks.redact
    import sys
    monkeypatch.setitem(sys.modules, "presidio_analyzer", None)
    monkeypatch.setitem(sys.modules, "presidio_anonymizer", None)
    project = tmp_path / "proj"
    project.mkdir()
    src = tmp_path / "raw" / "x.md"
    src.parent.mkdir()
    src.write_text("Hello.")
    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(src), "--root", str(src.parent), "--redact-pii"],
    )
    assert res.exit_code != 0
    assert "redact" in res.output.lower() or "presidio" in res.output.lower()


@pytest.mark.skipif(
    not _presidio_installed(),
    reason="presidio not installed; --redact-pii path skipped"
)
def test_ingest_with_redact_pii_writes_redacted_blocks(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    src = tmp_path / "raw" / "audit.md"
    src.parent.mkdir()
    src.write_text("Customer John Smith emailed alice@example.com about claim.")

    res = _invoke(
        ["--project", str(project), "--no-global",
         "ingest", str(src), "--root", str(src.parent), "--redact-pii"],
    )
    assert res.exit_code == 0, res.output

    get_res = _invoke(
        ["--project", str(project), "--no-global",
         "blocks", "get", "audit.md#L1-1"],
    )
    payload = json.loads(get_res.output[get_res.output.find("{"):])
    assert payload["block"]["redacted"] is True
    content = payload["block"]["content"]
    assert "John Smith" not in content
    assert "alice@example.com" not in content
    assert "[REDACTED:" in content
```

You'll need a `_presidio_installed()` helper at the top of test_cli.py:

```python
def _presidio_installed() -> bool:
    try:
        import presidio_analyzer  # noqa: F401
        import presidio_anonymizer  # noqa: F401
        return True
    except ImportError:
        return False
```

Commit:
```bash
git add src/dks/cli.py tests/test_cli.py
git commit -m "feat: dks ingest --redact-pii flag with lazy Presidio import (v0.3.2 part 3)"
```

---

## Task 4 — Skill prompts + docs + bump

**Files:**
- `dks/skills/dks-search/SKILL.md`
- `dks/commands/ingest.md`
- README.md, docs/USAGE.md
- pyproject.toml, src/dks/__init__.py, dks/.claude-plugin/plugin.json → 0.3.2

**dks-search SKILL.md** — add to "Handling classified content" or as a new section:

```markdown
### Redacted blocks

A block may have been redacted at ingest (`--redact-pii`). When `dks blocks get`
returns a block with `"redacted": true`, the `content` field contains
`[REDACTED:<TYPE>]` markers where PII was detected and replaced.

For redacted blocks, you can still cite them normally — the citation is still
audit-grade because the block_id traces to the original source span — but
acknowledge in your answer that the source has been redacted:

```
The customer notification rule applies [ref: audit.md#L1-1 @ project, redacted].
(Source block has been redacted at ingest; refer to the original document for
unredacted detail.)
```
```

**ingest command** — add `--redact-pii` to the procedure documentation.

**README** — status table row:

```markdown
| `v0.3.2` (minor) | **Optional Presidio redaction**: `dks ingest --redact-pii` replaces detected PII (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, AU_TFN, ...) with `[REDACTED:<TYPE>]` markers in block content. Requires the `redact` extra (`presidio-analyzer + presidio-anonymizer + spaCy`). `NormalizedBlock` gains a `redacted: bool` field. Without the flag, ingest behaviour is unchanged. |
```

**USAGE** — add a new subsection inside "Source classification & PII guardrails":

```markdown
### Content redaction via Presidio (optional)

For docs containing real PII, `dks ingest --redact-pii` runs Microsoft Presidio
on each block's content before writing, replacing detected entities (PERSON,
EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME, AU_TFN, AU_MEDICARE, AU_ABN, etc.)
with `[REDACTED:<TYPE>]` markers.

**Install the optional extra** (one-time):

\`\`\`bash
uv tool install --with presidio-analyzer --with presidio-anonymizer dks
python -m spacy download en_core_web_lg   # ~500MB, one-time download
\`\`\`

**Usage:**

\`\`\`bash
dks ingest path/to/audit.pdf --classification confidential --redact-pii
\`\`\`

Blocks land with redacted content and a `redacted: true` field. The citation
chain is preserved (block_id traces to the original source span); only the
extracted text is rewritten. The `raw/` file is untouched.

**What Presidio does well:**
- Names (PERSON)
- Email addresses, phone numbers, dates
- AU identifiers: TFN, Medicare, ABN
- Other structured identifiers (credit cards, IP addresses, etc.)

**What it misses:**
- Context-dependent identifiers (e.g. "the second claimant" referring to someone elsewhere named)
- Names with unusual formats
- Indirect identifiers (rare condition + location + age combination)

Treat redaction as a strong default, not a complete defense. For high-risk
material, redact upstream of `raw/` with a dedicated tool and a human review
pass, then ingest the redacted version normally.
```

Bump versions to 0.3.2. Commit + tag.

---

## Self-review

- 4 commits on the branch.
- ~5 new redact tests (skipped if Presidio not installed) + ~2 block tests + ~2 CLI tests = ~9 new tests.
- mypy + ruff clean (lazy imports won't trigger mypy if Presidio isn't installed; use `# type: ignore[import-not-found]` where needed).
- Default ingest behaviour unchanged.
- `--redact-pii` without Presidio errors with clear install hint.
- `NormalizedBlock.redacted` defaults to False — backward-compatible for existing on-disk blocks.

## Report
Status, total test count (note how many redact tests were skipped vs ran), lint/typecheck, files changed, smoke test if Presidio installed.
