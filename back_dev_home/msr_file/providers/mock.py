"""msr_file — MSR raw measurement detail mock for 스큐보아 (Skewvoir).

Spec: docs/datatables/msr_file_pickle.txt
Each row is one measurement, and one measurement owns exactly one sequence
number: row 1건 = 측정 1건 = sequence 1개입니다 (office 확인 2026-07-27,
docs/datatables/msr_file_pickle.txt). 같은 지점에서 여러 parameter가 측정되어도
parameter마다 서로 다른 sequence를 가지므로, row와 sequence는 항상 1:1로
대응합니다 — 예전 표현("특정 sequence, 특정 parameter로 측정된 1개 측정값")은
sequence와 parameter를 각각 독립된 축처럼 보이게 해, 실제로는 row 하나에
sequence 하나만 대응한다는 사실을 가렸습니다.

Beyond per-measurement CD values, the MinIO-parsed pickle carries FDC telemetry
(fixed_fdc / dynamic_fdc) that lets 스큐보아 cross-check CD drift against tool
condition. We model the abnormal-behavior FDC params called out in
docs/datatables/hardware.txt (Brightness/Contrast, Stigma X·Y, OBJECT_SEM·VRD
defocus, LFB imageshift / alignment stage-drift), plus two deliberately
CONSTANT setpoint channels (VT, ESCdV — see DYNAMIC_FDC_SPECS). Real tools
stream flat channels alongside the varying ones (user-confirmed 2026-08-07),
and a mock without any would let every 평가 불가/숨기기 code path in 스큐보아
go untested at home — which is how the 2026-08-07 matrix-overflow bug shipped.

The data is not generated independently: it is derived from a parent meas_hist
row (its msr / class_name / total_images). Generation is deterministic from the
md5(msr) seed, so the same MSR always opens to identical detail data with no DB
(Phase 1) — this mirrors the Python prototype the feature was ported from.

A single per-MSR ``health`` scalar (0 = nominal, 1 = strongly abnormal) biases
BOTH the CD drift and the FDC drift, so an unhealthy tool shows correlated CD ↔
FDC excursions — that correlation is exactly what the skewvoir analysis surfaces.

THREE SEED IDENTITIES, NOT ONE. Determinism per-MSR is necessary but not
sufficient: some facts belong to the recipe, not to the run. Which identity a
property is seeded from IS the domain model here, so it is stated once:

    program (recipe)  WHAT is measured — the parameter set, the settling-shot
                      count, the measurement-point count, the CD target the
                      recipe aims at, and WHERE it is measured: the wafer map
                      (die array, pitch, origin, grid offset) and the die walk
                      over it. Every run of one recipe agrees on these.
    tool (eqp_id)     HOW this tool reads a given feature — a fixed measurement
                      bias. This is the tool skew the analysis exists to find,
                      so it is deliberately NOT keyed on the recipe: one tool
                      reads the same way across every program it runs.
    run (msr)         What is genuinely per-execution — health, site noise, the
                      within-die jitter on each measured point, injected
                      outliers, quality scores, images.

The wafer map joined the program layer on 2026-08-08; it was the last property
still seeded from the msr. The office's own site_layout_hash — sha1 over
chip_array / chip_pitch / wafer_size / map_origin plus the site set
(docs/datatables/msr_file_pickle.txt) — presupposes it: a layout digest that
changed every run could not identify a shared layout, which is its only job.
Keyed on the msr, two runs of ADI_CD_BIAS_001 reported 45x53 and 40x56 with
ZERO sites in common, so 분석 준비 상태 read same-site analysis as structurally
impossible rather than merely office-gated.

Seeding a program-level fact from the msr is the bug this layering replaces. It
made every run of one recipe measure a different, randomly drawn parameter
subset, so 스큐보아's multi-MSR Time-Series excluded most of a selected set as
`metadata-missing` (app/utils/skewvoirAnalysis/compatibility.ts) and the trend
it did plot was uncorrelated noise. See ``_program_params`` and ``_cd_field``.

A run with NO parent meas_hist row belongs to no recipe, so it is its own
program (program key = its msr). That is the honest answer — with no parent
there is no recipe to belong to — and it keeps parentless synthetic MSRs
varying, which is what the contract tests use to exercise both settling-shot
paths.

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
    # All image files of the row, pickle column order (mp_image_name_01.._NN,
    # len == no_of_mp_image). Multi-image rows model HV-SEM, whose tools shoot
    # several images per targeting point and suffix the shared stem (-U/-T/-M/-L,
    # user-confirmed 2026-08-08). Mirrors contracts.MsrFileRow.
    mp_image_names: list[str]
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
    # The measuring tool's IPv4 address, from the parent meas_hist row — the
    # third leg of the (eqp_ip, class_name, msr) address msr_image is fetched
    # by. "" when the MSR has no parent row. Mirrors contracts.MsrFileResponse.
    eqp_ip: str
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
    # Die-grid offset (nm). The SINGLE source for both the stage_coordinate this
    # module generates and the map_offset it reports, so the two can never
    # disagree -- the bug this replaces was a random map_offset that nothing
    # encoded, which only looked fine because nothing read it.
    offset_x_nm: int
    offset_y_nm: int


@lru_cache(maxsize=256)
def _wafer_geometry(program_key: str) -> WaferGeom:
    """Die array, pitch and die-grid offset — a PROGRAM property, keyed on
    program_key (the parent's recipe_name, else the msr). Pitch = wafer diameter
    / array count, so the array physically spans the wafer and stage coordinates
    land inside it. The offset is kept under 0.3*pitch: a real, visible shift
    that still never pushes a die off the wafer.

    Keyed on the recipe, not the run, because a recipe is a fixed measurement
    program: two runs of it step through the same wafer map. The office says so
    structurally — site_layout_hash is the sha1 of chip_array / chip_pitch /
    wafer_size / map_origin plus the site set (docs/datatables/msr_file_pickle.txt),
    and a hash that changed every run could never identify a shared layout, which
    is the only thing it exists to do.

    It was keyed on the msr until 2026-08-08, which made every run of one recipe
    report a different wafer map — two runs of ADI_CD_BIAS_001 came out as
    45x53 and 40x56 with ZERO sites in common. That taught the frontend's
    cross-MSR compatibility work something false about the real data: it made
    same-site analysis look structurally impossible rather than merely
    office-gated. This is the last of the program properties to be moved;
    _program_params / _program_step_count / _program_dummy_count were already
    keyed this way."""
    rng = random.Random(_seed(program_key, 313))
    cols, rows_n = rng.randint(38, 46), rng.randint(52, 62)
    pitch_x, pitch_y = round(_WAFER_NM / cols), round(_WAFER_NM / rows_n)
    offset_x = round(rng.uniform(-0.3, 0.3) * pitch_x)
    offset_y = round(rng.uniform(-0.3, 0.3) * pitch_y)
    return WaferGeom(cols, rows_n, pitch_x, pitch_y, offset_x, offset_y)


def _die_center_nm(col: int, row: int, geom: WaferGeom) -> tuple[float, float]:
    """Physical centre (nm, corner origin) of die (col, row), on the die grid
    shifted off the wafer centre by the map_offset this MSR reports."""
    return (
        _WAFER_CENTER_NM + geom.offset_x_nm + col * geom.pitch_x_nm,
        _WAFER_CENTER_NM + geom.offset_y_nm + row * geom.pitch_y_nm,
    )


@lru_cache(maxsize=256)
def _measured_dies(program_key: str) -> tuple[tuple[int, int], ...]:
    """Die (col, row) indices whose centre lies within the wafer (minus an edge
    exclusion), shuffled so a sequence→die walk spreads across the whole wafer
    instead of marching down one column.

    Eligibility is measured on the SHIFTED grid (via _die_center_nm), not on
    col*pitch: the die-grid offset moves every die by up to 0.3*pitch, so an
    unshifted test would eat into the edge exclusion and let a die's measured
    point land off the wafer once the within-die jitter is added on top.

    Keyed on program_key with the geometry it reads, so the ORDER is a program
    property too: step N of one recipe lands on the same die in every run, which
    is what makes two runs' site sets comparable at all. Runs whose step budget
    differs (the total_images clamp in _build_rows) walk a shorter prefix of the
    same list — a partial overlap, not a different wafer map."""
    geom = _wafer_geometry(program_key)
    limit = _WAFER_RADIUS_NM - _EDGE_EXCLUSION_NM
    dies = [
        (col, row)
        for col in range(-(geom.cols // 2), geom.cols // 2 + 1)
        for row in range(-(geom.rows // 2), geom.rows // 2 + 1)
        if math.hypot(*(c - _WAFER_CENTER_NM for c in _die_center_nm(col, row, geom))) <= limit
    ]
    random.Random(_seed(program_key, 971)).shuffle(dies)
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
# nm, not "" (user-confirmed 2026-08-08). The pickle carries no unit column at
# all — `unit` is DERIVED here from the parameter name, and this is the answer
# for a name the table does not recognise. An unlabelled CD-SEM measurement is a
# length in nanometres; the office data is "just a number" precisely because nm
# is the assumed unit, not because the unit is unknown.
#
# The column is absent because the MEASUREMENT IMAGE carries the unit
# (user-confirmed 2026-08-08): a reviewer opens the SEM image and reads it there,
# so the numeric column never had to repeat it. To a person the blank is an
# omission, not a gap — which is why nothing looked broken on screen for as long
# as it did. Only code has to be told.
#
# It was "" until 2026-08-08, which the frontend reads as UNKNOWN — and an
# unknown unit on a candidate is a hard `metadata-missing` exclusion
# (app/utils/skewvoirAnalysis/compatibility.ts::compareToReference). So every
# recipe whose parameter names miss this table (DEF_REVIEW_001's WAFER / EDGE,
# for instance) excluded its entire comparison set from 스큐보아 analysis, and
# 분석 준비 상태 reported 측정 2개 이상 필요 over a set of twelve.
#
# The range stays a CD-like 10–50, which was always an nm range: the values were
# already nanometres, only the label was missing.
_DEFAULT_SPEC: tuple[float, float, str] = (10.0, 50.0, "nm")


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
    # Setpoint-like channels that sit CONSTANT across the whole run (gain and
    # sigma both 0). That real tools stream flat channels is user-confirmed
    # 2026-08-07 — it is the entire reason 스큐보아's 평가 불가 (constant axis)
    # verdict and its 숨기기 toggle exist, and without these the home mock could
    # never exercise either path. WHICH channels sit constant is OFFICE-VERIFY:
    # these two are taken from the real dynamic_fdc key list in
    # docs/datatables/msr_file_pickle.txt as plausible setpoints, not observed
    # office behavior.
    "VT": FdcSpec(1200.0, 0.0, "V", "source", 0.0),
    "ESCdV": FdcSpec(2500.0, 0.0, "V", "echuck", 0.0),
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


def _exe_detail_info(
    msr: str, parent: MeasHistRow | None, class_name: str, program_key: str
) -> ExeDetailInfo:
    """Acquisition context. Sourced from the parent meas_hist row wherever
    possible so the MSR detail can never contradict the measurement history it
    hangs off; only the wafer geometry (absent upstream) is seeded.

    `program_key` is passed in rather than derived here on purpose. The local
    `recipe_name` below falls back to a shared "<CLASS>_UNKNOWN" display string,
    and seeding off THAT would collapse every parentless MSR into one program —
    the same trap get_msr_file documents at its own program_key."""
    recipe_name = parent["recipe_name"] if parent else f"{class_name}_UNKNOWN"
    lot_id = parent["lot_id"] if parent else f"LOT{_seed(msr) % 1_000_000:06d}"
    idp_name = parent["idp_name"] if parent else f"/Recipe/{class_name}/{recipe_name}.idp"
    idw_name = parent["idw_name"] if parent else f"/Recipe/{class_name}/{recipe_name}.idw"

    # Array + pitch come from the shared geometry so chip_array, chip_pitch and
    # wafer_size stay mutually consistent with the chip_number / stage columns.
    # Same key the rows are built with, so the reported map and the measured
    # dies can never describe different wafers.
    geom = _wafer_geometry(program_key)

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
        # Office formats (confirmed 2026-07-24): wafer_size is nm ("300000000"
        # = 300 mm), and map_origin is the ARRAY index of the origin die — the
        # die the centred chip_number (0,0) maps to — not an nm pair.
        wafer_size=str(_WAFER_NM),
        # map_offset is the die-grid offset actually encoded in stage_coordinate
        # (see _die_center_nm) -- read from the shared geometry so the reported
        # value and the generated coordinates cannot drift apart.
        map_offset=f"{geom.offset_x_nm},{geom.offset_y_nm}",
        map_origin=f"{geom.cols // 2},{geom.rows // 2}",
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


# How far each layer of the CD model moves the mean, as a fraction of the
# parameter's physical span. The ORDER is load-bearing, not the exact numbers:
# tool > site > run. A tool's bias has to be larger than both the within-wafer
# noise and the run-to-run wobble it is read through, or the tool-skew lens is
# ranking values it cannot actually separate.
_TOOL_SKEW_FRAC = 0.035    # per-(eqp, parameter) fixed measurement bias
_SITE_SIGMA_FRAC = 0.012   # within-wafer site-to-site noise
_RUN_OFFSET_FRAC = 0.010   # per-run wobble around this tool's level
_RUN_OFFSET_CLAMP = 2.5    # in units of _RUN_OFFSET_FRAC, so one run can't fly off
_HEALTH_DRIFT_FRAC = 0.12  # how far a fully unhealthy run is pushed off target


def _cd_field(
    msr: str, program_key: str, eqp_id: str, parameter: str, health: float
) -> CdField:
    """Wafer CD model, as four additive layers over one parameter.

        mean = recipe target + tool bias + run wobble + health drift

    Each layer is seeded from the identity it actually belongs to (see the
    module docstring). That split is the whole point: a single per-MSR draw
    made every run of a recipe an independent uniform sample, so a Time-Series
    trend across a set was scatter with no centre and the tool-skew panel
    ranked noise. With the layers separated, a set of runs clusters around the
    recipe's target, tools separate from each other by a fixed amount, and an
    unhealthy run is the visible excursion above both.

    Sites still cluster tightly around ``mean`` with a smooth centre→edge trend
    (``radial_amp``, a process signature and so also a recipe property) and
    small site noise (``site_sigma``), so leave-one-out outlier detection flags
    genuine excursions rather than most of the wafer.
    """
    lo, hi, _ = _param_spec(parameter)
    span = hi - lo

    # 1. The recipe's target. A recipe measures a feature to a spec, so every
    #    run of it aims at the same number — this is the trend's centre line.
    program_rng = random.Random(_seed(f"program:{program_key}:{parameter}", 431))
    target = lo + span * program_rng.uniform(0.42, 0.58)
    radial_amp = span * program_rng.uniform(0.03, 0.06) * (
        1.0 if program_rng.random() < 0.5 else -1.0
    )

    # 2. Tool skew: how THIS tool reads THIS feature, fixed for that pairing.
    #    Keyed on (eqp, parameter) and NOT the recipe, so a tool's bias is the
    #    same across every program it runs — which is what makes a skew finding
    #    transferable instead of an artifact of one recipe. A parentless run has
    #    no tool to attribute, so it carries no skew rather than a fabricated one.
    tool_offset = 0.0
    if eqp_id:
        tool_rng = random.Random(_seed(f"tool:{eqp_id}:{parameter}", 577))
        tool_offset = span * _TOOL_SKEW_FRAC * tool_rng.uniform(-1.0, 1.0)

    # 3. Run-to-run wobble around the tool's level, plus the health drift that
    #    makes an unhealthy run the excursion the trend is meant to expose.
    run_rng = random.Random(_seed(f"{msr}:{parameter}", 431))
    wobble = max(-_RUN_OFFSET_CLAMP, min(_RUN_OFFSET_CLAMP, run_rng.gauss(0, 1)))
    run_offset = span * _RUN_OFFSET_FRAC * wobble

    mean = target + tool_offset + run_offset + span * _HEALTH_DRIFT_FRAC * health
    return CdField(
        mean=mean, radial_amp=radial_amp, site_sigma=span * _SITE_SIGMA_FRAC, lo=lo, hi=hi
    )


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
    """The unit for a parameter, derived from its NAME (see _PARAM_SPECS).

    Cross-phase: office_example.py imports `_summaries`, which calls this, so
    this table is the single owner of what a unit means in BOTH phases. Never
    returns "" — an unrecognised name is nm, and the frontend treats a blank
    unit as unknown rather than as "unitless".
    """
    return _param_spec(parameter)[2]


def _resolve_params(class_name: str) -> tuple[str, ...]:
    measurement_class = CLASS_ALIAS.get(class_name.upper(), class_name.upper())
    return PARAMETER_MAPPING.get(measurement_class, FALLBACK_PARAMS)


# ── Program (recipe) properties ──────────────────────────────────────────────
# A recipe is a fixed measurement program, so these three are the same for every
# run of it. They are seeded from the program key rather than the msr; see the
# module docstring's three-seed-identities note for why that distinction is the
# domain model and not an implementation detail.


def _program_params(program_key: str, class_name: str) -> tuple[str, ...]:
    """WHICH parameters this recipe measures.

    Returned in PARAMETER_MAPPING order rather than draw order, so the set reads
    in its canonical order everywhere it is listed.
    """
    pool = _resolve_params(class_name)
    rng = random.Random(_seed(f"program:{program_key}", 1301))
    picked = set(rng.sample(pool, min(rng.randint(1, 3), len(pool))))
    return tuple(param for param in pool if param in picked)


def _program_dummy_count(program_key: str) -> int:
    """How many unnamed settling shots the recipe opens with.

    A program either starts with settling shots or it does not, so this cannot
    vary run to run. Seeded so that some programs carry them and some do not,
    which is what keeps BOTH paths exercised at home (see the settling-shot note
    in _build_rows and docs/datatables/msr_file_pickle.txt).
    """
    return random.Random(_seed(f"program:{program_key}", 911)).choice((0, 0, 0, 1, 1, 2, 3))


def _program_step_count(program_key: str) -> int:
    """How many measurement points the recipe visits, before the parent's image
    budget clamps it (see _build_rows)."""
    return random.Random(_seed(f"program:{program_key}", 1487)).randint(20, 80)


# The four stem suffixes HV-SEM tools append when one targeting point is shot
# as several images (user-confirmed 2026-08-08: IMMS0001-U.jpeg style, also on
# MSR result images e.g. S04_M0004-01MP-U.jpeg). Order matters: the pickle's
# mp_image_name 01..NN columns list them in this order, so the mock does too.
_MP_IMAGE_SUFFIXES = ("U", "T", "M", "L")


def _row_image_names(msr: str, sequence: int, parameter: str, rng: random.Random) -> list[str]:
    """The image file names of one measured row (pickle mp_image_name 01..NN).

    A single-image row keeps the bare stem (the CD-SEM convention); a
    multi-image row suffixes the shared stem -U/-T/-M/-L (the HV-SEM
    convention). The mock has no tool-family axis, so both shapes are drawn for
    every class — what matters at home is that multi-image rows EXIST, not
    which tool produced them. Extensions are drawn per file: office tools mix
    JPEG previews with TIFF originals (office 확인 2026-07-24: 26 jpeg / 13 tif
    in one MSR) and a sub-image sometimes exists only as .tif (user-confirmed
    2026-08-08), so a per-file draw keeps tif-only members in the value domain.
    """
    count = 1 + rng.randint(0, 3)
    stem = f"{msr}_{sequence:03d}_{parameter}_{rng.randint(0, 9999):04d}"
    if count == 1:
        return [f"{stem}.{'tif' if rng.random() < 0.3 else 'jpeg'}"]
    return [
        f"{stem}-{suffix}.{'tif' if rng.random() < 0.3 else 'jpeg'}"
        for suffix in _MP_IMAGE_SUFFIXES[:count]
    ]


def _build_rows(
    msr: str,
    class_name: str,
    total_images: int,
    health: float,
    program_key: str,
    eqp_id: str,
    offset: int = 0,
) -> list[MsrFileRow]:
    seed = _seed(msr, offset)
    rng = random.Random(seed)

    selected_params = _program_params(program_key, class_name)
    # STEP count, not measurement-point count: each step emits one row (one
    # sequence) PER PARAMETER, so points are num_measurements * num_params.
    # Deliberately still bounded by total_images // 2 rather than that product —
    # dividing by num_params drops low-image MSRs (min total_images is 42) below
    # 20 steps, and the every-20th-step failure rule would then never fire, so
    # those MSRs would carry no null-cd_value rows at all. Note this bound does
    # not cap total row count: rows = num_measurements * num_params, so a
    # 3-parameter MSR can claim ~1.5x more measurement points than the parent's
    # total_images ever produced — total_images // 2 bounds the STEP count only.
    #
    # The clamp is the one place a program property still bends to the run: two
    # runs of one recipe whose parents report very different total_images can
    # land on different step counts. That is a limit of deriving the budget from
    # meas_hist rather than a modelling claim — the parameter set, which is what
    # cross-MSR analysis keys on, stays identical either way.
    num_measurements = min(_program_step_count(program_key), max(1, total_images // 2))

    geom = _wafer_geometry(program_key)
    dies = _measured_dies(program_key)
    rows: list[MsrFileRow] = []
    span = max(1, num_measurements - 1)

    # ── Unnamed dummy MPs (settling shots) ───────────────────────────────────
    # Many recipes OPEN with one or more measurement points that carry no
    # parameter name. They are dummies in the sense that nobody analyses their
    # value, but they are real measurements: they run first so the tool is
    # stable by the time the recipe's actual parameters are measured, and they
    # produce SEM images that reviewers do look at.
    #
    # HOW MANY is a program property (_program_dummy_count) — a recipe either
    # opens with settling shots or it does not, so every run of it agrees. Their
    # CONTENT stays per-run: the values, images and scores below come from a
    # per-MSR rng, because two runs of one recipe do not repeat the same shots.
    dummy_rng = random.Random(_seed(msr, 911))
    num_dummy = _program_dummy_count(program_key)

    # Per-parameter wafer CD model + a handful of injected outliers, so most sites
    # sit tight (few flags) while the 이상 UI still has genuine excursions to show.
    fields = {p: _cd_field(msr, program_key, eqp_id, p, health) for p in selected_params}
    measured_steps = [s for s in range(1, num_measurements + 1) if s % 20 != 0]
    outliers_by_param: dict[str, dict[int, float]] = {}
    for p in selected_params:
        prng = random.Random(_seed(f"{msr}:{p}:outliers", 733))
        picks = prng.sample(measured_steps, min(prng.choice((0, 0, 1, 1, 2)), len(measured_steps)))
        outliers_by_param[p] = {
            s: (1.0 if prng.random() < 0.5 else -1.0) * abs(fields[p].mean) * prng.uniform(0.24, 0.40)
            for s in picks
        }

    # The settling shots themselves: sequences 1..num_dummy, all on the same die
    # (the tool does not move between them), each with a real image and real
    # acquisition conditions. mp_number 0 plus the lowest sequences puts them at
    # the head of the measurement order, which is what makes them the parameter a
    # naive "first parameter" default would land on.
    dummy_x, dummy_y = dies[0]
    dummy_center_x_nm, dummy_center_y_nm = _die_center_nm(dummy_x, dummy_y, geom)
    for sequence in range(1, num_dummy + 1):
        # No parameter segment in the filename — there is no name to put there.
        # Settling shots are single-image on both tool families.
        dummy_image = (
            f"{msr}_{sequence:03d}_{dummy_rng.randint(0, 9999):04d}"
            f".{'tif' if dummy_rng.random() < 0.3 else 'jpeg'}"
        )
        rows.append(MsrFileRow(
            msr=msr,
            sequence=sequence,
            chip_number=f"{dummy_x},{dummy_y}",
            chip_coordinate=f"{int(dummy_center_x_nm)},{int(dummy_center_y_nm)}",
            stage_coordinate=f"{int(dummy_center_x_nm)},{int(dummy_center_y_nm)}",
            dnum_group="0, -1",
            mp_number=0,
            # The defining trait: measured, imaged — and NAMELESS.
            parameter="",
            cd_value=round(dummy_rng.uniform(10.0, 50.0), 3),
            no_of_mp_image=1,
            mp_image_name_01=dummy_image,
            mp_image_names=[dummy_image],
            meas_condition_mag=_MAGNIFICATIONS[(sequence + seed) % len(_MAGNIFICATIONS)],
            meas_condition_vac=_VOLTAGES[(sequence + seed) % len(_VOLTAGES)],
            meas_condition_pixel=_PIXELS[(sequence + seed) % len(_PIXELS)],
            addressing1_score=int(round(dummy_rng.uniform(600, 950) - 200 * health)),
            addressing2_score=int(round(dummy_rng.uniform(600, 950) - 200 * health)),
            measurement_score=int(round(dummy_rng.uniform(820, 990) - 220 * health)),
            meas_method=_MEAS_METHODS[(sequence + seed) % len(_MEAS_METHODS)],
            object_type=_OBJECT_TYPES[(sequence + seed) % len(_OBJECT_TYPES)],
            meas_kind=_MEAS_KINDS[(sequence + seed) % len(_MEAS_KINDS)],
        ))

    # A STEP is one measurement point (one die). Each parameter measured there is
    # its own measurement and takes the next global sequence number — so two
    # parameters at one point share chip/stage but never share a sequence
    # (office 확인 2026-07-27, docs/datatables/msr_file_pickle.txt).
    # A distinct name from the dummy loop's own `sequence` above: this counter
    # STARTS at num_dummy (the settling shots already claimed 1..num_dummy) and
    # is not a reset of that binding, it is a continuation of it.
    running_sequence = num_dummy
    for step in range(1, num_measurements + 1):
        seq_frac = (step - 1) / span

        # Die index (chip_number) + its physical stage position (nm, corner
        # origin). A small within-die offset keeps stage_coordinate from being an
        # exact multiple of the pitch — the point is measured somewhere in the die.
        chip_x, chip_y = dies[(step - 1) % len(dies)]
        chip_number = f"{chip_x},{chip_y}"
        center_x_nm, center_y_nm = _die_center_nm(chip_x, chip_y, geom)
        off_x = rng.uniform(-0.3, 0.3) * geom.pitch_x_nm
        off_y = rng.uniform(-0.3, 0.3) * geom.pitch_y_nm
        stage_coordinate = f"{int(center_x_nm + off_x)},{int(center_y_nm + off_y)}"
        chip_coordinate = f"{int(center_x_nm)},{int(center_y_nm)}"
        # Physical radius from wafer centre, normalised to the wafer radius, drives
        # the centre→edge CD trend seen in the radius plot. Derived from the stage
        # position rather than from col*pitch so it includes the die-grid offset --
        # the frontend's siteRadiusMm reads the same stage_coordinate, and the two
        # radii have to agree or the CD trend is drawn against the wrong radius.
        radius_norm = math.hypot(
            center_x_nm + off_x - _WAFER_CENTER_NM, center_y_nm + off_y - _WAFER_CENTER_NM
        ) / _WAFER_RADIUS_NM

        # Every 20th STEP carries point METADATA but no point DATA (spec rule 9).
        # The whole point failed, so every parameter measured there fails with it.
        empty = step % 20 == 0

        if empty:
            dnum_group, mp_number = "-1, -1", -1
        else:
            mp_number = (step - 1) % 30
            dnum_group = f"{mp_number}, -1"

        if empty:
            meas_mag, meas_vac, meas_pixel = 0, 0, "0,0"
            measurement_score = None
            addressing1 = addressing2 = None
            meas_kind = None
        else:
            meas_mag = _MAGNIFICATIONS[(step + seed) % len(_MAGNIFICATIONS)]
            meas_vac = _VOLTAGES[(step + seed) % len(_VOLTAGES)]
            meas_pixel = _PIXELS[(step + seed) % len(_PIXELS)]
            # Quality scores fall as health rises; ~health fraction fail to score.
            scored = rng.random() > (0.05 + 0.35 * health)
            measurement_score = int(round(rng.uniform(820, 990) - 220 * health)) if scored else None
            addressing1 = int(round(rng.uniform(600, 950) - 200 * health)) if scored else None
            addressing2 = int(round(rng.uniform(600, 950) - 200 * health)) if scored else None
            meas_kind = _MEAS_KINDS[(step + seed) % len(_MEAS_KINDS)]

        meas_method = _MEAS_METHODS[(step + seed) % len(_MEAS_METHODS)]
        object_type = _OBJECT_TYPES[(step + seed) % len(_OBJECT_TYPES)]

        for parameter in selected_params:
            running_sequence += 1
            image_names = [] if empty else _row_image_names(msr, running_sequence, parameter, rng)
            rows.append(MsrFileRow(
                msr=msr,
                sequence=running_sequence,
                chip_number=chip_number,
                chip_coordinate=chip_coordinate,
                stage_coordinate=stage_coordinate,
                dnum_group=dnum_group,
                mp_number=mp_number,
                parameter=parameter,
                cd_value=None if empty else _cd_value(
                    fields[parameter], radius_norm, health, seq_frac, rng,
                    outliers_by_param[parameter].get(step, 0.0),
                ),
                no_of_mp_image=len(image_names),
                mp_image_name_01=image_names[0] if image_names else "",
                mp_image_names=image_names,
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
        # A constant channel (sigma 0) has no noise scale to measure drift in;
        # it also cannot drift, so its abnormality is 0 by definition.
        drift_sigma = 0.0 if spec.sigma == 0 else round(abs(mean - spec.nominal) / spec.sigma, 2)
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
    # The two identities beyond the run itself (see the module docstring). Both
    # are read from the parent row, so a measurement's program and tool are the
    # ones meas_hist already recorded — never separately invented here. With no
    # parent there is no recipe and no tool: the run becomes its own program and
    # carries no tool skew, rather than borrowing an identity it cannot know.
    #
    # This deliberately does NOT reuse _exe_detail_info's recipe_name, which
    # falls back to a shared "<CLASS>_UNKNOWN" display string — as a seed that
    # would make every parentless MSR one identical program.
    program_key = parent["recipe_name"] if parent else msr
    eqp_id = parent["eqp_id"] if parent else ""
    rows = _build_rows(msr, class_name, total_images, health, program_key, eqp_id)

    # One row is one measurement and each carries its own sequence, so this set
    # is simply every row — the office invariant len(rows) == len(dynamic_fdc)
    # (office 확인 2026-07-27, docs/datatables/msr_file_pickle.txt).
    sequences = sorted({row["sequence"] for row in rows})
    fixed_fdc, dynamic_fdc, fdc_params = _build_fdc(msr, sequences, health)

    return MsrFileResponse(
        msr=msr,
        class_name=class_name,
        # Straight off the parent row (docs/datatables/meas_hist.txt: eqp_ip).
        # A synthesized MSR has no parent, so no tool — "" is the honest answer.
        eqp_ip=parent["eqp_ip"] if parent else "",
        total_images=total_images,
        sequence_count=rows[-1]["sequence"] if rows else 0,
        health=health,
        parameters=_summaries(rows),
        fdc_params=fdc_params,
        fixed_fdc=fixed_fdc,
        dynamic_fdc=dynamic_fdc,
        exe_detail_info=_exe_detail_info(msr, parent, class_name, program_key),
        alignment=_alignment(msr, health),
        spm_dict=_spm_dict(msr),
        total=len(rows),
        rows=rows
    )
