"""msr_file — MSR raw measurement detail mock for 스큐보아 (Skewvoir).

Spec: docs/datatables/msr_file.txt
Each row = "하나의 MSR 안에서 특정 sequence, 특정 parameter로 측정된 1개 측정값".

The data is not generated independently: it is derived from a parent meas_hist
row (its msr / class_name / total_images). Generation is deterministic from the
md5(msr) seed, so the same MSR always opens to identical detail data with no DB
(Phase 1) — this mirrors the Python prototype the feature was ported from.
"""

import hashlib
import random
from functools import lru_cache
from statistics import fmean, pstdev
from typing import TypedDict

from back_dev_home.meas_hist.data import find_meas_hist_by_msr


__all__ = ["MsrFileRow", "MsrParamSummary", "MsrFileResponse", "get_msr_file"]


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


class MsrParamSummary(TypedDict):
    parameter: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    unit: str


class MsrFileResponse(TypedDict):
    msr: str
    class_name: str
    total_images: int
    sequence_count: int
    parameters: list[MsrParamSummary]
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


def _cd_value(rng: random.Random, parameter: str) -> float:
    lo, hi, _unit_label = _param_spec(parameter)
    return round(rng.uniform(lo, hi), 2)


def _unit(parameter: str) -> str:
    return _param_spec(parameter)[2]


def _resolve_params(class_name: str) -> tuple[str, ...]:
    measurement_class = CLASS_ALIAS.get(class_name.upper(), class_name.upper())
    return PARAMETER_MAPPING.get(measurement_class, FALLBACK_PARAMS)


def _build_rows(msr: str, class_name: str, total_images: int, offset: int = 0) -> list[MsrFileRow]:
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

    for sequence in range(1, num_measurements + 1):
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
                cd_value=_cd_value(rng, parameter),
                no_of_mp_image=1 + rng.randint(0, 4),
                mp_image_name_01=f"{msr}_{sequence:03d}_{parameter}_{rng.randint(0, 9999):04d}.tif"
            ))

    return rows


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

    rows = _build_rows(msr, class_name, total_images)

    return MsrFileResponse(
        msr=msr,
        class_name=class_name,
        total_images=total_images,
        sequence_count=rows[-1]["sequence"] if rows else 0,
        parameters=_summaries(rows),
        total=len(rows),
        rows=rows
    )
