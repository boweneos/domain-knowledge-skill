---
name: dks-lint-wiki
description: Scan compiled wiki entries for broken citations, contradictions, and stale references. Use periodically or after re-ingesting source documents.
argument-hint: ""
---

# dks-lint-wiki

You audit the compiled wiki for citation integrity and consistency. This skill is read-only — it reports, it does not edit.

## When NOT to use this skill

Skip this skill when:
- The wiki is empty (`dks wiki list` returns nothing). There's nothing to lint.
- The user wants the lint to also fix issues — it doesn't. Lint reports; fixes are a separate human-judgment step (re-run `dks-compile-wiki` on affected slugs).
- The user is debugging one specific wiki entry — use `dks wiki read <slug>` + `dks blocks get` directly rather than a full corpus scan.

Lint is a corpus-wide audit pass. Run it after a re-ingest, on a schedule, or before relying on the wiki for high-stakes downstream work — not for routine in-session debugging.

## Procedure

1. **List all entries.** Run:
   ```bash
   dks wiki list
   ```
   This returns a JSON array of `{"slug": "...", "layer": "..."}` objects (not a flat list of slugs). Iterate over these objects; the `layer` field tells you which layer owns each slug after shadowing (a project entry shadows a global entry with the same slug).

2. **For each entry,** run:
   ```bash
   dks wiki read <slug>
   ```
   This returns `{"entry": {...}, "layer": "..."}`. From `.entry`, capture `topic`, `source_refs`, and `body`. Record the `.layer` of the entry — you'll need it for the report and cross-layer checks.

3. **Per-entry checks:**
   - For every `block_id` in `source_refs`, run `dks blocks get <block_id>`. If it returns a non-zero exit code or an error, record this as a **broken citation** (noting the entry's layer). If the block resolves successfully, inspect the JSON result: note the `.layer` returned — if the entry's layer is `project` but the block's layer is `global`, record this as a **cross-layer citation** (informational). Also check `.shadows`: for any shadow entry where `content_differs` is true (or equivalently, if a `WARN:` line appears in the command output), record this as a **divergent shadow** (see report template below).
   - Extract every inline `[ref: <block_id>]` from the body. For each:
     - If the cited block_id is NOT in `source_refs`, record as **inline drift (cited but not in source_refs)** (noting the entry's layer).
   - For every `block_id` in `source_refs` that does NOT appear in any inline `[ref: ...]` in the body, record as **inline drift (in source_refs but not cited in body)** (noting the entry's layer).
   - **Classification leak.** Fetch each cited block via `dks blocks get` and
     read its `classification`. Compute `max_cited = max` of those (using the
     order `public < internal < confidential < restricted`). If the wiki
     entry's own `classification` is less strict than `max_cited`, record as a
     classification leak.

4. **Cross-entry contradiction scan.** Read each entry's body. Flag any pair of entries that make directly opposing factual claims on the same narrow topic (e.g., entry A says "30 days" and entry B says "60 days" without versioning context). Be conservative — only flag direct, factual conflicts. Same word ≠ contradiction.

5. **Report.** Produce a structured report:
   ```
   ## Wiki lint report

   ### Broken citations
   - (project) entry `<slug>`: block_id `<id>` no longer exists in any layer
   - (global) entry `<slug>`: block_id `<id>` no longer exists in any layer

   ### Inline-vs-source_refs drift
   - (project) entry `<slug>`: body cites `<id>` but it isn't in source_refs
   - (global) entry `<slug>`: source_refs lists `<id>` but body never cites it

   ### Cross-layer citations
   - (project) entry `<slug>`: cites `<id>` which resolves from the global layer (informational)

   ### Divergent shadows
   - (project) entry `<slug>`: block `<id>` served from project layer shadows a global block with
     different content — the global version may represent a baseline rule the project is
     intentionally overriding; verify that the project version is deliberate
   - (global) entry `<slug>`: block `<id>` served from global layer shadows another lower layer
     with different content

   ### Classification leaks
   - (project) entry `<slug>` classified `<entry_class>` cites <N> blocks at `<higher_class>` — reclassify or remove cited material

   ### Possible contradictions
   - (project) `<slug-a>` says "<claim>" [<id> @ project] but (global) `<slug-b>` says "<other>" [<id> @ global] — same topic area

   ### Summary
   - N entries scanned (project: P, global: G)
   - X broken citations
   - Y drift issues
   - Z cross-layer citations
   - V divergent shadows
   - W classification leaks
   - W possible contradictions
   ```

   If a section has zero items, write `(none)` rather than omitting it — that makes "everything is clean" visually obvious.

## Constraints

- **Read-only.** Do not invoke `dks wiki write`, `dks pageindex write`, or any mutating command. If a user asks you to fix issues during a lint run, tell them lint is read-only and refer them to `dks-compile-wiki` for the relevant slug.
- **Be conservative on contradictions.** False positives erode trust in the lint output. Only flag direct, factual conflicts on the same narrow topic. When in doubt, don't flag — but you may include the pair in a separate "review suggested" section if it feels worth a human glance.
- **No editing.** This skill runs `dks blocks get` and `dks wiki read`; it does not run any write command.
- **Don't suggest fixes you can't be sure are right.** If a broken citation could be fixed by re-ingesting the source, say so. If a drift could be a real new claim that wasn't added to source_refs, surface it but don't auto-correct.
