# Hardware raw-doc mocks (beam_shape · reso_center · fdc · mdc · sce)

Date: 2026-06-19
Status: Approved (pending spec review)
Feature folder: `back_dev_home/ebeam/hitachi/hardware/`

## 1. Goal

Mock five OpenSearch-sourced hardware datasets in the Flask backend, in their
**final retrieved form** (the shape after OpenSearch → `json` / `pd.DataFrame.to_dict`).
These power the **hardware page** today and will be **combined in the skewvoir
page** later — because every doc carries a timestamp, the skewvoir view can use
them to judge the **credibility / hardware condition** behind a measurement.

The five sources (one sample doc each lives in `docs/datatables/*.txt`; production
has many docs per tool, sampled continuously):

| source txt | service key | nature |
| --- | --- | --- |
| `beam_shape.txt` | `bsm` | per-eqp time-series of radar (16-point / 360°) beam-shape docs |
| `reso_center_data.txt` | `reso-center` | per-eqp time-series of resolution-center docs |
| `network_fdc_cdsem.txt` | `fdc` | per-eqp time-series of FDC docs, one per `fdc_key` |
| `mdc_setting.txt` | `mdc` | fleet dict-of-dict `{eqp_id: {beam_cond: value}}` (latest snapshot) |
| `sce_setting.txt` | `sce` | fleet dict-of-dict `{eqp_id: {SemCond, ImgCond, SCEParam, Coefficients}}` |

## 2. Decisions (resolved during brainstorming)

1. **Fidelity:** faithful raw docs — preserve every field, including the metadata
   tail (`timestamp`, `timestamp_date`, `eqp_ip`, `eqp_id`, `fac_id`, `fab_name`,
   `fdc_category`) and source spellings (`Ellipicity`, `Apature angle factor`).
2. **URL shape (equipment-first):**
   `/<tool_slug>/hardware/<eqp_id>/<service>?fab_name=<fab_name>&start=<iso>&end=<iso>`
   - `eqp_id` → path segment (the entity; now **required**).
   - `fab_name` → query param (scope hint; office indices are fab-partitioned, so
     this lets the office provider target the right index without a reverse
     lookup; also the key for the mdc/sce in-fab sibling set).
   - `start`/`end` → query params (ISO 8601 time window; default = last 30 days).
3. **mdc / sce** return the requested eqp **plus its in-fab siblings**
   (dict-of-dict keyed by `eqp_id`). `start`/`end` are accepted but ignored
   (latest snapshot).
4. **Route migration:** all hardware services (`bsm`, `fdc`, `bm-pm`, plus the new
   `reso-center`, `mdc`, `sce`) move to the new path — one routing surface.
5. **`fabId` → `fabName` rename**, end-to-end, so the value (`fab_name`, e.g.
   `"M16B"`) and every name holding it agree. The old `fab_id` query key was a
   misnomer (it always carried a `fab_name`).
6. **BSM preservation (locked assumption):** the existing `bsm` canonical block
   (`angles` + `categories` with `sharpness`/`noise`/radar profiles) stays so
   `BsmPanel`/`BsmRadarChart`/`BsmTrendChart` keep working untouched; the faithful
   beam_shape docs attach **additively** in the payload. No chart rewrite now.

## 3. URL contract

```text
GET /<tool_slug>/hardware/<eqp_id>/<service>?fab_name=<fab_name>&start=<iso>&end=<iso>

tool_slug : cdsem | hvsem
eqp_id    : required path segment (e.g. ECXDX1234)
service   : bsm | reso-center | fdc | mdc | sce | bm-pm
fab_name  : query, e.g. M16B (scope hint; required for mdc/sce siblings)
start,end : query, ISO 8601; default window = last 30 days; ignored by mdc/sce
```

`tool_slug` invalid → 400. `service` invalid → 400. `bsm`/`reso-center`/`sce`
are CD-SEM-only → an `available: false` payload for `hvsem`.

## 4. Canonical payload (contract additions)

`HardwarePayload` keeps its envelope (`tool_slug`, `service`, `eqp_id`,
`fab_name`, `available`, `fetched_at`, `summary`, `cards`, `tables`) and gains two
optional faithful-data fields:

```python
class HardwarePayload(TypedDict):
    ...
    bsm: NotRequired[BsmBlock]              # existing, preserved
    docs: NotRequired[list[dict]]          # NEW — beam_shape / reso_center / fdc raw docs
    settings: NotRequired[dict[str, dict]] # NEW — mdc / sce dict-of-dict (eqp + siblings)
    raw: NotRequired[dict]
```

- `bsm` payload: `cards` (count/latest) + preserved `bsm` block + `docs` (faithful
  beam_shape `total` & `index2` docs).
- `reso-center` / `fdc` payload: `docs` (faithful list) + thin `cards`
  (doc count, latest timestamp).
- `mdc` / `sce` payload: `settings` (dict-of-dict) + thin `cards` (sibling count).

## 5. Faithful doc shapes

### 5.1 `bsm` — beam_shape (CD-SEM only)

Time-series of docs across `[start, end]`. Two `type`s emitted per measurement:

- `type: "total"` — `category`, `Reso EB Focus Range` (list), `Reso EB Focus`
  (list of 16-lists), `degree` (16: 0…337.5), `Reso Detector` (16), `Noise` (16),
  `Reso EB` (16), `Focus offset` (16), `Apature angle factor` (16), scalars
  `Major Axis`, `Minor Axis`, `Ellipicity`, `Tilt`, `X range`, `Y range`, `Area`,
  `Ave. Reso Detector`, `Ave. Noise`, `Ave. Apature angle factor`,
  `beam_condition` (e.g. `HR0800_IP0080`), `fdc_category: "bsi_beam_shape"`,
  metadata tail.
- `type: "index2"` — `degree`, `Reso EB` (16), `RR00 Reso EB` (16),
  `RR90 Reso EB` (16), `beam_condition`, metadata tail.

**Rule:** every numeric array is exactly length 16; never emit a short array (lost
credibility per source note).

### 5.2 `reso-center` — reso_center_data (CD-SEM only)

Time-series of `category: "reso_center_log"` docs: scalars `CenterX`, `CenterY`,
`BestReso`, `ResoIScenter`, `ResoDelta`; `Resolution_Range`
(`['-10','-5','0','5','10']`); `Resolution_Range_Raw` and
`Resolution_Range_Smooth` (dict keyed by those 5 offsets, each → 5 numbers);
`beam_condition` (e.g. `HR0500_IP0080`), `fdc_category == category`, metadata tail.

### 5.3 `fdc` — network_fdc_cdsem

Time-series of docs; **one doc = one `eqp_id` + one `timestamp` + one `values`
list** (one `fdc_key`). Fields: `eqp_id`, `eqp_model_cd`, `fab_name`, `eqp_ip`,
`fdc_key`, `timestamp`, `values`. `values` starts with the `fdc_key`, then:

- `TemperatureEchuck` — `[key, '0', position(1/2/3), temp]`; 3 positions sampled
  periodically, each its own doc/timestamp.
- `SPMVoltages` — `[key, '0', A/B/C, n, n, n, judgment(spline|quartic), …~100 nums]`.
- `LaserPower` — `[key, '0', x1, y1, x2, y2]` (two pairs, different scales).
- `ContactpinConductionInfo` — `[key, '0', A/B/C, n, judgment(Conduction|NotConduction),
  …5 nums]`.

A/B/C variants are sampled close together in time.

### 5.4 `mdc` — mdc_setting (fleet, latest snapshot)

`{ eqp_id: { beam_condition: value_str } }` for the requested eqp + in-fab
siblings. Beam conditions vary per eqp (`800V_HR_0Deg`, `500V_HR_90Deg`, and some
tools `3000V`/`Valley`). Values are correction factors (`result = MDC × raw`).

### 5.5 `sce` — sce_setting (fleet, CD-SEM M-fab)

`{ eqp_id: { FileInfo, SemCond{No,Optics,Vacc,Ip,IpMode,Detector},
ImgCond{FocusOffset[],Mag[],Pixel[]}, SCEParam{7 thresholds},
Coefficients[{index, values:[2 floats]} × 360] } }` for eqp + in-fab siblings.
Indices 0…359. R3/R4 don't use SCE; emit anyway for any CD-SEM eqp (mock), but the
`summary` notes M-fab usage.

## 6. Module layout

```text
back_dev_home/ebeam/hitachi/hardware/
  contracts.py                 # + docs / settings fields; fab_id → fab_name
  routes.py                    # new path <eqp_id>/<service>; parse fab_name/start/end
  normalizers.py               # + docs_payload(), settings_payload(); rename fab_name
  data.py                      # dispatch unchanged (swap surface)
  providers/
    mock.py                    # dispatch new services
    office.py                  # stubs for new services (return unavailable)
    bsm_mock.py                # existing block kept; add faithful beam_shape docs
    beam_shape_mock.py         # NEW — faithful total/index2 docs
    reso_center_mock.py        # NEW
    fdc_mock.py                # NEW
    mdc_mock.py                # NEW — eqp + in-fab siblings
    sce_mock.py                # NEW — eqp + in-fab siblings
```

Conventions (mirror existing `bsm_mock.py`): deterministic `random.Random` seeded
from `md5(eqp_id)`; anchor `NOW = 2026-05-24 09:00`; emit `pd.DataFrame.to_dict`
where a tabular intermediate is natural. In-fab siblings: pick a handful of
plausible same-prefix eqp_ids in the given `fab_name`, seeded for stability.

## 7. Frontend changes (keep the app working)

- `useHardwareApi.ts`: add `reso-center | mdc | sce` to `HardwareServiceKey`;
  build the new path (`/${slug}/hardware/${eqpId}/${service}`); `fabId` → `fabName`
  (query key `fab_name`); add `start`/`end`; add `docs` / `settings` to
  `HardwarePayload`.
- `HardwareView.vue:163-168`: call site `fabId:` → `fabName:`.
- `stores/navigation.ts` value semantics unchanged (`fab` already holds a
  `fab_name`).

## 8. Out of scope

- Skewvoir frontend / combination view (future; reuses these endpoints).
- Real office/OpenSearch wiring (`providers/office.py` stays a stub).
- BSM radar/trend chart rewrite (preserved as-is).

## 9. Blast radius

Touched: `contracts.py`, `routes.py`, `normalizers.py`, `providers/mock.py`,
`providers/office.py`, `providers/bsm_mock.py`, 5 new `*_mock.py`,
`useHardwareApi.ts`, `HardwareView.vue`. No tests reference the hardware route; no
skewvoir backend exists yet.

## 10. Open assumptions (veto on review)

- BSM preserve+add (no chart rewrite). — §2.6
- Default time window = last 30 days when `start`/`end` omitted.
- Thin summary `cards` added per service (cheap), `tables` left empty for raw
  services (the frontend renders `docs`/`settings` directly later).
