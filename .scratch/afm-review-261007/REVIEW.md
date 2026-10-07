Reviewed the combined change from `b9a9611442f23fab8c0048ad038a5fc6e2b0eb17` to
`89eaeaf31fc31af774cfeb259175c24d05de82ad`, against the office replies 7–9 and
both user decisions. The auth change and regenerated JSON captures were excluded.
Six findings: three functional defects, two contract mismatches and one verified
test-coverage gap. No blocker found.

## [should] An MCNT tip with no applicable limits is reported as normal

- Where: `frontend/app/utils/afmTips.ts:168`, `frontend/app/utils/afmTips.ts:180`; verdict rendered at `frontend/app/pages/afm/[tool]/tips.vue:411` and `:443`.
- Input: Six Info-only measurements of `MCNT-150`, cassette `TC12`, port `1`: five measurements in slot `3`, one newer measurement in slot `9`. All widths are `35`; `approach_count_mean`, `mileage_mean`, `not_completed_count` and `invalid_count` are null throughout. Info-only measurements with null aggregates are permitted by the recorded office contract.
- Actual → Expected: `tipCategories(tipPoints(rows))` gives slot `9` `widthLimits: null`, `state: 'ok'`, and a verdict that its latest measurement is inside the limits. It should be `hold`: this tip has only one width and no other judged metric. `judged` is computed for the whole category, so slot `3`'s private MCNT width limits incorrectly authorize a verdict for slot `9`.
- Why it matters: The monitoring page gives an affirmative healthy verdict for a tip it could not evaluate. The existing MCNT test gives both tips at least five widths and misses this input.

## [should] Capture matching can take a point number from the filename prefix

- Where: `frontend/app/utils/afmPoints.ts:123`; consumed by `frontend/app/components/afm/detail/AnalysisImages.vue:401`.
- Input: `imagePoint('#260709#033958#RL1C_L1_XDEC_5MM_LINE#01#MON69683#NA#RL1C078_0001_0003.webp', ['0001', '0003'])`. This is a capture of `0003` whose original filename stem ends in `_0001`. MAPC01's original filename segment varies by recipe; the recorded capture contract guarantees the final `_<position>.webp`, without prohibiting this prefix. This is a contract-permitted adversarial input, not an office-observed filename.
- Actual → Expected: Returns `'0001'` → should return `'0003'`. The stripped-head candidate ends in `_0001` and returns before the complete capture stem ending in `_0003` is considered.
- Why it matters: The image receives the wrong point label, grouping and selected-point highlighting. Current tests cover point-like tokens earlier in a recipe, but not this filename-tail collision.

## [should] The column picker immediately undoes an explicit request to hide 회차

- Where: `frontend/app/utils/afmPointsTable.ts:59`; picker and persistence at `frontend/app/components/afm/detail/MeasurementPointsTable.vue:177` and `:186`.
- Input: A repeated-point table has columns `Lap`, `measurement_point`, `H (nm)` and `State`. Starting from all four selected, the user unchecks `Lap`, leaving `['measurement_point', 'H (nm)', 'State']`.
- Actual → Expected: `mergePointColumnKeys` correctly saves that selection, but `resolvePointColumnKeys` immediately returns `['Lap', 'measurement_point', 'H (nm)', 'State']` → the user's current selection should remain in effect. The rule for updating selections saved before the column existed also applies to deliberate new exclusions.
- Why it matters: 회차 is exposed as an ordinary selectable column but cannot be deselected. The new test checks migration of an old selection, without checking a subsequent picker change.

## [nit] The frontend still requires the method field that the providers stopped returning

- Where: `backend/afm/providers/mock.py:572`; stale declaration at `frontend/app/composables/useAfmDetailApi.ts:68`.
- Input: The first data row of a generated `Fi-Tapping TEST` measurement, with the mock date fixed to `2026-10-03`.
- Actual → Expected: The row has `'Method ID': 'Fi-Tapping TEST'` and no `Method_ID`, while `AfmDetailRow` requires `Method_ID: string | number` → the required frontend field should be `'Method ID'`, matching both providers and the seventh office reply.
- Why it matters: A response represented as `AfmDetailRow` violates its declared required shape; the pure-function fixtures continue supplying the obsolete spelling. No current production caller directly reads `Method_ID`, so this is contract drift rather than a demonstrated UI crash.

## [nit] The measurement YAML omits the new pickup field and retains the old slot format

- Where: `backend/afm/contracts.py:67`, `frontend/app/composables/useAfmDetailApi.ts:30`; schema at `docs/api-contracts/afm.yaml:42` and `:97`.
- Input: A measurement with `slot_number: '5'` and `last_pick_up_time: '2026-10-07 01:33:00'`, or null for an unrecorded pickup time.
- Actual → Expected: Both providers and the Python/frontend contracts carry the nullable pickup field, but YAML's `AfmMeasurementRow` omits it and still declares slot format `01..25` → YAML should carry `last_pick_up_time: string | null` and describe unpadded slot strings, with `''` for an unknown slot after adapter normalization.
- Why it matters: The published response description contradicts the ninth reply and the actual values added by this change.

The schema comparison also found nine older omitted tip/aggregate fields and five
obsolete camel-case `has*` fields present only in YAML. Those mismatches predate
this review range; they are not counted as additional introduced defects.

## [nit] The office tests stay green when BMP/PNG original handling is reverted

- Where: `backend/afm/tests/test_office_template.py:43`; changed classifier at `backend/afm/providers/office_example.py:250`.
- Input: An office record with `align_dir_list` containing full keys for `1_Result.webp` and `1_Result.bmp`. Replace only the classifier **in memory** with its previous rule, `lambda name: name.lower().endswith(('.tif', '.tiff'))`, then run the office-template tests.
- Actual → Expected: All seven tests still pass, although the regressed classifier would list the BMP as a gallery image and fail to offer the webp's BMP original → this input should cause a regression test to fail. The office fixtures contain Result TIFFs, but no align BMP, point-tip PNG, measurement-tip BMP or capture PNG.
- Why it matters: New download tests exercise the mock, leaving the independently implemented office branch unprotected. The current office implementation passed the manual inputs below; this finding concerns the demonstrated weakness of its tests.

## Checked and found sound

- Office facts: Read `docs/datatables/afm/afm_redis.txt` and the seventh, eighth, ninth and two user sections of `docs/afm/office-data-findings.md`. Confirmed the later replies take precedence on measured time, original formats, fab mapping and Mileage change evidence.
- Office normalization: Executed an in-memory parquet round trip through `pd.read_parquet` and `_records`, including numpy list arrays, null list cells, empty lists, NaN width/count cells, `None`, `pd.NA` and `NaT`. Resulting measurement rows matched `AfmMeasurementRow`; missing slots became `''`, and missing measured time, width and pickup became null. No new office runtime failure was reproduced for these inputs.
- Originals: Exercised the current office adapter with align BMP, point-tip PNG, measurement-tip BMP, capture PNG and Result TIFF pairs. Checked gallery exclusion of originals, original URL presence, unchanged original bytes, stored filenames and MIME types, including keys with `#`, spaces and parentheses. Mock and office agree on the non-webp rule and the tested same-stem pairing cases. Missing originals remain absent; the route tests cover unknown downloads and the align originals ZIP.
- Frontend: Verified ID/seat changes and the combined Mileage-decrease/pickup-change rule; Mileage is excluded from statistical judgment. Ordinary MCNT tips use their own width bands, and sparse widths have no band. The standard Height, C_PR, capture, align and C_Result filename cases passed, subject to the prefix collision above.
- Repetition and export: Checked per-block lap numbering, a partial final lap, absence of the generated column without repetition, table facets and persisted-column migration. Both detail Excel actions consume `tableRows`; `buildDetailedTable` puts generated Block/Lap columns first and retains ragged-row columns. The column-deselection exception is reported above.
- Time and contracts: Checked measured-time priority and null fallback in search and usage. `AfmFileRow` carries both newly added fields; it remains a consumer subset of the Python measurement row. Contract discrepancies are listed above.
- Rate limit: Statically traced the added `afm.` prefix through the shared `endpoint.startswith(_EXEMPT_BLUEPRINTS)` exemption loop. The new originals ZIP validates `type` and the frontend passes its active image type. No server or live rate-limit probe was run.
- Verification: `PYTHONDONTWRITEBYTECODE=1 ARROW_DEFAULT_MEMORY_POOL=system .venv/bin/python -m pytest backend/afm -q -p no:cacheprovider` — **82 passed**. From `frontend/`, Node 24 `node --test app/utils/afm*.test.ts` — **125 passed**. Additional inline probes reproduced the three functional findings; the in-memory classifier mutation reproduced **7 passing office tests despite the regression**. No test/probe files were created.
- Limits: No browser rendering, office Redis/MinIO, deployment or CI validation was performed. Tracked working-tree and index diffs were empty and HEAD remained at the target before writing this report. No repository edits, staging, commits, checkouts or server starts were performed; this report is the sole written file.

## Author's response (2026-10-07)

All six findings were accepted and fixed in `a1242477`.

| Finding | Outcome |
| --- | --- |
| MCNT tip with no applicable limits reported as normal | Fixed — a tip is held unless a limit applies to it; test added. |
| Capture matching takes a point from the filename prefix | Fixed — the whole stem is tried before the kind-stripped head; test added. |
| Column picker undoes hiding 회차 | Fixed — 회차 is structural: always shown on a repeat measurement, not offered in the picker. |
| Frontend type still requires `Method_ID` | Fixed — `AfmDetailRow` and the test fixtures use `Method ID`. |
| YAML omits the pick-up field, old slot format | Fixed. The nine older omitted fields and five camel-case `has*` fields predate today and were left. |
| Office tests green with BMP/PNG handling reverted | Fixed — the fixture carries align / tip / capture originals and a test pins them. |
