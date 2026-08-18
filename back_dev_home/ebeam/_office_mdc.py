"""Office-side plumbing: MDC settings, and WHEN each of them changed.

MDC (Meas Data Correction) is the per-tool, per-beam factor the tool applies to
every measurement — ``result = MDC x actual`` — so a change to it moves that
tool's numbers without anything about the tool having moved. Two features need
that fact, and neither of them needs the hardware page's version of it:

* **tttm** cannot compare two tools across an MDC change. A pairwise skew
  pooled over a boundary is the change, reported as a tool difference.
* **pm_planning** shows an Up-gate whose whole question is "did anything change
  since the last PM", and an MDC edit is one of the two things that can have.

``hardware/providers/mdc/office_example.py`` reads the SAME two sources for the
hardware tab (a fab-wide snapshot table and a per-tool trend chart), but it is a
gitignored-copy TEMPLATE and it answers a different question — it lists values,
never boundaries. Importing it would also couple two features to whether the
hardware adapter happens to have been ``cp``-ed. This module is TRACKED, so it
travels with ``git pull``, and it answers only the boundary question.

Sources (docs/datatables/hardware_mdc_setting.txt, 담당자 확인 2026-07-27):

* Redis hash ``mdc_setting`` — field per ``fab_name``, value the fab's
  ``{eqp_id: {beam_condition: value}}`` map. Overwritten in place: latest only.
* MinIO ``hitachi_sem/cdsem/mdc_setting/YYYY/MM/DD/{fab_name}.json`` — one file
  per collection date, the same dict-of-dict shape. This is the only place
  history exists, so every "when did it change" answer is a walk of these.

★ An empty read is ABNORMAL here, unlike SCE. MDC covers every fab including
R3/R4, so a missing hash field or archive file is a collection failure, not a
fab that opts out. Callers get an empty result (blanking a page helps nobody)
and the failure goes to the log — see ``_warn_empty``. For a feature whose
whole subject is tool-to-tool skew, a silently stale MDC is the worst available
way to be wrong.

Collection dates are DISCOVERED, never computed: the cadence is not guaranteed
regular, so a walk that assumed daily files would read a gap as a change.
"""

from __future__ import annotations

import json
import pickle
from datetime import date, datetime
from functools import lru_cache
from typing import Any, NamedTuple

from back_dev_home._logging.providers import logger as _LOG


__all__ = [
    "MDC_MINIO_BASE",
    "MDC_REDIS_KEY",
    "MdcChange",
    "archive_dates",
    "changes",
    "latest_snapshot",
    "snapshot_on",
    "split_condition",
]


# Redis hash: field per fab_name, value = that fab's dict-of-dict map.
MDC_REDIS_KEY = "mdc_setting"

# MinIO anchor; composes onto the configured default prefix. One
# {fab_name}.json per collection date beneath it.
MDC_MINIO_BASE = "hitachi_sem/cdsem/mdc_setting"


class MdcChange(NamedTuple):
    """One observed edit of one tool's correction factor."""

    eqp_id: str
    condition: str          # raw key, e.g. "500V_HR_0Deg"
    beam_condition: str     # "500V_HR"
    axis: str | None        # "X" | "Y" | None when the suffix is not a rotation
    on: date                # the first collection date carrying the new value
    old_value: float
    new_value: float


def _warn_empty(what: str, detail: str) -> None:
    _LOG.warning(
        "mdc: %s — %s. MDC covers every fab including R3/R4, so this is a "
        "collection or ingestion problem, not a fab that skips MDC.",
        what, detail,
    )


# ── the beam_condition key ─────────────────────────────────────────────────

# The archive keys look like "800V_HR_0Deg": voltage, optics, rotation. The
# first two together are the BEAM; the last is what both contracts call an axis.
_ROTATION_TO_AXIS = {"0deg": "X", "90deg": "Y"}


def split_condition(condition: str) -> tuple[str, str | None]:
    """``"500V_HR_0Deg"`` -> ``("500V_HR", "X")``. Unknown suffix -> ``None``.

    OFFICE-VERIFY, and it is item 4 of
    ``docs/research/2026-08-16-skew-tttm-feasibility.md`` section 6: whether
    ``0Deg``/``90Deg`` names the image rotation or the measurement direction is
    unconfirmed. Both contracts type their axis as ``Literal["X", "Y"]``, so
    this mapping is what fills it — if the office answer turns out to be
    "image rotation", the axis on every cell means something else and the
    mapping here is the single line to change.

    A key whose tail is not a rotation (a tool carrying a bare ``3000V``, say)
    returns ``None`` rather than a guess: callers drop it, and a dropped cell
    is visible where a mislabelled one is not.
    """
    parts = condition.strip().split("_")
    if len(parts) < 2:
        return condition.strip(), None
    axis = _ROTATION_TO_AXIS.get(parts[-1].casefold())
    if axis is None:
        return condition.strip(), None
    return "_".join(parts[:-1]), axis


# ── reads ──────────────────────────────────────────────────────────────────


def _conditions(entry: Any) -> dict[str, float]:
    """One tool's raw entry -> ``{condition: float}``.

    The source carries these as strings ("1.004984") and the hardware tab keeps
    them that way, because there they are settings to compare rather than
    quantities to compute with. Here they ARE computed with — a change is a
    difference — so they are floats, and a value that will not parse is dropped
    rather than coerced to 0.0, which would read as a catastrophic
    recalibration instead of as bad data.
    """
    if not isinstance(entry, dict):
        return {}
    out: dict[str, float] = {}
    for condition, value in entry.items():
        try:
            out[str(condition)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def _parse_fab_blob(raw: bytes, fab: str) -> Any:
    """One Redis hash-field value -> the fab's raw map.

    The writer stores JSON; the pickle branch is a fallback in case a fab lands
    via ``pickle.dumps`` instead. Mirrors ``hardware/providers/mdc`` and
    ``sce``, which face the same writer — keep the three in step.
    """
    if raw.lstrip()[:1] in (b"{", b"["):
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LookupError(
                f"Redis {MDC_REDIS_KEY!r}[{fab!r}] looks like JSON but does "
                f"not parse -> {type(exc).__name__}: {exc}"
            ) from exc
    try:
        return pickle.loads(raw)
    except Exception as exc:  # noqa: BLE001 — any unpickling failure is data
        raise LookupError(
            f"Could not deserialize Redis {MDC_REDIS_KEY!r}[{fab!r}] "
            f"(first bytes: {raw[:16].hex(' ')!r}, length {len(raw)}). "
            f"Real error -> {type(exc).__name__}: {exc}."
        ) from exc


def _fab_map(payload: Any) -> dict[str, dict[str, float]]:
    if not isinstance(payload, dict):
        return {}
    return {
        str(eqp): conditions
        for eqp, entry in payload.items()
        if (conditions := _conditions(entry))
    }


def latest_snapshot(fab_name: str) -> dict[str, dict[str, float]]:
    """The fab's current MDC map from Redis, ``{eqp_id: {condition: value}}``."""
    from back_dev_home._runtime.office_redis import redis_client

    fab = fab_name.strip().upper()
    client = redis_client()
    raw = client.hget(MDC_REDIS_KEY, fab)
    if raw is None:
        _warn_empty(
            f"fab {fab!r} has no field in the snapshot hash",
            f"Redis {MDC_REDIS_KEY} carries no {fab!r} field",
        )
        return {}
    return _fab_map(_parse_fab_blob(raw, fab))


def _is_missing_object(exc: Exception) -> bool:
    return getattr(exc, "code", None) in ("NoSuchKey", "NoSuchObject")


@lru_cache(maxsize=8)
def archive_dates(fab_name: str) -> tuple[date, ...]:
    """Every collection date present in the MinIO archive, ascending.

    Cached per fab for the process: the walk is three levels of common-prefix
    listing with no payload objects, but a fleet request would otherwise repeat
    it once per tool. A long-lived office worker will therefore not notice a
    new collection date until restart — acceptable because every caller here
    reads a window that ends days ago, and unacceptable to fix with a TTL that
    re-walks on a page the user is clicking through.
    """
    del fab_name  # the walk is fab-independent; the parameter keys the cache
    from minio_handler import MinioObject

    folders = MinioObject().list_date_folders(MDC_MINIO_BASE)
    return tuple(folder.date for folder in folders)


@lru_cache(maxsize=512)
def snapshot_on(fab_name: str, on: date) -> dict[str, dict[str, float]]:
    """The fab's whole MDC map as archived on one collection date.

    ``{}`` when that date's file is missing — logged, because for MDC a gap is
    an ingestion problem. Cached per (fab, date): a 60-day window is 60 GETs
    the first time and none afterwards, and the archive for a past date never
    changes.
    """
    from minio_handler import MinioObject

    fab = fab_name.strip().upper()
    key = f"{MDC_MINIO_BASE}/{on:%Y/%m/%d}/{fab}.json"
    try:
        payload = MinioObject().get_json(key)
    except Exception as exc:  # noqa: BLE001 — re-raised unless it is a 404
        if _is_missing_object(exc):
            _warn_empty(
                f"no archive file for {fab} on {on}",
                f"MinIO {key!r} is absent",
            )
            return {}
        raise LookupError(f"MinIO read failed for {key!r}: {exc}") from exc
    return _fab_map(payload)


def changes(
    fab_name: str,
    start: datetime | date,
    end: datetime | date,
) -> list[MdcChange]:
    """Every MDC edit visible in ``[start, end]``, oldest first.

    An edit is a value that DIFFERS from the previous collection date's value
    for the same (tool, condition). The first date in the window establishes the
    baseline and can therefore never itself be a change — which is why the walk
    starts one archived date BEFORE ``start`` when one exists. Without that, a
    tool edited the day before the window opens looks unchanged for the whole
    window, and the epoch boundary the caller is looking for is exactly the one
    that goes missing.

    A tool or condition that appears for the first time is not a change: there
    is no old value to have moved away from.
    """
    lo = start.date() if isinstance(start, datetime) else start
    hi = end.date() if isinstance(end, datetime) else end
    dates = [d for d in archive_dates(fab_name) if d <= hi]
    if not dates:
        return []
    in_window = [d for d in dates if d >= lo]
    if not in_window:
        return []
    # One date of run-up, so the first in-window date is compared against
    # something rather than establishing a baseline it can never contradict.
    first_index = dates.index(in_window[0])
    walk = dates[max(0, first_index - 1):]

    found: list[MdcChange] = []
    previous = snapshot_on(fab_name, walk[0])
    for on in walk[1:]:
        current = snapshot_on(fab_name, on)
        if not current:
            continue  # a gap is not a change; keep `previous` as the baseline
        for eqp_id, conditions in current.items():
            before = previous.get(eqp_id, {})
            for condition, value in conditions.items():
                old = before.get(condition)
                if old is None or old == value:
                    continue
                beam, axis = split_condition(condition)
                found.append(
                    MdcChange(
                        eqp_id=eqp_id,
                        condition=condition,
                        beam_condition=beam,
                        axis=axis,
                        on=on,
                        old_value=old,
                        new_value=value,
                    )
                )
        previous = current

    return [change for change in found if lo <= change.on <= hi]
