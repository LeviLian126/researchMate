# Challenge and Validate

Stress-test the spec before handing it to Node02. Challenge each key claim from five
risk dimensions. If any risk is high, design the cheapest test before deciding to
build.

## When to read this file

After the spec is produced, or when the user wants to challenge an existing product
idea or PRD.

## Five risk dimensions

For each dimension, provide your recommended rating (LOW, MEDIUM, HIGH, or UNKNOWN)
with the evidence behind it.

### 1. Value risk: is the problem painful enough?

- Would users spend time or money to solve this today?
- Is there behavioral evidence (repeated use, payment, complaints) or only verbal
  claims of need?
- Treat stated interest as weaker than observed behavior, commitment, or payment.

### 2. Reach risk: can you access the users?

- Where does the first user come from? Name a specific channel, not "content" or
  "community."
- Do you have an existing audience, network, or distribution advantage?

### 3. Feasibility risk: can you build it?

- Are the core APIs or dependencies reliable, affordable, and permitted for this use?
- Is there anything that must be prototyped before commitment?
- Are latency, accuracy, scale, or platform requirements realistic for a solo build?

### 4. Sustainability risk: can one person maintain it?

- How much daily manual work does operating this require?
- What happens to cost and support burden as usage grows?
- Does it depend on a single vendor or platform that could change terms?

### 5. Founder fit: will you keep doing this?

- Is this a product you are willing to maintain for years, not just build once?
- Do you have domain expertise or an unfair advantage here?

## Validation ladder

If any risk is HIGH or UNKNOWN, select the cheapest method that produces
decision-quality evidence:

| Method | Cost | Tests |
|---|---|---|
| Research existing evidence | zero | market demand, competitor analysis |
| Landing page or fake door | low | does demand exist |
| Concierge or manual service | low | value assumption, willingness to use |
| Prototype (throwaway code) | low to medium | technical feasibility, UI direction |
| Paid pilot | medium | willingness to pay |
| Narrow functional MVP | high | full validation |

Do not require validation when all risks are LOW. Proceed directly to GO.

For each risk that needs validation, specify:

- The hypothesis being tested.
- The method chosen.
- Pass threshold: what result confirms the hypothesis.
- Fail threshold: what result rejects it.
- Decision after pass: GO to Node02.
- Decision after fail: NO_GO, or revise the spec and re-grill.

## Final decision

One decision per spec:

| Decision | Condition | Next step |
|---|---|---|
| GO | All five risks are LOW or MEDIUM, and the riskiest assumption has a validation plan or is already validated | Proceed to Node02 |
| VALIDATE | One or more risks are HIGH but can be tested cheaply | Run the cheapest test first; result decides GO or NO_GO |
| NO_GO | A risk is HIGH and cannot be tested cheaply, or evidence shows the problem is not painful enough | Stop; record the reason |

Do not issue GO when:

- The audience is not behaviorally specific.
- The core job cannot be stated in one sentence.
- The riskiest assumption is not identified.
- Scope has not been cut to fit the investment budget.

Record the decision, confidence (low, medium, high), the three strongest reasons, and
what evidence would reverse it.

## What not to do

- Do not treat signup count, page views, or download count as proof of value unless
  they causally represent the core job being completed.
- Do not skip a risk dimension because it seems fine. Rate it explicitly, even if LOW.
- Do not recommend building a full MVP when a cheaper test could answer the same
  question.
- Do not invent demand evidence. If no evidence exists, mark UNKNOWN and design a
  test.
