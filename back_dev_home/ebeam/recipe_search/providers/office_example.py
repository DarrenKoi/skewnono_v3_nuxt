# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 adapter for the office recipe catalog (Redis) and recipe-open (FTP).

TWO INDEPENDENT SOURCES, one per endpoint.

**Catalog** (``get_recipe_catalog``) — Redis. One hash per tool family::

    v3_cdsem_unique_rcp_list   # CD-SEM
    v3_hvsem_unique_rcp_list   # HV-SEM

Each hash is keyed by **lowercase** fab name and holds that fab's recipe-name
list::

    {"m14a": ["1/AC_M2_TAT", ...], "r3": [...]}

``routes.py`` uppercases ``?fab_name=`` before it reaches this module, so the
lowercasing happens here — at the Redis boundary — and never leaks into the
routes. The response echoes the caller's (uppercase) spelling so the contract
matches the mock.

**Recipe open** (``get_recipe_open_data``) — the measuring tool's own FTP
server. The path is assembled from the Redis recipe registry when it can be,
and from measurement history when it cannot::

    v3_{cdsem,hvsem}_rcp_loc_{fab}        full_name -> [idw_name, idp_name]
    v3_{cdsem,hvsem}_tools_in_rcp_{fab}   full_name -> [eqp_id, ...]
                                                          │
                          sem_list roster: eqp_id ────────┴──►  FTP host
                          full_name's "/" prefix ──────────►  {class}

    (fallback) meas_hist_{cdsem,hvsem}            (OpenSearch)
      ├── eqp_ip      ─────────────────────────►  FTP host
      ├── class_name  ──┐
      ├── idw_name    ──┼───────────────────────►  /HITACHI/DEVICE/HD/{class}/data/{idw}
      └── idp_name    ──┘                              └── {idp}.idp
                                                            │
        office_utils.read_idp_info.combined_idp_info(path) ◄─┘
          -> {"wafer_mp_info": df, "wafer_align_info": df, "idp_image_info": df}

The two are all-or-nothing rather than blended: a location assembled half from
each would be untraceable the day the path it produces turns out wrong. Both
yield an ORDERED LIST of candidates and ``_download_first`` walks it, so one
unreachable tool no longer fails a recipe several tools hold.

On the registry path the ``eqp_id -> eqp_ip`` join through sem_list IS needed —
the same one lateral check makes. Only on the meas_hist path is it avoidable,
because there the measurement row already names the tool that ran the recipe,
so the host it must be readable from is the host we just proved ran it.

Column names and response types are the contract, not a convenience — see
``docs/datatables/recipe_idp.txt``, which is the schema of record for all three
tables and for this module's three known traps: ``wafer_align_info`` uses
dot-columns (``Chip.X``, ``P.No``); ``img_meas2`` means different things in
``wafer_mp_info`` (P_No's integer) and ``idp_image_info`` (a filename); and
``idp_image_info``'s ``Addressing``, ``Mother_Para`` and ``dnumber_removed``
are ``bool`` (office 확인 2026-07-28) — until then they were documented as a
``"Yes"``/``"No"`` string, a parameter name and an int64 count, and the screen
was built on all three guesses. The parser's dtypes are not reliable, so
``_scalar`` and ``_coerce`` normalize cells to the response contract. Exact
binary text sentinels (``"0"``/``"1"``) are accepted for booleans; ambiguous
words such as ``"False"`` are rejected and logged rather than interpreted via
Python truthiness.

WRITING THIS AT HOME: ``office_utils`` exists only on office machines, so a
gitignored stand-in of the same name sits at the repo root matching its
signature, keys, columns and dtypes. That makes everything below the parse
runnable here; only ``_locate_via_redis`` (Redis), ``_locate_via_meas_hist``
(OpenSearch), and ``_download_first``/``_download_idp`` (FTP) are genuinely
unreachable. They are separate functions from ``_to_detail_response`` for
exactly that reason — the mapping is covered by a tracked test that needs
neither.

STILL NOT WIRED:

* ``get_recipe_compare_data`` — re-exported from the mock below. Compare may
  request up to 200 recipes, and the honest office implementation is one FTP
  session per distinct tool with all of that tool's .idp files batched into a
  single ``HostSpec(files=[...])``. Until that exists, compare returns mock
  data while ``/recipe-detail`` returns real data, so **the "compare is derived
  from open" invariant is knowingly broken office-side.** See the TODO there.

``align_images`` and ``amp_info`` used to be listed here as fabricated even at
the office. They are gone as of 2026-07-29: their source turned out to be the
**raw-recipe folder** beside the .idp, read by a second 사내 parser::

    /HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}/
      ├── IMMP0001.jpeg              img_add1    addressing image
      ├── .IMMP0001.jpeg/cond.txt    its beam condition (hidden sibling dir)
      ├── ENMP0000                   img_add2, PR->EN   AF/PR condition
      ├── I2MP0000.jpeg              image_add3  addressing image 3
      ├── IMMS0000.jpeg              img_meas1   measurement image
      ├── PRMS0000                   img_meas2   AMP setting (name used as-is)
      ├── IMAP0001.jpeg / ENAP0001   per wafer-align P.No
      │
      └─►  office_utils.idp_amp_reader — FIVE readers, and which file goes to
           which is the contract (docs/datatables/recipe_idp.txt):

             read_meas_image_condition(src)     .IMMP/.I2MP/.IMMS cond.txt
             read_amp_info(src)                 PRMS…
             read_af_pr_condition(src)          ENMP…
             read_align_image_condition(src, which)   .IMAP{p}/cond.txt
             get_align_beam_pr_conditions([src, ...]) every ENAP at once

All five were run against real files on 2026-07-30, and three results shape the
code below rather than merely the documentation:

* **ENMP returns a dict OF DICTS** — eight groups covering the addressing and
  measurement sequences. ``_to_rows`` tags each inner key with its group and
  ``SettingRow.section`` carries it to the screen. Flattening would be silently
  wrong, not merely ugly: addressing pass 1 and pass 2 hold the SAME inner keys,
  so a row's identity is (section, key) and never key alone.
* **get_align_beam_pr_conditions keys its return by OPTIC**, ``{"OM": …,
  "SEM": …}``, so the one batched call CAN be split per align point — P.No 1 is
  OM and P.No 2 is SEM. ``_split_align_settings`` tries that first; its older
  positional and name-keyed guesses stay behind it.
* **The readers do not only return strings.** ENMP's Wait(s) and
  Relative Position X/Y(um) come back as Python floats beside str siblings in
  the same group, while cond.txt and PRMS… are genuinely all-str. ``_to_rows``
  already ``str()``s everything, which is why nothing here needed changing —
  but do not add code that assumes a reader handed back a string.

Field NAMES are recorded in docs/datatables/recipe_idp.txt, not here, and they
are expected to change as the office parser is refined. Nothing in this module
keys off any of them: the contract is open key/value precisely so a renamed
field shows up on screen instead of vanishing.

Naming lives in ``rawfiles.py`` (pure, fully tested at home); the wiring is
``get_param_detail`` / ``get_align_detail`` / ``fetch_recipe_image`` below.
``"non"`` — French, not ``"none"`` — means the slot has no file, and a missing
file is normal rather than an error.

READ-ONLY, by design (user-confirmed 2026-07-30). This screen shows recipe
settings; there is no write mode. Every route is a read — the two POSTs take a
list body only because ``/api/*`` allows 20 requests per 5 s and a 20-recipe
compare would trip that as separate GETs. **Nothing is written anywhere**:
neither to the tool — these are live metrology recipes — nor to the Flask host,
since ``combined_idp_info`` accepts bytes as well as a path (user-confirmed
2026-08-05), the same as the five raw readers. The temp file this module kept
until then existed only to satisfy a path-only signature that never was one.

Connection settings come from ``REDIS_*`` and ``OPENSEARCH_*`` in
``back_dev_home/.env`` (self-loaded), and FTP credentials from
``SKEWNONO_TOOL_FTP_*`` — the same ones msr_image uses, because ``images/{msr}``
and ``data/{idw}`` are sibling folders on the same servers. At the office: fill
in .env, then `cp office_example.py office.py` — that file's existence is the
switch, no env var needed — and run the Verify command in MIGRATION.md.
"""

import ast
import json
import logging
import os
import tempfile
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from platform import system
from typing import Any, NamedTuple

import pandas as pd

from back_dev_home._runtime.office_redis import redis_client as _redis_client
from back_dev_home.ebeam._office_search import fetch_hits, query, ttl_cache
from back_dev_home.ebeam.recipe_search import rawfiles
from back_dev_home.msr_image.errors import SourceUnavailable
from back_dev_home.ebeam.recipe_search.contracts import (
    AlignDetailResponse,
    AlignPoint,
    IdpImageInfoRow,
    IdpLocator,
    ParamDetailRequestItem,
    ParamDetailResponse,
    RecipeDetailResponse,
    RecipeSearchResponse,
    RecipeSearchRow,
    SettingBlock,
    SettingRow,
    ToolType,
    WaferAlignInfoRow,
    WaferMpInfoRow,
)
from back_dev_home.sem_list.data import get_sem_list
# TODO(office): replace with a batched IDP-backed implementation — one FTP
# session per distinct eqp_ip, every recipe's .idp in one HostSpec(files=[...]).
# Re-exported (not reimplemented) so that when it lands it can stay derived
# from open, the invariant the mock guarantees.
from back_dev_home.ebeam.recipe_search.providers.mock import (
    IMAGE_SLOTS,
    get_recipe_compare_data,
)


__all__ = [
    "fetch_recipe_image",
    "get_align_detail",
    "get_param_detail",
    "get_recipe_catalog",
    "get_recipe_compare_data",
    "get_recipe_open_data",
]


_LOG = logging.getLogger(__name__)


_RECIPE_HASH: dict[ToolType, str] = {
    "cd-sem": "v3_cdsem_unique_rcp_list",
    "hv-sem": "v3_hvsem_unique_rcp_list",
}

# The same two families, spelled the way the per-fab registry hashes spell
# them. _RECIPE_HASH above is a whole key because the catalog has one hash per
# family; the registry has one hash per family AND fab, so it is built instead.
_FAMILY: dict[ToolType, str] = {"cd-sem": "cdsem", "hv-sem": "hvsem"}


# ── catalog (Redis) ───────────────────────────────────────────────────────


def _parse_str_list(value) -> list[str]:
    """A hash value -> list of strings, tolerant of JSON / repr / CSV.

    Shared by all three per-recipe hashes (the name catalog, the location
    registry, the tool registry) because they are written by the same kind of
    job: a Python list that lands in Redis as JSON (``["a", "b"]``) or as a
    ``repr`` (``['a', 'b']``) depending on the writer, and both parse here. The
    CSV fallback covers a plain comma-joined string — recipe names, paths and
    equipment ids carry ``/`` and ``_`` but no commas, so that split is safe as
    a last resort.
    """
    if isinstance(value, (bytes, bytearray)):
        value = bytes(value).decode("utf-8")
    value = str(value).strip()
    if not value:
        return []
    for parse in (json.loads, ast.literal_eval):
        try:
            parsed = parse(value)
        except (ValueError, SyntaxError):
            continue
        if isinstance(parsed, (list, tuple)):
            return [str(name).strip() for name in parsed if str(name).strip()]
    return [name.strip() for name in value.split(",") if name.strip()]


def _unique(names: list[str]) -> list[str]:
    """De-dup, first-seen order preserved.

    The hashes are named ``*_unique_rcp_list``, so upstream already promises
    uniqueness — this makes the promise cheap to keep rather than trusted,
    and stops the single-fab and all-fab paths from having different
    guarantees.
    """
    return list(dict.fromkeys(names))


def _missing_key_error(key: str) -> LookupError:
    return LookupError(
        f"Redis key {key!r} not found — check REDIS_HOST/REDIS_PORT/"
        "REDIS_PASSWORD in back_dev_home/.env and that the recipe-list job "
        "has populated the hash."
    )


def _tagged_rows(names: Iterable[str], fab_name: str) -> list[RecipeSearchRow]:
    fab = fab_name.strip().upper()
    return [{"recipe_name": name, "fab_name": fab} for name in names]


def _recipes_for_fab(client, key: str, fab_name: str) -> list[str]:
    """One fab's recipe names. Unknown fab -> empty, missing key -> error.

    A missing *field* and a missing *key* mean different things: the first is
    "this fab has no recipes" (a legitimate empty result), the second is "the
    upstream job never ran" (an infrastructure fault worth a 502). Only probe
    for the key when the field lookup comes back empty, so the common path
    stays a single round trip.
    """
    raw = client.hget(key, fab_name.strip().lower())
    if raw is not None:
        return _unique(_parse_str_list(raw))
    if not client.exists(key):
        raise _missing_key_error(key)
    return []


def _all_recipes(client, key: str) -> list[RecipeSearchRow]:
    """Every fab's recipe names, tagged with the owning fab.

    Reached only when the caller omits ``fab_name``. The hash field IS the
    provenance (field = lowercase fab), and the row grain is (recipe, fab),
    so there is no cross-fab dedupe — a name present in two fabs is two rows.
    """
    entries = client.hgetall(key)
    if not entries:
        raise _missing_key_error(key)
    rows: list[RecipeSearchRow] = []
    for field, value in entries.items():
        fab = field.decode() if isinstance(field, bytes) else str(field)
        rows.extend(_tagged_rows(_unique(_parse_str_list(value)), fab))
    return rows


def get_recipe_catalog(
    tool_type: ToolType,
    fab_names: Sequence[str] | None = None,
) -> RecipeSearchResponse:
    key = _RECIPE_HASH.get(tool_type)
    if key is None:
        raise ValueError(
            f"Unknown tool_type {tool_type!r}; expected one of {sorted(_RECIPE_HASH)}"
        )
    requested = [fab.strip().upper() for fab in (fab_names or ()) if fab and fab.strip()]
    client = _redis_client()
    if requested:
        rows: list[RecipeSearchRow] = []
        for fab in requested:
            rows.extend(_tagged_rows(_recipes_for_fab(client, key, fab), fab))
    else:
        rows = _all_recipes(client, key)
    return {
        "tool_type": tool_type,
        "fab_names": requested,
        "total": len(rows),
        "rows": rows,
    }


# ── recipe open, step 1: locate the .idp (OpenSearch) ─────────────────────


# Same aliases _office_meas_hist.INDEX names. Declared locally rather than
# imported so recipe_search does not take a dependency on recipe_tat's
# contracts module for two string literals; docs/datatables/meas_hist.txt is
# the shared record if they ever change.
_MEAS_HIST_INDEX: dict[ToolType, str] = {
    "cd-sem": "meas_hist_cdsem",
    "hv-sem": "meas_hist_hvsem",
}

# The catalog's recipe names are "class/recipe" strings, which is exactly
# meas_hist's `full_name` (docs/datatables/meas_hist.txt) — so the id the
# frontend hands back from the search table is already the lookup key.
_FULL_NAME_KW = "full_name.keyword"
_FAB_NAME_KW = "fab_name.keyword"

# CASE TRAP: the Redis catalog keys fabs in lowercase, meas_hist stores them
# uppercase ("R3"). routes.py uppercases the query param, so the catalog path
# lowercases (above) and this path must NOT.

_SOURCE = ["class_name", "idw_name", "idp_name", "eqp_ip", "eqp_id", "timestamp"]

# Newest first, but keep a few in reserve: a recipe's most recent run is the
# best guess at where its current .idp lives, and if that document is missing
# a field the next one down is a better answer than a 502.
_LOCATE_CANDIDATES = 5

# Root shared with msr_image (office 확인 2026-07-24): images/{msr} and
# data/{idw} are siblings under the same tree, on the same servers.
_FTP_ROOT = "/HITACHI/DEVICE/HD"


class _IdpLocation(NamedTuple):
    eqp_id: str
    eqp_ip: str
    class_name: str
    idw_stem: str
    idp_stem: str


def _stem(value: Any) -> str:
    """'/Recipe/ADI/ADI_CD_BIAS_001.idp' -> 'ADI_CD_BIAS_001'.

    meas_hist stores idp_name/idw_name as *paths* while the FTP tree wants a
    bare folder/file name (office 확인 2026-07-27). Tolerates a bare name
    already, since the stem of a name without a directory is that name.
    """
    return PurePosixPath(str(value or "").strip()).stem


def _fab_hash(kind: str, tool_type: ToolType, fab_name: str) -> str:
    """Redis key for one fab's per-recipe registry hash.

    ``kind`` is ``"rcp_loc"`` (the ``[idw_name, idp_name]`` pair) or
    ``"tools_in_rcp"`` (the equipment list). The fab is lowercased HERE, at the
    Redis boundary, for the same reason the catalog does it: routes.py hands
    down an uppercase name and nothing above this module should have to know
    that the store disagrees.
    """
    family = _FAMILY.get(tool_type)
    if family is None:
        raise ValueError(
            f"Unknown tool_type {tool_type!r}; expected one of {sorted(_FAMILY)}"
        )
    return f"v3_{family}_{kind}_{fab_name.strip().lower()}"


def _class_name(recipe_id: str) -> str:
    """'ADI/ADI_CD_BIAS_001' -> 'ADI'. The FTP tree's class directory.

    ``full_name = f"{class_name}/{recipe_name}"``
    (docs/datatables/meas_hist.txt), so on the Redis path the class is the
    prefix of the key just looked up — neither registry hash carries it
    separately, and meas_hist is not queried to get it.

    A name with no ``/`` yields ``""`` rather than the name itself: using the
    whole name would assemble a plausible path to a directory that does not
    exist, and a blank forces the caller to fall back instead.
    """
    return recipe_id.split("/", 1)[0].strip() if "/" in recipe_id else ""


@ttl_cache
def _eqp_ip_index() -> dict[str, tuple[str, str]]:
    """``eqp_id -> (eqp_ip, available)`` for the whole fleet.

    The registry names tools by ``eqp_id`` but FTP dials an IP, so the roster
    resolves the gap — the same ``eqp_id -> eqp_ip`` join lateral check makes,
    and through the same source, so the two screens cannot disagree about
    which tools exist.

    Cached because ``get_sem_list()`` deserializes two parquet blobs from Redis
    and merges them: reasonable once per TTL, wasteful once per recipe open.
    What that costs is an IP change taking up to 15 minutes to be seen, which
    is the right trade for a roster that only moves when tools do.
    """
    index: dict[str, tuple[str, str]] = {}
    for row in get_sem_list():
        eqp_id = str(row.get("eqp_id") or "").strip()
        eqp_ip = str(row.get("eqp_ip") or "").strip()
        if eqp_id and eqp_ip:
            index[eqp_id] = (eqp_ip, str(row.get("available") or ""))
    return index


def _order_candidates(
    eqp_ids: list[str],
    index: dict[str, tuple[str, str]],
) -> list[tuple[str, str]]:
    """``[eqp_id, ...]`` -> ``[(eqp_id, eqp_ip), ...]``, best host first. Pure.

    Tools the roster reports available sort ahead of the rest; within each
    group the registry's own order is preserved, since it carries no ranking
    and a stable order keeps the same recipe hitting the same tool. Offline
    tools are kept rather than dropped — ``available`` describes whether the
    tool is running production, not whether its FTP server answers, and the
    .idp is worth trying for once the online tools have failed.

    An ``eqp_id`` the roster does not know is dropped: the registry says the
    recipe is there, but with no IP there is nothing to dial.
    """
    online: list[tuple[str, str]] = []
    offline: list[tuple[str, str]] = []
    unknown: list[str] = []
    for raw_id in eqp_ids:
        eqp_id = raw_id.strip()
        resolved = index.get(eqp_id)
        if resolved is None:
            unknown.append(eqp_id)
            continue
        eqp_ip, available = resolved
        (online if available == "On" else offline).append((eqp_id, eqp_ip))
    if unknown:
        _LOG.warning(
            "recipe_search: %d tool(s) named by the recipe registry are not in "
            "the sem_list roster and were skipped: %s. The two sources use the "
            "same eqp_id spelling (user-confirmed 2026-07-29), so this means "
            "the roster is missing the tool, not that the ids disagree.",
            len(unknown), unknown,
        )
    # A tools_in_rcp value can repeat an eqp_id; collapse exact repeats so the
    # download walk tries each distinct tool once rather than re-dialing one.
    return list(dict.fromkeys(online + offline))


def _locate_via_redis(
    tool_type: ToolType,
    recipe_id: str,
    fab_name: str | None,
    notes: list[str] | None = None,
) -> list[_IdpLocation] | None:
    """Candidate locations from the two per-fab registry hashes, or ``None``.

    ``None`` means "ask meas_hist" and is never an error: the registry is a
    newer source and is not promised to cover every fab or every recipe. It is
    all-or-nothing on purpose — a location assembled half from the registry and
    half from measurement history would be untraceable the day the path it
    produces turns out to be wrong.

    Every bail names the step that produced it, and that reason goes to TWO
    places: the log, and ``notes`` if the caller passed a list. ``_locate_idp``
    passes one so the reason can ride along on the error the browser receives —
    from outside the office, a log line is not evidence anybody has.
    """
    def _bail(reason: str) -> None:
        if notes is not None:
            notes.append(reason)
        _LOG.info("recipe_search: %s — falling back to meas_hist.", reason)
        return None

    if not fab_name:
        return _bail(
            f"no fab_name for {recipe_id!r}, so no registry key can be built"
        )

    class_name = _class_name(recipe_id)
    if not class_name:
        return _bail(
            f"{recipe_id!r} has no class prefix, so the registry cannot supply "
            "the FTP class directory"
        )

    client = _redis_client()

    loc_key = _fab_hash("rcp_loc", tool_type, fab_name)
    parts = _parse_str_list(client.hget(loc_key, recipe_id) or "")
    if len(parts) < 2:
        return _bail(
            f"{loc_key} has no usable [idw, idp] entry for {recipe_id!r} "
            f"(got {parts})"
        )

    tools_key = _fab_hash("tools_in_rcp", tool_type, fab_name)
    eqp_ids = _parse_str_list(client.hget(tools_key, recipe_id) or "")
    if not eqp_ids:
        return _bail(f"{tools_key} names no tool for {recipe_id!r}")

    idw_stem, idp_stem = _stem(parts[0]), _stem(parts[1])
    if not idw_stem or not idp_stem:
        return _bail(
            f"{loc_key} entry for {recipe_id!r} has an empty path component "
            f"({parts[:2]})"
        )

    candidates = _order_candidates(eqp_ids, _eqp_ip_index())
    if not candidates:
        return _bail(
            f"none of {eqp_ids} resolves to an IP for {recipe_id!r} — the "
            "sem_list roster does not carry these tools"
        )

    _LOG.info(
        "recipe_search: located %r via the Redis registry — %d tool "
        "candidate(s), no OpenSearch query.", recipe_id, len(candidates),
    )
    return [
        _IdpLocation(
            eqp_id=eqp_id,
            eqp_ip=eqp_ip,
            class_name=class_name,
            idw_stem=idw_stem,
            idp_stem=idp_stem,
        )
        for eqp_id, eqp_ip in candidates
    ]


def _locate_via_meas_hist(
    tool_type: ToolType,
    recipe_id: str,
    fab_name: str | None,
) -> list[_IdpLocation]:
    """Candidate locations from measurement history, newest run first.

    The fallback for anything the Redis registry cannot answer, and still the
    only source for a fab the registry does not cover. Every complete document
    becomes a candidate rather than only the newest: if the tool that ran the
    recipe most recently is unreachable, the tool that ran it the time before
    holds the same file.

    Raises:
        LookupError: no measurement document names this recipe, or none of the
            candidates carries the four fields the FTP path is assembled from.
    """
    index = _MEAS_HIST_INDEX.get(tool_type)
    if index is None:
        raise ValueError(
            f"Unknown tool_type {tool_type!r}; expected one of {sorted(_MEAS_HIST_INDEX)}"
        )

    clauses: list[dict[str, Any]] = [{"term": {_FULL_NAME_KW: recipe_id}}]
    if fab_name:
        clauses.append({"term": {_FAB_NAME_KW: fab_name}})

    hits = fetch_hits(
        index,
        query(clauses),
        size=_LOCATE_CANDIDATES,
        sort=[{"timestamp": "desc"}],
        source=_SOURCE,
    )
    if not hits:
        raise LookupError(
            f"No document in {index} has full_name={recipe_id!r}"
            + (f" for fab {fab_name!r}" if fab_name else "")
            + ". A recipe that exists in the catalog but has never been measured "
            "has no .idp location to derive — recipe open needs one run, or an "
            "entry in the Redis recipe registry."
        )

    complete: list[_IdpLocation] = []
    incomplete: list[str] = []
    for hit in hits:
        location = _IdpLocation(
            eqp_id=str(hit.get("eqp_id") or "").strip(),
            eqp_ip=str(hit.get("eqp_ip") or "").strip(),
            class_name=str(hit.get("class_name") or "").strip(),
            idw_stem=_stem(hit.get("idw_name")),
            idp_stem=_stem(hit.get("idp_name")),
        )
        missing = [
            name
            for name, value in (
                ("eqp_ip", location.eqp_ip),
                ("class_name", location.class_name),
                ("idw_name", location.idw_stem),
                ("idp_name", location.idp_stem),
            )
            if not value
        ]
        if not missing:
            complete.append(location)
            continue
        incomplete.append(f"{hit.get('timestamp')}: missing {', '.join(missing)}")

    if complete:
        # meas_hist's grain is one document per measurement RUN — one tool
        # running one recipe on one lot (docs/datatables/meas_hist.txt) — so
        # the newest _LOCATE_CANDIDATES documents for a recipe are usually the
        # SAME tool measuring several different lots, which would otherwise
        # yield several identical _IdpLocation tuples. Without collapsing
        # them, _download_first would re-dial that one (possibly dead) host
        # several times instead of trying several different hosts.
        return list(dict.fromkeys(complete))

    raise LookupError(
        f"Found {len(hits)} document(s) in {index} for full_name={recipe_id!r}, "
        "but none carries every field the FTP path needs — "
        + " | ".join(incomplete)
    )


def _locate_idp(
    tool_type: ToolType,
    recipe_id: str,
    fab_name: str | None,
) -> list[_IdpLocation]:
    """Where this recipe's .idp can be fetched from, best candidate first.

    The Redis registry knows this directly and answers without a query to
    measurement history; meas_hist is the fallback. Both return an ordered
    list rather than one answer so the download can walk it.

    When BOTH come up empty the error names both, because the meas_hist half
    alone is the least useful sentence of the two: "this recipe was never
    measured" is the expected state for a great many recipes, and the registry
    exists precisely to serve them. What the operator needs to know is why the
    registry did not.

    READING THE 502 THIS RAISES — the presence of the registry clause tells you
    which adapter is deployed, which is worth more than it sounds:

      * clause present -> office.py has the registry path; the clause says why
        it declined, and the fix is in Redis (or in the fab/recipe spelling).
      * clause ABSENT  -> office.py predates the registry entirely (a STALE
        copy of a pre-2026-07-29 template). It never consulted Redis at all.
        Refresh it: ``python -m scripts.sync_office_adapters recipe_search``.
        The boot log flags this too, but a 502 body reaches further.
    """
    notes: list[str] = []
    located = _locate_via_redis(tool_type, recipe_id, fab_name, notes)
    if located:
        return located
    try:
        return _locate_via_meas_hist(tool_type, recipe_id, fab_name)
    except LookupError as exc:
        if not notes:
            raise
        # Bare LookupError, never a subclass: back_dev_home/__init__.py maps
        # only the exact type to a 502 and turns subclasses into opaque 500s.
        raise LookupError(
            f"{exc} Redis recipe registry was tried first and declined: "
            + "; ".join(notes)
            + "."
        ) from exc


def _idp_remote_path(location: _IdpLocation) -> str:
    """The .idp file's absolute path on that tool's FTP server. Pure."""
    return (
        f"{_FTP_ROOT}/{location.class_name}/data/"
        f"{location.idw_stem}/{location.idp_stem}.idp"
    )


# ── recipe open, step 2: fetch it (FTP) ───────────────────────────────────


class _Transport(NamedTuple):
    """The FTP classes this host talks to tools with, plus a log label.

    Named rather than a bare 4-tuple because the three classes are structurally
    interchangeable at the call site: every caller unpacks all four and two of
    the three discard ``list_dir_cls``. Reorder the return and nothing here
    complains — the failure surfaces as a broken FTP call at the office, which
    is the worst place this repo has to debug anything.
    """

    downloader_cls: type
    host_spec_cls: type
    list_dir_cls: type
    label: str


def _transport() -> _Transport:
    """The FTP transport for this host.

    The office Windows PC has no direct FTP egress to the tools and must go
    through the fileloader HTTP proxy; the cloud Linux host reaches them
    directly. Identical split to msr_image, so behaviour verified there
    transfers here unchanged.
    """
    if system() == "Windows":
        from ftp_handler.proxy import FtpFleetDownloader, HostSpec, ListDir
        return _Transport(FtpFleetDownloader, HostSpec, ListDir, "proxy (Windows)")
    from ftp_handler.direct_downloader import FtpFleetDownloader, HostSpec, ListDir
    return _Transport(FtpFleetDownloader, HostSpec, ListDir, "direct")


def _downloader(downloader_cls, config):
    """One place the FTP credentials and timeout are wired in.

    Both the .idp download and the raw-folder fetch construct the same client,
    so a credential or timeout change would otherwise have to be made twice in
    this file.
    """
    return downloader_cls(
        user=config.ftp_user,
        password=config.ftp_password,
        port=config.ftp_port,
        connect_timeout=config.ftp_timeout,
    )


def _download_idp(location: _IdpLocation) -> bytes:
    """RETR the .idp and return its bytes.

    Nothing lands on disk: ``combined_idp_info`` takes bytes (user-confirmed
    2026-08-05), so the download goes straight to the parser the same way the
    raw-folder files go straight to the five readers.

    Raises:
        LookupError: the tool refused the connection or does not have the file.
    """
    from back_dev_home.msr_image.config import load_config
    from back_dev_home.msr_image.paths import validate_tool_ip

    config = load_config()
    # The backend opens an FTP session to whatever this resolves to, so the
    # SSRF guard applies even though the IP came from OpenSearch and not from
    # a client. A tool outside the allowed subnets is a finding, not a fetch.
    validate_tool_ip(location.eqp_ip, config.allowed_subnets)

    remote_path = _idp_remote_path(location)
    tp = _transport()
    downloader_cls, host_spec_cls, transport = tp.downloader_cls, tp.host_spec_cls, tp.label
    report = _downloader(downloader_cls, config).download(
        [host_spec_cls(location.eqp_ip, files=[remote_path])]
    )

    fetched = {result.remote_path: result.data for result in report.files}
    if remote_path not in fetched:
        reasons = "; ".join(
            f"{failure.remote_path or location.eqp_ip}: {failure.error}"
            for failure in report.failures
        ) or "no failure reported"
        raise LookupError(
            f"Could not download {remote_path} from {location.eqp_id or '?'} "
            f"({location.eqp_ip}, transport: {transport}) — {reasons}"
        )

    data = fetched[remote_path]
    _LOG.info(
        "recipe_search: fetched %s (%d bytes) from %s via %s",
        remote_path, len(data), location.eqp_ip, transport,
    )
    return data


def _download_first(
    candidates: list[_IdpLocation],
) -> tuple[bytes, _IdpLocation]:
    """Try each candidate in order; return the first success AND its location.

    The location is returned, not just the path, because the caller has to know
    WHICH tool actually served the file: `RecipeDetailResponse.locator` sends
    the client back to that tool's raw-recipe folder, and with a candidate list
    the winner is not necessarily the first entry. Handing back only the path
    would leave the caller naming a tool that may not hold the folder at all.

    Raises:
        InvalidToolIp: EVERY candidate was refused by the tool-IP guard.
        LookupError: candidates were dialable but none served the file.
    """
    # Imported here, not at module scope, to match _download_idp's deferral of
    # the msr_image imports. InvalidToolIp is NOT a LookupError subclass
    # (msr_image/errors.py: it descends from MsrImageError), so the two except
    # clauses below are disjoint.
    from back_dev_home.msr_image.errors import InvalidToolIp

    failures = []
    blocked = []
    for location in candidates:
        try:
            return _download_idp(location), location
        except InvalidToolIp as exc:
            # Skipped rather than raised: one stale roster IP must not fail
            # every recipe held on that tool. The guard still refuses to dial
            # it and the WARNING names it, so the roster can be corrected.
            blocked.append(exc)
            _LOG.warning(
                "recipe_search: %s (%s) is outside SKEWNONO_TOOL_SUBNETS and "
                "was skipped — %s", location.eqp_id, location.eqp_ip, exc,
            )
            failures.append(
                f"{location.eqp_id or '?'} ({location.eqp_ip}): IP blocked"
            )
        except LookupError as exc:
            failures.append(f"{location.eqp_id or '?'}: {exc}")

    if blocked and len(blocked) == len(candidates):
        # Not a fetch failure. Every tool holding this recipe sits outside the
        # allowed subnets, which is a configuration fault worth surfacing as
        # itself rather than flattening into "could not download".
        raise blocked[0]

    # Unreachable today (get_recipe_open_data always calls this with at least
    # one candidate — _locate_via_redis/_locate_via_meas_hist both raise or
    # return non-empty), but an empty candidates list must not read as if a
    # failure were omitted: no " — " separator when there is nothing to list.
    detail = f" — {' | '.join(failures)}" if failures else ""
    raise LookupError(f"Tried {len(candidates)} tool(s) and none served the .idp{detail}")


# ── recipe open, step 3: parse it (office_utils) ──────────────────────────


_PARSED_TABLES = ("wafer_mp_info", "wafer_align_info", "idp_image_info")

# Each table's documented columns. Used ONLY to recognise a table when the
# parser hands back a bare container instead of the documented mapping, so the
# recovery below identifies tables by what they contain rather than by their
# position — position would map silently wrong on a parser that reorders.
_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "wafer_mp_info": frozenset(WaferMpInfoRow.__annotations__),
    "wafer_align_info": frozenset(WaferAlignInfoRow.__annotations__),
    "idp_image_info": frozenset(IdpImageInfoRow.__annotations__),
}

# How many documented columns a frame must share with a table before it counts
# as that table. ``Parameter`` and ``img_meas2`` appear in two of the three, so
# anything below 3 could match the wrong one; every real table clears it (mp
# and image have 14 columns each, align has 6).
_IDENTIFY_MIN_COLUMNS = 3


def _describe(value: Any) -> str:
    """One unknown object -> a short description. Must never raise.

    Every caller is on an error path, so a description that itself throws
    replaces the diagnosis with a second, less informative traceback — which is
    exactly what ``sorted()`` over a list of dicts used to do here
    (``'<' not supported between instances of 'dict' and 'dict'``).
    """
    if isinstance(value, pd.DataFrame):
        return f"DataFrame({len(value)} rows, columns {[str(c) for c in value.columns][:16]})"
    if isinstance(value, dict):
        # Values described alongside keys: the second 2026-08-03 cloud 502
        # named the keys of two dicts (the three documented names, twice) and
        # nothing else, leaving what they HELD as guesswork. Sorted by key so
        # the message is stable across parser insertion orders.
        items = ", ".join(
            f"{key}={_describe(value[key])}" for key in sorted(value, key=str)[:8]
        )
        return f"dict({len(value)} items: {items})"
    if isinstance(value, (list, tuple)):
        inner = ", ".join(_describe(item) for item in value[:4])
        return f"{type(value).__name__}({len(value)} items: {inner})"
    return f"{type(value).__name__}({value!r:.60})"


def _parse_error(source: str, saw: Any, detail: str) -> LookupError:
    """The one shape of parse-failure message, so the variants cannot drift."""
    return LookupError(
        f"combined_idp_info({source}) returned {_describe(saw)} — {detail}. "
        "docs/datatables/recipe_idp.txt is the schema of record."
    )


def _as_frame(value: Any) -> pd.DataFrame | None:
    """Anything table-shaped -> a DataFrame; None if it is not table-shaped."""
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, (dict, list, tuple)):
        try:
            return pd.DataFrame(value)
        except (ValueError, TypeError):
            return None
    return None


def _require_frame(value: Any, table: str, source: str) -> pd.DataFrame:
    """A documented key's value -> a DataFrame, or a diagnosis.

    The documented return holds DataFrames. Without this, a parser that keeps
    the three keys but changes their values reaches ``_records`` and dies on
    ``frame.columns`` — the same crash-instead-of-diagnosis this whole function
    family exists to prevent, one step further down.
    """
    if isinstance(value, pd.DataFrame):
        return value
    frame = _as_frame(value)
    if frame is None:
        raise _parse_error(
            source, value,
            f"whose {table!r} is not a DataFrame and not table-shaped",
        )
    _LOG.warning(
        "recipe_search: combined_idp_info(%s) returned %s for %s rather than a "
        "DataFrame; converted. docs/datatables/recipe_idp.txt says DataFrame.",
        source, type(value).__name__, table,
    )
    return frame


def _identify_table(frame: pd.DataFrame) -> str | None:
    """Which documented table is this, judged by its columns alone."""
    columns = {str(column) for column in frame.columns}
    scored = sorted(
        ((len(columns & documented), table)
         for table, documented in _TABLE_COLUMNS.items()),
        reverse=True,
    )
    (best_score, best_table), (runner_up_score, _) = scored[0], scored[1]
    if best_score < _IDENTIFY_MIN_COLUMNS or best_score == runner_up_score:
        return None
    return best_table


def _normalize_frames(raw: Any, source: str) -> dict[str, pd.DataFrame]:
    """Parser output -> the three documented tables, or a usable error.

    The documented return is a three-key mapping (``recipe_idp.txt`` §파서 반환
    구조, user-confirmed 2026-07-27) and that path is untouched. A parser that
    returns a bare container of tables instead is recovered from — by matching
    documented columns, never by position — because the alternative is a dead
    screen at the office over a shape home can neither see nor reproduce. Every
    recovery is logged as a warning: the doc is the schema of record, so a
    return shape it does not describe is a doc bug to reconcile, not a new
    normal to absorb silently.

    The container is taken as anything iterable rather than ``list``/``tuple``
    specifically. The cloud traceback proves only that ``sorted()`` compared two
    dicts, and ``sorted()`` iterates ANY iterable — a ``Series`` or an
    ``ndarray`` of dicts fits the evidence exactly as well, so accepting only
    the two obvious containers would leave the reported failure unfixed.

    The second cloud 502 (2026-08-03, OFFICE-VERIFY) narrowed the shape: a
    tuple of TWO dicts, EACH carrying the three documented keys — the
    container wraps the documented mapping itself, it does not scatter loose
    tables. So candidates are also tried AS the mapping: one qualifies when
    each documented key's value identifies, by columns, as that key's own
    table. A shadow dict with the same keys but non-table values (whatever the
    second element holds) fails that test and falls away by content, not by
    position.
    """
    if isinstance(raw, dict) and all(name in raw for name in _PARSED_TABLES):
        return {
            name: _require_frame(raw[name], name, source) for name in _PARSED_TABLES
        }

    if isinstance(raw, dict):
        candidates, container = list(raw.values()), "mapping with undocumented keys"
    elif isinstance(raw, (str, bytes, pd.DataFrame)):
        # Iterable, but iterating them yields characters or column names — a
        # table count of one at best, and a misleading description at worst.
        raise _parse_error(source, raw, "which holds no tables to recover")
    else:
        try:
            candidates = list(raw)
        except TypeError:
            raise _parse_error(
                source, raw, "which is neither the documented mapping nor iterable",
            ) from None
        container = f"bare {type(raw).__name__}"

    # A candidate that IS the documented mapping (the observed tuple-of-dicts
    # shape) beats identifying loose frames: its key->table assignment is the
    # parser's own, verified per key by columns before it is believed.
    qualifying: list[dict[str, pd.DataFrame]] = []
    for candidate in candidates:
        if not (isinstance(candidate, dict)
                and all(name in candidate for name in _PARSED_TABLES)):
            continue
        frames: dict[str, pd.DataFrame] = {}
        for name in _PARSED_TABLES:
            frame = _as_frame(candidate[name])
            if frame is None or _identify_table(frame) != name:
                break
            frames[name] = frame
        else:
            qualifying.append(frames)

    if qualifying:
        first = qualifying[0]
        if any(
            not first[name].equals(other[name])
            for other in qualifying[1:] for name in _PARSED_TABLES
        ):
            # Two DIFFERENT full table sets (an OM/SEM split would look like
            # this). Choosing one renders a plausible screen over the wrong
            # half of the data — worse than the error, which now describes
            # both sets' contents.
            raise _parse_error(
                source, candidates,
                f"a {container} holding {len(qualifying)} distinct copies of "
                "the documented mapping, which columns cannot choose between",
            )
        _LOG.warning(
            "recipe_search: combined_idp_info(%s) returned a %s wrapping the "
            "documented three-key mapping; unwrapped it after verifying each "
            "table by its columns. docs/datatables/recipe_idp.txt now "
            "disagrees with the parser — reconcile it. Saw: %s",
            source, container, _describe(candidates),
        )
        return first

    # Every match is kept, not just the first: two frames answering to the same
    # table means the columns did NOT decide it, and silently taking whichever
    # came first is the positional guess this function exists to refuse.
    identified: dict[str, list[pd.DataFrame]] = {}
    for candidate in candidates:
        frame = _as_frame(candidate)
        if frame is None:
            continue
        table = _identify_table(frame)
        if table is not None:
            identified.setdefault(table, []).append(frame)

    missing = [name for name in _PARSED_TABLES if name not in identified]
    ambiguous = [name for name in _PARSED_TABLES if len(identified.get(name, ())) > 1]
    if missing or ambiguous:
        trouble = ", ".join(filter(None, (
            f"{missing} could not be recognised by their documented columns" if missing else "",
            f"{ambiguous} matched more than one frame each" if ambiguous else "",
        )))
        raise _parse_error(source, candidates, f"a {container} in which {trouble}")

    _LOG.warning(
        "recipe_search: combined_idp_info(%s) returned a %s, not the documented "
        "three-key mapping. All three tables were recovered by their columns, "
        "but docs/datatables/recipe_idp.txt now disagrees with the parser — "
        "reconcile it. Saw: %s", source, container, _describe(candidates),
    )
    return {name: identified[name][0] for name in _PARSED_TABLES}


def _parse_idp(data: bytes, label: str) -> dict[str, pd.DataFrame]:
    """Run the 사내 IDP parser over the downloaded bytes.

    ``label`` never reaches the parser — it names the source in the LookupError
    ``_normalize_frames`` raises, which is the only diagnosis anyone gets for a
    parse that happened where no debugger can be attached.

    ESCAPE HATCH: ``SKEWNONO_RECIPE_IDP_VIA_TEMPFILE=1`` restores the pre-
    2026-08-05 behaviour — write the bytes to a temp file and pass the parser a
    path. "combined_idp_info takes bytes" is user-confirmed but has never been
    executed at the office, and this file cannot be tested from home, so the day
    it turns out the office parser wants a path there must be a way to keep
    recipe 열어보기 alive that does not require an edit, a review and a pull on
    an office PC. Set it in ``back_dev_home/.env``, restart, and tell home.
    Delete this branch once the bytes path has served real traffic.

    ``office_utils`` is imported here rather than at module scope on purpose:
    it exists only on office machines (home has a gitignored stand-in), and a
    module-scope import would turn its absence into a collection-time
    ImportError for anything that so much as imports this adapter — including
    the tracked tests. Deferred, it becomes a 503 on the one endpoint that
    needs it.

    Raises:
        RuntimeError: the parser is not installed (unconfigured environment).
        LookupError: it ran but did not return the three documented tables.
    """
    try:
        from office_utils.read_idp_info import combined_idp_info
    except ImportError as exc:
        raise RuntimeError(
            "office_utils.read_idp_info is not importable — recipe open needs "
            "the 사내 IDP parser. It exists only on office machines; at home a "
            "gitignored stand-in at the repo root fills in "
            "(docs/datatables/recipe_idp.txt §집에서의 대역)."
        ) from exc

    if os.getenv("SKEWNONO_RECIPE_IDP_VIA_TEMPFILE", "").strip() == "1":
        _LOG.warning(
            "recipe_search: SKEWNONO_RECIPE_IDP_VIA_TEMPFILE=1 — parsing %s "
            "through a temp file. Report this: it means combined_idp_info "
            "rejected bytes, contradicting docs/datatables/recipe_idp.txt.",
            label,
        )
        with tempfile.TemporaryDirectory(prefix="skewnono-idp-") as tmp_dir:
            local_path = Path(tmp_dir) / label
            local_path.write_bytes(data)
            return _normalize_frames(combined_idp_info(local_path), label)

    return _normalize_frames(combined_idp_info(data), label)


# ── recipe open, step 4: map to the contract (pure) ───────────────────────


def _scalar(value: Any) -> Any:
    """One DataFrame cell -> a JSON-safe Python scalar.

    Two hazards, both invisible at home unless the stand-in returns real
    frames: a missing value reaches JSON as ``NaN``, which is not valid JSON
    and makes the browser's ``JSON.parse`` throw on an otherwise-200 response;
    and on older pandas ``.to_dict()`` can hand back numpy scalars, which
    Flask's encoder rejects outright.
    """
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # arrays and other non-scalars: not missing, fall through
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except (AttributeError, ValueError):
            pass
    return value


def _coerce(value: Any, declared: Any, table: str, column: str, seen: set) -> Any:
    """One cell -> the type ``contracts.py`` promises the frontend.

    The office parser is not obliged to hand back the dtypes the schema doc
    records, and on 2026-08-05 it did not: ``Coordinate.X`` arrived as the
    string ``"52.676"``. Nothing here raised — ``_scalar`` passes a str
    through, the response was a valid 200 — and the browser called
    ``.toFixed(3)`` on it, which threw inside a computed and took out both the
    align table and the modal's close button.

    So the adapter converts rather than trusts. That is what
    "office adapters must normalize results to the contract" has to mean for
    TYPES as well as for shape; the mock builds its frames from a dtype map
    and can never reproduce the failure.

    Unconvertible values become ``None`` — a blank cell the screen already
    knows how to draw — and are logged once per (table, column) via ``seen``,
    because a 4000-row frame with one bad column would otherwise write 4000
    identical warnings.

    ``bool`` is deliberately NOT inferred from arbitrary text: ``bool("False")``
    is True, and those flags colour the screen. The parser's exact binary text
    sentinels ``"0"`` and ``"1"`` are unambiguous and normalized explicitly;
    any other non-bool value is dropped like an unconvertible value.
    """
    if value is None or declared not in (int, float, bool, str):
        return value
    if isinstance(value, bool):
        # Checked before int: bool IS an int subclass, so True would otherwise
        # satisfy the int branch and pass silently into a numeric column.
        return value if declared is bool else _coerce_fail(table, column, value, seen)
    if declared is bool:
        if isinstance(value, str) and value in ("0", "1"):
            return value == "1"
        return _coerce_fail(table, column, value, seen)
    if declared is str:
        return value if isinstance(value, str) else str(value)
    if isinstance(value, (int, float)) and declared is float:
        return float(value)
    if isinstance(value, int) and declared is int:
        return value
    try:
        # float() first even for an int column: "1.0" is what a float64 cell
        # stringifies to, and int("1.0") raises.
        number = float(value)
    except (TypeError, ValueError):
        return _coerce_fail(table, column, value, seen)
    if declared is int:
        return int(number)
    return number


def _coerce_fail(table: str, column: str, value: Any, seen: set) -> None:
    """Log once per (table, column) and blank the cell."""
    if (table, column) not in seen:
        seen.add((table, column))
        _LOG.warning(
            "recipe_search: %s.%s from the IDP parser is not the type "
            "contracts.py declares and could not be converted (e.g. %r, a %s) "
            "— those cells are blank. Record the real type in "
            "docs/datatables/recipe_idp.txt.",
            table, column, value, type(value).__name__,
        )
    return None


def _records(
    frame: pd.DataFrame, columns: dict[str, Any], table: str
) -> list[dict[str, Any]]:
    """DataFrame -> contract rows: documented columns only, in contract order.

    ``columns`` is a row TypedDict's ``__annotations__`` — names AND declared
    types, so this is the one place that guarantees what leaves the adapter
    matches what the frontend was told to expect. It also keeps the two
    ``img_meas2`` columns straight without a special case: a str in
    ``idp_image_info`` (a slot key) and an int in ``wafer_mp_info`` (P_No), so
    each table is coerced against its own contract.

    Restricting to the contract keeps the response shape stable when the
    parser gains a column, and filling an absent one with ``None`` keeps the
    screen up when it loses one. Both are logged, because either silently
    would look identical to correct data on screen — a missing column renders
    as an empty table cell, not as an error.
    """
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        _LOG.warning(
            "recipe_search: %s from the IDP parser is missing %s — those cells "
            "will be blank. Check docs/datatables/recipe_idp.txt against the "
            "parser's actual output.", table, missing,
        )
    extra = [column for column in frame.columns if column not in columns]
    if extra:
        _LOG.info(
            "recipe_search: %s from the IDP parser has undocumented columns %s "
            "(dropped). Worth adding to docs/datatables/recipe_idp.txt.",
            table, extra,
        )

    present = [column for column in columns if column in frame.columns]
    rows = frame[present].to_dict(orient="records") if present else []
    seen: set = set()
    return [
        {
            column: _coerce(_scalar(row.get(column)), declared, table, column, seen)
            for column, declared in columns.items()
        }
        for row in rows
    ]


def _to_detail_response(
    frames: dict[str, pd.DataFrame],
    recipe_id: str,
    fab_name: str,
    tool_category: str,
    location: _IdpLocation,
) -> RecipeDetailResponse:
    """Parser output -> ``RecipeDetailResponse``. Pure — no I/O, no office deps.

    Everything unreachable from home is upstream of this function, which is
    why it is separate: the mapping it performs is the part most likely to be
    wrong, and this way it is the part that can be tested anywhere.
    """
    idp_image_info: list[IdpImageInfoRow] = _records(
        frames["idp_image_info"],
        IdpImageInfoRow.__annotations__,
        "idp_image_info",
    )
    wafer_mp_info: list[WaferMpInfoRow] = _records(
        frames["wafer_mp_info"],
        WaferMpInfoRow.__annotations__,
        "wafer_mp_info",
    )
    wafer_align_info: list[WaferAlignInfoRow] = _records(
        frames["wafer_align_info"],
        WaferAlignInfoRow.__annotations__,
        "wafer_align_info",
    )

    # The MP table is filtered by Parameter against idp_image_info on screen
    # (RecipeOpenView.vue), so a mismatch renders as a silently empty table
    # rather than an error. Say so in the log instead.
    mp_parameters = {row["Parameter"] for row in wafer_mp_info if row["Parameter"]}
    idp_parameters = {row["Parameter"] for row in idp_image_info if row["Parameter"]}
    if mp_parameters and idp_parameters and not (mp_parameters & idp_parameters):
        _LOG.warning(
            "recipe_search: no Parameter value is shared between wafer_mp_info "
            "and idp_image_info for %r — the MP table will render empty. "
            "Compare the two sets for whitespace/case differences: %s vs %s",
            recipe_id, sorted(mp_parameters)[:3], sorted(idp_parameters)[:3],
        )

    return {
        "wafer_mp_info": wafer_mp_info,
        "wafer_align_info": wafer_align_info,
        "idp_image_info": idp_image_info,
        # Handed to the client so param-detail, align-detail and recipe-image
        # reach the raw folder without repeating the OpenSearch lookup or the
        # .idp download. Replaces the fabricated amp_info/align_images that used
        # to be assembled here by _sourceless_extras (deleted 2026-07-29 — the
        # deletion that function's own docstring asked for).
        "locator": {
            "eqp_ip": location.eqp_ip,
            "class_name": location.class_name,
            "idw": location.idw_stem,
            "idp": location.idp_stem,
        },
        "recipe_id": recipe_id,
        "fab_name": fab_name,
        "tool_category": tool_category,
        # Volatile, scrubbed by the parity harness (VOLATILE_KEYS) — office
        # does not have to match the mock byte-for-byte here.
        "timestamp": datetime.now().isoformat(),
    }


# ── raw-recipe folder: AMP, AF/PR and beam conditions ─────────────────────
#
# The folder beside the .idp (``data/{idw}/{idp}/``) holds the parameter
# settings the recipe-open screen used to fabricate. Naming lives in
# rawfiles.py, reading lives in office_utils.idp_amp_reader; only the wiring is
# here — which is why almost none of this needs a tool to be tested.


def _to_rows(obj: Any) -> list[SettingRow]:
    """Whatever a reader returned -> ordered key/value rows.

    The readers' return CONTAINER is OFFICE-VERIFY: a reader may hand back a
    dict, a one-row DataFrame whose columns are the fields, a two-column
    DataFrame whose rows are pairs, or a list of pairs. Handling all four means
    a wrong guess degrades to rows in a slightly odd order rather than a 500 on
    a screen that used to work.

    Their FIELD NAMES no longer are. All five readers were run against real
    files (office 확인 2026-07-30) and every key is written down in
    docs/datatables/recipe_idp.txt. Only ONE of the five forced a change here —
    ENMP's nested branch below — which is the open key/value contract paying for
    itself. The ambiguous 1x2 reading cannot reach any of them either way: the
    smallest real file carries three settings.

    Values are NOT all strings — ENMP mixes float and str inside one group — so
    every branch here stringifies rather than passing a value through.
    """
    if obj is None:
        return []
    if isinstance(obj, pd.DataFrame):
        if obj.empty:
            return []
        # ONE ROW is read as field-per-column, and this test comes FIRST because
        # a 1x2 frame satisfies both readings and the two disagree: as pairs it
        # yields one setting, as columns it yields two. A settings file with a
        # single setting is rarer than one with two, so columns win. If the
        # office turns out to emit 1x2 pair frames, this is the branch to flip
        # — and the OFFICE-VERIFY note in recipe_idp.txt is where to record it.
        if len(obj) == 1:
            first = obj.iloc[0]
            return [{"key": str(c), "value": str(first[c])} for c in obj.columns]
        if obj.shape[1] == 2:
            key_column, value_column = obj.columns[0], obj.columns[1]
            return [
                {"key": str(row[key_column]), "value": str(row[value_column])}
                for _, row in obj.iterrows()
            ]
        # Many rows AND many columns maps to no key/value reading at all. The
        # first row is the best guess; say so rather than silently dropping the
        # rest, because that is a shape nobody has predicted.
        _LOG.warning(
            "recipe_search: reader returned a %dx%d frame, which has no "
            "key/value reading — using row 0 and dropping %d row(s). Record the "
            "real shape in docs/datatables/recipe_idp.txt.",
            len(obj), obj.shape[1], len(obj) - 1,
        )
        first = obj.iloc[0]
        return [{"key": str(c), "value": str(first[c])} for c in obj.columns]
    if isinstance(obj, dict):
        # A dict OF DICTS is ENMP (read_af_pr_condition), the one reader that
        # groups its settings: eight groups covering the addressing and
        # measurement sequences (office 확인 2026-07-30). Each inner dict becomes
        # rows tagged with its group, so the screen shows the tool's own
        # structure. str()-ing the inner dict — what this did before — rendered
        # a whole group as one unreadable "{'a': 1, ...}" cell.
        #
        # Mixed is tolerated rather than rejected: a flat pair beside grouped
        # ones keeps its own row with no section, since dropping it would hide a
        # setting the office does send.
        if any(isinstance(v, dict) for v in obj.values()):
            rows: list[SettingRow] = []
            for section, value in obj.items():
                if isinstance(value, dict):
                    rows += [
                        {"key": str(k), "value": str(v), "section": str(section)}
                        for k, v in value.items()
                    ]
                else:
                    rows.append({"key": str(section), "value": str(value)})
            return rows
        return [{"key": str(k), "value": str(v)} for k, v in obj.items()]
    if isinstance(obj, (list, tuple)):
        return [
            {"key": str(pair[0]), "value": str(pair[1])}
            for pair in obj
            if isinstance(pair, (list, tuple)) and len(pair) >= 2
        ]
    _LOG.warning(
        "recipe_search: unrecognised reader return type %s — rendered empty. "
        "Add it to _to_rows and record it in docs/datatables/recipe_idp.txt.",
        type(obj).__name__,
    )
    return []


def _read_block(
    source_name: str | None,
    payload: bytes | None,
    reader: Any,
) -> SettingBlock | None:
    """Parse one raw file into a block. None when absent OR unparseable.

    A reader raising on a real file must not fail the whole parameter — the
    blocks beside it are still good, and a parameter legitimately missing one
    setting file is the common case rather than an error. The filename is
    logged so a bad file can be found without reproducing the click.
    """
    if source_name is None or payload is None:
        return None
    try:
        parsed = reader(payload)
    except Exception:
        _LOG.warning(
            "recipe_search: %s could not be parsed by %s — rendered as 파일 없음",
            source_name,
            getattr(reader, "__name__", reader),
            exc_info=True,
        )
        return None
    return {"source": source_name, "rows": _to_rows(parsed)}


def _locator_key(locator: IdpLocator) -> tuple[str, str, str, str]:
    return (
        locator["eqp_ip"], locator["class_name"], locator["idw"], locator["idp"]
    )


def _fetch_many(
    wanted: dict[tuple[str, str, str, str], list[str]],
) -> dict[tuple[str, str, str, str], dict[str, bytes]]:
    """Every raw file every locator needs, in ONE fleet download.

    ``FtpFleetDownloader.download`` takes a LIST of HostSpec and fans out
    concurrently across hosts, so a compare spanning 20 tools is one call rather
    than 20 sequential single-host sessions.

    A missing file is NOT an error: parameters routinely lack a third
    addressing image or an AF/PR setting. Failures are logged and are simply
    absent from the result — only the session itself failing raises. Results are
    keyed by (locator, file NAME) so callers need not re-derive a path.

    Two locators can share one host, and two hosts can hold the same path, so
    results are matched on BOTH — which is what ``report.grouped()`` returns
    (``{host: {remote_path: data}}``) and why it is used instead of flattening.
    """
    from back_dev_home.msr_image.config import load_config
    from back_dev_home.msr_image.paths import validate_tool_ip

    wanted = {key: names for key, names in wanted.items() if names}
    if not wanted:
        return {}

    config = load_config()
    tp = _transport()
    downloader_cls, host_spec_cls, transport = tp.downloader_cls, tp.host_spec_cls, tp.label

    # host -> {remote_path -> [(locator key, name), ...]}. A list because two
    # locators on one host CAN resolve to the same path (the same recipe opened
    # under two names), and both must receive the bytes.
    origin: dict[str, dict[str, list[tuple[tuple[str, str, str, str], str]]]] = {}
    files_for: dict[str, set[str]] = {}
    for key, names in wanted.items():
        eqp_ip, class_name, idw, idp = key
        # Unlike _download_idp, whose IP comes from OpenSearch, this one arrives
        # from the client — so the guard here is the SSRF gate, not a formality.
        validate_tool_ip(eqp_ip, config.allowed_subnets)
        raw = rawfiles.raw_dir(class_name, idw, idp)
        for name in dict.fromkeys(names):
            path = rawfiles.remote_path(raw, name)
            origin.setdefault(eqp_ip, {}).setdefault(path, []).append((key, name))
            files_for.setdefault(eqp_ip, set()).add(path)

    specs = [
        host_spec_cls(eqp_ip, files=sorted(paths))
        for eqp_ip, paths in files_for.items()
    ]
    report = _downloader(downloader_cls, config).download(specs)

    # ``HostFailure.remote_path is None`` means the failure happened BEFORE any
    # specific file — connect, login or listing — which is the tool being
    # unreachable, not a file being absent. That distinction is the whole 502:
    # counting "answered nothing" instead would report a healthy tool as down
    # whenever the only file a parameter asked for legitimately does not exist.
    unreachable = {f.host: f.error for f in report.failures if f.remote_path is None}
    if unreachable:
        raise SourceUnavailable(
            "raw-recipe folder unreachable on "
            + "; ".join(f"{host} ({error})" for host, error in sorted(unreachable.items()))
            + f" (transport: {transport})"
        )

    for failure in report.failures:
        _LOG.info(
            "recipe_search: %s absent via %s (%s) — rendered as 파일 없음",
            failure.remote_path, transport, failure.error,
        )

    out: dict[tuple[str, str, str, str], dict[str, bytes]] = {key: {} for key in wanted}
    for host, by_path in report.grouped().items():
        for path, data in by_path.items():
            for key, name in origin.get(host, {}).get(path, ()):
                out[key][name] = data
    return out


def _fetch_raw(locator: IdpLocator, names: list[str]) -> dict[str, bytes]:
    """One locator's files. Thin wrapper over ``_fetch_many``."""
    key = _locator_key(locator)
    return _fetch_many({key: names}).get(key, {})


def _list_raw_dirs(
    keys: set[tuple[str, str, str, str]],
) -> dict[tuple[str, str, str, str], list[str] | None]:
    """Each locator's raw-folder listing (basenames), or ``None`` if unlisted.

    The discovery step HV-SEM makes mandatory (user-confirmed 2026-08-08): a
    slot stem expands to stem-suffixed files (``IMMS0001-U.jpeg`` / -T / -M /
    -L, per targeting sub-position) that no derivation can predict, so the
    read plan has to start from what the folder actually holds. One
    ``list_dirs`` fleet call across hosts — a compare spanning N tools stays
    one extra round trip, mirroring ``_fetch_many``'s shape.

    A listing failure is SOFT on purpose: the caller falls back to the derived
    single ``{stem}.jpeg`` plan (the CD-SEM shape, and exactly the
    pre-discovery behavior), and a genuinely unreachable tool still surfaces
    as ``SourceUnavailable`` from the download step right after. Raising here
    would turn a degraded listing into a dead screen.
    """
    from back_dev_home.msr_image.config import load_config
    from back_dev_home.msr_image.paths import validate_tool_ip

    if not keys:
        return {}

    config = load_config()
    tp = _transport()
    downloader_cls, host_spec_cls = tp.downloader_cls, tp.host_spec_cls
    list_dir_cls, transport = tp.list_dir_cls, tp.label

    dirs_for: dict[str, set[str]] = {}
    for eqp_ip, class_name, idw, idp in keys:
        # Same SSRF gate as _fetch_many: the IP arrives from the client.
        validate_tool_ip(eqp_ip, config.allowed_subnets)
        dirs_for.setdefault(eqp_ip, set()).add(rawfiles.raw_dir(class_name, idw, idp))

    specs = [
        host_spec_cls(eqp_ip, listings=[list_dir_cls(d) for d in sorted(dirs)])
        for eqp_ip, dirs in dirs_for.items()
    ]
    try:
        report = _downloader(downloader_cls, config).list_dirs(specs)
    except Exception as exc:  # noqa: BLE001 — degrade to the derived-name plan
        _LOG.warning("recipe_search: raw-folder listing failed via %s (%s)", transport, exc)
        return dict.fromkeys(keys)

    failed_hosts = {f.host for f in report.failures}
    for failure in report.failures:
        _LOG.info(
            "recipe_search: listing failed on %s (%s) — planning with derived names",
            failure.host, failure.error,
        )

    # HostListing merges every listed dir of one host into a single path list,
    # so paths are attributed back to a locator by its raw-dir prefix. NLST
    # output is normalized to full paths (same as msr_image's list_images);
    # the nested-path guard keeps a subfolder's files (e.g. the hidden
    # .{name}/cond.txt sidecar dirs) out of the image plan.
    paths_by_host = report.grouped()
    out: dict[tuple[str, str, str, str], list[str] | None] = {}
    for key in keys:
        eqp_ip, class_name, idw, idp = key
        if eqp_ip not in paths_by_host and eqp_ip in failed_hosts:
            out[key] = None
            continue
        prefix = rawfiles.raw_dir(class_name, idw, idp) + "/"
        out[key] = [
            path[len(prefix):]
            for path in paths_by_host.get(eqp_ip, [])
            if path.startswith(prefix) and "/" not in path[len(prefix):]
        ]
    return out


def get_param_detail(
    items: list[ParamDetailRequestItem],
) -> list[ParamDetailResponse]:
    """Settings and image names for each requested (recipe, parameter).

    Grouped by locator so a compare across N recipes on ONE tool opens one FTP
    session carrying every file, rather than N sessions of five files each.
    The raw folders are LISTED first (one fleet call) so HV-SEM's suffixed
    image files are discovered rather than guessed — see ``_list_raw_dirs``.
    """
    from office_utils.idp_amp_reader import (
        read_af_pr_condition,
        read_amp_info,
        read_meas_image_condition,
    )

    stage_of = {slot["key"]: slot["stage"] for slot in IMAGE_SLOTS}

    listings = _list_raw_dirs({_locator_key(item["locator"]) for item in items})

    wanted: dict[tuple[str, str, str, str], list[str]] = {}
    plans: list[tuple[tuple[str, str, str, str], ParamDetailRequestItem, Any]] = []
    for item in items:
        key = _locator_key(item["locator"])
        plan = rawfiles.slot_sources(item.get("slots") or {}, listing=listings.get(key))
        amp, af_pr, images = plan
        # Settings only. The images' BYTES are deliberately NOT fetched here:
        # this response carries their filenames, and the browser pulls each one
        # through recipe-image when it actually renders. Fetching them would
        # double the tool round-trips for bytes this function then discards.
        names = [name for name in (amp, af_pr) if name]
        names += [cond for _, _, cond in images]
        wanted.setdefault(key, []).extend(names)
        plans.append((key, item, plan))

    fetched = _fetch_many(wanted)

    out: list[ParamDetailResponse] = []
    for key, item, (amp, af_pr, images) in plans:
        blob = fetched.get(key, {})
        out.append({
            "parameter": item.get("parameter", ""),
            "amp": _read_block(amp, blob.get(amp or ""), read_amp_info),
            "af_pr": _read_block(af_pr, blob.get(af_pr or ""), read_af_pr_condition),
            "images": [
                {
                    "slot": slot,
                    "stage": stage_of.get(slot, slot),
                    "name": name,
                    "cond": _read_block(
                        cond, blob.get(cond), read_meas_image_condition
                    ),
                }
                for slot, name, cond in images
            ],
        })
    return out


def _split_align_settings(
    parsed: Any,
    names: list[str],
    optics: dict[str, str | None] | None = None,
) -> dict[str, SettingBlock]:
    """``get_align_beam_pr_conditions``'s ONE return value -> a block per ENAP.

    IT KEYS BY OPTIC (office 확인 2026-07-30): ``{"OM": {...}, "SEM": {...}}``.
    That settles the question this function was built to hedge — the result CAN
    be split per align point, because P.No 1 is OM and P.No 2 is SEM. The optic
    branch therefore comes first and is the only one expected to fire.

    The older guesses are kept below rather than deleted. They cost nothing, and
    a reader that turns out to vary by tool generation would otherwise fall
    straight to the un-splittable path:

    * a sequence parallel to the input — the adapter passes bytes, so the office
      function never learns the ENAP filenames and could only key positionally;
    * a mapping that keys by filename — possible only if it derives names from
      the content;
    * anything else — treated as ONE value describing the whole align set and
      attached to every point, with the type logged. Splitting it by guessing
      would put one point's optics under another point's heading.
    """
    if isinstance(parsed, dict) and optics:
        # Case-folded because "OM"/"SEM" is a label we pass IN as `which` for the
        # sibling reader; nothing guarantees this one echoes the same casing.
        by_optic = {str(key).strip().upper(): value for key, value in parsed.items()}
        matched = {
            name: {"source": name, "rows": _to_rows(by_optic[optic.upper()])}
            for name, optic in optics.items()
            if name in names and optic and optic.upper() in by_optic
        }
        if matched:
            missing = [name for name in names if name not in matched]
            if missing:
                # Not an error: a P.No outside 1/2 has no optic to look up, and
                # the point renders 파일 없음 exactly as its image condition does.
                _LOG.info(
                    "recipe_search: get_align_beam_pr_conditions returned optics "
                    "%s, which do not cover %s",
                    sorted(by_optic), ", ".join(missing),
                )
            return matched
    if isinstance(parsed, (list, tuple)) and len(parsed) == len(names):
        return {
            name: {"source": name, "rows": _to_rows(value)}
            for name, value in zip(names, parsed, strict=True)
        }
    if isinstance(parsed, dict) and set(names) <= set(map(str, parsed)):
        return {
            name: {"source": name, "rows": _to_rows(parsed[name])}
            for name in names
        }
    _LOG.warning(
        "recipe_search: get_align_beam_pr_conditions returned %s for %d file(s) "
        "(%s) — could not be split per align point, so every point shows the "
        "whole result. Record the real shape in docs/datatables/recipe_idp.txt.",
        type(parsed).__name__, len(names), ", ".join(names),
    )
    shared: SettingBlock = {"source": ", ".join(names), "rows": _to_rows(parsed)}
    return dict.fromkeys(names, shared)


def _align_settings(
    names: list[str],
    blob: dict[str, bytes],
    optics: dict[str, str | None] | None = None,
) -> dict[str, SettingBlock]:
    """Every align point's ENAP condition, in ONE reader call.

    ``get_align_beam_pr_conditions`` takes the whole ENAP list rather than one
    file (user-confirmed 2026-07-29), so this is called once per recipe. Absent
    files are dropped BEFORE the call — a recipe with only point 1 must not send
    a hole the reader would have to interpret.

    ``optics`` maps each ENAP name to "OM" or "SEM", which is how the return
    value is keyed (office 확인 2026-07-30). Passed in rather than re-derived
    here so one function owns the P.No -> optic rule: ``rawfiles.align_optics``.
    """
    from office_utils.idp_amp_reader import get_align_beam_pr_conditions

    present = [name for name in names if blob.get(name) is not None]
    if not present:
        return {}
    try:
        parsed = get_align_beam_pr_conditions([blob[name] for name in present])
    except Exception:
        # One unreadable ENAP file must not cost the align popup its images and
        # beam conditions, the same way _read_block absorbs a per-file failure.
        _LOG.warning(
            "recipe_search: get_align_beam_pr_conditions failed for %s — align "
            "settings rendered as 파일 없음",
            ", ".join(present), exc_info=True,
        )
        return {}
    return _split_align_settings(parsed, present, optics)


def get_align_detail(
    locator: IdpLocator,
    p_numbers: list[int],
) -> AlignDetailResponse:
    """Wafer-align image, beam condition and AF/PR setting per align point.

    Align files go to align-SPECIFIC readers, not the parameter-side lookalikes
    (user-confirmed 2026-07-29): the ENAP settings to
    ``get_align_beam_pr_conditions`` for the whole list at once, and the image's
    cond.txt to ``read_align_image_condition``, which must be told which optic
    took the image. Until 2026-07-29 this function called
    ``read_af_pr_condition`` and ``read_meas_image_condition`` instead — the
    wrong parsers, on files that would still have downloaded and still have
    rendered, which is why nothing here failed loudly.
    """
    from functools import partial

    from office_utils.idp_amp_reader import read_align_image_condition

    plan = [
        (p_no, image, setting, rawfiles.cond_source(image))
        for p_no in sorted({int(p) for p in p_numbers})
        for image, setting in [rawfiles.align_names(p_no)]
    ]
    # The align IMAGE itself is not fetched — the response carries its name and
    # the browser pulls it through recipe-image only for the points it renders.
    names = [name for _, _, setting, cond in plan for name in (setting, cond)]

    blob = _fetch_raw(locator, names)
    # The reader keys its return by optic, so it needs the same P.No -> optic
    # rule the image condition uses. Derived once, here, and handed to both.
    optic_of = {setting: rawfiles.align_optics(p_no) for p_no, _, setting, _ in plan}
    settings = _align_settings(
        [setting for _, _, setting, _ in plan], blob, optic_of,
    )

    points: list[AlignPoint] = []
    for p_no, image, setting, cond in plan:
        optics = rawfiles.align_optics(p_no)
        if optics is None and blob.get(cond) is not None:
            # The file is right there and still not read, so say why: the office
            # has only ever described points 1 and 2, and read_align_image_condition
            # cannot be called without knowing which of the two this is.
            _LOG.warning(
                "recipe_search: align point P.No=%s is neither 1 (OM) nor 2 (SEM); "
                "%s downloaded but not parsed, since the optic it was taken with "
                "is unknown. Record P.No=%s in docs/datatables/recipe_idp.txt.",
                p_no, cond, p_no,
            )
        points.append({
            "P_No": p_no,
            "image": image,
            "cond": _read_block(
                cond,
                blob.get(cond),
                partial(read_align_image_condition, which=optics),
            ) if optics else None,
            "setting": settings.get(setting),
        })
    return {"points": points}


def fetch_recipe_image(locator: IdpLocator, name: str) -> tuple[bytes, str]:
    """One raw-recipe image's bytes and content type.

    Raises:
        LookupError: absent on the tool — the route turns this into a 404.
    """
    from back_dev_home.msr_image.providers.office_example import _content_type

    fetched = _fetch_raw(locator, [name])
    if name not in fetched:
        raise LookupError(f"{name} not found under the raw-recipe folder")
    # msr_image's mapping, not a local one: it already knows tools serve TIFF
    # originals alongside JPEG previews (office 확인 2026-07-24), which a
    # .jpeg-only check would hand back as undownloadable octet-stream.
    return fetched[name], _content_type(name)


def get_recipe_open_data(
    recipe_id: str | None = None,
    fab_name: str | None = None,
    tool_category: str | None = None,
) -> RecipeDetailResponse:
    """One recipe's IDP tables: locate -> download -> parse -> map.

    Locate prefers the Redis recipe registry and falls back to measurement
    history; either way it yields tool candidates in preference order and the
    download walks them until one answers.

    The .idp never touches the Flask host's disk — it is fetched, parsed and
    dropped. Nothing is cached either: a recipe's .idp is small, and with the
    registry path the lookup is two Redis reads rather than an OpenSearch query.
    If 열어보기 latency ever becomes a complaint this is still the seam to put a
    TTL cache behind (keyed on the recipe triple).
    """
    recipe = (recipe_id or "").strip()
    if not recipe:
        raise ValueError("recipe_id is required for recipe open.")
    tool_type: ToolType = tool_category or "cd-sem"
    fab_name = (fab_name or "").strip() or None

    locations = _locate_idp(tool_type, recipe, fab_name)
    data, location = _download_first(locations)
    frames = _parse_idp(data, f"{location.idp_stem}.idp")

    return _to_detail_response(frames, recipe, fab_name or "", tool_type, location)


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.ebeam.recipe_search.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    for tool in ("cd-sem", "hv-sem"):
        catalog = get_recipe_catalog(tool, ("R3",))
        print(f"{tool}: {catalog['total']} recipes for R3")
        if catalog["rows"]:
            first = catalog["rows"][0]
            print("  first:", first)
            detail = get_recipe_open_data(first["recipe_name"], "R3", tool)
            for table in _PARSED_TABLES:
                print(f"  {table}: {len(detail[table])} rows")
