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
