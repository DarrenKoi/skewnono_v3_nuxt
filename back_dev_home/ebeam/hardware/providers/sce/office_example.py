# TEMPLATE — copy to office.py at the office, then run the Verify command.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office SCE adapter — Redis latest snapshot + MinIO bidaily trend.

Two builders, matching ``sce/mock.py``:

- ``build_sce_settings`` — the LATEST collection from the Redis hash
  ``sce_info``: one field per fab_name (``M15A``, ``M14B``, ...), each value
  the fab's ``{eqp_id: {FileInfo, SemCond, ImgCond, SCEParam, Coefficients}}``
  dict (see ``docs/datatables/hitachi/hardware_sce_setting.txt``). The whole fab map IS the
  "selected tool + in-fab siblings" cohort the page compares.
- ``build_sce_history`` — the bidaily archive from MinIO: one
  ``{fab_name}.json`` per collection date under
  ``hitachi_sem/cdsem/sce_info/YYYY/MM/DD/`` (default bucket/prefix from
  ``minio_handler/minio_config.py``). Dates are discovered, not computed —
  the cadence is bidaily-ish (07/17, 07/22, 07/24, ...), not strictly
  regular.

Coverage: SCE runs in 양산 M-fabs only. R3/R4 don't use it, and M10 has no
data yet — an absent hash field / archive file is a legitimate empty, NOT an
error, so those fabs return ``{}`` / ``[]`` and the page shows its graceful
empty state instead of a 502.

The top-level ``providers/office.py`` dispatcher wraps both with
``normalizers.settings_payload`` (settings + docs), like ``mdc``.

At the office: fill in REDIS_* in ``back_dev_home/.env`` and
``minio_handler/minio_config.py``, ``cp office_example.py office.py``, set
``SKEWNONO_HARDWARE_PROVIDER=office``, then run the Verify command in
``hardware/MIGRATION.md``.
"""

from __future__ import annotations

import json
import pickle
from datetime import datetime
import math
from typing import Any

from back_dev_home._runtime.office_redis import redis_client


__all__ = ["build_sce_history", "build_sce_settings"]


# Redis hash holding the latest collection: field per fab_name, value = the
# fab's dict-of-dict. Overwritten in place each run — history lives in MinIO.
REDIS_KEY = "sce_info"

# MinIO date anchor (composes onto the configured default prefix): one
# {fab_name}.json per collection date under MINIO_BASE/YYYY/MM/DD/.
MINIO_BASE = "hitachi_sem/cdsem/sce_info"

# Per-eqp setting blocks passed through verbatim when present as dicts.
_BLOCK_KEYS = ("FileInfo", "SemCond", "ImgCond", "SCEParam")


def _parse_fab_blob(raw: bytes, fab: str) -> dict[str, Any]:
    """One hash-field value → the fab's ``{eqp_id: entry}`` dict.

    The writer stores JSON; the pickle branch is a fallback in case a fab
    lands via ``pickle.dumps`` instead. Anything else is an upstream data
    problem → bare LookupError, which the app factory maps to a JSON 502.
    """
    if raw.lstrip()[:1] in (b"{", b"["):
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LookupError(
                f"Redis {REDIS_KEY!r}[{fab!r}] looks like JSON but does not "
                f"parse -> {type(exc).__name__}: {exc}"
            ) from exc
    else:
        try:
            value = pickle.loads(raw)
        except Exception as exc:
            raise LookupError(
                f"Could not deserialize Redis {REDIS_KEY!r}[{fab!r}] "
                f"(first bytes: {raw[:16].hex(' ')!r}, length {len(raw)}). "
                f"Real error -> {type(exc).__name__}: {exc}."
            ) from exc
    if not isinstance(value, dict):
        raise LookupError(
            f"Redis {REDIS_KEY!r}[{fab!r}] deserialized to "
            f"{type(value).__name__}, expected the fab's dict-of-dict"
        )
    return value


def _as_float(value: Any) -> float | None:
    """Coerce a source cell (float OR numeric string) to a finite float.

    Same contract as the bsm / reso_center helpers of the same name.
    """
    if isinstance(value, bool):  # bool is an int subclass — never a measurement
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return parsed if math.isfinite(parsed) else None


def _normalize_coefficients(raw: Any) -> list[dict]:
    """Source curve → the mock's ``[{'index': int, 'values': [...]}]`` list.

    The canonical source shape is already a list of ``{index, values}`` dicts
    (indices 0..359); the dict form (``{"0": [...]}``) and the bare
    list-of-pairs form are normalized too so a writer-side representation
    change cannot silently blank the curve chart. Entries whose index does
    not parse are dropped; output is ascending by index.
    """
    pairs: list[tuple[int, Any]] = []
    if isinstance(raw, dict):
        items: Any = raw.items()
        for idx, vals in items:
            pairs.append((idx, vals))
    elif isinstance(raw, list):
        for pos, entry in enumerate(raw):
            if isinstance(entry, dict):
                pairs.append((entry.get("index", pos), entry.get("values")))
            else:
                pairs.append((pos, entry))
    out: list[dict] = []
    for idx, vals in pairs:
        try:
            index = int(idx)
        except (TypeError, ValueError):
            continue
        if not isinstance(vals, (list, tuple)):
            continue
        # Coerce, do not pass through. The sibling bsm / reso_center adapters
        # run every source cell through _as_float because these indices store
        # measurements as float OR numeric string; sce alone forwarded the raw
        # list, so a stringified curve would reach a `values: list[float]`
        # contract as strings and only misbehave at render time. The mock emits
        # rounded floats, so home can never show this.
        out.append({"index": index, "values": [_as_float(v) for v in vals]})
    out.sort(key=lambda c: c["index"])
    return out


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """One eqp's raw entry → the mock's five-block shape."""
    out: dict[str, Any] = {
        key: entry[key] for key in _BLOCK_KEYS if isinstance(entry.get(key), dict)
    }
    out["Coefficients"] = _normalize_coefficients(entry.get("Coefficients"))
    return out


def _normalize_fab_map(fab_map: dict[str, Any]) -> dict[str, dict]:
    return {
        eqp: _normalize_entry(entry)
        for eqp, entry in fab_map.items()
        if isinstance(entry, dict)
    }


def build_sce_settings(
    eqp_id: str,
    fab_name: str | None,
    as_of: datetime,
) -> dict[str, dict]:
    """Latest SCE settings for the tool's fab, keyed by eqp_id.

    Redis holds only the latest collection (the hash is overwritten per run),
    so ``as_of`` exists for signature parity with the mock and does not select
    an older snapshot — ``build_sce_history`` covers that. A fab with no hash
    field (R3/R4 don't run SCE; M10 has no data yet) returns ``{}``.
    """
    del as_of
    client = redis_client()
    fields: list[str]
    if fab_name:
        fields = [fab_name.strip().upper()]
    else:
        # No fab given (shouldn't happen from the page): scan fields for the
        # tool. Fields are per-fab and few; values are fetched one at a time.
        fields = [f.decode("utf-8") for f in client.hkeys(REDIS_KEY)]

    for field in fields:
        raw = client.hget(REDIS_KEY, field)
        if raw is None:
            continue
        fab_map = _parse_fab_blob(raw, field)
        if fab_name or eqp_id in fab_map:
            return _normalize_fab_map(fab_map)

    if fab_name and not client.exists(REDIS_KEY):
        raise LookupError(
            f"Redis key {REDIS_KEY!r} does not exist — the SCE collector has "
            "not populated the hash on this instance."
        )
    return {}


def _is_missing_object(exc: Exception) -> bool:
    # minio.error.S3Error carries the S3 error code; a missing per-fab file on
    # a collection date is expected (not every fab uploads every run).
    return getattr(exc, "code", None) in ("NoSuchKey", "NoSuchObject")


def build_sce_history(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Bidaily SCE snapshots of ``eqp_id`` from the MinIO archive, ascending.

    Collection dates are discovered via a cheap prefix walk
    (``list_date_folders``), scoped to ``[start, end]``. A date without this
    fab's file, or whose file lacks the tool, is skipped. Each doc is the
    mock-shaped settings block plus the collection ``date`` (YYYY-MM-DD).
    """
    if not fab_name:
        return []
    # Lazy import: office-only dependency, keeps home boot free of minio_handler.
    from minio_handler import MinioObject

    store = MinioObject()
    fab = fab_name.strip().upper()
    docs: list[dict] = []
    for folder in store.list_date_folders(MINIO_BASE):
        if not (start.date() <= folder.date <= end.date()):
            continue
        key = f"{MINIO_BASE}/{folder.date:%Y/%m/%d}/{fab}.json"
        try:
            payload = store.get_json(key)
        except Exception as exc:
            if _is_missing_object(exc):
                continue
            raise LookupError(f"MinIO read failed for {key!r}: {exc}") from exc
        entry = payload.get(eqp_id) if isinstance(payload, dict) else None
        if isinstance(entry, dict):
            docs.append({"date": folder.date.isoformat(), **_normalize_entry(entry)})
    return docs


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #   .venv/bin/python -m back_dev_home.ebeam.hardware.providers.sce.office <eqp_id> <fab_name>
    import sys
    from datetime import timedelta

    # Default to a real M-fab SCE tool so a no-arg run prints actual data
    # instead of empty (build_sce_settings needs a fab, build_sce_history
    # returns [] without one). Override by passing <eqp_id> <fab_name>.
    eqp = sys.argv[1] if len(sys.argv) > 1 else "6MCD1201"
    fab = sys.argv[2] if len(sys.argv) > 2 else "M16A"
    now = datetime.now()

    settings = build_sce_settings(eqp, fab, now)
    print(f"settings: {len(settings)} tools for fab={fab!r}")
    if settings:
        tool, entry = next(iter(settings.items()))
        print("first tool:", tool, "| blocks:", sorted(entry.keys()))
        print("coefficients:", len(entry.get("Coefficients", [])))

    docs = build_sce_history(eqp, fab, now - timedelta(days=30), now)
    print(f"history: {len(docs)} snapshots for eqp={eqp!r}")
    if docs:
        print("dates:", [d["date"] for d in docs])
