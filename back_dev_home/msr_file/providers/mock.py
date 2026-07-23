"""msr_file — MSR raw measurement detail mock for 스큐보아 (Skewvoir).

Spec: docs/datatables/msr_file.txt + docs/datatables/msr_file_pickle.txt
Each row = "하나의 MSR 안에서 특정 sequence, 특정 parameter로 측정된 1개 측정값".

Beyond per-measurement CD values, the MinIO-parsed pickle carries FDC telemetry
(fixed_fdc / dynamic_fdc) that lets 스큐보아 cross-check CD drift against tool
condition. We model the abnormal-behavior FDC params called out in
docs/datatables/hardware.txt (Brightness/Contrast, Stigma X·Y, OBJECT_SEM·VRD
defocus, LFB imageshift / alignment stage-drift).

The data is not generated independently: it is derived from a parent meas_hist
row (its msr / class_name / total_images). Generation is deterministic from the
md5(msr) seed, so the same MSR always opens to identical detail data with no DB
(Phase 1) — this mirrors the Python prototype the feature was ported from.

A single per-MSR ``health`` scalar (0 = nominal, 1 = strongly abnormal) biases
BOTH the CD drift and the FDC drift, so an unhealthy tool shows correlated CD ↔
FDC excursions — that correlation is exactly what the skewvoir analysis surfaces.

Two columns are renamed from the pickle spec because the literal names are not
usable as Python identifiers in a TypedDict: `class` -> `class_name` (keyword)
and `object` -> `object_type` (shadows the builtin). The wire format uses the
renamed keys and the frontend consumes them under those names.

`cd_value` is NULLABLE (docs §df_result_data). It is None exactly when
mp_number < 0 — a point with metadata but no data has no measurement. Every
consumer must gate on this; see app/utils/msrRows.ts.

UNKNOWN-SAFE SIGNATURE BOUNDARY (Task 2). The response DELIBERATELY carries no
``site_layout_hash``, ``recipe_revision``, ``coordinate_transform_version`` or
``sequence_timestamp``. The frontend compatibility signature
(app/utils/skewvoirAnalysis/compatibility.ts) reads those as UNKNOWN and never
fabricates them, which is what forces layout-dependent readiness (multi-MSR
delta, site variability, same-site gallery) to ``unavailable`` in Phase 1. Note
also that the per-MSR wafer geometry (``_wafer_geometry``) is seeded off
md5(msr): there is NO shared layout identity across MSRs, so a layout hash could
not be honestly emitted here even if the field existed. Do NOT add any of these
fields to make a screen result line up — connect them in the office adapter
instead (see providers/office.py). The absence is pinned by
tests/test_contract.py.
"""

import hashlib
import math
import random
from functools import lru_cache
from statistics import fmean, pstdev, stdev
from typing import NamedTuple, TypedDict

from back_dev_home.meas_hist.contracts import MeasHistRow
from back_dev_home.meas_hist.providers.mock import find_meas_hist_by_msr


__all__ = [
    "MsrFileRow",
    "MsrParamSummary",
    "FdcParamSummary",
    "ExeDetailInfo",
    "AlignmentInfo",
    "SpmDict",
    "MsrFileResponse",
    "get_msr_file",
]


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


class MsrParamSummary(TypedDict):
    parameter: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    unit: str


class FdcParamSummary(TypedDict):
    name: str
    category: str
    category_label: str
    unit: str
    nominal: float
    mean: float
    std: float
    min: float
    max: float
    # |mean - nominal| in units of the normal sigma; the abnormality magnitude.
    drift_sigma: float
    status: str  # ok | warning | bad


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


class MsrFileResponse(TypedDict):
    msr: str
    class_name: str
    total_images: int
    sequence_count: int
    health: float
    parameters: list[MsrParamSummary]
    fdc_params: list[FdcParamSummary]
    # Per-MSR scalar FDC (docs §fixed_fdc): one value for the whole measurement.
    fixed_fdc: dict[str, float]
    # Per-sequence FDC (docs §dynamic_fdc): keyed by sequence string → {param: value}.
    dynamic_fdc: dict[str, dict[str, float]]
    exe_detail_info: ExeDetailInfo
    alignment: AlignmentInfo
    spm_dict: SpmDict
    total: int
    rows: list[MsrFileRow]


# Measurement parameter candidates per measurement class (spec §"Class별 parameter 후보").
PARAMETER_MAPPING: dict[str, tuple[str, ...]] = {
    "CD": ("CD_TOP", "CD_BOTTOM", "CD_MIDDLE", "SIDEWALL_ANGLE"),
    "OVL": ("OVERLAY_X", "OVERLAY_Y", "OVERLAY_R", "OVERLAY_THETA"),
    "PROF": ("HEIGHT", "SIDEWALL_ANGLE", "TOP_WIDTH", "BOTTOM_WIDTH"),
    "ROUGH": ("LWR", "LER", "RMS_ROUGHNESS", "CORRELATION_LENGTH"),
    "THICK": ("THICKNESS", "UNIFORMITY", "REFRACTIVE_INDEX"),
    "GATE": ("GATE_CD", "GATE_HEIGHT", "GATE_PROFILE"),
    "CONTACT": ("CONTACT_CD", "CONTACT_DEPTH", "ASPECT_RATIO"),
    "VIA": ("VIA_CD", "VIA_DEPTH", "TAPER_ANGLE"),
    "METAL": ("LINE_WIDTH", "LINE_HEIGHT", "PITCH", "SPACE_WIDTH"),
}

# Fallback parameters for classes with no measurement mapping (spec §"기타 class").
FALLBACK_PARAMS: tuple[str, ...] = ("WAFER", "EDGE", "LEVEL")

# meas_hist.class_name is a process layer (ADI/AEI/CNT…), not a measurement
# class. Translate it onto a PARAMETER_MAPPING key so 스큐보아 shows meaningful
# parameters; unmapped layers (DEF, QC, …) fall through to FALLBACK_PARAMS.
CLASS_ALIAS: dict[str, str] = {
    "ADI": "CD",
    "AEI": "CD",
    "OVL": "OVL",
    "GATE": "GATE",
    "CNT": "CONTACT",
    "EDGE": "PROF",
}


def _seed(msr: str, offset: int = 0) -> int:
    digest = hashlib.md5(msr.encode("utf-8")).hexdigest()
    return (int(digest[:8], 16) + offset) % (2 ** 31)


# ── Wafer geometry (physical, coherent across chip_number / stage / wafer_size) ──
# A 300 mm wafer. `chip_number` is the die INDEX (col, row) centred on the wafer;
# `stage_coordinate` is the physical position in nm from a corner origin, so the
# wafer centre sits at (wafer_size/2, wafer_size/2). Die pitch is derived from the
# array count so pitch * array ≈ the wafer diameter — the three fields can never
# disagree (docs/datatables/msr_file_pickle.txt).
WAFER_SIZE_MM = 300
NM_PER_MM = 1_000_000
_WAFER_NM = WAFER_SIZE_MM * NM_PER_MM
_WAFER_CENTER_NM = _WAFER_NM // 2
_WAFER_RADIUS_NM = _WAFER_NM / 2
_EDGE_EXCLUSION_NM = 3 * NM_PER_MM  # dies whose centre is < 3 mm from the edge


class WaferGeom(NamedTuple):
    cols: int
    rows: int
    pitch_x_nm: int
    pitch_y_nm: int


@lru_cache(maxsize=256)
def _wafer_geometry(msr: str) -> WaferGeom:
    """Per-MSR die array + pitch. Pitch = wafer diameter / array count, so the
    array physically spans the wafer and stage coordinates land inside it."""
    rng = random.Random(_seed(msr, 313))
    cols, rows_n = rng.randint(38, 46), rng.randint(52, 62)
    return WaferGeom(cols, rows_n, round(_WAFER_NM / cols), round(_WAFER_NM / rows_n))


def _die_center_nm(col: int, row: int, geom: WaferGeom) -> tuple[float, float]:
    """Physical centre (nm, corner origin) of die (col, row)."""
    return (
        _WAFER_CENTER_NM + col * geom.pitch_x_nm,
        _WAFER_CENTER_NM + row * geom.pitch_y_nm,
    )


@lru_cache(maxsize=256)
def _measured_dies(msr: str) -> tuple[tuple[int, int], ...]:
    """Die (col, row) indices whose centre lies within the wafer (minus an edge
    exclusion), shuffled so a sequence→die walk spreads across the whole wafer
    instead of marching down one column."""
    geom = _wafer_geometry(msr)
    limit = _WAFER_RADIUS_NM - _EDGE_EXCLUSION_NM
    dies = [
        (col, row)
        for col in range(-(geom.cols // 2), geom.cols // 2 + 1)
        for row in range(-(geom.rows // 2), geom.rows // 2 + 1)
        if math.hypot(col * geom.pitch_x_nm, row * geom.pitch_y_nm) <= limit
    ]
    random.Random(_seed(msr, 971)).shuffle(dies)
    return tuple(dies)


# Parameter name substrings -> (value range, unit). First match wins, so range
# and unit stay defined together and can't drift apart. Order mirrors the
# original precedence (CD/WIDTH before the layer-specific names).
_PARAM_SPECS: tuple[tuple[tuple[str, ...], float, float, str], ...] = (
    (("CD", "WIDTH"), 15.0, 45.0, "nm"),
    (("HEIGHT", "DEPTH"), 50.0, 200.0, "nm"),
    (("ANGLE",), 85.0, 95.0, "deg"),
    (("OVERLAY",), -5.0, 5.0, "nm"),
    (("ROUGH",), 1.0, 5.0, "nm"),
    (("THICK",), 10.0, 100.0, "nm"),
    (("PITCH", "SPACE", "LINE", "LWR", "LER"), 10.0, 50.0, "nm"),
)
_DEFAULT_SPEC: tuple[float, float, str] = (10.0, 50.0, "")


def _param_spec(parameter: str) -> tuple[float, float, str]:
    for tokens, lo, hi, unit in _PARAM_SPECS:
        if any(token in parameter for token in tokens):
            return lo, hi, unit
    return _DEFAULT_SPEC


# ── FDC modelling ────────────────────────────────────────────────────────────
# Abnormal-behavior FDC params (docs/datatables/hardware.txt). `gain` is how far
# a fully-unhealthy MSR (health=1) pushes the param off `nominal`, expressed in
# absolute units; `sigma` is the normal run-to-run noise. A param whose drift
# exceeds ~2σ is "warning", ~3.5σ is "bad" — the same convention FDC dashboards use.
class FdcSpec(NamedTuple):
    nominal: float
    sigma: float
    unit: str
    category: str
    gain: float


DYNAMIC_FDC_SPECS: dict[str, FdcSpec] = {
    "Brightness": FdcSpec(128.0, 3.0, "DN", "image", 20.0),
    "Contrast": FdcSpec(64.0, 2.0, "DN", "image", 10.4),
    "StigmaX": FdcSpec(0.0, 0.40, "%", "astigmatism", 2.5),
    "StigmaY": FdcSpec(0.0, 0.40, "%", "astigmatism", 2.5),
    "ObjectSem": FdcSpec(2400.0, 1.5, "V", "defocus", 7.1),  # OBJECT_SEM defocus
    "Vrd": FdcSpec(300.0, 1.0, "V", "defocus", 4.4),  # VRD defocus
    "ImageShiftX": FdcSpec(0.0, 1.2, "nm", "stage_drift", 8.0),  # LFB imageshift X
    "ImageShiftY": FdcSpec(0.0, 1.2, "nm", "stage_drift", 8.0),  # LFB imageshift Y
    "Alignment2X": FdcSpec(0.0, 0.8, "nm", "stage_drift", 4.5),  # LFB alignment 2X
    "Alignment2Y": FdcSpec(0.0, 0.8, "nm", "stage_drift", 4.5),  # LFB alignment 2Y
}

FIXED_FDC_SPECS: dict[str, FdcSpec] = {
    "SEMCondVsup": FdcSpec(1500.0, 2.0, "V", "source", 7.0),
    "ESCD": FdcSpec(23.40, 0.10, "degC", "echuck", 1.6),
    "Lux": FdcSpec(95.0, 1.0, "%", "source", 5.0),
    "Alignment1X": FdcSpec(0.0, 0.5, "nm", "alignment", 3.2),
    "Alignment1Y": FdcSpec(0.0, 0.5, "nm", "alignment", 3.2),
    "Alignment3X": FdcSpec(0.0, 0.5, "nm", "alignment", 3.2),
    "Alignment3Y": FdcSpec(0.0, 0.5, "nm", "alignment", 3.2),
}

FDC_CATEGORY_LABELS: dict[str, str] = {
    "image": "이미지 품질",
    "astigmatism": "비점수차 (Stigma)",
    "defocus": "디포커스",
    "stage_drift": "스테이지 드리프트",
    "source": "전자총/소스",
    "echuck": "E-Chuck",
    "alignment": "정렬",
}

_MEAS_METHODS: tuple[str, ...] = ("Score", "Width", "Edge")
_OBJECT_TYPES: tuple[str, ...] = ("MP", "Line", "Space")

_MEAS_KINDS: tuple[str | None, ...] = ("Multi Point", "Single Point", None)
_MAGNIFICATIONS: tuple[int, ...] = (200015, 250030, 250044)
_VOLTAGES: tuple[int, ...] = (500, 800, 1000)
_PIXELS: tuple[str, ...] = ("512,512", "1024,1024")
_PROCESS_BY_CLASS: dict[str, str] = {
    "ADI": "PHOTO", "AEI": "ETCH", "OVL": "PHOTO", "GATE": "ETCH",
    "CNT": "ETCH", "EDGE": "ETCH", "QC": "METRO", "DEF": "METRO",
}
SPM_POINTS = 32


def _exe_detail_info(msr: str, parent: MeasHistRow | None, class_name: str) -> ExeDetailInfo:
    """Acquisition context. Sourced from the parent meas_hist row wherever
    possible so the MSR detail can never contradict the measurement history it
    hangs off; only the wafer geometry (absent upstream) is seeded."""
    rng = random.Random(_seed(msr, 313))
    recipe_name = parent["recipe_name"] if parent else f"{class_name}_UNKNOWN"
    lot_id = parent["lot_id"] if parent else f"LOT{_seed(msr) % 1_000_000:06d}"
    idp_name = parent["idp_name"] if parent else f"/Recipe/{class_name}/{recipe_name}.idp"
    idw_name = parent["idw_name"] if parent else f"/Recipe/{class_name}/{recipe_name}.idw"

    # Array + pitch come from the shared geometry so chip_array, chip_pitch and
    # wafer_size stay mutually consistent with the chip_number / stage columns.
    geom = _wafer_geometry(msr)

    return ExeDetailInfo(
        class_name=class_name,
        recipe_name=recipe_name,
        idp_name=idp_name,
        lot_id=lot_id,
        process=_PROCESS_BY_CLASS.get(class_name.upper(), "METRO"),
        # 25 wafers to a lot; the slot is stable per MSR.
        wafer_id=f"{lot_id}_{(_seed(msr, 41) % 25) + 1:02d}",
        idw_name=idw_name,
        chip_array=f"{geom.cols},{geom.rows}",
        chip_pitch=f"{geom.pitch_x_nm},{geom.pitch_y_nm}",
        wafer_size=str(WAFER_SIZE_MM),
        # Origin at the wafer centre (corner-origin system: centre = size/2).
        map_offset=f"{rng.randrange(-3_000_000, 3_000_000)},{rng.randrange(-3_000_000, 3_000_000)}",
        map_origin=f"{_WAFER_CENTER_NM},{_WAFER_CENTER_NM}",
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


def _health(msr: str) -> float:
    """Per-MSR abnormality in [0, 1]; squared so most MSRs sit near nominal."""
    raw = (_seed(msr, 7919) % 1000) / 1000.0
    return round(raw * raw, 3)


def _fdc_status(drift_sigma: float) -> str:
    if drift_sigma >= 3.5:
        return "bad"
    if drift_sigma >= 2.0:
        return "warning"
    return "ok"


class CdField(NamedTuple):
    mean: float
    radial_amp: float  # centre→edge delta (absolute units)
    site_sigma: float
    lo: float
    hi: float


def _cd_field(msr: str, parameter: str, health: float) -> CdField:
    """Per-(MSR, parameter) wafer CD model. Sites cluster tightly around ``mean``
    with a smooth centre→edge trend (``radial_amp``) and small run-to-run noise
    (``site_sigma``), so leave-one-out outlier detection flags only genuine
    excursions — not most of the wafer. ``mean`` rises with ``health`` so a
    tool's CD tracks its FDC excursion across the multi-measurement trend."""
    lo, hi, _ = _param_spec(parameter)
    span = hi - lo
    rng = random.Random(_seed(f"{msr}:{parameter}", 431))
    mean = lo + span * rng.uniform(0.42, 0.58) + span * 0.12 * health
    radial_amp = span * rng.uniform(0.03, 0.06) * (1.0 if rng.random() < 0.5 else -1.0)
    return CdField(mean=mean, radial_amp=radial_amp, site_sigma=span * 0.012, lo=lo, hi=hi)


def _cd_value(
    field: CdField,
    radius_norm: float,
    health: float,
    seq_frac: float,
    rng: random.Random,
    outlier_dev: float,
) -> float:
    """One site's CD: wafer mean + radial trend + noise, plus a mild within-run
    tilt for unhealthy tools and an injected deviation for the few flagged sites.
    Clamped to the parameter's physical range."""
    val = field.mean + field.radial_amp * radius_norm + rng.gauss(0, field.site_sigma)
    val += field.mean * 0.03 * health * (2 * seq_frac - 1)  # slight late-run tilt
    val += outlier_dev
    return round(min(field.hi, max(field.lo, val)), 2)


def _unit(parameter: str) -> str:
    return _param_spec(parameter)[2]


def _resolve_params(class_name: str) -> tuple[str, ...]:
    measurement_class = CLASS_ALIAS.get(class_name.upper(), class_name.upper())
    return PARAMETER_MAPPING.get(measurement_class, FALLBACK_PARAMS)


def _build_rows(
    msr: str, class_name: str, total_images: int, health: float, offset: int = 0
) -> list[MsrFileRow]:
    seed = _seed(msr, offset)
    rng = random.Random(seed)

    params_pool = _resolve_params(class_name)
    # num_measurements stays under total_images // 2 so detail never claims
    # more measurement points than the parent measurement produced images.
    num_measurements = min(rng.randint(20, 80), max(1, total_images // 2))
    num_params = min(rng.randint(1, 3), len(params_pool))
    selected_params = rng.sample(params_pool, num_params)

    geom = _wafer_geometry(msr)
    dies = _measured_dies(msr)
    rows: list[MsrFileRow] = []
    span = max(1, num_measurements - 1)

    # Per-parameter wafer CD model + a handful of injected outliers, so most sites
    # sit tight (few flags) while the 이상 UI still has genuine excursions to show.
    fields = {p: _cd_field(msr, p, health) for p in selected_params}
    measured_seqs = [s for s in range(1, num_measurements + 1) if s % 20 != 0]
    outliers_by_param: dict[str, dict[int, float]] = {}
    for p in selected_params:
        prng = random.Random(_seed(f"{msr}:{p}:outliers", 733))
        picks = prng.sample(measured_seqs, min(prng.choice((0, 0, 1, 1, 2)), len(measured_seqs)))
        outliers_by_param[p] = {
            s: (1.0 if prng.random() < 0.5 else -1.0) * abs(fields[p].mean) * prng.uniform(0.24, 0.40)
            for s in picks
        }

    for sequence in range(1, num_measurements + 1):
        seq_frac = (sequence - 1) / span

        # Die index (chip_number) + its physical stage position (nm, corner
        # origin). A small within-die offset keeps stage_coordinate from being an
        # exact multiple of the pitch — the point is measured somewhere in the die.
        chip_x, chip_y = dies[(sequence - 1) % len(dies)]
        chip_number = f"{chip_x},{chip_y}"
        center_x_nm, center_y_nm = _die_center_nm(chip_x, chip_y, geom)
        off_x = rng.uniform(-0.3, 0.3) * geom.pitch_x_nm
        off_y = rng.uniform(-0.3, 0.3) * geom.pitch_y_nm
        stage_coordinate = f"{int(center_x_nm + off_x)},{int(center_y_nm + off_y)}"
        chip_coordinate = f"{int(center_x_nm)},{int(center_y_nm)}"
        # Physical radius from wafer centre, normalised to the wafer radius, drives
        # the centre→edge CD trend seen in the radius plot.
        radius_norm = math.hypot(
            chip_x * geom.pitch_x_nm + off_x, chip_y * geom.pitch_y_nm + off_y
        ) / _WAFER_RADIUS_NM

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
                cd_value=None if empty else _cd_value(
                    fields[parameter], radius_norm, health, seq_frac, rng,
                    outliers_by_param[parameter].get(sequence, 0.0),
                ),
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

    return rows


def _build_fdc(
    msr: str, sequences: list[int], health: float
) -> tuple[dict[str, float], dict[str, dict[str, float]], list[FdcParamSummary]]:
    """Build fixed + dynamic FDC and a per-param summary.

    Each param drifts off nominal proportional to ``health`` (sign fixed per
    param so the trend is coherent), with slow ramp across the run plus Gaussian
    run-to-run noise.
    """
    fixed_fdc: dict[str, float] = {}
    for name, spec in FIXED_FDC_SPECS.items():
        rng = random.Random(_seed(f"{msr}:{name}", 101))
        sign = 1.0 if rng.random() < 0.5 else -1.0
        fixed_fdc[name] = round(spec.nominal + sign * spec.gain * health + rng.gauss(0, spec.sigma), 3)

    dynamic_fdc: dict[str, dict[str, float]] = {}
    summaries: list[FdcParamSummary] = []
    span = max(1, len(sequences) - 1)

    for name, spec in DYNAMIC_FDC_SPECS.items():
        rng = random.Random(_seed(f"{msr}:{name}", 202))
        sign = 1.0 if rng.random() < 0.5 else -1.0
        values: list[float] = []
        for i, seq in enumerate(sequences):
            seq_frac = i / span
            drift = spec.gain * health * (0.35 + 0.65 * seq_frac)
            value = round(spec.nominal + sign * drift + rng.gauss(0, spec.sigma), 3)
            values.append(value)
            dynamic_fdc.setdefault(str(seq), {})[name] = value

        mean = fmean(values)
        std = pstdev(values) if len(values) > 1 else 0.0
        drift_sigma = round(abs(mean - spec.nominal) / spec.sigma, 2)
        summaries.append(FdcParamSummary(
            name=name,
            category=spec.category,
            category_label=FDC_CATEGORY_LABELS[spec.category],
            unit=spec.unit,
            nominal=spec.nominal,
            mean=round(mean, 3),
            std=round(std, 3),
            min=round(min(values), 3),
            max=round(max(values), 3),
            drift_sigma=drift_sigma,
            status=_fdc_status(drift_sigma),
        ))

    return fixed_fdc, dynamic_fdc, summaries


def _summaries(rows: list[MsrFileRow]) -> list[MsrParamSummary]:
    """Per-parameter descriptive stats over MEASURED rows only.

    These summaries feed the Data Summary table, the 3-sigma column AND the
    time-series anomaly verdicts, so a single unmeasured row leaking in here
    propagates into a wrong watch/abnormal call. Mirrors the frontend gate in
    app/utils/msrRows.ts::isMeasuredRow.
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

    # FDC is sampled once per sequence, so collapse the (sequence × parameter)
    # rows down to the distinct sequence list before building telemetry.
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
        rows=rows
    )
