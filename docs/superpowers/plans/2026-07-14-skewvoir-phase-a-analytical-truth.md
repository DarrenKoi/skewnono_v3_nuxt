# Skewvoir Phase 0 + Phase A — Full MSR Mock & Analytical Truth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the `msr_file` mock up to the full `msr_file_pickle.txt` spec (Phase 0), then make every Skewvoir number derive from the same validated rows and the same tested statistics functions (Phase A).

**Architecture:** The pickle spec says `cd_value` is **nullable**. The current mock instead fabricates a `cd_value` for `mp_number = -1` rows — points that by definition have no measurement — and those junk values silently contaminate every mean, σ, 3Σ column and anomaly verdict in the app. Phase 0 fixes this at the source: `cd_value: float | None`, null exactly when `mp_number < 0`. That single type change makes the invalid row *structurally unmeasurable* and forces the TypeScript compiler to enumerate every consumer that was quietly reading junk. Phase A then routes all of those consumers through one validity gate and one statistics module.

**Tech Stack:** Flask + pytest (backend); Nuxt 4 / Vue 3 / TypeScript + ECharts (frontend). Frontend tests use Node's built-in runner (`node --test`) with `node:assert/strict` — **there is no vitest in this repo.**

## Global Constraints

- **Layout must not change.** No panel is added, removed or restructured in Phase 0 or Phase A. Values on screen *will* change — that is the deliverable. The Dashboard / pages 2–5 redesign is **Phase B** and is out of scope.
- **Determinism is non-negotiable.** Every new field must derive from the existing `md5(msr)` seed (`_seed()`), so the same MSR always opens to identical data with no DB. Never call bare `random.random()` outside a seeded `random.Random` instance.
- **Tests only ever live in `app/utils/*.test.ts`.** This repo has 22 test files and every one tests a pure util. Do not test `.vue` components or composables. If math needs a test, it must first move into `app/utils/`.
- **Frontend test command:** `npm --prefix front-dev-home test`. Import sibling modules with an explicit `.ts` extension (see `boxplotStats.test.ts`).
- **`utils/boxplotStats.ts` keeps true-extreme whiskers.** Its header records a deliberate decision: MDC fleet boxplots cover 4–6 tools, so IQR fencing would hide real tools. Do not add fencing to `boxStats`. CD site distributions get fencing from a *separate* function.
- **One definition of "outlier."** The leave-one-out peer model in `app/utils/anomaly/` is authoritative. Do not add a competing IQR-based outlier verdict. IQR fences are for *whisker rendering only*.
- **`status` and `severity` stay separate axes** (`anomaly/types.ts`) — "did detection run?" is not "how abnormal is it?".
- **Do not surface `MsrFileResponse.health` in the UI.** It is the mock generator's hidden bias scalar and will not exist in the office backend.
- **Two Python-keyword renames.** The pickle's `class` and `object` columns cannot be TypedDict fields under those names (`class` is a keyword; `object` shadows the builtin). Wire names stay **`class_name`** and **`object_type`**, matching what the frontend already consumes. Document the mapping in the module docstring.
- Verification gates: `python -m pytest -q`, `npm --prefix front-dev-home test`, `npm --prefix front-dev-home run typecheck`, `npm --prefix front-dev-home run lint`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `back_dev_home/msr_file/data.py` (modify) | Mock generator. Gains the missing pickle columns, `exe_detail_info`, `alignment`, `spm_dict`; `cd_value` becomes nullable; `_summaries()` gates invalid rows and switches to sample σ. |
| `tests/test_msr_file.py` (create/modify) | pytest coverage for the new schema and the corrected summaries. |
| `front-dev-home/app/composables/useMsrFileApi.ts` (modify) | Types mirror the new response. `cd_value: number \| null`. |
| `front-dev-home/app/utils/msrRows.ts` (create) | The one place the row-validity rule is written down. |
| `front-dev-home/app/utils/msrRows.test.ts` (create) | Tests for the gate. |
| `front-dev-home/app/utils/stats.ts` (create) | Pure statistics: mean, sample σ, quantiles, IQR fences, Pearson, Spearman, linear fit. |
| `front-dev-home/app/utils/stats.test.ts` (create) | Tests for the statistics. |
| `front-dev-home/app/utils/boxplotStats.ts` (modify) | Imports `quantileSorted` from `stats.ts` instead of defining it. Behaviour unchanged. |
| `front-dev-home/app/utils/anomaly/site.ts` (create) | Thin adapter running the existing `peerVerdicts` over site-level CD values. |
| `front-dev-home/app/utils/anomaly/site.test.ts` (create) | Tests for the adapter. |
| Components (modify) | `DistributionChart.vue`, `CorrelationScatter.vue`, `SequenceTrend.vue`, `FdcAnalysis.vue`, `WaferMap.vue`, `RadiusChart.vue`, `views/PositionStack.vue`, `views/Gallery.vue`, `dashboard/*.vue` — consume the gate; delete inline math. |

---

# Phase 0 — Bring the mock up to spec

### Task 1: Regenerate the MSR mock from `msr_file_pickle.txt`

**Why:** `back_dev_home/msr_file/data.py` cites the pickle spec in its docstring but implements roughly half of it. Missing: nullable `cd_value`, `meas_condition_{mag,vac,pixel}`, `addressing1_score`, `addressing2_score`, `meas_kind`, and the `exe_detail_info` / `alignment` / `spm_dict` structures entirely. The nullable `cd_value` is the load-bearing one — `data.py:297` currently assigns a real CD to every row including `mp_number = -1`, so ~5% of every average in the app is junk.

**Files:**
- Modify: `back_dev_home/msr_file/data.py`
- Test: `tests/test_msr_file.py`

**Interfaces:**
- Consumes: `find_meas_hist_by_msr(msr)` → `MeasHistRow | None` (existing, `back_dev_home/meas_hist/data.py`). Fields used: `class_name`, `recipe_name`, `idp_name`, `idw_name`, `lot_id`, `total_images`.
- Produces: `get_msr_file(msr, class_name=None, total_images=None) -> MsrFileResponse | None`, where `MsrFileResponse` gains `exe_detail_info`, `alignment`, `spm_dict`, and `MsrFileRow.cd_value` becomes `float | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_msr_file.py`:

```python
import math

import pytest

from back_dev_home.msr_file.data import _summaries, get_msr_file
from back_dev_home.meas_hist.data import get_meas_hist


@pytest.fixture(scope="module")
def sample_msr() -> str:
    """A real MSR id from the meas_hist fixture — never hardcode one."""
    rows = get_meas_hist()["rows"]
    return rows[0]["msr"]


def _row(**over):
    row = {
        "msr": "M1", "sequence": 1, "chip_number": "0, 0", "chip_coordinate": "",
        "stage_coordinate": "", "dnum_group": "0, -1", "mp_number": 1,
        "parameter": "CD_TOP", "cd_value": 10.0, "no_of_mp_image": 1,
        "mp_image_name_01": "", "meas_condition_mag": 250030,
        "meas_condition_vac": 500, "meas_condition_pixel": "512,512",
        "addressing1_score": 868, "addressing2_score": 646,
        "measurement_score": 165, "meas_method": "Score", "object_type": "MP",
        "meas_kind": "Multi Point",
    }
    row.update(over)
    return row


# ── cd_value nullability ─────────────────────────────────────────────────────

def test_invalid_rows_have_null_cd_value(sample_msr):
    payload = get_msr_file(sample_msr)
    invalid = [r for r in payload["rows"] if r["mp_number"] < 0]
    assert invalid, "fixture has no mp_number=-1 rows — test is not exercising the rule"
    for row in invalid:
        assert row["cd_value"] is None
        assert row["no_of_mp_image"] == 0
        assert row["measurement_score"] is None


def test_valid_rows_always_have_a_cd_value(sample_msr):
    payload = get_msr_file(sample_msr)
    valid = [r for r in payload["rows"] if r["mp_number"] >= 0]
    assert valid
    for row in valid:
        assert isinstance(row["cd_value"], float)
        assert math.isfinite(row["cd_value"])


# ── summaries ────────────────────────────────────────────────────────────────

def test_summaries_exclude_null_cd_values():
    rows = [_row(cd_value=10.0), _row(cd_value=20.0), _row(cd_value=None, mp_number=-1)]
    summary = _summaries(rows)[0]
    assert summary["count"] == 2
    assert summary["mean"] == 15.0
    assert summary["max"] == 20.0


def test_summaries_use_sample_stdev_not_population():
    rows = [_row(cd_value=v) for v in (2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0)]
    # population stdev = 2.0; sample stdev = 2.138. The frontend uses sample (n-1).
    assert _summaries(rows)[0]["std"] == 2.138


def test_parameter_with_no_valid_rows_is_omitted():
    rows = [_row(parameter="CD_TOP", cd_value=10.0),
            _row(parameter="CD_BOTTOM", cd_value=None, mp_number=-1)]
    assert [s["parameter"] for s in _summaries(rows)] == ["CD_TOP"]


def test_summary_count_matches_valid_row_count(sample_msr):
    payload = get_msr_file(sample_msr)
    summary = payload["parameters"][0]
    raw = [r for r in payload["rows"] if r["parameter"] == summary["parameter"]]
    valid = [r for r in raw if r["cd_value"] is not None]
    assert len(valid) < len(raw), "fixture has no invalid rows"
    assert summary["count"] == len(valid)


# ── new row columns ──────────────────────────────────────────────────────────

def test_new_measurement_condition_columns_present(sample_msr):
    payload = get_msr_file(sample_msr)
    valid = next(r for r in payload["rows"] if r["mp_number"] >= 0)
    assert valid["meas_condition_mag"] > 0
    assert valid["meas_condition_vac"] > 0
    assert valid["meas_condition_pixel"] != "0,0"
    assert valid["meas_kind"] in ("Multi Point", "Single Point", None)
    assert valid["object_type"] in ("MP", "Line", "Space")
    assert valid["meas_method"] in ("Score", "Width", "Edge")


def test_invalid_rows_report_zeroed_measurement_conditions(sample_msr):
    payload = get_msr_file(sample_msr)
    invalid = next(r for r in payload["rows"] if r["mp_number"] < 0)
    assert invalid["meas_condition_mag"] == 0
    assert invalid["meas_condition_vac"] == 0
    assert invalid["meas_condition_pixel"] == "0,0"


def test_addressing_scores_are_nullable_ints(sample_msr):
    payload = get_msr_file(sample_msr)
    seen_int = False
    for row in payload["rows"]:
        for key in ("addressing1_score", "addressing2_score"):
            assert row[key] is None or isinstance(row[key], int)
            if isinstance(row[key], int):
                seen_int = True
    assert seen_int, "every addressing score was None — generator is not producing values"


# ── exe_detail_info ──────────────────────────────────────────────────────────

def test_exe_detail_info_is_sourced_from_the_parent_meas_hist(sample_msr):
    parent = next(r for r in get_meas_hist()["rows"] if r["msr"] == sample_msr)
    info = get_msr_file(sample_msr)["exe_detail_info"]
    assert info["class_name"] == parent["class_name"]
    assert info["recipe_name"] == parent["recipe_name"]
    assert info["idp_name"] == parent["idp_name"]
    assert info["idw_name"] == parent["idw_name"]
    assert info["lot_id"] == parent["lot_id"]


def test_exe_detail_info_has_wafer_geometry(sample_msr):
    info = get_msr_file(sample_msr)["exe_detail_info"]
    assert info["wafer_size"] == "300"
    assert info["wafer_id"].startswith(info["lot_id"])
    for key in ("chip_array", "chip_pitch", "map_offset", "map_origin", "process"):
        assert info[key]


# ── alignment ────────────────────────────────────────────────────────────────

def test_alignment_has_three_points_with_matching_keys(sample_msr):
    align = get_msr_file(sample_msr)["alignment"]
    assert set(align["image_file"]) == set(align["offset"]) == set(align["score"])
    assert set(align["image_file"]) == {"1", "2", "3"}
    for key in align["offset"]:
        method, x, y = align["offset"][key]
        assert method in ("OM", "SEM")
        assert x.lstrip("-").isdigit() and y.lstrip("-").isdigit()
        # Any non-negative integer. Nothing thresholds on the score yet, so the
        # scale is deliberately not asserted.
        assert align["score"][key].isdigit()


# ── spm_dict (placeholder mock — shape only, no signal) ──────────────────────

def test_spm_dict_is_a_32_point_profile(sample_msr):
    spm = get_msr_file(sample_msr)["spm_dict"]
    assert len(spm["Vol"]) == 32
    assert len(spm["wf_len"]) == 32
    assert len(spm["vave"]) == 1
    assert spm["wf_len"] == sorted(spm["wf_len"]), "wf_len must be monotonic"
    assert spm["wf_len"][0] < 0 < spm["wf_len"][-1]
    assert all(isinstance(v, float) for v in spm["Vol"])


# ── determinism ──────────────────────────────────────────────────────────────

def test_same_msr_always_yields_identical_data(sample_msr):
    get_msr_file.cache_clear()
    first = get_msr_file(sample_msr)
    get_msr_file.cache_clear()
    second = get_msr_file(sample_msr)
    assert first == second
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python -m pytest tests/test_msr_file.py -v`
Expected: FAIL — `KeyError: 'exe_detail_info'`, and `test_invalid_rows_have_null_cd_value` fails because the mock assigns a float.

- [ ] **Step 3: Add the new types**

In `back_dev_home/msr_file/data.py`, extend `MsrFileRow` and add three new TypedDicts. Also update `__all__`.

```python
class MsrFileRow(TypedDict):
    msr: str
    sequence: int
    chip_number: str
    chip_coordinate: str
    stage_coordinate: str
    dnum_group: str
    mp_number: int
    parameter: str
    # NULLABLE (docs §df_result_data: "cd_value": 43.14, None). None exactly when
    # mp_number < 0 — a point with no data has no measurement. Emitting a float
    # here is what silently contaminated every mean, sigma and anomaly verdict.
    cd_value: float | None
    no_of_mp_image: int
    mp_image_name_01: str
    meas_condition_mag: int      # pickle "meas_condition mag"
    meas_condition_vac: int      # pickle "meas_condition vac"
    meas_condition_pixel: str    # pickle "meas_condition pixel"
    addressing1_score: int | None
    addressing2_score: int | None
    measurement_score: int | None
    meas_method: str             # Score | Width | Edge
    object_type: str             # pickle "object" — renamed, `object` shadows the builtin
    meas_kind: str | None        # Multi Point | Single Point | None


class ExeDetailInfo(TypedDict):
    """docs §exe_detail_info. `class` is a Python keyword -> `class_name`."""
    class_name: str
    recipe_name: str
    idp_name: str
    lot_id: str
    process: str
    wafer_id: str
    idw_name: str
    chip_array: str
    chip_pitch: str
    wafer_size: str
    map_offset: str
    map_origin: str


class AlignmentInfo(TypedDict):
    """docs §alignment. Keys "1".."3" are the alignment points."""
    image_file: dict[str, str]
    offset: dict[str, list[str]]   # [method, x, y] e.g. ["OM", "365", "3525"]
    score: dict[str, str]


class SpmDict(TypedDict):
    """docs §spm_dict. A 32-point profile: Vol (signal) against wf_len (nm).

    PLACEHOLDER MOCK. The real waveform is broadly stable or gently parabolic,
    and Phase 1 (home) has no consumer for it — nothing reads spm_dict yet. So it
    is generated as a shallow parabola plus noise, deliberately NOT coupled to
    cd_value. Do not build analysis on its shape; it carries no signal.
    """
    vave: list[float]
    Vol: list[float]
    wf_len: list[float]
```

Then add to `MsrFileResponse`:

```python
class MsrFileResponse(TypedDict):
    msr: str
    class_name: str
    total_images: int
    sequence_count: int
    health: float
    parameters: list[MsrParamSummary]
    fdc_params: list[FdcParamSummary]
    fixed_fdc: dict[str, float]
    dynamic_fdc: dict[str, dict[str, float]]
    exe_detail_info: ExeDetailInfo
    alignment: AlignmentInfo
    spm_dict: SpmDict
    total: int
    rows: list[MsrFileRow]
```

- [ ] **Step 4: Add the generators**

Add these module-level constants and functions to `back_dev_home/msr_file/data.py`:

```python
import math

_MEAS_KINDS: tuple[str | None, ...] = ("Multi Point", "Single Point", None)
_MAGNIFICATIONS: tuple[int, ...] = (200015, 250030, 250044)
_VOLTAGES: tuple[int, ...] = (500, 800, 1000)
_PIXELS: tuple[str, ...] = ("512,512", "1024,1024")
_PROCESS_BY_CLASS: dict[str, str] = {
    "ADI": "PHOTO", "AEI": "ETCH", "OVL": "PHOTO", "GATE": "ETCH",
    "CNT": "ETCH", "EDGE": "ETCH", "QC": "METRO", "DEF": "METRO",
}
SPM_POINTS = 32


def _exe_detail_info(msr: str, parent: dict | None, class_name: str) -> ExeDetailInfo:
    """Acquisition context. Sourced from the parent meas_hist row wherever
    possible so the MSR detail can never contradict the measurement history it
    hangs off; only the wafer geometry (absent upstream) is seeded."""
    rng = random.Random(_seed(msr, 313))
    recipe_name = parent["recipe_name"] if parent else f"{class_name}_UNKNOWN"
    lot_id = parent["lot_id"] if parent else f"LOT{_seed(msr) % 1_000_000:06d}"
    idp_name = parent["idp_name"] if parent else f"/Recipe/{class_name}/{recipe_name}.idp"
    idw_name = parent["idw_name"] if parent else f"/Recipe/{class_name}/{recipe_name}.idw"

    cols, rows_n = rng.randint(38, 46), rng.randint(52, 62)
    pitch_x, pitch_y = rng.randrange(24, 28) * 1_000_000, rng.randrange(31, 35) * 1_000_000

    return ExeDetailInfo(
        class_name=class_name,
        recipe_name=recipe_name,
        idp_name=idp_name,
        lot_id=lot_id,
        process=_PROCESS_BY_CLASS.get(class_name.upper(), "METRO"),
        # 25 wafers to a lot; the slot is stable per MSR.
        wafer_id=f"{lot_id}_{(_seed(msr, 41) % 25) + 1:02d}",
        idw_name=idw_name,
        chip_array=f"{cols},{rows_n}",
        chip_pitch=f"{pitch_x},{pitch_y}",
        wafer_size="300",
        map_offset=f"{rng.randrange(-3_000_000, 3_000_000)},{rng.randrange(-3_000_000, 3_000_000)}",
        map_origin=f"{rng.randrange(-1_000_000, 1_000_000)},{rng.randrange(-1_000_000, 1_000_000)}",
    )


def _alignment(msr: str, health: float) -> AlignmentInfo:
    """Three alignment points. Scores are plain integers, seeded per MSR and
    trending lower as `health` rises. Nothing downstream thresholds on them yet,
    so the exact scale is not load-bearing — keep it an int and keep it stable."""
    rng = random.Random(_seed(msr, 617))
    image_file: dict[str, str] = {}
    offset: dict[str, list[str]] = {}
    score: dict[str, str] = {}

    for i in range(1, 4):
        key = str(i)
        method = "OM" if i == 1 else "SEM"
        image_file[key] = f"{msr}_ALIGN{i}_{rng.randint(0, 9999):04d}.tif"
        offset[key] = [method, str(rng.randrange(-4000, 4000)), str(rng.randrange(-4000, 4000))]
        score[key] = str(max(0, int(round(rng.uniform(820, 960) - 400 * health))))

    return AlignmentInfo(image_file=image_file, offset=offset, score=score)


def _spm_dict(msr: str) -> SpmDict:
    """A 32-point profile. PLACEHOLDER — see SpmDict.

    Shallow parabola + noise. Nothing reads spm_dict in Phase 1, and the real
    signal is broadly stable, so this exists to satisfy the response shape and
    nothing more. It is deliberately NOT derived from cd_value or health: a mock
    that looks meaningful invites analysis it cannot support.
    """
    rng = random.Random(_seed(msr, 829))
    span = 148.0
    wf_len = [round(-span + (2 * span) * i / (SPM_POINTS - 1), 2) for i in range(SPM_POINTS)]

    curvature = rng.uniform(2e-5, 8e-5)
    base = rng.uniform(0.8, 1.6)
    vol = [round(base - curvature * (x ** 2) + rng.gauss(0, 0.03), 5) for x in wf_len]

    return SpmDict(vave=[round(fmean(vol), 5)], Vol=vol, wf_len=wf_len)
```

- [ ] **Step 5: Rewrite `_build_rows` to emit the new columns and null CD**

Replace the body of the sequence loop in `_build_rows` (`data.py:267-303`):

```python
    for sequence in range(1, num_measurements + 1):
        seq_frac = (sequence - 1) / span
        chip_x, chip_y = positions[(sequence - 1) % len(positions)]
        chip_number = f"{chip_x}, {chip_y}"
        chip_coordinate = f"{12_000_000 + sequence * 1000 + seed % 1_000_000},{250_000 + sequence * 100}"
        stage_coordinate = f"{175_000_000 + sequence * 10000 + seed % 100_000}, {147_000_000 + sequence * 5000}"

        # Every 20th sequence carries point METADATA but no point DATA (spec rule 9).
        # Such a row has no measurement, so it has no cd_value, no image and no
        # score. Emitting a float here is the bug this rewrite exists to kill.
        empty = sequence % 20 == 0

        if empty:
            dnum_group, mp_number = "-1, -1", -1
        else:
            mp_number = (sequence - 1) % 30
            dnum_group = f"{mp_number}, -1"

        if empty:
            meas_mag, meas_vac, meas_pixel = 0, 0, "0,0"
            measurement_score = None
            addressing1 = addressing2 = None
            meas_kind = None
        else:
            meas_mag = _MAGNIFICATIONS[(sequence + seed) % len(_MAGNIFICATIONS)]
            meas_vac = _VOLTAGES[(sequence + seed) % len(_VOLTAGES)]
            meas_pixel = _PIXELS[(sequence + seed) % len(_PIXELS)]
            # Quality scores fall as health rises; ~health fraction fail to score.
            scored = rng.random() > (0.05 + 0.35 * health)
            measurement_score = int(round(rng.uniform(820, 990) - 220 * health)) if scored else None
            addressing1 = int(round(rng.uniform(600, 950) - 200 * health)) if scored else None
            addressing2 = int(round(rng.uniform(600, 950) - 200 * health)) if scored else None
            meas_kind = _MEAS_KINDS[(sequence + seed) % len(_MEAS_KINDS)]

        meas_method = _MEAS_METHODS[(sequence + seed) % len(_MEAS_METHODS)]
        object_type = _OBJECT_TYPES[(sequence + seed) % len(_OBJECT_TYPES)]

        for parameter in selected_params:
            rows.append(MsrFileRow(
                msr=msr,
                sequence=sequence,
                chip_number=chip_number,
                chip_coordinate=chip_coordinate,
                stage_coordinate=stage_coordinate,
                dnum_group=dnum_group,
                mp_number=mp_number,
                parameter=parameter,
                cd_value=None if empty else _cd_value(rng, parameter, health, seq_frac),
                no_of_mp_image=0 if empty else 1 + rng.randint(0, 4),
                mp_image_name_01=(
                    "" if empty
                    else f"{msr}_{sequence:03d}_{parameter}_{rng.randint(0, 9999):04d}.tif"
                ),
                meas_condition_mag=meas_mag,
                meas_condition_vac=meas_vac,
                meas_condition_pixel=meas_pixel,
                addressing1_score=addressing1,
                addressing2_score=addressing2,
                measurement_score=measurement_score,
                meas_method=meas_method,
                object_type=object_type,
                meas_kind=meas_kind,
            ))
```

- [ ] **Step 6: Fix `_summaries` — gate nulls, switch to sample σ**

`fmean()` will now raise on a `None`, so this fix is *forced* by Step 5 rather than optional. Change the import at the top of the module from `pstdev` to `stdev`, then replace `_summaries` (`data.py:358-376`):

```python
def _summaries(rows: list[MsrFileRow]) -> list[MsrParamSummary]:
    """Per-parameter descriptive stats over MEASURED rows only.

    These summaries feed the Data Summary table, the 3-sigma column AND the
    time-series anomaly verdicts, so a single unmeasured row leaking in here
    propagates into a wrong watch/abnormal call. Mirrors the frontend gate in
    app/utils/msrRows.ts::isValidRow.
    """
    by_param: dict[str, list[float]] = {}
    for row in rows:
        value = row["cd_value"]
        if value is None or not math.isfinite(value):
            continue
        by_param.setdefault(row["parameter"], []).append(value)

    summaries = [
        MsrParamSummary(
            parameter=parameter,
            count=len(values),
            mean=round(fmean(values), 3),
            # Sample stdev (n-1), matching app/utils/stats.ts::sampleStd and
            # anomaly/peer.ts::looStats. pstdev would make the backend sigma and
            # the frontend sigma different quantities.
            std=round(stdev(values), 3) if len(values) > 1 else 0.0,
            min=round(min(values), 3),
            max=round(max(values), 3),
            unit=_unit(parameter),
        )
        for parameter, values in by_param.items()
        if values
    ]
    summaries.sort(key=lambda summary: summary["parameter"])
    return summaries
```

- [ ] **Step 7: Wire the new structures into `get_msr_file`**

`exe_detail_info` needs parent fields (`recipe_name`, `lot_id`, `idp_name`, `idw_name`) that the current early-return only fetches when `class_name`/`total_images` are absent. Always attempt the lookup:

```python
@lru_cache(maxsize=256)
def get_msr_file(
    msr: str,
    class_name: str | None = None,
    total_images: int | None = None
) -> MsrFileResponse | None:
    if not msr:
        return None

    # The skewvoir UI passes class_name/total_images from the selected meas_hist
    # row, but exe_detail_info needs recipe_name, lot_id, idp_name and idw_name
    # too — so always attempt the parent lookup, and only fall back to seeded
    # synthesis when the MSR has no parent at all.
    parent = find_meas_hist_by_msr(msr)
    if class_name is None:
        if parent is None:
            return None
        class_name = parent["class_name"]
    if total_images is None:
        if parent is None:
            return None
        total_images = parent["total_images"]

    health = _health(msr)
    rows = _build_rows(msr, class_name, total_images, health)

    sequences = sorted({row["sequence"] for row in rows})
    fixed_fdc, dynamic_fdc, fdc_params = _build_fdc(msr, sequences, health)

    return MsrFileResponse(
        msr=msr,
        class_name=class_name,
        total_images=total_images,
        sequence_count=rows[-1]["sequence"] if rows else 0,
        health=health,
        parameters=_summaries(rows),
        fdc_params=fdc_params,
        fixed_fdc=fixed_fdc,
        dynamic_fdc=dynamic_fdc,
        exe_detail_info=_exe_detail_info(msr, parent, class_name),
        alignment=_alignment(msr, health),
        spm_dict=_spm_dict(msr),
        total=len(rows),
        rows=rows,
    )
```

- [ ] **Step 8: Update the module docstring**

Record the two renames so the next reader doesn't think the mock drifted from spec:

```python
"""...

Two columns are renamed from the pickle spec because the literal names are not
usable as Python identifiers in a TypedDict: `class` -> `class_name` (keyword)
and `object` -> `object_type` (shadows the builtin). The wire format uses the
renamed keys and the frontend consumes them under those names.

`cd_value` is NULLABLE (docs §df_result_data). It is None exactly when
mp_number < 0 — a point with metadata but no data has no measurement. Every
consumer must gate on this; see app/utils/msrRows.ts.
"""
```

- [ ] **Step 9: Run the tests and confirm they pass**

Run: `python -m pytest tests/test_msr_file.py -v`
Expected: PASS — all tests.

Then the full backend suite, which will catch anything that asserted on the old contaminated numbers:

Run: `python -m pytest -q`
Expected: PASS. If an existing test fails because it hardcoded an old mean or assumed a non-null `cd_value`, **that test was asserting the bug** — update it and say so in the commit body.

- [ ] **Step 10: Verify a live payload by hand**

Run: `PORT=5050 python index.py &` then
`curl -s 'http://localhost:5050/api/msr-file?msr=<sample_msr>' | python -m json.tool | head -60`
Expected: `exe_detail_info`, `alignment`, `spm_dict` present; at least one row with `"cd_value": null`.

- [ ] **Step 11: Commit**

```bash
git add back_dev_home/msr_file/data.py tests/test_msr_file.py
git commit -m "feat(msr-file): complete the mock against msr_file_pickle.txt

Adds the missing df_result_data columns (meas_condition_*, addressing scores,
meas_kind), plus exe_detail_info, alignment and spm_dict.

cd_value is now NULLABLE and is None exactly when mp_number < 0, per spec. The
old mock fabricated a CD for those rows, so ~5% junk was contaminating every
mean, sigma, 3-sigma column and time-series anomaly verdict in Skewvoir.
_summaries() now gates on it and switches pstdev -> stdev so the backend sigma
matches the frontend's sample-sigma convention.

spm_dict is a placeholder: a seeded parabola satisfying the response shape. It is
deliberately not derived from cd_value — nothing consumes it in Phase 1, and a
mock that looks meaningful would invite analysis it cannot support."
```

---

# Phase A — Establish analytical truth

### Task 2: Nullable `cd_value` in the frontend + the validity gate

**Why:** This is one atomic change: you cannot half-migrate a type. Flipping `cd_value` to `number | null` makes `npm run typecheck` enumerate *every* consumer that was silently reading fabricated values — the compiler produces the worklist. The gate is what makes it green again.

**Do not "fix" the type errors with `?? 0` or `!`.** A zero is not a missing measurement; it is a measurement of zero, and it would poison exactly the averages this whole plan exists to clean. Every site must either drop the row or explicitly handle null.

**Files:**
- Modify: `front-dev-home/app/composables/useMsrFileApi.ts`
- Create: `front-dev-home/app/utils/msrRows.ts`
- Test: `front-dev-home/app/utils/msrRows.test.ts`
- Modify (compiler will name them; expect roughly): `components/ebeam/skewvoir/{WaferMap,RadiusChart,DistributionChart,CorrelationScatter,SequenceTrend}.vue`, `views/{PositionStack,Gallery}.vue`, `dashboard/{WaferMap,MeasurementPoints,SemImage}.vue`

**Interfaces:**
- Produces:
  - `isValidRow(row: MsrFileRow): row is ValidMsrRow`
  - `validRows(rows: MsrFileRow[]): ValidMsrRow[]`
  - `paramValues(rows: MsrFileRow[], parameter: string): number[]`
  - `type ValidMsrRow = MsrFileRow & { cd_value: number }`

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/msrRows.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isValidRow, validRows, paramValues } from './msrRows.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 10,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

test('a null cd_value is invalid', () => {
  assert.equal(isValidRow(row({ cd_value: null, mp_number: -1 })), false)
})

test('mp_number < 0 is invalid even if a cd_value somehow survives', () => {
  // Defence in depth: the office backend may not honour the null contract.
  assert.equal(isValidRow(row({ mp_number: -1, cd_value: 42 })), false)
})

test('non-finite cd_value is invalid', () => {
  assert.equal(isValidRow(row({ cd_value: Number.NaN })), false)
  assert.equal(isValidRow(row({ cd_value: Number.POSITIVE_INFINITY })), false)
})

test('mp_number 0 is valid — only negatives are sentinels', () => {
  assert.equal(isValidRow(row({ mp_number: 0 })), true)
})

test('validRows drops invalid rows and preserves order', () => {
  const rows = [
    row({ sequence: 1 }),
    row({ sequence: 2, mp_number: -1, cd_value: null }),
    row({ sequence: 3 })
  ]
  assert.deepEqual(validRows(rows).map(r => r.sequence), [1, 3])
})

test('paramValues filters by parameter AND validity', () => {
  const rows = [
    row({ parameter: 'CD_TOP', cd_value: 10 }),
    row({ parameter: 'CD_BOTTOM', cd_value: 20 }),
    row({ parameter: 'CD_TOP', cd_value: null, mp_number: -1 }),
    row({ parameter: 'CD_TOP', cd_value: 12 })
  ]
  assert.deepEqual(paramValues(rows, 'CD_TOP'), [10, 12])
})

test('empty input yields empty output', () => {
  assert.deepEqual(validRows([]), [])
  assert.deepEqual(paramValues([], 'CD_TOP'), [])
})
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `Cannot find module './msrRows.ts'`.

- [ ] **Step 3: Update the API types to mirror the new response**

In `front-dev-home/app/composables/useMsrFileApi.ts`, update `MsrFileRow` and `MsrFileResponse`:

```ts
export interface MsrFileRow {
  msr: string
  sequence: number
  chip_number: string
  chip_coordinate: string
  stage_coordinate: string
  dnum_group: string
  mp_number: number
  parameter: string
  // NULLABLE: null exactly when mp_number < 0 — a point with metadata but no
  // data has no measurement. Never coerce this to 0; gate it via utils/msrRows.
  cd_value: number | null
  no_of_mp_image: number
  mp_image_name_01: string
  meas_condition_mag: number
  meas_condition_vac: number
  meas_condition_pixel: string
  addressing1_score: number | null
  addressing2_score: number | null
  measurement_score: number | null
  meas_method: string
  object_type: string
  meas_kind: string | null
}

export interface ExeDetailInfo {
  class_name: string
  recipe_name: string
  idp_name: string
  lot_id: string
  process: string
  wafer_id: string
  idw_name: string
  chip_array: string
  chip_pitch: string
  wafer_size: string
  map_offset: string
  map_origin: string
}

export interface AlignmentInfo {
  image_file: Record<string, string>
  // [method, x, y] — e.g. ['OM', '365', '3525']
  offset: Record<string, [string, string, string]>
  score: Record<string, string>
}

// A 32-point profile: Vol (signal) against wf_len (nm). PLACEHOLDER — the mock
// generates a seeded parabola with no signal in it. Nothing consumes this yet;
// do not build analysis on its shape.
export interface SpmDict {
  vave: number[]
  Vol: number[]
  wf_len: number[]
}
```

…and add `exe_detail_info: ExeDetailInfo`, `alignment: AlignmentInfo`, `spm_dict: SpmDict` to `MsrFileResponse`.

- [ ] **Step 4: Write the validity gate**

Create `front-dev-home/app/utils/msrRows.ts`:

```ts
// The ONE place the raw-row validity rule is written down.
//
// A row with mp_number < 0 carries point metadata but no point data, so the
// backend reports cd_value: null (docs/datatables/msr_file_pickle.txt). We check
// BOTH conditions rather than trusting either alone: the null is the contract,
// and the mp_number check is defence in depth for an office backend that may not
// honour it.
//
// isValidRow is a type guard, so ValidMsrRow.cd_value is a plain `number` —
// downstream code cannot forget the null, because the compiler removes it.
import type { MsrFileRow } from '~/composables/useMsrFileApi'

export type ValidMsrRow = MsrFileRow & { cd_value: number }

export const isValidRow = (row: MsrFileRow): row is ValidMsrRow =>
  row.mp_number >= 0 && row.cd_value != null && Number.isFinite(row.cd_value)

export const validRows = (rows: MsrFileRow[]): ValidMsrRow[] => rows.filter(isValidRow)

// Measured CD values for one parameter, in row order.
export const paramValues = (rows: MsrFileRow[], parameter: string): number[] => {
  const out: number[] = []
  for (const row of rows) {
    if (row.parameter === parameter && isValidRow(row)) out.push(row.cd_value)
  }
  return out
}
```

- [ ] **Step 5: Run the unit test, then let the compiler build the worklist**

Run: `npm --prefix front-dev-home test`
Expected: PASS — 7 tests.

Run: `npm --prefix front-dev-home run typecheck`
Expected: **FAIL, loudly.** Every error is a place that was reading a fabricated CD. This is the worklist. Capture it:

```bash
npm --prefix front-dev-home run typecheck 2>&1 | grep -E "error TS" | sort -u
```

- [ ] **Step 6: Resolve each error through the gate**

Work the list. Three legitimate shapes — and nothing else:

1. **Component consumes rows for a chart** → filter once at the top and use the narrowed type:
   ```ts
   import { validRows } from '~/utils/msrRows'
   const rows = computed(() => validRows(props.rows))
   ```
   Then have the existing computeds read `rows.value` instead of `props.rows`. Applies to `SequenceTrend.vue`, `WaferMap.vue`, `RadiusChart.vue`, `views/Gallery.vue`, `dashboard/*.vue`. In the six components that already hand-rolled `r.mp_number < 0`, **delete that check** — `isValidRow` subsumes it.

2. **Component needs values for one parameter** → `paramValues(props.rows, props.parameter)`.

3. **A table cell genuinely renders the raw row** (e.g. a raw-point table showing every sequence, invalid ones included) → render the null explicitly as `—`, never as `0`:
   ```vue
   {{ row.cd_value ?? '—' }}
   ```

- [ ] **Step 7: Confirm every gate goes through the util**

Run: `grep -rn "mp_number < 0" front-dev-home/app/`
Expected: **no matches.** Every site now calls `isValidRow`/`validRows`.

Run: `grep -rn "cd_value ?? 0\|cd_value!" front-dev-home/app/`
Expected: **no matches.** A coerced zero is a fabricated measurement — the exact bug this task removes.

- [ ] **Step 8: Full gates**

Run: `npm --prefix front-dev-home test && npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add front-dev-home/app/composables/useMsrFileApi.ts front-dev-home/app/utils/msrRows.ts front-dev-home/app/utils/msrRows.test.ts front-dev-home/app/components/
git commit -m "fix(skewvoir): make cd_value nullable and gate every consumer

Mirrors the backend contract: cd_value is null when mp_number < 0. Flipping the
type surfaced every chart that was silently averaging fabricated CDs for points
that were never measured. All of them now route through utils/msrRows."
```

---

### Task 3: Consolidated statistics module

**Why:** Pearson is implemented twice and the copies disagree — `CorrelationScatter.vue:39-56` accepts `n >= 2` and returns `null` on zero variance; `FdcAnalysis.vue:430-447` requires `n >= 3` (correctly: at `n = 2` any two points are collinear, so *r* is trivially ±1) and returns `0`. Quantiles are implemented twice (`DistributionChart.vue:54-61` duplicates `boxplotStats.ts:13-18`, minus the finite filter). σ is computed two ways: `PositionStack.vue:109` uses the unstable one-pass `sumsq/n - m²` with a `Math.max(0, …)` clamp and population σ, while `anomaly/peer.ts:26-28` uses two-pass sample σ.

**Files:**
- Create: `front-dev-home/app/utils/stats.ts`
- Modify: `front-dev-home/app/utils/boxplotStats.ts`
- Test: `front-dev-home/app/utils/stats.test.ts`

**Interfaces:**
- Produces:
  - `mean(values: number[]): number` — NaN on empty
  - `sampleStd(values: number[]): number` — two-pass, `n-1`; `0` when `n < 2`
  - `quantileSorted(sorted: number[], p: number): number` — R-7; caller pre-sorts and pre-filters
  - `iqrFences(values: number[]): IqrFences | null` — `{ q1, q3, lower, upper }`, Tukey 1.5×IQR
  - `pearson(pairs: [number, number][]): number | null` — null when `n < 3` or either axis has zero variance
  - `spearman(pairs: [number, number][]): number | null` — average-rank ties, then Pearson on ranks
  - `linearFit(pairs: [number, number][]): { slope: number, intercept: number } | null`

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/stats.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mean, sampleStd, quantileSorted, iqrFences, pearson, spearman, linearFit } from './stats.ts'

const close = (a: number, b: number, eps = 1e-9) =>
  assert.ok(Math.abs(a - b) < eps, `${a} !== ${b}`)

test('mean of empty is NaN, not 0 — an empty set has no centre', () => {
  assert.ok(Number.isNaN(mean([])))
})

test('sampleStd uses n-1 and is 0 for a single value', () => {
  close(sampleStd([2, 4, 4, 4, 5, 5, 7, 9]), 2.138089935299395)
  assert.equal(sampleStd([3]), 0)
  assert.equal(sampleStd([]), 0)
})

test('sampleStd is numerically stable for large offsets', () => {
  // The one-pass sumsq/n - m^2 shortcut loses all precision here and can go negative.
  close(sampleStd([1e9 + 4, 1e9 + 7, 1e9 + 13, 1e9 + 16]), 5.477225575051661, 1e-6)
})

test('quantileSorted matches R-7 / numpy default', () => {
  close(quantileSorted([1, 2, 3, 4], 0.25), 1.75)
  close(quantileSorted([1, 2, 3, 4], 0.5), 2.5)
  close(quantileSorted([1, 2, 3, 4], 0.75), 3.25)
})

test('iqrFences applies Tukey 1.5x IQR', () => {
  const f = iqrFences([1, 2, 3, 4, 5, 6, 7, 8, 9])!
  close(f.q1, 3)
  close(f.q3, 7)
  close(f.lower, 3 - 1.5 * 4)
  close(f.upper, 7 + 1.5 * 4)
})

test('iqrFences returns null on empty and ignores non-finite values', () => {
  assert.equal(iqrFences([]), null)
  close(iqrFences([1, Number.NaN, 2, 3, 4])!.q1, 1.75)
})

test('pearson is 1 for a perfect positive line and -1 for a negative one', () => {
  close(pearson([[1, 2], [2, 4], [3, 6], [4, 8]])!, 1)
  close(pearson([[1, -2], [2, -4], [3, -6], [4, -8]])!, -1)
})

test('pearson refuses n < 3 — at n=2 r is trivially +/-1', () => {
  assert.equal(pearson([[1, 5], [2, 9]]), null)
})

test('pearson returns null on zero variance in either axis', () => {
  assert.equal(pearson([[1, 5], [1, 7], [1, 9]]), null)
  assert.equal(pearson([[1, 5], [2, 5], [3, 5]]), null)
})

test('spearman is 1 for any monotonic relation, even a non-linear one', () => {
  // Pearson would NOT be 1 here; that is the whole reason Spearman exists.
  close(spearman([[1, 1], [2, 8], [3, 27], [4, 64]])!, 1)
})

test('spearman handles tied ranks with average ranks', () => {
  // x ranks: 1, 2.5, 2.5, 4 | y ranks: 1, 2.5, 2.5, 4 -> perfect agreement
  close(spearman([[10, 1], [20, 2], [20, 2], [30, 3]])!, 1)
})

test('linearFit recovers slope and intercept', () => {
  const fit = linearFit([[0, 1], [1, 3], [2, 5], [3, 7]])!
  close(fit.slope, 2)
  close(fit.intercept, 1)
})

test('linearFit returns null when x has zero variance', () => {
  assert.equal(linearFit([[2, 1], [2, 3], [2, 5]]), null)
})
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `Cannot find module './stats.ts'`.

- [ ] **Step 3: Write the implementation**

Create `front-dev-home/app/utils/stats.ts`:

```ts
// Pure descriptive statistics. No framework deps, no domain knowledge.
// This is the ONLY place these formulas are written down — before this module,
// Pearson lived in two components with different edge-case behaviour.

// NaN, not 0: an empty set has no centre, and 0 would silently poison averages.
export const mean = (values: number[]): number => {
  if (values.length === 0) return Number.NaN
  let sum = 0
  for (const v of values) sum += v
  return sum / values.length
}

// Two-pass sample std (n-1). The one-pass sumsq/n - m^2 shortcut is faster but
// catastrophically cancels when the mean is large relative to the spread — it can
// even return a negative variance. CD values sit at ~1e2 nm with ~1 nm spread, so
// the stability matters. n-1 matches anomaly/peer.ts::looStats.
export const sampleStd = (values: number[]): number => {
  const n = values.length
  if (n < 2) return 0
  const m = mean(values)
  let acc = 0
  for (const v of values) acc += (v - m) ** 2
  return Math.sqrt(acc / (n - 1))
}

// R-7 linear interpolation (numpy/Excel default). Caller pre-sorts and pre-filters.
export const quantileSorted = (sorted: number[], p: number): number => {
  if (sorted.length === 0) return Number.NaN
  const pos = (sorted.length - 1) * p
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo]! + (pos - lo) * (sorted[hi]! - sorted[lo]!)
}

export interface IqrFences {
  q1: number
  q3: number
  lower: number
  upper: number
}

// Tukey 1.5x IQR — for WHISKER RENDERING on CD site distributions only. It is NOT
// an outlier verdict; utils/anomaly/ owns that. And it deliberately does not touch
// boxplotStats.ts, whose true-extreme whiskers are correct for 4-6-tool fleet plots
// where fencing would hide real tools.
export const iqrFences = (values: number[]): IqrFences | null => {
  const sorted = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return null
  const q1 = quantileSorted(sorted, 0.25)
  const q3 = quantileSorted(sorted, 0.75)
  const iqr = q3 - q1
  return { q1, q3, lower: q1 - 1.5 * iqr, upper: q3 + 1.5 * iqr }
}

// Centred sums shared by pearson and linearFit.
const centred = (pairs: [number, number][]) => {
  const pts = pairs.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
  const n = pts.length
  if (n === 0) return null
  let mx = 0
  let my = 0
  for (const [x, y] of pts) {
    mx += x
    my += y
  }
  mx /= n
  my /= n
  let sxy = 0
  let sxx = 0
  let syy = 0
  for (const [x, y] of pts) {
    sxy += (x - mx) * (y - my)
    sxx += (x - mx) ** 2
    syy += (y - my) ** 2
  }
  return { n, mx, my, sxy, sxx, syy }
}

// n >= 3 floor: with n = 2 any two distinct points are perfectly collinear, so r is
// trivially +/-1 and means nothing. Returns null (not 0) when undefined, so callers
// must render "no answer" rather than a fake zero that reads as a real finding.
export const pearson = (pairs: [number, number][]): number | null => {
  const c = centred(pairs)
  if (!c || c.n < 3) return null
  if (c.sxx === 0 || c.syy === 0) return null
  return c.sxy / Math.sqrt(c.sxx * c.syy)
}

// Average ranks for ties (1, 2.5, 2.5, 4) — the standard tie correction.
const ranks = (values: number[]): number[] => {
  const idx = values.map((v, i) => [v, i] as const).sort((a, b) => a[0] - b[0])
  const out = new Array<number>(values.length)
  let i = 0
  while (i < idx.length) {
    let j = i
    while (j + 1 < idx.length && idx[j + 1]![0] === idx[i]![0]) j++
    const avg = (i + j) / 2 + 1
    for (let k = i; k <= j; k++) out[idx[k]![1]] = avg
    i = j + 1
  }
  return out
}

// Spearman rho = Pearson on ranks. Captures ANY monotonic relation, not just a
// linear one, and is far less sensitive to a single wild CD than Pearson.
export const spearman = (pairs: [number, number][]): number | null => {
  const pts = pairs.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
  if (pts.length < 3) return null
  const rx = ranks(pts.map(p => p[0]))
  const ry = ranks(pts.map(p => p[1]))
  return pearson(rx.map((r, i) => [r, ry[i]!] as [number, number]))
}

export interface LinearFit {
  slope: number
  intercept: number
}

export const linearFit = (pairs: [number, number][]): LinearFit | null => {
  const c = centred(pairs)
  if (!c || c.n < 2 || c.sxx === 0) return null
  const slope = c.sxy / c.sxx
  return { slope, intercept: c.my - slope * c.mx }
}
```

- [ ] **Step 4: Point `boxplotStats.ts` at the shared quantile**

Delete its local `quantileSorted` (lines 13-18) and import instead. `boxStats`'s behaviour — including true-extreme whiskers — is unchanged:

```ts
// Pure: five-number summary for the MDC fleet boxplot. Quartiles use R-7 linear
// interpolation (numpy/Excel default). min/max are the true extremes — hardware
// fleets are 4-6 tools, so whisker fencing would hide real tools. (CD site
// distributions DO want fencing — see iqrFences in stats.ts.)
import { quantileSorted } from './stats.ts'

export interface BoxStats {
  min: number
  q1: number
  median: number
  q3: number
  max: number
}

export const boxStats = (values: number[]): BoxStats | null => {
  const sorted = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return null
  return {
    min: sorted[0]!,
    q1: quantileSorted(sorted, 0.25),
    median: quantileSorted(sorted, 0.5),
    q3: quantileSorted(sorted, 0.75),
    max: sorted[sorted.length - 1]!
  }
}
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `npm --prefix front-dev-home test`
Expected: PASS — the new `stats.test.ts` cases plus **every existing `boxplotStats.test.ts` case still green.** That regression is the proof the refactor was behaviour-preserving.

- [ ] **Step 6: Gates and commit**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`

```bash
git add front-dev-home/app/utils/stats.ts front-dev-home/app/utils/stats.test.ts front-dev-home/app/utils/boxplotStats.ts
git commit -m "feat(skewvoir): add tested stats module, dedupe quantile from boxplotStats"
```

---

### Task 4: Route the chart components through the shared statistics

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/DistributionChart.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/CorrelationScatter.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/FdcAnalysis.vue`

**Interfaces:**
- Consumes: `paramValues`, `isValidRow` (Task 2); `mean`, `quantileSorted`, `iqrFences`, `pearson`, `spearman`, `linearFit` (Task 3).
- Produces: nothing. This task only deletes code.

> No unit test here — these are `.vue` files and this repo does not test components (Global Constraints). The math they now call is already covered by Tasks 2–3. Verification is the browser check in Step 4.

- [ ] **Step 1: `DistributionChart.vue` — shared quantiles, fenced whiskers**

Delete the local `quantile` (lines 54-61) and the hand-rolled `boxStats` array (lines 63-73). Replace:

```ts
import { paramValues } from '~/utils/msrRows'
import { mean as meanOf, quantileSorted, iqrFences } from '~/utils/stats'

const values = computed(() => paramValues(props.rows, props.parameter))

const mean = computed(() => {
  const v = values.value
  return v.length ? meanOf(v) : 0
})

// Five-number summary with Tukey-fenced whiskers. Unlike the MDC fleet boxplot
// (boxplotStats.ts), a CD distribution has hundreds of sites, so fencing surfaces
// genuine outliers instead of hiding real tools.
const boxStats = computed(() => {
  const sorted = [...values.value].sort((a, b) => a - b)
  if (sorted.length === 0) return null
  const f = iqrFences(sorted)!
  const inliers = sorted.filter(v => v >= f.lower && v <= f.upper)
  return [
    inliers[0] ?? sorted[0]!,
    f.q1,
    quantileSorted(sorted, 0.5),
    f.q3,
    inliers[inliers.length - 1] ?? sorted[sorted.length - 1]!
  ]
})
```

The `bins` computed already reads `values.value` and needs no change — it is now gated for free.

- [ ] **Step 2: `CorrelationScatter.vue` — shared Pearson, plus ρ and n**

Delete the local `r2` block (lines 39-56). Replace:

```ts
import { isValidRow } from '~/utils/msrRows'
import { pearson, spearman, linearFit } from '~/utils/stats'

const pairs = computed<[number, number][]>(() => {
  const xBySite = new Map<string, number>()
  for (const r of props.rows) {
    if (!isValidRow(r)) continue
    if (r.parameter === props.paramX) xBySite.set(`${r.chip_number}#${r.sequence}`, r.cd_value)
  }
  const out: [number, number][] = []
  for (const r of props.rows) {
    if (!isValidRow(r) || r.parameter !== props.paramY) continue
    const x = xBySite.get(`${r.chip_number}#${r.sequence}`)
    if (x != null) out.push([x, r.cd_value])
  }
  return out
})

const r = computed(() => pearson(pairs.value))
const r2 = computed(() => (r.value == null ? null : r.value * r.value))
const rho = computed(() => spearman(pairs.value))
const sampleN = computed(() => pairs.value.length)
```

Source `fitLine` from `linearFit` rather than `polyfit`, so the fit and the *r* come from the same centred sums. In the template, show `n` alongside r² — a correlation without its sample size is not a finding — and render `표본 부족` when `r2` is `null`, so "not computed" stays distinguishable from "zero."

- [ ] **Step 3: `FdcAnalysis.vue` — delete the second Pearson**

Delete the local Pearson (~lines 430-447) and `scatterFit` (~450-467); import `pearson` and `linearFit` from `~/utils/stats`. The shared `pearson` already carries FdcAnalysis's own `n >= 3` rule — its comment is what set the floor in `stats.ts` — so behaviour is preserved. **One change:** it now returns `null` instead of `0` where the correlation is undefined. Update the call site to render "insufficient" rather than a `0`, which reads as a real, measured non-correlation.

- [ ] **Step 4: Verify**

Run: `npm --prefix front-dev-home test && npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`

Then launch the app (Flask :5050 + Nuxt with `NUXT_API_TARGET=http://localhost:5050` — see the `verify` project skill) and open the Correlation and Dashboard views for a single MSR. Confirm the layout is unchanged, the scatter now shows *n* and ρ, and the distribution's whiskers are fenced. **The numbers will have moved — that is the deliverable.** Screenshot to `.playwright-mcp/screenshots/`.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/
git commit -m "refactor(skewvoir): route charts through shared stats, delete duplicate Pearson"
```

---

### Task 5: Stabilise the wafer-to-wafer σ in PositionStack

**Why:** `views/PositionStack.vue:106-112` computes `variance = sumsq/n - m²` and clamps with `Math.max(0, …)` — the clamp exists precisely because that one-pass formula returns *negative* variance under floating-point cancellation. CD values are ~1e2 nm with ~1 nm site-to-site spread, exactly the regime where it loses precision. It is also population σ, while `anomaly/peer.ts` uses sample σ.

**Files:**
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/PositionStack.vue:88-114`

**Interfaces:**
- Consumes: `isValidRow` (Task 2); `mean`, `sampleStd` (Task 3); `parseChipXY` (existing).

- [ ] **Step 1: Collect per-site values, then reduce with the shared functions**

```ts
import { isValidRow } from '~/utils/msrRows'
import { mean as meanOf, sampleStd } from '~/utils/stats'

// Aggregate CD across every wafer in the set, per chip position, for the active
// parameter: composite mean + wafer-to-wafer sigma at each site.
//
// Values are collected first and reduced in two passes. The old one-pass
// sumsq/n - m^2 shortcut needed a Math.max(0, ...) clamp because it can return a
// NEGATIVE variance when the mean dominates the spread — which is exactly the CD
// regime (mean ~1e2 nm, spread ~1 nm).
const composite = computed(() => {
  const param = props.analysis.activeParam.value
  const acc = new Map<string, { x: number, y: number, values: number[] }>()
  for (const file of props.analysis.setFiles.value.values()) {
    for (const r of file.rows) {
      if (r.parameter !== param || !isValidRow(r)) continue
      const xy = parseChipXY(r.chip_number)
      if (!xy) continue
      const key = `${xy[0]},${xy[1]}`
      const e = acc.get(key) ?? { x: xy[0], y: xy[1], values: [] }
      e.values.push(r.cd_value)
      acc.set(key, e)
    }
  }
  const mean: [number, number, number][] = []
  const sigma: [number, number, number][] = []
  for (const e of acc.values()) {
    mean.push([e.x, e.y, Number(meanOf(e.values).toFixed(3))])
    sigma.push([e.x, e.y, Number(sampleStd(e.values).toFixed(3))])
  }
  return { mean, sigma }
})
```

`isValidRow` replaces the bare `r.mp_number < 0` check and additionally drops null/non-finite CDs.

- [ ] **Step 2: Verify**

Run: `npm --prefix front-dev-home test && npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`

Open PositionStack with a multi-MSR set (`?msrs=a,b,c`) and confirm the σ heatmap renders with an unchanged layout and a plausible scale.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/views/PositionStack.vue
git commit -m "fix(skewvoir): use stable two-pass sample sigma for wafer-to-wafer spread"
```

---

### Task 6: Extend leave-one-out anomaly detection to site level

**Why:** `utils/anomaly/` is the app's authoritative outlier model, but it has only ever run on MSR-level trend points (`useSkewvoirAnalysis.ts:180-186` scores `mean` and `spread` across a curated set). **It has never seen a single `cd_value`.** There is no per-site outlier detection within a wafer. This is the gap — filled by *reusing* `peerVerdicts`, not by inventing a second outlier definition beside it.

**Files:**
- Create: `front-dev-home/app/utils/anomaly/site.ts`
- Test: `front-dev-home/app/utils/anomaly/site.test.ts`

**Interfaces:**
- Consumes: `peerVerdicts` (`./peer.ts`); `AnomalyVerdict`, `MethodConfig`, `DEFAULT_METHOD_CONFIG` (`./types.ts`); `isValidRow`, `ValidMsrRow` (Task 2).
- Produces: `siteVerdicts(rows: MsrFileRow[], parameter: string, config?: MethodConfig): SiteVerdict[]`, `SiteVerdict = { row: ValidMsrRow, verdict: AnomalyVerdict }`.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/anomaly/site.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { siteVerdicts } from './site.ts'
import { DEFAULT_METHOD_CONFIG } from './types.ts'
import type { MsrFileRow } from '~/composables/useMsrFileApi'

const row = (over: Partial<MsrFileRow>): MsrFileRow => ({
  msr: 'M1', sequence: 1, chip_number: '0, 0', chip_coordinate: '', stage_coordinate: '',
  dnum_group: '0, -1', mp_number: 1, parameter: 'CD_TOP', cd_value: 100,
  no_of_mp_image: 1, mp_image_name_01: '', meas_condition_mag: 250030,
  meas_condition_vac: 500, meas_condition_pixel: '512,512', addressing1_score: 868,
  addressing2_score: 646, measurement_score: 165, meas_method: 'Score',
  object_type: 'MP', meas_kind: 'Multi Point',
  ...over
})

test('a site far from its peers is abnormal; the rest are normal', () => {
  // Peers sit at 100; one site at 130 is +30% off the LOO mean (abnormalPct = 20).
  const rows = [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: 100 }),
    row({ sequence: 3, cd_value: 100 }),
    row({ sequence: 4, cd_value: 130 })
  ]
  const out = siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(out.length, 4)
  assert.equal(out[3]!.verdict.severity, 'abnormal')
  assert.equal(out[0]!.verdict.severity, 'normal')
})

test('unmeasured rows are excluded — they cannot be judged nor judge others', () => {
  const rows = [
    row({ sequence: 1, cd_value: 100 }),
    row({ sequence: 2, cd_value: 100 }),
    row({ sequence: 3, cd_value: 100 }),
    row({ sequence: 4, cd_value: null, mp_number: -1 })
  ]
  const out = siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(out.length, 3)
  assert.ok(out.every(o => o.verdict.severity === 'normal'))
})

test('other parameters are ignored', () => {
  const rows = [
    row({ sequence: 1, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 3, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 4, parameter: 'CD_BOTTOM', cd_value: 5 })
  ]
  assert.equal(siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG).length, 3)
})

test('too few sites yields insufficient, not normal', () => {
  const rows = [row({ sequence: 1, cd_value: 100 }), row({ sequence: 2, cd_value: 100 })]
  const out = siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(out.length, 2)
  assert.ok(out.every(o => o.verdict.status === 'insufficient'))
})

test('the verdict is paired back to its originating row', () => {
  const rows = [
    row({ sequence: 1, chip_number: '1, 1', cd_value: 100 }),
    row({ sequence: 2, chip_number: '2, 2', cd_value: 100 }),
    row({ sequence: 3, chip_number: '3, 3', cd_value: 100 }),
    row({ sequence: 4, chip_number: '9, 9', cd_value: 130 })
  ]
  const out = siteVerdicts(rows, 'CD_TOP', DEFAULT_METHOD_CONFIG)
  assert.equal(out.find(o => o.verdict.severity === 'abnormal')!.row.chip_number, '9, 9')
})

test('empty input yields empty output', () => {
  assert.deepEqual(siteVerdicts([], 'CD_TOP', DEFAULT_METHOD_CONFIG), [])
})
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `npm --prefix front-dev-home test`
Expected: FAIL — `Cannot find module './site.ts'`.

- [ ] **Step 3: Write the implementation**

Create `front-dev-home/app/utils/anomaly/site.ts`:

```ts
// front-dev-home/app/utils/anomaly/site.ts
// Site-level abnormality: judge each measurement site against the OTHER sites on
// the same wafer, for one parameter.
//
// This is deliberately a thin adapter over peerVerdicts rather than a new
// algorithm. The app must have exactly one meaning for "outlier" — leave-one-out
// against peers, with `status` (did we evaluate?) held separate from `severity`
// (how bad?). An independent IQR-fence verdict living beside this one would let
// two panels disagree about the same site.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { ValidMsrRow } from '~/utils/msrRows'
import { isValidRow } from '~/utils/msrRows'
import type { AnomalyVerdict, MethodConfig } from './types.ts'
import { DEFAULT_METHOD_CONFIG } from './types.ts'
import { peerVerdicts } from './peer.ts'

export interface SiteVerdict {
  row: ValidMsrRow
  verdict: AnomalyVerdict
}

export const siteVerdicts = (
  rows: MsrFileRow[],
  parameter: string,
  config: MethodConfig = DEFAULT_METHOD_CONFIG
): SiteVerdict[] => {
  // Gate FIRST. An unmeasured row admitted here would distort the peer band and
  // could mask a genuine outlier.
  const sites = rows.filter((r): r is ValidMsrRow => r.parameter === parameter && isValidRow(r))
  if (sites.length === 0) return []

  const verdicts = peerVerdicts(sites.map(r => r.cd_value), {
    config,
    metric: 'site',
    tag: '사이트'
  })

  return sites.map((row, i) => ({ row, verdict: verdicts[i]! }))
}
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `npm --prefix front-dev-home test`
Expected: PASS — 6 new tests; the existing `anomaly/{score,peer,combine,types}.test.ts` suites stay green.

- [ ] **Step 5: Gates and commit**

Run: `npm --prefix front-dev-home run typecheck && npm --prefix front-dev-home run lint`

```bash
git add front-dev-home/app/utils/anomaly/site.ts front-dev-home/app/utils/anomaly/site.test.ts
git commit -m "feat(skewvoir): extend leave-one-out anomaly detection to site level"
```

> `siteVerdicts` is intentionally **not wired into any view here** — Phase A ends with zero layout change. Phase B consumes it for the Distribution "outlier candidates" list and the Gallery "review relevance" sort. It ships now, tested, so Phase B builds on proven math.

---

## Exit Criteria

- [ ] `python -m pytest -q` — green.
- [ ] `npm --prefix front-dev-home test` — green, including every pre-existing test.
- [ ] `npm --prefix front-dev-home run typecheck` — clean.
- [ ] `npm --prefix front-dev-home run lint` — clean.
- [ ] `npm --prefix front-dev-home run build` — succeeds.
- [ ] `grep -rn "mp_number < 0" front-dev-home/app/` — **no matches** (every call site goes through `isValidRow`).
- [ ] `grep -rn "cd_value ?? 0\|cd_value!" front-dev-home/app/` — **no matches** (no fabricated zeros).
- [ ] Live payload carries `exe_detail_info`, `alignment`, `spm_dict`, and at least one `"cd_value": null` row.
- [ ] Browser: all five views render with unchanged layout under both `/ebeam/cd-sem/skewvoir/analysis` and `/ebeam/hv-sem/skewvoir/analysis`.
- [ ] The diff touches no file outside the File Structure table. **Note: this worktree has 7 pre-existing modified files from the layout pass — confirm none were clobbered.**

## Explicitly Out of Scope (Phase B)

Dashboard rebuild as "Measurement Overview"; removing the hardcoded `HEALTH · LAST 31H` block (`workspace/LeftRail.vue:90`, fed by `useState(..., () => ({ scans: 24, outliers: 15 }))` at `useSkewvoirWorkspace.ts:59`); comparison-set selector; focus-minus-composite delta map; FDC drift trend; gallery sort/filter/compare; CD↔FDC correlation; and the new panels the Phase 0 data unlocks — acquisition context (`exe_detail_info`) and alignment evidence (`alignment`).

`spm_dict` is **not** a Phase B candidate. It is a shape-only placeholder with no signal in it; do not build a panel on it until the office backend supplies the real waveform.
