# TEMPLATE — copy to office.py at the office, then run the Verify command.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office MDC adapter — Redis latest snapshot + MinIO dated trend.

RECONSTRUCTED FROM THE SCHEMA DOC, NOT COPIED FROM THE OFFICE. A working
``office.py`` has existed at the office since 2026-07-27, but it is gitignored
and never reached this repo, so this body was written from
``docs/datatables/hardware_mdc_setting.txt`` plus the sibling ``sce`` adapter,
which has the identical two-tier shape. **Diff it against the office copy before
overwriting that copy** — `cp`-ing this file over a working ``office.py`` would
replace verified code with a reconstruction.

Two builders, matching ``mdc/mock.py``:

- ``build_mdc_settings`` — the LATEST collection from the Redis hash
  ``mdc_setting``: one field per fab_name (``M15A``, ``M14B``, ...), each value
  the fab's ``{eqp_id: {beam_condition: value}}`` map. The whole fab map IS the
  "selected tool + in-fab siblings" cohort the 비교 sub-tab compares.
- ``build_mdc_history`` — the dated archive from MinIO: one ``{fab_name}.json``
  per collection date under ``hitachi_sem/cdsem/mdc_setting/YYYY/MM/DD/``
  (default bucket/prefix from ``minio_handler/minio_config.py``). Dates are
  discovered, not computed — the cadence is not guaranteed regular.

MDC is a correction factor: ``result = MDC * raw measurement``. Values sit near
1.0 and are carried as STRINGS, matching the mock and the source, because they
are settings compared across tools rather than quantities to do arithmetic on.
The history series converts to float for plotting; the snapshot does not.

★ COVERAGE DIFFERS FROM SCE, AND SO DOES THE MEANING OF AN EMPTY READ.
``sce`` treats a missing hash field or archive file as a legitimate empty,
because R3/R4 don't run SCE and M10 has no data yet. MDC covers **every fab
including R3/R4** (confirmed 2026-07-27), so the same absence is a collection
failure or a lagging load. This adapter therefore logs a WARNING and returns
empty rather than silently returning empty: the tab still renders (no reason to
502 the page), but the failure is on the record. MDC is the basis for judging
tool-to-tool skew, where an unnoticed stale or absent value is the worst
available way to be wrong. Do NOT copy sce's graceful-empty path over this.

The ``as_of`` gap, inherited from sce deliberately: Redis holds only the latest
collection, so ``build_mdc_settings`` cannot honour an older ``as_of``, and the
비교 sub-tab labelled "as-of <past date>" shows today's values. The dated MinIO
archive could serve a true as-of snapshot, and that is the obvious improvement
here — left undone so this template matches ``sce``'s established behaviour
rather than quietly diverging from it. Fix both together.

At the office: fill in REDIS_* in ``back_dev_home/.env`` and
``minio_handler/minio_config.py``, ``cp providers/office_example.py
providers/office.py`` (the dispatcher), then ``cp providers/mdc/office_example.py
providers/mdc/office.py``, set ``SKEWNONO_HARDWARE_PROVIDER=office``, and run
hardware/MIGRATION.md's Verify.
"""

from __future__ import annotations

import json
import pickle
from datetime import datetime
from typing import Any

from back_dev_home._logging.providers import logger as _LOG
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home._runtime.office_redis import redis_client
from back_dev_home.ebeam.hitachi._office_search import text as _text, ttl_cache
from back_dev_home.sem_list.data import get_sem_list


__all__ = ["build_mdc_history", "build_mdc_settings"]


# Redis hash holding the latest collection: field per fab_name, value = the
# fab's {eqp_id: {beam_condition: value}} map. Overwritten in place each run —
# history lives in MinIO.
REDIS_KEY = "mdc_setting"

# MinIO date anchor (composes onto the configured default prefix): one
# {fab_name}.json per collection date under MINIO_BASE/YYYY/MM/DD/.
MINIO_BASE = "hitachi_sem/cdsem/mdc_setting"

# The archive is keyed by DATE — the path carries no time of day. The mock's
# series uses "%Y-%m-%d %H:%M", so archive dates are emitted at 00:00 to keep
# one timestamp format across providers. OFFICE-VERIFY: if the archived JSON
# turns out to carry its own collection time, use that and drop _ARCHIVE_TIME.
_ARCHIVE_TIME = "00:00"


def _parse_fab_blob(raw: bytes, fab: str) -> dict[str, Any]:
    """One hash-field value → the fab's ``{eqp_id: {condition: value}}`` map.

    The writer stores JSON; the pickle branch is a fallback in case a fab lands
    via ``pickle.dumps`` instead. Anything else is an upstream data problem →
    bare LookupError, which the app factory maps to a JSON 502. Mirrors
    ``sce/office_example.py``'s parser, which faces the same writer.
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
            f"{type(value).__name__}, expected the fab's {{eqp_id: {{...}}}} map"
        )
    return value


def _normalize_conditions(entry: Any) -> dict[str, str]:
    """One tool's raw entry → ``{beam_condition: value_string}``.

    Values stay STRINGS (the mock emits ``"1.004984"``). A numeric source cell
    is stringified rather than rejected, so a writer-side type change cannot
    blank the 비교 table. A nested or null value is dropped: rendering "None"
    in a settings cell reads as a real calibration factor.
    """
    if not isinstance(entry, dict):
        return {}
    out: dict[str, str] = {}
    for condition, value in entry.items():
        if value is None or isinstance(value, (dict, list, tuple)):
            continue
        as_text = _text(value)
        if as_text:
            out[str(condition)] = as_text
    return out


def _normalize_fab_map(fab_map: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        str(eqp): conditions
        for eqp, entry in fab_map.items()
        if (conditions := _normalize_conditions(entry))
    }


@ttl_cache
def _fab_by_eqp_id() -> dict[str, str]:
    """``eqp_id -> fab_name`` from the sem_list roster, on the shared TTL.

    ``build_mdc_history`` receives no ``fab_name`` — the dispatcher calls it
    positionally with ``(eqp_id, start, end)`` — but the MinIO archive is filed
    per fab, so the fab has to be recovered. The roster is the same source the
    tool-inventory view uses; deriving a fab from the eqp_id string instead
    would let this tab disagree with the inventory with no way to tell which is
    right.
    """
    if get_data_provider("sem_list") != "office":
        raise LookupError(
            f"{REDIS_KEY}: the hardware provider is 'office' but sem_list is on "
            "the mock provider, so eqp_id -> fab_name resolution would use "
            "fabricated fab labels and read the wrong MinIO path. Unset "
            "SKEWNONO_SEM_LIST_PROVIDER or set it to 'office'."
        )
    return {
        eqp_id: fab
        for row in get_sem_list()
        if (eqp_id := _text(row.get("eqp_id"))) and (fab := _text(row.get("fab_name")))
    }


def _resolve_fab(eqp_id: str) -> str:
    fab = _fab_by_eqp_id().get(eqp_id)
    if not fab:
        raise LookupError(
            f"{MINIO_BASE}: {eqp_id!r} has no fab_name in the sem_list roster, "
            "so its MDC archive path cannot be built. Check the tool's row in "
            "the tool-inventory view."
        )
    return fab.strip().upper()


def _warn_empty(what: str, detail: str) -> None:
    """Record an absence that MDC's fleet-wide coverage says is abnormal.

    Not an exception: blanking the whole tab helps nobody. Not silence either —
    see the COVERAGE note in the module docstring. ``_LOG`` is the providers
    logger, which carries its own INFO handler, so this line survives the root
    logger's WARNING-and-above default the way the dispatcher's fallback does.
    """
    _LOG.warning(
        "hardware/mdc: %s — %s. MDC covers every fab including R3/R4, so this "
        "is a collection or ingestion problem, not a fab that skips MDC.",
        what, detail,
    )


def _is_missing_object(exc: Exception) -> bool:
    # minio.error.S3Error carries the S3 error code.
    return getattr(exc, "code", None) in ("NoSuchKey", "NoSuchObject")


def build_mdc_settings(
    eqp_id: str,
    fab_name: str | None,
    as_of: datetime,
) -> dict[str, dict[str, str]]:
    """Latest MDC settings for the tool's fab, keyed by eqp_id.

    Redis holds only the latest collection (the hash is overwritten per run), so
    ``as_of`` exists for signature parity with the mock and does NOT select an
    older snapshot — see the ``as_of`` gap in the module docstring.
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
            settings = _normalize_fab_map(fab_map)
            if not settings:
                _warn_empty(
                    f"fab {field!r} snapshot has no usable tool entries",
                    f"Redis {REDIS_KEY}[{field}] parsed but every entry was empty",
                )
            return settings

    if not client.exists(REDIS_KEY):
        raise LookupError(
            f"Redis key {REDIS_KEY!r} does not exist — the MDC collector has "
            "not populated the hash on this instance."
        )
    _warn_empty(
        f"fab {fab_name!r} has no field in the snapshot hash",
        f"Redis {REDIS_KEY} exists but carries no {fab_name!r} field",
    )
    return {}


def build_mdc_history(
    eqp_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, str | float]]:
    """Dated MDC snapshots of ``eqp_id`` from the MinIO archive, ascending.

    LONG format, one record per (date, beam_condition) — the shape the 시계열
    sub-tab reads. A wide record per date would need the chart rewritten.

    Collection dates are discovered via a prefix walk (``list_date_folders``)
    and filtered to ``[start, end]``; the cadence is not guaranteed regular, so
    expected dates are never computed. A date whose file is missing, or whose
    file lacks this tool, is skipped — and logged, because for MDC that is not
    a fab that skips collection (see the module docstring).
    """
    # Lazy import: office-only dependency, keeps home boot free of minio_handler.
    from minio_handler import MinioObject

    fab = _resolve_fab(eqp_id)
    store = MinioObject()

    records: list[dict[str, str | float]] = []
    dates_seen = 0
    dates_missing_file = 0
    dates_missing_tool = 0

    for folder in store.list_date_folders(MINIO_BASE):
        if not (start.date() <= folder.date <= end.date()):
            continue
        dates_seen += 1
        key = f"{MINIO_BASE}/{folder.date:%Y/%m/%d}/{fab}.json"
        try:
            payload = store.get_json(key)
        except Exception as exc:
            if _is_missing_object(exc):
                dates_missing_file += 1
                continue
            raise LookupError(f"MinIO read failed for {key!r}: {exc}") from exc

        entry = payload.get(eqp_id) if isinstance(payload, dict) else None
        conditions = _normalize_conditions(entry)
        if not conditions:
            dates_missing_tool += 1
            continue

        timestamp = f"{folder.date.isoformat()} {_ARCHIVE_TIME}"
        for condition, value in conditions.items():
            try:
                mdc_value = round(float(value), 6)
            except (TypeError, ValueError):
                # A non-numeric correction factor cannot go on a trend chart.
                # Dropped rather than coerced to 0.0, which would read as a
                # catastrophic calibration rather than as bad data.
                continue
            records.append(
                {
                    "timestamp": timestamp,
                    "beam_condition": condition,
                    "mdc_value": mdc_value,
                }
            )

    if dates_missing_file or dates_missing_tool:
        _warn_empty(
            f"{eqp_id} archive gaps in {start.date()}..{end.date()}",
            f"{dates_seen} collection dates in range, {dates_missing_file} with "
            f"no {fab}.json, {dates_missing_tool} whose file lacked the tool",
        )

    records.sort(key=lambda r: (r["timestamp"], r["beam_condition"]))
    return records


if __name__ == "__main__":  # pragma: no cover
    # Office smoke check, no Flask / Nuxt / provider switch involved:
    #   python -m back_dev_home.ebeam.hitachi.hardware.providers.mdc.office
    #   python -m ...providers.mdc.office 6MCD1201 M16A 60
    #
    # Exercises THREE systems: the Redis snapshot, the sem_list roster (which
    # supplies history's fab), and the MinIO archive. The output separates them,
    # because an empty 시계열 chart looks the same whichever one is at fault.
    #
    # Each section catches its OWN failure and the run continues. Letting the
    # first exception kill the process would defeat the separation entirely:
    # run from home, where none of the three is reachable, an unguarded version
    # prints one redis traceback and never reveals that the other two are also
    # unreachable. One run should diagnose all three.
    import sys
    from datetime import timedelta

    eqp = sys.argv[1] if len(sys.argv) > 1 else "6MCD1201"
    fab_arg = sys.argv[2] if len(sys.argv) > 2 else "M16A"
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    now = datetime.now()
    _failed: list[str] = []

    def _fail(section: str, exc: Exception, hint: str) -> None:
        _failed.append(section)
        print(f"  FAILED — {type(exc).__name__}: {exc}")
        print(f"  {hint}")

    print(f"target: eqp={eqp!r} fab={fab_arg!r} window={days}d")

    print("\n--- 1. Redis snapshot (비교 sub-tab) ---")
    try:
        snapshot = build_mdc_settings(eqp, fab_arg, now)
        print(f"  {len(snapshot)} tools for fab={fab_arg!r}")
        if snapshot:
            tool, conditions = next(iter(snapshot.items()))
            print(f"  first tool: {tool}  conditions: {sorted(conditions)}")
            print(f"  values    : {conditions}")
            print("  (values are STRINGS by contract — compare, do not average)")
        else:
            print("  EMPTY — for MDC that is a collection problem, not a fab that")
            print("  skips MDC. Check the collector and this instance's Redis.")
    except Exception as exc:  # noqa: BLE001 — a diagnostic, not a control path
        _fail("Redis", exc, "Check REDIS_HOST/REDIS_PORT/REDIS_PASSWORD in "
                            "back_dev_home/.env. Expected at home: unreachable.")

    print("\n--- 2. sem_list roster (history's fab source) ---")
    roster_ok = True
    try:
        resolved = _resolve_fab(eqp)
        print(f"  {eqp} -> fab_name {resolved!r}  "
              f"(roster: {len(_fab_by_eqp_id())} tools)")
        if fab_arg and resolved != fab_arg.strip().upper():
            print(f"  NOTE the page passed fab={fab_arg!r} but the roster says "
                  f"{resolved!r}; history reads the roster's path.")
    except Exception as exc:  # noqa: BLE001
        roster_ok = False
        _fail("sem_list", exc, "history cannot build its MinIO path without a "
                               "fab. sem_list must be on the office provider.")

    print("\n--- 3. MinIO archive (시계열 sub-tab) ---")
    if not roster_ok:
        # build_mdc_history resolves the fab BEFORE touching MinIO, so running
        # it now would re-raise section 2's error under a MinIO heading and send
        # the reader to minio_config.py for a roster problem. Say what is
        # actually true: this section never ran.
        print("  SKIPPED — blocked by section 2. The archive path is "
              f"{MINIO_BASE}/YYYY/MM/DD/<fab>.json and the fab is unknown, so "
              "MinIO was not contacted and is NOT implicated here.")
        _failed.append("MinIO (not reached)")
    else:
        try:
            series = build_mdc_history(eqp, now - timedelta(days=days), now)
            print(f"  {len(series)} records over the last {days}d")
            if series:
                dates = sorted({str(r["timestamp"])[:10] for r in series})
                conds = sorted({str(r["beam_condition"]) for r in series})
                print(f"  collection dates ({len(dates)}): {dates}")
                print(f"  conditions: {conds}")
                print(f"  first record: {series[0]}")
                # OFFICE-VERIFY: 00:00 stands in for a time the archive path
                # does not carry. If the JSON has a real collection time, use it.
                print(f"  (time-of-day is {_ARCHIVE_TIME} — the path is date-only)")
            else:
                print("  EMPTY — check the prefix walk first:")
                print(f"    MinioObject().list_date_folders({MINIO_BASE!r})")
        except Exception as exc:  # noqa: BLE001
            _fail("MinIO", exc, "Check minio_handler/minio_config.py "
                                "(bucket/prefix come from there, NOT from .env).")

    print()
    if _failed:
        print(f"UNREACHABLE: {', '.join(_failed)}")
        print("At home all three are expected to fail — that is not a code "
              "problem. At the office, each line above names its own cause.")
        sys.exit(1)
    print("OK — all three systems answered.")
