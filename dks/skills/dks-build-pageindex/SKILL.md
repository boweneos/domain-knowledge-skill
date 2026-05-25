---
name: dks-build-pageindex
description: Build a hierarchical PageIndex tree for a source document already ingested by dks. Use when the user wants to construct or refresh the per-document tree of contents that the consumer-facing dks-search skill uses for navigation.
argument-hint: "<source_file>"
---

# dks-build-pageindex

You build a hierarchical PageIndex tree for a single source document that has already been ingested by the `dks` package.

## When NOT to use this skill

Skip this skill for:
- Sources that haven't been ingested yet (run `dks ingest` first; `dks blocks list` returning empty is the signal).
- Short or flat documents (< ~30 pages, no nested headings) — they don't benefit from a tree; flat block lookup is sufficient.
- Pure data sources (CSVs, raw Excel data tables with no narrative structure) — the tree primitive doesn't apply.
- Re-runs on a tree that hasn't changed — the build is amortised cost; only re-run when the source has been re-ingested or the previous tree is stale.

If you're not sure whether a source warrants a tree, run `dks blocks list <source>`. If you see fewer than ~30 blocks and most are `block_type: "text"` rather than `"heading"`, skip the tree.

## Input

The user names a `source_file` (e.g. `policies/claims_handling.pdf`). Layer flags (`--project`, `--global`, `--no-global`) are available on the root `dks` command but are not needed for typical use — the CLI auto-discovers the project layer and falls back to `~/.dks/` for the global layer.

## Procedure

1. **List the blocks.** Run:
   ```bash
   dks blocks list "$SOURCE_FILE"
   ```
   This returns a JSON array of objects, each with `block_id` and `layer` (e.g. `[{"block_id": "claims.pdf#p1#1", "layer": "project"}, ...]`). Extract the `block_id` values to drive the next step. Note the `layer` values — you'll use them when deciding where to write the tree (see step 4).

2. **Fetch every block's content.** For each `block_id`, run:
   ```bash
   dks blocks get "$BLOCK_ID"
   ```
   This returns a JSON object with two top-level fields: `.block` (the full block JSON with `content`, `block_type`, `locator`, etc.) and `.layer` (which layer resolved this block). Use `.block.content`, `.block.block_type`, and `.block.locator` for the tree-building step below.

3. **Reason over the structure.** Headings (`block_type == "heading"`) define section boundaries; text/table/list/code blocks belong to the most recent heading. Build a tree where each node has:
   - `title`: the heading text (or a synthesized title for the root)
   - `block_ids`: the list of `block_id`s that fall directly under this node (between this heading and the next sibling/parent heading)
   - `children`: a list of child nodes (deeper headings)

   The tree must be JSON-serializable and use this schema:
   ```json
   {
     "title": "string",
     "block_ids": ["string", "..."],
     "children": [ { "title": "...", "block_ids": ["..."], "children": [] } ]
   }
   ```

4. **Persist the tree.** Pipe the JSON into:
   ```bash
   echo '<json-tree>' | dks pageindex write "$SOURCE_FILE"
   ```
   By default the tree writes to the **project** layer (when a project is present). To build a global-scoped tree shared across projects, add `--write-global`:
   ```bash
   echo '<json-tree>' | dks pageindex write --write-global "$SOURCE_FILE"
   ```
   Most users want the project default.

5. **Report back.** Tell the user the path the tree was written to and a one-line summary (top-level section count, deepest nesting depth, total nodes).

## Constraints

- **Never invent block_ids.** Only assign `block_id`s that were returned by `dks blocks list`. If a block's content suggests it belongs somewhere unexpected, still place it; the tree reflects the document, not your judgment about correctness.
- **Every block_id must appear in the tree exactly once.** If a block has no preceding heading, place it under a synthetic root node.
- **Don't summarize the content.** This skill produces structure, not summaries. The `dks-compile-wiki` skill is where summarization happens.
- **Fail loudly.** If `dks blocks list` returns an empty array, tell the user the source hasn't been ingested yet — don't fabricate a tree.
- **Layer placement heuristic.** When blocks come from mixed layers, prefer to write the tree into the layer that owns the majority of the blocks: build globally (use `--write-global`) for sources where all or most blocks resolve from the `global` layer; use the default project write for anything that touches a project block. This keeps the index colocated with its data.

## Cost guidance

A typical 50-page policy PDF has 100–300 blocks. Reading all of them and constructing a tree is one Sonnet-class prompt with ~50K tokens of context. Don't loop over blocks one at a time with LLM calls; fetch them all, then reason once.
