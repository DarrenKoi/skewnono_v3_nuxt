---
name: oc-review
description: Two-axis code review (Standards + Spec) of the changes since a fixed point, run by an opencode model rather than by Claude, then reconciled against Claude's own reading with disagreements called out. Use when the user asks for a second opinion on a branch or diff, says "oc-review", "review with opencode", "have another model look at this", or wants an outside model to check work before it lands.
---

Review the diff between `HEAD` and a fixed point along two independent axes,
delegating each axis to an **opencode** model so the findings come from
outside this conversation's context:

- **Standards** — does the code follow this repo's documented conventions?
- **Spec** — does it faithfully implement what was actually asked for?

Then add a third section Claude owns: where Claude agrees, and where Claude
thinks the delegated model is wrong.

Read `.claude/skills/_opencode/models.md` for the tier rubric before running.

## Why delegate instead of reviewing directly

Claude wrote (or watched the user write) the code under review, and carries
every assumption that produced it. A model with no such history reads the diff
cold. That is the entire value here — so do **not** pre-digest the diff into a
summary and send that. Give the model the diff command and let it look.

## Process

### 1. Pin the fixed point

Whatever the user names is the fixed point — a SHA, `main`, a tag, `HEAD~5`.
If they gave none, ask; do not guess.

Verify before spending anything:

```bash
git rev-parse <fixed-point>            # must resolve
git diff --stat <fixed-point>...HEAD   # must be non-empty
git log <fixed-point>..HEAD --oneline
```

A bad ref or an empty diff fails here, not inside two paid model calls.

### 2. Pick a tier and announce it

Judge complexity by the rubric in `models.md`, apply the escalation rule, and
say so in one line before running:

> 14 files, touches `sem_list/providers/` → `heavy` (glm-5.3)

`medium` (deepseek-v4-pro) is the honest default for an ordinary one-feature
diff — it was measured on a tool-using review, which is why the old blanket
"always `heavy`" rule is gone. Do not drop to `light` for a review; it is
untested at that length.

Discount generated churn: a 400-line vendored-package resync is not complexity.
If the user named a model, use it and skip the rubric.

Expect a heavy review to take **2–4 minutes per axis**. That is normal, not a
hang; `oc.sh` bounds it at `OC_TIMEOUT` (default 900s) and exits 124 if
exceeded.

### 3. Identify the spec source

In order: issue references in the commit messages (`.scratch/` per
`docs/agents/issue-tracker.md`), a path the user passed, a spec under
`.scratch/<topic>/spec.md` or `docs/` matching the branch, then ask. If the
user says there is no spec, skip the Spec axis and say so in the report —
do not invent a spec from the diff and then grade the diff against it.

### 4. Run both axes in parallel

Both axes read the same diff but must not see each other's findings. Write the
prompts to files (they are long, and quoting a diff command inside a shell
string is how you lose a `$`):

```bash
D=$(mktemp -d)
SMELLS=.claude/skills/_opencode/smells.md

{
  echo "You are reviewing a change in the SKEWNONO repository."
  echo "Inspect it yourself with: git diff <fixed-point>...HEAD"
  echo "Commits under review: git log <fixed-point>..HEAD --oneline"
  echo
  echo "Read these for the repo's documented standards: CLAUDE.md, DESIGN.md,"
  echo "and any MIGRATION.md under a feature folder the diff touches."
  echo
  echo "=== SMELL BASELINE (apply this exactly; do not substitute your own) ==="
  cat "$SMELLS"
  echo "=== END BASELINE ==="
  echo
  echo "Report, per file or hunk: (a) every place the diff violates a"
  echo "documented standard, citing the file and the rule; (b) any baseline"
  echo "smell, naming it and quoting the hunk. Mark each finding HARD"
  echo "(documented breach) or JUDGEMENT (baseline smell). A documented repo"
  echo "standard overrides the baseline. Skip anything ruff, eslint, or"
  echo "markdownlint already enforces. Under 400 words. If you find nothing,"
  echo "say so plainly rather than padding."
} > "$D/standards.txt"

{
  echo "You are checking a change in the SKEWNONO repository against its spec."
  echo "Inspect it yourself with: git diff <fixed-point>...HEAD"
  echo "The spec is at: <spec path>"
  echo
  echo "Report: (a) requirements the spec asked for that are missing or only"
  echo "partly done; (b) behaviour in the diff nobody asked for (scope creep);"
  echo "(c) requirements that look implemented but where the implementation"
  echo "looks wrong. Quote the spec line for every finding. Under 400 words."
} > "$D/spec.txt"

OC=.claude/skills/_opencode/oc.sh
"$OC" --tier <tier> --label standards < "$D/standards.txt" > "$D/standards.out" 2> "$D/standards.err" &
P1=$!
"$OC" --tier <tier> --label spec      < "$D/spec.txt"      > "$D/spec.out"      2> "$D/spec.err" &
P2=$!
# Capture each job's status separately: a bare `wait` yields only the last
# one's, and then a failed axis is indistinguishable from a clean one.
wait $P1; S1=$?
wait $P2; S2=$?
echo "=== STANDARDS (exit $S1) ==="; cat "$D/standards.out"; [ $S1 -ne 0 ] && tail -6 "$D/standards.err"
echo "=== SPEC (exit $S2) ===";      cat "$D/spec.out";      [ $S2 -ne 0 ] && tail -6 "$D/spec.err"
```

A non-zero axis must be reported as **failed**, quoting the reason from its
`.err` file — never as an axis that found nothing. Exit 124 is a timeout (rerun
with a higher `OC_TIMEOUT`), 1 is a provider or empty-reply failure. Do not
present a one-axis review as if both had run.

### 5. Report

Three sections, in this order:

```text
## Standards      <- the model's findings, verbatim or lightly cleaned
## Spec           <- the model's findings, verbatim or lightly cleaned
## Claude's read  <- agreements, disagreements, and anything both axes missed
```

Rules for the third section, which is where this skill earns its keep:

- **Name disagreements explicitly.** "opencode flags X as duplicated code; that
  is wrong, the two call sites diverge at the office because …". A finding
  Claude silently drops is a finding the user never gets to judge.
- **Concede plainly when the model is right**, especially where it caught
  something Claude wrote. No hedging.
- **Add what both axes missed.** Claude has the conversation history; they do
  not.

Do **not** merge or rerank the two axes into one list. A change can pass
Standards and fail Spec, and reporting them together lets one mask the other.
End with one line per axis: finding count and the worst item within that axis.

### 6. Record the run

Write a summary to `docs/opencode/YYYY-MM-DD-<title>.md` following
`.claude/skills/_opencode/logging.md`, quoting both axes verbatim, then run
`npm run lint:md` from the repo root. Do this **whether or not** findings were
acted on, and record a failed run too.

### 7. Applying fixes

opencode runs read-only (`--agent plan`), so nothing has been changed. If the
user wants findings fixed, Claude applies them with `Edit` and commits with
**explicit pathspecs only** — never `git add -A` — per `CLAUDE.md`, because
other agent sessions share this working tree.

A review usually yields fixes across several files, which is exactly the case
`CLAUDE.md` routes into an isolated `git worktree`. Single-file fixes stay in
the main tree; anything wider gets a worktree first, and it is torn down in the
same session once the work is merged.

## Failure modes to avoid

- Reviewing a diff you summarised for the model. Give it the command.
- Presenting an empty axis as a clean bill of health. `oc.sh` exits non-zero on
  empty output precisely so this cannot happen quietly.
- Grading against a spec you inferred from the diff being graded.
- Burning `heavy` on a diff that is mostly generated or vendored churn.
