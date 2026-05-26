# Phase 2 Carryovers from Phase 1

Notes from the Phase 1 final review (sonnet, 2026-05-21). All five items are **non-blocking for Phase 2 to begin**, but each is a real decision to revisit before Phase 2 ships.

## Status (updated 2026-05-25)

| # | Item | Status | Where addressed |
|---|---|---|---|
| 1 | `source_file` scoping (basename collision) | ✅ addressed | Phase 2 Task 0: `dks ingest --root <dir>` computes relative path |
| 2 | `PdfLocator.clause` unused by encoder | ✅ addressed | Phase 2 Task 0: clause now encoded as `<file>#p<page>#<section>#<clause>`; `_PDF_RE` updated |
| 3 | BOM handling in Markdown parser | ✅ addressed | Phase 2 Task 0: `read_text(encoding="utf-8-sig")` |
| 4 | `heading_path` lossy in `decode_blockref` | ⚠ open | Documented behaviour; not a citation-integrity bug (`check_block` re-encodes from the live locator). Only matters if a future consumer calls `decode_blockref` and expects to recover heading_path. |
| 5 | `block_type` forward declarations (`table`/`list`/`code`) | ◐ partially | Excel parser emits `table`; DOCX/PDF parsers still only emit `text`/`heading`. Refinement deferred. |
| 6 | Cross-field validator on `MarkdownLocator` (`line_end >= line_start`) | ⚠ open | Not currently exploited. Worth adding before accepting locators from external callers. |

Items 1-3 closed in Phase 2; items 4-6 remain explicit open follow-ups (none blocking).

## Findings from Phase 4 + real-world testing (2026-05-26)

| # | Item | Status | Detail |
|---|---|---|---|
| 7 | Auto-discovery walker matched `~/.dks` (global default) as project | ✅ fixed in 0.2.1 | When a repo has no `.dks/` of its own and the user has the default global at `~/.dks/`, the walker used to climb past `$HOME` and treat the global location as the project layer — both layers resolved to the same dir, every read tagged `"project"`. Fix: `resolve_layers` now resolves global first and passes it as a `skip` to `_auto_discover_project`. Two regression tests in `tests/test_layers.py`. |
| 8 | Content-divergence warning when project shadows global | ⚠ open | Mentioned in the Phase 4 plan's "What's left" section. When project and global both have a block at the same `block_id` with different content, `dks blocks get` should emit a stderr `WARN: shadows global block with different content` (currently silent). |
| 9 | `dks layers list` introspection subcommand | ⚠ open | Useful for debugging which layers are active and where they resolved from. Print `{name, base, env_var_used, auto_discovered: bool}` per active layer. |

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
