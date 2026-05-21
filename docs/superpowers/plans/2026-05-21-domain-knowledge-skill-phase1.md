# Domain Knowledge Skill — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ingestion + normalization foundation. Given a Markdown source file, produce citation-preserving Markdown blocks under `normalized/`, each carrying frontmatter with its source coordinates and a stable `block_id`. Heavy parsers (PDF/DOCX/Excel) are out of scope; they land in Phase 2.

**Architecture:** A pure-Python pipeline with three internal stages: *parser* (produces a typed content list per the RAG-Anything shape) → *normalizer* (wraps each item in a `NormalizedBlock` and runs the citation guard) → *writer* (serializes each block to disk as `<block_id>.md` with frontmatter). Types are Pydantic models; the CLI is Typer. No LLM, no vectors, no network — Phase 1 is deterministic and unit-testable end-to-end.

**Tech Stack:** Python 3.12, uv (project + venv), Pydantic v2 (types + validation), Typer (CLI), pytest (tests), ruff (lint+format), mypy (typecheck).

**Phase scope:** Phases 2 and 3 are tracked as follow-up plans:
- Phase 2: MinerU PDF parser, Docling DOCX parser, openpyxl Excel parser, PageIndex tree builder, compiled wiki + lint.
- Phase 3: Claude Code skill package (`search_topic`, `get_source`), eval harness, baseline vs treatment runs.

The seams in Phase 1 (`Locator` union, `TypedContentItem` shape, parser registry pattern) are explicitly designed so Phase 2 parsers plug in without changing the normalizer or writer.

---

## File Structure

Phase 1 creates the following layout. Files that change together live together. Each module has one responsibility.

```
pyproject.toml                       # uv project, deps, ruff/pytest/mypy config
.gitignore                           # adds normalized/, .venv/, __pycache__/, etc.
src/
  dks/
    __init__.py
    locators.py                      # Locator union + concrete locator types
    blockref.py                      # encode_blockref / decode_blockref
    types.py                         # TypedContentItem (parser → normalizer contract)
    block.py                         # NormalizedBlock + frontmatter serializer
    citation_guard.py                # accept/reject blocks by citation completeness
    normalizer.py                    # TypedContentItem list → NormalizedBlock list
    writer.py                        # NormalizedBlock list → files on disk
    parsers/
      __init__.py                    # parser registry (dispatch by file suffix)
      markdown.py                    # .md pass-through parser
    cli.py                           # `dks ingest <path>` Typer app
tests/
  test_locators.py
  test_blockref.py
  test_block.py
  test_citation_guard.py
  test_normalizer.py
  test_writer.py
  parsers/
    test_markdown.py
  test_cli.py
  fixtures/
    sample_simple.md                 # tiny doc for unit tests
    sample_with_headings.md          # multi-heading doc for path tracking
```

---

## Task 1 — Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/dks/__init__.py`
- Create: `src/dks/parsers/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/parsers/__init__.py`
- Create: `tests/fixtures/sample_simple.md`
- Create: `tests/fixtures/sample_with_headings.md`
- Modify: `.gitignore`

- [ ] **Step 1: Initialize uv project and create pyproject.toml**

```bash
cd /Users/bowen.li/development/KB
uv init --package --no-readme --no-pin-python --name dks
```

Then overwrite `pyproject.toml` with the version below (uv's default is too minimal):

```toml
[project]
name = "dks"
version = "0.0.1"
description = "Domain knowledge skill — citation-grounded RAG for life-insurance code agents"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.7",
  "typer>=0.12",
]

[dependency-groups]
dev = [
  "pytest>=8.0",
  "ruff>=0.6",
  "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/dks"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.mypy]
strict = true
python_version = "3.12"
mypy_path = "src"
```

- [ ] **Step 2: Install deps and verify environment**

```bash
uv sync --all-groups
uv run python -c "import pydantic, typer; print(pydantic.__version__, typer.__version__)"
```

Expected: prints two version numbers; exits 0.

- [ ] **Step 3: Create package and test scaffolding**

Create these empty files (one line each is fine, except `__init__.py` files which can be empty):

`src/dks/__init__.py`:
```python
"""Domain knowledge skill — Phase 1 (ingestion + normalization)."""
__version__ = "0.0.1"
```

`src/dks/parsers/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

`tests/parsers/__init__.py`:
```python
```

- [ ] **Step 4: Create test fixtures**

`tests/fixtures/sample_simple.md`:
```markdown
This is a single paragraph with no headings.
```

`tests/fixtures/sample_with_headings.md`:
```markdown
# Claims Handling

Claims must be filed within 30 days.

## Filing Window

Subject to subsection (2), the window may be extended.

### Extensions

Only the regulator may grant an extension beyond 60 days.
```

- [ ] **Step 5: Update .gitignore**

Append to `.gitignore`:
```
.venv/
uv.lock
normalized/
raw/

# Allow fixture files to be tracked
!tests/fixtures/
```

- [ ] **Step 6: Verify pytest discovers no tests yet (smoke check)**

```bash
uv run pytest
```

Expected: `no tests ran` or `collected 0 items`. Exits 0 or 5 (pytest's "no tests collected" code).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore src/ tests/
git commit -m "chore: scaffold dks package (uv, pydantic, typer, pytest)"
```

---

## Task 2 — Locator types

**Files:**
- Create: `src/dks/locators.py`
- Create: `tests/test_locators.py`

The `Locator` discriminated union captures the citation primitive for each doc type. Phase 1 implements all four locator types (so the citation contract is stable end-to-end) but only the Markdown variant is exercised by Phase 1 parsers. The others ride along unused until Phase 2.

- [ ] **Step 1: Write the failing tests**

`tests/test_locators.py`:
```python
import pytest
from pydantic import ValidationError

from dks.locators import (
    DocxLocator,
    ExcelLocator,
    Locator,
    MarkdownLocator,
    PdfLocator,
)


def test_pdf_locator_minimal():
    loc = PdfLocator(page=14)
    assert loc.kind == "pdf"
    assert loc.page == 14
    assert loc.section is None
    assert loc.clause is None


def test_pdf_locator_with_section_and_clause():
    loc = PdfLocator(page=14, section="3.2", clause="3.2.1")
    assert loc.section == "3.2"
    assert loc.clause == "3.2.1"


def test_pdf_locator_rejects_zero_page():
    with pytest.raises(ValidationError):
        PdfLocator(page=0)


def test_docx_locator():
    loc = DocxLocator(section="Introduction", paragraph_idx=3)
    assert loc.kind == "docx"


def test_excel_locator():
    loc = ExcelLocator(sheet="Assumptions", cells="B2:D40")
    assert loc.kind == "excel"
    assert loc.cells == "B2:D40"


def test_markdown_locator():
    loc = MarkdownLocator(heading_path=["Claims Handling", "Filing Window"], line_start=5, line_end=7)
    assert loc.kind == "md"
    assert loc.heading_path == ["Claims Handling", "Filing Window"]


def test_markdown_locator_rejects_zero_line():
    with pytest.raises(ValidationError):
        MarkdownLocator(heading_path=[], line_start=0, line_end=1)


def test_locator_discriminated_union_roundtrip():
    """Pydantic should discriminate by `kind` when parsing dicts into Locator."""
    from pydantic import TypeAdapter

    adapter = TypeAdapter(Locator)
    parsed = adapter.validate_python({"kind": "pdf", "page": 1, "section": "1.0"})
    assert isinstance(parsed, PdfLocator)
    assert parsed.section == "1.0"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_locators.py -v
```

Expected: ImportError / module not found — the file `dks/locators.py` does not yet exist.

- [ ] **Step 3: Implement `src/dks/locators.py`**

```python
"""Locator types — the citation primitive per document format.

A `Locator` carries the minimum information required to point back to a specific
span of a source document. The shape varies by document type but every variant
provides enough detail to reconstruct an audit-grade citation.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PdfLocator(BaseModel):
    kind: Literal["pdf"] = "pdf"
    page: int = Field(ge=1)
    section: str | None = None
    clause: str | None = None


class DocxLocator(BaseModel):
    kind: Literal["docx"] = "docx"
    section: str
    paragraph_idx: int = Field(ge=0)


class ExcelLocator(BaseModel):
    kind: Literal["excel"] = "excel"
    sheet: str
    cells: str  # "A1" or "A1:C12"


class MarkdownLocator(BaseModel):
    kind: Literal["md"] = "md"
    heading_path: list[str]
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


Locator = Annotated[
    PdfLocator | DocxLocator | ExcelLocator | MarkdownLocator,
    Field(discriminator="kind"),
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_locators.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/locators.py tests/test_locators.py
git commit -m "feat: define Locator union for PDF/DOCX/Excel/Markdown citation primitives"
```

---

## Task 3 — BlockRef encoding and decoding

**Files:**
- Create: `src/dks/blockref.py`
- Create: `tests/test_blockref.py`

A `BlockRef` is the opaque string form of `(source_file, locator)`. The encoded form is what callers will hold and pass through to `get_source` in Phase 3. Format per the design spec:

| Doc type | Format |
|---|---|
| PDF      | `<file>#p<page>` or `<file>#p<page>#<section>` |
| DOCX     | `<file>#§<section>#p<paragraph_idx>` |
| Excel    | `<file>#s<sheet>!<cells>` |
| Markdown | `<file>#L<start>-<end>` |

Heading path is stored on the `MarkdownLocator` but not encoded into the BlockRef (it would make refs unstable across edits); line range is the stable identifier.

- [ ] **Step 1: Write the failing tests**

`tests/test_blockref.py`:
```python
import pytest

from dks.blockref import decode_blockref, encode_blockref
from dks.locators import DocxLocator, ExcelLocator, MarkdownLocator, PdfLocator


def test_encode_pdf_minimal():
    assert encode_blockref("policies/claims.pdf", PdfLocator(page=14)) == "policies/claims.pdf#p14"


def test_encode_pdf_with_section():
    ref = encode_blockref("policies/claims.pdf", PdfLocator(page=14, section="3.2"))
    assert ref == "policies/claims.pdf#p14#3.2"


def test_encode_docx():
    ref = encode_blockref("specs/intro.docx", DocxLocator(section="Introduction", paragraph_idx=3))
    assert ref == "specs/intro.docx#§Introduction#p3"


def test_encode_excel():
    ref = encode_blockref("models/assumptions.xlsx", ExcelLocator(sheet="Mortality", cells="A1:D40"))
    assert ref == "models/assumptions.xlsx#sMortality!A1:D40"


def test_encode_markdown():
    ref = encode_blockref(
        "notes/handling.md",
        MarkdownLocator(heading_path=["A", "B"], line_start=5, line_end=7),
    )
    assert ref == "notes/handling.md#L5-7"


def test_roundtrip_pdf():
    original = PdfLocator(page=14, section="3.2")
    ref = encode_blockref("policies/claims.pdf", original)
    src, loc = decode_blockref(ref)
    assert src == "policies/claims.pdf"
    assert loc == original


def test_roundtrip_markdown():
    original = MarkdownLocator(heading_path=[], line_start=5, line_end=7)
    ref = encode_blockref("a.md", original)
    src, loc = decode_blockref(ref)
    assert src == "a.md"
    # heading_path isn't in the encoded ref, so it's empty after decode
    assert loc.line_start == 5
    assert loc.line_end == 7


def test_decode_rejects_malformed():
    with pytest.raises(ValueError, match="malformed"):
        decode_blockref("no-hash-here")


def test_decode_rejects_unknown_locator_prefix():
    with pytest.raises(ValueError, match="unknown locator"):
        decode_blockref("file.xyz#qWhatever")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_blockref.py -v
```

Expected: ImportError — `dks/blockref.py` does not exist.

- [ ] **Step 3: Implement `src/dks/blockref.py`**

```python
"""Encode / decode BlockRef strings.

A BlockRef is the canonical string form `<source_file>#<locator>` used as a
stable opaque identifier. `decode_blockref` reconstructs the source path and a
minimal Locator; some metadata that is not part of the stable identifier (e.g.
markdown heading_path) is not recovered by decode.
"""

import re

from dks.locators import DocxLocator, ExcelLocator, Locator, MarkdownLocator, PdfLocator


def encode_blockref(source_file: str, locator: Locator) -> str:
    if isinstance(locator, PdfLocator):
        suffix = f"p{locator.page}"
        if locator.section:
            suffix += f"#{locator.section}"
        return f"{source_file}#{suffix}"
    if isinstance(locator, DocxLocator):
        return f"{source_file}#§{locator.section}#p{locator.paragraph_idx}"
    if isinstance(locator, ExcelLocator):
        return f"{source_file}#s{locator.sheet}!{locator.cells}"
    if isinstance(locator, MarkdownLocator):
        return f"{source_file}#L{locator.line_start}-{locator.line_end}"
    raise TypeError(f"Unknown locator type: {type(locator).__name__}")


_PDF_RE = re.compile(r"^p(?P<page>\d+)(?:#(?P<section>.+))?$")
_DOCX_RE = re.compile(r"^§(?P<section>.+?)#p(?P<idx>\d+)$")
_EXCEL_RE = re.compile(r"^s(?P<sheet>[^!]+)!(?P<cells>.+)$")
_MD_RE = re.compile(r"^L(?P<start>\d+)-(?P<end>\d+)$")


def decode_blockref(ref: str) -> tuple[str, Locator]:
    if "#" not in ref:
        raise ValueError(f"malformed BlockRef (no '#'): {ref!r}")

    source_file, _, locator_str = ref.partition("#")
    if not locator_str:
        raise ValueError(f"malformed BlockRef (empty locator): {ref!r}")

    if m := _PDF_RE.match(locator_str):
        page = int(m.group("page"))
        section = m.group("section")
        return source_file, PdfLocator(page=page, section=section)

    if m := _DOCX_RE.match(locator_str):
        return source_file, DocxLocator(section=m.group("section"), paragraph_idx=int(m.group("idx")))

    if m := _EXCEL_RE.match(locator_str):
        return source_file, ExcelLocator(sheet=m.group("sheet"), cells=m.group("cells"))

    if m := _MD_RE.match(locator_str):
        return source_file, MarkdownLocator(
            heading_path=[],
            line_start=int(m.group("start")),
            line_end=int(m.group("end")),
        )

    raise ValueError(f"unknown locator format: {locator_str!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_blockref.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/blockref.py tests/test_blockref.py
git commit -m "feat: BlockRef encode/decode with per-doc-type formats"
```

---

## Task 4 — TypedContentItem (parser → normalizer contract)

**Files:**
- Create: `src/dks/types.py`
- Create: `tests/test_types.py`

`TypedContentItem` is the shape parsers produce and the normalizer consumes. It mirrors RAG-Anything's typed content list but slimmed to fields Phase 1 actually uses. The locator field is the discriminated `Locator` union from Task 2.

- [ ] **Step 1: Write the failing tests**

`tests/test_types.py`:
```python
import pytest
from pydantic import ValidationError

from dks.locators import MarkdownLocator
from dks.types import TypedContentItem


def test_typed_content_item_basic():
    item = TypedContentItem(
        content="Hello world",
        block_type="text",
        locator=MarkdownLocator(heading_path=["A"], line_start=1, line_end=1),
    )
    assert item.content == "Hello world"
    assert item.block_type == "text"
    assert item.locator.kind == "md"


def test_typed_content_item_rejects_empty_content():
    with pytest.raises(ValidationError):
        TypedContentItem(
            content="",
            block_type="text",
            locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
        )


def test_typed_content_item_default_block_type_is_text():
    item = TypedContentItem(
        content="x",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=1),
    )
    assert item.block_type == "text"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_types.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/dks/types.py`**

```python
"""Shared parser → normalizer contract.

`TypedContentItem` is the slim shape every parser must emit. The normalizer
turns a list of these (plus source metadata) into `NormalizedBlock`s.
"""

from typing import Literal

from pydantic import BaseModel, Field

from dks.locators import Locator

BlockType = Literal["text", "heading", "table", "list", "code"]


class TypedContentItem(BaseModel):
    content: str = Field(min_length=1)
    block_type: BlockType = "text"
    locator: Locator
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_types.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/types.py tests/test_types.py
git commit -m "feat: TypedContentItem parser→normalizer contract"
```

---

## Task 5 — NormalizedBlock and frontmatter serialization

**Files:**
- Create: `src/dks/block.py`
- Create: `tests/test_block.py`

`NormalizedBlock` is the final output of the normalizer: source file + block_id + locator + block_type + content. It serializes to a Markdown file whose frontmatter carries the citation primitive. Frontmatter is YAML-ish but we serialize via JSON-in-YAML to avoid YAML's null/string ambiguities — Pydantic's `model_dump_json` is the canonical form.

- [ ] **Step 1: Write the failing tests**

`tests/test_block.py`:
```python
from dks.block import NormalizedBlock, parse_markdown, to_markdown
from dks.locators import MarkdownLocator


def _make_block() -> NormalizedBlock:
    return NormalizedBlock(
        source_file="notes/handling.md",
        block_id="notes/handling.md#L5-7",
        locator=MarkdownLocator(heading_path=["Claims", "Filing"], line_start=5, line_end=7),
        block_type="text",
        content="Claims must be filed within 30 days.",
    )


def test_to_markdown_includes_frontmatter_and_content():
    md = to_markdown(_make_block())
    assert md.startswith("---\n")
    assert '"block_id":' in md
    assert '"source_file":' in md
    assert "Claims must be filed within 30 days." in md


def test_to_markdown_roundtrip():
    original = _make_block()
    md = to_markdown(original)
    parsed = parse_markdown(md)
    assert parsed == original


def test_parse_markdown_rejects_missing_frontmatter():
    import pytest

    with pytest.raises(ValueError, match="frontmatter"):
        parse_markdown("just some plain text\n")


def test_parse_markdown_rejects_unterminated_frontmatter():
    import pytest

    with pytest.raises(ValueError, match="frontmatter"):
        parse_markdown("---\nblock_id: x\nstill in frontmatter\n")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_block.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/dks/block.py`**

```python
"""NormalizedBlock — the citation-preserving block that the writer persists."""

import json
from typing import Literal

from pydantic import BaseModel

from dks.locators import Locator
from dks.types import BlockType

_FENCE = "---"


class NormalizedBlock(BaseModel):
    source_file: str
    block_id: str
    locator: Locator
    block_type: BlockType = "text"
    content: str


def to_markdown(block: NormalizedBlock) -> str:
    """Serialize a NormalizedBlock to its on-disk Markdown form."""
    frontmatter = block.model_dump_json(exclude={"content"}, indent=2)
    return f"{_FENCE}\n{frontmatter}\n{_FENCE}\n{block.content}\n"


def parse_markdown(text: str) -> NormalizedBlock:
    """Parse a Markdown file written by `to_markdown` back into a NormalizedBlock."""
    if not text.startswith(_FENCE + "\n"):
        raise ValueError("missing opening frontmatter fence ('---')")

    rest = text[len(_FENCE) + 1 :]
    close_idx = rest.find("\n" + _FENCE + "\n")
    if close_idx == -1:
        raise ValueError("missing closing frontmatter fence ('---')")

    frontmatter_str = rest[:close_idx]
    content = rest[close_idx + len(_FENCE) + 2 :].rstrip("\n")

    data = json.loads(frontmatter_str)
    data["content"] = content
    return NormalizedBlock.model_validate(data)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_block.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/block.py tests/test_block.py
git commit -m "feat: NormalizedBlock with JSON-frontmatter Markdown roundtrip"
```

---

## Task 6 — Citation guard

**Files:**
- Create: `src/dks/citation_guard.py`
- Create: `tests/test_citation_guard.py`

The citation guard is the structural enforcement point. A candidate block passes only if its `block_id` round-trips through `decode_blockref → encode_blockref` unchanged AND the encoded ref matches the supplied `(source_file, locator)`. This catches: hand-constructed inconsistent blocks, locator mutations after BlockRef was minted, and Phase 2 parser bugs that emit bad refs.

- [ ] **Step 1: Write the failing tests**

`tests/test_citation_guard.py`:
```python
import pytest

from dks.block import NormalizedBlock
from dks.citation_guard import CitationError, check_block
from dks.locators import MarkdownLocator, PdfLocator


def _good_block() -> NormalizedBlock:
    return NormalizedBlock(
        source_file="a.md",
        block_id="a.md#L1-3",
        locator=MarkdownLocator(heading_path=[], line_start=1, line_end=3),
        block_type="text",
        content="hi",
    )


def test_check_passes_on_valid_block():
    check_block(_good_block())  # must not raise


def test_check_rejects_mismatched_blockref():
    bad = _good_block().model_copy(update={"block_id": "a.md#L99-99"})
    with pytest.raises(CitationError, match="block_id does not match locator"):
        check_block(bad)


def test_check_rejects_mismatched_source_file():
    block = _good_block().model_copy(update={"source_file": "different.md"})
    with pytest.raises(CitationError, match="source_file"):
        check_block(block)


def test_check_passes_on_pdf_block():
    block = NormalizedBlock(
        source_file="x.pdf",
        block_id="x.pdf#p5#3.2",
        locator=PdfLocator(page=5, section="3.2"),
        block_type="text",
        content="hello",
    )
    check_block(block)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_citation_guard.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/dks/citation_guard.py`**

```python
"""Citation guard — rejects NormalizedBlocks whose block_id is inconsistent
with their (source_file, locator). Structural enforcement of citation discipline.
"""

from dks.block import NormalizedBlock
from dks.blockref import decode_blockref, encode_blockref


class CitationError(ValueError):
    """Raised when a block fails the citation completeness/consistency check."""


def check_block(block: NormalizedBlock) -> None:
    """Raise CitationError if the block_id is not the canonical encoding
    of (source_file, locator). Returns None on success.
    """
    expected_ref = encode_blockref(block.source_file, block.locator)
    if block.block_id != expected_ref:
        raise CitationError(
            f"block_id does not match locator: got {block.block_id!r}, expected {expected_ref!r}"
        )

    decoded_source, _ = decode_blockref(block.block_id)
    if decoded_source != block.source_file:
        raise CitationError(
            f"block_id source_file does not match block source_file: "
            f"{decoded_source!r} vs {block.source_file!r}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_citation_guard.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/citation_guard.py tests/test_citation_guard.py
git commit -m "feat: citation_guard.check_block enforces block_id ↔ locator consistency"
```

---

## Task 7 — Normalizer

**Files:**
- Create: `src/dks/normalizer.py`
- Create: `tests/test_normalizer.py`

The normalizer takes a source filename and a list of `TypedContentItem` (from a parser) and returns a list of `NormalizedBlock`. For every item it computes the `block_id` (via `encode_blockref`) and runs `check_block`. Any failure halts ingestion — Phase 1 does not silently drop blocks.

- [ ] **Step 1: Write the failing tests**

`tests/test_normalizer.py`:
```python
import pytest

from dks.locators import MarkdownLocator
from dks.normalizer import normalize
from dks.types import TypedContentItem


def test_normalize_simple():
    items = [
        TypedContentItem(
            content="Hello world",
            locator=MarkdownLocator(heading_path=["A"], line_start=1, line_end=1),
        ),
        TypedContentItem(
            content="Goodbye",
            locator=MarkdownLocator(heading_path=["A"], line_start=3, line_end=3),
        ),
    ]
    blocks = normalize(source_file="notes.md", items=items)
    assert len(blocks) == 2
    assert blocks[0].block_id == "notes.md#L1-1"
    assert blocks[1].block_id == "notes.md#L3-3"
    assert blocks[0].content == "Hello world"
    assert blocks[0].source_file == "notes.md"


def test_normalize_empty_list_returns_empty():
    assert normalize(source_file="x.md", items=[]) == []


def test_normalize_propagates_block_type():
    items = [
        TypedContentItem(
            content="# Title",
            block_type="heading",
            locator=MarkdownLocator(heading_path=["Title"], line_start=1, line_end=1),
        ),
    ]
    [block] = normalize(source_file="x.md", items=items)
    assert block.block_type == "heading"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_normalizer.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/dks/normalizer.py`**

```python
"""Normalizer — turns a parser's TypedContentItem list into NormalizedBlocks
with citation-checked block_ids.
"""

from collections.abc import Iterable

from dks.block import NormalizedBlock
from dks.blockref import encode_blockref
from dks.citation_guard import check_block
from dks.types import TypedContentItem


def normalize(source_file: str, items: Iterable[TypedContentItem]) -> list[NormalizedBlock]:
    blocks: list[NormalizedBlock] = []
    for item in items:
        block_id = encode_blockref(source_file, item.locator)
        block = NormalizedBlock(
            source_file=source_file,
            block_id=block_id,
            locator=item.locator,
            block_type=item.block_type,
            content=item.content,
        )
        check_block(block)  # raises CitationError on inconsistency
        blocks.append(block)
    return blocks
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_normalizer.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/normalizer.py tests/test_normalizer.py
git commit -m "feat: normalizer turns TypedContentItem list into citation-checked NormalizedBlocks"
```

---

## Task 8 — Writer

**Files:**
- Create: `src/dks/writer.py`
- Create: `tests/test_writer.py`

The writer persists `NormalizedBlock`s to disk under `<output_dir>/<source_basename>/`. Each block becomes one `.md` file whose name is a filesystem-safe version of its block_id. The writer is idempotent — re-running it overwrites blocks rather than appending.

- [ ] **Step 1: Write the failing tests**

`tests/test_writer.py`:
```python
from pathlib import Path

from dks.block import NormalizedBlock, parse_markdown
from dks.locators import MarkdownLocator
from dks.writer import write_blocks, safe_filename


def _block(source: str, start: int, end: int, content: str) -> NormalizedBlock:
    loc = MarkdownLocator(heading_path=[], line_start=start, line_end=end)
    from dks.blockref import encode_blockref

    return NormalizedBlock(
        source_file=source,
        block_id=encode_blockref(source, loc),
        locator=loc,
        block_type="text",
        content=content,
    )


def test_write_blocks_creates_files(tmp_path: Path):
    blocks = [
        _block("notes.md", 1, 1, "first"),
        _block("notes.md", 3, 5, "second"),
    ]
    written = write_blocks(blocks, output_dir=tmp_path)

    assert len(written) == 2
    for path in written:
        assert path.exists()
        assert path.parent.name == "notes.md"
        # roundtrip
        parsed = parse_markdown(path.read_text())
        assert parsed.source_file == "notes.md"


def test_write_blocks_overwrites_on_rerun(tmp_path: Path):
    [original] = write_blocks([_block("a.md", 1, 1, "v1")], output_dir=tmp_path)
    [rewritten] = write_blocks([_block("a.md", 1, 1, "v2")], output_dir=tmp_path)
    assert original == rewritten
    parsed = parse_markdown(rewritten.read_text())
    assert parsed.content == "v2"


def test_safe_filename_strips_unsafe_chars():
    assert safe_filename("a/b.md#L1-3") == "a__b.md__L1-3"
    assert safe_filename("x.pdf#p5#3.2") == "x.pdf__p5__3.2"


def test_write_blocks_empty_list_no_op(tmp_path: Path):
    assert write_blocks([], output_dir=tmp_path) == []
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_writer.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/dks/writer.py`**

```python
"""Writer — persists NormalizedBlocks to disk.

Layout: <output_dir>/<source_basename>/<safe_block_filename>.md
where source_basename is the relative source path with separators preserved as
folder structure under output_dir.
"""

from collections.abc import Iterable
from pathlib import Path

from dks.block import NormalizedBlock, to_markdown


def safe_filename(s: str) -> str:
    """Make a string safe for filesystem use: replace / and # with __."""
    return s.replace("/", "__").replace("#", "__")


def write_blocks(blocks: Iterable[NormalizedBlock], output_dir: Path) -> list[Path]:
    output_dir = Path(output_dir)
    written: list[Path] = []
    for block in blocks:
        source_basename = Path(block.source_file).name
        target_dir = output_dir / source_basename
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{safe_filename(block.block_id)}.md"
        target.write_text(to_markdown(block))
        written.append(target)
    return written
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_writer.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/writer.py tests/test_writer.py
git commit -m "feat: writer persists NormalizedBlocks as frontmatter Markdown files"
```

---

## Task 9 — Markdown pass-through parser

**Files:**
- Create: `src/dks/parsers/markdown.py`
- Create: `tests/parsers/test_markdown.py`

The Markdown parser reads a `.md` file and emits one `TypedContentItem` per paragraph. It tracks heading paths so each paragraph knows where it sits in the doc's heading hierarchy. Code fences and lists are treated as single blocks; later phases can refine. The output drives a `MarkdownLocator` for each item.

Algorithm:
1. Read file as lines.
2. Walk lines, maintaining a heading path (list[str]).
3. On a heading line, update heading_path at the appropriate depth.
4. On a blank-line boundary, emit any accumulated paragraph as one `TypedContentItem`.
5. Headings are themselves emitted as `block_type="heading"` items so they're searchable.

- [ ] **Step 1: Write the failing tests**

`tests/parsers/test_markdown.py`:
```python
from pathlib import Path

from dks.parsers.markdown import parse_markdown_file


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_simple_markdown():
    items = parse_markdown_file(FIXTURES / "sample_simple.md")
    assert len(items) == 1
    assert items[0].content == "This is a single paragraph with no headings."
    assert items[0].locator.kind == "md"
    assert items[0].locator.heading_path == []
    assert items[0].block_type == "text"


def test_parse_markdown_with_headings():
    items = parse_markdown_file(FIXTURES / "sample_with_headings.md")

    # We expect:
    #   heading "Claims Handling"
    #   paragraph "Claims must be filed..."
    #   heading "Filing Window"
    #   paragraph "Subject to subsection..."
    #   heading "Extensions"
    #   paragraph "Only the regulator..."
    assert len(items) == 6
    headings = [i for i in items if i.block_type == "heading"]
    paragraphs = [i for i in items if i.block_type == "text"]
    assert len(headings) == 3
    assert len(paragraphs) == 3

    # The paragraph under H2 should have a heading_path of length 2
    filing_paragraph = next(p for p in paragraphs if "Subject to subsection" in p.content)
    assert filing_paragraph.locator.heading_path == ["Claims Handling", "Filing Window"]

    # The paragraph under H3 should have a heading_path of length 3
    ext_paragraph = next(p for p in paragraphs if "Only the regulator" in p.content)
    assert ext_paragraph.locator.heading_path == ["Claims Handling", "Filing Window", "Extensions"]


def test_parse_markdown_line_ranges_are_one_indexed_and_inclusive(tmp_path):
    src = tmp_path / "x.md"
    src.write_text("alpha\nbeta\n\ngamma\n")
    items = parse_markdown_file(src)
    # "alpha\nbeta" is the first paragraph (lines 1-2); "gamma" is the second (line 4)
    assert items[0].locator.line_start == 1
    assert items[0].locator.line_end == 2
    assert items[1].locator.line_start == 4
    assert items[1].locator.line_end == 4
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/parsers/test_markdown.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/dks/parsers/markdown.py`**

```python
"""Markdown pass-through parser.

Walks a .md file line by line, maintaining a heading path, and emits one
TypedContentItem per heading and per paragraph. Code fences and list blocks
are treated as paragraphs in Phase 1; refinement is a Phase 2 concern.
"""

import re
from pathlib import Path

from dks.locators import MarkdownLocator
from dks.types import TypedContentItem

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def parse_markdown_file(path: Path) -> list[TypedContentItem]:
    lines = Path(path).read_text().splitlines()
    items: list[TypedContentItem] = []
    heading_path: list[str] = []
    para_buf: list[str] = []
    para_start: int | None = None

    def flush_paragraph(end_line: int) -> None:
        nonlocal para_buf, para_start
        if para_buf and para_start is not None:
            items.append(
                TypedContentItem(
                    content="\n".join(para_buf),
                    block_type="text",
                    locator=MarkdownLocator(
                        heading_path=list(heading_path),
                        line_start=para_start,
                        line_end=end_line,
                    ),
                )
            )
        para_buf = []
        para_start = None

    for idx, line in enumerate(lines, start=1):
        m = _HEADING_RE.match(line)
        if m:
            flush_paragraph(idx - 1)
            level = len(m.group(1))
            title = m.group(2)
            # Truncate heading_path to depth = level-1, then append
            heading_path = heading_path[: level - 1] + [title]
            items.append(
                TypedContentItem(
                    content=line,
                    block_type="heading",
                    locator=MarkdownLocator(
                        heading_path=list(heading_path),
                        line_start=idx,
                        line_end=idx,
                    ),
                )
            )
        elif line.strip() == "":
            flush_paragraph(idx - 1)
        else:
            if para_start is None:
                para_start = idx
            para_buf.append(line)

    flush_paragraph(len(lines))
    return items
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/parsers/test_markdown.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/parsers/markdown.py tests/parsers/test_markdown.py
git commit -m "feat: markdown parser with heading-path tracking and line ranges"
```

---

## Task 10 — Parser registry

**Files:**
- Modify: `src/dks/parsers/__init__.py`
- Create: `tests/parsers/test_registry.py`

A tiny registry maps a file suffix to the parser function. Phase 1 has one entry (`.md`). Phase 2 will add `.pdf`, `.docx`, `.xlsx`. Centralizing the dispatch here keeps the CLI thin.

- [ ] **Step 1: Write the failing tests**

`tests/parsers/test_registry.py`:
```python
from pathlib import Path

import pytest

from dks.parsers import get_parser


def test_get_parser_for_markdown():
    parser = get_parser(Path("notes.md"))
    assert callable(parser)


def test_get_parser_for_uppercase_extension():
    parser = get_parser(Path("notes.MD"))
    assert callable(parser)


def test_get_parser_raises_on_unknown_extension():
    with pytest.raises(ValueError, match="no parser"):
        get_parser(Path("mystery.bin"))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/parsers/test_registry.py -v
```

Expected: AttributeError or ImportError.

- [ ] **Step 3: Implement `src/dks/parsers/__init__.py`**

```python
"""Parser registry: dispatch a file path to the right parser by suffix."""

from collections.abc import Callable
from pathlib import Path

from dks.parsers.markdown import parse_markdown_file
from dks.types import TypedContentItem

ParserFn = Callable[[Path], list[TypedContentItem]]

_REGISTRY: dict[str, ParserFn] = {
    ".md": parse_markdown_file,
}


def get_parser(path: Path) -> ParserFn:
    suffix = path.suffix.lower()
    if suffix not in _REGISTRY:
        raise ValueError(f"no parser registered for suffix {suffix!r} (path={path})")
    return _REGISTRY[suffix]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/parsers/test_registry.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/dks/parsers/__init__.py tests/parsers/test_registry.py
git commit -m "feat: parser registry (suffix → parser fn)"
```

---

## Task 11 — Ingest CLI

**Files:**
- Create: `src/dks/cli.py`
- Create: `tests/test_cli.py`
- Modify: `pyproject.toml` (add console script entrypoint)

The CLI ties parser + normalizer + writer. Single command: `dks ingest <source-path> [--output-dir DIR]`. Default output is `./normalized/`. Stdout summary tells the operator how many blocks landed where.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
from pathlib import Path

from typer.testing import CliRunner

from dks.cli import app

runner = CliRunner()


def test_ingest_markdown_creates_normalized_files(tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# Heading\n\nA paragraph.\n")
    output = tmp_path / "out"

    result = runner.invoke(app, ["ingest", str(source), "--output-dir", str(output)])
    assert result.exit_code == 0, result.output
    assert "wrote 2 blocks" in result.output

    files = list((output / "notes.md").glob("*.md"))
    assert len(files) == 2


def test_ingest_missing_file_exits_nonzero(tmp_path):
    result = runner.invoke(app, ["ingest", str(tmp_path / "nope.md")])
    assert result.exit_code != 0


def test_ingest_unsupported_extension_exits_nonzero(tmp_path):
    source = tmp_path / "x.bin"
    source.write_bytes(b"\x00\x01")
    result = runner.invoke(app, ["ingest", str(source)])
    assert result.exit_code != 0
    assert "no parser" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/dks/cli.py`**

```python
"""Typer CLI: `dks ingest <path>`."""

from pathlib import Path

import typer

from dks.normalizer import normalize
from dks.parsers import get_parser
from dks.writer import write_blocks

app = typer.Typer(no_args_is_help=True)


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="Source file to ingest."),
    output_dir: Path = typer.Option(
        Path("normalized"), "--output-dir", "-o", help="Where to write normalized blocks."
    ),
) -> None:
    """Parse, normalize, and persist a source document."""
    if not path.exists() or not path.is_file():
        typer.echo(f"error: file not found: {path}", err=True)
        raise typer.Exit(code=2)

    try:
        parser = get_parser(path)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=2) from e

    items = parser(path)
    blocks = normalize(source_file=path.name, items=items)
    written = write_blocks(blocks, output_dir=output_dir)
    typer.echo(f"wrote {len(written)} blocks to {output_dir}/{path.name}/")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Add console script entrypoint to pyproject.toml**

Append to the `[project]` section (above `[dependency-groups]`):

```toml
[project.scripts]
dks = "dks.cli:app"
```

Then re-sync:

```bash
uv sync --all-groups
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Smoke test the CLI manually**

```bash
uv run dks ingest tests/fixtures/sample_with_headings.md --output-dir /tmp/dks-smoke
ls /tmp/dks-smoke/sample_with_headings.md/
```

Expected: prints "wrote 6 blocks ..." and lists 6 `.md` files.

- [ ] **Step 7: Commit**

```bash
git add src/dks/cli.py tests/test_cli.py pyproject.toml
git commit -m "feat: dks ingest CLI ties parser → normalizer → writer"
```

---

## Task 12 — Full-suite verification and cleanup

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass (target: ~37 passing across 8 test files).

- [ ] **Step 2: Run ruff and mypy**

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
```

Fix any reported issues inline. If mypy complains about Pydantic discriminated-union narrowing, the canonical fix is `isinstance` checks (already used) — re-read the error before editing.

- [ ] **Step 3: Run end-to-end on the design spec itself**

This is a real-world smoke test: feed the project's own design spec through the pipeline.

```bash
uv run dks ingest docs/superpowers/specs/2026-05-21-domain-knowledge-skill-design.md --output-dir /tmp/dks-selftest
ls /tmp/dks-selftest/
```

Expected: many `.md` files, one per heading + paragraph. Inspect a few; confirm the frontmatter carries source_file, block_id, locator, and the content is the original prose.

- [ ] **Step 4: Commit any lint/format fixes**

```bash
git status
# if anything is dirty:
git add -A
git commit -m "chore: lint + format cleanup"
```

- [ ] **Step 5: Push and tag the phase boundary**

```bash
git push
git tag phase-1-complete
git push --tags
```

---

## Self-review — handled inline during writing

- **Spec coverage (Phase 1 portion):** Layers 1 (ingestion — Markdown only this phase) and 2 (normalization) are covered. PageIndex (Layer 3), wiki (Layer 4), skill (Layer 5), eval (Layer 6) are explicitly deferred to Phases 2 and 3. The `Locator` union includes PDF/DOCX/Excel variants so the contract is stable for Phase 2.
- **Placeholder scan:** every step contains the code or command to run. No "TBD", no "add appropriate validation," no "similar to Task N."
- **Type consistency:** `Locator` (Task 2) is used by `TypedContentItem` (Task 4) and `NormalizedBlock` (Task 5). `encode_blockref` (Task 3) is used by `citation_guard` (Task 6) and `normalizer` (Task 7). `TypedContentItem` is produced by parsers (Task 9) and consumed by normalizer (Task 7). All names cross-check.
- **What's deliberately not here:** any LLM call (we're pre-LLM Phase 1), embeddings, knowledge graph, retrieval logic, eval framework. All deferred.

## What Phase 1 leaves for Phase 2

- PDF parser (MinerU) — emits `TypedContentItem` with `PdfLocator`. Plugs into the parser registry.
- DOCX parser (Docling) — emits with `DocxLocator`.
- Excel parser (openpyxl/pandas) — emits with `ExcelLocator`.
- PageIndex tree builder — LLM-driven, sidecar JSON per long source file.
- Wiki compile + lint — LLM-driven, citation-preserving summaries that link to block_ids.
- A `WikiEntry` type and writer (analogous to `NormalizedBlock` + writer).

None of these require changes to Phase 1 modules. The `parser registry` (Task 10) is the only Phase-1 file Phase 2 will touch, to register the new suffixes.
