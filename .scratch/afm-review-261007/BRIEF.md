# Review brief — AFM changes of 2026-10-07

You are the reviewer. **Read-only**: do not edit, stage, commit or check out
anything in this repository. The only file you write is
`.scratch/afm-review-261007/REVIEW.md`.

## What to review

Nine commits on `main`, one author, all AFM. Review the combined change:

```bash
git diff b9a96114 89eaeaf3 -- backend/afm backend/__init__.py frontend/app docs/api-contracts/afm.yaml
git log --oneline b9a96114..89eaeaf3 -- backend/afm frontend/app   # per-commit intent
```

Leave `82e9bc0d` (auth, another author) and `backend/afm/__fixtures__/*.json`
(regenerated captures) out. Docs under `docs/` are context, not the target —
but say so if the code contradicts what they record.

The change applied three rounds of answers from the office about the real AFM
data. The facts it was built on are in
`docs/datatables/afm/afm_redis.txt` and `docs/afm/office-data-findings.md`
(sections 7차, 8차, 9차 and the two 사용자 sections). Read those before judging
a rule as wrong: several look odd until you see the office's answer.

## What changed, by area

- `backend/afm/providers/office_example.py` — the office adapter template
  (never run at home; the office data is unreachable from here). New columns
  `measured_time`, `last_pick_up_time`; "original = whatever is not .webp";
  `get_tiff_original` now finds an original in any image list; fab from a table.
- `backend/afm/providers/mock.py` — generated values changed to match the
  office facts (tip mileage, widths, image names, Sample Count, slot_number…).
- `backend/afm/routes.py` — `tiff.zip?type=`.
- `backend/__init__.py` — `afm` exempt from the rate limit.
- `frontend/app/utils/afmTips.ts`, `afmTrend.ts`, `afmPoints.ts`,
  `afmPointsTable.ts`, `afmUsage.ts`, `afmSearch.ts`, `afmExport.ts` and the
  pages / components that call them — tip judging (per-tip width limits for
  MCNT, Mileage not judged), tip-change marks, `imagePoint`, the 회차 (Lap)
  column, measured time.

## What I want from you

Find defects — things that give a wrong result, crash, or silently show
nothing. In particular:

1. **Office-only paths.** The adapter is exercised only by
   `backend/afm/tests/test_office_template.py` with hand-built frames. Look for
   inputs the real frames can hold that the code mishandles: NaN / None / NaT
   cells, numpy arrays where a list is assumed, float where text is assumed,
   empty lists, names with `#`, spaces and parentheses.
2. **Mock ↔ adapter drift.** The same rule written twice (e.g. "what is an
   original", how an original is paired with its webp, how a null is produced)
   that does not agree between `mock.py` and `office_example.py`.
3. **Frontend logic** — `tipChanges`, `tipCategories` (per-tip limits, the
   `judged` / `hold` state), `imagePoint` (three name shapes now), `tagLaps`,
   `resolvePointColumnKeys`. Give a concrete input that produces a wrong output.
4. **Contract drift** — a field in `backend/afm/contracts.py` that the
   frontend type `AfmFileRow` (composables/useAfmDetailApi.ts) or
   `docs/api-contracts/afm.yaml` does not carry, or the reverse.
5. **Tests that would pass if the code were wrong** — an assertion that cannot
   fail, or a new rule with no test at all.

Not wanted: style, naming, comment wording, "consider extracting", or anything
you cannot attach a failing input to.

## Project constraints an outsider would not guess

- `backend/afm/data.py` is a fixed dispatcher and must not change; a new
  provider function is therefore expensive. That is why `get_tiff_original`
  kept its name while serving every image type.
- Python 3.11 at the office; pandas 3 (a text column's dtype is not `object`).
- No Pinia, no TanStack Query; pure functions under `frontend/app/utils` are
  tested with `node --test`.
- You may run, from the repo root:
  `.venv/bin/python -m pytest backend/afm -q` and, from `frontend/`,
  `node --test app/utils/afmTips.test.ts` (any `afm*.test.ts`). Do not start
  servers.

## Output — `.scratch/afm-review-261007/REVIEW.md`

One finding per heading, most severe first:

```markdown
## [blocker|should|nit] <one-line claim>
- Where: path:line
- Input: the concrete input / state
- Actual → Expected
- Why it matters: one sentence
```

End with a section `## Checked and found sound` listing what you examined and
could not break, so silence is not mistaken for coverage. If you found
nothing, say so plainly.
