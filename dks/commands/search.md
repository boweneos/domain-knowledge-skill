---
description: Ground a domain fact in citable source from the dks knowledge base.
argument-hint: "<topic or query>"
---

# /dks:search

Look up a domain rule or fact in the dks knowledge base and return a grounded, cited answer. Thin trigger for the `dks-search` skill.

## Procedure

Invoke the `dks-search` skill with `$ARGUMENTS` as the query:

> Use the **dks-search** skill to ground: `$ARGUMENTS`.

If `$ARGUMENTS` is empty, ask the user what they want grounded. The skill handles discovery (`dks wiki search`), fact substrate (`dks blocks get`), and the citation-discipline contract (no uncited extracted fact, abstain when KB lacks the rule).

## When NOT to use this command

See the `dks-search` skill's "When NOT to use this skill" section. In short:
- Skip for UI / styling / infra / refactor work that doesn't touch a domain rule.
- Skip for generic programming questions.
- Use the skill auto-activation (rather than this explicit command) when you're already mid-conversation about regulated code — the skill description will trigger it naturally.
