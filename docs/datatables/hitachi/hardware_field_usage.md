# Hardware page — what SKEWNONO expects from each office source

This brief is written for an LLM running **at the office**, next to the real
databases. Home cannot reach them, so everything below is what the code
*assumes*. Your job is to compare these assumptions against the real
Redis / OpenSearch / MinIO data and report every mismatch. That tells us why
data is missing on the Hardware page.

Written 2026-09-28 from `backend/ebeam/hardware/providers/*/office_example.py`
and the frontend panels under `frontend/app/components/ebeam/hardware/`. The
schema background for each source lives in the `hardware_*.txt` files in this
folder. Where this brief and those files disagree, report it.

## How to run the check

1. **Know which adapter code is actually running.** `office.py` is a gitignored
   copy of `office_example.py`, so the two can differ. Check both
   `ls backend/ebeam/hardware/providers/*/office.py` and
   `diff office_example.py office.py` per tab.
   - A tab without `office.py` silently serves **mock** data. The only trace is
     one INFO line in the server log (`hardware/<tab> has no providers/<tab>/office.py`).
   - `reso_center` and `mdc` templates were **reconstructed at home**. The
     office copies of those two came first and are the verified ones.
   - Say in your report which file you checked against.
2. **Get the real shape of each source.**
   - OpenSearch: `GET <index>/_mapping`, plus one or two recent `_source`
     samples for a known tool.
   - Redis: `HKEYS <key>` and one `HGET` per key.
   - MinIO: list the date folders and read one `{FAB}.json`.
3. **Run the adapter's own diagnostic.** Each tab module has a `__main__`
   block that prints raw values stage by stage, for example
   `python -m backend.ebeam.hardware.providers.fdc.office`. Use it when you
   need to find which query clause empties the result.
4. **Compare field by field** against the tables below, then write the report
   in the format at the end of this file.

## Shared request path (all 7 tabs)

- **Route:** `GET /api/{cdsem|hvsem}/hardware/{eqp_id}/{service}?fab_name=&start=&end=`
  - `service` is one of `bsm`, `reso-center`, `fdc`, `sharpness`, `mdc`,
    `sce`, `bm-pm`.
- **Window:** the frontend sends the last 30 days as UTC ISO strings. The route
  converts them to a **naive KST wall clock** before the adapters see them.
  - Every OpenSearch range filter therefore assumes the stored `timestamp` is
    **offset-less KST** (for example `2026-06-17T09:20:00`).
  - A stored `Z` or `+00:00` value makes the window slide 9 hours. You would see
    the newest ~9h of data missing, not an error.
- **Tool identity:** the tool selector's `eqp_id` comes from the `sem_list`
  roster, Redis `v3_df_sem_avail` + `v3_df_sem_version`. See `sem_list.txt`.
  - Three tabs look up a second value from that roster:
    - `sharpness` and `reso-center` need `eqp_id → eqp_ip`.
    - `mdc` history needs `eqp_id → fab_name`.
  - They raise an error if `sem_list` itself is on the mock provider.
  - The roster's `eqp_id` must match each index's stored `eqp_id`
    **character for character**, and its `eqp_ip` must match each index's
    stored IP the same way. A spelling difference returns zero documents. It
    shows as an empty chart, not an error.
- **CD-SEM gate:** `bsm`, `reso-center`, `sce` and `sharpness` answer HV-SEM
  tools with "CD-SEM 장비에서만 제공됩니다" and never query anything. `fdc`
  is not gated, so an HV-SEM tool just matches 0 docs. `mdc` and `bm-pm` serve
  both tool types.
- **Failure styles.** Keep these two apart when you diagnose:
  - **Raise:** the whole tab shows a red "요청 실패: …" line. The adapter found
    a document it refuses to render. The message names the index, the tool and
    the field.
  - **Silent:** an empty chart, a missing metric or a blank cell. Usually a
    filter matched nothing, or a field has a different name, type or shape.
    Most "missing data" reports are this kind.
- **Size cap:** every OpenSearch pull is one request capped at 10,000 docs
  (BM/PM: 1,000 rows). Hitting the cap raises instead of truncating.

Notation below: `kw` means the term query uses the `.keyword` subfield (the
base field is assumed to be analyzed `text`). `bare` means it queries the
field directly (it is assumed to be `keyword` or `date`).

**About the "Expected sample" blocks.** Each section ends with what the code
expects to find in the database: a mapping excerpt and one `_source` document
for OpenSearch, or the raw value for Redis and MinIO.

- The samples are **built from what the code accepts, not copied from real
  data.** IPs, ids and note text are illustrative. Where a value's real
  spelling is unknown, the sample says `OFFICE-VERIFY`.
- `jsonc` blocks use `/* … */` comments to mark elided keys.
- The mapping excerpts list only the fields the code relies on.
- Put one real sample next to each block and diff them. That is the fastest
  way to find a `NAME`, `TYPE` or `VALUE` mismatch.

## 0. Tool roster — `sem_list` (shared by several tabs)

The Hardware page reads only three columns of this roster: `eqp_id` (the
tool selector), `eqp_ip` (used by sharpness and reso-center) and `fab_name`
(used by mdc history). The full schema is in `sem_list.txt`. This source has
been live at the office since 2026-07-20.

### Expected sample — `sem_list`

Redis holds pandas DataFrames serialized with `to_parquet()`. The raw bytes
start with `PAR1`.

```text
GET v3_df_sem_avail    -> b"PAR1..."   columns: fac_id, eqp_id, eqp_model_cd, eqp_grp_id,
                                                vendor_nm, eqp_ip, fab_name, updt_dt, available
GET v3_df_sem_version  -> b"PAR1..."   columns: eqp_ip, version
```

The two keys are LEFT-merged on `eqp_ip`. One row after the merge:

```json
{
  "fac_id": "M16",
  "eqp_id": "6MCDE305",
  "eqp_model_cd": "CG6300",
  "eqp_grp_id": "CDSEM_G1",
  "vendor_nm": "HITACHI",
  "eqp_ip": "10.0.12.41",
  "fab_name": "M16A",
  "updt_dt": "2021-03-04T00:00:00",
  "available": "On",
  "version": "7.20"
}
```

The rules the hardware tabs rely on:

- `eqp_id` is spelled exactly as in `network_fdc_cdsem`, `beam_shape_cdsem`
  and `fab_inform_notes` (the FDC match was confirmed 2026-07-23).
- `eqp_ip` is spelled exactly as in `sharpness_monitor_cdsem.ip` and
  `reso_center_cdsem.eqp_ip`: a bare dotted quad, no port.
- `fab_name` is uppercase and matches the Redis hash fields of
  `mdc_setting`/`sce_info` and the MinIO file names `{FAB}.json`.

## 1. FDC — OpenSearch `network_fdc_cdsem`

**Query:**

- `term eqp_id.keyword = <eqp_id>`
- `range timestamp gte start lte end`
- sorted by `timestamp` asc
- `_source` = the 7 fields below

**Not filtered by `fab_name`.** Mapping confirmed at the office 2026-07-23:
dynamic, so strings are `text` + `.keyword`, and `timestamp` is `date`.

| Field | Expected type | Used for | If wrong or missing |
| --- | --- | --- | --- |
| `eqp_id` | text+keyword, e.g. `6MCDE305` | filter (`kw`); each hit must equal the requested id | different spelling → 0 docs (silent); a hit for another tool → raise |
| `timestamp` | `date`, offset-less KST | range, sort, x-axis | empty → raise; `Z` → 9h slide |
| `fdc_key` | string, exactly one of `TemperatureEChuck`, `SPMVoltages`, `LaserPower`, `ContactpinConductionInfo` | sub-tab grouping; validation | any other value → **raise** (note the capital `C` in `EChuck`) |
| `values` | list; `values[0]` must equal `fdc_key` | parsed by position (see below) | not a non-empty list, or `values[0]` ≠ `fdc_key` → raise |
| `eqp_model_cd`, `fab_name`, `eqp_ip` | string | fetched, never read | — |

**`values[]` positions the frontend reads** (`frontend/app/utils/fdcValues.ts`).
Items arrive as strings and are parsed as numbers where needed.

- `TemperatureEChuck`
  - `[2]` = position `'1'`, `'2'` or `'3'`. There is one line per position.
  - `[3]` = temperature in °C.
- `LaserPower`
  - `[2]`,`[3]` = x1,y1 (about 0.8). `[4]`,`[5]` = x2,y2 (about 1e8).
  - A missing position becomes NaN, so points go missing.
- `SPMVoltages`
  - `[2]` = channel `A`, `B` or `C`.
  - The **first non-numeric token from `[3]` on** is the fit-model name
    (`spline`, `quartic`), not a verdict. Every number after it is the profile,
    always 107 points (office 확인 2026-09-28).
  - Docs more than 30 min apart start a new cycle.
- `ContactpinConductionInfo`
  - `[2]` = channel.
  - The first non-numeric token from `[3]` on is the judgment:
    `Conduction` (green), `UnstableConduction` (amber) or `NonConduction`
    (red) (office 확인 2026-09-28).
  - The first 4 numbers after the judgment are listed with their spread
    (max − min), the margin that separates the classes. The last number is a
    per-channel counter, shown as a rate per day.
  - The sample in `hardware_network_fdc_cdsem.txt` has `'25,0'`, with a comma.
    The parser reads a comma decimal as `25.0`, and keeps every number in its
    position, so an unreadable cell leaves a gap instead of shifting the
    counter. How often commas occur is still unknown (OFFICE-VERIFY).

### Expected sample — `network_fdc_cdsem`

Mapping excerpt. This one is office-confirmed: the index is dynamic-mapped.

```json
{
  "eqp_id":    { "type": "text", "fields": { "keyword": { "type": "keyword", "ignore_above": 256 } } },
  "fdc_key":   { "type": "text", "fields": { "keyword": { "type": "keyword", "ignore_above": 256 } } },
  "timestamp": { "type": "date" },
  "values":    { "type": "text", "fields": { "keyword": { "type": "keyword", "ignore_above": 256 } } }
}
```

One `_source` per `fdc_key`. Every item in `values` is a string.

```jsonc
{ "eqp_id": "6MCDE305", "eqp_model_cd": "CG6300", "fab_name": "M16A", "eqp_ip": "10.0.12.41",
  "fdc_key": "TemperatureEChuck", "timestamp": "2026-06-17T09:20:00",
  "values": ["TemperatureEChuck", "0", "1", "23.39053"] }

{ "fdc_key": "SPMVoltages", "timestamp": "2026-06-17T09:20:00", /* + the 4 identity fields */
  "values": ["SPMVoltages", "0", "B", "7", "1", "1", "spline", "-0.2", "0", "-0.4", "0.0", "-1.2" /* … ~100 numbers */] }

{ "fdc_key": "LaserPower", "timestamp": "2026-06-17T09:20:00",
  "values": ["LaserPower", "0", "0.78", "0.73", "341990938", "46504250"] }

{ "fdc_key": "ContactpinConductionInfo", "timestamp": "2026-06-17T09:20:00",
  "values": ["ContactpinConductionInfo", "0", "B", "3", "Conduction", "-5.0", "-5.0", "0.0", "5.0", "182671"] }
```

## 2. Sharpness — OpenSearch `sharpness_monitor_cdsem`

**Query:**

- `term ip = <eqp_ip>`, **bare**, because `ip` is explicitly mapped `keyword`
  (user-confirmed 2026-07-22)
- `range timestamp`, sorted by `timestamp` asc
- `_source` = the 8 fields below

The index has **no `eqp_id` or `fab_name`**. The IP comes from the sem_list
roster.

| Field | Expected type | Used for | If wrong or missing |
| --- | --- | --- | --- |
| `ip` | `keyword`, bare dotted quad | filter; must equal roster `eqp_ip` | port, hostname or zero-padding difference → 0 docs (silent); another IP in a hit → raise |
| `timestamp` | `date`, offset-less KST | range, sort, measurement identity | empty → raise |
| `os_inserted` | `date` | fetched, not used | — |
| `beam_condition` | **object** | `SEM_Cond_No` + `Vacc` build the condition selector | not an object, or either key missing → **raise** |
| `beam_condition.SEM_Cond_No` | number, or numeric string (coerced to int) | selector key `"{No}_{Vacc}"` | non-numeric → raise |
| `beam_condition.Vacc` | number or numeric string | compared as a number: default condition = first doc where `Vacc == 800`; `800`, `"800"` and `800.0` are one condition | non-numeric (e.g. `"800V"`) → its own button, and the default falls back to the first condition |
| `reso_eb`, `noise` | object keyed `"0.0"`…`"337.5"` (16 keys, step 22.5) | radar charts | empty or not an object → **raise**; a missing degree key → a gap in the radar |
| `reso_detector` | same shape | 0–360° line chart | same as above |
| `summ_beam` | object of floats: `Ellipticity`, `Major Axis`, `Minor Axis`, `Offset`, `Tilt`, `x_range`, `y_range` | trend dropdown; default `Ellipticity` | empty → raise; **only `docs[0]`'s keys are offered**, so a key that first appears in a later doc never shows |

Expected pairing: `SEM_Cond_No` 5 ↔ `Vacc` 500 and 6 ↔ 800. Report any other
pair you find. Other `beam_condition` sub-keys (`Vsup`, `Ip`, `Optics`, …) are
ignored by the page.

### Expected sample — `sharpness_monitor_cdsem`

Mapping excerpt, user-confirmed 2026-07-22 (explicit mapping, not dynamic).

```json
{
  "ip":             { "type": "keyword" },
  "timestamp":      { "type": "date" },
  "os_inserted":    { "type": "date" },
  "beam_condition": { "type": "object" },
  "reso_detector":  { "type": "object" },
  "noise":          { "type": "object" },
  "reso_eb":        { "type": "object" },
  "summ_beam":      { "type": "object" }
}
```

```jsonc
{
  "ip": "10.0.12.41",
  "timestamp": "2026-06-17T09:20:00",
  "os_inserted": "2026-06-17T09:31:12",
  "beam_condition": {
    "Serial_No": "OFFICE-VERIFY", "SEM_Cond_No": 6, "Vacc": 800, "Vsup": 1.80,
    "Ip": "OFFICE-VERIFY", "Optics": "OFFICE-VERIFY", "Detector": "OFFICE-VERIFY"
    /* … AL3_x_offset, AL3_y_offset and other keys, unread by the page */
  },
  "reso_detector": { "0.0": 0.0051, "22.5": 0.0049 /* … 16 keys, step 22.5, up to "337.5" */ },
  "noise":         { "0.0": 6.10,   "22.5": 6.12   /* … same 16 keys */ },
  "reso_eb":       { "0.0": 8.01,   "22.5": 7.98   /* … same 16 keys */ },
  "summ_beam": {
    "Ellipticity": 1.023, "Major Axis": 8.12, "Minor Axis": 7.94,
    "Offset": 0.31, "Tilt": -35.1, "x_range": 8.07, "y_range": 8.00
  }
}
```

The degree keys must be the strings `"0.0"`, `"22.5"` … `"337.5"`. A key
spelled `"0"` would be read as a different angle from `"0.0"`.

## 3. BSM (beam shape) — OpenSearch `beam_shape_cdsem`

**Query:**

- `type.keyword = "total"`
- `fdc_category.keyword = "bsi_beam_shape"`
- `eqp_id.keyword = <eqp_id>`
- `fab_name.keyword = <FAB>`, **uppercased** (e.g. `M16A`)
- `range timestamp` (formatted `YYYY-MM-DDTHH:MM:SS`), sorted asc

No `_source` projection. All four term fields are **assumed** `text+keyword`
(OFFICE-VERIFY). If any is a bare `keyword`, that term matches nothing and the
tab is empty.

**The adapter copies an explicit list of keys; every other key in the doc is
dropped.** A real metric whose name differs from this list, even by one
character, vanishes silently. `Ellipticity` was spelled `Ellipicity` here
until 2026-09-28 and was corrected on the user's word (user-confirmed).
`Apature` (not `Aperture`) is the real spelling, set by the fab tool
(user-confirmed 2026-09-28). Do not report it as a mismatch.

| Key | Expected source shape | Output | If wrong |
| --- | --- | --- | --- |
| `degree` | 16 numbers | angle labels | missing → falls back to 0…337.5 |
| `Reso EB`, `Reso Detector`, `Noise`, `Focus offset`, `Apature angle factor` | list of exactly 16 numbers (floats or numeric strings mixed) | radar metric | not exactly 16 clean numbers → **dropped** |
| `Reso EB Focus` | doubly nested `[[16 numbers]]` (flat is also accepted). Holds only the **last of the source CSV's 5 focus rows, the +10 focus row** (office 확인 2026-09-28) | radar metric | same as above |
| `Reso EB Focus Range` | one-element list `['8.0000']`: the focus value of the row kept in `Reso EB Focus` | unwrapped to a float trend metric | non-numeric → dropped |
| `Major Axis`, `Minor Axis`, `Ellipticity`, `Tilt`, `X range`, `Y range`, `Area`, `Ave. Reso Detector`, `Ave. Noise`, `Ave. Apature angle factor` | float or numeric string | trend metric | non-numeric → dropped |
| `beam_condition` | **string**, e.g. `HR0800_IP0080` (not an object, unlike sharpness) | condition filter; measurement id = `timestamp`+`beam_condition` | — |
| `category`, `type`, `fdc_category`, `timestamp`, `timestamp_date`, `eqp_ip`, `eqp_id`, `fac_id`, `fab_name` | string | passed through; `category` is shown as a badge | — |

Default charts: trend A `Ellipticity`, trend B `Ave. Noise`, radar A `Reso EB`,
radar B `Reso Detector`. If a default key is absent, the chart falls back to
the first available metric.

`Reso EB Focus Range` records **which** focus row was kept, not a focus-range
drift. If its trend moves, suspect a change in the ingestion rule, not the
tool. Keeping a different row is a one-line change on the office ingestion side.

### Expected sample — `beam_shape_cdsem`

Mapping excerpt. The `text+keyword` types are **assumed** (OFFICE-VERIFY).

```json
{
  "type":         { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
  "fdc_category": { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
  "eqp_id":       { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
  "fab_name":     { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
  "timestamp":    { "type": "date" }
}
```

The `_source` of a `type: "total"` document, as the adapter expects to
receive it. This is the source shape, before the adapter reshapes it:

```jsonc
{
  "category": "I-diff_hp",
  "type": "total",
  "fdc_category": "bsi_beam_shape",
  "beam_condition": "HR0800_IP0080",
  "timestamp": "2026-06-17T09:20:00",
  "timestamp_date": "2026-06-17",
  "eqp_id": "6MCDE305", "eqp_ip": "10.0.12.41", "fac_id": "M16", "fab_name": "M16A",

  "degree":        [0.0, 22.5 /* … 16 numbers, up to 337.5 */],
  "Reso EB":       [8.0668 /* … exactly 16 */],
  "Reso Detector": [0.005665, 0.005116 /* … exactly 16 */],
  "Noise":         [6.069593, "6.118456" /* … exactly 16; numeric strings are fine */],
  "Focus offset":  [4.6745, 7.53525 /* … exactly 16 */],
  "Apature angle factor": [0.00117, 0.001521 /* … exactly 16 */],
  "Reso EB Focus":        [["8.94623", "8.096161" /* … 16 inside ONE inner list */]],
  "Reso EB Focus Range":  ["8.0000"],

  "Major Axis": 8.124588, "Minor Axis": 7.941668, "Ellipticity": 1.023033,
  "Tilt": -35.09035, "X range": 8.06693, "Y range": 7.995835, "Area": 202.704313,
  "Ave. Reso Detector": 0.003042, "Ave. Noise": 6.27704, "Ave. Apature angle factor": 0.001214
}
```

Documents with `type: "index2"` (`RR00 Reso EB`, `RR90 Reso EB`) also live in
this index. The page does not read them.

## 4. Reso Center — OpenSearch `reso_center_cdsem`

The office alias was confirmed 2026-07-27. `reso_center_log` is the value of
the `category` field, **not** an index name.

**Query:**

- `term eqp_ip.keyword = <eqp_ip>` (IP comes from the roster)
- if a fab is given: `term fab_name.keyword = <FAB>` (uppercase)
- `range timestamp`, sorted asc
- `_source` = the 13 fields below

`.keyword` on `eqp_ip`/`fab_name` is **assumed**. Sharpness's `ip` is a bare
keyword, so this index may be too. Check the mapping.

| Field | Expected type | Used for | If wrong or missing |
| --- | --- | --- | --- |
| `eqp_ip` | text+keyword | filter; must equal the roster IP | another IP in a hit → raise; spelling difference → 0 docs |
| `fab_name` | text+keyword, uppercase | filter | lowercase stored, or `M16` instead of `M16A` → 0 docs (silent) |
| `timestamp` | `date`, offset-less KST | range, sort, x-axis | empty → raise |
| `timestamp_date` | string `YYYY-MM-DD` | passed through | filled from `timestamp` |
| `beam_condition` | string, e.g. `HR0500_IP0080` | the page always shows **one** condition (first in sorted order) | — |
| `CenterX`, `CenterY` | float or numeric string | scatter plot | a point needs both, so non-numeric or null skips it. **`CenterX` is corrupted in every doc written before 2026-09-28**: it holds the CenterXY magnitude, not the X offset (office 확인 2026-09-28). The adapter blanks `CenterX` when `timestamp` < `2026-09-28`, so those points are hidden |
| `BestReso`, `ResoIScenter` | float | two trend lines on one nm axis | same as above |
| `ResoData` | float, stored (`ResoIScenter − BestReso`, ≥ 0). Spelled `ResoData`, not `ResoDelta` (user-confirmed 2026-09-28) | tooltip; **never recomputed** | missing → `—` |
| `eqp_id`, `fac_id`, `category` | string | passed through | a missing `eqp_id` is filled from the request |

The index has **never** carried `Resolution_Range*`: the office ingestion
pops them before indexing (office 확인 2026-09-28; an earlier version of this
brief said otherwise). `fdc_category` is not fetched even if present.

### Expected sample — `reso_center_cdsem`

Mapping excerpt. The `.keyword` subfields are **assumed** (OFFICE-VERIFY).

```json
{
  "eqp_ip":    { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
  "fab_name":  { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
  "timestamp": { "type": "date" }
}
```

```json
{
  "category": "reso_center_log",
  "CenterX": 1.15,
  "CenterY": -0.99,
  "BestReso": 2.98,
  "ResoIScenter": 3.04,
  "ResoData": 0.06,
  "beam_condition": "HR0500_IP0080",
  "timestamp": "2026-04-20T12:55:16",
  "timestamp_date": "2026-04-20",
  "eqp_id": "6MCDE305",
  "eqp_ip": "10.0.12.41",
  "fac_id": "M16",
  "fab_name": "M16A"
}
```

## 5. BM/PM — OpenSearch `fab_inform_notes` + `tool_maintenance_plan`

Both are queried by `term eqp_id.keyword`. Neither is filtered by fab.

- **Past** (`fab_inform_notes`): `range down_dt` from `end − 180d` to `end`,
  sorted `down_dt desc`.
- **Future** (`tool_maintenance_plan`): `range tool_start_tm` from `end` to
  `end + 90d`, sorted asc.
- The cap is 1,000 rows per side.

Stored dates are parsed and then **reformatted** to `YYYY-MM-DD HH:MM` without
any timezone conversion. The frontend matches that exact string format against
chart x-values to place the BM/PM markers.

| Index.field | Expected type | Output column | If wrong or missing |
| --- | --- | --- | --- |
| `fab_inform_notes.eqp_id` | text+keyword | filter, `eqp_id` | another tool in a hit → raise |
| `.down_dt` | `date`, offset-less KST (office 확인 2026-08-20) | `job_starts`; range, sort | empty → **raise** |
| `.equp_dt` | `date` | `job_end` | empty = tool still down ("진행 중"), valid |
| `.hub_load_tm` | `date` | `timestamp` (Uploaded) | — |
| `.pm_type`, `.eq_event` | text | shown; also classify `category` | see note below |
| `.lot_id`, `.last_recipe_id` | text | shown | — |
| `.note_comment`, `.zzproblem`, `.hltext` | text (long, multi-line) | expandable notes; merged into `engr_note` for the marker tooltip | — |
| `tool_maintenance_plan.eqp_id` | text+keyword | filter | same as above |
| `.tool_start_tm` | `date` — **timezone still unverified** | `job_starts`; range, sort | empty → **raise**; `Z` stored → 9h slide |
| `.tool_end_tm` | `date` | `job_end` | — |
| `.chg_tm` | `date` | `timestamp` (Registered) | — |
| `.event_name`, `.work_item_nm` | text | shown; classify `category` | see note below |
| `.work_user_cd` | text | Worker | — |

**`category` classification.** The adapter looks for `PM` first, then `BM`, as
a case-insensitive substring:

- past rows check `pm_type`, then `eq_event`;
- future rows check `event_name`, then `work_item_nm`.

A row that matches neither gets an empty `category`. It still shows in the
table, but the chart overlay draws only rows whose category is exactly `BM`
or `PM`. So: **if real values spell BM/PM in Korean or with other codes,
every marker disappears.** List the distinct values you find.

Cards: `Last BM` = the newest past row with category BM. `Next PM` = the
soonest future row with category PM.

### Expected sample — `fab_inform_notes` / `tool_maintenance_plan`

Mapping excerpt, taken from `ops_index_mgmt/*.py` as described in
`hardware_bm_pm.txt`. The date fields are mapped explicitly; everything else
is dynamic `text+keyword`.

```json
{
  "fab_inform_notes": {
    "eqp_id":      { "type": "text", "fields": { "keyword": { "type": "keyword", "ignore_above": 256 } } },
    "down_dt":     { "type": "date" },
    "equp_dt":     { "type": "date" },
    "hub_load_tm": { "type": "date" }
  },
  "tool_maintenance_plan": {
    "eqp_id":        { "type": "text", "fields": { "keyword": { "type": "keyword", "ignore_above": 256 } } },
    "tool_start_tm": { "type": "date" },
    "tool_end_tm":   { "type": "date" },
    "chg_tm":        { "type": "date" }
  }
}
```

The category values below come from the mock and are **OFFICE-VERIFY**. What
matters is that `PM` or `BM` appears somewhere in one of the classifying
fields.

```jsonc
// fab_inform_notes — one maintenance that happened
{
  "aufnr": "OFFICE-VERIFY", "doc_id": "OFFICE-VERIFY",
  "eqp_id": "6MCDE305", "fab_name": "M16A", "fac_id": "M16",
  "down_dt": "2026-05-31T08:57:00",      // office 확인 2026-08-20: no offset
  "equp_dt": "2026-05-31T14:20:00",      // empty while the tool is still down
  "hub_load_tm": "2026-05-31T15:02:00",
  "pm_type": "PM2",                      // may be empty
  "eq_event": "PM_WEEKLY",
  "lot_id": "MONI0001", "last_recipe_id": "M16_CDMEAS_01",
  "note_comment": "free text, may contain newlines",
  "zzproblem": "free text", "hltext": "free text"
}

// tool_maintenance_plan — one planned maintenance
{
  "eqp_id": "6MCDE305", "det_fac_id": "M16A", "fac_id": "M16",
  "chg_tm": "2026-06-20T10:00:00",
  "tool_start_tm": "2026-06-25T09:00:00",  // timezone OFFICE-VERIFY
  "tool_end_tm": "2026-06-25T18:00:00",
  "event_name": "PM_QUARTER",
  "work_item_nm": "정기 PM — 컬럼 청소 및 정렬 확인",
  "work_user_cd": "OFFICE-VERIFY"
}
```

## 6. MDC — Redis hash `mdc_setting` + MinIO archive

**Snapshot** (the 비교 sub-tab):

- Command: `HGET mdc_setting <FAB>`, where the field is the page's
  `fab_name`, **uppercased**.
- The value is JSON (pickle is accepted as a fallback), shaped
  `{eqp_id: {beam_condition: value}}`.
  - Values are expected as strings near 1.0, e.g. `'1.004984'`. Numbers are
    turned into strings. Null, nested or list values are dropped.
  - The whole fab map is the comparison group: the selected tool plus its
    siblings.
- Missing field → empty, logged as a WARNING. MDC covers **every** fab
  including R3/R4, so an absent field is a collection failure.
- Missing key → raise.
- Redis holds the latest collection only. An older "as-of" date still shows
  today's values; that is a known gap.

**History** (the 시계열 sub-tab):

- The adapter walks the date folders under
  `hitachi_sem/cdsem/mdc_setting/YYYY/MM/DD/` (default bucket/prefix from
  `minio_handler/minio_config.py`) and keeps the ones inside the window.
- For each date it reads `{FAB}.json`, then `payload[eqp_id]`.
- `FAB` comes from the **sem_list roster's `fab_name` for that eqp_id**, not
  from the request.
- Each condition becomes one record
  `{timestamp: "YYYY-MM-DD 00:00", beam_condition, mdc_value: float}`.
  Non-numeric values are dropped.

**Condition key convention** (frontend `utils/mdcHistory.ts`):

- The suffix `_0Deg` or `_90Deg` sets the 0°/90° axis. The rest is the family,
  e.g. `800V_HR_0Deg` → family `800V_HR`.
- The default family is hard-coded `800V_HR`.
- A key without the suffix (e.g. `3000V`, `Valley`) goes on the 0° axis.
- 0°/90° points pair only on an **exact** timestamp match.

Check that the real keys follow `<voltage>_<mode>_<0|90>Deg`, and list the
ones that do not.

### Expected sample — `mdc_setting`

The Redis value is UTF-8 JSON bytes. Field names are uppercase `fab_name`.

```text
HKEYS mdc_setting        -> ["M16A", "M16B", "M15A", "R3", "R4", ...]   (every fab, R3/R4 included)
HGET  mdc_setting M16A   -> b'{"6MCDE305": {...}, "4CCD6701": {...}, ...}'
```

```json
{
  "4CCD6701": {
    "800V_HR_0Deg": "1.004984",
    "800V_HR_90Deg": "1.005625",
    "500V_HR_0Deg": "1.004096",
    "500V_HR_90Deg": "1.003888"
  },
  "6MCDE305": {
    "800V_HR_0Deg": "1.002110",
    "800V_HR_90Deg": "1.002870",
    "3000V": "0.998700"
  }
}
```

The MinIO archive holds the same JSON shape for every collection date:

```text
<default bucket>/<default prefix>/hitachi_sem/cdsem/mdc_setting/2026/07/24/M16A.json
```

The history sub-tab turns each (date, condition) pair into one record, for
example `{"timestamp": "2026-07-24 00:00", "beam_condition": "800V_HR_0Deg",
"mdc_value": 1.004984}`. If the archived JSON carries its own collection time,
report it as `EXTRA`. The code currently assumes the file has no time of day
and uses `00:00`.

## 7. SCE — Redis hash `sce_info` + MinIO archive

The same two-tier layout as MDC:

- Snapshot: `HGET sce_info <FAB>`.
- History: `hitachi_sem/cdsem/sce_info/YYYY/MM/DD/{FAB}.json`, where `FAB`
  comes from the request's `fab_name`.

**An empty result is valid here.** R3/R4 don't run SCE, and M10 had no data as
of 2026-07. A missing `sce_info` key raises.

Per-tool shape `settings[eqp_id]`:

| Block | Expected | Used for | If wrong |
| --- | --- | --- | --- |
| `SemCond` | dict, e.g. `SemCond_No`, `SemCond_Optics`, `SemCond_Vacc`, `SemCond_Ip`, `SemCond_IpMode`, `SemCond_Detector` | compare table (string compare vs siblings); numeric fields become trend options | not a dict → block dropped |
| `ImgCond` | dict of **lists**, e.g. `ImgCond_FocusOffset ['-2']`, `ImgCond_Mag`, `ImgCond_Pixel` | compare table (lists joined with `,`); trend uses `[0]` | same as above |
| `SCEParam` | dict of numeric strings, `SCEParam_*` | compare table; trend | same as above |
| `FileInfo` | dict of file paths | passed through, **ignored by the page** | — |
| `Coefficients` | list of `{index: 0..359, values: [v0, v1]}` (dict `{"0": [...]}` also accepted) | two curves (`v0` ≈ ±0.02, `v1` ≈ 0.9–1.0) + polar view | a bad index or non-list `values` → entry skipped; missing indices show as gaps |

- Trend labels strip the `SCEParam_`, `SemCond_` or `ImgCond_` prefix, so
  un-prefixed field names still work but read oddly.
- The revision view merges consecutive collections whose `Coefficients` are
  **exactly equal**. If every collection is its own revision ("중복 없음"),
  suspect float or serialization jitter in the writer.
- History docs are `{date: "YYYY-MM-DD", SemCond, ImgCond, SCEParam, Coefficients}`.

### Expected sample — `sce_info`

The Redis value is UTF-8 JSON bytes; pickle is accepted as a fallback. It has
no R3/R4 fields.

```text
HKEYS sce_info          -> ["M16A", "M16E", "M15A", ...]
HGET  sce_info M16A     -> b'{"6MCD1201": {...}, ...}'
MinIO                   -> .../hitachi_sem/cdsem/sce_info/2026/07/24/M16E.json   (same JSON shape)
```

```jsonc
{
  "6MCD1201": {
    "FileInfo": { "SharpCharFile": "/HITACHI/...", "BaseSharpCharFile": "/HITACHI/..." },
    "SemCond": {
      "SemCond_No": "6", "SemCond_Optics": "High Reso.", "SemCond_Vacc": "800",
      "SemCond_Ip": "8.0000", "SemCond_IpMode": "Middle", "SemCond_Detector": "SE+EF"
    },
    "ImgCond": {
      "ImgCond_FocusOffset": ["-2"],
      "ImgCond_Mag": ["150003298", "150003298"],
      "ImgCond_Pixel": ["1024", "1024"]
    },
    "SCEParam": {
      "SCEParam_CycleUpperTh": "6.000", "SCEParam_CycleLowerTh": "22.500000",
      "SCEParam_SmoothRadius": "7", "SCEParam_SmoothTheta": "7",
      "SCEParam_FitRangeSt": "40", "SCEParam_FitRangeEd": "79",
      "SCEParam_CorrCoefLimit": "0.20000"
    },
    "Coefficients": [
      { "index": 0, "values": [0.00884, 0.964293] },
      { "index": 1, "values": [0.000927, 0.972554] }
      /* … one entry per index, 0 to 359 */
    ]
  }
}
```

`hardware_sce_setting.txt` writes `Coefficients` as one dict with repeated
`index`/`values` keys. A JSON parser keeps only the last pair of such a
dict, so read it as shorthand for the list above. Report which shape the real
data uses.

## What a mismatch report should look like

One line per finding, grouped by tab. Use these kinds:

| Kind | Meaning |
| --- | --- |
| `MISSING` | the code reads a field, key or path that the real source does not have |
| `NAME` | the field exists under a different spelling or case |
| `TYPE` | a different type or shape (e.g. object vs string, nested list, not 16 long) |
| `MAPPING` | `text+keyword` vs bare `keyword` (or the reverse), so a term matches nothing |
| `VALUE` | a value convention differs: timezone offset, case, IP format, eqp_id format, BM/PM wording, condition-key suffix |
| `COVERAGE` | the shape is right but there are no documents for this tool, fab or window |
| `EXTRA` | the real source has a field the page never reads (informational only) |
| `ADAPTER-DRIFT` | the running `office.py` differs from `office_example.py` in a way that matters |

Format each line as:

```text
<tab> | <source>.<field> | <kind> | expected: … | actual: … | effect on page | evidence (query/command + sample value)
```

Mark each finding with the provenance convention of this folder: `office 확인
YYYY-MM-DD` if you verified it against real data today, `OFFICE-VERIFY` if it
is still a guess. The facts you confirm are then recorded in the matching
`hardware_*.txt` file and the tab's `mock.py`.
