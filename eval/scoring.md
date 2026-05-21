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
