# Usage — A Worked Example

This walks through the full lifecycle of `dks` with a realistic example: a life-insurer ingests a claims-handling policy PDF, builds an index, compiles a topic wiki, then has Claude Code write a feature that needs to respect the policy's rules.

The session is annotated so you can map each step to either the **deterministic CLI** (you or the skill runs it) or the **Claude Code skill** (LLM judgment).

---

## Installation

`dks` has **two halves** that install separately:
1. The **Python package** (`dks` CLI: ingest, blocks, pageindex, wiki, wiki search) — installed via `uv`.
2. The **Claude Code plugin** (4 skills + 5 slash commands) — installed via Claude Code's `/plugin` machinery.

### Half 1 — Python package

```bash
git clone git@github.com:boweneos/domain-knowledge-skill.git
cd domain-knowledge-skill
uv sync --all-groups
uv run dks --help     # smoke check
uv run pytest         # full suite — 81 passing expected
```

The CLI is then runnable as `uv run dks ...` from the project root, or you can `uv pip install -e .` into a venv on your PATH if you want a global `dks` binary.

### Half 2 — Claude Code plugin

Choose one of three paths.

#### Path A — Marketplace install from GitHub (recommended, persistent)

Inside a Claude Code session:

```text
/plugin marketplace add boweneos/domain-knowledge-skill
/plugin install dks@domain-knowledge-skill
```

The first command registers the GitHub repo as a marketplace; the second installs the `dks` plugin from it. The plugin is persistent across sessions and **auto-updates daily by default** (disable in `/plugin` → Marketplaces tab → toggle Enable auto-update).

Verify:
```text
/plugin            # Installed tab should list "dks"
```

#### Path B — Local-directory install (dev/testing, non-persistent)

Useful when you're iterating on the plugin contents locally and want changes to load without a marketplace round-trip.

```bash
# Launch Claude Code with the plugin directory pre-loaded
claude --plugin-dir /Users/bowen.li/development/KB
```

Or, if Claude Code is already running:
```text
/reload-plugins
```
after pointing it at the local directory. This install does **not** persist across sessions — re-pass `--plugin-dir` next launch.

#### Path C — Manual skill copy (skills only, no commands)

Falls back when `/plugin` machinery isn't available (e.g. older Claude Code versions). You lose the `/dks:*` slash commands but keep skill auto-activation.

```bash
mkdir -p ~/.claude/skills
cp -r skills/dks-search skills/dks-build-pageindex \
      skills/dks-compile-wiki skills/dks-lint-wiki \
      ~/.claude/skills/
```

### Verifying everything wired up

After Path A or B, in a Claude Code session:

```text
/plugin                          # → Installed tab lists "dks"
/dks:search "test"               # → should invoke the search skill (likely with empty wiki, abstains)
```

After Path C:

> Ask Claude Code: "Use the dks-search skill on the topic 'test'."

The skill should activate by name (no slash command available on Path C).

### Updating

```text
/plugin marketplace update domain-knowledge-skill
```

Or wait for the daily auto-update (Path A only).

### Uninstall

```text
/plugin uninstall dks@domain-knowledge-skill
/plugin marketplace remove domain-knowledge-skill   # optional, drops the marketplace too
```

For Path C, just `rm -rf ~/.claude/skills/dks-*`.

### Common pitfalls

- **Skills + commands must live at plugin root, not under `.claude-plugin/`.** Our layout is correct (`skills/` and `commands/` at the top level); only `plugin.json` and `marketplace.json` live under `.claude-plugin/`. If you fork and restructure, keep skills/commands at root or they won't be discovered.
- **Command-name collisions are global.** Slash commands (`/dks:*`) are namespaced by plugin name, so collisions with other plugins are rare. Skills are namespaced by skill name (`dks-search`); pick names other plugins are unlikely to use.
- **Version pinning matters for updates.** `.claude-plugin/plugin.json` carries a `version` field. Bump it when shipping behaviour changes — that's the signal Claude Code uses to surface "update available". Without a version bump, the auto-updater treats commit SHAs as the version key and any push re-pulls.
- **The Python and plugin halves are independent.** Path A installs the plugin but does NOT install the `dks` Python CLI — skills shell out to `dks`, so the CLI must be on PATH (or `uv run dks` from a known directory) for them to work. Always do Half 1 before relying on the skills in anger.

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

One command per source. The parser is chosen by suffix.

```bash
$ uv run dks ingest raw/policies/claims_handling.pdf
wrote 287 blocks to normalized/claims_handling.pdf/

$ uv run dks ingest raw/policies/pii_obligations.docx
wrote 64 blocks to normalized/pii_obligations.docx/

$ uv run dks ingest raw/schedules/retention_periods.xlsx
wrote 41 blocks to normalized/retention_periods.xlsx/
```

Inspect what landed:

```bash
$ uv run dks blocks list policies/claims_handling.pdf | head -5
policies/claims_handling.pdf#p1
policies/claims_handling.pdf#p10
policies/claims_handling.pdf#p11
policies/claims_handling.pdf#p12
policies/claims_handling.pdf#p13

$ uv run dks blocks get "policies/claims_handling.pdf#p14"
{
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
}
```

Each block now carries an audit-grade citation primitive (`page`, optionally `section` / `clause` for PDFs; `sheet` + `cells` for Excels; etc.).

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
  "topic": "Claim filing windows",
  "slug": "claim-filing-windows",
  "source_refs": [
    "policies/claims_handling.pdf#p14#3.2",
    "policies/claims_handling.pdf#p14#3.2.2",
    "schedules/retention_periods.xlsx#sLife!B4:D4",
    ...
  ],
  "compiled_at": "2026-05-22T01:34:00+00:00",
  "body": "Claims must be filed within 30 days..."
}
```

Compile one entry per domain topic. The wiki is a discovery layer, not a mirror of the corpus.

---

## Step 5 — Consume in compliance-sensitive code (the payoff)

Now Claude Code is working on a real feature. Some example session:

> **You:** Add a "submit claim" endpoint to our policyholder service. Include input validation for filing dates.

Without `dks-search`, Claude Code would invent a filing-window rule (likely something plausible-but-wrong like 60 or 90 days). With `dks-search` loaded:

> **Claude Code:**
> _(internally invokes `dks-search`)_
> Let me check the KB for the filing-window rule.
> _runs:_ `dks wiki search "filing window"`
> _gets back the `claim-filing-windows` entry, sees the cited blocks_
> _runs:_ `dks blocks get "policies/claims_handling.pdf#p14#3.2"`
> _gets the verbatim text: "Claims must be filed within 30 days..."_
>
> Here's the endpoint. Filing window validation enforces 30 days per the claims policy.
>
> ```typescript
> // Claim filing window: 30 days from incident
> // Source: policies/claims_handling.pdf §3.2 (block_id: policies/claims_handling.pdf#p14#3.2)
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
> - `policies/claims_handling.pdf#p14#3.2` — 30-day filing window
>
> Note: I did not find a KB entry for *late-filing exception handling* — if your service needs to support the subsection 3.2.2 extension path, the KB needs a wiki entry for it before I can ground that logic.

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

Sample report (clean run):

```
## Wiki lint report

### Broken citations
(none)

### Inline-vs-source_refs drift
(none)

### Possible contradictions
(none)

### Summary
12 entries scanned, 0 broken citations, 0 drift issues, 0 possible contradictions.
```

A dirty run will name specific entries and `block_id`s — those are your fix targets, generally via re-running `dks-compile-wiki` on the affected slug.

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
