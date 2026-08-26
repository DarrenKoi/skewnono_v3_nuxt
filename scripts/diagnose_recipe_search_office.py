"""Diagnose a 502 from recipe-search → 자세히 보기 (``/recipe-detail``).

That endpoint answers 502 when the adapter cannot work out WHERE a recipe's
``.idp`` file lives. The location has two independent sources and the endpoint
tries them in order, so a 502 means both declined::

    1. Redis recipe registry   v3_{family}_rcp_loc_{fab}      [idw, idp]
                               v3_{family}_tools_in_rcp_{fab} [eqp_id, ...]
                                 └─ eqp_id -> eqp_ip through the sem_list roster
    2. meas_hist_{family}      (OpenSearch)  the recipe's most recent runs

The message the browser shows names source 2 ("No document in meas_hist_cdsem
has full_name=..."), which is the expected state for any recipe that has never
been measured - source 1 exists precisely to serve those. So the useful
question is almost never "why is meas_hist empty" but "why did the registry
decline", and this script walks every step of both sources until one of them
produces an answer or all of them have been ruled out.

It diagnoses the DEPLOYED adapter, not the template: it imports
``providers/office.py`` when that file exists, because that is the code
actually serving requests. A copy left behind by an older ``git pull`` has no
registry path at all - stage 0 catches that outright, since no amount of
correct Redis data helps an adapter that never reads it.

The flow this script replays is the one ``get_recipe_open_data`` runs, one
stage per step, printing what each step READ and what it DERIVED from it::

    0. providers/office.py             which adapter is deployed
    1. Redis   INFO keyspace + SCAN    which logical DB the client is on (db 0,
                                       there is no REDIS_DB knob) and which
                                       v3_{family}_* keys that DB holds - a
                                       registry loaded into db1 reads as
                                       "key absent" from db0, not as an error
    2. Redis   HGET x3                 v3_{family}_unique_rcp_list    [fab]    -> names
                                       v3_{family}_rcp_loc_{fab}      [recipe] -> [idw, idp]
                                       v3_{family}_tools_in_rcp_{fab} [recipe] -> [eqp_id, ...]
    3. Redis   v3_df_sem_avail         eqp_id -> eqp_ip  (FTP dials an IP)
    4. OpenSearch meas_hist_{family}   the fallback when stage 2 declines
    5. verdict                         /HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}.idp
                                       per candidate tool, in download order
    6. FTP     RETR                    --fetch: download, parse from bytes
    7. FTP     raw folder              --fetch: the five raw readers

Run FROM THE REPO ROOT at the office (reads REDIS_* / OPENSEARCH_* from
back_dev_home/.env the same way the adapter does)::

    .venv/bin/python -m scripts.diagnose_recipe_search_office "1/AC_M2_TAT"
    .venv/bin/python -m scripts.diagnose_recipe_search_office "ADI/X" --fab M14A
    .venv/bin/python -m scripts.diagnose_recipe_search_office "ADI/X" --tool hvsem

Stages 1-5 write nothing and open no FTP session: they are read-only against
Redis and OpenSearch, and locating the file is the step that 502s.

``--fetch`` adds stages 6-7, which go past locating into the office_utils
surface itself - download the ``.idp``, parse it FROM BYTES, and run one
parameter's slots through the five raw readers::

    .venv/bin/python -m scripts.diagnose_recipe_search_office "1/AC_M2_TAT" --fetch
    ... --fetch --parameter CD_MEAS_01     # a specific parameter, not the first

Those two are opt-in because they dial the measuring tool. They exist for the
2026-08-05 change: the adapter stopped writing the ``.idp`` to a temp file on
the strength of ``combined_idp_info`` accepting bytes - user-confirmed, but
never executed at the office and untestable from home. Stage 6 parses the same
bytes both ways and reports whether they agree, so the claim is checked by a
command instead of by a user hitting a 502. If it turns out to be wrong,
``SKEWNONO_RECIPE_IDP_VIA_TEMPFILE=1`` in ``back_dev_home/.env`` restores the
old behaviour without an edit.

Still nothing writes to the tool, and with the hatch off nothing writes to the
Flask host either.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import os
import sys
from pathlib import Path
from types import ModuleType

import redis

# Make `back_dev_home` importable however this file was started. `-m` puts the
# working directory on sys.path and works from the repo root; running the file
# by path puts scripts/ there instead and fails on the first import below. Both
# forms get typed -- a file manager, an IDE "run this file" button and tab
# completion all produce the by-path one -- so support both.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Importing the package applies its stdout UTF-8 fix. `-m` gets it for free
# because -m imports the package first; running this file by path does not,
# and would then die on the ANSI code page. One line covers both.
import scripts  # noqa: E402,F401

from back_dev_home._runtime import office_template  # noqa: E402
from back_dev_home._runtime.office_redis import (  # noqa: E402
    STORE_ERRORS,
    load_env_file,
    redis_client,
)


_PACKAGE = "back_dev_home.ebeam.recipe_search.providers"
_SLUG = "ebeam/recipe_search"

_TOOL_TYPE = {"cdsem": "cd-sem", "hvsem": "hv-sem"}


def _rule(title: str) -> None:
    print(f"\n{'-' * 72}\n{title}\n{'-' * 72}")


def _ok(message: str) -> None:
    print(f"  OK    {message}")


def _bad(message: str) -> None:
    print(f"  FAIL  {message}")


def _info(message: str) -> None:
    print(f"        {message}")


# ── stage 0: which code is actually deployed ──────────────────────────────


DEPLOYED = "deployed"  # office.py imported; this is what serves requests
MISSING = "missing"    # no office.py, so the feature serves mock data
BROKEN = "broken"      # office.py exists but cannot be imported at all


def _load_adapter() -> tuple[ModuleType, str]:
    """Import the deployed office.py, or fall back to the tracked template.

    Returns ``(module, state)``. Diagnosing the template when no usable copy
    exists is still worth doing - it proves the Redis/OpenSearch data is or is
    not in the shape the adapter wants - but the caller has to say so, because
    a passing run against the template does not mean the endpoint works.

    BROKEN is its own state rather than an unhandled traceback because it is a
    real and recoverable office condition, not a bug in this script: a copy
    left behind by an older ``git pull`` can reference names that the tracked
    ``mock.py`` beside it has since dropped. That is worse than a 502 - the
    blueprint auto-discovery imports every ``routes.py`` at app-factory time,
    so the whole backend fails to boot rather than one endpoint failing.
    """
    fallback = importlib.import_module(f"{_PACKAGE}.office_example")
    target = Path(fallback.__file__).with_name("office.py")
    if not target.exists():
        return fallback, MISSING
    try:
        return importlib.import_module(f"{_PACKAGE}.office"), DEPLOYED
    except ImportError as exc:
        print(f"\n  !!  providers/office.py exists but will not import: {exc}")
        return fallback, BROKEN


def _check_deployment(adapter: ModuleType, state: str) -> bool:
    """True when the deployed adapter is capable of reading the registry."""
    _rule("0. Which adapter is deployed?")

    if state == BROKEN:
        _bad("providers/office.py cannot be imported - the BACKEND WILL NOT BOOT.")
        _info("Blueprints are auto-discovered at app-factory time, so this is a")
        _info("startup failure, not a per-endpoint one. It means the copy predates")
        _info("a change to the tracked modules beside it. Refresh it:")
        _info("  python -m scripts.sync_office_adapters recipe_search")
        _info("Continuing against the tracked template so the data can still be checked.")
        return hasattr(adapter, "_locate_via_redis")

    if state == MISSING:
        _bad("providers/office.py does not exist - this feature is serving MOCK data.")
        _info("Nothing below reflects what the endpoint returns. To go live:")
        _info("  python -m scripts.sync_office_adapters recipe_search")
        _info("Continuing against the tracked template so the data can still be checked.")
    else:
        for candidate in office_template.discover():
            if candidate.slug != _SLUG:
                continue
            status, note = office_template.classify(candidate)
            detail = f"{status}" + (f" ({note})" if note else "")
            if status == office_template.SYNCED:
                _ok(f"providers/office.py is {detail} with the tracked template.")
            elif status == office_template.STALE:
                _bad(f"providers/office.py is {detail}.")
                _info("The template moved ahead and this copy still runs. Refresh it:")
                _info("  python -m scripts.sync_office_adapters recipe_search")
            else:
                _info(f"providers/office.py is {detail} - hand-edited, left alone.")
            break

    # The decisive check, independent of git: does this code have the registry
    # path at all? A pre-2026-07-29 copy goes straight to meas_hist, which is
    # exactly the 502 being diagnosed, and no Redis fix can reach it.
    has_registry = hasattr(adapter, "_locate_via_redis")
    if has_registry:
        _ok("It has the Redis registry path (_locate_via_redis).")
    else:
        _bad("It has NO Redis registry path - it only ever queries meas_hist.")
        _info("This alone explains a 502 on any recipe that has never been measured.")
        _info("  python -m scripts.sync_office_adapters recipe_search")
    return has_registry


# ── stage 1: Redis - which database, which keys ──────────────────────────


def _codec(raw: object) -> str:
    """Which of ``_parse_str_list``'s three parsers a stored value falls to.

    The loader is not pinned to one serialization (JSON list, Python repr,
    or a comma-joined string - docs/datatables/hitachi/recipe_name_list.txt),
    and the adapter accepts all three, so this is reported rather than judged.
    It is still worth seeing: a value that parses as "comma-separated" was not
    written as a list at all, and one day a name with a comma will split.
    """
    text = _text(raw).strip()
    for name, parse in (("JSON", json.loads), ("Python repr", ast.literal_eval)):
        try:
            if isinstance(parse(text), (list, tuple)):
                return name
        except (ValueError, SyntaxError):
            continue
    return "comma-separated"


def _expected_keys(adapter: ModuleType, family: str, fab: str) -> dict[str, str]:
    """The three keys the adapter will build for this request -> what each is.

    Built through the adapter's own ``_fab_hash`` where the copy has one, so a
    mismatch here is a mismatch between the deployed code and the store, not
    between this script and the store.
    """
    keys = {f"v3_{family}_unique_rcp_list": "catalog   fab -> [recipe names]"}
    fab_hash = getattr(adapter, "_fab_hash", None)
    if fab_hash is not None:
        tool_type = _TOOL_TYPE[family]
        keys[fab_hash("rcp_loc", tool_type, fab)] = "registry  recipe -> [idw, idp]"
        keys[fab_hash("tools_in_rcp", tool_type, fab)] = "registry  recipe -> [eqp_id, ...]"
    return keys


def _check_redis_inventory(adapter: ModuleType, family: str, fab: str) -> bool:
    """Is the client on the DB that holds the recipe keys? Returns reachable.

    ``redis_client()`` has no db setting - it always talks to logical DB 0.
    The office Redis is one server shared by several loaders, and a registry
    written into db1 is indistinguishable from an absent one when read from
    db0: HGET answers nil, the adapter bails to meas_hist, and the browser
    shows the meas_hist sentence. ``INFO keyspace`` lists every DB with a key
    count in one round trip, and ``SCAN v3_{family}_*`` shows what this DB
    actually holds before any per-recipe read is attempted. When an expected
    key is missing, the other DBs are scanned for it too, so "wrong DB" is
    named outright rather than left to be inferred from a nil.
    """
    _rule("1. Redis - which database is the client on, and which keys are in it")

    client = redis_client()
    kwargs = dict(client.connection_pool.connection_kwargs)
    db = int(kwargs.get("db") or 0)
    where = f"{kwargs.get('host')}:{kwargs.get('port')}"
    try:
        client.ping()
    except STORE_ERRORS as exc:
        _bad(f"cannot reach {where}: {type(exc).__name__}: {exc}")
        _info("REDIS_HOST/REDIS_PORT/REDIS_PASSWORD come from back_dev_home/.env. "
              "At home the host is set but unreachable - run this at the office.")
        return False
    _ok(f"connected to {where}  db={db}")
    _info("redis_client() has no db setting, so db 0 is the only DB the adapter "
          "ever reads.")

    keyspace = client.info("keyspace")  # {"db0": {"keys": N, ...}, "db1": ...}
    for name, stats in sorted(keyspace.items()):
        count = stats.get("keys") if isinstance(stats, dict) else stats
        tag = "  <- the adapter reads this one" if name == f"db{db}" else ""
        _info(f"{name}: {count} keys{tag}")
    if f"db{db}" not in keyspace:
        _bad(f"db{db} holds no keys at all - nothing the adapter reads exists there.")

    pattern = f"v3_{family}_*"
    keys = sorted(_text(key) for key in client.scan_iter(match=pattern, count=1000))
    expected = _expected_keys(adapter, family, fab)
    if keys:
        _ok(f"db{db} holds {len(keys)} key(s) matching {pattern}:")
        for key in keys:
            kind = _text(client.type(key))
            size = f"{client.hlen(key)} fields" if kind == "hash" else ""
            _info(f"{key:<40} {kind:<6} {size:<12} {expected.get(key, '')}")
    else:
        _bad(f"db{db} has NO key matching {pattern}.")

    missing = [key for key in expected if key not in keys]
    for key in missing:
        _bad(f"expected {key} ({expected[key].split()[0]}) is not in db{db}.")
        near = [other for other in keys if other.lower() == key.lower()]
        if near:
            _info(f"but {near[0]} IS - the loader spelled the fab in another case. "
                  "Both hashes were regenerated lowercase on 2026-08-07 "
                  "(docs/datatables/hitachi/recipe_name_list.txt).")
    if not missing:
        _ok("all three keys the adapter will read for this request exist.")
        return True

    # The direct answer to "are we on the right DB": look for the same keys
    # everywhere else the server has data.
    for name in sorted(keyspace):
        other = int(name[2:])
        if other == db:
            continue
        pool = redis.ConnectionPool(**{**kwargs, "db": other})
        try:
            found = sorted(
                _text(key) for key in
                redis.Redis(connection_pool=pool).scan_iter(match=pattern, count=1000)
            )
        finally:
            pool.disconnect()
        if found:
            _bad(f"db{other} holds {len(found)} {pattern} key(s): "
                 + ", ".join(found[:6]) + (" ..." if len(found) > 6 else ""))
            _info("The loader wrote to a DB the adapter never reads. Either the "
                  "loader must SELECT 0, or redis_client() needs a REDIS_DB "
                  "setting - it has none today (back_dev_home/_runtime/office_redis.py).")
    return True


# ── stage 2: Redis - the three reads for this recipe ─────────────────────


def _check_redis(adapter: ModuleType, family: str, fab: str, recipe: str) -> list[str]:
    """Walk the catalog and both registry hashes. Returns the eqp_ids found."""
    _rule("2. Redis - catalog and recipe-location registry, for this recipe")

    client = redis_client()

    catalog_key = f"v3_{family}_unique_rcp_list"
    fields = client.hkeys(catalog_key)
    if not fields:
        _bad(f"{catalog_key} is empty or absent - the recipe-list job has not run.")
        return []
    decoded = sorted(_text(field) for field in fields)
    _ok(f"{catalog_key} holds {len(decoded)} fab(s): {', '.join(decoded)}")

    if fab.lower() not in decoded:
        _bad(f"fab field {fab.lower()!r} is NOT one of them - check the fab spelling.")
        _info("Fields are lowercase here; the screen and routes use uppercase.")
        return []

    raw = client.hget(catalog_key, fab.lower()) or b""
    names = adapter._parse_str_list(raw)
    _info(f"HGET {catalog_key} {fab.lower()}  -> {len(raw)} bytes, {_codec(raw)}: "
          f"{_text(raw)[:60]!r}...")
    if recipe in names:
        _ok(f"{fab} lists {len(names)} recipes, including {recipe!r}.")
    else:
        _bad(f"{fab} lists {len(names)} recipes and {recipe!r} is NOT among them.")
        _info(f"first few: {', '.join(names[:3])}")
        near = [name for name in names if recipe.split('/')[-1] in name][:5]
        if near:
            _info(f"similar names present: {', '.join(near)}")

    # The two hashes recipe open actually assembles the path from.
    loc_key = adapter._fab_hash("rcp_loc", _TOOL_TYPE[family], fab)
    tools_key = adapter._fab_hash("tools_in_rcp", _TOOL_TYPE[family], fab)

    eqp_ids: list[str] = []
    for key, label in ((loc_key, "[idw, idp] paths"), (tools_key, "tool list")):
        if not client.exists(key):
            _bad(f"{key} does not exist - this fab has no {label} registry at all.")
            _info("Every recipe in this fab therefore falls through to meas_hist.")
            continue
        raw = client.hget(key, recipe)
        if raw is None:
            _bad(f"{key} exists ({client.hlen(key)} recipes) but has no entry for "
                 f"{recipe!r}.")
            sample = [_text(field) for field in (client.hkeys(key) or [])[:3]]
            _info(f"sample fields (compare the spelling): {', '.join(sample)}")
            continue
        parsed = adapter._parse_str_list(raw)
        _info(f"HGET {key} {recipe}  -> {_codec(raw)}: {_text(raw)!r}")
        if key == loc_key:
            if len(parsed) < 2:
                _bad(f"{key} entry is {parsed} - needs 2 entries, read positionally.")
            else:
                _ok(f"{key} -> idw={parsed[0]!r} idp={parsed[1]!r}")
        else:
            eqp_ids = parsed
            if eqp_ids:
                _ok(f"{key} -> {len(eqp_ids)} tool(s): {', '.join(eqp_ids)}")
            else:
                _bad(f"{key} entry for {recipe!r} names no tool.")
    return eqp_ids


# ── stage 3: the eqp_id -> eqp_ip join through sem_list ───────────────────


def _check_roster(adapter: ModuleType, eqp_ids: list[str]) -> None:
    _rule("3. sem_list roster - eqp_id -> eqp_ip (FTP dials an IP, not an id)")

    if not eqp_ids:
        _info("skipped: stage 2 found no tool list to resolve.")
        return

    index = adapter._eqp_ip_index()
    _ok(f"roster carries {len(index)} tool(s) with an IP.")

    resolved = adapter._order_candidates(eqp_ids, index)
    unknown = [eqp_id for eqp_id in eqp_ids if eqp_id.strip() not in index]
    if unknown:
        _bad(f"not in the roster (dropped): {', '.join(unknown)}")
        _info("Both sources use the same eqp_id spelling, so this means the "
              "roster is missing the tool.")
    if resolved:
        _ok("download order (available tools first): "
            + ", ".join(f"{eqp_id}@{eqp_ip}" for eqp_id, eqp_ip in resolved))
    else:
        _bad("no tool resolves to an IP - the registry path bails here.")


# ── stage 4: OpenSearch fallback ─────────────────────────────────────────


def _check_meas_hist(adapter: ModuleType, family: str, fab: str, recipe: str) -> None:
    _rule("4. meas_hist - the fallback, and the source the 502 message names")

    from back_dev_home.ebeam._office_search import aggregate, fetch_hits, query

    index = adapter._MEAS_HIST_INDEX[_TOOL_TYPE[family]]

    hits = fetch_hits(
        index,
        query([{"term": {"full_name.keyword": recipe}},
               {"term": {"fab_name.keyword": fab}}]),
        size=3,
        sort=[{"timestamp": "desc"}],
        source=adapter._SOURCE,
    )
    if hits:
        _ok(f"{index} has {len(hits)}+ document(s) for {recipe!r} in {fab}.")
        for hit in hits:
            _info(f"{hit.get('timestamp')} {hit.get('eqp_id')} @ {hit.get('eqp_ip')} "
                  f"class={hit.get('class_name')} idp={hit.get('idp_name')}")
        return

    _bad(f"{index} has no document with full_name={recipe!r} for fab {fab!r}.")
    _info("This is the sentence the browser shows. On its own it is NORMAL - a "
          "recipe that was never measured has no run to derive a path from.")

    # Split the miss: wrong fab, wrong recipe spelling, or genuinely unmeasured.
    any_fab = fetch_hits(
        index, query([{"term": {"full_name.keyword": recipe}}]),
        size=1, sort=[{"timestamp": "desc"}], source=["fab_name", "timestamp"],
    )
    if any_fab:
        _bad(f"but it EXISTS under fab {any_fab[0].get('fab_name')!r} - the "
             f"fab filter is what excluded it.")
        return

    buckets = aggregate(
        index,
        {"names": {"terms": {"field": "full_name.keyword",
                             "include": f".*{recipe.split('/')[-1]}.*",
                             "size": 5}}},
        None,
    ).get("names", {}).get("buckets", [])
    if buckets:
        _bad("no exact match, but these look close - compare the spelling:")
        for bucket in buckets:
            _info(f"{bucket['key']}  ({bucket['doc_count']} docs)")
    else:
        _ok("and no near-miss spelling either, so this recipe genuinely has no "
            "measurement history. The Redis registry is the only source that "
            "can open it.")


# ── stage 5: the verdict the endpoint itself would reach ─────────────────


def _check_verdict(adapter: ModuleType, family: str, fab: str, recipe: str) -> None:
    _rule("5. Verdict - what /recipe-detail would do with this exact request")

    try:
        locations = adapter._locate_idp(_TOOL_TYPE[family], recipe, fab)
    except LookupError as exc:
        _bad("502 upstream_data_error. The browser would show:")
        _info(str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - a diagnosis must not itself crash
        _bad(f"{type(exc).__name__}: {exc}")
        return

    _ok(f"located - {len(locations)} tool candidate(s), tried in this order:")
    for location in locations:
        _info(f"{location.eqp_id or '?'} @ {location.eqp_ip}  "
              f"{adapter._idp_remote_path(location)}")
    _info("Locating succeeded, so a 502 now would come from the FTP download "
          "instead - add --fetch to carry on into it.")


# ── stage 6: download and parse, the step --fetch adds ───────────────────


def _check_fetch(
    adapter: ModuleType, family: str, fab: str, recipe: str
) -> tuple[dict, dict] | None:
    """Download the .idp and hand the parser BYTES, the 2026-08-05 change.

    Split from stage 5 because it is the first step that opens an FTP session
    and the first that runs 사내 code. Everything above is read-only against
    Redis and OpenSearch and safe to run against anything.

    ``combined_idp_info`` accepting bytes is user-confirmed but had never been
    executed when the adapter stopped writing its temp file, so this stage
    parses TWICE - once from bytes, once through the escape hatch's temp file -
    and reports whether the two agree. That comparison is the whole reason the
    stage exists: if bytes are rejected or quietly return something different,
    it says so here instead of on a user's screen as a 502.
    """
    _rule("6. Download + parse (--fetch)")

    try:
        locations = adapter._locate_idp(_TOOL_TYPE[family], recipe, fab)
        data, location = adapter._download_first(locations)
    except Exception as exc:  # noqa: BLE001 - a diagnosis must not itself crash
        _bad(f"{type(exc).__name__}: {exc}")
        _info("The download failed, so nothing below can run. "
              "scripts/probe_recipe_ftp.py explores the FTP tree itself.")
        return None

    _ok(f"downloaded {len(data)} bytes from {location.eqp_id or '?'} "
        f"@ {location.eqp_ip} - nothing was written to disk.")
    _info(f"first 16 bytes: {data[:16].hex(' ')}")

    label = f"{location.idp_stem}.idp"
    try:
        frames = adapter._parse_idp(data, label)
    except Exception as exc:  # noqa: BLE001
        _bad(f"combined_idp_info(bytes) -> {type(exc).__name__}: {exc}")
        _info("If this is a TypeError or an encoding error, the parser wants a "
              "path after all. Set SKEWNONO_RECIPE_IDP_VIA_TEMPFILE=1 in "
              "back_dev_home/.env, restart Flask to restore the temp file, and "
              "tell home - docs/datatables/hitachi/recipe_idp.txt records the opposite.")
        return None

    _ok("combined_idp_info(bytes) returned the three documented tables:")
    for name, frame in frames.items():
        _info(f"{name}: {len(frame)} rows x {len(frame.columns)} cols")
    if _is_home_standin("office_utils.read_idp_info"):
        _bad("but this is the HOME STAND-IN - every value above is fabricated. "
             "Run this at the office for it to mean anything.")

    _compare_with_tempfile(adapter, data, label, frames)
    # The same locator _to_detail_response sends to the browser, so stage 7
    # reaches the raw folder exactly the way param-detail does.
    locator = {
        "eqp_ip": location.eqp_ip,
        "class_name": location.class_name,
        "idw": location.idw_stem,
        "idp": location.idp_stem,
    }
    return frames, locator


def _is_home_standin(module_name: str) -> bool:
    """Is the office_utils module in play the gitignored home stand-in?

    Only the stand-ins define IS_HOME_STANDIN, so this is False at the office
    and False as well if office_utils is absent entirely.

    It IMPORTS rather than reading ``sys.modules``: the adapter imports these
    modules inside the functions that use them, so a stage that asks before
    calling one would read an empty ``sys.modules`` and wrongly report office
    data. Importing is safe - both modules are import-side-effect-free.
    """
    try:
        return bool(getattr(importlib.import_module(module_name), "IS_HOME_STANDIN", False))
    except ImportError:
        return False


def _compare_with_tempfile(
    adapter: ModuleType, data: bytes, label: str, frames: dict
) -> None:
    """Does parsing a path give the same answer as parsing the bytes?

    A silent disagreement is worse than a rejection: the screen fills in either
    way, and only the values are wrong.
    """
    previous = os.environ.get("SKEWNONO_RECIPE_IDP_VIA_TEMPFILE")
    os.environ["SKEWNONO_RECIPE_IDP_VIA_TEMPFILE"] = "1"
    try:
        via_path = adapter._parse_idp(data, label)
    except Exception as exc:  # noqa: BLE001
        _info(f"(the temp-file fallback itself raised {type(exc).__name__}: "
              f"{exc} - the bytes path above is the only one that works)")
        return
    finally:
        if previous is None:
            os.environ.pop("SKEWNONO_RECIPE_IDP_VIA_TEMPFILE", None)
        else:
            os.environ["SKEWNONO_RECIPE_IDP_VIA_TEMPFILE"] = previous

    differing = [
        name for name in frames
        if not frames[name].equals(via_path.get(name))
    ]
    if differing and _is_home_standin("office_utils.read_idp_info"):
        _info("(the home stand-in fabricates from whatever it is handed, so "
              "bytes and a path necessarily differ here - this comparison only "
              "means something at the office.)")
        return
    if not differing:
        _ok("parsing the same bytes through a temp file gives an IDENTICAL "
            "result - the disk write really was unnecessary.")
        return

    _bad(f"bytes and path DISAGREE on: {', '.join(differing)}.")
    for name in differing:
        mine, theirs = frames[name], via_path.get(name)
        _info(f"{name}: bytes {mine.shape} vs path "
              f"{getattr(theirs, 'shape', type(theirs).__name__)}")
    _info("Set SKEWNONO_RECIPE_IDP_VIA_TEMPFILE=1 in back_dev_home/.env and "
          "restart: the path result is the one that was in production before "
          "2026-08-05. Then send this output home.")


# ── stage 7: the five raw readers ────────────────────────────────────────


def _check_readers(
    adapter: ModuleType, frames: dict, locator: dict, parameter: str | None
) -> None:
    """Run one parameter's slots through the readers and print what came back.

    The readers are the other half of the office_utils surface and their return
    CONTAINERS are the part home cannot see: ENMP returns a dict of dicts, the
    align batch keys by optic, and values are not all strings. A shape that
    changes renders as an empty 설정 panel rather than an error, so this prints
    what actually arrived rather than asserting anything about it.
    """
    _rule("7. Raw-folder readers (--fetch)")

    if _is_home_standin("office_utils.idp_amp_reader"):
        _bad("the HOME STAND-IN is installed - the settings below are "
             "fabricated and their FIELD NAMES are placeholders (AMP_FIELD_1).")

    rows = frames.get("idp_image_info")
    if rows is None or rows.empty:
        _bad("idp_image_info is empty - no parameter to follow into the folder.")
        return

    wanted = (parameter or "").strip()
    match = rows[rows["Parameter"] == wanted] if wanted else rows.head(1)
    if match.empty:
        _bad(f"no idp_image_info row has Parameter=={wanted!r}. Available: "
             f"{', '.join(map(str, rows['Parameter'].head(8)))}")
        return

    row = match.iloc[0].to_dict()
    slots = {
        slot: str(row.get(slot, ""))
        for slot in ("img_add1", "img_add2", "img_meas1", "img_meas2", "image_add3")
    }
    _info(f"Parameter={row.get('Parameter')!r}  slots={slots}")

    try:
        detail = adapter.get_param_detail([{
            "locator": locator,
            "parameter": str(row.get("Parameter")),
            "slots": slots,
        }])
    except Exception as exc:  # noqa: BLE001
        _bad(f"get_param_detail -> {type(exc).__name__}: {exc}")
        return

    for response in detail:
        _ok(f"parameter {response['parameter']!r}")
        for key in ("amp", "af_pr"):
            block = response.get(key)
            if block is None:
                _info(f"{key}: 파일 없음 (slot empty, file missing, or unparsed)")
            else:
                sample = ", ".join(
                    f"{r['key']}={r['value']}" for r in block["rows"][:3]
                )
                _info(f"{key}: {len(block['rows'])} rows - {sample}")
        for image in response.get("images", []):
            cond = image.get("cond")
            _info(f"image {image.get('slot')}={image.get('name')}: "
                  f"{'파일 없음' if cond is None else str(len(cond['rows'])) + ' cond rows'}")


def _text(value: object) -> str:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8")
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="diagnose_recipe_search_office",
        description="Trace why recipe-search → 자세히 보기 answers 502.",
    )
    parser.add_argument("recipe", help='full_name, e.g. "1/AC_M2_TAT"')
    parser.add_argument("--fab", default="R3", help="fab name (default: R3)")
    parser.add_argument("--tool", default="cdsem", choices=sorted(_TOOL_TYPE))
    parser.add_argument(
        "--fetch", action="store_true",
        help="carry on past locating: download the .idp, parse it from BYTES, "
             "and run one parameter's slots through the five raw readers",
    )
    parser.add_argument(
        "--parameter", default=None,
        help="with --fetch, which parameter to follow (default: the first)",
    )
    args = parser.parse_args()

    fab = args.fab.strip().upper()
    recipe = args.recipe.strip()

    if not os.environ.get("REDIS_HOST"):
        load_env_file("REDIS_HOST")
    if not os.environ.get("OPENSEARCH_HOST"):
        load_env_file("OPENSEARCH_HOST")

    print(f"recipe={recipe!r}  fab={fab}  tool={args.tool}")

    adapter, state = _load_adapter()
    has_registry = _check_deployment(adapter, state)

    reachable = _check_redis_inventory(adapter, args.tool, fab)
    if not reachable:
        _rule("2-3. Redis registry and roster")
        _info("skipped: Redis is unreachable, so every read below would fail "
              "the same way.")
    elif has_registry:
        eqp_ids = _check_redis(adapter, args.tool, fab, recipe)
        _check_roster(adapter, eqp_ids)
    else:
        _rule("2-3. Redis registry and roster")
        _info("skipped: this adapter cannot read it. Refresh it first, then "
              "re-run - stage 1 already showed whether the keys are there.")

    try:
        _check_meas_hist(adapter, args.tool, fab, recipe)
    except RuntimeError as exc:  # OpenSearch not configured or unreachable
        _bad(str(exc))
    _check_verdict(adapter, args.tool, fab, recipe)

    if args.fetch:
        fetched = _check_fetch(adapter, args.tool, fab, recipe)
        if fetched is not None:
            frames, locator = fetched
            _check_readers(adapter, frames, locator, args.parameter)
    else:
        _rule("6-7. Download, parse and readers")
        _info("skipped: add --fetch. Those stages open an FTP session to the "
              "tool and run 사내 office_utils code, so they are opt-in.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
