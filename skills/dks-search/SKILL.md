---
name: dks-search
description: Ground domain facts in citable source documents. Use when working on regulated code (compliance, data handling, claim rules, underwriting, policy logic) where every factual claim must trace back to a verifiable source. Provides discovery via wiki and fact substrate via verbatim source block.
---

# dks-search

You ground domain facts in citable source documents. Other parts of your work may produce code, designs, or recommendations; this skill is the **only** sanctioned path to learn a domain rule or extract a fact about how the business operates.

## When this skill applies

Invoke this skill when you are about to:
- Write product code that implements a compliance rule (data retention, PII handling, claim handling, underwriting, policy logic).
- Answer the user's question about how the business behaves in a regulated area.
- Make a design decision that hinges on a domain rule.

If you are doing unrelated work (UI tweaks, infra, generic refactors), this skill does not apply.

## Procedure

### Phase 1 — Discovery (`search_topic`)

Run:
```bash
dks wiki search "<query>"
```
This returns a JSON array of matching wiki entries, each with `slug`, `topic`, `source_refs`, and a `snippet`.

Read the snippets. The snippet is **not** authoritative — it's a discovery hint to help you pick which source blocks to fetch next.

If no entries match:
- Tell the user the topic is not yet in the KB.
- Do NOT fabricate facts. Either ask the user to compile a wiki entry (`dks-compile-wiki` skill) or proceed without grounding and clearly say "this is an assumption, not a cited fact."

### Phase 2 — Fact substrate (`get_source`)

For each `block_id` in the `source_refs` of a relevant hit, run:
```bash
dks blocks get "<block_id>"
```
This returns the block as JSON: `{source_file, block_id, locator, block_type, content}`. The `content` is the verbatim source text. The `locator` is the citation primitive (page, section/clause for PDFs; sheet+cells for Excel; etc.).

Use `content` as your source of truth, not the wiki snippet.

If you need adjacent context (the block before or after), use:
```bash
dks blocks list "<source_file>"
```
to enumerate blocks for that source, then fetch by `block_id` as above.

### Phase 3 — Emit cited facts

When you write code, documentation, or an answer that uses a fact you extracted:
- Quote or paraphrase the verbatim block content.
- Always include the citation in a form that traces back to source. Examples:
  - In code comments: `# Retention rule: 7 years (source: claims.pdf p20 §5.1, block claims.pdf#p20#5.1)`
  - In prose: `Claims must be filed within 30 days [source: claims.pdf#p14#3.2].`
  - In a PR description: a "Sources" section listing each block_id you relied on.

## Contract — what you must NOT do

- **No uncited extracted fact.** If you would write a sentence stating a domain rule and you cannot end it with a citation tracing back to a `block_id` you fetched, do not write the sentence. Ask for clarification, or write the code without the rule (and surface that to the user).
- **No reliance on the wiki snippet alone.** The snippet is for discovery. Cite the source block, not the wiki entry.
- **No quoting beyond the verbatim block content.** If you need a longer passage than one block contains, fetch the adjacent blocks (`dks blocks list <source_file>` to enumerate, then `dks blocks get`).
- **No fabricated block_ids.** Only cite block_ids that were actually returned by a CLI call in this session.

## Abstention

If after Phase 1 + Phase 2 you cannot find a block that supports the claim you need, **abstain**. Tell the user clearly:

> "The KB does not contain a citation for X. I can proceed without grounding (and you can verify against authoritative sources later), or you can compile a wiki entry first using the dks-compile-wiki skill."

This is the right behavior — citation discipline matters more than confident guessing.

## Cost guidance

A typical grounding query is one `dks wiki search` (≤ 1KB output) plus a handful of `dks blocks get` calls (small JSON each). No LLM tokens are needed for the CLI calls themselves — the LLM work is just reading the returned content. Budget: trivial.
