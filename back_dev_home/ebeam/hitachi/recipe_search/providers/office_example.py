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
server, via one meas_hist document::

    meas_hist_{cdsem,hvsem}                       (OpenSearch)
      ├── eqp_ip      ─────────────────────────►  FTP host
      ├── class_name  ──┐
      ├── idw_name    ──┼───────────────────────►  /HITACHI/DEVICE/HD/{class}/data/{idw}
      └── idp_name    ──┘                              └── {idp}.idp
                                                            │
        office_utils.read_idp_info.combined_idp_info(path) ◄─┘
          -> {"wafer_mp_info": df, "wafer_align_info": df, "idp_image_info": df}

``eqp_ip`` riding on the measurement document is what makes this one query
instead of two: unlike lateral check (which resolves ``eqp_id -> eqp_ip``
through sem_list), the measurement row already names the tool that ran the
recipe, so the host it must be readable from is the host we just proved ran it.

Column names *and dtypes* are the contract, not a convenience — see
``docs/datatables/recipe_idp.txt``, which is the schema of record for all three
tables and for this module's three known traps: ``wafer_align_info`` uses
dot-columns (``Chip.X``, ``P.No``); ``img_meas2`` means different things in
``wafer_mp_info`` (P_No's integer) and ``idp_image_info`` (a filename); and
``idp_image_info``'s ``Addressing``, ``Mother_Para`` and ``dnumber_removed``
are ``bool`` (office 확인 2026-07-28) — until then they were documented as a
``"Yes"``/``"No"`` string, a parameter name and an int64 count, and the screen
was built on all three guesses. ``_scalar`` below turns the parser's
``numpy.bool_`` into a Python ``bool``, so no coercion belongs here: if the
parser's shape ever changes, it should break loudly rather than be normalised
into plausible-looking wrong data.

WRITING THIS AT HOME: ``office_utils`` exists only on office machines, so a
gitignored stand-in of the same name sits at the repo root matching its
signature, keys, columns and dtypes. That makes everything below the parse
runnable here; only ``_locate_idp`` (OpenSearch) and ``_download_idp`` (FTP)
are genuinely unreachable. They are separate functions from
``_to_detail_response`` for exactly that reason — the mapping is covered by a
tracked test that needs neither.

STILL NOT WIRED:

* ``get_recipe_compare_data`` — re-exported from the mock below. Compare may
  request up to 200 recipes, and the honest office implementation is one FTP
  session per distinct tool with all of that tool's .idp files batched into a
  single ``HostSpec(files=[...])``. Until that exists, compare returns mock
  data while ``/recipe-detail`` returns real data, so **the "compare is derived
  from open" invariant is knowingly broken office-side.** See the TODO there.
* ``align_images`` and ``amp_info`` — not among the parser's three keys, so
  still fabricated even at the office. Isolated in ``_sourceless_extras``.

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
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from platform import system
from typing import Any, NamedTuple

import pandas as pd

from back_dev_home._runtime.office_redis import redis_client as _redis_client
from back_dev_home.ebeam.hitachi._office_search import fetch_hits, query
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    IdpImageInfoRow,
    RecipeDetailResponse,
    RecipeSearchResponse,
    RecipeSearchRow,
    ToolType,
    WaferAlignInfoRow,
    WaferMpInfoRow,
)
# TODO(office): replace with a batched IDP-backed implementation — one FTP
# session per distinct eqp_ip, every recipe's .idp in one HostSpec(files=[...]).
# Re-exported (not reimplemented) so that when it lands it can stay derived
# from open, the invariant the mock guarantees.
from back_dev_home.ebeam.hitachi.recipe_search.providers.mock import (
    generate_amp_info,
    generate_wafer_align_images,
    get_recipe_compare_data,
)


__all__ = [
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


def _unique(names: list[RecipeSearchRow]) -> list[RecipeSearchRow]:
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


def _recipes_for_fab(client, key: str, fab_name: str) -> list[RecipeSearchRow]:
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
    """Every fab's recipe names, de-duped in first-seen order.

    Reached only when the caller omits ``fab_name``; the frontend always
    sends one, so this is the blank-query edge case.
    """
    entries = client.hgetall(key)
    if not entries:
        raise _missing_key_error(key)
    names: list[RecipeSearchRow] = []
    for value in entries.values():
        names.extend(_parse_str_list(value))
    return _unique(names)


def get_recipe_catalog(
    tool_type: ToolType,
    fab_name: str | None = None,
) -> RecipeSearchResponse:
    key = _RECIPE_HASH.get(tool_type)
    if key is None:
        raise ValueError(
            f"Unknown tool_type {tool_type!r}; expected one of {sorted(_RECIPE_HASH)}"
        )

    client = _redis_client()
    rows = (
        _recipes_for_fab(client, key, fab_name)
        if fab_name
        else _all_recipes(client, key)
    )
    return {
        "tool_type": tool_type,
        "fab_name": fab_name,
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


def _locate_idp(
    tool_type: ToolType,
    recipe_id: str,
    fab_name: str | None,
) -> _IdpLocation:
    """Find the tool and path that hold this recipe's .idp file.

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
            "has no .idp location to derive — recipe open needs one run."
        )

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
            return location
        incomplete.append(f"{hit.get('timestamp')}: missing {', '.join(missing)}")

    raise LookupError(
        f"Found {len(hits)} document(s) in {index} for full_name={recipe_id!r}, "
        "but none carries every field the FTP path needs — "
        + " | ".join(incomplete)
    )


def _idp_remote_path(location: _IdpLocation) -> str:
    """The .idp file's absolute path on that tool's FTP server. Pure."""
    return (
        f"{_FTP_ROOT}/{location.class_name}/data/"
        f"{location.idw_stem}/{location.idp_stem}.idp"
    )


# ── recipe open, step 2: fetch it (FTP) ───────────────────────────────────


def _transport():
    """(FtpFleetDownloader, HostSpec, label) for this host.

    The office Windows PC has no direct FTP egress to the tools and must go
    through the fileloader HTTP proxy; the cloud Linux host reaches them
    directly. Identical split to msr_image, so behaviour verified there
    transfers here unchanged.
    """
    if system() == "Windows":
        from ftp_handler.proxy import FtpFleetDownloader, HostSpec
        return FtpFleetDownloader, HostSpec, "proxy (Windows)"
    from ftp_handler.direct_downloader import FtpFleetDownloader, HostSpec
    return FtpFleetDownloader, HostSpec, "direct"


def _download_idp(location: _IdpLocation, dest_dir: Path) -> Path:
    """RETR the .idp to ``dest_dir`` and return the local path.

    The parser reads a file, so the bytes have to land on disk before it is
    called — this returns a path rather than bytes to keep that ordering
    explicit at the call site.

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
    downloader_cls, host_spec_cls, transport = _transport()
    downloader = downloader_cls(
        user=config.ftp_user,
        password=config.ftp_password,
        port=config.ftp_port,
        connect_timeout=config.ftp_timeout,
    )
    report = downloader.download([host_spec_cls(location.eqp_ip, files=[remote_path])])

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

    local_path = dest_dir / f"{location.idp_stem}.idp"
    local_path.write_bytes(fetched[remote_path])
    _LOG.info(
        "recipe_search: fetched %s (%d bytes) from %s via %s",
        remote_path, len(fetched[remote_path]), location.eqp_ip, transport,
    )
    return local_path


# ── recipe open, step 3: parse it (office_utils) ──────────────────────────


_PARSED_TABLES = ("wafer_mp_info", "wafer_align_info", "idp_image_info")


def _parse_idp(local_path: Path) -> dict[str, pd.DataFrame]:
    """Run the 사내 IDP parser over a downloaded file.

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

    frames = combined_idp_info(local_path)
    missing = [name for name in _PARSED_TABLES if name not in frames]
    if missing:
        raise LookupError(
            f"combined_idp_info({local_path.name}) returned keys "
            f"{sorted(frames)} — missing {missing}. "
            "docs/datatables/recipe_idp.txt is the schema of record."
        )
    return frames


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


def _records(frame: pd.DataFrame, columns: list[str], table: str) -> list[dict[str, Any]]:
    """DataFrame -> contract rows: documented columns only, in contract order.

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
    return [{column: _scalar(row.get(column)) for column in columns} for row in rows]


def _sourceless_extras(
    idp_image_info: list[IdpImageInfoRow],
    recipe_id: str,
    fac_id: str,
    tool_category: str,
) -> dict[str, Any]:
    """``align_images`` and ``amp_info`` — FABRICATED, even at the office.

    Neither is among ``combined_idp_info``'s three keys. The screen already
    draws both, so they are generated rather than dropped, and this function
    exists to keep exactly one place to delete when a source turns up. The
    candidate is the raw-recipe folder beside the .idp
    (``data/{idw}/{idp}/``), which a second 사내 parser is expected to read.

    AMP is at least keyed off the REAL parameter names — it derives from the
    parsed ``idp_image_info`` — so its parameter column is not fiction even
    though its optical values are.
    """
    import random

    seed_rng = random.Random(hash((recipe_id, fac_id, tool_category)) & 0xFFFFFFFF)
    return {
        "align_images": generate_wafer_align_images(rng=seed_rng),
        "amp_info": generate_amp_info(idp_image_info),
    }


def _to_detail_response(
    frames: dict[str, pd.DataFrame],
    recipe_id: str,
    fac_id: str,
    tool_category: str,
) -> RecipeDetailResponse:
    """Parser output -> ``RecipeDetailResponse``. Pure — no I/O, no office deps.

    Everything unreachable from home is upstream of this function, which is
    why it is separate: the mapping it performs is the part most likely to be
    wrong, and this way it is the part that can be tested anywhere.
    """
    idp_image_info: list[IdpImageInfoRow] = _records(
        frames["idp_image_info"],
        list(IdpImageInfoRow.__annotations__),
        "idp_image_info",
    )
    wafer_mp_info: list[WaferMpInfoRow] = _records(
        frames["wafer_mp_info"],
        list(WaferMpInfoRow.__annotations__),
        "wafer_mp_info",
    )
    wafer_align_info: list[WaferAlignInfoRow] = _records(
        frames["wafer_align_info"],
        list(WaferAlignInfoRow.__annotations__),
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
        **_sourceless_extras(idp_image_info, recipe_id, fac_id, tool_category),
        "recipe_id": recipe_id,
        "fac_id": fac_id,
        "tool_category": tool_category,
        # Volatile, scrubbed by the parity harness (VOLATILE_KEYS) — office
        # does not have to match the mock byte-for-byte here.
        "timestamp": datetime.now().isoformat(),
    }


def get_recipe_open_data(
    recipe_id: str | None = None,
    fac_id: str | None = None,
    tool_category: str | None = None,
) -> RecipeDetailResponse:
    """One recipe's IDP tables: locate -> download -> parse -> map.

    The download lands in a temp directory that is removed on the way out.
    Nothing is cached: a recipe's .idp is small and the OpenSearch lookup
    dominates, but if 열어보기 latency becomes a complaint this is the seam to
    put a TTL cache behind (keyed on the recipe triple, not on the path).
    """
    recipe = (recipe_id or "").strip()
    if not recipe:
        raise ValueError("recipe_id is required for recipe open.")
    tool_type: ToolType = tool_category or "cd-sem"
    fab_name = (fac_id or "").strip() or None

    location = _locate_idp(tool_type, recipe, fab_name)
    with tempfile.TemporaryDirectory(prefix="skewnono-idp-") as tmp_dir:
        local_path = _download_idp(location, Path(tmp_dir))
        frames = _parse_idp(local_path)

    return _to_detail_response(frames, recipe, fab_name or "", tool_type)


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.ebeam.hitachi.recipe_search.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    for tool in ("cd-sem", "hv-sem"):
        catalog = get_recipe_catalog(tool, "R3")
        print(f"{tool}: {catalog['total']} recipes for R3")
        if catalog["rows"]:
            first = catalog["rows"][0]
            print("  first:", first)
            detail = get_recipe_open_data(first, "R3", tool)
            for table in _PARSED_TABLES:
                print(f"  {table}: {len(detail[table])} rows")
