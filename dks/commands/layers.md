---
description: Inspect which KB layers are active and where each resolved from (project / global, env / auto-discover / explicit).
argument-hint: ""
---

# /dks:layers

Print the active dks KB layers with their resolution source. Useful when debugging "why is dks finding/not-finding the layer I expected?".

## Procedure

Run:
```bash
dks layers list
```

This prints a JSON array. Each entry has:
- `name`: `"project"` or `"global"`
- `base`: absolute path to the layer's base directory
- `source`: how the layer was resolved (`explicit`, `env`, `auto-discover`, or `default`)
- `exists`: whether the base directory actually exists on disk

If a layer the user expects is missing or pointing somewhere unexpected, the `source` field tells you why. Common cases:

- Project `auto-discover` to an unexpected path → the walker found a `.dks/` higher up than intended. Set `DKS_PROJECT` explicitly or move into the right repo.
- Global `default` → no `DKS_GLOBAL` env var, no `--global` flag, fell back to `~/.dks`. Set `DKS_GLOBAL` if you need a non-default location.
- Project missing and you expected one → no `.dks/` found anywhere on the walker's path from CWD. `mkdir .dks` at the repo root to create one.

## When NOT to use this command

This is purely an introspection command. It doesn't read or write KB content. Skip it for normal grounding/compilation workflows — only reach for it when behaviour is surprising.
