# Domain Knowledge Skill — Architecture Spec

**Date:** 2026-05-21
**Status:** Draft, pending user review
**Scope:** Generic life-insurance domain (public OSS)

## 1. Purpose

A domain-knowledge skill that Claude Code invokes when building life-insurance product code, so that compliance-sensitive logic (data retention, PII handling, claim / underwriting / policy / product rules, and other regulated requirements) is grounded in citable source material rather than guessed.

Every fact returned by the skill carries a citation pointing back to source file + page/section/clause. The skill is the only sanctioned path for the coding agent to learn a domain rule.

The architecture is intentionally generic across the life-insurance domain — applicable to any regulated insurer (claims handling, underwriting, product disclosure statements, policy schedules, actuarial assumptions, regulator filings). No employer-specific data, terminology, or processes are baked in.

## 2. Scope and Non-Goals

### In scope
- Ingest life-insurance domain docs (PDF, DOCX, Excel, Markdown) into a citation-preserving local store.
- Build a discovery wiki and per-document hierarchical indices.
- Expose a Claude Code skill with a narrow tool contract that makes citation structurally mandatory.
- Validate against a baseline-vs-treatment eval on real compliance-sensitive coding tasks.

### Explicit non-goals
- Not a human-facing search portal (no chat UI, no Notion replacement).
- Not a general-purpose "ask anything about the business" assistant. Scoped to compliance / domain rules that affect code.
- Not a vector database. No embeddings in v0.
- Not a knowledge graph or GraphRAG-style system.
- Not multi-tenant or org-wide-deployed in v0. Single user, single consumer (Claude Code on local machine).
- Not an adaptive multi-strategy retrieval framework. Adaptive *ingestion* (parser per doc type) is in scope; adaptive *retrieval* is deferred until eval evidence demands it.

### Build vs buy
Ruled out in favour of in-house build on data-residency, compliance, and cost grounds that are typical of regulated life-insurance contexts (sensitive policyholder data, jurisdiction-specific retention rules, audit-grade citation requirements). Recorded, not revisited.

## 3. Success Criterion (v0)

On a set of ~20 coding tasks in compliance-sensitive areas, Claude Code-with-skill produces:

1. Fewer compliance-rule violations than Claude Code-without-skill (baseline).
2. Accurate citations on every claimed fact (file + page/section/clause/cell).
3. Zero facts emitted without a citation traceable to a real source span.

The eval is the gate. Architecture choices are subordinate to eval outcomes.

## 4. Architecture

Six layers, each with one clear responsibility. The seams are designed so any single layer can be swapped without rewriting the others.

### Layer 1 — Ingestion (adaptive per doc type)

A parser per document format, each preserving the citation primitive native to that format.

| Format | Parser              | Citation primitive               |
|--------|---------------------|----------------------------------|
| PDF    | MinerU              | file + page + section/clause     |
| DOCX   | Docling             | file + section + paragraph idx   |
| Excel  | pandas / openpyxl   | file + sheet + cell range        |
| MD     | pass-through        | file + heading path + line range |
| Code   | pass-through        | file + line range                |

Output of every parser is a *typed content list* using the RAG-Anything JSON shape: `{type, content, page_idx | sheet_ref | section_ref, ...}`. This is the only output format downstream layers consume.

RAG-Anything's parsers and content-list shape are reused. Its LightRAG-based retrieval is rejected (wrong fit for clause-structured compliance docs and the citation discipline we require).

### Layer 2 — Normalization to citation-preserving Markdown

The typed content list is converted into Markdown blocks. Each block carries frontmatter with its source coordinates.

```markdown
---
source_file: policies/claims_handling.pdf
page: 14
section: "3.2"
clause: "3.2.1"
block_id: claims_handling.pdf#p14#3.2.1
---
Claims must be filed within 30 days of the incident, subject to subsection 3.2.2.
```

Citation discipline is enforced *structurally* at ingestion: blocks without a complete citation primitive are rejected. The downstream system has no way to handle un-cited content — there is no representation for it.

### Layer 3 — PageIndex layer (per long structured document)

For each long structured doc (policy PDFs, technical manuals, regulatory filings), an LLM builds a tree-of-contents at ingestion time (amortised cost, not per-query). The tree is stored as sidecar JSON next to the normalized Markdown.

The PageIndex tree is consulted when the agent needs to navigate within a single document to a precise clause — for example, when `search_topic` returns a discovery hit and the agent needs to walk to the exact section to extract a verbatim fact.

Short documents (< ~30 pages) skip PageIndex; flat block lookup is sufficient.

### Layer 4 — Compiled wiki (discovery only, AlexChen31337 style)

An LLM compiles topic articles (e.g. "PII handling rules for life-insurance products", "Claims retention requirements", "Underwriting decision rules"). The wiki is the agent's table of contents through the corpus.

**Critical rule: wiki entries are summaries that point at PageIndex nodes / Markdown block IDs. They are *not* standalone facts.** The agent reads the wiki to find *where to look*. It must walk back to the source via `get_source` for anything it cites.

A lint pass detects broken links, contradicting summaries, and missing topics.

### Layer 5 — Skill interface (Claude Code, v0)

**Architecture refinement (2026-05-21):** All LLM-driven operations — PageIndex tree builds, wiki compile, lint, and eval — are exposed as **Claude Code skill commands**, not as in-process LLM calls from the `dks` Python package. The Python package stays deterministic (parsers, normalization, storage, file IO, CLI). Skills orchestrate the LLM judgment and invoke the `dks` CLI for any deterministic step (read blocks, persist tree, write wiki entry).

Consequences:
- No `ANTHROPIC_API_KEY` or other provider credentials in the `dks` package.
- No LLM client code, no prompt management, no cost accounting inside Python — Claude Code's existing auth and billing handles all of it.
- A new user installs the `dks` Python package (deterministic) **and** copies the skills directory into their `~/.claude/skills/` (LLM-driven). Both halves are version-controlled in the same repo.

The narrow tool contract below describes the **consumer-facing** skill (what other agents call when they need to ground a fact). Internal skills (`build-pageindex`, `compile-wiki`, `lint-wiki`) live alongside.

Two tools with a narrow contract. The narrowness is what makes citation discipline enforceable.

**`BlockRef`** is the opaque string identifier of a normalized block. Format:
`<source_filename>#<locator>` where `<locator>` is `p<page>#<section>` for PDFs,
`s<sheet>!<cell_range>` for Excels, `§<section_path>` for DOCX, `L<start>-<end>` for
Markdown/code. Example: `claims_handling.pdf#p14#3.2.1`. Consumers treat it as
opaque; only the skill internals parse it.

```
search_topic(query: str) -> List[{
  topic: str,
  summary: str,
  source_refs: List[BlockRef]
}]

get_source(ref: BlockRef) -> {
  verbatim_text: str,
  citation: {
    file: str,
    page: int | null,
    sheet: str | null,
    cells: str | null,
    section: str | null,
    clause: str | null,
    block_id: BlockRef
  }
}
```

The skill's system prompt makes the contract explicit and forbidden patterns clear:

> Any extracted or quoted fact you emit MUST be the result of a prior `get_source` call. Summaries from `search_topic` are discovery hints, not citable facts. If you cannot find a source via `get_source`, you must abstain and tell the user the rule is not in the KB.

A verification step (optional in v0, recommended in v1) post-checks every claimed citation in the agent's output against the `block_id`s that were actually returned to it.

### Layer 6 — Refresh and governance

- File watcher on `raw/` re-runs ingestion (layers 1-3) for changed documents.
- Lint pass runs on schedule, detects rot (broken refs, contradicting summaries, orphan blocks).
- Wiki recompile diffs are reviewable in git: when a policy doc changes, you see exactly which wiki entries shifted.
- Manual review gate for compile-step diffs in v0. (Auto-merge can come later if diffs prove trustworthy.)

## 5. Storage Layout

File-over-app, git-tracked. Matches the audit/compliance posture typical of regulated life-insurance work and gives change history for free.

```
raw/         # originals, immutable, copied on ingest
normalized/  # citation-preserving Markdown blocks (one file per source doc, or per section for very large docs)
index/       # PageIndex trees as sidecar JSON, one per long doc
wiki/        # compiled topic articles + INDEX.md
eval/        # 20 questions, baseline vs treatment runs, scores
skill/       # the Claude Code skill package (manifest, tool implementations)
```

## 6. v0 First Slice

The smallest version that proves or refutes the hypothesis.

### Corpus
- One compliance-sensitive area chosen first: **PII handling rules** (decision pending user pick).
- 5-10 documents covering that area (policy PDFs + any related schemas/specs).

### Eval
- ~20 representative coding tasks in the chosen area (e.g. "build a form that captures customer details", "add audit logging to claim submission").
- Each task scored on: rule violations introduced, citation accuracy, citation completeness (every claim has one), latency, cost.
- Run two arms:
  - **Baseline:** Claude Code with no KB skill.
  - **Treatment:** Claude Code with KB skill loaded.
- Treatment must beat baseline measurably on violations and citation completeness, with acceptable latency/cost.

### Build order
1. Parser layer for the 2-3 formats actually present in the v0 corpus (skip the rest).
2. Normalization to citation-preserving Markdown.
3. PageIndex for any long doc; skip for short.
4. Compiled wiki over the 5-10 docs.
5. Skill package with `search_topic` and `get_source`.
6. Eval harness; run baseline first, then treatment.

### Stop conditions
- If treatment does not beat baseline measurably, **stop and rethink** before scaling corpus.
- If citation completeness drops below 100%, **fix the contract before adding more docs**.

## 7. Open Questions

These are unresolved and should be answered before / during implementation. They are not blockers for the spec, but they will need decisions.

1. **Which compliance area for v0?** PII handling, claims rules, data retention — pick one. Recommendation: pick the one where you can name the most concrete recent CC failure.
2. **Refresh trigger granularity.** File watcher per-doc vs polling vs git pre-commit hook on the `raw/` dir. Probably file watcher; needs prototype.
3. **Compile-prompt design.** The wiki-compile LLM call must produce summaries that always cite back to block IDs. The prompt and the schema enforcement need careful design; expect 1-2 days of iteration.
4. **`get_source` granularity.** Block-level by default; do we ever need clause-level sub-spans? Defer until a real query demands it.
5. **Conflict handling.** When two docs say contradictory things (old vs new policy, two jurisdictions), which wins? Default: surface both via `search_topic`, let the agent flag the conflict; refine when first conflict appears in eval.
6. **Cost ceiling.** PageIndex tree build + wiki compile are LLM-heavy at ingest. Set a per-doc budget; alert if exceeded.
7. **What if LLM compile produces uncited summaries?** Rejection + retry up to N times, then escalate to manual.
8. **Authorization for future multi-user.** v0 sidesteps (single user). Deferred but flagged.
9. **MCP vs Claude Code skill.** v0 ships as a Claude Code skill (single named consumer). MCP wrapping can come later if a second consumer (a non-Claude-Code agent) emerges.

## 8. Out of Scope for v0 (deferred to v1+)

Each of these is something to add behind the clean seams already in place, but only when eval evidence demands it.

- Vector embeddings / semantic similarity retrieval.
- Knowledge-graph or entity-extraction layers.
- Adaptive retrieval dispatcher (multi-strategy framework).
- MCP server interface for non-Claude-Code consumers.
- Multi-tenant access control / per-section auth.
- Web UI for human browsing.
- Auto-merge of compile diffs (manual review only in v0).

## 9. References

- AlexChen31337/llm-knowledge-base — LLM-compiled wiki + lint pattern, agent-skill packaging.
- VectifyAI/PageIndex — hierarchical document tree, reasoning-based retrieval, vectorless.
- HKUDS/RAG-Anything — ingestion-parser pipeline (MinerU/Docling/PaddleOCR + VLM), typed content list shape. **Parsers reused; retrieval stack rejected.**
- microsoft/graphrag — entity/community graph approach. **Rejected as wrong fit for clause-structured compliance docs.**
