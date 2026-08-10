---
name: oc-discuss
description: Debate a technical decision with an opencode model across several rounds — Claude states a position, the model attacks it, Claude rebuts or concedes — then reports what was agreed, what stayed disputed, and where Claude was wrong. Use when the user says "oc-discuss", "debate this with opencode", "get a second opinion", "argue this out", or wants a design or diagnosis pressure-tested before committing to it.
---

Pressure-test a position by arguing it out with an opencode model over up to
three rounds, using session continuation so the model remembers its own earlier
argument and cannot quietly drift.

The output is not a summary of what the model said. It is a verdict on **who
was right about what**, including the parts where Claude was wrong.

Read `.claude/skills/_opencode/models.md` for the tier rubric before running.

## When this beats a single question

A one-shot second opinion mostly reflects back the framing it was given. The
rounds are what create pressure: the model has to defend its critique against a
rebuttal, and Claude has to either answer the critique or concede it. Positions
that survive that are worth more than positions nobody attacked.

Use `heavy` (kimi-k3) for architecture, provider design, and anything touching
the mock→office swap. `medium` is fine for a scoped implementation choice.

## Process

### 1. State the position first, in writing

Before involving the model, write down the position, the reasoning, and what
would falsify it. A vague position produces a vague debate.

Include the constraints an outside model cannot infer: that the office DBs are
unreachable from home, that Pinia is not used, that the working tree is shared
across agent sessions, whatever bears on the question. Otherwise round one gets
spent on advice that is already ruled out.

### 2. Round 1 — invite attack, not agreement

```bash
D=$(mktemp -d)
{
  echo "You are the adversarial reviewer of a technical decision in SKEWNONO,"
  echo "a Nuxt 4 + Flask metrology app. Inspect the repo yourself as needed."
  echo
  echo "THE POSITION:"
  echo "<position, reasoning, and what would falsify it>"
  echo
  echo "RELEVANT CONSTRAINTS:"
  echo "<constraints an outsider cannot infer from the code>"
  echo
  echo "Your job is to find what is WRONG with this, not to improve on the"
  echo "margins. Give your strongest objections, worst first. For each: the"
  echo "claim, why it fails, and what it would cost. If you think the position"
  echo "is right, say so and give the strongest objection you considered and"
  echo "rejected - do not manufacture disagreement."
  echo "Under 400 words."
} > "$D/r1.txt"

OC=.claude/skills/_opencode/oc.sh
SID=$("$OC" --tier <tier> --label round1 < "$D/r1.txt" 2>&1 >"$D/r1.out" \
      | sed -n 's/^OC_SESSION=//p')
cat "$D/r1.out"; echo "SID=$SID"
```

The `2>&1 >file` order matters: it sends stderr (carrying `OC_SESSION=`) down
the pipe while stdout goes to the file.

### 3. Rounds 2–3 — rebut or concede, point by point

Answer every objection. For each one, either rebut it with a reason, or concede
it outright. **Do not skip the ones that landed** — a debate where Claude only
answers the weak objections is theatre.

```bash
{
  echo "Here is my response to each of your objections."
  echo "<point-by-point: rebut with reasoning, or concede plainly>"
  echo
  echo "Where I conceded, treat it as settled - do not re-argue it."
  echo "Where I rebutted, either press the objection with a concrete failure"
  echo "case, or drop it and say you are dropping it."
  echo "Raise a new objection only if it is genuinely stronger than what you"
  echo "already gave. Under 300 words."
} > "$D/r2.txt"

"$OC" --tier <tier> --session "$SID" --label round2 < "$D/r2.txt"
```

Stop when the exchange converges — when the model drops its objections, or
both sides restate rather than advance. **Three rounds is the ceiling, not the
target.** A clean concession in round 1 is a finished debate; do not spend two
more rounds manufacturing friction.

### 4. Report the verdict

```text
## Agreed
   <points both sides settled on, and what follows from them>

## Disputed
   <where you still disagree, each side's best argument, and what evidence
    would settle it>

## I was wrong
   <what Claude conceded, and what changes as a result>
```

Rules for the verdict:

- **"I was wrong" being empty is a claim, not a default.** If it is empty, say
  why the objections did not land. An empty section every time means the debate
  is not doing its job.
- **Disputed is a real outcome.** Do not resolve a genuine disagreement by
  splitting the difference. Name what evidence would settle it — often a probe
  script or an office run.
- **Report cost** if the debate ran to three `heavy` rounds. `oc.sh` prints it.

### 5. Then act

The verdict is input to a decision, not the decision. Recommend a course, note
what the user should weigh, and wait for their call before implementing
anything the debate changed.

## Failure modes to avoid

- Asking "what do you think of this?" — that invites agreement. Ask what is
  wrong with it.
- Conceding to sound agreeable when the objection was answerable, or defending
  a position out of momentum after it has been refuted. Both corrupt the
  verdict.
- Withholding constraints, then treating the resulting off-target advice as a
  finding about the model.
- Running three rounds because three is the number, when round 1 converged.
