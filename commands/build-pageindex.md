---
description: Build a hierarchical PageIndex tree for an ingested source document.
argument-hint: "<source_file>"
---

# /dks:build-pageindex

Construct or refresh the PageIndex tree for a source document. Thin trigger for the `dks-build-pageindex` skill.

## Procedure

Invoke the `dks-build-pageindex` skill with the user's argument:

> Use the **dks-build-pageindex** skill to build a hierarchical tree for source_file: `$ARGUMENTS`.

If `$ARGUMENTS` is empty, ask the user which source to index. Suggest they run `dks blocks list` (with no source) or check `normalized/` to see which sources have been ingested.

The skill handles the full procedure: listing blocks, fetching contents, reasoning over headings, persisting the tree JSON via `dks pageindex write`, and reporting back the path + summary.

## When NOT to use this command

See the `dks-build-pageindex` skill's "When NOT to use this skill" section. In short:
- Skip for sources that haven't been ingested.
- Skip for short / flat documents (< ~30 blocks, mostly text).
- Skip if the existing tree is still current.
