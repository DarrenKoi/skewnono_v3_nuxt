"""Probe the tool FTP for a recipe's IDP file, starting from meas_hist.

Reconnaissance for "recipe 열어보기" (recipe-search → 자세히 보기). Today that
screen is served entirely by the mock: ``recipe_search/providers/office_example.py``
re-exports ``get_recipe_open_data`` from ``providers/mock.py`` with a
``TODO(office)`` because the raw IDP payload has no office source yet. The real
source is the tool's own FTP server, and this script establishes what it
actually serves before any adapter is written against it.

The chain, all from ONE meas_hist document:

    meas_hist_{cdsem,hvsem}          OpenSearch
      ├── eqp_ip      ────────────►  the FTP host
      ├── class_name  ──┐
      ├── idw_name    ──┼──────────► /HITACHI/DEVICE/HD/{class}/data/{idw}
      └── idp_name    ──┘                 ├── {idp}.idp        ← downloaded
                                          └── {idp}/           ← listed only

``eqp_ip`` living on the measurement document is what makes this a single query:
unlike lateral check (which resolves ``eqp_id -> eqp_ip`` through sem_list), the
measurement row already names the tool that ran the recipe, so the host it must
be readable from is the host we just proved ran it.

THE ASSUMPTION UNDER TEST — ``idp_name``/``idw_name`` are documented as *paths*
("/Recipe/ADI/ADI_CD_BIAS_001.idp", docs/datatables/meas_hist.txt) while the FTP
tree wants a bare folder name. Every derivation below is therefore a stem, and
the script prints the raw value beside the assembled path so a wrong guess reads
as a wrong string rather than an unexplained 550. When the primary path misses,
``_fallback_dirs`` re-probes plausible alternates and finally lists the parent
``data/`` directory, which reveals the real naming convention outright.

Scope: download the .idp, LIST the raw-recipe folder. Parsing the .idp and
mapping it onto RecipeDetailResponse is the next step, deliberately not here —
we look at real bytes before committing to a shape.

Run FROM THE REPO ROOT at the office (reads OPENSEARCH_* and SKEWNONO_TOOL_FTP_*
from back_dev_home/.env, like the adapters do). Bare, it probes the newest
document in the index; every filter is opt-in:

    .venv/bin/python -m scripts.probe_recipe_ftp
    .venv/bin/python -m scripts.probe_recipe_ftp --pick 2
    .venv/bin/python -m scripts.probe_recipe_ftp --tool hvsem --eqp MHV101 --date 2026-07-26
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from platform import system
from typing import Any
from zoneinfo import ZoneInfo

from back_dev_home._runtime.office_redis import load_env_file
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.paths import validate_tool_ip
from ops_store import OSSearch, create_client

# Same root msr_image already reads images from (office 확인 2026-07-24); the
# recipe tree is its sibling: images/{msr} vs data/{idw}.
_ROOT = "/HITACHI/DEVICE/HD"

_INDEX = {"cdsem": "meas_hist_cdsem", "hvsem": "meas_hist_hvsem"}

# Office indices store KST wall-clock with NO offset (docs/datatables/meas_hist.txt),
# so "today" must be resolved in Seoul time and sent as a naive string. Using the
# host's local date would silently select the wrong day on a UTC cloud box.
_KST = ZoneInfo("Asia/Seoul")

# Fields the FTP path (and the eventual adapter) is assembled from. Requesting
# them explicitly keeps the printout readable and the response small.
_SOURCE = [
    "class_name",
    "recipe_name",
    "full_name",
    "idp_name",
    "idw_name",
    "eqp_id",
    "eqp_ip",
    "fab_name",
    "timestamp",
]


# ── OpenSearch ────────────────────────────────────────────────────────────


def _query(fab: str, eqp: str, date: str | None, recipe: str | None) -> dict[str, Any]:
    must: list[dict[str, Any]] = []
    if fab:
        must.append({"term": {"fab_name.keyword": fab}})
    if eqp:
        must.append({"term": {"eqp_id.keyword": eqp}})
    if date:
        must.append({
            "range": {"timestamp": {"gte": f"{date}T00:00:00", "lte": f"{date}T23:59:59"}}
        })
    if recipe:
        must.append({
            "wildcard": {"recipe_name.keyword": {"value": f"*{recipe}*", "case_insensitive": True}}
        })
    return {"bool": {"must": must}} if must else {"match_all": {}}


def _search(client, index: str, query: dict[str, Any], size: int) -> list[dict[str, Any]]:
    body = {
        "size": size,
        "query": query,
        "sort": [{"timestamp": "desc"}],
        "_source": _SOURCE,
    }
    result = OSSearch(client=client, index=index).search_raw(body)
    return result.get("hits", {}).get("hits", [])


def _explain_no_hits(client, index: str, fab: str, eqp: str, date: str | None) -> None:
    """Say WHY the filter matched nothing, instead of just reporting zero.

    Three filters are ANDed; any one can be the culprit, and the fix differs
    per culprit (wrong fab spelling vs. a tool idle today vs. ingestion lag).
    One aggregation per suspect turns a silent empty result into a decision.
    """
    search = OSSearch(client=client, index=index)
    print("\n  -- why zero? --")

    aggs = {
        "max_ts": {"max": {"field": "timestamp"}},
        "fabs": {"terms": {"field": "fab_name.keyword", "size": 20}},
    }
    result = search.aggregate(aggs, query=None).get("aggregations", {})
    print(f"  newest timestamp in {index}: {result.get('max_ts', {}).get('value_as_string')!r}")
    fabs = result.get("fabs", {}).get("buckets", [])
    print("  fab_name values:", ", ".join(f"{b['key']}({b['doc_count']})" for b in fabs) or "(none)")

    # Which tools DID run in the requested fab+day — names the alternative eqp_id
    # to retry with when MCD719 simply sat idle.
    day_query = _query(fab, "", date, None)
    day_aggs = {"eqps": {"terms": {"field": "eqp_id.keyword", "size": 30}}}
    day = search.aggregate(day_aggs, query=day_query).get("aggregations", {})
    eqps = day.get("eqps", {}).get("buckets", [])
    print(f"  eqp_id seen for fab={fab!r} date={date}:",
          ", ".join(f"{b['key']}({b['doc_count']})" for b in eqps) or "(none)")

    # Same tool, no date bound: distinguishes "wrong eqp_id" from "idle today".
    ever = search.count(query=_query(fab, eqp, None, None)).get("count")
    print(f"  docs for fab={fab!r} eqp={eqp!r} across ALL dates: {ever}")


def _print_candidates(hits: list[dict[str, Any]]) -> None:
    """Dump every candidate verbatim — the raw idp_name/idw_name strings are
    the point of this stage, so they are never trimmed or normalized here."""
    print(f"\n=== Stage A: {len(hits)} candidate(s) ===")
    for i, hit in enumerate(hits):
        src = hit.get("_source", {})
        marker = "->" if i == 0 else "  "
        print(f"\n{marker} [{i}] _index={hit.get('_index')}  _id={hit.get('_id')}")
        for field in _SOURCE:
            print(f"      {field:<12} {src.get(field)!r}")


# ── path derivation ───────────────────────────────────────────────────────


def _stem(value: str) -> str:
    """'/Recipe/ADI/ADI_CD_BIAS_001.idp' -> 'ADI_CD_BIAS_001'.

    Tolerates the office storing a bare name already (stem of a name without a
    directory is that name), so this is safe whichever form turns up.
    """
    return PurePosixPath(str(value or "").strip()).stem


def _derive(src: dict[str, Any]) -> tuple[str, str, str]:
    """(data_dir, idp_file, raw_dir) plus a printed derivation chain."""
    class_name = str(src.get("class_name") or "").strip()
    raw_idw = str(src.get("idw_name") or "")
    raw_idp = str(src.get("idp_name") or "")
    idw_key, idp_key = _stem(raw_idw), _stem(raw_idp)

    data_dir = f"{_ROOT}/{class_name}/data/{idw_key}"
    idp_file = f"{data_dir}/{idp_key}.idp"
    raw_dir = f"{data_dir}/{idp_key}"

    print("\n=== Stage B: path derivation ===")
    print(f"  class_name  {class_name!r}")
    print(f"  idw_name    {raw_idw!r}  --stem-->  {idw_key!r}")
    print(f"  idp_name    {raw_idp!r}  --stem-->  {idp_key!r}")
    print(f"  data_dir    {data_dir}")
    print(f"  idp_file    {idp_file}")
    print(f"  raw_dir     {raw_dir}")
    if idw_key != idp_key:
        # meas_hist derives both from one recipe_name, so a divergence here is
        # itself a finding worth seeing before the FTP call explains it badly.
        print(f"  NOTE: idw stem != idp stem ({idw_key!r} vs {idp_key!r})")
    return data_dir, idp_file, raw_dir


def _fallback_dirs(src: dict[str, Any]) -> list[tuple[str, str]]:
    """(label, path) alternates tried when the derived data_dir lists nothing.

    Ordered cheapest-assumption-first; the final entry lists the parent, which
    answers "what IS the folder naming here" regardless of every guess above.
    """
    class_name = str(src.get("class_name") or "").strip()
    raw_idw = str(src.get("idw_name") or "")
    base = f"{_ROOT}/{class_name}/data"
    return [
        ("idw basename with extension", f"{base}/{PurePosixPath(raw_idw).name}"),
        ("idp stem", f"{base}/{_stem(src.get('idp_name'))}"),
        ("recipe_name", f"{base}/{str(src.get('recipe_name') or '').strip()}"),
        ("parent data/ listing", base),
    ]


# ── FTP ───────────────────────────────────────────────────────────────────


def _transport(direct: bool):
    """Windows office PC has no direct FTP egress to tools — it must go through
    the fileloader HTTP proxy. Cloud/Linux reaches tools directly. Same split
    msr_image makes, so a result here transfers to the adapter unchanged."""
    if system() == "Windows" and not direct:
        from ftp_handler.proxy import FtpFleetDownloader, HostSpec, ListDir
        return FtpFleetDownloader, HostSpec, ListDir, "proxy (Windows)"
    from ftp_handler.direct_downloader import FtpFleetDownloader, HostSpec, ListDir
    return FtpFleetDownloader, HostSpec, ListDir, "direct"


def _downloader(cls, cfg):
    return cls(
        user=cfg.ftp_user,
        password=cfg.ftp_password,
        port=cfg.ftp_port,
        connect_timeout=cfg.ftp_timeout,
    )


def _list(dl, HostSpec, ListDir, ip: str, remote_dir: str) -> list[str] | None:
    """List one directory. Returns paths, or None when the listing failed —
    the distinction matters: empty means "exists but bare", None means the
    path or the host is wrong, and only the second should trigger fallbacks."""
    report = dl.list_dirs([HostSpec(ip, listings=[ListDir(remote_dir)])])
    if report.failures:
        for f in report.failures:
            print(f"    FAIL {f.remote_path or remote_dir}: {f.error}")
        return None
    return [p for listing in report.listings for p in listing.paths]


def _print_listing(remote_dir: str, paths: list[str], limit: int) -> None:
    print(f"    {len(paths)} entry(ies) under {remote_dir}")
    for p in sorted(paths)[:limit]:
        print(f"      {PurePosixPath(p).name}")
    if len(paths) > limit:
        print(f"      ... {len(paths) - limit} more (raise --limit to see all)")


def _preview(data: bytes, lines: int = 25) -> str:
    """Best-effort text view; hexdump when the bytes are not text.

    The .idp format is unknown — it may be an INI-ish text file, a Windows
    codepage text file (Hitachi tools are Japanese/Korean Windows), or a binary
    blob. Trying utf-8 then cp949 then cp932 before giving up means one run
    tells us which, instead of printing mojibake and looking like a failure.
    """
    for encoding in ("utf-8", "cp949", "cp932", "latin-1"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        printable = sum(c.isprintable() or c in "\r\n\t" for c in text[:2000])
        if printable / max(1, len(text[:2000])) > 0.85:
            head = "\n".join(f"      | {line}" for line in text.splitlines()[:lines])
            return f"    decoded as {encoding}, {len(text.splitlines())} lines\n{head}"
    dump = data[:256]
    rows = [
        f"      {i:04x}  {dump[i:i+16].hex(' '):<47}  "
        f"{''.join(chr(b) if 32 <= b < 127 else '.' for b in dump[i:i+16])}"
        for i in range(0, len(dump), 16)
    ]
    return "    binary (not text in utf-8/cp949/cp932); first 256 bytes:\n" + "\n".join(rows)


# ── main ──────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    today = datetime.now(_KST).date().isoformat()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tool", choices=sorted(_INDEX), default="cdsem")
    # All four filters default to off. They are ANDed, so any default here is a
    # way for the run to find nothing: a fab typo or a tool idle since midnight
    # returns zero hits and spends the run explaining the zero rather than
    # fetching a file. Narrow deliberately, never by accident.
    p.add_argument("--fab", default="", help="optional fab_name.keyword term (e.g. R3)")
    p.add_argument("--eqp", default="", help="optional eqp_id.keyword term (e.g. MCD719)")
    p.add_argument("--date", default="", help=f"optional KST day for the timestamp range (e.g. {today})")
    p.add_argument("--recipe", default=None, help="optional recipe_name substring filter")
    p.add_argument("--candidates", type=int, default=5, help="documents to fetch and print (default: 5)")
    p.add_argument("--pick", type=int, default=0, help="which candidate to probe (default: 0)")
    p.add_argument("--limit", type=int, default=40, help="max listing entries to print (default: 40)")
    p.add_argument("--direct", action="store_true", help="force direct FTP even on Windows")
    p.add_argument("--out", default=".ftp-probe", help="download destination (default: .ftp-probe)")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if not os.environ.get("OPENSEARCH_HOST"):
        load_env_file("OPENSEARCH_HOST")

    index = _INDEX[args.tool]
    # Unfiltered by default: the sort is already timestamp desc, so candidate 0
    # is whatever ran most recently anywhere in the index — the highest-odds row
    # when the goal is to hold a real .idp rather than one specific recipe.
    date = args.date or None
    print(f"index={index} fab={args.fab!r} eqp={args.eqp!r} date={date}")

    client = create_client()
    hits = _search(client, index, _query(args.fab, args.eqp, date, args.recipe), args.candidates)
    if not hits:
        print(f"\nNo documents matched in {index}.")
        _explain_no_hits(client, index, args.fab, args.eqp, date)
        return 1

    _print_candidates(hits)
    if not 0 <= args.pick < len(hits):
        print(f"\n--pick {args.pick} out of range (0..{len(hits) - 1})")
        return 1
    src = hits[args.pick].get("_source", {})

    data_dir, idp_file, raw_dir = _derive(src)

    ip = str(src.get("eqp_ip") or "").strip()
    if not ip:
        print("\neqp_ip missing on the document — cannot open an FTP session.")
        return 1
    try:
        # The IP comes from OpenSearch rather than a client here, but the adapter
        # will apply this same guard, so a value that fails it is a finding now.
        validate_tool_ip(ip)
    except Exception as exc:
        print(f"\neqp_ip {ip!r} rejected by the tool-IP guard: {exc}")
        return 1

    cfg = load_config()
    FtpFleetDownloader, HostSpec, ListDir, mode = _transport(args.direct)
    dl = _downloader(FtpFleetDownloader, cfg)
    print(f"\n=== Stage C: FTP {ip} (transport: {mode}, user={cfg.ftp_user}) ===")

    print(f"\n  [1] list data_dir  {data_dir}")
    paths = _list(dl, HostSpec, ListDir, ip, data_dir)
    if paths:
        _print_listing(data_dir, paths, args.limit)
    else:
        print("    nothing here — trying fallbacks")
        for label, alt in _fallback_dirs(src):
            if alt == data_dir:
                continue
            print(f"    [fallback: {label}] {alt}")
            alt_paths = _list(dl, HostSpec, ListDir, ip, alt)
            if alt_paths:
                _print_listing(alt, alt_paths, args.limit)
                print(f"    ^ THIS ONE WORKED — data_dir should be derived as: {label}")
                break
        print("\n  Stopping before download: the derived data_dir was wrong.")
        return 1

    print(f"\n  [2] download idp   {idp_file}")
    report = dl.download([HostSpec(ip, files=[idp_file])])
    fetched = {f.remote_path: f.data for f in report.files}
    if idp_file not in fetched:
        for f in report.failures:
            print(f"    FAIL {f.remote_path or idp_file}: {f.error}")
        print("    .idp not retrieved — compare the name against the listing above.")
        return 1

    data = fetched[idp_file]
    dest = Path(args.out) / str(src.get("eqp_id") or ip) / PurePosixPath(idp_file).relative_to("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"    OK {len(data):,} bytes -> {dest}")
    print(_preview(data))

    print(f"\n  [3] list raw_dir   {raw_dir}   (listing only, no download)")
    raw_paths = _list(dl, HostSpec, ListDir, ip, raw_dir)
    if raw_paths is None:
        print("    listing failed — the raw-recipe folder may be named differently.")
    else:
        _print_listing(raw_dir, raw_paths, args.limit)

    print(f"\nDone. .idp saved under {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
