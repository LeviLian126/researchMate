# Ops, Learning, and Iteration

## Read the relevant workflow

| Need | Read |
|---|---|
| recover what shipped, validate signals, assess health, and distinguish incidents from learning | `production-health-and-signal-integrity.md` |
| synthesize customer value, choose an experiment or next slice, and preserve the decision | `customer-evidence-experiments-and-next-slice.md` |

Every applicable requirement in the selected workflow is a minimum delivery standard because it keeps operating decisions tied to real signals. Skip only genuinely irrelevant checks. Add analysis, investigation, or action when it helps answer the current operating question; stop when a required secret, API credential, or environment is unavailable.

## Output contract

Return the observed product/production state, evidence and confidence, customer or
operational signal, incident or learning interpretation, the next decision or slice, its
owner, and the trigger or evidence that should cause re-entry. Do not imply background
monitoring beyond the evidence actually collected.
