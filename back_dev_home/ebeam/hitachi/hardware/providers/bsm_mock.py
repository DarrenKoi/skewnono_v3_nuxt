"""Phase 1 BSM (Beam Shape Matching) mock generator.

BSM is a CD-SEM-only check: a beam profile is sampled across 16 angular steps
(0deg -> 337.5deg, every 22.5deg) for two metrics, `sharpness` (~7.8-8.1) and
`noise` (~6.6-7.0). Real office data arrives as one pandas DataFrame of summary
rows per category plus the underlying per-measurement raw profiles. This module
fabricates the same shape deterministically from the `eqp_id` (the same
seed-from-id trick `bm_pm_mock.py` / `sem_list/data.py` use), so a given tool
shows identical BSM history on every request without any stored fixture.

Two categories use *different sample sets* and are therefore kept as two
separate tables:

* `daily` - scheduled monitoring, 3 measurements/day for ~30 days.
* `pm`    - one confirmation measurement after each completed PM (sparse).

`build_bsm_data()` is the only public entry point; per-measurement summaries are
computed straight off the generated raw profiles so avg/3sigma stay consistent
with the radar values, then handed to `normalizers.bsm_payload`.
"""

import hashlib
import random
import statistics
from datetime import datetime, timedelta

import pandas as pd


__all__ = ["build_bsm_data"]


# Anchor "today" so generated dates are stable regardless of the wall clock.
NOW = datetime(2026, 5, 24, 9, 0)
_TS_FMT = "%Y-%m-%d %H:%M"

# 16 angular steps: 0, 22.5, 45.0, ... 337.5 (360deg / 22.5deg).
ANGLES: list[str] = [f"{i * 22.5:g}" for i in range(16)]

# Scheduled monitoring runs at roughly these three slots each day.
_DAILY_HOURS: tuple[int, ...] = (6, 14, 22)

_SUMMARY_COLUMNS = [
    "timestamp",
    "eqp_id",
    "sharpness_avg",
    "sharpness_3std",
    "noise_avg",
    "noise_3std",
]


def _seed_for(eqp_id: str) -> int:
    """Stable int seed derived from the equipment id.

    `hash()` is salted per-process, so we hash explicitly to keep the same tool
    reproducible across requests and restarts.
    """
    digest = hashlib.md5(eqp_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _fmt(dt: datetime) -> str:
    return dt.strftime(_TS_FMT)


def _make_profile(
    rng: random.Random,
    *,
    sharp_center: float,
    noise_center: float,
) -> dict[str, list[float]]:
    """16-angle sharpness/noise profile around per-measurement centers.

    A small per-angle wobble gives the radar an organic (non-circular) shape;
    the center drifts measurement-to-measurement so the trend chart isn't flat.
    Values are clamped to the physically plausible band and rounded to 3 dp.
    """
    sharpness = [
        round(min(8.10, max(7.80, sharp_center + rng.uniform(-0.05, 0.05))), 3)
        for _ in ANGLES
    ]
    noise = [
        round(min(7.00, max(6.60, noise_center + rng.uniform(-0.05, 0.05))), 3)
        for _ in ANGLES
    ]
    return {"sharpness": sharpness, "noise": noise}


def _summarize(eqp_id: str, timestamp: str, profile: dict[str, list[float]]) -> dict[str, object]:
    """One summary row (avg + 3sigma) computed off the raw 16-angle profile."""
    sharp = profile["sharpness"]
    noise = profile["noise"]
    return {
        "timestamp": timestamp,
        "eqp_id": eqp_id,
        "sharpness_avg": round(statistics.mean(sharp), 3),
        "sharpness_3std": round(3 * statistics.pstdev(sharp), 3),
        "noise_avg": round(statistics.mean(noise), 3),
        "noise_3std": round(3 * statistics.pstdev(noise), 3),
    }


def _build_category(
    eqp_id: str,
    rng: random.Random,
    timestamps: list[datetime],
) -> tuple[pd.DataFrame, dict[str, dict[str, list[float]]]]:
    """Summary frame (timestamp desc) + raw profiles keyed by timestamp."""
    records: list[dict[str, object]] = []
    profiles: dict[str, dict[str, list[float]]] = {}
    # Slowly drifting centers make the trend lines wander rather than jitter.
    sharp_center = rng.uniform(7.90, 8.00)
    noise_center = rng.uniform(6.75, 6.85)
    for moment in timestamps:
        sharp_center = min(8.05, max(7.85, sharp_center + rng.uniform(-0.01, 0.01)))
        noise_center = min(6.95, max(6.65, noise_center + rng.uniform(-0.01, 0.01)))
        ts = _fmt(moment)
        profile = _make_profile(rng, sharp_center=sharp_center, noise_center=noise_center)
        profiles[ts] = profile
        records.append(_summarize(eqp_id, ts, profile))

    frame = pd.DataFrame.from_records(records, columns=_SUMMARY_COLUMNS)
    if not frame.empty:
        frame = frame.sort_values("timestamp", ascending=False, ignore_index=True)
    return frame, profiles


def _daily_timestamps(rng: random.Random) -> list[datetime]:
    """3 measurements/day for the last ~30 days."""
    moments: list[datetime] = []
    for day in range(30):
        date = NOW - timedelta(days=day)
        for hour in _DAILY_HOURS:
            moments.append(date.replace(hour=hour, minute=rng.choice([0, 15, 30, 45])))
    return moments


def _pm_timestamps(rng: random.Random) -> list[datetime]:
    """One confirmation measurement after each completed PM over ~180 days."""
    moments: list[datetime] = []
    cursor = NOW - timedelta(days=rng.randint(3, 20))
    while cursor > NOW - timedelta(days=180):
        moments.append(cursor.replace(hour=rng.choice([8, 9, 13]), minute=rng.choice([0, 30])))
        # PM cadence wanders between ~2 and ~4 weeks.
        cursor -= timedelta(days=rng.randint(14, 30))
    return moments


def build_bsm_data(eqp_id: str) -> dict[str, object]:
    """Deterministic daily + PM BSM categories for one tool."""
    rng = random.Random(_seed_for(eqp_id))

    daily_frame, daily_profiles = _build_category(eqp_id, rng, _daily_timestamps(rng))
    pm_frame, pm_profiles = _build_category(eqp_id, rng, _pm_timestamps(rng))

    return {
        "angles": ANGLES,
        "categories": [
            {
                "key": "daily",
                "label": "Daily Monitoring",
                "summary": daily_frame.to_dict(orient="records"),
                "profiles": daily_profiles,
            },
            {
                "key": "pm",
                "label": "PM Confirm",
                "summary": pm_frame.to_dict(orient="records"),
                "profiles": pm_profiles,
            },
        ],
    }
