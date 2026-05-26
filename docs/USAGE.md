# Usage — A Worked Example

This walks through the full lifecycle of `dks` with a realistic example: a life-insurer ingests a claims-handling policy PDF, builds an index, compiles a topic wiki, then has Claude Code write a feature that needs to respect the policy's rules.

The session is annotated so you can map each step to either the **deterministic CLI** (you or the skill runs it) or the **Claude Code skill** (LLM judgment).

---

## Installation

`dks` has **two halves** that install separately:
1. The **Python package** (`dks` CLI: ingest, blocks, pageindex, wiki, wiki search) — installed via `uv`.
2. The **Claude Code plugin** (4 skills + 5 slash commands) — installed via Claude Code's `/plugin` machinery.

### Half 1 — Python package

Pick one of two install patterns:

#### A. `uv tool install` (recommended — `dks` on global PATH)

```bash
git clone git@github.com:boweneos/domain-knowledge-skill.git
cd domain-knowledge-skill
uv tool install --editable .
which dks                                # → ~/.local/bin/dks
dks --help                                # smoke check
```

Editable install means the binary follows your dev clone — `git pull` and edits to source flow through automatically. This is the install pattern used when the plugin's skills need to invoke `dks` from any working directory (including other repos).

To uninstall later: `uv tool uninstall dks`.

#### B. `uv sync` (in-project venv, invoke via `uv run`)

```bash
git clone git@github.com:boweneos/domain-knowledge-skill.git
cd domain-knowledge-skill
uv sync --all-groups
uv run dks --help                         # smoke check
uv run pytest                             # full suite — 95 passing expected
```

The CLI is invokable as `uv run dks ...` from inside this clone only. Useful for dev work on `dks` itself; skills running from other repos won't find `dks` on PATH.

### Half 2 — Claude Code plugin

Choose one of four paths. **A or B for normal use; C for plugin development; D as a last-resort fallback.**

The repo is laid out as a Claude Code **marketplace** containing a single plugin:

```
domain-knowledge-skill/        ← marketplace root
├── .claude-plugin/
│   └── marketplace.json       ← marketplace catalog (lists the dks plugin)
└── dks/                       ← the plugin itself
    ├── .claude-plugin/
    │   └── plugin.json        ← plugin manifest (name, version, etc.)
    ├── skills/
    └── commands/
```

The marketplace `name` and the plugin `name` both happen to be `dks`, so install commands consistently use `dks@dks` (`<plugin>@<marketplace>`).

#### Path A — Local persistent install (recommended for personal use)

You've cloned the repo and want to install the plugin from that directory. **No GitHub roundtrip; survives Claude Code restarts.** Inside a Claude Code session:

```text
/plugin marketplace add /Users/bowen.li/development/KB
/plugin install dks@dks
```

`/plugin marketplace add` accepts either an absolute path or a relative path (resolved from your current working directory). It can also point at a `marketplace.json` file directly if you prefer:

```text
/plugin marketplace add /Users/bowen.li/development/KB/.claude-plugin/marketplace.json
```

Verify:
```text
/plugin            # Installed tab should list "dks"
```

When you change skill/command files in the clone and want Claude Code to pick them up:
```text
/plugin marketplace update dks
```

#### Path B — GitHub marketplace install (recommended for distribution / team use)

Same idea, but pointed at the public repo. **Survives restarts AND auto-updates daily.** Inside a Claude Code session:

```text
/plugin marketplace add boweneos/domain-knowledge-skill
/plugin install dks@dks
```

Auto-update is on by default. Toggle off in `/plugin` → Marketplaces tab → "Enable auto-update."

#### Path C — `--plugin-dir` (plugin development, session-only)

Useful when you're iterating on the plugin contents and want to see changes without re-running `/plugin marketplace update`.

```bash
claude --plugin-dir /Users/bowen.li/development/KB/dks
```

Note this points at the plugin directory (`dks/`), not the marketplace root. The plugin loads for the current session only; re-pass the flag next launch. If Claude Code is already running, use `/reload-plugins` to refresh.

#### Path D — Manual skill copy (fallback)

If `/plugin` machinery isn't available in your Claude Code version, you can still get the skills (but not the slash commands):

```bash
mkdir -p ~/.claude/skills
cp -r dks/skills/dks-search dks/skills/dks-build-pageindex \
      dks/skills/dks-compile-wiki dks/skills/dks-lint-wiki \
      ~/.claude/skills/
```

Skills activate by name in conversation. You won't have `/dks:*` slash commands.

### Verifying everything wired up

After Path A, B, or C, in a Claude Code session:

```text
/plugin                          # → Installed tab lists "dks"
/dks:search "test"               # → invokes the search skill (likely abstains on empty wiki)
```

After Path D:

> Ask Claude Code: "Use the dks-search skill on the topic 'test'."

The skill activates by name (no slash command available on Path D).

### Updating

```text
/plugin marketplace update dks
```

Path A picks up your local file changes. Path B picks up new commits from GitHub. Path C reloads from the on-disk plugin dir on `/reload-plugins`.

### Uninstall

```text
/plugin uninstall dks@dks
/plugin marketplace remove dks    # optional — also drops the marketplace registration
```

For Path D, `rm -rf ~/.claude/skills/dks-*`.

### Common pitfalls

- **Marketplace root vs plugin root are different directories.** The marketplace lives at the repo root (where `.claude-plugin/marketplace.json` is). The plugin lives one level down at `dks/` (where `dks/.claude-plugin/plugin.json` is). `/plugin marketplace add` always wants the marketplace root; `--plugin-dir` always wants the plugin root.
- **The plugin name and the marketplace name happen to both be `dks`.** That's why the install command is `/plugin install dks@dks` (`<plugin-name>@<marketplace-name>`) rather than something like `dks@dks-marketplace`. If you fork and rename either, update the install command accordingly.
- **Skills + commands must live at plugin root, not under `.claude-plugin/`.** Our `dks/skills/` and `dks/commands/` are at the plugin root. Only `plugin.json` and `marketplace.json` live under `.claude-plugin/`.
- **Version pinning matters for updates.** `dks/.claude-plugin/plugin.json` carries a `version` field. Bump it when shipping behaviour changes — that's the signal Claude Code uses to offer updates. Without a version bump on GitHub installs, the auto-updater treats commit SHAs as the version key and any push re-pulls.
- **The Python and plugin halves are independent.** Plugin install does NOT install the `dks` Python CLI — skills shell out to `dks`, so the CLI must be on PATH (or `uv run dks` from a known directory) for skills to work. Always do Half 1 before relying on the plugin in anger.

---

## Cascaded KB layers

`dks` supports a two-layer KB so a single plugin install can serve multiple projects without duplicating company-wide content into every repo.

### The two layers

| Layer | Default location | Override |
|---|---|---|
| **Global** | `~/.dks/` | `DKS_GLOBAL=/path/to/global` env var, or `--global /path` CLI flag |
| **Project** | Auto-discovered (walk up from CWD looking for a `.dks/` directory) | `DKS_PROJECT=/path/to/project/.dks` env var, or `--project /path` CLI flag |

Each layer is a directory containing the four subdirs `raw/`, `normalized/`, `index/`, `wiki/` — the same layout the CLI used in single-layer mode.

### Read semantics — project shadows global

Every read cascades **project first, fall back to global**. Specifically:

- `dks blocks get <id>` — tries project, falls back to global. Output JSON includes a `layer` field: `{"block": {...}, "layer": "project"}`.
- `dks blocks list <source>` — merges block_ids from both layers, deduped (project shadows global on collision). Output: `[{"block_id": "...", "layer": "project|global"}, ...]`.
- `dks wiki list` — same dedup-and-tag for slugs.
- `dks wiki read <slug>` — same project-first cascade with `layer` tag.
- `dks wiki search <query>` — searches both layers; each hit carries `layer`.
- `dks pageindex read <source>` — same cascade.

### Write semantics — project by default

Writes go to the **project layer** when one exists. If no project layer is active (you're outside any `.dks/`-marked directory), writes go to global. Pass `--write-global` on `ingest` / `pageindex write` / `wiki write` to force the global layer regardless.

### When to write to which

| Content | Where | Why |
|---|---|---|
| Company-wide policies, regulations, standards that every project should consult | **Global** | Single source of truth across products; `--write-global` |
| Project-specific overrides (custom rules, product-line exceptions) | **Project** (default) | Auto-discovered; shadows global where slugs collide |
| Ad-hoc test corpora during plugin development | **Project** | Isolated to the test directory; doesn't pollute global |

### Citation format

The consumer skill (`dks-search`) surfaces the layer in citations:

```
Claims must be filed within 30 days [ref: claims.pdf#p14#3.2 @ global].
The product-line extension to 60 days [ref: product-rules.md#L8-12 @ project] applies only to legacy term-life products.
```

Layer tags help reviewers see at a glance whether a fact is a company-wide rule or a project-specific override.

### Auto-discovery

When no `--project` flag or `DKS_PROJECT` env var is set, the CLI walks up from the current working directory looking for a `.dks/` directory. The first match becomes the project layer. If we hit the filesystem root with no match, there's no project layer and only global is active. This mirrors how `git` finds `.git/` and how `npm` walks up for `node_modules/`.

**One subtlety (fixed in 0.2.1):** the walker explicitly skips the global layer's resolved location. Without this, running `dks` from anywhere under `$HOME` would find `~/.dks` (the default global) and treat it as the project layer, causing both layers to resolve to the same directory. After 0.2.1, the walker silently passes over the global location and continues climbing — returning `None` (project-less, global-only mode) if nothing closer exists.

If you're not sure which layers `dks` is actually using, run:

```bash
dks layers list
```

It prints a JSON array of active layers with `name`, `base` (absolute path), `source` (how it was resolved — `explicit`, `env`, `auto-discover`, or `default`), and `exists` (does the base dir exist?). This is the fastest way to diagnose "why is `dks` finding the wrong layer?" — the `source` field shows where the path came from.

### Suppressing the global layer

Pass `--no-global` to any command if you want project-only mode (no global fallback for reads, no `~/.dks/` writes). Useful when working in a sandboxed corpus where you don't want cross-talk.

### Project layer initialisation

To start using the project layer in a repo, just create `.dks/`:

```bash
mkdir .dks
```

The first `dks ingest`, `dks wiki write`, or `dks pageindex write` from inside that repo will populate the standard subdirs automatically.

---

## Step 1 — Curate `raw/`

Drop authoritative source documents into `raw/`. Mirror your real folder taxonomy; the path under `raw/` becomes the canonical `source_file` identifier for every block.

```
raw/
  policies/
    claims_handling.pdf          # 42 pages, signed PDS
    pii_obligations.docx         # internal compliance memo
  schedules/
    retention_periods.xlsx       # rules per jurisdiction × product
```

Best practice: snapshot the version you ingested. Policies change; the KB should record what was true on what date. A file like `claims_handling-2026-05.pdf` is a defensible choice if you expect to track multiple versions.

---

## Step 2 — Ingest

One command per source. The parser is chosen by suffix. By default, ingest writes to the **project layer** (auto-discovered from CWD by walking up for `.dks/`); pass `--write-global` to push into the global layer at `~/.dks/`.

```bash
# From inside a project repo with a .dks/ at the root:
$ uv run dks ingest raw/policies/claims_handling.pdf
wrote 287 blocks to <project>/.dks/normalized/policies/claims_handling.pdf/

# Or to write into the global layer (company-wide reference doc):
$ uv run dks ingest raw/policies/claims_handling.pdf --write-global
wrote 287 blocks to ~/.dks/normalized/policies/claims_handling.pdf/

$ uv run dks ingest raw/policies/pii_obligations.docx
$ uv run dks ingest raw/schedules/retention_periods.xlsx
```

Inspect what landed (output is layer-tagged JSON):

```bash
$ uv run dks blocks list policies/claims_handling.pdf | head -10
[
  {"block_id": "policies/claims_handling.pdf#p1", "layer": "global"},
  {"block_id": "policies/claims_handling.pdf#p10", "layer": "global"},
  {"block_id": "policies/claims_handling.pdf#p14", "layer": "global"},
  ...
]

$ uv run dks blocks get "policies/claims_handling.pdf#p14"
{
  "block": {
    "source_file": "policies/claims_handling.pdf",
    "block_id": "policies/claims_handling.pdf#p14",
    "locator": {
      "kind": "pdf",
      "page": 14,
      "section": null,
      "clause": null
    },
    "block_type": "text",
    "content": "3.2 Filing window. Claims must be filed within 30 days..."
  },
  "layer": "global"
}
```

Each block carries an audit-grade citation primitive (`page`, optionally `section` / `clause` for PDFs; `sheet` + `cells` for Excels; etc.) plus a `layer` tag showing which layer served the read.

---

## Step 3 — Build PageIndex trees (Claude Code skill)

For long structured docs, the PageIndex tree lets the consumer skill navigate by structure rather than substring match.

From Claude Code, after loading the skills:

> **You:** Use `dks-build-pageindex` on `policies/claims_handling.pdf`.

Claude Code will:
1. Run `dks blocks list policies/claims_handling.pdf` — gets 287 block_ids.
2. Run `dks blocks get <block_id>` for each (in one large context window) — collects content + types.
3. Reason over the structure: headings define sections, text/table blocks belong under the nearest preceding heading.
4. Pipe a JSON tree into `dks pageindex write policies/claims_handling.pdf`.

You'll see something like:

> **Claude Code:** Tree written to `index/claims_handling.pdf.pageindex.json`. Top-level sections: 7. Deepest nesting: 4. Total nodes: 58.

Inspect:

```bash
$ uv run dks pageindex read policies/claims_handling.pdf | head -20
{
  "title": "Claims Handling Policy",
  "block_ids": [],
  "children": [
    {
      "title": "1. Scope and Definitions",
      "block_ids": ["policies/claims_handling.pdf#p2", "..."],
      "children": [...]
    },
    {
      "title": "3. Filing Procedures",
      "block_ids": [],
      "children": [
        {"title": "3.1 Notice", "block_ids": ["..."], "children": []},
        {"title": "3.2 Filing window", "block_ids": ["..."], "children": []}
      ]
    },
    ...
  ]
}
```

Repeat for each long structured source. Short or unstructured docs (a 3-page memo, an Excel) don't need trees.

---

## Step 4 — Compile a topic wiki entry (Claude Code skill)

Wiki entries are organized by topic, not by source. Pull from however many docs cover the topic.

> **You:** Use `dks-compile-wiki` to write a topic article on claim filing windows. Slug `claim-filing-windows`. Draw from `policies/claims_handling.pdf` and `schedules/retention_periods.xlsx`.

Claude Code will:
1. List blocks in both sources.
2. Get the relevant blocks (probably section 3.2 of the policy + the relevant rows of the spreadsheet).
3. Compose Markdown that cites every claim:

```markdown
Claims must be filed within 30 days of the incident [ref: policies/claims_handling.pdf#p14#3.2].
The window may be extended subject to subsection 3.2.2 [ref: policies/claims_handling.pdf#p14#3.2.2].
For term-life products the maximum extension is 60 days [ref: schedules/retention_periods.xlsx#sLife!B4:D4].
```

4. Build the JSON envelope and pipe it into `dks wiki write claim-filing-windows`.

> **Claude Code:** Wrote `wiki/claim-filing-windows.md`. Topic "Claim filing windows", 7 source refs, 280 words.

Verify:

```bash
$ uv run dks wiki read claim-filing-windows
{
  "entry": {
    "topic": "Claim filing windows",
    "slug": "claim-filing-windows",
    "source_refs": [
      "policies/claims_handling.pdf#p14#3.2",
      "policies/claims_handling.pdf#p14#3.2.2",
      "schedules/retention_periods.xlsx#sLife!B4:D4"
    ],
    "compiled_at": "2026-05-22T01:34:00+00:00",
    "body": "Claims must be filed within 30 days..."
  },
  "layer": "project"
}
```

Compile one entry per domain topic. The wiki is a discovery layer, not a mirror of the corpus. To compile an entry meant for cross-project reuse (a company-wide rule), add `--write-global`; without it, the entry lives in the project layer and only that repo sees it.

---

## Step 5 — Consume in compliance-sensitive code (the payoff)

Now Claude Code is working on a real feature. Some example session:

> **You:** Add a "submit claim" endpoint to our policyholder service. Include input validation for filing dates.

Without `dks-search`, Claude Code would invent a filing-window rule (likely something plausible-but-wrong like 60 or 90 days). With `dks-search` loaded:

> **Claude Code:**
> _(internally invokes `dks-search`)_
> Let me check the KB for the filing-window rule.
> _runs:_ `dks wiki search "filing window"`
> _gets back the `claim-filing-windows` entry (layer: project), sees the cited blocks_
> _runs:_ `dks blocks get "policies/claims_handling.pdf#p14#3.2"`
> _gets the verbatim text: "Claims must be filed within 30 days...", served from global_
>
> Here's the endpoint. Filing window validation enforces 30 days per the claims policy. The product-specific filing rule (in the project layer wiki) confirms this matches the company-wide policy at global.
>
> ```typescript
> // Claim filing window: 30 days from incident
> // Source: policies/claims_handling.pdf §3.2 @ global
> // Block: policies/claims_handling.pdf#p14#3.2
> const MAX_FILING_DAYS = 30;
>
> function validateFilingDate(incidentDate: Date, filedDate: Date): ValidationResult {
>   const days = daysBetween(incidentDate, filedDate);
>   if (days > MAX_FILING_DAYS) {
>     return { ok: false, reason: 'filing-window-exceeded' };
>   }
>   return { ok: true };
> }
> ```
>
> Sources:
> - `policies/claims_handling.pdf#p14#3.2` @ global — 30-day filing window
>
> Note: I did not find a KB entry for *late-filing exception handling* — if your service needs to support the subsection 3.2.2 extension path, the KB needs a wiki entry for it before I can ground that logic. Consider compiling a project-layer entry if it's specific to this product line, or a global entry if it applies company-wide.

Two things to notice:
1. **The 30-day number is not invented** — it's the verbatim policy rule.
2. **Abstention is honest** — Claude Code surfaces the gap rather than fabricating exception logic.

If you saw the abstention message, the right next move is to ingest more context (a section on extensions) and compile a second wiki entry, then re-prompt.

---

## Step 6 — Periodic audit

Run `dks-lint-wiki` after re-ingesting any source, or on a schedule.

> **You:** Use `dks-lint-wiki`.

Claude Code will:
1. List every wiki entry.
2. For each, verify every `block_id` in `source_refs` still exists via `dks blocks get`.
3. Verify inline `[ref: ...]` matches `source_refs`.
4. Conservative scan for cross-entry contradictions.
5. Produce a structured report.

Sample report (clean run, two layers active):

```
## Wiki lint report

### Broken citations
(none)

### Inline-vs-source_refs drift
(none)

### Cross-layer citations
- (project) entry `retention-exception`: cites `policies/claims_handling.pdf#p20#5.1` which resolves from the global layer (informational)

### Possible contradictions
(none)

### Summary
- 12 entries scanned (project: 3, global: 9)
- 0 broken citations
- 0 drift issues
- 1 cross-layer citation (informational)
- 0 possible contradictions
```

A dirty run will name specific entries and `block_id`s — those are your fix targets, generally via re-running `dks-compile-wiki` on the affected slug. Cross-layer citations (a project entry citing a global block, or vice versa) are informational, not bugs — but worth knowing when reviewing what a wiki entry actually depends on.

---

## Operating notes

### Versioning the corpus

`raw/` and `normalized/` are gitignored by default (`raw/` may contain sensitive material; `normalized/` is regenerable). To track what was true at a point in time, commit `wiki/` and `index/` — those capture human-reviewed knowledge state.

If you want full reproducibility, comment out the `raw/` and `normalized/` lines in `.gitignore` and commit the corpus.

### Re-ingesting after source changes

When a policy doc changes:
1. Replace the file in `raw/`.
2. Re-run `dks ingest` (writer overwrites idempotently).
3. Re-run `dks-build-pageindex` for that source.
4. Run `dks-lint-wiki` — it'll surface every wiki entry whose `source_refs` now point at moved/deleted blocks.
5. Re-run `dks-compile-wiki` on each affected slug.

This is by design. The KB is a living artifact and the lint pass is the change-management gate.

### Cost shape

The CLI is deterministic and free. The skills are LLM-driven:

| Skill | When LLM runs | Approximate token budget |
|---|---|---|
| `dks-build-pageindex` | Once per long source | ~50K input tokens (all blocks) + small output |
| `dks-compile-wiki` | Once per topic; re-run on lint failure | ~30–60K input + a few KB output |
| `dks-lint-wiki` | On schedule | Bounded by wiki size; typically modest |
| `dks-search` | Per consumer query | Trivial — small CLI roundtrips |

All LLM cost flows through Claude Code's own auth and billing. The `dks` Python package has no LLM client of its own.

### Skill discipline (the part operators care most about)

- **Don't bypass the skill.** Reading wiki entries directly and quoting them in code defeats the citation contract — the wiki snippet is for discovery, the source block is for grounding.
- **Don't auto-fix lint failures.** Lint is read-only by design. Failures require human judgment about whether a re-compile, a re-ingest, or a real policy change is the right response.
- **Trust abstention.** When Claude Code says "the KB does not contain a citation for X," that's the contract working. Either fix the gap (compile a wiki entry) or accept the un-grounded code with eyes open.

### Scripting against the CLI — shell-quoting gotcha

The CLI emits JSON with newlines escaped as `\n` (correct per the JSON spec). Bash's builtin `echo` interprets those escapes by default and converts `\n` to actual newline characters — which then breaks downstream JSON parsers with `Invalid control character` errors.

**Don't:**

```bash
HITS=$(dks wiki search "filing window")
echo "$HITS" | python3 -m json.tool      # echo unescapes \n → invalid JSON
```

**Do — any of these:**

```bash
# 1. printf with %s — does not interpret escapes
printf '%s' "$HITS" | python3 -m json.tool

# 2. here-string — preserves bytes verbatim
python3 -m json.tool <<< "$HITS"

# 3. pipe directly without intermediate capture
dks wiki search "filing window" | python3 -m json.tool

# 4. write to a tempfile
dks wiki search "filing window" > /tmp/hits.json
python3 -m json.tool < /tmp/hits.json
```

Same rule applies when iterating block_ids returned by `dks blocks list`:

```bash
# Don't word-split into a single $for variable — block_ids contain # and / which are
# fine in shell, but the whole-array form is brittle. Prefer one-per-line:
while IFS= read -r block_id; do
  dks blocks get "$block_id"
done < <(dks blocks list policies/term-life-policy.pdf)
```

This is a shell-script-author concern, not a `dks` issue — the CLI output is valid JSON in every case.

---

## What's not in scope (yet)

- **Automated eval runs.** `eval/` ships the *shape* and one example task; running baseline-vs-treatment across a real corpus needs SME-curated tasks and a headless Claude Code runner — separate project.
- **Semantic search.** `dks wiki search` is keyword-only in v0. Add embeddings only when keyword proves insufficient on real queries.
- **MCP server for non-Claude-Code consumers.** Architecture supports it; ship when a second consumer emerges.
- **Image / scanned PDF ingestion.** The PDF parser (pypdf) handles text-extractable PDFs; OCR for scanned docs is out of scope.
