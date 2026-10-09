# Review brief 3 — residual defects cleanup of 2026-10-09

Same rules as `./.scratch/skewvoir-afm-batch-261009/BRIEF.md` (standards, the
owner's rejections, report format) and the decisions listed in `BRIEF-2.md`.
Read-only: the only file you create or edit is
`./.scratch/skewvoir-afm-batch-261009/codex-review-3.md`. No servers, no browser.

## What to review

`git diff 20b3071e..HEAD` on `main` (11 commits). These close defects left
open by today's earlier work — several of them your own findings.

**Skewvoir**

| Commit | Claim |
| --- | --- |
| `5abb93bb` | One σ per screen: Distribution header and 파라미터 요약's Std read `cduMetrics` (client sample σ over `isMeasuredRow` rows) instead of the backend summary `std`; the Time-Series tooltip labels the backend value `std (서버 요약)`. |
| `9b2bb009` | Set-scope Composite Mean / Site Variability maps moved into `compositeSiteMap` (`baselineCompare.ts`): a site is (chip, `mp_number`), σ needs two wafers at that MP, members are `manifest.included`, and neither map is drawn when `analysis.siteDeltaReady` is false. `baselineDeltaMap` shares `collectChips`. |
| `1b52b5d3`, `ca827ecf`, `f7944e60` | Three receipt sheets: `위치 합성 site`, `반경 fit` (`radialSamples` exported from `spatial.ts`), `세트 상관`. The set-scope correlation axes are now URL state (`ax` / `ay`, `resolveAcrossMsrAxes` / `encodeAcrossMsrAxes` in `acrossMsr.ts`), and view and receipt both call `acrossMsrOutcomeFor`. A demo-data caution is added to home receipts. |
| `4cebdbdd` | `formatScaleLabel` (`utils/scaleLabel.ts`) for colour-scale end labels: enough decimals for the magnitude, never `-0`. Applied to `WaferHeatChart` and `ColorScaleBar`. |

**AFM**

| Commit | Claim |
| --- | --- |
| `5b6517d8` | Section 06: `relationState` decides empty / few / chart; an empty block shows one sentence only; legend entries appear only for marks that are drawn. |
| `3f76dc4a`, `f02fa311` | Section 07 legend likewise; a lone entry reads `측정`, not `다른 측정`. |
| `c08c2e06` | Recommendation doc: 관리선 → 기준 범위 in two places, plus the decision that a configurable 관리선 is built only on engineers' request. |
| `3cdd9810` | Left-rail Site layout: hint text says it is an index layout with larger Site Y at the top and cross-hairs at index 0; nothing about the notch. |

One more decision since the last brief (do not reopen): **the wafer notch
cannot be known and is not tracked** — the raw files carry no orientation,
engineers change it on purpose, checking it is theirs. Recorded in
`docs/datatables/afm/afm_raw_files.txt` and `backend/afm/providers/mock.py`.

## What I want, in priority order

1. **Correctness — give the failing input.**
   - `compositeSiteMap`: the chip value is the equal-weight mean of its (chip,
     MP) statistics, so an MP only one wafer measured still enters the chip mean
     with full weight. Is that a defect of the same kind as the Δ-map one you
     found (composition difference read as a value difference), or acceptable
     for a composite that is not a comparison? If a defect, say what rule you
     would hold it to. Also: σ averaged over only the MPs that have a σ; a
     wafer measuring one site twice; `included` versus all loaded files; the
     shared `collectChips` and `baselineDeltaMap`'s unchanged behaviour.
   - σ change (`5abb93bb`): any panel still showing the backend `std` under a
     label that reads as the same quantity; 파라미터 요약 now mixes backend
     Count / Mean / Min / Max with client Std in one row — can they visibly
     disagree on the mock, or only when an office row with `mp_number < 0`
     carries a number? The author left the Time-Series 산포 VERDICT on the
     backend `std` (labelled, not re-sourced): is that a wrong number, or only
     an inconsistency?
   - `세트 상관`: `featureRows` includes MSRs the manifest excluded, so the
     sheet (matching the screen) and `MSR별 지표` (included only) can list
     different MSR sets in one file. Is that misleading enough to be a blocker?
     `resolveAcrossMsrAxes` defaults and the `ax`/`ay` round trip; a stale
     `ax` naming an axis the current set does not have; Pearson / Spearman with
     n < 3, constant axis, ties.
   - `반경 fit`: do the coefficients, n and RMSE in the sheet equal what
     RadiusPlot shows for the same `rfit`; is the coefficient basis (`t =
     (반경 − 중간 반경) / 반폭`) stated correctly; `radialSamples` used
     identically by `analyzeSpatial`, RadiusPlot and the receipt.
   - `formatScaleLabel`: boundaries (99.95, 9.995, 0.9995, −0.0004, NaN,
     ±Infinity), and whether two different range ends can print as the same
     label (e.g. 0.2231 and 0.2234) and so show a zero-width scale.
   - AFM `relationState`, and the template conditions for the legend entries
     in `RelationChart.vue` and `ProfileOverlay.vue`.
2. **Claims the data cannot support.** Any verdict / significance / cause
   wording in the new sheets; any 관리선 / UCL / LCL left on live AFM screens;
   anything on the AFM Site layouts that implies a wafer outline, centre,
   notch or orientation.
3. **Behaviour changed outside the stated scope.** The authors were told to
   change nothing but the listed defects. Flag anything else that moved —
   including the two places they report: `ColorScaleBar` labels on single-scope
   maps (`45.0 → 45`, `0.3 → 0.25`), and section 06 no longer offering X = Y on
   a single-column block.
4. **Standards and tests** as before: tautological tests, behaviour with no
   test that deserves one (the authors say `compositeSiteMap`, `radialSamples`
   and the axis functions were only seen red as a missing export), Korean
   formal endings in docs.

Run what you can: `cd frontend && npm test && npm run lint` (nvm Node on PATH),
`.venv/bin/python -m pytest backend/msr_file backend/afm -q`,
`.venv/bin/python -m ruff check .`. Report counts and say plainly what the
sandbox stopped.

## Report

Same format (blocker / should / nit, `where`, `what`, failing input, suggested
fix), then what you checked, the gate results, and what you did NOT review.
Answer the direct questions above explicitly. Do not ask me questions — record
open questions in the file.
