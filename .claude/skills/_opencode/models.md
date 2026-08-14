# opencode model tiers

Shared reference for the `oc-review`, `oc-simplify`, and `oc-discuss` skills.
All three shell out through `.claude/skills/_opencode/oc.sh`, which maps a tier
name to a model and handles provider fallback.

## The three tiers

| Tier | Model | Reach for it when |
| --- | --- | --- |
| `heavy` | `glm-5.3` | More than ~10 changed files, cross-feature contracts, security or auth logic, concurrency, or anything touching the mock→office swap |
| `medium` | `deepseek-v4-pro` | The common case: one feature slice, roughly 3–10 files, ordinary application logic |
| `light` | `gpt-5.6-luna` | A single file, docs, tests, renames, formatting, or a mechanical change |

Invoke by tier, not by model id, so the mapping stays in one place:

```bash
echo "$PROMPT" | .claude/skills/_opencode/oc.sh --tier medium --label standards
```

Override with an explicit model when the user names one:

```bash
echo "$PROMPT" | .claude/skills/_opencode/oc.sh --model kimi-k3 --label standards
```

## Measured reliability (2026-08-15)

The tiers above describe *how much capability a task deserves*. This section
describes *what actually works*, which is not the same thing, and was found by
running them rather than by reading docs.

The probe is a bounded review of one real commit that **requires** three tool
calls (`git show --stat`, `git show`, one full file read) and ends with a
falsifiable demand: *name one file you read that was not in the diff*. A model
that answered from the prompt alone cannot fill that last field correctly, so
the check does not depend on judging whether the prose sounds plausible.

| Model | Tool-using review | Elapsed | Notes |
| --- | --- | --- | --- |
| `glm-5.3` | **works** | 68s on Go | Every `main.css` line number it cited verified exactly; ran `node --test` unprompted and reported 19/19 |
| `deepseek-v4-pro` | **works** | 83s on Go | Same citations verified; also reasoned correctly about a non-generic predicate being contravariant-safe against generic callers |
| `kimi-k3` | works | 137–194s | Measured 2026-08-10, the previous `heavy`. Still fine, just slower than `glm-5.3` here |
| `glm-5.2` | **unreliable** | — | 2026-08-10: two failures out of two, once a hallucinated unrelated document, once an empty final message. Retired from the tier table |
| `gpt-5.6-luna` | untested at length | — | Fine for short bounded prompts |

**Consequence: the blanket "always default to `heavy`" workaround is lifted.**
It existed for one reason — `glm-5.2` died on exactly the tool-using shape every
`oc-*` skill produces — and the model that caused it is no longer in the table.
`medium` is now a measured-working tier, so the skills pick a tier by the
complexity rubric again. `light` is still untested at review length and is still
not a floor any `oc-*` skill should choose on its own.

Recheck is cheap and the probe is reusable: point the prompt above at any recent
commit, run it under `--model <candidate>`, then *verify the line numbers it
cites* rather than reading the report for tone.

`oc.sh` refuses to print an empty reply (it exits non-zero instead), so a
silent version of the `glm-5.2` failure cannot reach a report as "no findings".

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

> 14 files, touches `sem_list/providers/` → escalating to `heavy` (glm-5.3)

The user can then interrupt and downgrade. Do not silently pick `heavy` on a
large diff that is entirely generated or vendored churn.

## Provider fallback

`oc.sh` tries `opencode-go/<model>` first, then `opencode/<model>` (Zen). If
both fail it reports each provider's reason and exits non-zero. It never falls
back to a *different* model — a review that quietly ran on a weaker tier than
you were told is worse than one that visibly did not run. Rerun with an
explicit `--model` if you want a substitute.

**Go first is deliberate and the two catalogues are not the same.** Go carries
the open-weight models; Zen carries those *plus* the Claude, Gemini and GPT
families. So the retry is only a real safety net for an id that exists on both,
and choosing a model means choosing its fallback story too:

| Model | Go | Zen | What a Go failure means |
| --- | --- | --- | --- |
| `deepseek-v4-pro` (`medium`) | yes | yes | retried on Zen, same model |
| `gpt-5.6-luna` (`light`) | yes | yes | retried on Zen, same model |
| `glm-5.3` (`heavy`) | yes | **no** | the Zen retry cannot succeed — the run just fails |
| `kimi-k3`, `kimi-k2.7-code`, `grok-4.5`, `minimax-m3`, `qwen3.6-plus`, `deepseek-v4-flash`, `glm-5.2` | yes | yes | retried on Zen |
| `qwen3.8-max`, `qwen3.7-max`, `mimo-v2.5-pro`, `hy3` | yes | **no** | no fallback |
| Claude / Gemini / `gpt-5.x` (except `-luna`) | **no** | yes | wastes one guaranteed-failed Go attempt first |

The Go-only `heavy` tier is an accepted trade: `glm-5.3` was the fastest
verified reviewer in the probe above, and `oc.sh` fails loudly rather than
silently substituting, so a lost fallback costs a visible rerun and never a
review you were misled about. Rerun with `--model kimi-k3` — which *is* on both
— if Go is down.

`oc.sh` prints the elapsed time of each call to stderr, not its cost — the
default output format carries no token accounting. For spend, use
`opencode stats`. Reviews are cheap relative to an office trip, but a `heavy`
debate over several rounds is not free.

## Notes

- On the OpenCode Go plan, `gpt-5.6-luna` and `deepseek-v4-flash` are marked
  "2x usage", meaning a doubled allowance — which is why `light` is the
  cheap tier rather than an expensive one.
- `opencode models` lists the full catalogue, not what the account is entitled
  to, and it does **not** distinguish the two providers' coverage in a way you
  can eyeball. Several ids answer `Model is disabled` at call time. Derive the
  coverage table above with:

  ```bash
  opencode models | grep -E '^(opencode-go|opencode)/' | sort
  ```

  The three tiers above were each verified to respond on `opencode-go/`.
- Everything runs under `--agent plan`, which opencode enforces as read-only:
  it will run `git diff` and read files, but refuses to write. Findings come
  back as text and get applied by Claude, under the normal explicit-pathspec
  commit rules — and in a `git worktree` when the fixes span more than one
  file, per `CLAUDE.md`.
