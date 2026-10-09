# Review brief 2 — AFM follow-up of 2026-10-09

Same rules as `./.scratch/skewvoir-afm-batch-261009/BRIEF.md` (read it for the
standards, the owner's rejections and the report format). Read-only: the only
file you create or edit is
`./.scratch/skewvoir-afm-batch-261009/codex-review-2.md`. No servers, no browser.

## What to review

`git diff a7d79271..HEAD` on `main` (5 commits, all AFM):

| Commit | Claim |
| --- | --- |
| `93c9f236` | 팁 모니터링 and the AFM intro copy call the self-computed band 기준 범위, not 관리선. Wording only. |
| `c37b5af6` | 시계열 비교 section 02 gains a 포함 / 제외 toggle for FAILED · Valid FALSE rows (`pointValues`, `pointScope` in `utils/afmTrend.ts`); default 포함 = old behaviour; choice persisted with `usePersistedState`. |
| `34d86fcf` | New office fact, `user-confirmed 2026-10-09`: the larger `Site Y` index is drawn at the top. Recorded in `docs/datatables/afm/afm_raw_files.txt` and `backend/afm/providers/mock.py`; `SiteGrid.vue` copy updated. Units, X direction, notch and mm mapping stay unconfirmed. |
| `302f43da`, `e3518680` | 이상 측정 조사 묶음: an xlsx from the 시계열 비교 header (`utils/afmBundle.ts`, `components/afm/trend/BundleModal.vue`). Suspect = what the screen already marks (`TrendRow.out`, or a measurement with a non-COMPLETED row). Numbers rounded to 4 decimals. |

Owner decisions behind these (do not reopen them, but do flag where the code
departs from them): rename the band now and build a real configurable 관리선
only if engineers ask; the section-02 toggle must exist and default to 포함;
larger Site Y at the top is confirmed; the investigation bundle is a file
(the recommendation doc's section 8.3 put a screen first — the owner chose the
file).

## What I want, in priority order

1. **Correctness.** Give the failing input.
   - `utils/afmTrend.ts`: does 포함 mode produce byte-identical results to before
     `c37b5af6` (it must)? In 제외 mode, the repeat-lap rule ("drop invalid rows,
     then last lap wins"), a point with no valid row, and `pointScope`'s
     `invalid` count. Does anything downstream of section 02 (포인트 안정도 σ,
     the 기준 대비 Δ mode, the reference line) still read the unscoped rows?
   - `utils/afmBundle.ts`: does every number in the file match the screen for
     the same state — band, μ, Δ, out flags, FAILED/STOPPED counts, per-point
     reference? The per-point reference is taken with `pointMatrix(..., 'mean',
     null)` in 포함 mode regardless of the new toggle: is the file then
     inconsistent with a screen showing 제외, and does the file say which it
     used? Pinned-baseline groups: the measurement-level band comes from the
     baseline while the per-point reference is the group mean — is that stated
     clearly enough not to mislead? Mixed-recipe groups. Measurements that
     failed to load. `기준 범위` switched off.
   - `BundleModal.vue` and the `see-together.vue` wiring: enabled/disabled
     states, a download attempted while details are still loading, the memo.
   - Rounding in `e3518680`: can it turn a displayed "밖" into a value that looks
     inside the rounded band, or otherwise make two cells disagree?
2. **Claims the data cannot support.** Any 관리선 / UCL / LCL / spec / verdict /
   cause wording left on live AFM screens or in the bundle's text; anything that
   treats the Site Y confirmation as more than a drawing direction (wafer
   outline, notch, mm, radius, centre/edge).
3. **Two-places rule** for the Site Y fact: is it in both the datatables file
   and the mock docstring, with the same scope, and is anything that is still
   unconfirmed now written as confirmed anywhere (code comments, docs, UI)?
4. **Standards and tests** as in the first brief: tautological tests, behaviour
   with no test that deserves one, `usePersistedState` usage, colours, Korean
   formal endings in docs.

Run what you can: `cd frontend && npm test && npm run lint`,
`.venv/bin/python -m pytest backend/afm -q`, `.venv/bin/python -m ruff check .`
(use the nvm Node on PATH as last time). Report counts and say plainly what the
sandbox stopped.

## Report

Same format as before (blocker / should / nit, `where`, `what`, failing input,
suggested fix), then what you checked, the gate results, and what you did NOT
review. Do not ask me questions — record open questions in the file.
