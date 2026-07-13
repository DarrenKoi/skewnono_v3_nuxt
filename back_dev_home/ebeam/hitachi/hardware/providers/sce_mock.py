"""Phase 1 faithful sce_setting mock (fleet dict-of-dict, as-of snapshot).

Shape from `docs/datatables/sce_setting.txt`: per eqp a FileInfo/SemCond/
ImgCond/SCEParam block plus a 360-entry Coefficients curve (`{index, values:
[2 floats]}`, indices 0..359). Returned for the requested eqp + in-fab
siblings. SCE is an M-fab production feature (R3/R4 don't use it); we emit for
any CD-SEM eqp in the mock and let `normalizers.settings_payload` note usage.
"""

from __future__ import annotations

import math
import random
from datetime import datetime

from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
    seed_for,
    sibling_eqp_ids,
)


__all__ = ["build_sce_settings"]


def _file_info(rng: random.Random, eqp_id: str) -> dict[str, str]:
    day = rng.randint(1, 28)
    return {
        "FileName": f"SCE_{eqp_id}_2026{rng.randint(1, 5):02d}{day:02d}.dat",
        "Updated": f"2026-{rng.randint(1, 5):02d}-{day:02d}",
    }


def _sem_cond(rng: random.Random) -> dict[str, str]:
    return {
        "SemCond_No": str(rng.randint(1, 8)),
        "SemCond_Optics": rng.choice(["High Reso.", "Standard"]),
        "SemCond_Vacc": rng.choice(["500", "800"]),
        "SemCond_Ip": f"{rng.uniform(6.0, 9.0):.4f}",
        "SemCond_IpMode": rng.choice(["Low", "Middle", "High"]),
        "SemCond_Detector": rng.choice(["SE+EF", "SE", "EF"]),
    }


def _img_cond(rng: random.Random) -> dict[str, list[str]]:
    mag = str(rng.randint(150_000_000, 150_009_999))
    return {
        "ImgCond_FocusOffset": [str(rng.randint(-3, 1))],
        "ImgCond_Mag": [mag, mag],
        "ImgCond_Pixel": ["1024", "1024"],
    }


def _sce_param(rng: random.Random) -> dict[str, str]:
    return {
        "SCEParam_CycleUpperTh": f"{rng.uniform(5.0, 7.0):.3f}",
        "SCEParam_CycleLowerTh": f"{rng.uniform(20.0, 24.0):.6f}",
        "SCEParam_SmoothRadius": str(rng.randint(5, 9)),
        "SCEParam_SmoothTheta": str(rng.randint(5, 9)),
        "SCEParam_FitRangeSt": str(rng.randint(35, 45)),
        "SCEParam_FitRangeEd": str(rng.randint(75, 85)),
        "SCEParam_CorrCoefLimit": f"{rng.uniform(0.1, 0.3):.5f}",
    }


def _smooth_curve(
    rng: random.Random,
    center: float,
    half_range: float,
) -> list[float]:
    """Smooth periodic curve over 0..359 deg staying in center +/- half_range.

    SCE coefficients are angular corrections, so the real curves are smooth
    (a few low-order harmonics), not per-index noise. Sum 3 sinusoids with
    random order/phase/weight, add small jitter, and clamp to the band.
    """
    terms = [
        (order, rng.uniform(0.0, 2.0 * math.pi), rng.uniform(0.4, 1.0))
        for order in (1, 2, rng.randint(3, 5))
    ]
    total_weight = sum(weight for _, _, weight in terms)
    values: list[float] = []
    for index in range(360):
        theta = math.radians(index)
        shape = sum(
            weight * math.sin(order * theta + phase)
            for order, phase, weight in terms
        ) / total_weight
        jitter = rng.uniform(-0.04, 0.04)
        unit = max(-1.0, min(1.0, shape + jitter))
        values.append(center + half_range * unit)
    return values


def _coefficients(rng: random.Random) -> list[dict]:
    v0 = _smooth_curve(rng, center=0.0, half_range=0.02)
    v1 = _smooth_curve(rng, center=0.95, half_range=0.05)
    return [
        {"index": index, "values": [round(v0[index], 6), round(v1[index], 6)]}
        for index in range(360)
    ]


def build_sce_settings(
    eqp_id: str,
    fab_name: str | None,
    as_of: datetime,
) -> dict[str, dict]:
    eqp_ids = sibling_eqp_ids(eqp_id, fab_name)
    as_of_salt = int(as_of.strftime("%Y%m%d"))
    out: dict[str, dict] = {}
    for tool in eqp_ids:
        rng = random.Random(seed_for(tool) ^ 0x5343_4532 ^ as_of_salt)
        out[tool] = {
            "FileInfo": _file_info(rng, tool),
            "SemCond": _sem_cond(rng),
            "ImgCond": _img_cond(rng),
            "SCEParam": _sce_param(rng),
            "Coefficients": _coefficients(rng),
        }
    return out
