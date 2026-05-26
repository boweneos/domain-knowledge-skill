# Source Classification & PII Guardrails — v0.3.0 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Add an opt-in classification system that tags each ingested source with a sensitivity level and enforces guardrails downstream. Default behaviour unchanged — guardrails activate only when the operator explicitly classifies a source as `confidential` or `restricted`.

**Version:** 0.2.3 → **0.3.0** (minor bump: new field on `NormalizedBlock` and `WikiEntry`, new CLI flag, new semantic restrictions).

**Why minor (not patch):** The classification field is additive and defaults preserve existing behaviour, so it's not a breaking-API change. But the new semantic restrictions (global-write rejection, skill output changes) are user-visible behaviour and deserve a minor bump.

---

## Classification levels

```
public        — fully public material (regulator standards, ASIC notices). Informational only.
internal      — DEFAULT. Internal business rules. No restrictions.
confidential  — may contain incidental PII or sensitive business detail. Restricted.
restricted    — contains PII or commercial-in-confidence. Strictest restrictions.
```

Sort order (for "stricter than" comparisons): `public < internal < confidential < restricted`.

## Architecture

### Data model

`NormalizedBlock.classification: Classification = "internal"` — Pydantic default keeps existing blocks valid; new ingests can override per-source.

`WikiEntry.classification: Classification = "internal"` — wiki entries declare their own classification, which must be ≥ the max classification of their cited blocks (lint enforced).

### Guardrails (the semantic changes)

1. **Global-write rejection at ingest.** `dks ingest --classification {confidential,restricted} --write-global` exits 2 with explanatory error. Sensitive content stays in the project layer. Same rule for `dks wiki write --write-global` if `classification` ≥ confidential.
2. **`dks blocks get` stderr warning.** For confidential/restricted blocks, emit `WARN: block <id> classification=<level>; verify requester is authorized`. Block content still returned — the warning is awareness, not a block.
3. **Skill behaviour changes.** `dks-search` skill instructions: for `confidential` blocks, return citation pointer + brief summary; for `restricted`, return only "rule exists at <citation>, consult source directly" — never surface block content. `dks-compile-wiki` skill: any wiki article citing restricted material must NOT include verbatim content from those blocks, and the wiki entry's own `classification` must be ≥ the max of cited blocks.
4. **Lint check.** `dks-lint-wiki` adds a "Classification leaks" section: for each wiki entry, verify entry classification ≥ max(cited block classifications); flag mismatches.
5. **`dks layers list` breakdown (optional).** Add a per-layer count of blocks by classification, to give operators a quick "do I have sensitive content in the wrong layer?" check.

### Backward compatibility

- Pydantic defaults keep old NormalizedBlock/WikiEntry files valid.
- No CLI flag is *required* — existing scripts keep working.
- Default classification is `internal` so existing skills aren't disrupted.

---

## Task A — Types + storage + normalizer (Python core)

**Files:**
- `src/dks/types.py` — `Classification` literal + `classification_rank()` helper
- `src/dks/block.py` — `NormalizedBlock` gains `classification` field
- `src/dks/store/wiki.py` — `WikiEntry` gains `classification` field
- `src/dks/normalizer.py` — `normalize(source_file, items, classification="internal")` propagates to all blocks
- Tests in `tests/test_block.py`, `tests/store/test_wiki.py`, `tests/test_normalizer.py`

Steps (TDD as usual):

1. **Add `Classification` literal + rank helper to `src/dks/types.py`:**
   ```python
   Classification = Literal["public", "internal", "confidential", "restricted"]
   _CLASSIFICATION_ORDER: tuple[Classification, ...] = ("public", "internal", "confidential", "restricted")

   def classification_rank(c: Classification) -> int:
       return _CLASSIFICATION_ORDER.index(c)
   ```

2. **Extend `NormalizedBlock`:**
   ```python
   class NormalizedBlock(BaseModel):
       source_file: str
       block_id: str
       locator: Locator
       block_type: BlockType = "text"
       content: str
       classification: Classification = "internal"
   ```

3. **Extend `WikiEntry`:**
   ```python
   class WikiEntry(BaseModel):
       topic: str
       slug: str
       source_refs: list[str]
       body: str
       compiled_at: str | None = None
       classification: Classification = "internal"
   ```

4. **Update normalizer:**
   ```python
   def normalize(
       source_file: str,
       items: Iterable[TypedContentItem],
       classification: Classification = "internal",
   ) -> list[NormalizedBlock]:
       ...
       block = NormalizedBlock(
           source_file=source_file,
           block_id=block_id,
           locator=item.locator,
           block_type=item.block_type,
           content=item.content,
           classification=classification,
       )
       ...
   ```

5. **Tests:**
   - Block roundtrip preserves classification.
   - Wiki entry roundtrip preserves classification.
   - Normalizer propagates classification to all emitted blocks.
   - Default classification is `internal`.
   - `classification_rank("restricted") > classification_rank("internal")`.

Commit: `feat: add Classification type to NormalizedBlock + WikiEntry + normalizer (v0.3.0 part 1)`

---

## Task B — CLI guardrails

**Files:**
- `src/dks/cli.py` — ingest `--classification`, blocks get WARN, wiki write `--classification`, global-write rejection
- Tests in `tests/test_cli.py`

Steps:

1. **`dks ingest` accepts `--classification {public,internal,confidential,restricted}`** (default: `internal`). Passes through to `normalize()`. If `--write-global` AND classification is `confidential` or `restricted`, exit 2 with error:
   ```
   error: cannot write 'confidential' content to the global layer; use the project layer (default)
   ```

2. **`dks blocks get` emits stderr WARN** for confidential/restricted blocks:
   ```
   WARN: block <id> classification=<level>; verify requester is authorized
   ```
   Block content still returned in stdout JSON; the new `classification` field appears in the JSON `block` object naturally via `model_dump`.

3. **`dks wiki write` accepts `--classification`** (default: `internal`). Same global-write rejection as ingest.

4. **(Optional, defer if pressed for time)** `dks layers list` adds per-layer classification breakdown:
   ```json
   {
     "name": "project", ..., "classification_breakdown": {
       "public": 0, "internal": 12, "confidential": 3, "restricted": 0
     }
   }
   ```
   Counts derived by walking each layer's `normalized/` and reading frontmatter.

5. **Tests:**
   - `dks ingest --classification confidential` writes blocks with that field set.
   - `dks ingest --classification restricted --write-global` exits 2 with the expected error.
   - `dks ingest --classification internal --write-global` (default classification) succeeds.
   - `dks blocks get` on a confidential block emits WARN; on internal does not.
   - `dks wiki write --classification confidential --write-global` exits 2.

Commit: `feat: CLI guardrails for classified content (v0.3.0 part 2)`

---

## Task C — Skill prompts + lint check

**Files:**
- `dks/skills/dks-search/SKILL.md`
- `dks/skills/dks-compile-wiki/SKILL.md`
- `dks/skills/dks-lint-wiki/SKILL.md`
- `dks/commands/ingest.md` (mention the new flag)

Updates:

1. **`dks-search`** — new section "Handling classified content":
   - For `confidential`: cite the block_id, summarise the rule in your own words, but do not paste verbatim block content into the answer.
   - For `restricted`: say *"A rule on [topic] exists at [block_id]. Per its restricted classification, I won't surface its content here — please consult the source directly."* Stop. Do not summarise. Do not paraphrase.
   - In the answer's `Sources:` block, prepend the classification: `[@ project, confidential] <block_id> — ...`

2. **`dks-compile-wiki`** — new constraint:
   - The wiki entry's classification must be ≥ the strictest classification of any cited block. (Pass `--classification` to `dks wiki write` accordingly.)
   - For entries citing `confidential` material, paraphrase rather than quote.
   - For entries citing `restricted` material, do NOT include block content at all — write a "see source" pointer with the citation. (This is rare; most wiki entries should not cite restricted material.)

3. **`dks-lint-wiki`** — new report section "Classification leaks":
   - For each wiki entry, fetch each cited block's classification (via `dks blocks get`).
   - Compute `max_cited = max(classification_rank for each cited block)`.
   - If entry's own classification < `max_cited`, flag as a leak: *"entry `<slug>` is classified `<entry_class>` but cites `<n>` blocks at `<higher_class>` — wiki should be reclassified up or the cited material removed."*
   - Add to the Summary line: `- classification leaks: N`.

4. **`/dks:ingest` command** — mention `--classification` flag in the procedure.

Commit: `docs: skills updated for classification guardrails (v0.3.0 part 3)`

---

## Task D — Version bump, README/USAGE, smoke

**Files:**
- `pyproject.toml`, `src/dks/__init__.py`, `dks/.claude-plugin/plugin.json` → `0.3.0`
- `README.md` — status table row for v0.3.0; CLI reference gains `--classification` flag note
- `docs/USAGE.md` — new section after "Cascaded KB layers" called "Source classification & PII guardrails"

USAGE section content:

```markdown
## Source classification & PII guardrails

`dks` supports opt-in classification of ingested sources, with downstream guardrails to keep sensitive content from leaking across layers or into agent output.

### Levels

| Level | Use for | Restrictions |
|---|---|---|
| `public` | regulator standards, public guidance | none |
| `internal` (DEFAULT) | internal business rules, policy docs | none |
| `confidential` | docs with incidental PII or sensitive business detail | cannot write to global layer; consumer skill paraphrases instead of quoting |
| `restricted` | docs containing real PII or commercial-in-confidence | cannot write to global layer; consumer skill only points at source, never surfaces content |

### Setting classification at ingest

\`\`\`bash
dks ingest path/to/policy.pdf --classification internal      # default; equivalent to no flag
dks ingest path/to/audit.pdf --classification confidential
dks ingest path/to/claim-sample.pdf --classification restricted
\`\`\`

The classification applies to every block emitted from that source. To revise, re-ingest with the new flag (overwrites idempotently).

### What changes downstream

- **Global-write rejection:** `dks ingest --classification confidential --write-global` (or `restricted`) exits 2 with an error. Sensitive content stays in the project layer.
- **`dks blocks get` warning:** classified blocks emit `WARN: block <id> classification=<level>; verify requester is authorized` to stderr. Content still returned — the warning is for the operator's awareness.
- **`dks-search` skill behaviour:** for confidential blocks, the skill paraphrases the rule with a citation rather than pasting verbatim content. For restricted blocks, it returns only "a rule exists at [citation], consult the source directly" and abstains from surfacing content.
- **Wiki classification propagation:** a wiki entry citing confidential or restricted blocks must itself be classified at least as strictly (lint enforces this).

### What classification doesn't do

- **Doesn't redact PII automatically.** If you ingest a doc with real customer names, those names land verbatim in `normalized/`. Classification gates *output*, not *storage*. For true redaction, run a redaction pass upstream of `raw/`.
- **Doesn't replace access controls on the filesystem.** Your `~/.dks/` and `<project>/.dks/` directories should still have appropriate filesystem permissions.
- **Doesn't classify legacy blocks.** Blocks ingested before v0.3.0 default to `internal`. Re-ingest with `--classification` to reclassify.

### When to use which level

- Default to `internal` for the bulk of policy and rule documents.
- Reach for `confidential` when a document includes incidental sensitive detail (named example claimants in training material; named internal stakeholders; commercial terms in vendor contracts) that you'd rather not have the LLM quote verbatim into PR descriptions or commit messages.
- Reach for `restricted` for documents containing real PII (claim files, audit reports referencing named claimants) — *and consider whether such documents belong in `dks` at all*. Classification is a backstop, not a substitute for redacting upstream.
```

Smoke test in product-engine to verify:
- Ingest a `--classification confidential` doc, blocks get emits WARN
- Try `--write-global` with restricted → exit 2
- `dks layers list` (if breakdown is shipped) shows the new field

Commit: `chore: bump to 0.3.0; classification docs + smoke verification`

---

## Final summary

- Bump 0.2.3 → 0.3.0
- ~10 new tests
- 3 SKILL.md files updated
- README + USAGE updated
- Carryover notes get a new entry (#10 or similar) documenting that classification guardrails landed as a real feature, not as a follow-up to be revisited
- Push branch, tag `v0.3.0`, merge to main, push tag
