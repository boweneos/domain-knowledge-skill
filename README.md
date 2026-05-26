# domain-knowledge-skill (`dks`)

A citation-grounded knowledge skill for AI coding agents working in regulated life-insurance contexts.

When Claude Code (or any consumer agent) writes code that touches regulated logic — PII handling, data retention, claim / underwriting / policy / product rules — every fact it relies on must trace back to a verifiable citation: file + page/section/clause for PDFs, sheet + cell range for Excels, paragraph index for DOCX, line range for Markdown. No uncited facts. The skill makes citation discipline structural, not optional.

## Status

**Shipped end-to-end. Current version: 0.2.2.** Four phases merged to `main` and tagged:

| Tag | What |
|---|---|
| `phase-1-complete` | Citation primitives, normalizer, writer, Markdown parser, `dks ingest` CLI. |
| `phase-2-complete` | Excel / DOCX / PDF parsers, block + PageIndex + wiki storage, three LLM-orchestration skills. |
| `phase-3-complete` | Keyword search, consumer-facing `dks-search` skill, eval scaffolding. |
| `phase-4-complete` | **Cascaded KB**: global `~/.dks/` + auto-discovered project `.dks/` layers. Project shadows global; writes default to project. v0.2.0 (breaking CLI flag rename). |
| `v0.2.1` (patch) | Walker fix: auto-discovery no longer matches the global default location as a project layer when no closer `.dks/` exists. Surfaced by real end-to-end testing in a second repo. |
| `v0.2.2` (minor) | **Divergence warning** on `dks blocks get` when a project block shadows a global block with different content (stderr WARN + `shadows` field in JSON). **`dks layers list`** introspection subcommand prints active layers with resolution source (explicit / env / auto-discover / default) for debugging. |

110 tests passing, mypy strict + ruff clean. End-to-end smoke verified on the project's own design spec, on layer cascade behaviour, and on a real cross-repo install (global at `~/.dks/`, project at `<other-repo>/.dks/`).

---

## Quick start (5 minutes)

```bash
# 1. Clone the repo and install the Python CLI globally
git clone git@github.com:boweneos/domain-knowledge-skill.git
cd domain-knowledge-skill
uv tool install --editable .   # puts `dks` on ~/.local/bin/dks, reflects live source edits
#   (Or `uv sync --all-groups` if you'd rather invoke via `uv run dks ...`)
```

```text
# 2. Install as a Claude Code plugin — run inside a Claude Code session.
#    Pick ONE of these two paths.

# 2a. Local install (no GitHub required — works with your clone directly):
/plugin marketplace add /Users/bowen.li/development/KB
/plugin install dks@dks

# 2b. GitHub install (persistent + auto-updating from the public repo):
/plugin marketplace add boweneos/domain-knowledge-skill
/plugin install dks@dks

#  Verify either: /plugin    (Installed tab should list "dks")
#  Full installation reference (dev mode, manual fallback): docs/USAGE.md → Installation.
```

```bash
# 3. Drop your domain docs into raw/
mkdir -p raw/policies
cp /path/to/your/policy.pdf raw/policies/claims_handling.pdf
```

```text
# 4. Ingest — slash command from inside Claude Code, or CLI from a shell
/dks:ingest raw/policies/claims_handling.pdf
#  → wrote N blocks to normalized/policies/claims_handling.pdf/
#  CLI equivalent: uv run dks ingest raw/policies/claims_handling.pdf

# 5. Build PageIndex + compile your first wiki entry (all from Claude Code)
/dks:build-pageindex policies/claims_handling.pdf
/dks:compile-wiki "Claim filing windows" claim-filing-windows policies/claims_handling.pdf
```

Once `wiki/` has entries, any future Claude Code session has two paths in:
- **Auto-activation** — the `dks-search` skill triggers when you work on regulated code.
- **Explicit** — `/dks:search "<query>"` whenever you want grounding on demand.

---

## The lifecycle

```
   ┌─────────────┐    dks ingest    ┌──────────────┐
   │   raw/      │ ───────────────▶ │ normalized/  │  citation-preserving
   │ PDF/DOCX/   │                  │  blocks (md  │  Markdown blocks
   │ XLSX/MD     │                  │  + frontmatter)
   └─────────────┘                  └──────────────┘
                                          │  │
                          ┌───────────────┘  └────────────┐
                          ▼                                ▼
                  ┌──────────────┐                ┌──────────────┐
                  │   index/     │                │   wiki/      │
                  │  PageIndex   │ ◀──────────────│  topic       │
                  │  trees       │   linked via   │  articles    │
                  └──────────────┘   block_ids    └──────────────┘
                          ▲                                ▲
                          │ dks-build-pageindex            │ dks-compile-wiki
                          │ (Claude Code skill)            │ (Claude Code skill)
                          │                                │
                          └────────────┬───────────────────┘
                                       ▼
                              ┌──────────────────┐
                              │   dks-search     │
                              │ (consumer skill, │   ←—  invoked by Claude Code
                              │  enforces "no    │       when it works on
                              │  uncited fact")  │       compliance-sensitive code
                              └──────────────────┘
                                       │
                                       │ periodic audit
                                       ▼
                              ┌──────────────────┐
                              │  dks-lint-wiki   │
                              │ (read-only       │
                              │  citation audit) │
                              └──────────────────┘
```

**Deterministic layer (`dks` Python package):** parsing, normalization, citation guard, file IO, CLI. No LLM, no network, no API keys.

**Judgment layer (Claude Code skills under `skills/`):** the LLM work — building trees, composing wiki articles, grounding consumer answers — lives in skill prompts. Each skill invokes the `dks` CLI for any deterministic step. Claude Code's own auth handles billing; nothing leaks outside it.

---

## Skills + commands cheat-sheet

The plugin ships **four skills** (auto-activated by Claude Code when conversation context matches) and **five slash commands** (explicit user-triggered).

### Skills (auto-activated)

| Skill | When to invoke | What it does |
|---|---|---|
| **`dks-search`** ← consumer-facing | Working on regulated code (compliance, PII, claims, underwriting, policy logic) | Discovery via `dks wiki search`; fetches verbatim source via `dks blocks get`; enforces "no uncited extracted fact"; abstains when KB lacks the rule. |
| `dks-build-pageindex` | After ingesting a long structured source (policy PDF, spec doc, technical manual) | Lists blocks, reasons over structure, writes hierarchical tree to `index/<source>.pageindex.json`. |
| `dks-compile-wiki` | When a domain topic deserves a reusable article (e.g. "PII fields requiring encryption") | Gathers relevant blocks, composes a Markdown article with inline `[ref: <block_id>]` citations on every claim, writes to `wiki/<slug>.md`. |
| `dks-lint-wiki` | Periodically or after re-ingesting sources | Walks every wiki entry, verifies every cited `block_id` still exists, surfaces drift and possible contradictions. Read-only. |

### Commands (explicit slash invocation)

| Command | Args | What it triggers |
|---|---|---|
| `/dks:ingest` | `<path-to-source-file>` | Runs the `dks ingest` CLI; suggests a next step based on the source shape. |
| `/dks:build-pageindex` | `<source_file>` | Invokes `dks-build-pageindex` skill. |
| `/dks:compile-wiki` | `<topic> <slug> [<source_file>...]` | Invokes `dks-compile-wiki` skill. |
| `/dks:search` | `<topic or query>` | Invokes `dks-search` skill explicitly (skill also auto-activates from conversation context). |
| `/dks:lint` | _(no args)_ | Invokes `dks-lint-wiki` skill — corpus-wide audit. |

**When to use which:** Let Claude Code auto-activate skills during free-form work on regulated code. Reach for `/dks:*` commands when you want explicit control — kicking off a batch ingestion, building an index right after dropping in a doc, or running lint on a schedule.

---

## Best-outcome usage patterns

These are the patterns that maximize the value of the KB. The skill prompts already encode most of this — these are the patterns to keep in mind as the operator.

### Curate raw/ thoughtfully

The KB is only as good as what you ingest. Prefer:
- **Authoritative sources.** Final policy docs, regulator filings, signed PDS, technical specs that are the system of record.
- **Stable copies.** Snapshot the version you ingested. Policies change; the KB should record what was true on what date.
- **Structured docs.** PageIndex shines on policy PDFs and spec docs with real headings and clause numbering. Scanned image-only PDFs need OCR upstream — not in scope.

Avoid ingesting drafts, working docs, or wiki exports that themselves cite uncited claims.

### Build PageIndex trees once per source, then forget

Tree builds are one-time amortised cost per source. After ingesting a doc, immediately invoke `dks-build-pageindex` against it. The tree becomes part of the substrate other skills navigate.

### Compile wikis topic-by-topic, not doc-by-doc

A wiki entry should answer a single domain question (e.g., "PII fields requiring encryption", "Claim filing window rules", "Maximum retention periods by jurisdiction") and pull blocks from however many sources it needs. Do **not** create one wiki entry per source PDF — the wiki is for discovery across docs, not a mirror of the corpus.

### Re-lint after every re-ingest

When a source doc changes and you re-ingest:
1. The `block_id`s for changed sections may shift (line ranges move).
2. Wiki entries that cite the old `block_id`s now have broken refs.
3. Run `dks-lint-wiki` to surface every broken citation.
4. Re-compile the affected wiki entries via `dks-compile-wiki`.

### Trust abstention over false confidence

If `dks-search` can't find a block to ground a claim, the right behavior is for Claude Code to **abstain** — say "the KB does not contain a citation for X" — not guess. This is the contract. When you see Claude Code abstain on a topic, that's a signal to either compile a wiki entry covering it or accept that the rule isn't authoritative.

### Use git as the audit trail

`raw/`, `normalized/`, `index/`, and `wiki/` are all file-over-app and git-trackable in **each layer**. The repo's own `.gitignore` excludes top-level `normalized/` and `raw/` (regenerable / sensitive); `wiki/` and `index/` are committable so the human-reviewed knowledge state is diffable.

For project layers (a `.dks/` directory inside a product repo), pick a convention per repo:
- Commit `.dks/wiki/` and `.dks/index/` so teammates see the same override state.
- Gitignore `.dks/raw/` and `.dks/normalized/` unless you want full reproducibility from this repo alone.

The global layer (`~/.dks/`) lives in your home directory and isn't tracked by any repo — back it up separately or rebuild it on demand from a source-of-truth corpus directory.

---

## CLI reference

All deterministic operations. Skills invoke these; you can also run them directly.

### Top-level layer flags (apply to every subcommand)

| Flag | Default | What |
|---|---|---|
| `--project <path>` | auto-discover `.dks/` | Explicit project layer base. Overrides `DKS_PROJECT` env. |
| `--global <path>` | `~/.dks/` | Explicit global layer base. Overrides `DKS_GLOBAL` env. |
| `--no-global` | global is active | Suppress the global layer entirely (project-only mode). |

### Subcommands

| Command | Purpose |
|---|---|
| `dks layers list` | Print active layers with resolution source (env / auto-discover / explicit / default) and existence. Useful for debugging. |
| `dks ingest <path> [--root DIR] [--write-global]` | Parse + normalize + write blocks. `--root` (default `raw/`) defines the relative `source_file` path. Writes to project layer by default; `--write-global` forces global. |
| `dks blocks list <source_file>` | List `BlockHit`s across active layers: `[{"block_id", "layer"}, ...]` (deduped, project shadows global). |
| `dks blocks get <block_id>` | Print `{"block": {...}, "layer": "..."}` from the first layer that has it. |
| `dks pageindex write <source_file> [--write-global]` | Read JSON tree from stdin, persist as `<layer>/index/<source>.pageindex.json`. |
| `dks pageindex read <source_file>` | Print `{"tree": {...}, "layer": "..."}`. |
| `dks wiki write <slug> [--write-global]` | Read `{topic, source_refs, body}` JSON from stdin, persist as `<layer>/wiki/<slug>.md`. |
| `dks wiki read <slug>` | Print `{"entry": {...}, "layer": "..."}`. |
| `dks wiki list` | List all wiki slugs across active layers: `[{"slug", "layer"}, ...]`. |
| `dks wiki search <query>` | Keyword search over topic + body across layers; each `SearchHit` carries a `layer` tag. |

Use `--help` on any subcommand for flags and defaults. Full layer semantics are documented in [`docs/USAGE.md` → Cascaded KB layers](docs/USAGE.md#cascaded-kb-layers).

---

## Architecture summary

- **Adaptive ingestion** per doc type → typed content list (RAG-Anything parser shape).
- **Normalization** → citation-preserving Markdown blocks. Blocks without a complete citation primitive are rejected at ingest by `citation_guard`.
- **PageIndex layer** per long structured document — hierarchical tree, built once by an LLM via the `dks-build-pageindex` skill, stored as sidecar JSON.
- **Compiled wiki** for discovery — every claim in every wiki article carries inline `[ref: <block_id>]` citations.
- **Two-tool consumer contract** — `dks wiki search` (discovery) + `dks blocks get` (fact substrate). Citation is the only path to a fact.
- **File-over-app storage**, git-tracked, audit-friendly.
- **Two-layer KB**: global `~/.dks/` (cross-project rules) + auto-discovered project `.dks/` (overrides and additions). Project shadows global on reads; writes default to project. See [`docs/USAGE.md` → Cascaded KB layers](docs/USAGE.md#cascaded-kb-layers).

No vector embeddings, no entity graph, no adaptive retrieval dispatcher in v0. Each is a deferred extension that can plug into the existing seams when eval evidence demands it.

Full design rationale: [`docs/superpowers/specs/2026-05-21-domain-knowledge-skill-design.md`](docs/superpowers/specs/2026-05-21-domain-knowledge-skill-design.md).
Walkthrough with a worked example: [`docs/USAGE.md`](docs/USAGE.md).

---

## Why not just use existing RAG?

The defining requirement is **structural enforcement of citation**: a consumer agent is contractually forbidden from emitting a quoted or extracted fact unless it was obtained via a source-fetch call that returned the verbatim span plus citation metadata. Most off-the-shelf RAG systems treat citation as an *attribute of the answer*; this design treats it as *the only path to an answer*.

This matters when wrong answers carry regulatory weight. A retrieval system that produces a plausible-sounding paraphrase of a policy clause is a compliance hazard; a system that hands the agent the verbatim clause and a citation, and refuses to do anything else, is not.

---

## References and prior art

- `AlexChen31337/llm-knowledge-base` — LLM-compiled wiki + lint pattern (adopted).
- `VectifyAI/PageIndex` — hierarchical doc tree, vectorless retrieval (adopted for long structured docs).
- `HKUDS/RAG-Anything` — ingestion parsers + typed content list (adopted); LightRAG retrieval (not adopted).
- `microsoft/graphrag` — entity / community graph (not adopted — wrong fit for clause-structured compliance docs).

---

## License

MIT — see [LICENSE](LICENSE).
