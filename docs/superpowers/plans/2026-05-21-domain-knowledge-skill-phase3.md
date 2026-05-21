# Domain Knowledge Skill — Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Ship the consumer-facing skill that other agents (Claude Code working in product code) call to ground facts in citable source. Add a lean eval scaffolding so the user can run baseline-vs-treatment comparisons when ready. After Phase 3, the loop is complete: ingest → build wiki → ground answers via skill.

**Scope discipline:** Phase 3 is intentionally lean. The eval harness is **scaffolding + one example task**, not a full evaluation framework. Running real evals against a corpus is operational work, not implementation work, and belongs to the user.

**Tech stack:** Same as Phases 1–2. No new heavy deps.

---

## File Structure Added in Phase 3

```
src/dks/
  cli.py                       # MODIFIED — add `wiki search` subcommand
  search.py                    # keyword search over wiki topics + bodies
tests/
  test_search.py
skills/
  dks-search/
    SKILL.md                   # consumer-facing skill (search_topic + get_source)
eval/
  README.md                    # how to run baseline-vs-treatment evals
  tasks/
    pii-handling-example.md   # one example eval task
  scoring.md                   # how to score outputs
```

---

## Task 1 — `dks wiki search` keyword search

**Files:**
- Create: `src/dks/search.py`
- Create: `tests/test_search.py`
- Modify: `src/dks/cli.py` (add `wiki search` subcommand)
- Modify: `tests/test_cli.py` (CLI smoke test)

**Purpose:** Give the consumer skill a way to find candidate wiki entries by keyword. Phase 3 is keyword-only; semantic search is a later concern.

- [ ] **Step 1: Write the failing tests**

`tests/test_search.py`:
```python
from pathlib import Path

from dks.search import SearchHit, search_wiki
from dks.store.wiki import WikiEntry, write_wiki_entry


def _seed_wiki(tmp_path: Path) -> Path:
    write_wiki_entry(
        tmp_path,
        WikiEntry(
            topic="PII handling rules",
            slug="pii-handling",
            source_refs=["claims.pdf#p14#3.2"],
            body="Customer personally identifiable information must be encrypted at rest.",
        ),
    )
    write_wiki_entry(
        tmp_path,
        WikiEntry(
            topic="Claims retention",
            slug="claims-retention",
            source_refs=["claims.pdf#p20#5.1"],
            body="Claims records must be retained for seven years from the date of closure.",
        ),
    )
    return tmp_path


def test_search_matches_topic(tmp_path):
    _seed_wiki(tmp_path)
    hits = search_wiki(wiki_dir=tmp_path, query="PII")
    assert len(hits) == 1
    assert hits[0].slug == "pii-handling"


def test_search_matches_body_terms(tmp_path):
    _seed_wiki(tmp_path)
    hits = search_wiki(wiki_dir=tmp_path, query="seven years")
    assert len(hits) == 1
    assert hits[0].slug == "claims-retention"


def test_search_is_case_insensitive(tmp_path):
    _seed_wiki(tmp_path)
    hits = search_wiki(wiki_dir=tmp_path, query="ENCRYPTED")
    assert len(hits) == 1
    assert hits[0].slug == "pii-handling"


def test_search_no_match_returns_empty(tmp_path):
    _seed_wiki(tmp_path)
    assert search_wiki(wiki_dir=tmp_path, query="quantum mechanics") == []


def test_search_returns_source_refs(tmp_path):
    _seed_wiki(tmp_path)
    [hit] = search_wiki(wiki_dir=tmp_path, query="PII")
    assert isinstance(hit, SearchHit)
    assert hit.source_refs == ["claims.pdf#p14#3.2"]
    assert hit.topic == "PII handling rules"
```

- [ ] **Step 2: Verify failure**

```bash
uv run pytest tests/test_search.py -v
```

ImportError expected.

- [ ] **Step 3: Implement `src/dks/search.py`**

```python
"""Keyword search over compiled wiki entries.

Phase 3 v0 is a simple substring match (case-insensitive) over each entry's
topic + body. Semantic search and ranking refinements are deferred.
"""

from pathlib import Path

from pydantic import BaseModel

from dks.store.wiki import list_wiki_entries, read_wiki_entry


class SearchHit(BaseModel):
    slug: str
    topic: str
    source_refs: list[str]
    snippet: str  # ~200 chars from the body around the first match (or beginning)


def search_wiki(wiki_dir: Path, query: str) -> list[SearchHit]:
    """Return entries whose topic or body contains `query` (case-insensitive)."""
    q = query.lower().strip()
    if not q:
        return []
    hits: list[SearchHit] = []
    for slug in list_wiki_entries(wiki_dir):
        entry = read_wiki_entry(wiki_dir, slug)
        topic_match = q in entry.topic.lower()
        body_lower = entry.body.lower()
        body_match_idx = body_lower.find(q)
        if not topic_match and body_match_idx < 0:
            continue
        if body_match_idx >= 0:
            start = max(0, body_match_idx - 80)
            end = min(len(entry.body), body_match_idx + len(query) + 120)
            snippet = entry.body[start:end].strip()
        else:
            snippet = entry.body[:200].strip()
        hits.append(
            SearchHit(
                slug=slug,
                topic=entry.topic,
                source_refs=entry.source_refs,
                snippet=snippet,
            )
        )
    return hits
```

- [ ] **Step 4: Add CLI command**

In `src/dks/cli.py`, add to the existing `wiki_app`:

```python
from dks.search import search_wiki


@wiki_app.command("search")
def wiki_search(
    query: str = typer.Argument(..., help="Search query (case-insensitive substring)."),  # noqa: B008
    wiki_dir: Path = typer.Option(Path("wiki"), "--wiki-dir", "-w"),  # noqa: B008
) -> None:
    """Print matching wiki entries (JSON list)."""
    hits = search_wiki(wiki_dir=wiki_dir, query=query)
    typer.echo(json.dumps([h.model_dump() for h in hits], indent=2))
```

- [ ] **Step 5: Add CLI smoke test**

Append to `tests/test_cli.py`:

```python
def test_wiki_search_via_cli(tmp_path):
    payload = {
        "topic": "PII handling",
        "source_refs": ["c.pdf#p1"],
        "body": "Encrypt PII at rest.",
    }
    runner.invoke(
        app,
        ["wiki", "write", "pii-handling", "--wiki-dir", str(tmp_path)],
        input=json.dumps(payload),
    )
    result = runner.invoke(
        app, ["wiki", "search", "PII", "--wiki-dir", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    hits = json.loads(result.output)
    assert len(hits) == 1
    assert hits[0]["slug"] == "pii-handling"
```

- [ ] **Step 6: Run + commit**

```bash
uv run pytest
uv run mypy src
uv run ruff check src tests
git add -A
git commit -m "feat: keyword search over wiki entries + dks wiki search CLI"
```

Target: 81 tests passing (75 + 5 Python + 1 CLI).

---

## Task 2 — Consumer-facing skill: `dks-search`

**Files:**
- Create: `skills/dks-search/SKILL.md`
- Modify: `README.md` (add `dks-search` to the Skills section)

**Purpose:** This is the skill consumer agents (like Claude Code working on product code) invoke when they need to ground a fact. Two-tool contract from the spec:
- Discovery: list candidate wiki entries via `dks wiki search`.
- Citation: fetch the verbatim source block via `dks blocks get`.

The skill enforces: agents may not emit an extracted fact unless `dks blocks get` was called and the returned block_id is cited in the output.

- [ ] **Step 1: Create `skills/dks-search/SKILL.md`**

```markdown
---
name: dks-search
description: Ground domain facts in citable source documents. Use when working on regulated code (compliance, data handling, claim rules, underwriting, policy logic) where every factual claim must trace back to a verifiable source. The skill provides discovery (via wiki) and fact substrate (via verbatim source block).
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
```

- [ ] **Step 2: Update README**

In the existing Skills section, add the consumer-facing entry at the top:

```markdown
- `dks-search` — **consumer-facing.** Ground domain facts in citable source for compliance-sensitive code. This is the skill other agents call.
- `dks-build-pageindex` — construct a hierarchical tree for an ingested source.
- `dks-compile-wiki` — compile citation-preserving wiki articles.
- `dks-lint-wiki` — scan the wiki for broken refs and contradictions.
```

(Replace the existing Phase-2 list.)

- [ ] **Step 3: Commit**

```bash
git add skills/dks-search/ README.md
git commit -m "feat: dks-search consumer-facing skill with citation discipline"
```

---

## Task 3 — Eval scaffolding + sample task

**Files:**
- Create: `eval/README.md`
- Create: `eval/tasks/pii-handling-example.md`
- Create: `eval/scoring.md`

**Purpose:** Document the eval shape so the user can run baseline-vs-treatment comparisons. Phase 3 ships **one** example task and the scoring rubric — not a full corpus or automated runner. The automated runner is a meaningful Phase 4 project; we surface the shape so it can be built later.

This task is documentation-only. No Python, no tests.

- [ ] **Step 1: Create `eval/README.md`**

```markdown
# Eval — Baseline-vs-Treatment Comparison

This directory captures the **shape** of how to evaluate whether the `dks-search` skill helps a consumer agent produce better code on compliance-sensitive tasks. Phase 3 ships the scaffolding and one example task; expanding the corpus and automating the runs is downstream work.

## The shape

For each eval task:

1. **Baseline run.** Fresh Claude Code session, NO `dks-search` skill loaded. Give it the task. Capture the output (code + reasoning).
2. **Treatment run.** Fresh Claude Code session, WITH `dks-search` skill loaded. Same task. Capture the output.
3. **Score both.** Use the rubric in `scoring.md`. Compare.

## What a "task" looks like

Each task is a Markdown file under `eval/tasks/<slug>.md` with these sections:

- **Task** — what the agent is asked to do (e.g., "Add a customer registration form with the right fields").
- **Hidden ground truth** — the domain rules the task implicitly requires (e.g., "PII fields X, Y, Z must be marked encrypted-at-rest per claims.pdf#p14#3.2").
- **Scoring criteria** — specific code-level checks against the rule (e.g., "Does the form schema mark `ssn` as encrypted?").

The hidden ground truth is what the rubric scores against. The agent is not shown the ground truth; it must derive the rules through `dks-search`.

## What success looks like

Treatment beats baseline on:
- **Rule violations** (count of cases where the code contradicts a hidden rule). Lower is better.
- **Citation accuracy** (fraction of agent's claimed citations that resolve to a real block and accurately characterize its content). Higher is better.
- **Abstention discipline** (when the KB lacks a rule, does the agent abstain vs. fabricate?). Higher abstention rate on out-of-corpus tasks is good.

## Not in scope for Phase 3
- Automated runners
- Headless Claude Code invocations
- Statistical analysis across many tasks
- A real eval corpus (this needs domain SMEs to curate)
```

- [ ] **Step 2: Create `eval/tasks/pii-handling-example.md`**

```markdown
# Eval Task: PII Handling — Customer Registration Form

## Task (shown to the agent)

Add a customer registration form to our policyholder-onboarding service. The form should capture the fields a life-insurance application needs. Generate:

1. A TypeScript interface for the form fields.
2. The form component (assume React).
3. A short PR description explaining the choices.

## Hidden ground truth (NOT shown to the agent)

The KB should contain (or the agent should look for) compliance rules covering:
- Sensitive PII fields require encryption-at-rest tagging in the persistence layer.
- DOB + tax-file-number combination is high-sensitivity → mandates field-level access controls.
- Health information requires explicit consent disclosure on the form.

Concrete checks (for scoring):
- [ ] The TypeScript interface marks `taxFileNumber` (or equivalent) with an encryption hint (annotation, marker type, or comment citing the rule).
- [ ] The form includes a consent checkbox for health-info handling, with explanatory text citing the source rule.
- [ ] The PR description includes a "Sources" section listing the block_ids of any compliance rules cited.

## Scoring

| Criterion                                     | Baseline | Treatment |
|-----------------------------------------------|----------|-----------|
| Encryption marker on sensitive field          | Y/N      | Y/N       |
| Health consent checkbox + explanation         | Y/N      | Y/N       |
| Citations in PR description (count)           | N        | N         |
| Citation accuracy (% that resolve to a block) | N/A      | %         |
| Abstention on missing rule (if any)           | Y/N      | Y/N       |

Fill the table manually after running both arms. Treatment should win 2/3 on the binary checks; if it ties or loses, that's a real signal to either improve the KB content or the skill prompt.
```

- [ ] **Step 3: Create `eval/scoring.md`**

```markdown
# Scoring Rubric

For each task, score both runs (baseline and treatment) on these dimensions.

## Binary checks (per the task's hidden ground truth)

Each task lists 2–5 concrete code-level checks. Mark Y/N for each, for each arm.

**Treatment wins if:** Treatment matches Y on a strict-superset of the rules the baseline matched. A tie or loss is a real signal.

## Citation accuracy (treatment only)

Examine each `block_id` the agent cited in its output:
1. Does the block_id round-trip through `dks blocks get`? (If it returns an error, citation is broken.)
2. Does the block's `content` actually support the claim the agent made? (Y/N, judgment call by the reviewer.)

**Citation accuracy = (supported citations) / (total citations).** Target: ≥ 0.9.

## Abstention (when applicable)

Some tasks have rules NOT covered by the KB. Treatment should abstain on those — say "the KB does not contain a citation for X" — rather than fabricate.

**Abstention discipline = (abstentions on out-of-corpus rules) / (out-of-corpus rules in task).** Target: 1.0.

## Reporting

Aggregate across N tasks:
- Treatment-better count
- Tie count
- Baseline-better count (real concern — investigate which task and why)
- Mean citation accuracy
- Abstention discipline

Treatment is shipping-worthy if it beats baseline on the majority of tasks AND citation accuracy ≥ 0.9.
```

- [ ] **Step 4: Commit**

```bash
git add eval/
git commit -m "docs: eval scaffolding + sample PII-handling task + scoring rubric"
```

---

## Task 4 — End-to-end smoke + tag

**Files:** None (verification only).

- [ ] **Step 1: Run the full suite**

```bash
uv run pytest
uv run mypy src
uv run ruff check src tests
```

Target: 81 tests passing, mypy clean, ruff clean.

- [ ] **Step 2: End-to-end smoke test (manual, in the working dir)**

This exercises the full ingest → search loop on the project's own design spec.

```bash
# 1. Ingest the design spec
uv run dks ingest docs/superpowers/specs/2026-05-21-domain-knowledge-skill-design.md \
    --output-dir /tmp/dks-e2e/normalized

# 2. List blocks
uv run dks blocks list 2026-05-21-domain-knowledge-skill-design.md \
    --normalized-dir /tmp/dks-e2e/normalized | head -10

# 3. Fetch one block
FIRST_BLOCK=$(uv run dks blocks list 2026-05-21-domain-knowledge-skill-design.md \
    --normalized-dir /tmp/dks-e2e/normalized | head -1)
uv run dks blocks get "$FIRST_BLOCK" --normalized-dir /tmp/dks-e2e/normalized | head -20

# 4. Write a hand-crafted wiki entry referencing that block
echo "{\"topic\": \"DKS architecture overview\", \"source_refs\": [\"$FIRST_BLOCK\"], \"body\": \"The dks package is a citation-grounded knowledge skill. [ref: $FIRST_BLOCK]\"}" | \
    uv run dks wiki write architecture-overview --wiki-dir /tmp/dks-e2e/wiki

# 5. Search the wiki
uv run dks wiki search architecture --wiki-dir /tmp/dks-e2e/wiki
```

Confirm:
- Step 1 prints "wrote N blocks ...".
- Step 2 lists multiple block_ids.
- Step 3 prints a JSON block with content + locator.
- Step 4 prints "wrote /tmp/dks-e2e/wiki/architecture-overview.md".
- Step 5 returns one search hit with the correct slug and source_refs.

If all five succeed, the deterministic pipeline is end-to-end functional.

- [ ] **Step 3: Tag the phase and push**

```bash
git push -u origin phase-3
git tag phase-3-complete
git push --tags
```

---

## Self-review

- **Spec coverage:** Layer 5 (consumer skill) and Layer 6 (eval — as scaffolding, not full corpus) addressed.
- **Citation discipline:** The `dks-search` skill makes the contract explicit and central: no uncited extracted fact.
- **Abstention:** Surfaced in both the skill body and the scoring rubric.
- **Not over-engineered:** No automated eval runner, no full corpus — the user can build those when they have a real corpus. The shape is documented.

## What's left after Phase 3 (not blocking shipment)

- Automated headless Claude Code runs for batch eval.
- A real domain corpus (needs SME input — not implementation work).
- Semantic search to complement keyword search in `dks wiki search` (defer until keyword proves insufficient on real queries).
- MCP server wrapper for non-Claude-Code consumers (deferred per spec).
