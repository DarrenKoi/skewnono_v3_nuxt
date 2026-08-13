# opencode model tiers

Shared reference for the `oc-review`, `oc-simplify`, and `oc-discuss` skills.
All three shell out through `.claude/skills/_opencode/oc.sh`, which maps a tier
name to a model and handles provider fallback.

## The three tiers

| Tier | Model | Reach for it when |
| --- | --- | --- |
| `heavy` | `kimi-k3` | More than ~10 changed files, cross-feature contracts, security or auth logic, concurrency, or anything touching the mock→office swap |
| `medium` | `glm-5.2` | The common case: one feature slice, roughly 3–10 files, ordinary application logic |
| `light` | `gpt-5.6-luna` | A single file, docs, tests, renames, formatting, or a mechanical change |

Invoke by tier, not by model id, so the mapping stays in one place:

```bash
echo "$PROMPT" | .claude/skills/_opencode/oc.sh --tier medium --label standards
```

Override with an explicit model when the user names one:

```bash
echo "$PROMPT" | .claude/skills/_opencode/oc.sh --model kimi-k3 --label standards
```

## Measured reliability (2026-08-10)

The tiers above describe *how much capability a task deserves*. This section
describes *what actually works*, which is not the same thing, and was found by
running them rather than by reading docs.

| Model | Simple prompt | Tool-using review | Notes |
| --- | --- | --- | --- |
| `kimi-k3` | works | **works** | 137s and 194s on single-file reviews; findings were specific and correct |
| `glm-5.2` | works | **unreliable** | Two failures out of two: once an unrelated hallucinated document, once an empty final message |
| `gpt-5.6-luna` | works | untested at length | Fine for short bounded prompts |

**Consequence: all three `oc-*` skills default to `heavy`, not `medium`, and
none of them drop to `light`.** A review, a simplify pass, and a debate round
are all tool-using tasks — the model runs `git diff`, greps, and reads files —
and that is exactly where `glm-5.2` fell over here. The `medium` tier remains
correct for its stated complexity band, but is not currently trustworthy for
delegated review work; `light` is untested at that length and is not a floor
any `oc-*` skill should use.

This is a measurement, not a verdict on the model, and it is cheap to recheck:
run `oc.sh --tier medium` on a bounded review and see whether it answers. If it
does so reliably, restore `medium` as the review default and update this table.

`oc.sh` refuses to print an empty reply (it exits non-zero instead), so a
silent version of this failure cannot reach a report as "no findings".

## Escalation rule

Move **up one tier** when the diff touches any of these, regardless of size:

- `**/providers/` — the mock↔office swap surface
- `**/contracts.py` — the shared return type both adapters must satisfy
- `back_dev_home/_runtime/` — site detection, provider registry, Redis plumbing
- `docs/datatables/` — the schema of record for office DBs

These are the surfaces where a missed finding does not fail at home. It fails
at the office, on a machine you cannot reach from here, on a later trip. A
one-file change to `providers/office_example.py` deserves `medium`, not
`light`, because home tests pass either way and the mock cannot contradict it.

Escalation is one step only: `light` → `medium` → `heavy` → `heavy`.

## Announce before spending

State the tier and the reason before running, in one line:

> 14 files, touches `sem_list/providers/` → escalating to `heavy` (kimi-k3)

The user can then interrupt and downgrade. Do not silently pick `heavy` on a
large diff that is entirely generated or vendored churn.

## Provider fallback

`oc.sh` tries `opencode-go/<model>` first, then `opencode/<model>` (Zen). If
both fail it reports each provider's reason and exits non-zero. It never falls
back to a *different* model — a review that quietly ran on a weaker tier than
you were told is worse than one that visibly did not run. Rerun with an
explicit `--model` if you want a substitute.

`oc.sh` prints the elapsed time of each call to stderr, not its cost — the
default output format carries no token accounting. For spend, use
`opencode stats`. Reviews are cheap relative to an office trip, but a `heavy`
debate over several rounds is not free.

## Notes

- On the OpenCode Go plan, `gpt-5.6-luna` and `deepseek-v4-flash` are marked
  "2x usage", meaning a doubled allowance — which is why `light` is the
  cheap tier rather than an expensive one.
- `opencode models` lists the full catalogue, not what the account is entitled
  to. Several ids there answer `Model is disabled` at call time. The three
  tiers above were each verified to respond on `opencode-go/`.
- Everything runs under `--agent plan`, which opencode enforces as read-only:
  it will run `git diff` and read files, but refuses to write. Findings come
  back as text and get applied by Claude, under the normal explicit-pathspec
  commit rules — and in a `git worktree` when the fixes span more than one
  file, per `CLAUDE.md`.
