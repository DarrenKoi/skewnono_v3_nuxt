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
"""

import hashlib
import random
from functools import lru_cache
from statistics import fmean, pstdev
from typing import NamedTuple, TypedDict

from back_dev_home.meas_hist.data import find_meas_hist_by_msr


__all__ = [
    "MsrFileRow",
    "MsrParamSummary",
    "FdcParamSummary",
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
    cd_value: float
    no_of_mp_image: int
    mp_image_name_01: str
    # Richer df_result_data fields from the pickle (docs §df_result_data). Quality
    # scores are nullable — a skipped/failed point reports None.
    measurement_score: int | None
    meas_method: str
    object_type: str


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


@lru_cache(maxsize=1)
def _chip_positions() -> tuple[tuple[int, int], ...]:
    """Simplified round wafer: -10..10 grid keeping abs(x) + abs(y) <= 15."""
    return tuple(
        (x, y)
        for x in range(-10, 11)
        for y in range(-10, 11)
        if abs(x) + abs(y) <= 15
    )


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


def _cd_value(rng: random.Random, parameter: str, health: float, seq_frac: float) -> float:
    lo, hi, _unit_label = _param_spec(parameter)
    base = rng.uniform(lo, hi)
    # Unhealthy tools drift CD upward, more so late in the run — this is what
    # makes CD track the FDC excursion in the correlation view.
    drift = health * (hi - lo) * 0.25 * (0.3 + 0.7 * seq_frac)
    return round(base + drift, 2)


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

    positions = _chip_positions()
    rows: list[MsrFileRow] = []
    span = max(1, num_measurements - 1)

    for sequence in range(1, num_measurements + 1):
        seq_frac = (sequence - 1) / span
        chip_x, chip_y = positions[(sequence - 1) % len(positions)]
        chip_number = f"{chip_x}, {chip_y}"
        chip_coordinate = f"{12_000_000 + sequence * 1000 + seed % 1_000_000},{250_000 + sequence * 100}"
        stage_coordinate = f"{175_000_000 + sequence * 10000 + seed % 100_000}, {147_000_000 + sequence * 5000}"

        # Every 20th sequence has point metadata but no actual point data.
        if sequence % 20 == 0:
            dnum_group, mp_number = "-1, -1", -1
        else:
            mp_number = (sequence - 1) % 30
            dnum_group = f"{mp_number}, -1"

        # Quality score falls as health rises; ~health fraction of points fail to score.
        scored = rng.random() > (0.05 + 0.35 * health)
        measurement_score = int(round(rng.uniform(820, 990) - 220 * health)) if scored else None
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
                cd_value=_cd_value(rng, parameter, health, seq_frac),
                no_of_mp_image=1 + rng.randint(0, 4),
                mp_image_name_01=f"{msr}_{sequence:03d}_{parameter}_{rng.randint(0, 9999):04d}.tif",
                measurement_score=measurement_score,
                meas_method=meas_method,
                object_type=object_type,
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
    by_param: dict[str, list[float]] = {}
    for row in rows:
        by_param.setdefault(row["parameter"], []).append(row["cd_value"])

    summaries = [
        MsrParamSummary(
            parameter=parameter,
            count=len(values),
            mean=round(fmean(values), 3),
            std=round(pstdev(values), 3) if len(values) > 1 else 0.0,
            min=round(min(values), 3),
            max=round(max(values), 3),
            unit=_unit(parameter)
        )
        for parameter, values in by_param.items()
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
    # row; for direct API access we fall back to the parent meas_hist lookup.
    if class_name is None or total_images is None:
        parent = find_meas_hist_by_msr(msr)
        if parent is None:
            return None
        if class_name is None:
            class_name = parent["class_name"]
        if total_images is None:
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
        total=len(rows),
        rows=rows
    )
