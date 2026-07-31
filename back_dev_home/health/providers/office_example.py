# TRACKED COPY of the office adapter — fully implemented, nothing to fill in.
# The office step is just `cp office_example.py office.py` (office.py is
# gitignored so `git pull` never conflicts on it). Edit this file, not the copy.
"""Office adapter for health — live Redis / OpenSearch / MinIO probes.

The probes themselves are in `probe_common.py`, shared with `mock.py`, because
two copies of the same three checks is exactly how the MinIO probe once ended
up un-chained here and still chained there. What lives in this file is what is
office-only: the standalone self-check below, and the raw payload dump that
makes schema drift visible.

Difference from `providers/mock.py`: mock.py answers canned `"mock · "` rows
**in mock mode only** — it never fakes health at the office. In office mode
both modules call the same `probe_services()`, so an office machine that has
not yet cp'd this file gets the same truthful answer, just without the
self-check.

Config (all from `back_dev_home/.env`, loaded by the app factory; the shared
helpers self-load it for standalone runs):

- Redis      : `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD`
               — via the shared fail-fast client in `_runtime/office_redis.py`
- OpenSearch : `OPENSEARCH_*` (read by `ops_store`), index `meas_hist_cdsem`,
               "up" when the newest doc's `timestamp` is < 1h old
- MinIO      : `minio_handler/minio_config.py` (gitignored — NOT .env; env
               vars would override that file), lists the configured
               bucket/prefix — a plain connectivity + auth check, independent
               of the other two

Self-check at the office, from the repo root:

    python -m back_dev_home.health.providers.office

Prints one line per service, dumps the raw payloads, and exits 1 if any is
down. The raw capture is a dict `_main()` passes into the probes, so the
request path collects nothing and does no extra server work.

Contract invariant: `get_services_health()` never raises and always returns
exactly three rows in the order [redis, opensearch, minio]. Each probe traps
its own exceptions, so flipping health to office can never 500 the endpoint or
break app startup. The failure detail sent to the client is the exception
CLASS only — `/api/health/services` is open to every user and a driver's
message carries internal hostnames and ports; the full text goes to the
`skewnono.health` log (see `probe_common.failure_row`).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from back_dev_home._runtime.office_redis import load_env_file
from back_dev_home.health.contracts import ServicesHealthResponse
from back_dev_home.health.providers.probe_common import probe_services


__all__ = ["get_services_health"]


# Cap per dumped section: a meas_hist doc can carry dozens of fields and a
# prefix can hold hundreds of folders. Enough to verify parsing, short enough
# to read in a terminal.
_DUMP_CHAR_LIMIT = 4000


def get_services_health() -> ServicesHealthResponse:
    # No capture argument: the HTTP path is a liveness check, nothing more.
    return probe_services()


def _dump(label: str, payload: Any) -> None:
    """Print a raw payload as readable JSON.

    `default=str` because these payloads carry datetimes and bytes straight
    off the wire — a TypeError from the serializer would hide the very data
    the dump exists to show. ensure_ascii=False keeps Korean field values
    legible instead of \\uXXXX escapes.
    """
    print(f"\n── {label} ─────────────────────────────────")
    if not payload:
        print("  (nothing extracted — the probe failed before reading data)")
        return
    text = json.dumps(payload, indent=2, default=str, ensure_ascii=False)
    if len(text) > _DUMP_CHAR_LIMIT:
        text = text[:_DUMP_CHAR_LIMIT] + f"\n  … truncated at {_DUMP_CHAR_LIMIT} chars"
    print(text)


def _main() -> int:
    """Standalone probe: `python -m back_dev_home.health.providers.office`.

    Run from the repo root at the office to check this adapter end to end
    without Flask, Nuxt or the provider switch in the way. Prints the summary
    each service would return over HTTP, then dumps the raw payload pulled
    from each server so you can confirm the parsing — field names, timestamp
    formats, object keys — rather than trusting a green "up". Exits 1 if any
    service is down, so it doubles as a shell check.

    The HTTP `detail` deliberately says only `probe failed (ConnectionError)`,
    so logging is configured here: the driver's real message goes to the log,
    and on a self-check that log is the whole point.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    load_env_file("REDIS_HOST")

    raw: dict[str, Any] = {}
    result = probe_services(capture=raw)

    print(f"checked_at: {result['checked_at']}")
    for svc in result["services"]:
        mark = "OK  " if svc["status"] == "up" else "DOWN"
        latency = "—" if svc["latency_ms"] is None else f"{svc['latency_ms']}ms"
        print(f"  [{mark}] {svc['label']:<11} {latency:>8}  {svc['detail']}")

    print("\n=== RAW DATA AS EXTRACTED ===")
    for svc in result["services"]:
        _dump(svc["label"], raw.get(svc["id"]))

    down = [s["label"] for s in result["services"] if s["status"] == "down"]
    if down:
        print(f"\n{len(down)} down: {', '.join(down)}")
        return 1
    print("\nall services up")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
