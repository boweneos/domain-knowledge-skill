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

> **Efficiency rule (since v0.3.4 / v0.3.6):** for a corpus-wide lint, **do NOT** call `dks blocks get` once per cited block_id. With ~80–100 citations across the wiki, that's 80–100 subprocess invocations and minutes of Python + spaCy startup overhead. **Use the bulk-then-check pattern** described in step 1 below: pull each entry's full payload once via `dks wiki list --with-content`, group citations by source, then call `dks blocks list <source>` once per source to enumerate which block_ids exist. Set-membership checks finish in seconds.
>
> Reach for per-id `dks blocks get` only when you need (a) divergent-shadow detection (the WARN line + `.shadows` field), (b) a block's `classification` field, or (c) the block's actual content. For both (a) and (b), batch by collecting unique block_ids first and fetching each once.

1. **Pull all entries with bodies in one call:**
   ```bash
   dks wiki list --with-content
   ```
   This returns a JSON array of `{"slug": "...", "layer": "...", "entry": {...full WikiEntry...}}`. Capture `slug`, `layer`, `entry.topic`, `entry.source_refs`, `entry.body`, and `entry.classification` for each.

2. **Group citations by source_file and bulk-enumerate existence:**
   ```bash
   # For each distinct source referenced across all entries:
   dks blocks list "<source_file>"
   ```
   Build a set of all existing block_ids across all referenced sources. Membership lookups against this set are how you detect **broken citations** — no per-id `blocks get` call required.

3. **Per-entry checks** (still iterate per entry, but use the bulk sets from steps 1–2):
   - **Broken citations:** for each `block_id` in `source_refs`, check membership in the existing-block_ids set built in step 2. Misses are broken citations (note the entry's layer).
   - **Inline drift (body vs source_refs):** extract every inline `[ref: <block_id>]` from the body. If a cited block_id is NOT in `source_refs`, record as **inline drift (cited but not in source_refs)**. For every `block_id` in `source_refs` that does NOT appear in any inline `[ref: ...]` in the body, record as **inline drift (in source_refs but not cited in body)**.
   - **Cross-layer citations:** when fetching the block (for classification or divergent-shadow checks below), inspect `.layer` in the returned JSON. If the entry's layer is `project` but the block's layer is `global`, record as a **cross-layer citation** (informational).
   - **Divergent shadows:** for citations where the cited source has blocks in both project and global layers (visible by running `dks blocks list <source>` in both layer modes — or simply check `.shadows[*].content_differs` from a single `dks blocks get`), record any shadow with `content_differs: true` as a **divergent shadow**. The CLI also emits a `WARN:` line for these.
   - **Classification leak:** fetch each unique cited block once via `dks blocks get` to read `.classification`. Compute `max_cited` of these (order: `public < internal < confidential < restricted`). If the entry's own classification is less strict than `max_cited`, record as a **classification leak**.
   - **Superseded source citations (since v0.4):** run `dks meta superseded-by` once at the start to get the inverse map `{old_source: [{source, layer}, ...]}`. For each `block_id` in an entry's `source_refs`, extract its source basename (the part before the first `#`). If that basename appears as a key in the superseded-by map, record as a **superseded source citation** — name the successor source(s) so the operator can re-compile against them.

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

   ### Superseded source citations
   - (global) entry `<slug>` cites <N> blocks from `<old_source>`, which has been superseded by `<new_source>` @ <layer> — re-compile this entry against `<new_source>` to incorporate the amendment

   ### Possible contradictions
   - (project) `<slug-a>` says "<claim>" [<id> @ project] but (global) `<slug-b>` says "<other>" [<id> @ global] — same topic area

   ### Summary
   - N entries scanned (project: P, global: G)
   - X broken citations
   - Y drift issues
   - Z cross-layer citations
   - V divergent shadows
   - W classification leaks
   - S superseded source citations
   - W possible contradictions
   ```

   If a section has zero items, write `(none)` rather than omitting it — that makes "everything is clean" visually obvious.

## Constraints

- **Read-only.** Do not invoke `dks wiki write`, `dks pageindex write`, or any mutating command. If a user asks you to fix issues during a lint run, tell them lint is read-only and refer them to `dks-compile-wiki` for the relevant slug.
- **Be conservative on contradictions.** False positives erode trust in the lint output. Only flag direct, factual conflicts on the same narrow topic. When in doubt, don't flag — but you may include the pair in a separate "review suggested" section if it feels worth a human glance.
- **No editing.** This skill runs `dks blocks get` and `dks wiki read`; it does not run any write command.
- **Don't suggest fixes you can't be sure are right.** If a broken citation could be fixed by re-ingesting the source, say so. If a drift could be a real new claim that wasn't added to source_refs, surface it but don't auto-correct.
