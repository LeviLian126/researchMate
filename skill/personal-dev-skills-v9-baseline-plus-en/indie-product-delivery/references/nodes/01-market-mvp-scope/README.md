# Market and MVP Scope

Turn a vague product idea into an implementation-ready spec for a solo developer or
very small team. Grill in focused rounds to separate facts from assumptions, cut scope
to what tests the riskiest hypothesis, and produce a document Node02 can consume
without re-asking questions.

## Read the relevant workflow

| Need | Read |
| --- | --- |
| turn a vague idea into a clear problem definition, audience, and alternatives | `discovery-and-grilling.md` |
| cut MVP boundary and write the implementation-ready spec | `scope-cut-and-spec.md` |
| challenge assumptions and decide BUILD, VALIDATE, or STOP | `challenge-and-validate.md` |

Node01 is a linear flow: discovery, then scope-cut, then challenge. Not every stage
must run. A clear small feature may skip discovery and enter scope-cut directly. An
existing PRD may only need challenge as an audit.

## Output contract

The final output is a spec document containing:

- Problem statement: who, what pain, how they cope today.
- Target audience: behavior-specific, not demographic.
- Core user journey: trigger, entry, action, result, next step.
- Scope: in scope, out of scope, non-goals.
- Acceptance criteria: testable, pass or fail, no "works correctly".
- Risk assumptions: each with "what happens if wrong" and "cheapest test".
- One decision: GO (to Node02), VALIDATE (run cheapest test first), or NO_GO (stop).

Node02 should be able to consume the spec without re-asking product questions.
