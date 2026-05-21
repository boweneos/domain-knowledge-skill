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
