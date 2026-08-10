"""Time the msr_image tool-FTP path so its tuning constants stop being guesses.

Four numbers in the image feature were picked from reasoning rather than
measurement, and every one of them is only checkable at the office. This script
takes them one at a time against a real tool and prints what the code should
say.

WHAT IT ANSWERS

  A. connect + login cost      -> is FTP connection pooling worth building?
     ``fetch_image`` opens a fresh session per image today, so a cold gallery
     pays this once per file. If login is a rounding error next to the transfer
     there is nothing to win; if it is comparable, pooling is the single
     biggest lever on the cold path.

  B. per-image transfer cost   -> is ``_SECONDS_PER_IMAGE = 5.0`` right?
     That constant (msr_image/providers/office_example.py) sizes a warm job's
     ``host_timeout``. Too small and big jobs get abandoned mid-transfer; too
     large and a genuinely stalled connection is held for minutes. It is
     currently marked OFFICE-VERIFY.

  C. concurrency scaling       -> is ``ftp_concurrency = 6`` the right fan-out?
     ``download_all`` splits one MSR's files over n connections to the SAME
     tool. Whether the tool's FTP server actually serves 6 streams faster than
     3 is a property of the server, not of our code.

  D. MinIO PUT cost (opt-in)   -> is inline cache-writing worth pipelining?
     The cache write runs INSIDE the FTP worker thread, so it blocks that
     connection's next RETR. Pipelining it is only worth the complexity if the
     PUT is a real fraction of the fetch.

NOTHING HERE WRITES TO A TOOL. Stages A-C are reads. Stage D is opt-in
(``--minio``), writes only under ``<cache prefix>_measure/``, and deletes what
it wrote before returning.

RUN IT (from the repo root, office only -- tools are unreachable from home)::

    .venv/bin/python -m scripts.measure_msr_image_ftp
    .venv/bin/python -m scripts.measure_msr_image_ftp --images 16 --minio
    .venv/bin/python -m scripts.measure_msr_image_ftp \
        --eqp-ip 10.1.2.3 --class-name ADI --msr 20260428_ADI_CD_..._ECXDX123
    .venv/bin/python -m scripts.measure_msr_image_ftp --direct   # bypass the proxy

With no locator it finds one itself: the newest meas_hist document that carries
both ``eqp_ip`` and ``msr``, the same discovery
``msr_image/providers/office_example.py``'s own smoke test uses.

The run uses a deliberately huge ``host_timeout`` so that NOTHING is abandoned
mid-measurement -- an abandoned host reports a failure instead of a duration,
which would silently bias every average here toward the fast files.

READING THE RESULT

The verdict block at the end prints the constants as they would be written in
source, with the headroom already applied. Copy them into
``office_example.py`` / the env, and replace the ``OFFICE-VERIFY`` mark with
``office 확인 YYYY-MM-DD``. If a recommendation exceeds the proxy ceiling the
block says so rather than printing a number that cannot be deployed: the proxy
host's uWSGI kills a request at ``harakiri`` (75s, ftp_handler/proxy/wsgi.ini),
and one request carries a whole BATCH of specs, so a budget above it loses the
batch rather than buying time.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import threading
import time
from dataclasses import replace
from typing import Any

from back_dev_home._runtime.office_redis import load_env_file
from back_dev_home.msr_image.config import ImageConfig, load_config
from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.paths import image_dir, validate_tool_ip

# Big enough that no stage is ever cut short by the backstop it is trying to
# measure. Every stage here is bounded by --images instead.
_MEASURE_HOST_TIMEOUT = 3600.0

# Multiplier applied to the observed worst case before it is recommended as a
# constant. A tool that is 2x slower than the day we measured must still finish;
# the cost of being generous is only that a truly stalled connection is held
# longer, and connect_timeout (not this) is what detects a dead tool.
_HEADROOM = 2.0

# ftp_handler/proxy/wsgi.ini. Mirrored rather than parsed: the file lives on the
# proxy host, and a stale mirror that prints a warning is better than a parse
# that silently finds nothing.
_PROXY_HARAKIRI = 75.0

# A fan-out level has to beat the baseline by this much before the verdict calls
# it a winner. One tool, one run, a handful of files -- anything under this is
# noise, and a confident recommendation built on noise is worse than silence.
_MIN_MEANINGFUL_GAIN = 1.15


# ── target discovery ──────────────────────────────────────────────────────


def _discover() -> tuple[str, str, str]:
    """Newest meas_hist document that names both a tool and an MSR.

    Imported lazily: OpenSearch is an office-only dependency and an explicit
    --eqp-ip run should not need it at all.
    """
    from back_dev_home.ebeam._office_meas_hist import ALL_INDICES, search, text

    body = {
        "query": {"bool": {"filter": [
            {"exists": {"field": "eqp_ip"}},
            {"exists": {"field": "msr"}},
        ]}},
        "sort": [{"timestamp": "desc"}],
        "size": 1,
    }
    hits = search(ALL_INDICES).search_raw(body).get("hits", {}).get("hits", [])
    if not hits:
        raise SystemExit("no meas_hist doc carries both eqp_ip and msr — check ingestion")
    src = hits[0].get("_source", {})
    return text(src.get("eqp_ip")), text(src.get("class_name")), text(src.get("msr"))


# ── stages ────────────────────────────────────────────────────────────────


def _stage_a_login(office: Any, cfg: ImageConfig, eqp_ip: str, rounds: int) -> float:
    """Median seconds for connect + login + quit, with no file transferred.

    Uses the downloader's own listing call against a directory that does not
    exist: the session is opened and torn down exactly as a real fetch would,
    while the NLST that fails costs one round trip instead of a file. The
    failure is the expected outcome, so it is not reported as an error.
    """
    print("\n── A. connect + login ────────────────────────────────────────")
    HostSpec, ListDir = office.HostSpec, office.ListDir
    samples: list[float] = []
    for i in range(rounds):
        started = time.monotonic()
        office._downloader(cfg).list_dirs(
            [HostSpec(eqp_ip, listings=[ListDir("/__skewnono_measure_nonexistent__")])]
        )
        samples.append(time.monotonic() - started)
        print(f"   round {i + 1}/{rounds}: {samples[-1] * 1000:7.1f} ms")
    median = statistics.median(samples)
    print(f"   median {median * 1000:.1f} ms   min {min(samples) * 1000:.1f}"
          f"   max {max(samples) * 1000:.1f}")
    return median


def _stage_b_serial(
    office: Any, cfg: ImageConfig, eqp_ip: str, class_name: str, msr: str,
    names: list[str], login: float,
) -> tuple[list[float], int]:
    """Time ``fetch_image`` per image — the real cold-GET path.

    This is what a browser waits on when the cache misses: a fresh downloader,
    a fresh login, then the image and its cond sidecar. Subtracting the Stage A
    login median is what separates "the tool is slow" from "we reconnect too
    much".
    """
    print("\n── B. per-image cold fetch (fresh login each) ────────────────")
    durations: list[float] = []
    total_bytes = 0
    failed = 0
    for name in names:
        started = time.monotonic()
        try:
            fetched = office.fetch_image(
                ImageLocator(eqp_ip, class_name, msr, name), _config=cfg
            )
        except Exception as exc:  # noqa: BLE001 - one bad file is data, not an abort
            # A measurement run must survive a file the tool will not serve.
            # Aborting throws away every timing already collected and forces a
            # whole new run per bad file -- and each run costs real minutes
            # against a real tool. Report it and keep going; the verdict block
            # is computed from whatever succeeded.
            failed += 1
            print(f"   {name[:44]:44s}  SKIP  {type(exc).__name__}: {exc}")
            continue
        elapsed = time.monotonic() - started
        durations.append(elapsed)
        total_bytes += len(fetched.data)
        transfer = max(0.0, elapsed - login)
        rate = (len(fetched.data) / transfer / 1e6) if transfer > 0 else float("inf")
        print(f"   {name[:44]:44s} {elapsed:6.2f}s  {len(fetched.data) / 1e6:6.2f} MB"
              f"  ({rate:5.1f} MB/s excl. login, cond={'y' if fetched.cond else 'n'})")
    if failed:
        print(f"   {failed} of {len(names)} could not be fetched — listing and RETR "
              f"disagree about what exists")
    if not durations:
        raise SystemExit(
            "every image failed to fetch — nothing to measure. The listing "
            "returned names the tool will not serve; check list_images's filter."
        )
    return durations, total_bytes


def _stage_c_concurrency(
    office: Any, cfg: ImageConfig, eqp_ip: str, class_name: str, msr: str,
    names: list[str], fanouts: list[int],
) -> dict[int, tuple[float, int]]:
    """Wall time for the whole set at each fan-out, via the real download_all.

    Driving ``download_all`` rather than hand-rolling the chunking means the
    number measured is the number the adapter will actually produce, including
    its image/cond pairing work.
    """
    print("\n── C. concurrency scaling (download_all) ─────────────────────")
    results: dict[int, tuple[float, int]] = {}
    for n in fanouts:
        scoped = replace(cfg, ftp_concurrency=n)
        # Built per iteration by a factory rather than closing over loop-local
        # names: `download_all` happens to call back synchronously, so the late
        # binding is harmless today, but it is one `asyncio` away from every
        # fan-out writing into the last iteration's counters.
        on_file, tally = _make_file_collector()

        started = time.monotonic()
        office.download_all(
            eqp_ip, class_name, msr, list(names), on_file, concurrency=n, _config=scoped
        )
        elapsed = time.monotonic() - started
        ok, failed = tally()
        results[n] = (elapsed, ok)
        per_conn = -(-len(names) // n)  # ceil: the busiest connection's share
        line = (f"   n={n:2d}  {elapsed:6.2f}s total   {elapsed / max(1, ok):5.2f}s/image"
                f"   {elapsed / max(1, per_conn):5.2f}s per image ON THE BUSIEST CONN"
                f"   ok={ok}/{len(names)}")
        print(line)
        for f in failed[:3]:
            print(f"       FAIL {f}")
    return results


def _make_file_collector() -> tuple[Any, Any]:
    """One fresh ``(on_file, tally)`` pair per fan-out round.

    Two reasons, and the second is not hypothetical.

    Defining the callback inside the loop would close over the loop's own
    counters, so a round's totals would live in whatever the last iteration
    happened to leave. A fresh pair keeps each round's numbers its own.

    And the counter needs a lock. ``download_all`` splits the file list into n
    HostSpecs and ``fleet_downloader.download`` builds **one ``_FileGate`` per
    spec** (fleet_downloader.py:489) — each gate serializes only its own host,
    so n worker threads call this callback CONCURRENTLY. ``ok += 1`` is a
    read-modify-write: a lost update here understates the success count of
    exactly the fan-out stage C exists to measure, and it gets more likely as
    n grows, which biases the very comparison being made.
    """
    lock = threading.Lock()
    ok = 0
    failed: list[str] = []

    def on_file(name: str, fetched: Any, error: str | None) -> None:
        nonlocal ok
        with lock:
            if fetched is not None:
                ok += 1
            else:
                failed.append(f"{name}: {error}")

    def tally() -> tuple[int, list[str]]:
        with lock:
            return ok, list(failed)

    return on_file, tally


def _stage_d_minio(office: Any, cfg: ImageConfig, locator: ImageLocator, rounds: int) -> float | None:
    """Median seconds for one cache PUT of a real image, then clean up.

    Writes under a ``_measure/`` sibling of the configured cache prefix so a
    failed run cannot leave anything the nightly purge would count as a cached
    image, and deletes the key itself on the way out.
    """
    print("\n── D. MinIO cache PUT (inline in the FTP worker today) ───────")
    from back_dev_home.msr_image.minio_cache import MinioImageCache

    if not cfg.cache_bucket:
        print("   SKIP: SKEWNONO_IMAGE_CACHE_BUCKET is not set")
        return None
    fetched = office.fetch_image(locator, _config=cfg)
    prefix = cfg.cache_prefix.rstrip("/") + "_measure/"
    cache = MinioImageCache(bucket=cfg.cache_bucket, prefix=prefix)
    samples: list[float] = []
    try:
        for i in range(rounds):
            started = time.monotonic()
            cache.put(locator, fetched)
            samples.append(time.monotonic() - started)
            print(f"   round {i + 1}/{rounds}: {samples[-1] * 1000:7.1f} ms"
                  f"  ({len(fetched.data) / 1e6:.2f} MB)")
    finally:
        # purge(0) sweeps the whole measure prefix — every object under it was
        # written by this run, seconds ago.
        try:
            removed = cache.purge(ttl_hours=0)
            print(f"   cleaned up {removed} object(s) under {prefix}")
        except Exception as exc:  # noqa: BLE001 — cleanup must not mask a result
            print(f"   WARNING: could not clean {prefix}: {exc}")
    return statistics.median(samples)


# ── verdict ───────────────────────────────────────────────────────────────


def _verdict(
    office: Any, cfg: ImageConfig, login: float, serial: list[float],
    concurrency: dict[int, tuple[float, int]], minio: float | None,
    names: int, via_proxy: bool,
) -> None:
    print("\n══ verdict ═══════════════════════════════════════════════════")

    # Size the budget from the fan-out PRODUCTION actually uses, not from
    # whichever level happened to win: host_timeout is computed against
    # cfg.ftp_concurrency every real run.
    budget_n = cfg.ftp_concurrency if cfg.ftp_concurrency in concurrency else (
        max(concurrency) if concurrency else None
    )
    if budget_n is not None:
        elapsed, _ = concurrency[budget_n]
        per_conn = -(-names // budget_n)
        observed = elapsed / max(1, per_conn)
        recommended = round(observed * _HEADROOM, 1)
        print(f"_SECONDS_PER_IMAGE = {recommended}"
              f"   # was {office._SECONDS_PER_IMAGE}, observed {observed:.2f}s at"
              f" n={budget_n} x{_HEADROOM:g} headroom")
        if recommended > office._SECONDS_PER_IMAGE:
            print("   -> the current constant is TOO SMALL; big warm jobs risk abandonment")
        elif recommended < office._SECONDS_PER_IMAGE / 2:
            print("   -> the current constant is generous; safe, just slower to give up")
        else:
            print("   -> the current constant is in the right range")

        if via_proxy:
            cap = office._PROXY_HOST_TIMEOUT_CAP
            max_images = int(cap // recommended) if recommended else 0
            print(f"\n   proxy ceiling: a connection may carry at most ~{max_images} images"
                  f" under the {cap:g}s cap")
            if cap >= _PROXY_HARAKIRI:
                print(f"   WARNING: the cap ({cap:g}s) is at/above uWSGI harakiri"
                      f" ({_PROXY_HARAKIRI:g}s) — raise harakiri in wsgi.ini FIRST")

        ordered = sorted(concurrency)
        if len(ordered) > 1:
            baseline_n = ordered[0]
            baseline = concurrency[baseline_n][0]
            print(f"\nftp_concurrency: currently configured {cfg.ftp_concurrency}")
            for n in ordered:
                took = concurrency[n][0]
                gain = baseline / took if took else 0.0
                print(f"   n={n:2d}  {took:6.2f}s  {gain:4.1f}x vs n={baseline_n}")
            # A winner must beat the baseline by more than run-to-run noise.
            # Without this floor a 3-millisecond difference reads as a finding
            # and talks someone into a config change that measured nothing.
            best_n = min(ordered, key=lambda n: concurrency[n][0])
            best_gain = baseline / concurrency[best_n][0] if concurrency[best_n][0] else 0.0
            if best_gain < _MIN_MEANINGFUL_GAIN:
                print(f"   -> no meaningful difference (best {best_gain:.2f}x, need"
                      f" >{_MIN_MEANINGFUL_GAIN:g}x to call it). Fan-out is not"
                      f" paying off on this tool, but {names} images may be too few"
                      f" to show it — re-run with --images {max(24, names * 4)}"
                      f" before changing ftp_concurrency.")
            elif best_n < cfg.ftp_concurrency:
                print(f"   -> the tool stops rewarding fan-out at n={best_n};"
                      f" consider lowering ftp_concurrency to it")
            else:
                print("   -> the configured value is at or below the sweet spot")

    if serial:
        median = statistics.median(serial)
        share = login / median if median else 0.0
        print(f"\nconnection pooling: login is {login * 1000:.0f} ms of a"
              f" {median * 1000:.0f} ms cold fetch ({share:.0%})")
        if share >= 0.25:
            print("   -> WORTH BUILDING: a pooled session would cut roughly that much"
                  " off every cold image")
        else:
            print("   -> not worth it: the transfer dominates, pooling would barely show")

    if minio is not None and serial:
        median = statistics.median(serial)
        share = minio / median if median else 0.0
        print(f"\nupload pipelining: a cache PUT is {minio * 1000:.0f} ms against a"
              f" {median * 1000:.0f} ms fetch ({share:.0%} added to each connection)")
        if share >= 0.25:
            print("   -> WORTH BUILDING: the PUT blocks the next RETR on that connection")
        else:
            print("   -> low payoff: the PUT is cheap next to the fetch")

    print("\nRecord what you keep in back_dev_home/msr_image/MIGRATION.md and replace"
          "\nthe OFFICE-VERIFY mark with `office 확인 YYYY-MM-DD`.")


# ── main ──────────────────────────────────────────────────────────────────


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--eqp-ip", default="", help="tool IP (default: discovered from meas_hist)")
    p.add_argument("--class-name", default="", help="class_name of the MSR")
    p.add_argument("--msr", default="", help="MSR identifier")
    p.add_argument("--images", type=int, default=12,
                   help="how many images to time (default: 12)")
    p.add_argument("--login-rounds", type=int, default=5,
                   help="connect+login samples for stage A (default: 5)")
    p.add_argument("--fanout", default="1,3,6",
                   help="comma-separated concurrency levels for stage C (default: 1,3,6)")
    p.add_argument("--minio", action="store_true",
                   help="also time a cache PUT (writes under <prefix>_measure/, then deletes)")
    p.add_argument("--direct", action="store_true", help="force direct FTP even on Windows")
    p.add_argument("--skip-serial", action="store_true",
                   help="skip stage B (it costs one login per image)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    # Stages B and C take minutes, and this is run at the office where the
    # operator is watching for signs of life. Block buffering (which is what
    # Python picks the moment output is piped or tee'd to a file) would hold
    # every line until a stage finished, so a working run and a hung one look
    # identical. It also reorders output against stderr, which is unbuffered:
    # a traceback then appears ABOVE the lines that were printed before it.
    sys.stdout.reconfigure(line_buffering=True)

    if not os.environ.get("OPENSEARCH_HOST"):
        load_env_file("OPENSEARCH_HOST")

    if args.direct:
        # office_example picks its transport at import time from the platform;
        # flipping this before the import is the only way to force direct.
        import platform
        platform.system = lambda: "Linux"  # noqa: E731

    from back_dev_home.msr_image.providers import office_example as office

    via_proxy = office._VIA_PROXY
    print(f"transport: {'proxy (Windows)' if via_proxy else 'direct'}")

    if args.eqp_ip and args.class_name and args.msr:
        eqp_ip, class_name, msr = args.eqp_ip, args.class_name, args.msr
    else:
        print("discovering a target from meas_hist (needs OpenSearch)...")
        try:
            eqp_ip, class_name, msr = _discover()
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 - the message matters, not the type
            # Discovery is a convenience, not the measurement. Failing it with a
            # raw traceback reads as "the script is broken" when the usual cause
            # is simply that OpenSearch is not reachable from this box.
            raise SystemExit(
                f"could not discover a target: {type(exc).__name__}: {exc}\n"
                "Pass a locator explicitly to skip OpenSearch entirely:\n"
                "    --eqp-ip 10.1.2.3 --class-name ADI --msr <MSR>"
            ) from exc
    print(f"target: eqp_ip={eqp_ip!r} class_name={class_name!r} msr={msr!r}")
    print(f"ftp dir: {image_dir(class_name, msr)!r}")

    cfg = load_config()
    validate_tool_ip(eqp_ip, cfg.allowed_subnets)
    # Nothing may be abandoned mid-measurement: an abandoned host yields a
    # failure, not a duration, which would bias every average toward fast files.
    cfg = replace(cfg, ftp_host_timeout=_MEASURE_HOST_TIMEOUT, ftp_host_timeout_max=_MEASURE_HOST_TIMEOUT)

    listing_started = time.monotonic()
    all_names = office.list_images(eqp_ip, class_name, msr, _config=cfg)
    listing_elapsed = time.monotonic() - listing_started
    print(f"listing: {len(all_names)} images in {listing_elapsed:.2f}s")
    if not all_names:
        print("nothing to measure — the tool dir served no images")
        return 1
    names = all_names[: args.images]
    print(f"measuring {len(names)} of them")

    login = _stage_a_login(office, cfg, eqp_ip, args.login_rounds)

    serial: list[float] = []
    if not args.skip_serial:
        serial, total = _stage_b_serial(office, cfg, eqp_ip, class_name, msr, names, login)
        print(f"   median {statistics.median(serial):.2f}s   max {max(serial):.2f}s"
              f"   {total / 1e6:.1f} MB total")

    fanouts = sorted({int(v) for v in args.fanout.split(",") if v.strip()})
    concurrency = _stage_c_concurrency(office, cfg, eqp_ip, class_name, msr, names, fanouts)

    minio = None
    if args.minio:
        minio = _stage_d_minio(
            office, cfg, ImageLocator(eqp_ip, class_name, msr, names[0]), rounds=3
        )

    _verdict(office, cfg, login, serial, concurrency, minio, len(names), via_proxy)
    return 0


if __name__ == "__main__":
    sys.exit(main())
