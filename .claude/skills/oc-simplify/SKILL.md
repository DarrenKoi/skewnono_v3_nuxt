---
name: oc-simplify
description: Quality-only pass over changed code — reuse, simplification, efficiency, and altitude — with the analysis delegated to an opencode model and the edits applied by Claude. Use when the user says "oc-simplify", "simplify with opencode", or wants an outside model to suggest cleanups on work in progress. Does not hunt for bugs; use oc-review for correctness.
---

Delegate a **quality** pass over the changed code to an opencode model, then
apply the suggestions worth applying and say which ones were declined and why.

This is the sibling of `oc-review`, split along a deliberate line:

| Skill | Question |
| --- | --- |
| `oc-review` | Is this correct, and is it what was asked for? |
| `oc-simplify` | Given that it works, could it be cleaner? |

**Behaviour must not change.** A suggestion that alters what the code does is
out of scope here — note it and hand it to `oc-review` instead.

Read `.claude/skills/_opencode/models.md` for the tier rubric before running.

## The four lenses

- **Reuse** — this reimplements something the repo already has. The strongest
  finding available, and the one an outside model is worst at guessing and best
  at finding by grepping. Tell it to search before claiming novelty.
- **Simplification** — the same behaviour with less structure: a branch that
  cannot be taken, a flag with one caller, a wrapper that only forwards, a
  local that is used once.
- **Efficiency** — repeated work that could be done once. Real algorithmic or
  I/O waste only, not micro-optimisation. In this repo that mostly means
  per-row work inside a DataFrame loop, or a Redis round trip inside a loop.
- **Altitude** — code sitting at the wrong level: a route handler doing frame
  manipulation, a provider adapter making presentation decisions, a Vue
  component computing domain logic that belongs in `utils/`.

## Process

### 1. Scope the change

Default scope is uncommitted work plus anything since the branch point:

```bash
git status --short
git diff --stat
git diff --stat main...HEAD
```

If that is empty, ask what to look at rather than reviewing the whole repo.

### 2. Pick a tier and announce it

Per `models.md`. Quality passes tolerate a lower tier than correctness
reviews — `medium` is the sensible default, and `light` is fine for a
single-file cleanup. Say which and why before spending.

### 3. Run the pass

```bash
D=$(mktemp -d)
{
  echo "You are doing a QUALITY pass on changed code in the SKEWNONO repo."
  echo "Inspect it yourself: git diff <scope>, and read the surrounding files."
  echo
  echo "Four lenses, in priority order:"
  echo "1. REUSE - does the repo already have this? grep before claiming it does."
  echo "   Look in back_dev_home/_runtime/, _core/, front-dev-home/app/utils/,"
  echo "   and app/composables/ especially."
  echo "2. SIMPLIFICATION - same behaviour, less structure."
  echo "3. EFFICIENCY - repeated work that could happen once. Real waste only,"
  echo "   not micro-optimisation."
  echo "4. ALTITUDE - logic sitting at the wrong layer."
  echo
  echo "HARD CONSTRAINT: behaviour must not change. If a cleanup would alter"
  echo "what the code does, label it BEHAVIOUR-CHANGE and do not recommend it."
  echo
  echo "For each finding give: the file and line, the lens, what to do, and"
  echo "roughly how many lines it removes. Order by value. Skip anything ruff,"
  echo "eslint, or markdownlint enforces. Under 400 words. Say plainly if the"
  echo "code is already clean - a short honest answer beats a padded one."
} > "$D/simplify.txt"

.claude/skills/_opencode/oc.sh --tier <tier> --label simplify < "$D/simplify.txt"
```

### 4. Triage, then apply

Go through the findings and sort them into three buckets, out loud:

- **Apply** — correct, in scope, behaviour-preserving.
- **Decline** — with a reason. "The two call sites look duplicated but diverge
  at the office" is information; silently dropping it is not.
- **Hand off** — anything labelled BEHAVIOUR-CHANGE, or that looks like a bug.
  Those belong to `oc-review`, not here.

Then apply the first bucket with `Edit`, in the main tree.

### 5. Verify, then report

A quality pass that changes behaviour is a failed quality pass, so prove it did
not:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest back_dev_home/<touched feature> -q
```

For frontend edits, `npm run typecheck` and `npm run lint` from
`front-dev-home/`. Run the full suite if the change reached shared plumbing.

Report what was applied, what was declined and why, and the verification
output. If a test fails, say so with the output — do not describe the pass as
clean and mention the failure later.

Commit with explicit pathspecs only, per `CLAUDE.md`.

## Failure modes to avoid

- Accepting a "reuse" finding without checking the helper actually exists and
  actually fits. An outside model will confidently name a plausible utility.
- Applying an edit that changes behaviour because it read as a cleanup.
- Bundling unrelated refactoring into a change the user scoped narrowly.
- Reporting "applied 6 suggestions" without saying what was declined.
