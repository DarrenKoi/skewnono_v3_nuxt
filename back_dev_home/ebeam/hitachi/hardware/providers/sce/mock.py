"""Phase 1 faithful sce_setting mock (fleet dict-of-dict + bidaily history).

Shape from `docs/datatables/sce_setting.txt`: per eqp a FileInfo/SemCond/
ImgCond/SCEParam block plus a 360-entry Coefficients curve (`{index, values:
[2 floats]}`, indices 0..359). The snapshot is returned for the requested eqp
+ in-fab siblings; the history is the office's bidaily MinIO archive mirrored
as one snapshot doc per collection date for the selected tool only. SCE is an
M-fab production feature (R3/R4 don't use it); we emit for any CD-SEM eqp in
the mock and let `normalizers.settings_payload` note usage.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta

from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
    seed_for,
    sibling_eqp_ids,
)
from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm.mock import (
    completed_pm_dates,
)


__all__ = ["build_sce_history", "build_sce_settings"]


def _file_info(rng: random.Random, eqp_id: str) -> dict[str, str]:
    day = rng.randint(1, 28)
    stamp = f"2026{rng.randint(1, 5):02d}{day:02d}"
    return {
        "SharpCharFile": f"/HITACHI/SCE/SharpChar_{eqp_id}_{stamp}.dat",
        "BaseSharpCharFile": f"/HITACHI/SCE/BaseSharpChar_{eqp_id}.dat",
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


def _revision_salt(tool: str, on: date, anchor: datetime) -> int:
    """Salt naming the SCE settings revision in force on `on`.

    SCE is re-tuned at PM, not per collection: between two PMs the tool keeps
    serving the same SharpChar file, so every collection in that span reads
    back byte-identical. Seeding from the most recent completed PM at or before
    the date models exactly that — values hold flat, then step.

    The PM dates come from the bm_pm mock rather than a schedule of our own, so
    a step in the 시계열 curve lands on the same day the BM/PM overlay draws its
    marker. A tool with no PM yet in the window gets salt 0 (one flat era).
    """
    prior = [day for day in completed_pm_dates(tool, anchor) if day <= on]
    return int(prior[-1].strftime("%Y%m%d")) if prior else 0


def _tool_snapshot(tool: str, revision_salt: int) -> dict:
    """One tool's full settings block for one settings revision.

    Shared by the snapshot and the history so a history doc for date D is
    IDENTICAL to a snapshot taken as-of D — the invariant the office side
    has for free (the latest MinIO file and the Redis hash hold the same
    collection).

    Two streams, because the blocks differ in nature. SemCond/ImgCond are tool
    CONFIGURATION (optics, accelerating voltage, pixel count): they hold steady
    across re-tunes too, so they seed from the tool alone and read as a flat
    line for the tool's whole life. FileInfo/SCEParam/Coefficients are the
    re-tune OUTPUTS — a PM writes a fresh SharpChar file with fresh parameters
    and a fresh curve — so they seed from tool+revision and step at PM. See
    `_revision_salt`.
    """
    config_rng = random.Random(seed_for(tool) ^ 0x5343_4532)
    rev_rng = random.Random(seed_for(tool) ^ 0x5343_4532 ^ revision_salt)
    return {
        "FileInfo": _file_info(rev_rng, tool),
        "SemCond": _sem_cond(config_rng),
        "ImgCond": _img_cond(config_rng),
        "SCEParam": _sce_param(rev_rng),
        "Coefficients": _coefficients(rev_rng),
    }


def build_sce_settings(
    eqp_id: str,
    fab_name: str | None,
    as_of: datetime,
) -> dict[str, dict]:
    eqp_ids = sibling_eqp_ids(eqp_id, fab_name)
    # Per tool, not per request: siblings are re-tuned on their own PM
    # schedules, so the 비교 tab shows curves of differing ages — which is the
    # thing that tab exists to make visible.
    return {
        tool: _tool_snapshot(tool, _revision_salt(tool, as_of.date(), as_of))
        for tool in eqp_ids
    }


def build_sce_history(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Bidaily SCE snapshots for the selected tool across [start, end], ascending.

    The office archives one {fab_name}.json per collection day (roughly every
    other day) in MinIO; this mirrors that cadence with a date-parity schedule
    so the same dates exist regardless of the requested window. Each doc is
    the tool's settings block for that date plus the collection ``date``.
    ``fab_name`` is unused here but part of the builder signature — the office
    adapter needs it to pick the per-fab archive file.

    Every collection date gets a doc, including the ones whose settings are
    unchanged from the previous collection — "we collected and nothing moved"
    is itself the reading, and the param trend needs the point. Collapsing the
    repeats is the frontend's job (`sceCoeffRevisions`).
    """
    del fab_name
    docs: list[dict] = []
    day = start.date()
    last = end.date()
    while day <= last:
        if day.toordinal() % 2 == 0:
            salt = _revision_salt(eqp_id, day, end)
            docs.append({"date": day.isoformat(), **_tool_snapshot(eqp_id, salt)})
        day += timedelta(days=1)
    return docs
