# FDC fleet view — verify it against the real side-fields

This brief is for an LLM running **at the office**, next to the real data. It
follows `hardware_fdc_sce_characterization.md`. That run's findings led to the
write-time side-fields, and home built a fab-wide FDC view on top of them:
the `fdc-fleet` hardware service and the `fab 전체` toggle on the FDC tab.

Home built that view against the field list from the office letter of
2026-09-28, not against the index. Only the office can say whether the
aggregations read real fields and return real numbers.

## Status after the first run (2026-09-28)

| Check | Result |
| --- | --- |
| V0.1 | The field is `pin_judgment` / `spm_judgment`, with no 'e'. The code now reads those names, and a test pins them |
| Deployment | Not yet: the writer lives in the scheduler repo and prod was not restarted, so 0 docs carry side-fields. They appear from the next 6 h FDC run after the restart |
| Dry run | The aggregation body runs on the real index in 27 ms. Unmapped fields return empty buckets, not a 500 |
| V3.1 | OK: no distinct docs of one tool share a timestamp, and every duplicate is byte-identical |
| V3.3 | OK: no SPM numbers are aggregated |
| Duplicates | Contactpin 0.38 %, TemperatureEChuck 0.76 % on the busiest tools |
| V3.2 | Busiest tools log ~2.7k Contactpin docs per 30 days, at the edge of the ~3000 default, so the query now sets `precision_threshold` 40000 |
| **Pending** | V0.3, V0.4, V1, V2 and V4. Re-run them 2-3 days after deployment |

## Status after the post-deploy check (2026-09-29)

| Check | Result |
| --- | --- |
| Deployment | Live since 2026-09-28. Side-fields exist in backing index 000005 only; older backing indices have none, as expected |
| V0.2 | OK: numbers are `float` / `long`, strings are `text` + `.keyword` |
| Fleet run | M16A: 57 ms, 34 tools, real temperature and laser means |
| Transition | ~6.8 % of docs written 2026-09-28 11:20-12:45 stay fieldless for good: an old-code twin task wrote them first and the create-dedup locked the `_id`. They add nothing to the aggregates; no action needed |
| CG5000 | SPMVoltages lines carry no fit-model token, so `spm_judgment` is always absent. CG5000 is SPM-only, so its fleet row has empty temperature, laser and Contactpin fields; that is a normal row |

Written 2026-09-28 from `backend/ebeam/hardware/providers/fdc/fleet.py`,
`fdc/office_example.py` (`build_fdc_fleet`) and
`frontend/app/components/ebeam/hardware/FdcFleetView.vue`.

## Rules for the run

- **Read-only.** Do not change code, indices, Redis or MinIO.
- **Mark provenance on every finding.** Use `office 확인 YYYY-MM-DD` for a
  number you computed today and `OFFICE-VERIFY` for anything you could not
  confirm.
- **Report numbers, not rows.** Where a sample is asked for, keep it to the
  size asked for.
- **Say what you could not answer and why.** A gap is useful; a guess dressed
  as a finding is not.
- Each check names what it **decides**. End each one with a verdict: `OK`,
  `FIX: <the change>` or `undecided: <why>`.

## Before you start

1. `git pull`, then refresh the FDC adapter from its template. `fdc/office.py`
   is a copy, and `build_fdc_fleet` is new, so an old copy has no fleet
   function.

   ```bash
   cp backend/ebeam/hardware/providers/fdc/office_example.py \
      backend/ebeam/hardware/providers/fdc/office.py
   ```

   If your `office.py` carries local edits, merge them by hand instead of
   overwriting. After restarting Flask, the boot log must not flag the
   hardware FDC adapter as STALE, and `GET /api/health/providers` must show
   `office` for hardware.
2. Pick the sample:
   - at least 2 M-fabs plus R3;
   - in one of them, one CG6300 tool (all four keys) and one GT2000/GT2000S
     tool (no Contactpin);
   - the window is the 30 days ending today, as on the page.
3. Note the date the side-field writer was deployed. Every check depends on
   how many days of side-fields exist.

The code under test:

```python
from datetime import datetime, timedelta
from backend.ebeam.hardware.providers.fdc import fleet
from backend.ebeam.hardware.providers.fdc.office import build_fdc_fleet, build_fdc_docs, INDEX
from backend.ebeam._office_search import client
from backend.sem_list.data import get_sem_list

end = datetime.now()
start = end - timedelta(days=30)
out = build_fdc_fleet("M16A", start, end)          # the payload's `fleet` object
body = {"size": 0, "aggs": fleet.fleet_aggs()}      # the exact aggregation it sends
```

## V0. Fields exist, with the names and types the code reads (do this first)

| # | Question | How | Decides |
| --- | --- | --- | --- |
| V0.1 | The mapping of `temp_pos`, `temp_c`, `laser_x1`, `laser_y1`, `spm_channel`, `spm_judgment`, `pin_channel`, `pin_no`, `pin_judgment`, `pin_spread`, `pin_counter` in **every** backing index behind the alias | `GET network_fdc_cdsem/_mapping/field/<names>` | Whether any name in `fleet.py` is wrong. Settled 2026-09-28: `judgment`, no 'e'; the code reads `fleet.JUDGMENT_KW = "pin_judgment.keyword"` |
| V0.2 | Are the numeric fields `long`/`float` in every backing index? Are the string fields `text` + `.keyword`? | same | If one backing index mapped `temp_c` as `long` (the first write looked integral), its averages are truncated |
| V0.3 | Since the deployment date: docs per `fdc_key`, and how many of them carry each side-field | `exists` filter per field, `terms fdc_key.keyword` | Whether the writer runs on every doc or only some tasks. A Temperature doc without `temp_c` means a gap in the writer |
| V0.4 | The earliest `timestamp` that carries a side-field | `min` agg under an `exists` filter | Whether the page needs a "집계 시작일" note while the 30-day window is only partly filled |

## V1. The adapter runs

| # | Question | How | Decides |
| --- | --- | --- | --- |
| V1.1 | Does `build_fdc_fleet(fab, start, end)` return without error for each sample fab? Report the tool count and the wall time | the snippet above | That the office path works end to end |
| V1.2 | `len(out["tools"])` vs the fab's CD-SEM roster size (`fleet.fab_roster(get_sem_list(), fab)`). List the roster tools missing from `tools`, with their `eqp_model_cd` | compare | Missing tools must be explainable: no FDC, or no side-fields yet. **A present tool reported missing** means an `eqp_id` spelling mismatch between roster and index |
| V1.3 | The aggregation's own latency and bucket count (tools × days) | `os_timing` or `took` from a raw `client().search(index=INDEX, body=body)` | That it stays "one cheap request", and far from `search.max_buckets` |
| V1.4 | Does R3 behave like the M-fabs? | same | R3 has FDC; only SCE is 미수집 there |

## V2. Each number matches the raw docs

Pick **one CG6300 tool** from V1.1. Recompute each fleet number from raw docs
(`build_fdc_docs(tool, fab, start, end)`, or a direct query), parsing `values`
yourself, **not** through the side-fields. Restrict the raw docs to timestamps
after the deployment date, as the side-fields are.

| # | Fleet number | Recompute from | Decides |
| --- | --- | --- | --- |
| V2.1 | `temp_c` (window mean) and 3 sample `temp_days` | mean of `float(values[3])` over TemperatureEChuck docs; per KST calendar day | The heatmap is right. Also check a day near midnight: are the day buckets KST days? The stored timestamp is an offset-less KST wall clock |
| V2.2 | `laser_x1`, `laser_y1` | mean of `values[2]` / `values[3]` | The laser ranking is right |
| V2.3 | `pin_counts` per judgement | distinct `(timestamp, values)` per `values[4]` | The dedupe is right. Also report the plain `doc_count` beside it and the duplicate share |
| V2.4 | `counter_rates` per channel | per `values[2]`: `(max - min)` of `values[9]` ÷ days between first and last doc | The rate is right. Also say whether any channel's counter **decreased** inside the window, which would mean a reset: `(max - min)` then overstates |
| V2.5 | `spread_bins` for the fab: total count per judgement | the count of Contactpin docs with 4 parseable numbers | The histogram covers every doc. `'25,0'`-style comma cells: how many, and did the writer read them as 25.0? |

## V3. The two cautions from the letter

| # | Question | How | Decides |
| --- | --- | --- | --- |
| V3.1 | Can two **distinct** Contactpin docs of one tool share a `timestamp`? | group raw docs by `(eqp_id, timestamp)`, count distinct `values` | `pin_counts` uses `cardinality(timestamp)`, which counts such a pair once. If it happens, that count undercounts |
| V3.2 | Is `cardinality` exact at our sizes? Compare it with V2.3's hand count | compare | The default `precision_threshold` is exact below ~3000 per bucket |
| V3.3 | Confirm nothing in the fleet view compares SPM numbers | read `fleet.fleet_aggs()` | SPM units differ up to 100× between tools |

## V4. The page

| # | Question | How | Decides |
| --- | --- | --- | --- |
| V4.1 | `GET /api/cdsem/hardware/<eqp_id>/fdc-fleet?fab_name=<FAB>` returns `available: true` and a `fleet` object | curl with the `LASTUSER` cookie | The service is routed and gated correctly |
| V4.2 | On H/W 관리 → FDC → `fab 전체`: do the five sections render? Heatmap, laser ranking, Contactpin 판정 비율, margin 분포, counter 증가율. Any console error? | the browser | The view works on real data |
| V4.3 | Do the views read right? The hottest tools on top of the heatmap, the worst green rate on top of the strip, where the 15–20 band falls against the real classes | screenshot + one line each | Whether the view needs another pass |
| V4.4 | For an HV-SEM tool, and with no fab selected: is the view unavailable, and does no 500 appear? | the browser | The gates hold |

## Report format

1. **Findings**, one line each, grouped by the ids above:

   ```text
   <id> | <finding with numbers> | <provenance> | evidence (query/code + one sample value)
   ```

2. **Fixes needed**: each `FIX:` with the file and the exact change. The most
   likely one is a field name in `fleet.py`.
3. **Deployment facts** for the datatables doc: the writer's deployment date,
   the side-field coverage per key (V0.3), and the duplicate share (V2.3).

The confirmed facts then go into `hardware_network_fdc_cdsem.txt` (section
`typed side-field`) and `fdc/mock.py`, as `CLAUDE.md` requires for any
office-DB fact.
