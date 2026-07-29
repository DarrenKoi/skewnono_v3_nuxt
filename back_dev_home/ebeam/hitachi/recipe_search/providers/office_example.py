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
      └─►  office_utils.idp_amp_reader.{read_amp_info,
             read_af_pr_condition, read_meas_image_condition}(path|bytes|str)

Naming lives in ``rawfiles.py`` (pure, fully tested at home); the wiring is
``get_param_detail`` / ``get_align_detail`` / ``fetch_recipe_image`` below.
``"non"`` — French, not ``"none"`` — means the slot has no file, and a missing
file is normal rather than an error.

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
from back_dev_home.ebeam.hitachi.recipe_search import rawfiles
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    AlignDetailResponse,
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
# TODO(office): replace with a batched IDP-backed implementation — one FTP
# session per distinct eqp_ip, every recipe's .idp in one HostSpec(files=[...]).
# Re-exported (not reimplemented) so that when it lands it can stay derived
# from open, the invariant the mock guarantees.
from back_dev_home.ebeam.hitachi.recipe_search.providers.mock import (
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


# ── catalog (Redis) ───────────────────────────────────────────────────────


def _parse_recipe_list(value) -> list[RecipeSearchRow]:
    """Hash value -> list of recipe names, tolerant of JSON / repr / CSV.

    The writer stores a Python list; whether that lands in Redis as JSON
    (``["a", "b"]``) or a ``repr`` (``['a', 'b']``) depends on the job, and
    both parse here. The CSV fallback covers a plain comma-joined string —
    recipe names carry ``/`` and ``_`` but no commas, so that split is safe
    as a last resort.
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
        return _unique(_parse_recipe_list(raw))
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
        names.extend(_parse_recipe_list(value))
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


def _to_detail_response(
    frames: dict[str, pd.DataFrame],
    recipe_id: str,
    fac_id: str,
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
        "fac_id": fac_id,
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

    The readers' return CONTAINER is OFFICE-VERIFY, not merely their field
    names: a reader may hand back a dict, a one-row DataFrame whose columns are
    the fields, a two-column DataFrame whose rows are pairs, or a list of pairs.
    Handling all four means a wrong guess degrades to rows in a slightly odd
    order rather than a 500 on a screen that used to work.
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
    """
    from back_dev_home.msr_image.config import load_config
    from back_dev_home.msr_image.paths import validate_tool_ip

    wanted = {key: names for key, names in wanted.items() if names}
    if not wanted:
        return {}

    config = load_config()
    downloader_cls, host_spec_cls, transport = _transport()

    specs = []
    # (host, remote_path) -> (locator key, name). The path alone is ambiguous:
    # two tools can hold the same recipe at the same path.
    origin: dict[tuple[str, str], tuple[tuple[str, str, str, str], str]] = {}
    for key, names in wanted.items():
        eqp_ip, class_name, idw, idp = key
        # Unlike _download_idp, whose IP comes from OpenSearch, this one arrives
        # from the client — so the guard here is the SSRF gate, not a formality.
        validate_tool_ip(eqp_ip, config.allowed_subnets)
        raw = rawfiles.raw_dir(class_name, idw, idp)
        paths = []
        for name in dict.fromkeys(names):
            path = rawfiles.remote_path(raw, name)
            origin[(eqp_ip, path)] = (key, name)
            paths.append(path)
        specs.append(host_spec_cls(eqp_ip, files=sorted(paths)))

    report = _downloader(downloader_cls, config).download(specs)
    for failure in report.failures:
        _LOG.info(
            "recipe_search: %s absent via %s (%s) — rendered as 파일 없음",
            failure.remote_path, transport, failure.error,
        )

    out: dict[tuple[str, str, str, str], dict[str, bytes]] = {key: {} for key in wanted}
    for result in report.files:
        found = origin.get((getattr(result, "host", ""), result.remote_path))
        if found is None:
            # Single-host reports may omit `host`; fall back to path alone,
            # which is unambiguous whenever only one locator asked for it.
            matches = [v for (_, path), v in origin.items() if path == result.remote_path]
            if len(matches) != 1:
                continue
            found = matches[0]
        key, name = found
        out[key][name] = result.data
    return out


def _fetch_raw(locator: IdpLocator, names: list[str]) -> dict[str, bytes]:
    """One locator's files. Thin wrapper over ``_fetch_many``."""
    key = _locator_key(locator)
    return _fetch_many({key: names}).get(key, {})


def get_param_detail(
    items: list[ParamDetailRequestItem],
) -> list[ParamDetailResponse]:
    """Settings and image names for each requested (recipe, parameter).

    Grouped by locator so a compare across N recipes on ONE tool opens one FTP
    session carrying every file, rather than N sessions of five files each.
    """
    from office_utils.idp_amp_reader import (
        read_af_pr_condition,
        read_amp_info,
        read_meas_image_condition,
    )

    stage_of = {slot["key"]: slot["stage"] for slot in IMAGE_SLOTS}

    wanted: dict[tuple[str, str, str, str], list[str]] = {}
    plans: list[tuple[tuple[str, str, str, str], ParamDetailRequestItem, Any]] = []
    for item in items:
        key = _locator_key(item["locator"])
        plan = rawfiles.slot_sources(item.get("slots") or {})
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


def get_align_detail(
    locator: IdpLocator,
    p_numbers: list[int],
) -> AlignDetailResponse:
    """Wafer-align image, beam condition and AF/PR setting per align point."""
    from office_utils.idp_amp_reader import (
        read_af_pr_condition,
        read_meas_image_condition,
    )

    plan = [
        (p_no, image, setting, rawfiles.cond_source(image))
        for p_no in sorted({int(p) for p in p_numbers})
        for image, setting in [rawfiles.align_names(p_no)]
    ]
    # The align IMAGE itself is not fetched — the response carries its name and
    # the browser pulls it through recipe-image only for the points it renders.
    names = [name for _, _, setting, cond in plan for name in (setting, cond)]

    blob = _fetch_raw(locator, names)
    return {
        "points": [
            {
                "P_No": p_no,
                "image": image,
                "cond": _read_block(cond, blob.get(cond), read_meas_image_condition),
                "setting": _read_block(
                    setting, blob.get(setting), read_af_pr_condition
                ),
            }
            for p_no, image, setting, cond in plan
        ]
    }


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

    return _to_detail_response(frames, recipe, fab_name or "", tool_type, location)


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
