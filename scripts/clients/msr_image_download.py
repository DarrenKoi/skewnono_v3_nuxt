#!/usr/bin/env python3
"""Download SKEWNONO metrology images to this PC.

Standard library only, on purpose -- this file is meant to be copied to a
user's machine, and a controlled in-house PC may have no `pip install`.

    export SKEWNONO_TOKEN=skn_...
    python msr_image_download.py --lot KPB266344 --ext jpg --out ./images

Mint the token in the web UI: settings page -> API tokens. The plaintext is
shown exactly once.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE = "http://skewnono.skhynix.com"
SEARCH_PATH = "/api/meas-hist/search"
LIST_PATH = "/api/msr-images"
IMAGE_PATH = "/api/msr-image"
TIMEOUT = 60


class ApiError(RuntimeError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"HTTP {status} [{code}] {message}")
        self.status = status
        self.code = code
        self.message = message


def build_url(base: str, path: str, params: dict | None = None) -> str:
    url = base.rstrip("/") + path
    if params:
        url += "?" + urlencode(params)
    return url


def api_call(base, path, token, *, params=None, method="GET", body=None, raw=False):
    """One HTTP call. Returns parsed JSON, or raw bytes when raw=True."""
    data = json.dumps(body).encode() if body is not None else None
    req = Request(build_url(base, path, params), data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            payload = resp.read()
    except HTTPError as exc:
        detail = exc.read()
        try:
            parsed = json.loads(detail)
        except ValueError:
            parsed = {}
        raise ApiError(
            exc.code, parsed.get("code", ""), parsed.get("error", exc.reason or "")
        ) from None
    except URLError as exc:
        raise ApiError(0, "unreachable", str(exc.reason)) from None
    return payload if raw else json.loads(payload)


def call_with_retry(fn, attempts: int = 5):
    """Retry only 429. Everything else is either fatal or the caller's to handle.

    Only the search call can 429 -- the msr_image blueprint is exempt from the
    per-user API budget -- but the helper is shared for simplicity.
    """
    delay = 1.0
    for attempt in range(attempts):
        try:
            return fn()
        except ApiError as exc:
            if exc.status != 429 or attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2


def safe_filename(name: str) -> str:
    """The server validates these names, but this function writes to the
    user's disk -- re-check rather than trust a remote value."""
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError(f"unsafe filename: {name!r}")
    return name


def search(base, token, *, lot=None, recipe=None, eq=None, msr=None,
           date_from=None, date_to=None, limit=50) -> list[dict]:
    params = {"limit": limit}
    # NOTE: `lot` matches lot_id (e.g. KPB266344), NOT the 3-char lot_cd.
    # Passing a lot_cd returns zero rows with no error.
    for key, value in (("lot", lot), ("recipe", recipe), ("eq", eq), ("msr", msr),
                       ("from", date_from), ("to", date_to)):
        if value:
            params[key] = value
    body = call_with_retry(lambda: api_call(base, SEARCH_PATH, token, params=params))
    return body["rows"]


def warm(base, token, row, names) -> None:
    """Ask the server to pull these files from the tool in parallel.

    Skipping this step is the single biggest performance mistake a client can
    make: office-side every uncached GET is a serial FTP round-trip to the
    tool, while the warm job fetches with SKEWNONO_TOOL_FTP_CONCURRENCY (6)
    connections. The job is scoped to `names` so an ext filter is honored and
    files already cached are not refetched.
    """
    payload = {
        "eqp_ip": row["eqp_ip"],
        "class_name": row["class_name"],
        "msr": row["msr"],
        "names": names,
    }
    try:
        job = api_call(base, LIST_PATH, token, method="POST", body=payload)
    except ApiError as exc:
        print(f"  warm skipped ({exc.code or exc.status}); fetching directly")
        return
    job_id = job["job_id"]
    for _ in range(600):
        try:
            status = api_call(base, f"{LIST_PATH}/{job_id}", token)
        except ApiError:
            return  # job expired or unknown; the GETs below still work
        if status["status"] != "running":
            if status["status"] == "error":
                # A whole-job failure still leaves the cache partly warm, and
                # per-file failures surface individually on the GETs below.
                print("  warm job reported error; continuing")
            return
        time.sleep(0.5)


def download_msr(base, token, row, out_dir, *, ext=None) -> int:
    """List, warm, then fetch one MSR's images. Returns files newly written."""
    params = {"eqp_ip": row["eqp_ip"], "class_name": row["class_name"], "msr": row["msr"]}
    if ext:
        params["ext"] = ext
    names = api_call(base, LIST_PATH, token, params=params)["images"]
    if not names:
        return 0

    target = out_dir / row["msr"]
    target.mkdir(parents=True, exist_ok=True)
    pending = [n for n in names if not (target / safe_filename(n)).exists()]
    if not pending:
        return 0

    warm(base, token, row, pending)

    written = 0
    for name in pending:
        dest = target / safe_filename(name)
        try:
            payload = api_call(
                base, IMAGE_PATH, token, params={**params, "name": name}, raw=True
            )
        except ApiError as exc:
            print(f"  {name}: {exc}")
            continue
        # Write to .part and rename, so an interrupted run never leaves a
        # truncated file that the exists() check above would later skip.
        part = dest.with_suffix(dest.suffix + ".part")
        part.write_bytes(payload)
        part.replace(dest)
        written += 1
    return written


def main(argv=None) -> int:
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("SKEWNONO_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--lot", help="lot_id, e.g. KPB266344 (NOT the 3-char lot_cd)")
    parser.add_argument("--recipe")
    parser.add_argument("--eq", help="equipment id, e.g. ECDX285")
    parser.add_argument("--msr")
    parser.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="YYYY-MM-DD")
    parser.add_argument("--ext", choices=("jpg", "tif"), help="omit for every file")
    parser.add_argument("--limit", type=int, default=50, help="max MSRs to process")
    parser.add_argument("--out", default="./msr_images")
    args = parser.parse_args(argv)

    token = os.environ.get("SKEWNONO_TOKEN")
    if not token:
        print("SKEWNONO_TOKEN is not set. Mint one in the web UI: settings -> API tokens.")
        return 2
    if not any((args.lot, args.recipe, args.eq, args.msr)):
        print("Give at least one of --lot / --recipe / --eq / --msr.")
        return 2

    out_dir = Path(args.out)
    try:
        rows = search(
            args.base_url, token, lot=args.lot, recipe=args.recipe, eq=args.eq,
            msr=args.msr, date_from=args.date_from, date_to=args.date_to,
            limit=args.limit,
        )
    except ApiError as exc:
        print(f"search failed: {exc}")
        return 1

    if not rows:
        print("No measurements matched. Note that --lot takes a lot_id "
              "(KPB266344), not a lot_cd (KPB).")
        return 1

    print(f"{len(rows)} measurement(s) matched.")
    total = 0
    for row in rows:
        print(f"- {row['msr']} ({row['eqp_id']})")
        try:
            total += download_msr(args.base_url, token, row, out_dir, ext=args.ext)
        except ApiError as exc:
            print(f"  failed: {exc}")
    print(f"Done. {total} new file(s) under {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
