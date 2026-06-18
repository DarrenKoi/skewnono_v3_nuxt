# Hardware raw-doc mocks + hardware-page UI/UX

Date: 2026-06-19
Status: Approved (pending spec review)
Feature folder: `back_dev_home/ebeam/hitachi/hardware/`

## 1. Goal

Mock five OpenSearch-sourced hardware datasets in the Flask backend in their
**final retrieved form** (the shape after OpenSearch → `json` / `pd.DataFrame.to_dict`),
and rebuild/extend the **hardware page** to render them. These power the hardware
page now and will be **deep-linked from skewvoir** later (§4): when an engineer
doubts a measurement, a skewvoir button opens the hardware page scoped to that
tool and the time window around the measurement, so they can judge the
**hardware condition / credibility** behind the data.

Sources (one sample doc each in `docs/datatables/*.txt`; production has many docs
per tool, sampled continuously):

| source txt | service key | nature |
| --- | --- | --- |
| `beam_shape.txt` | `bsm` | per-eqp time-series of 360° beam-shape docs (type `total` only) |
| `reso_center_data.txt` | `reso-center` | per-eqp time-series of resolution-center docs |
| `network_fdc_cdsem.txt` | `fdc` | per-eqp time-series of FDC docs, one per `fdc_key` |
| `mdc_setting.txt` | `mdc` | fleet dict-of-dict `{eqp_id: {beam_cond: value}}`, as-of snapshot |
| `sce_setting.txt` | `sce` | fleet dict-of-dict `{eqp_id: {SemCond, ImgCond, SCEParam, Coefficients}}`, as-of |

## 2. Decisions (resolved during brainstorming)

1. **Fidelity:** faithful raw docs — every field preserved, including the metadata
   tail (`timestamp`, `timestamp_date`, `eqp_ip`, `eqp_id`, `fac_id`, `fab_name`,
   `fdc_category`) and source spellings (`Ellipicity`, `Apature angle factor`).
2. **URL (equipment-first):**
   `/<tool_slug>/hardware/<eqp_id>/<service>?fab_name=<fab_name>&start=<iso>&end=<iso>`
   - `eqp_id` → required path segment (the entity).
   - `fab_name` → query (office indices are fab-partitioned; also the key for the
     mdc/sce in-fab sibling set).
   - `start`/`end` → query, ISO 8601; default window = **last 30 days**.
3. **mdc / sce** return the requested eqp **plus its in-fab siblings**
   (dict-of-dict keyed by `eqp_id`), at the **as-of** date from `end`
   (snapshot effective at/just-before `end`; default latest). MinIO keeps mdc by
   date, so as-of is historically meaningful.
4. **Route migration:** all hardware services (`bsm`, `fdc`, `bm-pm`, new
   `reso-center`, `mdc`, `sce`) move to the new path — one routing surface.
5. **`fabId` → `fabName` rename**, end-to-end (the old `fab_id` key always carried
   a `fab_name` value, e.g. `"M16B"`).
6. **BSM rebuild:** keep the UX shell (filter → time-series → 360° radars, all
   timestamp-synced, + CSV export) but rebind every axis to the faithful
   beam_shape doc. **Drop `type: index2`** (uncertain engineering use) — handle
   `type: total` only. See §7.1.
7. **Hardware page UI/UX is in scope** this round (all five panels), before skewvoir.

## 3. API URL contract

```text
GET /<tool_slug>/hardware/<eqp_id>/<service>?fab_name=<fab_name>&start=<iso>&end=<iso>

tool_slug : cdsem | hvsem
eqp_id    : required path segment (e.g. ECXDX1234)
service   : bsm | reso-center | fdc | mdc | sce | bm-pm
fab_name  : query (scope hint; required for mdc/sce siblings)
start,end : query, ISO 8601; default window = last 30 days
            mdc/sce treat `end` as an as-of date and ignore `start`
```

`tool_slug` invalid → 400. `service` invalid → 400. `bsm` / `reso-center` / `sce`
are CD-SEM-only → an `available: false` payload for `hvsem`.

## 4. Deep-link contract (frontend page) + scope split

The skewvoir → hardware integration is the credibility loop. The deep link points
at the hardware **page route** (not the API):

```text
/ebeam/cd-sem/<fab>/hardware?eqp_id=<eqp>&start=<iso>&end=<iso>
```

- `eqp_id` → the page pre-selects that tool (instead of defaulting to first row).
- `start`/`end` → sets the page time window; flows into every API call.
- Lands on the **default panel** (no `service` param this round).

**In scope now:** the hardware page *reads* these query params (pre-select tool,
set window) so it is deep-link-ready. **Future (out of scope):** the skewvoir
button that builds the link, and the skewvoir combination view.

## 5. Canonical payload (contract additions)

`HardwarePayload` keeps its envelope (`tool_slug`, `service`, `eqp_id`,
`fab_name`, `available`, `fetched_at`, `summary`, `cards`, `tables`) and gains two
optional faithful-data fields:

```python
class HardwarePayload(TypedDict):
    ...
    docs: NotRequired[list[dict]]          # NEW — beam_shape / reso_center / fdc raw docs
    settings: NotRequired[dict[str, dict]] # NEW — mdc / sce dict-of-dict (eqp + siblings)
    raw: NotRequired[dict]
```

- `bsm` / `reso-center` / `fdc` → `docs` (faithful list, ascending time) + thin
  `cards` (doc count, latest timestamp).
- `mdc` / `sce` → `settings` (dict-of-dict, eqp + siblings) + thin `cards`
  (as-of date, sibling count).
- The old simplified `bsm` block (`angles`/`categories`/`sharpness`/`noise`) and
  `BsmBlock` type are **removed**; the BSM panel reads `docs` directly (§7.1).

## 6. Faithful doc shapes

### 6.1 `bsm` — beam_shape, `type: "total"` only (CD-SEM)

Time-series of docs across `[start, end]`. Each `total` doc:

- per-degree 16-arrays: `Reso EB`, `Reso Detector`, `Noise`, `Focus offset`,
  `Apature angle factor`, `Reso EB Focus` (list-of-16); `degree` (16: 0…337.5);
  `Reso EB Focus Range` (list).
- scalars: `Major Axis`, `Minor Axis`, `Ellipicity`, `Tilt`, `X range`,
  `Y range`, `Area`, `Ave. Reso Detector`, `Ave. Noise`,
  `Ave. Apature angle factor`.
- `category`, `beam_condition` (e.g. `HR0800_IP0080`),
  `fdc_category: "bsi_beam_shape"`, `type: "total"`, metadata tail.

**Rule:** every per-degree array is exactly length 16; never emit a short array
(lost credibility per source note).

### 6.2 `reso-center` — reso_center_data (CD-SEM)

Time-series of `category: "reso_center_log"` docs: scalars `CenterX`, `CenterY`,
`BestReso`, `ResoIScenter`, `ResoDelta`; `Resolution_Range`
(`['-10','-5','0','5','10']`); `Resolution_Range_Raw` and
`Resolution_Range_Smooth` (dict keyed by those 5 offsets, each → 5 numbers);
`beam_condition`, `fdc_category == category`, metadata tail.

### 6.3 `fdc` — network_fdc_cdsem

Time-series; **one doc = one `eqp_id` + one `timestamp` + one `values` list**
(one `fdc_key`). Fields: `eqp_id`, `eqp_model_cd`, `fab_name`, `eqp_ip`,
`fdc_key`, `timestamp`, `values`. `values` starts with `fdc_key`, then:

- `TemperatureEchuck` → `[key, '0', position(1/2/3), temp]`; 3 positions sampled
  periodically, each its own doc/timestamp.
- `SPMVoltages` → `[key, '0', A/B/C, n, n, n, judgment(spline|quartic), …~100 nums]`.
- `LaserPower` → `[key, '0', x1, y1, x2, y2]` (two pairs, different scales).
- `ContactpinConductionInfo` → `[key, '0', A/B/C, n,
  judgment(Conduction|NotConduction), …5 nums]`.

### 6.4 `mdc` — mdc_setting (fleet, as-of)

`{ eqp_id: { beam_condition: value } }` for the requested eqp + in-fab siblings,
at the as-of date. Beam conditions vary per eqp (`800V_HR_0Deg`, `500V_HR_90Deg`,
some tools `3000V` / `Valley`). Values are correction factors (`result = MDC × raw`).

### 6.5 `sce` — sce_setting (fleet, CD-SEM M-fab, as-of)

`{ eqp_id: { FileInfo, SemCond{No,Optics,Vacc,Ip,IpMode,Detector},
ImgCond{FocusOffset[],Mag[],Pixel[]}, SCEParam{7 thresholds},
Coefficients[{index, values:[2 floats]} × 360] } }` for eqp + in-fab siblings.
Indices 0…359. R3/R4 don't use SCE; emit for any CD-SEM eqp (mock) but `summary`
notes M-fab usage.

## 7. Hardware page UI/UX

Each panel is comparison / credibility oriented (the trait skewvoir reuses).

### 7.1 `bsm` — beam explorer (rebuild, keep the shell)

Data-driven from `docs`. Filter row: `beam_condition`. Layout keeps today's
shape — time-series on top, dual 360° radars below, timestamp-synchronized, CSV
export — but axes are now selectable:

```text
filter: [ beam_condition ▾ ]
── Time-series (two stacked panes, each a scalar dropdown) ──
   pane A: [ Ellipicity ▾ ]   pane B: [ Ave. Noise ▾ ]   click point → select meas
── 360° radars (selected measurement) ──
   Radar [ Reso EB ▾ ]        Radar [ Reso Detector ▾ ]
── header cards: scalars of the selected measurement ──
```

**Data-driven selectors (no per-key frontend edits):** the radar dropdown lists
every doc key whose value is a length-16 numeric array; the time-series dropdowns
list every numeric scalar key. Radar radial range is auto-derived from the windowed
data (padded). Adding a future key to the mock therefore appears in the UI with no
frontend change. A small label map prettifies known keys; unknown keys show raw.

### 7.2 `reso-center`

Filter: `beam_condition`. Center-drift scatter (`CenterX` vs `CenterY`, latest
emphasized) + trend of `BestReso` / `ResoDelta` over time (click → select) + a
focus-sweep curve for the selected measurement (`Resolution_Range` −10…10 →
`Raw` vs `Smooth` overlaid).

### 7.3 `fdc` — `fdc_key` sub-tabs (structurally different per key)

- `TemperatureEchuck` → 3-position temperature trend (pos 1/2/3 over time).
- `LaserPower` → x/y trend, dual-axis (the two scales differ).
- `SPMVoltages` → ~100-point profile curve per A/B/C + judgment
  (`spline`/`quartic`) badge, timestamp-selectable.
- `ContactpinConductionInfo` → status table: timestamp · A/B/C · Conduction badge
  · the 5 values.

### 7.4 `mdc` — skew matrix

Comparison matrix from `settings`: rows = tools (selected eqp + siblings), columns
= `beam_condition`, cells = MDC value, **color-scaled by deviation from the
selected tool**. Surfaces tool-to-tool skew at a glance. Header card: as-of date.

### 7.5 `sce`

Settings-compare table (`SemCond` / `ImgCond` / `SCEParam`: selected vs siblings,
diffs flagged) + the `Coefficients[0..359]` curve (two series for `values[0/1]`,
selected vs sibling overlay).

## 8. Module layout

```text
back_dev_home/ebeam/hitachi/hardware/
  contracts.py                 # + docs / settings; fab_id → fab_name; drop BsmBlock
  routes.py                    # new path <eqp_id>/<service>; parse fab_name/start/end
  normalizers.py               # + docs_payload(), settings_payload(); rename fab_name
  data.py                      # dispatch unchanged (swap surface)
  metrics.py                   # NEW — beam_shape metric registry (key, kind, range)
  providers/
    mock.py                    # dispatch all services
    office.py                  # stubs for new services
    bsm_mock.py                # KEEP UNTOUCHED — pm_planning's BM/PM-gate source
    beam_shape_mock.py         # NEW — faithful total docs for the hardware bsm panel
    reso_center_mock.py        # NEW
    fdc_mock.py                # NEW
    mdc_mock.py                # NEW — eqp + in-fab siblings, as-of
    sce_mock.py                # NEW — eqp + in-fab siblings, as-of
```

**`bsm_mock.py` stays** — `pm_planning/data.py` imports `build_bsm_data` for its
BM/PM Up gate (simplified sharpness/noise vs `spec_range_mock`). The hardware `bsm`
service switches to `beam_shape_mock.py`; the two BSM representations coexist by
design (reconciliation deferred to a future round). The beam_shape metric registry
(`metrics.py`) is the one place a new per-degree / scalar key is declared; the mock
fabricates from it, and the frontend reads keys straight off the docs (§7.1).

## 9. Determinism & volume

Mirror existing conventions: deterministic `random.Random` seeded from
`md5(eqp_id)`; anchor `NOW = 2026-05-24 09:00`; `pd.DataFrame.to_dict` where a
tabular intermediate is natural. In-fab siblings: a handful of stable same-prefix
eqp_ids within the given `fab_name`. Cadence: beam_shape / reso_center at
BM/PM-style density; fdc temperature every few hours, A/B/C variants clustered in
time; mdc/sce a single as-of snapshot.

## 10. Frontend changes

- `useHardwareApi.ts`: add `reso-center | mdc | sce` to `HardwareServiceKey`;
  build `/${slug}/hardware/${eqpId}/${service}`; `fabId` → `fabName`
  (key `fab_name`); add `start`/`end`; add `docs` / `settings` to payload; drop
  `BsmBlock`/`BsmSummaryRow`/`BsmProfile`.
- `HardwareView.vue`: call site `fabId:` → `fabName:`; read deep-link query params
  (`eqp_id`, `start`, `end`) to pre-select tool + set window.
- BSM components reworked to the data-driven explorer (§7.1); new panel components
  for `reso-center`, `fdc`, `mdc`, `sce`.

## 11. Scope & out of scope

**In scope:** backend mocks for all five sources + the hardware-page UI/UX
(five panels) + deep-link param handling on the hardware page.

**Out of scope:** skewvoir frontend / button / combination view (reuses these
endpoints later); real office/OpenSearch wiring (`providers/office.py` stays stub).

## 12. Blast radius

Touched: `contracts.py` (remove `BsmBlock`/`BsmSummaryRow`/`BsmProfile` + `bsm`
field; add `docs`/`settings`; rename `fab_name`), `routes.py`, `normalizers.py`
(remove `bsm_payload`; add `docs_payload`/`settings_payload`), `data.py`,
`providers/mock.py`, `providers/office.py`, new `metrics.py` + five new `*_mock.py`;
`useHardwareApi.ts`, `HardwareView.vue`, BSM components, four new panel components.

**Left untouched:** `providers/bsm_mock.py` and `pm_planning/data.py` —
pm_planning imports `build_bsm_data` directly and must keep working. The removed
`BsmBlock`/`bsm_payload` types are safe to drop: pm_planning consumes
`build_bsm_data`'s raw dict, not those TypedDicts. No tests reference the hardware
route; no skewvoir backend exists yet.

## 13. Open assumptions (veto on review)

- Default time window = last 30 days when `start`/`end` omitted. — confirmed
- BSM selectors are data-driven off doc keys (length-16 array → radar; scalar →
  trend); radar range auto-derived. — §7.1
- Thin summary `cards` per service; `tables` left empty except where a panel is
  inherently tabular (mdc matrix, sce settings, fdc contactpin).
- In-fab siblings count ≈ 3–5 (stable, seeded).
