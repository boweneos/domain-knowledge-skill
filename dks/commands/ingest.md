---
description: Ingest a source document (PDF / DOCX / Excel / Markdown) into the dks knowledge base.
argument-hint: "<path-to-source-file>"
---

# /dks:ingest

Run the `dks` ingestion pipeline on a single source document. The path can be relative to the current directory or relative to `raw/` (the default root).

## Procedure

1. **Resolve the path.** If `$ARGUMENTS` is non-empty, treat it as the source path. If empty, ask the user which file to ingest.

2. **Run the ingestion command:**
   ```bash
   uv run dks ingest "$ARGUMENTS"
   ```
   (or `dks ingest "$ARGUMENTS"` if the user is outside the `dks` repo and has it installed globally.)

   For sources containing incidental sensitive content (PII, commercial-in-confidence,
   operational data), tag them at ingest with `--classification`:

   ```bash
   dks ingest path/to/audit.pdf --classification confidential
   ```

   Levels: `public` (regulator standards), `internal` (default, business rules),
   `confidential` (sensitive — global-write blocked, consumer skill paraphrases),
   `restricted` (PII — global-write blocked, consumer skill only points at source).

3. **Report the result.** The CLI prints `wrote N blocks to <output_dir>/<source_file>/`. Relay that to the user verbatim along with a one-line next-step suggestion:
   - If the source is long and structured (policy PDF, spec doc, technical manual), recommend `/dks:build-pageindex <source_file>` next.
   - If the source is short or flat (memo, simple spreadsheet), no PageIndex needed — they can move straight to `/dks:compile-wiki` when ready.

4. **Surface errors.** If the CLI returns a non-zero exit code:
   - `no parser registered for suffix '.xyz'` → tell the user the format isn't supported in Phase 1/2 (supported: `.md`, `.xlsx`, `.docx`, `.pdf`).
   - `file not found` → confirm the path with the user.
   - Any other error → quote it and ask the user to investigate.

## When NOT to use this command

- Skip if the source has already been ingested and hasn't changed — re-ingestion is idempotent but wastes I/O.
- For bulk ingestion across many files, suggest a shell loop rather than running this command repeatedly.
