# Review brief — AMAT recipe_usage (VeritySEM / Provision)

Read-only code review. Do not edit source, start servers, or commit. Write findings to
`./.scratch/amat-recipe-usage-261112/codex-review.md` (that one file is the only write).

## Range
`git diff main..HEAD` on branch `work/amat-recipe` (this worktree). 10 commits.

## What it is
New backend feature `backend/ebeam/recipe_usage/` (3 GET endpoints, mock + office_example
providers sharing pure aggregation in `providers/_shape.py`) and frontend Recipe 검색 /
Recipe 현황 pages for the `veritysem` and `provision` tool families
(`frontend/app/components/ebeam/RecipeUsage*.vue`, `composables/useRecipeUsageApi.ts`,
`utils/recipeUsage.ts`, nav gating in `utils/features.ts` + `components/nav/FeatureTabs.vue`).

## Ground truth
- Contract: `backend/ebeam/recipe_usage/contracts.py`.
- Office facts: `docs/datatables/veritysem/recipe_usage.txt` (derived from two office notes at
  `/Users/daeyoung/Codes/skewnono_v3_nuxt/docs/office-migration/veritysem_provision_recipe_{list,usage}.txt`
  — check the doc and the code against those notes).
- Project rules: `CLAUDE.md`, `docs/back-end/vendor-onboarding.md` §5.

## Look hardest at
1. `_shape.py` correctness: list grain (eqp_id, recipe_id, fab_id) summed correctly; roster
   (sem_list) is the only tool authority and fab scope; zero-usage roster tools present; window
   math, zero-fill, anchor/data_start; fail_rate / avg division by zero; duplicate roster eqp_ids.
2. `office_example.py`: it has never run against real Redis. NaN/NaT/None, pandas 3 string
   dtype, bytes vs str hash fields, JSON vs Python-repr hash values, missing key behaviour,
   KST date handling (latest dt is yesterday; no UTC conversion anywhere).
3. Hitachi regressions: `DateRangePopover.vue`, `FailIssueRankingTable.vue`,
   `utils/pageIdentity.ts`, `backend/_logging/feature_map.py`, `features.ts` — must behave
   exactly as before for cd-sem / hv-sem.
4. Frontend: stale selection / fetch keys when fab or tool changes, chart option reactivity,
   table paging over ~11k catalogue rows, the Fail-tab minimum-runs guard.
5. Mock realism vs. the office notes (anything the mock teaches that the notes contradict).

## Output format
Findings as `blocker` / `should` / `nit`, each with `file:line`, a concrete failing input, and
the fix. Under about 150 lines. End with a one-line verdict: `SHIP` or `FIX FIRST`.
You may run: `/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest backend/ebeam/recipe_usage -q`
and `npm test` in `frontend/`.
