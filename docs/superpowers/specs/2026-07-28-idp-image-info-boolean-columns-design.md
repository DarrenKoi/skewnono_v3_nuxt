# `idp_image_info` boolean columns — Design

- **Date:** 2026-07-28
- **Status:** approved
- **Area:** `recipe_search` recipe-open (`IDP_IMAGE_INFO` table) — backend contract, mock, home parser stand-in, frontend render sites

## Problem

The recipe-open screen has rendered the `idp_image_info` table since 2026-07-16.
It already shows exactly the eight columns the office confirms are the
frontend's business — `Parameter`, `SEQ`/`Last_SEQ`, `Region`, `Addressing`,
`Mother_Para`, `Double_Addressing`, `Meas_Counting`, `dnumber_removed` — and it
already keeps the five `img_*` columns out of that table.

What it got wrong is the **type** of three of them. Until 2026-07-28 nobody had
run the real office parser, so `docs/datatables/recipe_idp.txt` recorded guesses
and the home stand-in reproduced those guesses faithfully. The frontend was then
built against the stand-in and passed every test at home:

| Column | Built as | Rendered as | Actually is |
| --- | --- | --- | --- |
| `Addressing` | `str` `"Yes"`/`"No"` | `YesNoPill` (3 call sites) | `bool` |
| `Mother_Para` | `str` parameter name (`"Para_3"`) | plain text, `← Para_3` | `bool` |
| `dnumber_removed` | `int64` | plain number | `bool` |

This is the failure mode `docs/datatables/recipe_idp.txt` warns about in its own
header — *"컬럼 이름이 어긋나면 집에서는 통과하고 사무실에서만 깨진다"* — reached
through dtypes rather than names. `img_meas2` did the same thing for months.

The `Mother_Para` case is the worst of the three, because the guess leaked into
UI semantics: `RecipeOpenView.vue:93-98` renders `← {{ Mother_Para }}`, an arrow
pointing at another parameter by name. The real frame carries no such name, so
that arrow can only ever render `← true`.

## What the office run confirmed (user-confirmed 2026-07-28)

Established by running `scripts/probe_recipe_ftp.py` at the office against a
real `.idp` — the first time `combined_idp_info()` output has been seen:

1. **All three columns are real `bool` dtype.** Cells are `True`/`False`, not
   `"Yes"`/`"No"`, not `0`/`1`.
2. **`Mother_Para = True` means the row's own parameter IS a mother.** Usually
   the parameter with `SEQ = 1`. Son parameters obtain their cd_values from the
   *same image* as the mother's — which is why the `img_*` slots matter and why
   sons need no image of their own.
3. **`Region = P_No`.** `idp_image_info.Region` carries the same value as
   `wafer_mp_info.P_No`, making it a join key between the two tables.
4. **`D_No = -1` ⟺ `dnumber_removed = True`.** A `wafer_mp_info` row with
   `D_No = -1` is the same fact as the parameter's `dnumber_removed` flag.
5. **`dnumber_removed = True` means data is suppressed** — the d-number is
   removed, so nothing is sent to the legacy system.
6. **The five `img_*` columns are internal.** `img_add1`, `img_add2`,
   `img_meas1`, `img_meas2`, `image_add3` are keys used to fetch raw recipe /
   AMP (auto measurement parameter) data, not display columns.

Facts 3 and 4 are cross-table invariants that nothing in the codebase currently
expresses. They are recorded here and in `recipe_idp.txt` so they are not
re-guessed; acting on them is out of scope (see the last section).

## Approach

**Correct the types at the source of truth and fix the render sites.** No new
machinery. The office adapter needs *zero* logic change: `_scalar()`
(`providers/office_example.py:460-479`) already converts `numpy.bool_` to a
Python `bool` via `.item()`, and `_records()` already restricts to documented
columns in contract order.

Two alternatives were considered and rejected.

**A dtype assertion in the adapter** — validate that these columns arrive as
`bool` and log loudly otherwise. Rejected: `_records()` already logs missing and
undocumented columns, and the dtypes are now confirmed rather than assumed. This
would add a gate against a hypothetical future drift immediately after closing
the actual one.

**Defensive coercion** — normalise `"Yes"`, `1`, `True` to `bool` in the adapter
so any future parser shape keeps working. Rejected, and it is the actively
dangerous option: `Boolean("False") === true` in JavaScript, so a future string
regression would render *every* row as True. That is silently plausible wrong
data — precisely the failure mode that produced this bug. A shape change should
break loudly.

## Design — display

`BoolPill` (`recipeOpen/BoolPill.vue`) already takes an `okWhen` prop, so
polarity is expressible without touching the component:

- `Addressing`, `Mother_Para`, `Double_Addressing` — default pill, `True` reads
  as the normal state (green).
- `dnumber_removed` — `:ok-when="false"`, so `True` renders in the muted
  exception style.

The polarity matters. `dnumber_removed = True` means the row's data never
reaches the legacy system; painting that green would tell an operator the
opposite of what it means. With `okWhen=false` a suppressed row reads as the odd
one out in the column.

```text
Parameter    SEQ    Region  Addr    Mother  Double  Cnt  d# 제거
─────────────────────────────────────────────────────────────────
CD_TOP_L     1/12   3      (True)  (True)  (False)   4   (False)
CD_BOT_L     2/12   3      (True)  (False) (True)    2   (True)
                                                          ↑ muted — suppressed
```

`YesNoPill.vue` has no remaining caller once `Addressing` becomes a boolean at
its three sites, so it is deleted rather than left as dead code.

## Changes — backend

| File | Change |
| --- | --- |
| `recipe_search/contracts.py:72-76` | `Addressing: bool`, `Mother_Para: bool`, `dnumber_removed: bool` on `IdpImageInfoRow` |
| `docs/datatables/recipe_idp.txt` | The three dtypes; delete the stale `"Yes"/"No"` and `Para_N` notes; add facts 2-6 above as user-confirmed 2026-07-28 |
| `recipe_search/providers/mock.py:232-236` | Emit booleans. `Mother_Para = (seq == 1)` so the mock stops implying every row has a named mother |
| `recipe_search/providers/office_example.py`, `office.py` | Docstring only — the schema note at `:43` describing `img_meas2`. No logic change |
| `recipe_search/MIGRATION.md` | Record the corrected dtypes and the date they were confirmed |
| `office_utils/read_idp_info.py` | `_IMAGE_DTYPES` three entries → `"bool"`; same `seq == 1` rule for `Mother_Para` |

**`office_utils/read_idp_info.py` is gitignored and machine-specific.** At home
it is the fabricating stand-in and must be edited. At the office it is the
**real parser** and must not be touched. The change therefore cannot be
committed and has to be applied on the home machine only.

## Changes — frontend

| File | Change |
| --- | --- |
| `composables/useRecipeSearchApi.ts:69-73` | Three types → `boolean` |
| `composables/useRecipeCompareApi.ts:7-12` | Same three |
| `recipeOpen/IdpTable.vue:82,85,94` | `Addressing` and `Mother_Para` → `BoolPill`; `dnumber_removed` → `BoolPill :ok-when="false"` |
| `recipeOpen/IdpTable.vue:134` | Column label `d#_rm` → `d# 제거` |
| `recipeOpen/OverviewKV.vue:17,22,37` | Same three fields → pills |
| `RecipeOpenView.vue:92-98` | `Addressing` → `BoolPill`; delete the `← {{ Mother_Para }}` arrow, replace with a `MOTHER` pill rendered only when true |
| `recipeOpen/YesNoPill.vue` | Deleted — no remaining callers |
| `utils/recipeOpenTable.ts` | **No change.** `compare()` (`:20-22`) already handles booleans, so sorting on all four keeps working |
| `utils/recipeCompare.ts:159-166` | `buildIdpRows()` stringifies cells with `String(v)`, which turns a boolean into lowercase `"true"`/`"false"` — inconsistent with `BoolPill`'s `True`/`False` on the open screen. Format booleans explicitly. `cellsDiffer()` needs no change: it compares the stringified values, so diffing keeps working either way. `IDP_COMPARE_FIELDS` labels unchanged |

## Error handling

Nothing new. `_scalar()` maps `NaN` to `None`, so a missing boolean reaches the
frontend as `null` and `BoolPill` renders it False (falsy) — the muted state,
which reads correctly as "not set" rather than as an error. `_records()` keeps
logging if the parser ever stops emitting one of these columns.

## Testing

Fixtures move to booleans:

- `front-dev-home/app/utils/recipeOpenTable.test.ts:12-14`
- `front-dev-home/app/utils/recipeView.test.ts:63-64`
- `front-dev-home/app/utils/recipeCompare.test.ts:19-20,77,113`
- `back_dev_home/ebeam/hitachi/recipe_search/tests/test_contract.py`
- `back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_mapping.py`

Gates:

```bash
npm --prefix front-dev-home run typecheck   # red BEFORE the fix — that is the proof
npm --prefix front-dev-home run test
npm --prefix front-dev-home run lint
python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests -v
python -m pytest back_dev_home -q
```

`typecheck` failing before the change is the evidence the old types were wrong,
so run it first and record the failure.

## Out of scope

Deriving `dnumber_removed` from `D_No == -1`, joining the MP table on
`Region = P_No`, and anything in the `img_*` → AMP thread. Real work, unblocked
by the facts above, but separate from correcting the table's types — they are
items 1-3 of the next section, deferred rather than dropped.

## What we have to do together

Each of these needs office data or a decision that only you can make. Listed
roughly in dependency order.

1. **Parse the `{idp_name}/` raw-recipe folder.** `probe_recipe_ftp.py` lists it
   but downloads nothing. The five `img_*` columns are keys into it, and fact 2
   (sons share the mother's image) says the same image is referenced by several
   parameters. This is the source for `amp_info` and `align_images`, both still
   fabricated at the office by `_sourceless_extras()`
   (`office_example.py:511-535`). Needs: a probe run that downloads the folder
   so we can see what the files are before designing a parser.

2. **Decide whether `Region = P_No` should replace the `Parameter` join.** The
   MP table is filtered against `idp_image_info` by `Parameter` string equality,
   and `office_example.py:566-574` already logs a warning because that match is
   fragile — a stray space or case difference renders the MP table silently
   empty. `Region = P_No` is an integer join that cannot drift that way. Needs:
   confirmation that Region↔P_No holds for every row, not just the sampled
   recipe, and a call on whether to switch or to join on both.

3. **Decide what `D_No = -1` should do on screen.** It is the same fact as
   `dnumber_removed`, expressed per measurement point instead of per parameter.
   Options: mark those MP rows as suppressed, use the pair as a consistency
   check, or leave it as documentation only. Needs: a UX call from you.

4. **Close the remaining OFFICE-VERIFY items in `recipe_idp.txt`.** Does
   `Parameter` match byte-for-byte between `wafer_mp_info` and `idp_image_info`?
   What do the `img_*` strings actually contain — filenames, or keys needing
   assembly? Both are answerable from a probe run you have already done; they
   need reading off the frames rather than new work.

5. **Confirm the `Mother_Para` ≈ `SEQ = 1` rule.** You described it as "usually"
   true. If it is an invariant we can lean on it in the UI (group sons under
   their mother); if it is only usually true we must not. Needs: a look across
   several recipes, not one.

6. **`amp_info` / `align_images` contract review.** Once (1) lands, the
   fabricated `AmpRow` shape (`contracts.py:82-103`) meets real data and will
   almost certainly need the same kind of correction this spec applies to
   `IdpImageInfoRow`. Worth reviewing the shape before the parser is written
   rather than after.
