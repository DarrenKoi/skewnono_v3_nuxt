# Review brief — skewvoir + AFM batch of 2026-10-09

You are the reviewer. Read-only: do not edit, stage, commit, or run git commands
that change state. Do not start servers or a browser. Write your findings to
`./REVIEW-2026-10-09.md` at the repo root (that one file is the only thing you
create) and stop.

Read `CLAUDE.md` first — it carries the project rules a finding may rest on.

## What to review

`git diff a49931d8..HEAD` on `main` (13 commits, list with
`git log --oneline a49931d8..HEAD`). Two independent tracks:

**Skewvoir (e-beam analysis workspace)**

| Commit | Claim |
| --- | --- |
| `728ec069` | mock FDC keys `ObjectSEM` / `VRD` match the pickle schema; a contract test guards it |
| `b490269c` | anomaly thresholds (`anom=`) and radial fit degree (`rfit=`) are URL-carried; thresholds edited in the left rail; set-load failure and the 30-member cap are surfaced; residual axis label follows the real baseline |
| `07258a80` | S7: hand-split baseline vs target (`base=`), block on Time-Series, delta map on 위치 비교 |
| `40327232` | S8: review receipt xlsx from the rail |
| `5f12dbf5`, `5872ffb3` | measurement-quality / execution signals as display-only axes and a Score layer |

**AFM**

| Commit | Claim |
| --- | --- |
| `832949cc` | fixed baseline on 시계열 비교; band no longer called 관리선/UCL/LCL |
| `5980e777` | 측정 상세 finds same lot+slot measurements and adds them to the group |
| `7d62a30c`, `ed48b95c` | section 06 측정 항목 간 관계 (scatter, n, r; no column difference) |
| `cb2b781b` | seconds per point in section 05 |
| `92011acf` | Site 인덱스 격자 card; old card renamed 포인트 스캔 높이 맵 |
| `ea463854` | section 07 1D 프로파일 겹쳐 보기 (same recipe/point/unit only; 없음 / 직선 제거 levelling; session cache) |

Design sources the code claims to follow:
`docs/research/2026-10-06-page-value-plans.md` (S7, S8, S6 and their
"built 2026-10-09" notes), `docs/afm/service-recommendations.md` (and its 3.5
build log), `docs/issues/skewvoir/analysis-coverage-gap-analysis.md` §9,
`DESIGN.md`.

## What I want from you, in priority order

1. **Correctness defects.** Wrong numbers, wrong pairing, off-by-one, a state
   that renders a false statement. Give the input that fails. Areas I trust least:
   - `frontend/app/utils/skewvoirAnalysis/baselineCompare.ts` — pooled 3σ across
     MSRs, the dominance rule, `baselineDeltaMap` site pairing and `unpaired`.
   - `frontend/app/utils/skewvoirAnalysis/receipt.ts` — does every number in the
     file match what the screen computes for the same state; role assignment;
     what happens when the focus MSR is excluded or a set file failed to load.
   - `frontend/app/utils/skewvoirAnalysis/routeQuery.ts` `parseAnomalyCfg` /
     `encodeAnomalyCfg` round trip, and `workspace/AnomalyThresholds.vue`'s
     draft/emit watchers (can they loop, or write a config the parser rejects?).
   - `useSkewvoirAnalysis.ts` `loadSet` / `retrySet` — I turned a watcher body
     into a function; check the stale-response guards still hold and `setError`
     cannot stick.
   - `frontend/app/utils/afmTrend.ts` baseline path, `useAfmCart.ts` `setGroup`
     prune, `afmLotHistory.ts` slot normalisation and `pickForGroup` room rule,
     `afmRelation.ts`, `afmDuration.ts` divisor, `afmSiteGrid.ts` repeat-lap and
     multi-point-per-site rules, `afmProfile.ts` (1D/2D classification, unit
     comparison, `levelLine` least squares) and the module-level profile cache
     in `components/afm/trend/ProfileOverlay.vue` (stale result on a changed
     point or group?).
2. **Claims the UI or docs make that the data cannot support.** This project's
   owner has rejected: Cp/Cpk and spec pass/fail, control limits derived from a
   user-picked set, vendor scores in any judgement path, AFM↔e-beam linking,
   wafer orientation claims for AFM `Site X/Y` (unconfirmed), any utilisation /
   OEE wording. Flag any place the new code or copy slides into one of these.
   Specifically verify the claim that the quality axes (`quality.*`,
   `measurement_score`) cannot reach `utils/anomaly/*`, `verdict.ts`,
   `overviewSites` or the Time-Series roll-up.
3. **Mock/office drift and the two-places rule.** An office-DB fact must be in
   `docs/datatables/` AND the feature's `providers/mock.py`. Also: did any
   frontend type drift from a `contracts.py` field; does anything new assume a
   non-null where the office may send null (the mocks emit no NaN/None).
4. **Standards.** `DESIGN.md` (colours only from `--sk-*` tokens / chart
   palette; the rail rule), no hand-rolled localStorage (must be
   `usePersistedState`), `useEchart` options must not depend on hover state and
   helpers must be declared above the option computed, no cross-page links
   added, Korean docs in formal endings.
5. **Tests.** Tautological assertions (expected value recomputed by the code's
   own formula), tests that cannot fail, and behaviour with no test at all
   that deserves one.

Run what you can: `cd frontend && npm test` and `npm run lint`, and
`.venv/bin/python -m pytest backend/msr_file -q` and
`.venv/bin/python -m ruff check .` from the root. Report the counts, and say
plainly if the sandbox stopped you from running something.

## Report format (`./REVIEW-2026-10-09.md`)

One section per track. Each finding:

```text
### [blocker|should|nit] short title
- where: path:line
- what: the defect, in one or two sentences
- failing input / evidence: the concrete case, or the command and its output
- suggested fix: one line
```

`blocker` = a wrong number or a false statement a user would act on, or a
broken gate. `should` = real but not misleading. `nit` = style. Do not pad:
if a track is clean say so, and list what you checked so I can tell coverage
from silence. End with the gate results and a list of what you did NOT review.
Do not ask me questions — record open questions in the file.
