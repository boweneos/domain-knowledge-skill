# Phase 2 Carryovers from Phase 1

Notes from the Phase 1 final review (sonnet, 2026-05-21). All five items are **non-blocking for Phase 2 to begin**, but each is a real decision to revisit before Phase 2 ships.

## Status (updated 2026-05-25)

| # | Item | Status | Where addressed |
|---|---|---|---|
| 1 | `source_file` scoping (basename collision) | ✅ addressed | Phase 2 Task 0: `dks ingest --root <dir>` computes relative path |
| 2 | `PdfLocator.clause` unused by encoder | ✅ addressed | Phase 2 Task 0: clause now encoded as `<file>#p<page>#<section>#<clause>`; `_PDF_RE` updated |
| 3 | BOM handling in Markdown parser | ✅ addressed | Phase 2 Task 0: `read_text(encoding="utf-8-sig")` |
| 4 | `heading_path` lossy in `decode_blockref` | ✅ fixed in 0.2.3 | Loud docstring on `decode_blockref` explains the intentional lossy behaviour and directs callers to `store.blocks.get_block` for the full locator. Explicit roundtrip test pins down the behaviour (heading_path=[] after decode, line range preserved). |
| 5 | `block_type` forward declarations (`table`/`list`/`code`) | ✅ fixed in 0.2.3 | DOCX: `_block_type_from_label` maps all Docling labels (header→heading, list/enumeration→list, table→table, code→code, else→text). Markdown: code-fence detection (``` and ~~~) emits block_type='code'; unterminated fences handled gracefully. PDF: docstring explicitly notes pypdf flat extraction cannot detect structure; block_type always 'text'. |
| 6 | Cross-field validator on `MarkdownLocator` (`line_end >= line_start`) | ✅ fixed in 0.2.3 | `@model_validator(mode="after")` on `MarkdownLocator` enforces `line_end >= line_start`; equality permitted (single-line blocks). Two tests cover rejection and equality cases. |

Items 1-3 closed in Phase 2; items 4-6 closed in 0.2.3 (carryover-456 branch).

## Findings from Phase 4 + real-world testing (2026-05-26)

| # | Item | Status | Detail |
|---|---|---|---|
| 7 | Auto-discovery walker matched `~/.dks` (global default) as project | ✅ fixed in 0.2.1 | When a repo has no `.dks/` of its own and the user has the default global at `~/.dks/`, the walker used to climb past `$HOME` and treat the global location as the project layer — both layers resolved to the same dir, every read tagged `"project"`. Fix: `resolve_layers` now resolves global first and passes it as a `skip` to `_auto_discover_project`. Two regression tests in `tests/test_layers.py`. |
| 8 | Content-divergence warning when project shadows global | ✅ fixed in 0.2.2 | `get_block` now returns `BlockFetchResult(block, layer, shadows)`. CLI emits stderr `WARN: block <id> in layer <high> shadows <low> with different content`. JSON output gains a `shadows` field. Identical-content shadows are recorded but don't warn. Lint skill's report template gains a "Divergent shadows" section. |
| 9 | `dks layers list` introspection subcommand | ✅ fixed in 0.2.2 | New CLI subcommand prints active layers as JSON: `{name, base, source, exists}` per layer. `source` is one of `explicit`, `env`, `auto-discover`, or `default`. Backed by a new `resolution: dict[str, str]` field on `KbLayers` populated by `resolve_layers`. Plus `/dks:layers` slash command. |
| 10 | PII handling / source classification guardrails | ✅ shipped in 0.3.0 | Real architectural question raised during operator review. Designed and shipped as opt-in classification (`--classification {public,internal,confidential,restricted}`) with downstream guardrails: global-write rejection for confidential/restricted, stderr WARN on `dks blocks get`, consumer-skill paraphrase/point-only behaviour, lint check for classification leaks. Default `internal` preserves all prior behaviour. Full plan: `docs/superpowers/plans/2026-05-26-classification-v0.3.0.md`. |
| 11 | Walker corner case: `--no-global` makes walker match `~/.dks` as project | ✅ fixed in 0.3.3 | Even with the 0.2.1 walker-skip fix, `dks --no-global` set `resolved_global_base=None`, so the walker had nothing to skip → auto-discovery climbed past `$HOME` and matched the global default location as project. Fix: always compute the skip path (regardless of `include_global`); only layer EXPOSURE depends on the flag. Regression test `test_walker_skips_global_default_even_when_no_global`. |
| 12 | `--redact-pii` install hint was wrong in practice | ✅ fixed in 0.3.3 | Real operator hit during OneDrive mass-ingest. Shipped hint said `uv tool install --with presidio... dks` + `python -m spacy download`, but (a) `--reinstall` is required if dks is already installed without extras, (b) `python -m spacy download` doesn't work in a uv tool venv (no pip). Fix: `_missing_dep_message()` + USAGE now use `uv tool install --reinstall --with presidio-analyzer --with presidio-anonymizer --with "en-core-web-lg @ <wheel-url>" dks`. Also added `[[tool.mypy.overrides]]` so missing presidio stubs are tolerated in the default install (no `[redact]` extra). |

## 1. `source_file` scoping (collision risk)

`cli.ingest` currently passes `path.name` (basename) as `source_file`. Two files with the same name in different directories produce colliding `block_id`s and colliding output filenames.

**Decision needed before Phase 2 multi-file ingestion:** settle on relative-path-from-repo-root as the canonical `source_file` string and apply it consistently. Changing this later invalidates all stored `block_id`s.

## 2. `PdfLocator.clause` field is unused by encoder

`PdfLocator` carries an optional `clause` field, but `encode_blockref` only includes `section` in the output string. Two blocks at the same `(page, section)` but different `clause` values would receive the same `block_id`.

**Decision before Phase 2 PDF parser lands:** either encode `clause` into the BlockRef format, or drop the field entirely. Don't ship a parser that exercises it until this is resolved.

## 3. BOM handling

`parse_markdown_file` calls `Path(path).read_text()` with default encoding. Windows-authored files with a UTF-8 BOM (`﻿`) will pass the BOM into the first line, which can corrupt a heading match on line 1.

**Fix:** switch to `read_text(encoding="utf-8-sig")` in `parsers/markdown.py` and add a test fixture with a BOM.

## 4. `heading_path` is lossy in `decode_blockref`

The Markdown BlockRef format encodes only `L<start>-<end>`, not the heading path. `decode_blockref` returns a `MarkdownLocator` with `heading_path=[]`. This is **not** a citation-integrity bug — `check_block` re-encodes from the live locator (not the decoded one), so on-disk blocks remain consistent.

But any Phase 2 consumer that calls `decode_blockref` on a stored Markdown BlockRef expecting to recover the heading path will be surprised. The heading path lives only in the on-disk frontmatter JSON, not in the BlockRef string.

**Action:** document this in the Phase 2 plan's section on retrieval; possibly add a helper that loads the on-disk block and returns the full locator (with heading_path) when the consumer needs it.

## 5. `block_type` forward declarations

`BlockType = Literal["text", "heading", "table", "list", "code"]` declares `table`, `list`, `code` but the Phase 1 Markdown parser never emits them. The slots are ready; Phase 2's parser refinement just needs to detect fenced code blocks and list markers and set the type accordingly.

**Action:** include this refinement as a task in the Phase 2 plan rather than treating it as an extension.

## 6. Cross-field validator on `MarkdownLocator`

`line_start` and `line_end` are individually constrained `ge=1` but no validator enforces `line_end >= line_start`. Not currently exploited, but worth a model validator before user-provided locators are accepted from external callers (Phase 2 wiki compile may construct locators in code).

---

**Tests passing at the end of Phase 1:** 44/44 across 9 test files. mypy clean (11 source files). ruff clean (src + tests).

**Tag at phase boundary:** `phase-1-complete`.
