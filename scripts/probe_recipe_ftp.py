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
      └── idp_name    ──┘                 ├── {idp}.idp        ← downloaded, then parsed
                                          └── {idp}/           ← listed only

The downloaded file is then handed to the office parser, which is the only
thing that can say what a .idp actually contains::

    office_utils.read_idp_info.combined_idp_info(path) -> {
        "wafer_mp_info":    DataFrame,   # one row per measurement point
        "wafer_align_info": DataFrame,   # one row per wafer-align point
        "idp_image_info":   DataFrame,   # one row per parameter/image definition
    }

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

Stage D then takes ONE parameter — ``PARAMETER`` below, hard-coded so it can be
edited in place — and follows its five image slots into that raw folder::

    idp_image_info row where Parameter == PARAMETER
      ├── img_add1   'IMMP0001' ──► IMMP0001.jpeg  +  .IMMP0001.jpeg/cond.txt
      ├── image_add3 'I2MP0000' ──► I2MP0000.jpeg  +  .I2MP0000.jpeg/cond.txt
      ├── img_meas1  'IMMS0000' ──► IMMS0000.jpeg  +  .IMMS0000.jpeg/cond.txt
      ├── img_add2   'PRMP0000' ──► ENMP0000       (PR->EN, AF/PR condition)
      └── img_meas2  'PRMS0000' ──► PRMS0000       (as-is, AMP setting)

Each downloaded setting file is handed to the second office parser, the one the
adapter uses::

    office_utils.idp_amp_reader.read_amp_info(bytes)               <- img_meas2
    office_utils.idp_amp_reader.read_af_pr_condition(bytes)        <- img_add2
    office_utils.idp_amp_reader.read_meas_image_condition(bytes)   <- cond.txt

The names are derived by ``recipe_search/rawfiles.py`` rather than spelled out
here on purpose: that module is what the office adapter runs, so a name this
script gets wrong is a bug found rather than a probe-only typo. Two things
``docs/datatables/recipe_idp.txt`` still lists as unverified are what this stage
is for — whether the ``img_*`` values are filenames at all, and whether the
untranslated ``PR…`` file holds anything of its own (it is fetched beside the
``EN…`` one to find out).

Stage E does the same for the wafer-align set, which uses a DIFFERENT pair of
readers despite the files looking alike::

    wafer_align_info["P.No"], deduplicated
      ├── IMAP{p:04d}.jpeg              the align image itself
      ├── .IMAP{p:04d}.jpeg/cond.txt ─► read_align_image_condition(bytes, which)
      └── ENAP{p:04d} ────────────────► get_align_beam_pr_conditions([bytes, ...])

``which`` is "OM" or "SEM" and comes from the point NUMBER, not the file:
P.No 1 is the optical microscope and P.No 2 the SEM (user-confirmed
2026-07-29). Most recipes have both. A point outside that pair is left unparsed
rather than guessed, since either guess renders one instrument's settings under
the other's heading and reads as ordinary data.

The ENAP reader takes the whole point list in ONE call, so Stage E calls it once
per recipe and prints the return's length beside the number of files — whether
its result can be split per point is the open question about it.

Scope: download the .idp, parse it, LIST the raw-recipe folder, then fetch and
read one parameter's files and the align set's. Mapping any of it onto
RecipeDetailResponse stays out — that is the adapter's job
(recipe_search/providers/office_example.py), and it wants real frames to be
written against rather than assumed ones.

Run FROM THE REPO ROOT at the office (reads OPENSEARCH_* and SKEWNONO_TOOL_FTP_*
from back_dev_home/.env, like the adapters do). Bare, it probes the newest
document in the index; every filter is opt-in:

    .venv/bin/python -m scripts.probe_recipe_ftp
    .venv/bin/python -m scripts.probe_recipe_ftp --pick 2
    .venv/bin/python -m scripts.probe_recipe_ftp --tool hvsem --eqp MHV101 --date 2026-07-26

Nothing the run saw is thrown away: ``main()`` returns a ``Probe`` and
``__main__`` binds its fields at module scope, so breakpointing the closing
``sys.exit`` (or running the file with PyCharm's "Run with Python Console")
hands the IDE ``hits``, ``doc``, ``idp_bytes``, ``idp_text``, the listings and
the three parsed frames — ``wafer_mp_info``, ``wafer_align_info`` and
``idp_image_info`` are bound separately so "View as DataFrame" reaches them in
one click. Stage D adds ``raw_files`` (name -> bytes) and ``raw_parsed``
(name -> whatever the reader returned), so a setting file can be re-read by hand
without another FTP round-trip.

To drive it by hand instead, pass the flags as a list — ``main()`` takes argv
explicitly so a console session never has to own ``sys.argv``:

    from scripts.probe_recipe_ftp import main
    probe = main([])                            # no filters, newest document
    probe = main(["--eqp", "MCD719", "--pick", "1"])
    mp = probe.wafer_mp_info                    # .wafer_align_info, .idp_image_info

Running the whole file inside PyCharm's console works too: it detects the
console, ignores pydevconsole's own argv, and skips the closing sys.exit so the
names are simply left at the prompt.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from platform import system
from typing import Any
from zoneinfo import ZoneInfo

from back_dev_home._runtime.office_redis import load_env_file
from back_dev_home.ebeam.hitachi.recipe_search import rawfiles
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.paths import validate_tool_ip
from ops_store import OSSearch, create_client

# ── EDIT ME ───────────────────────────────────────────────────────────────
# The parameter Stage D follows into the raw-recipe folder. Hard-coded rather
# than defaulted-to-first-row because a run is usually about one parameter you
# already have a question about; when it matches nothing, Stage D prints the
# parameters the recipe DOES have so the next edit is one line away.
# (--param overrides it for a one-off run without touching the file.)
PARAMETER = "WAFER"
# ──────────────────────────────────────────────────────────────────────────

# Same root msr_image already reads images from (office 확인 2026-07-24); the
# recipe tree is its sibling: images/{msr} vs data/{idw}.
_ROOT = "/HITACHI/DEVICE/HD"

# idp_image_info's five slot columns, in the order docs/datatables/recipe_idp.txt
# lists them. Spelled out because the names do NOT follow one rule — image_add3
# breaks the img_* run — and because the printout is meant to read like the doc.
_SLOT_COLUMNS = ("img_add1", "img_add2", "img_meas1", "img_meas2", "image_add3")

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


def _decode(data: bytes) -> tuple[str, str]:
    """(encoding, text) for the first codec that reads as text; ("", "") if none.

    The .idp format is unknown — it may be an INI-ish text file, a Windows
    codepage text file (Hitachi tools are Japanese/Korean Windows), or a binary
    blob. Trying utf-8 then cp949 then cp932 before giving up means one run
    tells us which, instead of printing mojibake and looking like a failure.

    Kept separate from _preview because the two answer different questions:
    printing 25 lines is for reading the file now, the returned string is for
    parsing it next, and only the second is worth keeping past the run.
    """
    for encoding in ("utf-8", "cp949", "cp932", "latin-1"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        printable = sum(c.isprintable() or c in "\r\n\t" for c in text[:2000])
        if printable / max(1, len(text[:2000])) > 0.85:
            return encoding, text
    return "", ""


def _preview(data: bytes, lines: int = 25) -> str:
    """Best-effort text view; hexdump when the bytes are not text."""
    encoding, text = _decode(data)
    if encoding:
        head = "\n".join(f"      | {line}" for line in text.splitlines()[:lines])
        return f"    decoded as {encoding}, {len(text.splitlines())} lines\n{head}"
    dump = data[:256]
    rows = [
        f"      {i:04x}  {dump[i:i+16].hex(' '):<47}  "
        f"{''.join(chr(b) if 32 <= b < 127 else '.' for b in dump[i:i+16])}"
        for i in range(0, len(dump), 16)
    ]
    return "    binary (not text in utf-8/cp949/cp932); first 256 bytes:\n" + "\n".join(rows)


# ── parse ─────────────────────────────────────────────────────────────────

# What combined_idp_info() is documented to return (docs/datatables/recipe_idp.txt).
# Named here only to notice a difference, never to enforce one — if the office
# parser hands back something else, that IS the finding and the script says so.
_IDP_TABLES = ("wafer_mp_info", "wafer_align_info", "idp_image_info")


def _parse_idp(path: Path) -> tuple[dict[str, Any], str]:
    """(tables, error) from the office parser; ({}, message) when it cannot run.

    Imported inside the function on purpose: ``office_utils`` is gitignored and
    exists only on the office PC (at home the repo-root copy is a fabricating
    stand-in), so a module-scope import would make this whole script
    unimportable anywhere else, cloud box included. Same rule the adapter in
    recipe_search/providers/office_example.py follows.

    Takes a path rather than the bytes we already hold because that is the
    parser's signature — which forces the download to land on disk first, the
    same ordering the adapter will have.

    The error is returned instead of raised so a parser that blows up on a real
    .idp still leaves the bytes, the path and the traceback on the Probe. A
    traceback you can read beside the file that caused it is the whole point.
    """
    try:
        from office_utils.read_idp_info import combined_idp_info
    except ImportError as exc:
        return {}, f"office_utils not importable ({exc}) — office PC only."
    try:
        return combined_idp_info(path), ""
    except Exception:
        return {}, traceback.format_exc()


def _print_tables(tables: dict[str, Any], rows: int = 3) -> None:
    """Shape, every column with its dtype, and the first few rows per table.

    The dtype list is printed in full rather than summarised because column
    names are the office contract: a drifted name passes at home against the
    stand-in and only fails here, so this listing is the thing being checked.
    """
    for name, frame in tables.items():
        print(f"\n    {name}  —  {len(frame)} rows x {len(frame.columns)} cols")
        for column, dtype in frame.dtypes.items():
            print(f"      {str(column):<20} {dtype}")
        head = frame.head(rows).to_string(max_colwidth=20)
        print("\n".join(f"      | {line}" for line in head.splitlines()))


# ── raw-recipe folder: one parameter's files ──────────────────────────────


@dataclass(frozen=True)
class _Want:
    """One file a parameter's slots point at.

    ``slot`` is the idp_image_info column it came from and ``kind`` decides the
    reader, so the two are kept apart: three different columns produce a
    ``cond`` file and one column (img_add2) produces two files of different
    kinds. Collapsing them into "the slot's file" would lose exactly that.
    """

    slot: str   # source column, e.g. "img_add1"
    kind: str   # image | cond | amp | af_pr | pr-key
    name: str   # name relative to the raw-recipe folder


def _param_rows(frame: Any, parameter: str) -> list[dict[str, Any]]:
    """idp_image_info rows for one parameter, matched loosely on purpose.

    Case and surrounding whitespace are ignored because whether Parameter is
    written identically everywhere is still an OFFICE-VERIFY item — a run that
    silently found nothing over a trailing space would waste the trip and teach
    the wrong lesson. A match that only survives normalisation is reported.
    """
    if frame is None or "Parameter" not in getattr(frame, "columns", []):
        return []
    key = parameter.strip().casefold()
    rows = [
        row for row in frame.to_dict("records")
        if str(row.get("Parameter", "")).strip().casefold() == key
    ]
    exact = [row for row in rows if str(row.get("Parameter", "")) == parameter]
    if rows and not exact:
        print(f"    NOTE: matched only after normalising case/whitespace: "
              f"{sorted({str(r.get('Parameter')) for r in rows})}")
    return rows


def _wants(row: dict[str, Any]) -> list[_Want]:
    """One idp_image_info row -> every file it names, with its derivation printed.

    The derivation itself comes from ``rawfiles`` — the module the office
    adapter runs — so this stage tests the real naming rules rather than a
    second copy of them.
    """
    slots = {column: str(row.get(column) or "") for column in _SLOT_COLUMNS}
    amp, af_pr, images = rawfiles.slot_sources(slots)

    wants: list[_Want] = []
    for slot, image, cond in images:
        wants.append(_Want(slot, "image", image))
        wants.append(_Want(slot, "cond", cond))
    if amp:
        wants.append(_Want("img_meas2", "amp", amp))
    if af_pr:
        wants.append(_Want("img_add2", "af_pr", af_pr))

    # OFFICE-VERIFY (docs/datatables/recipe_idp.txt): the adapter only ever
    # reads the EN… translation of img_add2. Whether the PR… file it was
    # translated from carries anything of its own has never been looked at, and
    # this run is standing in the folder anyway.
    pr_key = rawfiles.setting_name(slots.get("img_add2"))
    if pr_key and pr_key != af_pr:
        wants.append(_Want("img_add2", "pr-key", pr_key))

    print("    slot values and the files they name:")
    for column in _SLOT_COLUMNS:
        value = slots[column] or "(missing column)"
        named = [w.name for w in wants if w.slot == column]
        arrow = ", ".join(named) if named else "— no file (empty slot 'non')"
        print(f"      {column:<11} {value!r:<14} -> {arrow}")
    return wants


def _fetch_raw(dl, HostSpec, ip: str, raw: str, names: list[str]) -> dict[str, bytes]:
    """Download every wanted name in ONE session, keyed by name not path.

    A missing file is normal here, not a failure: a parameter routinely has no
    third addressing image and no AF/PR setting. Failures are printed and left
    out of the result, which is the same distinction the adapter draws — only a
    connect/login/listing failure (``remote_path is None``) means the tool is
    down rather than the file being absent.
    """
    by_path = {rawfiles.remote_path(raw, name): name for name in dict.fromkeys(names)}
    report = dl.download([HostSpec(ip, files=sorted(by_path))])
    got = {
        by_path[f.remote_path]: f.data
        for f in report.files
        if f.remote_path in by_path
    }
    for failure in report.failures:
        where = failure.remote_path or "(session — connect/login/listing)"
        print(f"      absent/failed {where}: {failure.error}")
    return got


def _save_raw(probe: Probe, out: str, name: str, data: bytes) -> Path:
    """Keep the bytes on the probe and mirror the tool's own path under ``out``.

    Mirroring rather than flattening because two align points' sidecars are both
    called ``cond.txt`` and differ only by the hidden directory above them —
    flattened, the second would overwrite the first.
    """
    probe.raw_files[name] = data
    dest = (
        Path(out) / str(probe.doc.get("eqp_id") or probe.ip)
        / PurePosixPath(rawfiles.remote_path(probe.raw_dir, name)).relative_to("/")
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def _describe(data: bytes) -> str:
    """One line: how big, and what the bytes actually are."""
    if data[:2] == b"\xff\xd8":
        kind = "JPEG"
    elif data[:2] in (b"II", b"MM"):
        kind = "TIFF"
    elif _decode(data)[0]:
        kind = f"text/{_decode(data)[0]}"
    else:
        kind = "binary"
    return f"{len(data):,} bytes, {kind}"


def _print_parsed(name: str, reader: Any, parsed: Any, lines: int = 12) -> None:
    """What the reader returned, printed by its ACTUAL type.

    The return types of the three ``idp_amp_reader`` functions are an open
    OFFICE-VERIFY item — the adapter's ``_to_rows`` accepts dict, DataFrame,
    or pair-list precisely because nobody has seen one yet. So the type is
    printed first and the value second: the type IS the finding.
    """
    label = getattr(reader, "__name__", str(reader))
    print(f"      {label}({name}) -> {type(parsed).__name__}")
    if hasattr(parsed, "columns"):  # DataFrame
        print(f"        {len(parsed)} rows x {len(parsed.columns)} cols: "
              f"{[str(c) for c in parsed.columns]}")
        head = parsed.head(3).to_string(max_colwidth=24)
        print("\n".join(f"        | {line}" for line in head.splitlines()))
        return
    items = (
        list(parsed.items()) if isinstance(parsed, dict)
        else list(enumerate(parsed)) if isinstance(parsed, (list, tuple))
        else [("value", parsed)]
    )
    for key, value in items[:lines]:
        print(f"        {str(key):<24} {value!r}")
    if len(items) > lines:
        print(f"        ... {len(items) - lines} more")


def _readers() -> tuple[dict[str, Any], str]:
    """(kind -> reader, error). Imported late for the same reason as the parser:
    ``office_utils`` is office-only, and a module-scope import would make this
    script unimportable everywhere else."""
    try:
        from office_utils.idp_amp_reader import (
            get_align_beam_pr_conditions,
            read_af_pr_condition,
            read_align_image_condition,
            read_amp_info,
            read_meas_image_condition,
        )
    except ImportError as exc:
        return {}, f"office_utils.idp_amp_reader not importable ({exc}) — office PC only."
    return {
        "amp": read_amp_info,
        "af_pr": read_af_pr_condition,
        "cond": read_meas_image_condition,
        # Align files take their OWN two readers, not the three above. Keyed
        # separately so Stage E cannot reach for a parameter-side reader by
        # accident — which is the mistake the adapter itself made until
        # 2026-07-29, invisibly, because the wrong reader still returns a value.
        "align_cond": read_align_image_condition,   # (source, which)
        "align_batch": get_align_beam_pr_conditions,  # ([source, ...])
    }, ""


# ── result ────────────────────────────────────────────────────────────────


@dataclass
class Probe:
    """Everything one run touched, kept alive past main() so an IDE can open it.

    A recon script's real output is not its stdout — it is the values behind it,
    and each of those used to be a local that died on return. The fields below
    are the run in the order it happened; ``__main__`` binds them at module
    scope, so a breakpoint on the final ``sys.exit`` puts the whole chain in
    PyCharm's variable pane.

    Partially filled is the normal case, not an error: every early exit returns
    the probe as far as it got, so a run that dies deriving a path still hands
    back the candidates it derived it from.
    """

    index: str
    query: dict[str, Any] = field(default_factory=dict)
    hits: list[dict[str, Any]] = field(default_factory=list)  # Stage A, raw OpenSearch hits
    doc: dict[str, Any] = field(default_factory=dict)         # _source of the picked candidate
    ip: str = ""                                              # doc's eqp_ip, the FTP host
    data_dir: str = ""                                        # Stage B derivations
    idp_file: str = ""
    raw_dir: str = ""
    listing: list[str] = field(default_factory=list)          # entries under data_dir
    fallback: str = ""                                        # _fallback_dirs label, if one saved the run
    idp_bytes: bytes = b""                                    # Stage C, what RETR returned
    encoding: str = ""                                        # "" when the payload is not text
    idp_text: str = ""                                        # decoded idp_bytes; "" when binary
    dest: Path | None = None                                  # where the .idp was written
    tables: dict[str, Any] = field(default_factory=dict)      # combined_idp_info's three DataFrames
    parse_error: str = ""                                     # traceback, if the parser raised
    raw_listing: list[str] | None = None                      # None = listing failed, [] = empty dir
    parameter: str = ""                                       # Stage D, the parameter followed
    param_rows: list[dict[str, Any]] = field(default_factory=list)   # its idp_image_info rows
    raw_files: dict[str, bytes] = field(default_factory=dict)        # name -> downloaded bytes
    raw_parsed: dict[str, Any] = field(default_factory=dict)         # name -> reader return value
    raw_errors: dict[str, str] = field(default_factory=dict)         # name -> traceback, if it raised
    align_points: list[int] = field(default_factory=list)            # Stage E, unique P.No
    align_settings: Any = None                                       # the ONE batch-reader return
    code: int = 1                                             # 0 only when the whole chain ran

    # The three frames by name. Worth the six lines because this is what a
    # console session reaches for constantly: probe.wafer_mp_info autocompletes
    # and reads as the parser's own key, where probe.tables["wafer_mp_info"] is
    # a string literal you have to spell right. All None before the parse stage.

    @property
    def wafer_mp_info(self) -> Any:
        """Measurement-point table, or None if the run stopped before parsing."""
        return self.tables.get("wafer_mp_info")

    @property
    def wafer_align_info(self) -> Any:
        """Wafer-align point table, or None if the run stopped before parsing."""
        return self.tables.get("wafer_align_info")

    @property
    def idp_image_info(self) -> Any:
        """Parameter/image definition table, or None if the run stopped before parsing."""
        return self.tables.get("idp_image_info")


# ── main ──────────────────────────────────────────────────────────────────


def _in_pydev_console() -> bool:
    """Are we running inside PyCharm's Python console rather than a shell?

    It matters because sys.argv there belongs to pydevconsole, not to us
    (``--mode=client --host=... --port=...``), so argparse rejects it and exits
    2 before the probe starts — reported as ``pydevconsole.py: error:
    unrecognized arguments``. Sniffing argv[0] is crude, but the alternative,
    parse_known_args(), would also swallow a mistyped flag at a real shell and
    silently run unfiltered, which is a worse failure than this one.
    """
    return Path(sys.argv[0]).name in ("pydevconsole.py", "pydev_run_in_console.py")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse argv; None means read sys.argv, [] means "no flags, all defaults"."""
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
    p.add_argument("--param", default=PARAMETER,
                   help=f"parameter whose raw files Stage D fetches (default: {PARAMETER!r}, "
                        "edit the PARAMETER constant to change it permanently)")
    p.add_argument("--candidates", type=int, default=5, help="documents to fetch and print (default: 5)")
    p.add_argument("--pick", type=int, default=0, help="which candidate to probe (default: 0)")
    p.add_argument("--limit", type=int, default=40, help="max listing entries to print (default: 40)")
    p.add_argument("--direct", action="store_true", help="force direct FTP even on Windows")
    p.add_argument("--out", default=".ftp-probe", help="download destination (default: .ftp-probe)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> Probe:
    """Run the whole chain and return what it saw. ``main([])`` = no filters.

    argv is explicit so the console can drive this without sys.argv: from a
    shell, None lets argparse read the command line as usual.
    """
    args = _parse_args(argv)
    if not os.environ.get("OPENSEARCH_HOST"):
        load_env_file("OPENSEARCH_HOST")

    index = _INDEX[args.tool]
    # Unfiltered by default: the sort is already timestamp desc, so candidate 0
    # is whatever ran most recently anywhere in the index — the highest-odds row
    # when the goal is to hold a real .idp rather than one specific recipe.
    date = args.date or None
    print(f"index={index} fab={args.fab!r} eqp={args.eqp!r} date={date}")

    # Built before the first call and returned from every exit below, so the
    # values are inspectable at whichever stage the run actually stopped at.
    probe = Probe(index=index, query=_query(args.fab, args.eqp, date, args.recipe))

    client = create_client()
    probe.hits = _search(client, index, probe.query, args.candidates)
    if not probe.hits:
        print(f"\nNo documents matched in {index}.")
        _explain_no_hits(client, index, args.fab, args.eqp, date)
        return probe

    _print_candidates(probe.hits)
    if not 0 <= args.pick < len(probe.hits):
        print(f"\n--pick {args.pick} out of range (0..{len(probe.hits) - 1})")
        return probe
    probe.doc = src = probe.hits[args.pick].get("_source", {})

    probe.data_dir, probe.idp_file, probe.raw_dir = _derive(src)

    probe.ip = str(src.get("eqp_ip") or "").strip()
    if not probe.ip:
        print("\neqp_ip missing on the document — cannot open an FTP session.")
        return probe
    try:
        # The IP comes from OpenSearch rather than a client here, but the adapter
        # will apply this same guard, so a value that fails it is a finding now.
        validate_tool_ip(probe.ip)
    except Exception as exc:
        print(f"\neqp_ip {probe.ip!r} rejected by the tool-IP guard: {exc}")
        return probe

    cfg = load_config()
    FtpFleetDownloader, HostSpec, ListDir, mode = _transport(args.direct)
    dl = _downloader(FtpFleetDownloader, cfg)
    print(f"\n=== Stage C: FTP {probe.ip} (transport: {mode}, user={cfg.ftp_user}) ===")

    print(f"\n  [1] list data_dir  {probe.data_dir}")
    paths = _list(dl, HostSpec, ListDir, probe.ip, probe.data_dir)
    if paths:
        probe.listing = paths
        _print_listing(probe.data_dir, paths, args.limit)
    else:
        print("    nothing here — trying fallbacks")
        for label, alt in _fallback_dirs(src):
            if alt == probe.data_dir:
                continue
            print(f"    [fallback: {label}] {alt}")
            alt_paths = _list(dl, HostSpec, ListDir, probe.ip, alt)
            if alt_paths:
                probe.fallback, probe.listing = label, alt_paths
                _print_listing(alt, alt_paths, args.limit)
                print(f"    ^ THIS ONE WORKED — data_dir should be derived as: {label}")
                break
        print("\n  Stopping before download: the derived data_dir was wrong.")
        return probe

    print(f"\n  [2] download idp   {probe.idp_file}")
    report = dl.download([HostSpec(probe.ip, files=[probe.idp_file])])
    fetched = {f.remote_path: f.data for f in report.files}
    if probe.idp_file not in fetched:
        for f in report.failures:
            print(f"    FAIL {f.remote_path or probe.idp_file}: {f.error}")
        print("    .idp not retrieved — compare the name against the listing above.")
        return probe

    probe.idp_bytes = fetched[probe.idp_file]
    probe.encoding, probe.idp_text = _decode(probe.idp_bytes)
    probe.dest = (
        Path(args.out) / str(src.get("eqp_id") or probe.ip)
        / PurePosixPath(probe.idp_file).relative_to("/")
    )
    probe.dest.parent.mkdir(parents=True, exist_ok=True)
    probe.dest.write_bytes(probe.idp_bytes)
    print(f"    OK {len(probe.idp_bytes):,} bytes -> {probe.dest}")
    print(_preview(probe.idp_bytes))

    print(f"\n  [3] parse idp      combined_idp_info({probe.dest})")
    probe.tables, probe.parse_error = _parse_idp(probe.dest)
    if probe.parse_error:
        print("\n".join(f"    {line}" for line in probe.parse_error.splitlines()))
    else:
        unexpected = set(probe.tables) ^ set(_IDP_TABLES)
        if unexpected:
            print(f"    NOTE: keys differ from the documented three: {sorted(unexpected)}")
        _print_tables(probe.tables)

    print(f"\n  [4] list raw_dir   {probe.raw_dir}   (listing only, no download)")
    probe.raw_listing = _list(dl, HostSpec, ListDir, probe.ip, probe.raw_dir)
    if probe.raw_listing is None:
        print("    listing failed — the raw-recipe folder may be named differently.")
    else:
        _print_listing(probe.raw_dir, probe.raw_listing, args.limit)

    # Guarded because Stage D runs LAST: three stages of findings and a
    # downloaded .idp already exist, and a surprise in the newest stage must not
    # take them down with it. The traceback is printed where it happened.
    for stage, run in (("D", _stage_d), ("E", _stage_e)):
        try:
            run(probe, dl, HostSpec, args)
        except Exception:
            print(f"\n  Stage {stage} failed — earlier stages stand.")
            traceback.print_exc()

    print(f"\nDone. Files saved under {args.out}/")
    # A failed parse still leaves a downloaded file and three stages of findings,
    # so the run is reported rather than aborted — but it is not a clean run.
    probe.code = 1 if probe.parse_error else 0
    return probe


def _stage_d(probe: Probe, dl: Any, HostSpec: Any, args: argparse.Namespace) -> None:
    """Follow one parameter's five slots into the raw-recipe folder.

    Writes everything it reaches onto ``probe`` as it goes rather than returning
    it, so a run that dies mid-parameter still hands back the files it had
    already downloaded.
    """
    probe.parameter = args.param
    print(f"\n=== Stage D: raw files for parameter {args.param!r} ===")

    frame = probe.idp_image_info
    if frame is None:
        print("    no idp_image_info — the parse did not run or did not return it.")
        return

    probe.param_rows = _param_rows(frame, args.param)
    if not probe.param_rows:
        available = sorted({str(p) for p in frame.get("Parameter", [])})
        print(f"    {args.param!r} is not in this recipe. It has {len(available)}:")
        print("      " + ", ".join(available[:40]))
        print("    Edit PARAMETER at the top of this file (or pass --param).")
        return

    readers, reader_error = _readers()
    if reader_error:
        print(f"    {reader_error}\n    Files will be downloaded and previewed, not parsed.")

    for i, row in enumerate(probe.param_rows):
        # One parameter can hold several rows — SEQ orders a mother/son group,
        # and each row carries its own slots. Printing SEQ/Region keeps the
        # files attributable when they differ between rows.
        print(f"\n  [{i}] SEQ={row.get('SEQ')!r} Region={row.get('Region')!r} "
              f"Mother_Para={row.get('Mother_Para')!r}")
        wants = _wants(row)
        if not wants:
            print("    every slot is empty — nothing to fetch.")
            continue

        print(f"\n    downloading {len(wants)} file(s) from {probe.raw_dir}")
        fetched = _fetch_raw(dl, HostSpec, probe.ip, probe.raw_dir, [w.name for w in wants])

        for want in wants:
            data = fetched.get(want.name)
            if data is None:
                print(f"\n    {want.slot:<11} {want.kind:<7} {want.name}  — not on the tool")
                continue
            dest = _save_raw(probe, args.out, want.name, data)
            print(f"\n    {want.slot:<11} {want.kind:<7} {want.name}  — {_describe(data)}")
            print(f"      -> {dest}")

            if want.kind in ("image", "pr-key"):
                # No reader claims these: images are for the browser, and the
                # PR… key file is here only to find out whether it holds
                # anything. A preview is the whole answer for both.
                if want.kind == "pr-key" or _decode(data)[0]:
                    print(_preview(data, lines=12))
                continue

            reader = readers.get(want.kind)
            if reader is None:
                print(_preview(data, lines=12))
                continue
            try:
                parsed = reader(data)
            except Exception:
                probe.raw_errors[want.name] = traceback.format_exc()
                print("\n".join(f"      {line}"
                                for line in probe.raw_errors[want.name].splitlines()))
                continue
            probe.raw_parsed[want.name] = parsed
            _print_parsed(want.name, reader, parsed)


def _stage_e(probe: Probe, dl: Any, HostSpec: Any, args: argparse.Namespace) -> None:
    """The wafer-align file set — a different two readers from Stage D's.

    Align files look like parameter files and are not read like them
    (user-confirmed 2026-07-29): the ENAP settings go to
    ``get_align_beam_pr_conditions`` for the whole point list at once, and the
    image's cond.txt to ``read_align_image_condition``, which has to be told
    whether the point is OM (P.No 1) or SEM (P.No 2).

    Unlike the adapter, this fetches the align IMAGE too. The adapter only
    names it and lets the browser pull it later, but whether those images exist
    at all is still an open question in docs/datatables/recipe_idp.txt, and one
    listing answers it.
    """
    print("\n=== Stage E: wafer-align files ===")

    frame = probe.wafer_align_info
    if frame is None or "P.No" not in getattr(frame, "columns", []):
        print("    no wafer_align_info — the parse did not run or did not return it.")
        return

    # One file set per DISTINCT P.No: the align table names a P.No once per
    # align mark, so the same point repeats down the rows.
    probe.align_points = sorted({int(p) for p in frame["P.No"]})
    optics = {p_no: rawfiles.align_optics(p_no) for p_no in probe.align_points}
    print(f"    align points (unique P.No): "
          f"{', '.join(f'{p}={optics[p] or 'UNKNOWN OPTIC'}' for p in probe.align_points)}")
    unknown = [p_no for p_no, which in optics.items() if which is None]
    if unknown:
        print(f"    NOTE: {unknown} is outside the documented 1=OM / 2=SEM pair. "
              "Its image condition cannot be read without knowing the optic.")

    plan = [(p_no, *rawfiles.align_names(p_no)) for p_no in probe.align_points]
    names = [
        name
        for p_no, image, setting in plan
        for name in (image, rawfiles.cond_source(image), setting)
    ]
    print(f"\n    downloading {len(names)} file(s) from {probe.raw_dir}")
    fetched = _fetch_raw(dl, HostSpec, probe.ip, probe.raw_dir, names)

    readers, reader_error = _readers()
    if reader_error:
        print(f"    {reader_error}\n    Files will be downloaded and previewed, not parsed.")

    for p_no, image, setting in plan:
        cond = rawfiles.cond_source(image)
        print(f"\n  [P.No {p_no}] optic={optics[p_no] or '?'}  "
              f"image={image}  cond={cond}  setting={setting}")
        for name in (image, cond, setting):
            data = fetched.get(name)
            if data is None:
                print(f"    {name}  — not on the tool")
                continue
            print(f"    {name}  — {_describe(data)}")
            print(f"      -> {_save_raw(probe, args.out, name, data)}")

        # The image condition is read PER OPTIC. Passing a guessed "SEM" would
        # print the other instrument's settings as ordinary data, so an unknown
        # point is left unparsed here exactly as the adapter leaves it.
        reader = readers.get("align_cond")
        data = fetched.get(cond)
        if reader and data is not None and optics[p_no]:
            try:
                parsed = reader(data, optics[p_no])
            except Exception:
                probe.raw_errors[cond] = traceback.format_exc()
                print("\n".join(f"      {line}"
                                for line in probe.raw_errors[cond].splitlines()))
            else:
                probe.raw_parsed[cond] = parsed
                _print_parsed(f"{cond}, which={optics[p_no]!r}", reader, parsed)

    # ONE call for every point's ENAP, not one per point — that is the office
    # signature. Absent files are dropped first: a hole in the list would have
    # to be interpreted, and a positional return could then land on the wrong
    # point.
    batch = readers.get("align_batch")
    present = [setting for _, _, setting in plan if fetched.get(setting) is not None]
    if batch and present:
        print(f"\n  get_align_beam_pr_conditions({present}) — one call for the set")
        try:
            probe.align_settings = batch([fetched[name] for name in present])
        except Exception:
            probe.raw_errors["get_align_beam_pr_conditions"] = traceback.format_exc()
            print("\n".join(
                f"    {line}"
                for line in probe.raw_errors["get_align_beam_pr_conditions"].splitlines()
            ))
        else:
            # Whether this can be split per point is THE open question about
            # this function, so the length is printed beside the point count.
            parsed = probe.align_settings
            sized = len(parsed) if hasattr(parsed, "__len__") else "n/a"
            print(f"    -> {type(parsed).__name__}, len={sized}, "
                  f"for {len(present)} file(s)")
            _print_parsed(", ".join(present), batch, parsed)


if __name__ == "__main__":
    _console = _in_pydev_console()
    probe = main([] if _console else None)

    # Unpacked at module scope for the IDE. In PyCharm, put a breakpoint on the
    # sys.exit below and Debug: the pane then holds the whole run, and the
    # Evaluate box can slice it (idp_text.splitlines()[:40], doc["idp_name"]).
    # Running the file in the Python console leaves the same names at the >>>
    # prompt instead, to carry on with by hand.
    hits = probe.hits
    doc = probe.doc
    listing = probe.listing
    raw_listing = probe.raw_listing
    idp_bytes = probe.idp_bytes
    idp_text = probe.idp_text
    dest = probe.dest

    # The three parsed frames, each under its combined_idp_info key. Separate
    # names because a DataFrame nested in a dict is two clicks deep in the
    # variable pane, and these are what "View as DataFrame" is for. None when
    # the run stopped before the parse.
    tables = probe.tables
    wafer_mp_info = tables.get("wafer_mp_info")
    wafer_align_info = tables.get("wafer_align_info")
    idp_image_info = tables.get("idp_image_info")

    # Stage D. raw_files holds the bytes, so a setting file can be re-read by
    # hand — read_amp_info(raw_files["PRMS0000"]) — without a second FTP trip,
    # and an image can be opened straight from it (Image.open(BytesIO(...))).
    param_rows = probe.param_rows
    raw_files = probe.raw_files
    raw_parsed = probe.raw_parsed
    raw_errors = probe.raw_errors

    # Stage E. align_settings is the batch reader's single return value for the
    # whole ENAP list — whether it can be split per point is the open question,
    # so it is left exactly as the office handed it over.
    align_points = probe.align_points
    align_settings = probe.align_settings

    # Only a shell run has an exit status worth setting. Raising SystemExit into
    # a console session would print a traceback over output that is otherwise
    # fine, so there the module simply ends and leaves the names behind.
    if not _console:
        sys.exit(probe.code)
