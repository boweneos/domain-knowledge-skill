---
name: dks-search
description: Ground domain facts in citable source documents. Use when working on regulated code (compliance, data handling, claim rules, underwriting, policy logic) where every factual claim must trace back to a verifiable source. Provides discovery via wiki and fact substrate via verbatim source block.
argument-hint: "<topic or query>"
---

# dks-search

You ground domain facts in citable source documents. Other parts of your work may produce code, designs, or recommendations; this skill is the **only** sanctioned path to learn a domain rule or extract a fact about how the business operates.

> **Important:** This skill grounds answers in cited source material but does not replace qualified legal, compliance, or actuarial review. Treat its output as research support for human-reviewable decisions, not as authoritative legal advice. Regulatory requirements change; always verify against current authoritative sources before shipping regulated logic.

## When this skill applies

Invoke this skill when you are about to:
- Write product code that implements a compliance rule (data retention, PII handling, claim handling, underwriting, policy logic).
- Answer the user's question about how the business behaves in a regulated area.
- Make a design decision that hinges on a domain rule.

## When NOT to use this skill

Skip this skill for:
- UI / styling / layout work that doesn't encode a domain rule.
- Infrastructure changes (build config, CI, dependency upgrades) with no compliance dimension.
- Generic refactors that preserve behavior.
- Generic programming questions ("how do I parse a date in TypeScript?") — those don't need grounding in the corpus.
- Questions about non-domain technical choices (library selection, architectural patterns) unless a compliance constraint actually applies.

If you're unsure whether a task touches a regulated rule, do a single `dks wiki search` with a likely query — if nothing comes back, the topic isn't in the KB and you can proceed without grounding (with a note to the user).

## Procedure

### Phase 1 — Discovery (`search_topic`)

Run:
```bash
dks wiki search "<query>"
```
This returns a JSON array of matching wiki entries, each with `slug`, `topic`, `source_refs`, a `snippet`, and a `layer` field (`"project"` or `"global"`) indicating which layer owns this entry.

Read the snippets. The snippet is **not** authoritative — it's a discovery hint to help you pick which source blocks to fetch next. Note the `layer` on each hit — you'll include it in citations.

If no entries match:
- Tell the user the topic is not yet in the KB.
- Do NOT fabricate facts. Either ask the user to compile a wiki entry (`dks-compile-wiki` skill) or proceed without grounding and clearly say "this is an assumption, not a cited fact."

### Phase 2 — Fact substrate (`get_source`)

For each `block_id` in the `source_refs` of a relevant hit, run:
```bash
dks blocks get "<block_id>"
```
This returns a JSON object with three top-level fields:
- `.block` — the full block JSON: `{source_file, block_id, locator, block_type, content}`.
- `.layer` — which layer resolved this block (`"project"` or `"global"`).
- `.shadows` — a list of lower-precedence blocks at the same `block_id`, each with `{"layer": "...", "content_differs": bool}`. An empty list means no shadowing occurred.

If the command also prints a line beginning with `WARN:` to stderr (CliRunner surfaces it in output), it means the served block's content diverges from a same-id block in a lower layer. Surface that to the user using the "Project overrides global" edge-case template below.

Use `.block.content` as your source of truth (not the wiki snippet). Use `.block.locator` for the citation primitive (page, section/clause for PDFs; sheet+cells for Excel; etc.). Capture `.layer` — you'll include it in citations.

If you need adjacent context (the block before or after), use:
```bash
dks blocks list "<source_file>"
```
This returns a JSON array of `{"block_id": "...", "layer": "..."}` objects (not a flat list of strings). Pick the relevant `block_id`s from that array, then fetch each with `dks blocks get` as above.

### Phase 3 — Emit cited facts

When you write code, documentation, or an answer that uses a fact you extracted:
- Quote or paraphrase the verbatim block content.
- Always include the citation in a form that traces back to source, including the `@ layer` suffix from `.layer`. Examples:
  - In code comments: `# Retention rule: 7 years (source: claims.pdf p20 §5.1 @ global, block claims.pdf#p20#5.1)`
  - In prose: `Claims must be filed within 30 days [ref: claims.pdf#p14#3.2 @ global].`
  - In a PR description: a "Sources" section listing each block_id you relied on.

### Output format template

When you emit a grounded answer, use this shape. The trailing `Sources` block makes the citation contract visible and auditable.

```
[Answer in your own words, with inline citations like [ref: <block_id> @ <layer>] on every factual claim.]

Sources:
- <block_id_1> @ <layer> — <source_file> <human-readable locator e.g. "page 14 §3.2">
- <block_id_2> @ <layer> — <source_file> <human-readable locator>
```

When the answer is code, put the inline citations in comments adjacent to the relevant lines and the `Sources:` block in the PR description or your message to the user — not buried in code.

## Contract — what you must NOT do

- **No uncited extracted fact.** If you would write a sentence stating a domain rule and you cannot end it with a citation tracing back to a `block_id` you fetched, do not write the sentence. Ask for clarification, or write the code without the rule (and surface that to the user).
- **No reliance on the wiki snippet alone.** The snippet is for discovery. Cite the source block, not the wiki entry.
- **No quoting beyond the verbatim block content.** If you need a longer passage than one block contains, fetch the adjacent blocks (`dks blocks list <source_file>` to enumerate, then `dks blocks get`).
- **No fabricated block_ids.** Only cite block_ids that were actually returned by a CLI call in this session.

## Edge cases — handle these explicitly

### Ambiguous queries

If the user's request could mean two different domain topics, run **one** clarifying question before searching:

```
"Filing window" could refer to a few things. Are you looking for:
1. Claim filing window (time to submit after incident)?
2. Underwriting application window (validity period for quotes)?
3. Regulatory disclosure filing window (e.g. PDS distribution)?
```

Do not search blindly across all interpretations — that pollutes the result set and wastes the user's time.

### No results

If `dks wiki search` returns an empty list, **do not stop there.** Before abstaining, check whether the ingested corpus contains a source that LOOKS like it covers the topic but hasn't been compiled into a wiki entry yet. Many cases of "no wiki hit" turn out to be "wiki entry not yet compiled from an obviously-relevant source."

**Auto-suggest procedure** (since v0.3.7):

1. **Extract keyword(s) from the query.** Strip stopwords; keep the substantive nouns. E.g. `"what's our rule for sleep apnoea underwriting"` → `sleep apnoea`.

2. **Look for candidate sources by filename match.** Use the active layer's `normalized/` directory (which is where every ingested source lives, one subdirectory per source). Several ways:
   ```bash
   # Lightweight — list source names in each active layer
   ls "$(dks layers list | python3 -c 'import sys,json; print(json.load(sys.stdin)[-1][\"base\"])')/normalized/" 2>/dev/null
   # Or grep by keyword (case-insensitive):
   ls ~/.dks/normalized/ 2>/dev/null | grep -i "sleep" 2>/dev/null
   ```
   If a project layer is also active, repeat for `$(dks layers list | python3 ... project base)/normalized/`.

3. **If exactly one source matches**, propose compiling from it:
   ```
   The KB has no wiki entry for "<query>", but I found a source in the
   ingested corpus that looks relevant: "<source_filename>" (in <layer>).
   Want me to compile a wiki entry from it (using dks-compile-wiki) so I
   can ground the answer? Or would you rather I proceed un-grounded with
   "assumed, not cited" markers on the rules I rely on?
   ```

4. **If multiple sources match**, list them all and ask which:
   ```
   The KB has no wiki entry for "<query>", but I found N sources in the
   ingested corpus whose filenames suggest they cover the topic:
     - <source 1> (<layer>)
     - <source 2> (<layer>)
     - <source 3> (<layer>)
   Which should I compile from? (Or "all" / "none" / "skip and proceed
   un-grounded".)
   ```

5. **If NO sources match by filename**, fall back to the classic abstention message:
   ```
   The KB does not contain a citation for "<query>", and I couldn't find
   a source in the ingested corpus that obviously covers it. Possible
   next steps:
   - Ingest a new source document covering this topic (dks ingest), then
     compile a wiki entry (dks-compile-wiki).
   - Proceed without grounding, but I'll flag any rule I rely on as
     "assumed, not cited" so you can verify against authoritative
     sources later.
   Which would you prefer?
   ```

**Do NOT auto-invoke `dks-compile-wiki` without user approval.** The compile is opt-in even when the candidate source is obvious — it's an LLM-heavy operation that creates citable content the rest of the system will treat as authoritative, so the operator-in-the-loop trust gate stays.

### Partial corpus — search hit but block fetch fails

If `dks wiki search` returns hits but `dks blocks get <block_id>` fails (block not found / file moved), the wiki is stale:

```
I found wiki entry "<slug>" referencing block "<block_id>", but the block no longer exists in the corpus.
This usually means the source document was re-ingested and the wiki entry hasn't been recompiled.

Recommend: run dks-lint-wiki to surface all stale citations, then re-run dks-compile-wiki on the affected slug.

For this question, I'll abstain on the grounded claim until the wiki is refreshed.
```

### Project overrides global on the same topic

When the same slug (or closely related blocks) appears in both the `project` and `global` layers, the project version wins — the CLI resolves to it automatically. When this happens and it matters for the answer, surface it explicitly:

```
Note: project-specific override of a global rule. The global layer says X [ref: <id> @ global]; this project applies Y instead [ref: <id> @ project].
```

This makes layer divergence visible to the reader rather than silently shadowing.

### KB-covered topic but agent doesn't believe it

If the source block says X and your training prior says Y, **the source wins**. Cite X verbatim. If you think the source is wrong (e.g., obviously contradicting a well-known regulation), say so explicitly:

```
The KB says: "<verbatim quote>" [ref: <block_id>].
I note this appears to conflict with <general_rule>. Recommend verifying with a domain expert before relying on this.
```

Do not silently substitute your prior for the cited source.

## Handling classified content

Every block returned by `dks blocks get` now carries a `classification` field
(`public`, `internal`, `confidential`, or `restricted`) and may trigger a
stderr `WARN` line when fetched. The classification governs how you may use
the block's content in your answer:

- **`public` / `internal`** — no restrictions. Quote, paraphrase, cite as
  normal.
- **`confidential`** — cite the block_id and summarise the rule in your own
  words. **Do not paste verbatim block content** into the answer or into
  code comments. The citation discipline is preserved (you can still
  ground the claim) but the surface form changes.
- **`restricted`** — return only a pointer:
  > "A rule on [topic] exists at [block_id @ layer, classification: restricted].
  > Per its restricted classification, I won't surface its content here —
  > please consult the source directly."
  Then stop. Do not summarise. Do not paraphrase. Do not infer.

When you emit your `Sources:` block, include the classification in the tag:

```
Sources:
- claims.pdf#p14#3.2 @ global, internal — 30-day filing window
- product-pii-rules.docx#§3 @ project, confidential — see source for details
```

The stderr WARN lines are operator-visible diagnostics, not errors. They
exist so the human reviewing the session can verify that a sensitive block
was actually intended for this consumer.

### Redacted blocks

A block may have been redacted at ingest (`--redact-pii`). When `dks blocks get`
returns a block with `"redacted": true`, the `content` field contains
`[REDACTED:<TYPE>]` markers where PII was detected and replaced.

For redacted blocks, you can still cite them normally — the citation is still
audit-grade because the block_id traces to the original source span — but
acknowledge in your answer that the source has been redacted:

```
The customer notification rule applies [ref: audit.md#L1-1 @ project, redacted].
(Source block has been redacted at ingest; refer to the original document for
unredacted detail.)
```

## Abstention

If after Phase 1 + Phase 2 you cannot find a block that supports the claim you need, **abstain**. Tell the user clearly:

> "The KB does not contain a citation for X. I can proceed without grounding (and you can verify against authoritative sources later), or you can compile a wiki entry first using the dks-compile-wiki skill."

This is the right behavior — citation discipline matters more than confident guessing.

## Cost guidance

A typical grounding query is one `dks wiki search` (≤ 1KB output) plus a handful of `dks blocks get` calls (small JSON each). No LLM tokens are needed for the CLI calls themselves — the LLM work is just reading the returned content. Budget: trivial.
