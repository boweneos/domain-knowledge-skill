---
name: dks-compile-wiki
description: Compile a citation-preserving wiki article on a domain topic from normalized blocks. Use when the user wants to summarize a body of evidence into a topic article that consumer agents can read for discovery. Every claim in the output must cite a block_id.
argument-hint: "<topic> <slug> [<source_file>...]"
---

# dks-compile-wiki

You compile a Markdown article on a domain topic from a set of normalized source blocks. Every factual claim in the article must include an inline citation to a `block_id`.

## When NOT to use this skill

Skip this skill for:
- Topics with no normalized blocks backing them — compile would have nothing to cite. Ingest the source first.
- One-off questions that don't deserve a reusable wiki entry (use `dks-search` directly instead of compiling).
- Topics that mirror a single source 1:1 — the wiki is for cross-source topic synthesis, not for re-summarising one document. If a topic only ever cites one source, the original source is the better artifact.
- Personal notes or draft content — wiki entries are part of the audit substrate; only compile when the topic is stable enough to be cited.

If you would be writing an entry with only 2–3 citations from one source, reconsider whether the wiki is the right home.

## Input

The user names:
- A **topic** (free text), e.g. *"PII handling rules in life-insurance products"*
- A **slug** (kebab-case, no spaces, no slashes, lowercase), e.g. `pii-handling-rules`
- A set of **source_files** OR **block_ids** to draw from. If only source_files are given, list the blocks for each.

## Procedure

### Phase 0 — Narrow with pageindex (optional, since v0.3.9)

For each `source_file` the user named, **before** enumerating all blocks, check whether a pageindex tree is available for it. The tree lets you jump straight to the relevant subtree instead of reading every block of a long source.

```bash
dks pageindex search "<keyword from topic>"
```

This returns a JSON array of `{source, layer, title, path, block_ids}` hits across all pageindex-built sources whose node titles match. If hits include `source_file`s you're compiling from, take the union of those nodes' `block_ids` as your starting set — those are the blocks most likely to support the article.

If `dks pageindex search` returns nothing relevant, OR if the named sources have no pageindex (the search returns no hits for that source), fall through to Phase 1's full block listing. **Pageindex is an accelerator, not a gate** — its absence never blocks a compile.

Quick check whether a pageindex exists for a specific source:
```bash
dks pageindex read "<source_file>" 2>/dev/null && echo "pageindex available" || echo "no pageindex — full block listing"
```

**When to skip Phase 0:**
- The source is short (< ~30 blocks) — listing is cheap; pageindex adds nothing.
- The topic spans the whole source — narrowing to a subtree would drop relevant content.
- The user has explicitly named `block_ids` — go straight to Phase 1 with those.

### Phase 1 — Gather blocks

1. **Gather blocks.** For each source_file, run `dks blocks list <source>` (skip this if Phase 0 already gave you a narrower `block_id` set). This returns a JSON array of `{"block_id": "...", "layer": "..."}` objects (not a flat list of strings) — extract the `block_id` values and note their layers. For each `block_id` (whether from the user, from Phase 0, or from the list), run `dks blocks get <block_id>`. This returns `{"block": {...}, "layer": "...", "shadows": [...]}` — use `.block` for the block content and note `.layer` for citation tagging. The `.shadows` field lists any lower-precedence blocks at the same `block_id` as `{"layer": "...", "content_differs": bool}`; if `content_differs` is true (or a `WARN:` line appears in the output), note the divergence explicitly when authoring the article.

2. **Compose the article.** Write a Markdown article on the topic. Rules:
   - Every factual statement must end with an inline citation: `[ref: <block_id>]`.
   - Multiple citations: `[ref: id1, id2]`.
   - Do not synthesize claims that aren't supported by a block. If two blocks contradict, write `X says A [ref: ...] but Y says B [ref: ...]` and surface the conflict explicitly.
   - Use the canonical `block_id` strings exactly as returned by the CLI. Do not abbreviate or rewrite them.
   - Open with a short summary paragraph (1–2 sentences) of the topic before going into specifics.
   - Use H2/H3 to organize sub-topics if the material warrants it. Don't add an H1 — the wiki frontmatter carries the topic.
   - **Layer disambiguation in citations:** Adding `@ layer` to inline citations is optional for single-layer articles but **recommended when the article cites blocks from both layers** — the divergence matters to the reader. Example:
     ```
     Customer details must be encrypted at rest [ref: pii.pdf#p3 @ global], with the additional product-specific exception that minor accounts may use deferred encryption [ref: product-exceptions.md#L12-18 @ project].
     ```

3. **Set the wiki entry's classification.** The entry's classification must
   be at least as strict as the strictest cited block:

   - If you cited any `confidential` block → entry must be `confidential`
     (or `restricted`).
   - If you cited any `restricted` block → entry must be `restricted`. You
     should also reconsider whether such an entry should exist at all —
     wiki entries are for cross-source synthesis, and citing restricted
     material in a synthesised entry compounds exposure. Prefer to leave
     a "consult the source directly" pointer in a `confidential` entry.

   Pass the classification to `dks wiki write` via `--classification`:

   ```bash
   echo '...' | dks wiki write claim-filing-windows --classification confidential
   ```

   When writing the body:
   - For confidential cited blocks: paraphrase rather than quote.
   - For restricted cited blocks: do not include block content at all;
     reference the citation and let `dks-search` consumers retrieve the
     source themselves.

4. **Collect the unique source_refs.** Extract every distinct `block_id` you cited; that is the `source_refs` list.

5. **Persist.** Build a JSON object:
   ```json
   {
     "topic": "<topic>",
     "source_refs": ["<id>", "..."],
     "body": "<full article markdown>"
   }
   ```
   Pipe it into:
   ```bash
   echo '<json>' | dks wiki write <slug>
   ```
   By default the entry writes to the **project** layer. To write a company-wide article that should be reusable across projects, add `--write-global`:
   ```bash
   echo '<json>' | dks wiki write --write-global <slug>
   ```

6. **Report.** Tell the user the slug, the path written, the source_ref count, and the article length in words.

## Constraints

- **No uncited claim, ever.** If you start a sentence and can't end with `[ref: ...]`, you don't have evidence — either find a block that supports it, or omit the sentence. This is the core discipline; do not relax it.
- **No paraphrase past recognition.** Reword for clarity but don't change meaning. The wiki is for discovery; the underlying block is the source of truth.
- **No silent block dropping.** If a block in the user-provided set is irrelevant to the topic, you may exclude it from `source_refs`, but tell the user in your report which blocks were excluded and why.
- **Slug discipline.** The slug becomes a filename. Reject slugs with `/`, spaces, uppercase, or non-ASCII characters. Ask the user for a fixed slug if theirs is invalid; don't silently normalize.
- **No editing existing wiki entries.** This skill only writes new entries. If the slug already exists, the write will overwrite it — confirm with the user before doing so.
- **Cross-layer citation visibility.** If you cite blocks from BOTH layers in one article, include `@ layer` on at least the project citations so the layer divergence is visible to the reader.
- **Classification must propagate up.** A wiki entry citing `confidential`
  or `restricted` blocks must declare a matching (or stricter) classification.
  `dks-lint-wiki` flags mismatches as classification leaks.

## Cost guidance

Compiling one wiki article from ~50 blocks should fit comfortably in a single Sonnet-class prompt with ~30K–60K tokens of context. Don't loop per-block with LLM calls; fetch them all, reason once.
