# domain-knowledge-skill

A citation-grounded domain-knowledge skill for AI coding agents working in regulated life-insurance contexts.

The goal: when an AI coding agent writes product code that touches regulated logic (data retention, PII handling, claim / underwriting / policy / product rules), every fact it uses must be grounded in a verifiable citation back to source documents — file, page/section/clause, or sheet/cell.

## Status

Design / spec phase. Architecture and v0 scope are documented in
[`docs/superpowers/specs/2026-05-21-domain-knowledge-skill-design.md`](docs/superpowers/specs/2026-05-21-domain-knowledge-skill-design.md).
No implementation yet.

## Architecture summary

- **Ingestion** (adaptive per doc type) → typed content list using the RAG-Anything parser shape.
- **Normalization** → citation-preserving Markdown; blocks without a citation primitive are rejected at ingest.
- **PageIndex layer** per long structured document (hierarchical tree, LLM-built at ingestion).
- **Compiled wiki** (discovery only) — summaries that point at source blocks; never standalone facts.
- **Claude Code skill** with two narrow tools: `search_topic` (discovery) and `get_source` (verbatim source + citation).
- **File-over-app storage**, git-tracked.

No vector embeddings, no entity graph, no adaptive retrieval dispatcher in v0. Each is a deferred extension that can plug into the existing seams when eval evidence demands it.

## Why not just use existing RAG?

The defining requirement is **structural enforcement of citation**: the agent is contractually forbidden from emitting a quoted or extracted fact unless it was obtained via a source-fetch call returning the verbatim span plus citation metadata. Most off-the-shelf RAG systems treat citation as an attribute of the answer; this design treats it as the only path to an answer.

## References and prior art

- `AlexChen31337/llm-knowledge-base` — LLM-compiled wiki + lint pattern (adopted).
- `VectifyAI/PageIndex` — hierarchical doc tree, vectorless retrieval (adopted for long structured docs).
- `HKUDS/RAG-Anything` — ingestion parsers + typed content list (adopted); LightRAG retrieval (not adopted).
- `microsoft/graphrag` — entity/community graph (not adopted — wrong fit for clause-structured compliance docs).

## License

MIT — see [LICENSE](LICENSE).
