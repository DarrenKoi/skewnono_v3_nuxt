"""Phase 1 faithful sharpness_monitor_cdsem mock for the hardware sharpness panel.

Raw doc shape from `docs/datatables/hardware_sharpness_monitor_cdsem.txt`: beam quality read
off the stub sample in the tool chamber, automatically every 6~8 hours. Unlike BSM
(reference wafer, PM-tied), this is a high-cadence daily monitor, so it lives under
the 데일리 service group.

The index carries exactly eight fields — `ip`, `timestamp`, `os_inserted`,
`beam_condition`, `reso_detector`, `noise`, `reso_eb`, `summ_beam`
(user-confirmed 2026-07-22) — and this mock emits that set and nothing more. In
particular there is no `eqp_id` here: `ip` is the only tool identity the index
has, which is why the office adapter must resolve eqp_id -> eqp_ip through the
sem_list roster before it can query at all. The payload's own `eqp_id`/`fab_name`
come from `normalizers.docs_payload`, not from the docs.

Faithful nesting (kept verbatim, NOT flattened to the BSM array shape):
  - `beam_condition`: object grouping `SEM_Cond_No` + `Vacc` (paired) plus Vsup etc.
  - `reso_detector` / `noise` / `reso_eb`: dicts keyed "0.0"~"337.5" (step 22.5),
    all three selectable as the page's radar metric.
  - `summ_beam`: dict of scalar beam-shape summaries.

Determinism mirrors the other providers: `random.Random` seeded from md5(eqp_id),
anchored to `_siblings.NOW`; distinct stream so it never collides with bsm/reso.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
    eqp_ip_for,
    seed_for,
)


__all__ = ["build_network_sharpness_docs"]


# 16 angular steps as string keys: "0.0", "22.5", ... "337.5".
_DEGREE_KEYS: list[str] = [f"{round(i * 22.5, 1)}" for i in range(16)]

# Chamber stub auto-monitor runs roughly every 6~8h.
_DAILY_HOURS: tuple[int, ...] = (2, 9, 16, 22)

# Paired (SEM_Cond_No, Vacc) — the spec notes the two are locked together.
# Cond 6 carries 800V to mirror the office index: the panel defaults to the
# condition whose beam_condition.Vacc == 800, so this pair must stay present.
_CONDITION_PAIRS: tuple[tuple[int, int], ...] = ((5, 500), (6, 800))

# Stable per-tool serial used inside beam_condition.
_OPTICS: tuple[str, ...] = ("Optics_A", "Optics_B")
_DETECTORS: tuple[str, ...] = ("Upper", "Lower", "Mix")


def _timestamps(rng: random.Random, start: datetime, end: datetime) -> list[datetime]:
    """~4 measurements/day across [start, end], ascending (6~8h cadence)."""
    moments: list[datetime] = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        for hour in _DAILY_HOURS:
            moment = day.replace(hour=hour, minute=rng.choice([3, 17, 41, 58]))
            if start <= moment <= end:
                moments.append(moment)
        day += timedelta(days=1)
    moments.sort()
    return moments


def _profile(rng: random.Random, center: float, wobble: float, ndigits: int) -> dict[str, float]:
    """Per-degree dict keyed by the 16 degree strings, wobbling around center."""
    return {
        deg: round(center + rng.uniform(-wobble, wobble), ndigits)
        for deg in _DEGREE_KEYS
    }


def _summ_beam(rng: random.Random) -> dict[str, float]:
    major = round(rng.uniform(3.2, 3.8), 4)
    minor = round(major - rng.uniform(0.05, 0.35), 4)
    return {
        "Ellipticity": round(minor / major, 4),
        "Major Axis": major,
        "Minor Axis": minor,
        "Offset": round(rng.uniform(-0.5, 0.5), 4),
        "Tilt": round(rng.uniform(-12.0, 12.0), 4),
        "x_range": round(rng.uniform(2.5, 3.5), 4),
        "y_range": round(rng.uniform(2.5, 3.5), 4),
    }


def _beam_condition(
    rng: random.Random,
    *,
    serial_no: str,
    sem_cond_no: int,
    vacc: int,
) -> dict:
    return {
        "Serial_No": serial_no,
        "SEM_Cond_No": sem_cond_no,
        "Vacc": vacc,
        # Vsup wobbles a touch — the spec flags it as "worth watching".
        "Vsup": round(rng.uniform(1.78, 1.82), 4),
        "Ip": round(rng.uniform(7.5, 8.5), 2),
        "Optics": rng.choice(_OPTICS),
        "Detector": rng.choice(_DETECTORS),
        "AL3_x_offset": round(rng.uniform(-0.2, 0.2), 4),
        "AL3_y_offset": round(rng.uniform(-0.2, 0.2), 4),
    }


def _build_doc(
    rng: random.Random,
    *,
    eqp_ip: str,
    serial_no: str,
    moment: datetime,
    sem_cond_no: int,
    vacc: int,
) -> dict:
    # os_inserted trails the tool clock by the ingest hop — seconds, not hours.
    # It exists to diagnose ingest lag; nothing filters on it.
    inserted = moment + timedelta(seconds=rng.randint(20, 180))
    return {
        "ip": eqp_ip,
        "beam_condition": _beam_condition(
            rng, serial_no=serial_no, sem_cond_no=sem_cond_no, vacc=vacc
        ),
        "reso_detector": _profile(rng, 0.005, 0.0008, 6),
        "noise": _profile(rng, 6.10, 0.25, 4),
        "reso_eb": _profile(rng, 8.00, 0.30, 4),
        "summ_beam": _summ_beam(rng),
        "timestamp": moment.strftime("%Y-%m-%dT%H:%M:%S"),
        "os_inserted": inserted.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def build_network_sharpness_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Ascending-time faithful sharpness docs across [start, end].

    One doc per (timestamp, condition-pair). Deterministic per eqp_id.

    `eqp_id` selects the deterministic stream and resolves to the doc's `ip`;
    `fab_name` is accepted for dispatcher signature parity but unused, since
    the index has no fab field to fill.
    """
    rng = random.Random(seed_for(eqp_id) ^ 0x4E53_4332)  # distinct stream
    eqp_ip = eqp_ip_for(eqp_id)
    serial_no = f"SN{seed_for(eqp_id) % 100000:05d}"
    docs: list[dict] = []
    for moment in _timestamps(rng, start, end):
        for sem_cond_no, vacc in _CONDITION_PAIRS:
            docs.append(
                _build_doc(
                    rng,
                    eqp_ip=eqp_ip,
                    serial_no=serial_no,
                    moment=moment,
                    sem_cond_no=sem_cond_no,
                    vacc=vacc,
                )
            )
    docs.sort(key=lambda d: (d["timestamp"], d["beam_condition"]["SEM_Cond_No"]))
    return docs
