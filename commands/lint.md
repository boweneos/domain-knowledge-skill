---
description: Audit the compiled wiki for broken citations, drift, and contradictions.
argument-hint: ""
---

# /dks:lint

Run a read-only audit pass over every wiki entry. Thin trigger for the `dks-lint-wiki` skill.

## Procedure

Invoke the `dks-lint-wiki` skill:

> Use the **dks-lint-wiki** skill to audit the compiled wiki.

This command takes no arguments — the lint is corpus-wide. The skill handles listing every entry, verifying every cited `block_id` still exists, scanning for inline-vs-source_refs drift, and surfacing possible cross-entry contradictions. It produces a structured report; it does **not** auto-fix.

## When NOT to use this command

See the `dks-lint-wiki` skill's "When NOT to use this skill" section. In short:
- Skip if the wiki is empty.
- Don't use it as a fixer — broken citations are fixed by re-running `/dks:compile-wiki` on the affected slug.
- For debugging a single entry, use `dks wiki read <slug>` directly rather than a full lint pass.
