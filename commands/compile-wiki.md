---
description: Compile a citation-preserving wiki article on a domain topic.
argument-hint: "<topic> <slug> [<source_file>...]"
---

# /dks:compile-wiki

Compose a topic article that cites verbatim source for every claim. Thin trigger for the `dks-compile-wiki` skill.

## Procedure

Parse `$ARGUMENTS` into:
- **topic** (free text, can contain spaces — typically the first quoted segment or everything up to a recognizable slug)
- **slug** (kebab-case, no spaces — used as the wiki filename)
- **source_files** (optional, zero or more — defaults to "draw from the whole corpus" if omitted)

If parsing is ambiguous (e.g. the user just typed `/dks:compile-wiki something`), ask one clarifying question before invoking the skill:

```
I need three things to compile a wiki entry:
1. Topic (free text): what's the article about?
2. Slug (kebab-case): what should the wiki filename be?
3. Source files (optional): which sources should I draw from? (Defaults to the whole ingested corpus.)
```

Once parsed, invoke the `dks-compile-wiki` skill with:

> Use the **dks-compile-wiki** skill with topic: `<topic>`, slug: `<slug>`, source_files: `<list or "all">`.

The skill handles the full procedure: gathering blocks, composing the article with inline `[ref: <block_id>]` citations on every claim, persisting via `dks wiki write`, and reporting back.

## When NOT to use this command

See the `dks-compile-wiki` skill's "When NOT to use this skill" section. In short:
- Skip if there are no normalized blocks backing the topic (ingest the source first).
- Skip for one-off questions (use `/dks:search` instead).
- Skip if the topic only mirrors a single source 1:1 — the wiki is for cross-source synthesis.
