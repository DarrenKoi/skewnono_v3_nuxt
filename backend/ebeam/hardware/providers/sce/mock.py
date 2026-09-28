"""Phase 1 faithful sce_setting mock (fleet dict-of-dict + bidaily history).

Shape from `docs/datatables/hitachi/hardware_sce_setting.txt`: per eqp a FileInfo/SemCond/
ImgCond/SCEParam block plus a 360-entry Coefficients curve (`{index, values:
[2 floats]}`, indices 0..359). The snapshot is returned for the requested eqp
+ in-fab siblings; the history is the office's bidaily MinIO archive mirrored
as one snapshot doc per collection date for the selected tool only.

Calibrated to the office characterization run (office 확인 2026-09-28):

* `sce_info` has 13 fab fields, but M10A/M10C/R3/R4 are empty: SCE 미수집 fab.
  Those fabs get `{}` / `[]` here, the same empty the office adapter returns.
* SemCond_Detector/Ip/IpMode/Optics, ImgCond_Pixel and all 7 SCEParam_* are
  constant fleet-wide. The VALUES used are the sample in
  `hardware_sce_setting.txt` (OFFICE-VERIFY that the sample is the fleet value).
* Re-tunes are rare, and 4 of 5 changed ImgCond_Mag on the same date. The
  re-tune cadence below (60-240 days) is OFFICE-VERIFY.
* No single reference tool per fab: tools group by a shared
  `BaseSharpCharFile`. The two-groups-per-fab split is OFFICE-VERIFY.
* Coefficients are always 360 x 2, indices 0..359, no NaN. Harmonics 1-4
  carry 82-97 % of values[0]'s variance but only 64-91 % of values[1]'s;
  the curves are built to that split.
"""

from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from statistics import fmean, pstdev

from backend.ebeam.hardware.providers._siblings import (
    seed_for,
    sibling_eqp_ids,
)


__all__ = ["build_sce_history", "build_sce_settings"]


# SCE 미수집 fab: present as hash fields at the office, but empty.
NO_SCE_FABS = frozenset({"M10A", "M10C", "R3", "R4"})

# Constant fleet-wide (office 확인 2026-09-28); values from the doc sample.
_SEM_COND_FLEET = {
    "SemCond_Optics": "High Reso.",
    "SemCond_Ip": "8.0000",
    "SemCond_IpMode": "Middle",
    "SemCond_Detector": "SE+EF",
}
_SCE_PARAM_FLEET = {
    "SCEParam_CycleUpperTh": "6.000",
    "SCEParam_CycleLowerTh": "22.500000",
    "SCEParam_SmoothRadius": "7",
    "SCEParam_SmoothTheta": "7",
    "SCEParam_FitRangeSt": "40",
    "SCEParam_FitRangeEd": "79",
    "SCEParam_CorrCoefLimit": "0.20000",
}


def _file_info(rng: random.Random, eqp_id: str, fab_name: str | None) -> dict[str, str]:
    day = rng.randint(1, 28)
    stamp = f"2026{rng.randint(1, 5):02d}{day:02d}"
    # Tools share a base file in groups; no single reference tool per fab.
    group = "G1" if seed_for(eqp_id) % 2 else "G2"
    return {
        "SharpCharFile": f"/HITACHI/SCE/SharpChar_{eqp_id}_{stamp}.dat",
        "BaseSharpCharFile": f"/HITACHI/SCE/BaseSharpChar_{fab_name or 'FAB'}_{group}.dat",
    }


def _sem_cond(rng: random.Random) -> dict[str, str]:
    return {
        "SemCond_No": str(rng.randint(1, 8)),
        "SemCond_Vacc": rng.choice(["500", "800"]),
        **_SEM_COND_FLEET,
    }


def _img_cond(rng: random.Random, mag: str) -> dict[str, list[str]]:
    return {
        "ImgCond_FocusOffset": [str(rng.randint(-3, 1))],
        "ImgCond_Mag": [mag, mag],
        "ImgCond_Pixel": ["1024", "1024"],
    }


def _revision_mag(tool: str, retunes: list[date], salt: int) -> str:
    """ImgCond_Mag in force for the revision named by `salt`.

    Walks the re-tunes up to that revision: each one re-picks Mag with
    probability 0.8 (office: 4 of 5 re-tunes changed a setting on the same
    date, most often Mag) and otherwise keeps the previous value.
    """
    mag = random.Random(seed_for(tool) ^ 0x4D41_4700).randint(150_000_000, 150_009_999)
    for day in retunes:
        day_salt = int(day.strftime("%Y%m%d"))
        if day_salt > salt:
            break
        step = random.Random(seed_for(tool) ^ day_salt)
        if step.random() < 0.8:
            mag = step.randint(150_000_000, 150_009_999)
    return str(mag)


def _unit_variance(values: list[float]) -> list[float]:
    mean = fmean(values)
    std = pstdev(values, mean) or 1.0
    return [(v - mean) / std for v in values]


def _harmonics(rng: random.Random, orders: range) -> list[float]:
    terms = [
        (order, rng.uniform(0.0, 2.0 * math.pi), rng.uniform(0.3, 1.0) / order)
        for order in orders
    ]
    return [
        sum(w * math.sin(k * math.radians(i) + ph) for k, ph, w in terms)
        for i in range(360)
    ]


def _smooth_curve(
    rng: random.Random,
    center: float,
    half_range: float,
    low_share: float,
) -> list[float]:
    """Periodic curve over 0..359 deg staying in center +/- half_range.

    `low_share` is the fraction of the variance carried by harmonics 1-4; the
    rest is higher harmonics (5-12) plus per-index jitter. Both parts are
    scaled to unit variance and mixed by that share, so an FFT of the result
    reads back roughly `low_share` in harmonics 1-4.
    """
    low = _unit_variance(_harmonics(rng, range(1, 5)))
    rough = [h + rng.gauss(0.0, 0.3) for h in _harmonics(rng, range(5, 13))]
    high = _unit_variance(rough)
    a, b = math.sqrt(low_share), math.sqrt(1.0 - low_share)
    mixed = [a * lo + b * hi for lo, hi in zip(low, high, strict=True)]
    peak = max(abs(v) for v in mixed) or 1.0
    return [center + half_range * v / peak for v in mixed]


def _coefficients(rng: random.Random) -> list[dict]:
    v0 = _smooth_curve(rng, center=0.0, half_range=0.02, low_share=rng.uniform(0.84, 0.96))
    v1 = _smooth_curve(rng, center=0.95, half_range=0.05, low_share=rng.uniform(0.66, 0.89))
    return [
        {"index": index, "values": [round(v0[index], 6), round(v1[index], 6)]}
        for index in range(360)
    ]


# Walk origin for the re-tune schedule, far enough back to cover any plausible
# request window (same trick as `mdc/mock.py`'s `_WALK_ANCHOR`).
_RETUNE_ORIGIN = date(2025, 1, 1)


def _retune_dates(eqp_id: str, until: date) -> list[date]:
    """This tool's SCE re-tune dates from a FIXED origin through `until`, asc.

    Walks a per-tool cadence (~2-4 weeks) forward from `_RETUNE_ORIGIN` rather
    than back from the caller's window, which is what makes the schedule a
    PREFIX: extending `until` only appends, so the re-tune in force on a past
    date is the same answer no matter what range was requested. That property
    is what keeps history reproducible — the office archive file for a
    collection date is immutable, and a mock that rewrote the past when you
    widened the window would contradict it.

    Deliberately SCE's OWN schedule rather than `bm_pm`'s PM rows, even though
    a real re-tune happens at PM. Those rows are generated relative to the
    caller's anchor and the page sends a live clock, so anything seeded from
    them slides with wall time: stability and marker-alignment cannot both
    hold. Stability wins, and office-side nothing couples the two either — see
    hardware/MIGRATION.md.
    """
    rng = random.Random(seed_for(eqp_id) ^ 0x5245_5455)
    days: list[date] = []
    day = _RETUNE_ORIGIN
    while day <= until:
        # Re-tunes are rare (office 확인 2026-09-28); the gap is OFFICE-VERIFY.
        day += timedelta(days=rng.randint(60, 240))
        if day <= until:
            days.append(day)
    return days


def _revision_salt(retunes: list[date], on: date) -> int:
    """Salt naming the SCE settings revision in force on `on`.

    SCE is re-tuned at PM, not per collection: between two re-tunes the tool
    keeps serving the same SharpChar file, so every collection in that span
    reads back byte-identical. Seeding from the most recent re-tune at or
    before the date models exactly that — values hold flat, then step.

    Takes the schedule rather than looking it up, so callers hoist the walk out
    of their loop and this stays a pure function of (schedule, date). A date
    before the tool's first re-tune gets salt 0 — one flat era.
    """
    prior = max((day for day in retunes if day <= on), default=None)
    return int(prior.strftime("%Y%m%d")) if prior else 0


def _tool_snapshot(
    tool: str, fab_name: str | None, retunes: list[date], revision_salt: int
) -> dict:
    """One tool's full settings block for one settings revision.

    Shared by the snapshot and the history so a history doc for date D is
    IDENTICAL to a snapshot taken as-of D — the invariant the office side
    has for free (the latest MinIO file and the Redis hash hold the same
    collection).

    Two streams, because the blocks differ in nature. SemCond/ImgCond are tool
    CONFIGURATION (optics, accelerating voltage, pixel count): they seed from
    the tool alone and read as a flat line for the tool's whole life — except
    ImgCond_Mag, which the office saw change at most re-tunes
    (`_revision_mag`). FileInfo/Coefficients are the re-tune OUTPUTS — a PM
    writes a fresh SharpChar file and a fresh curve — so they seed from
    tool+revision and step at PM. SCEParam is constant fleet-wide. See
    `_revision_salt`.
    """
    config_rng = random.Random(seed_for(tool) ^ 0x5343_4532)
    rev_rng = random.Random(seed_for(tool) ^ 0x5343_4532 ^ revision_salt)
    return {
        "FileInfo": _file_info(rev_rng, tool, fab_name),
        "SemCond": _sem_cond(config_rng),
        "ImgCond": _img_cond(config_rng, _revision_mag(tool, retunes, revision_salt)),
        "SCEParam": dict(_SCE_PARAM_FLEET),
        "Coefficients": _coefficients(rev_rng),
    }


def _collected(fab_name: str | None) -> bool:
    return (fab_name or "").strip().upper() not in NO_SCE_FABS


def build_sce_settings(
    eqp_id: str,
    fab_name: str | None,
    as_of: datetime,
) -> dict[str, dict]:
    if not _collected(fab_name):
        return {}
    eqp_ids = sibling_eqp_ids(eqp_id, fab_name)
    on = as_of.date()
    # Per tool, not per request: siblings are re-tuned on their own PM
    # schedules, so the 비교 tab shows curves of differing ages — which is the
    # thing that tab exists to make visible.
    snapshots: dict[str, dict] = {}
    for tool in eqp_ids:
        retunes = _retune_dates(tool, on)
        snapshots[tool] = _tool_snapshot(tool, fab_name, retunes, _revision_salt(retunes, on))
    return snapshots


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
    ``fab_name`` picks the per-fab archive at the office; here it gates the
    SCE 미수집 fabs and names the shared base file.

    Every collection date gets a doc, including the ones whose settings are
    unchanged from the previous collection — "we collected and nothing moved"
    is itself the reading, and the param trend needs the point. Collapsing the
    repeats is the frontend's job (`sceCoeffRevisions`).
    """
    if not _collected(fab_name):
        return []
    retunes = _retune_dates(eqp_id, end.date())
    # One built snapshot per REVISION, not per date. A 30-day window is ~16
    # collections over 1-2 revisions, so rebuilding per date regenerated the
    # same 360-entry curve a dozen times (measured: 9.3ms -> 1.1ms). The
    # `**snap` spread gives each doc its own top-level dict; the nested blocks
    # are shared, which is safe because nothing downstream mutates a doc.
    snapshots: dict[int, dict] = {}
    docs: list[dict] = []
    day = start.date()
    last = end.date()
    while day <= last:
        if day.toordinal() % 2 == 0:
            salt = _revision_salt(retunes, day)
            snap = snapshots.get(salt)
            if snap is None:
                snap = snapshots[salt] = _tool_snapshot(eqp_id, fab_name, retunes, salt)
            docs.append({"date": day.isoformat(), **snap})
        day += timedelta(days=1)
    return docs
