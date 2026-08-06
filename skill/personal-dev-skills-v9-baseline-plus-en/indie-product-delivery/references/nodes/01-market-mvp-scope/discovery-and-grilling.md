# Discovery and Grilling

Turn a vague idea into a clear problem definition, a reachable audience, and a set of
alternatives the product must beat. Do this through focused grilling rounds, not a
questionnaire dump.

## Grilling rules

- Ask at most 5 questions per round. Wait for the user to answer before continuing.
- When an answer will change the next question, ask only 1 to 3 questions. Do not
  batch dependent questions.
- For each question, provide your recommended answer based on what you already know.
  The user confirms, corrects, or refines it.
- Look up facts you can find in the repo, docs, or environment before asking. Ask only
  for decisions, preferences, or information you cannot discover safely.
- When the user cannot answer, record the item as an assumption and continue. Do not
  stall the discovery on a single unknown.
- Do not act on the idea until grilling reaches a shared understanding.

## Round 1: Problem definition

Ask 1 to 3 questions here because later questions depend on earlier answers.

Rewrite the idea into a neutral problem frame before discussing features:

> For **[specific user]** who is trying to **[complete a job]** in **[situation]**,
> the current approach causes **[measurable pain]**. The product should help them
> achieve **[desired outcome]** without **[important trade-off]**.

If the user says "build an AI summarization tool," do not accept it. Ask: summarize
what, for whom, what do they do today, why is that not good enough?

Provide your recommended reading of the idea, marking inferences explicitly. Do not
invent facts, market sizes, user quotes, or demand.

## Round 2: Audience reach and alternatives

These questions are mostly independent, so up to 5 can be asked together.

- Where does the target audience congregate? Name communities, platforms, or search
  behavior.
- Can you reach them? Do you have an existing audience, channel, or network?
- Are they willing to change? What is the migration cost or habit resistance?
- What do they do today instead? List competitors, spreadsheets, manual flows,
  outsourcing, or doing nothing.
- For each alternative, why have users not switched already? That reason is your
  differentiation opportunity.

If the audience is "everyone" or "all developers," that is a signal the audience is
too broad. Recommend a narrower segment.

## Round 3: Riskiest assumption and investment budget

- What does product success depend on? Which single assumption, if false, makes the
  whole product pointless? That is the riskiest assumption.
- How much time can you invest? Weekends, one month, full-time?
- What is your monthly operating cost ceiling?
- What maintenance burden is acceptable? Daily, weekly, fully automated?

Frame the riskiest assumption:

> If **[assumption]** is false, then **[consequence for the product]**, because
> **[why this assumption is foundational]**.

Provide your recommended riskiest assumption based on what you know, marked as an
inference.

## When grilling is complete

Discovery is done when all of the following are true:

- The problem fits the one-sentence frame with specific user, pain, and outcome.
- The audience is behaviorally specific and reachable through a named channel.
- At least 2 alternatives are identified, each with a reason users have not switched.
- One riskiest assumption is named.
- Time and budget constraints are known.

If any item is missing, continue grilling. If the user is uncertain, record it as an
assumption and proceed. Do not block on unknowns that can be tested later.

## What not to do

- Do not produce a feature list before the problem is defined.
- Do not accept "everyone" as an audience.
- Do not invent market size, demand, user quotes, or competitor facts. Use web
  search when market or competitor data matters, and label what is researched versus
  inferred.
- Do not add AI or a technology stack to the problem frame. State the job, not the
  mechanism.
- Do not skip the "why have they not switched" question. Without it, differentiation
  is a guess.
