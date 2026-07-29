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
been measured — source 1 exists precisely to serve those. So the useful
question is almost never "why is meas_hist empty" but "why did the registry
decline", and this script walks every step of both sources until one of them
produces an answer or all of them have been ruled out.

It diagnoses the DEPLOYED adapter, not the template: it imports
``providers/office.py`` when that file exists, because that is the code
actually serving requests. A copy left behind by an older ``git pull`` has no
registry path at all — stage 0 catches that outright, since no amount of
correct Redis data helps an adapter that never reads it.

Run FROM THE REPO ROOT at the office (reads REDIS_* / OPENSEARCH_* from
back_dev_home/.env the same way the adapter does)::

    .venv/bin/python -m scripts.diagnose_recipe_search_office "1/AC_M2_TAT"
    .venv/bin/python -m scripts.diagnose_recipe_search_office "ADI/X" --fab M14A
    .venv/bin/python -m scripts.diagnose_recipe_search_office "ADI/X" --tool hvsem

Nothing here writes: it is read-only against Redis and OpenSearch, and it does
not open an FTP session. Locating the file is the step that 502s; downloading
it fails differently (503, or a 502 naming the tool) and is out of scope.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

from back_dev_home._runtime import office_template
from back_dev_home._runtime.office_redis import load_env_file, redis_client


_PACKAGE = "back_dev_home.ebeam.hitachi.recipe_search.providers"
_SLUG = "ebeam/hitachi/recipe_search"

_TOOL_TYPE = {"cdsem": "cd-sem", "hvsem": "hv-sem"}


def _rule(title: str) -> None:
    print(f"\n{'─' * 72}\n{title}\n{'─' * 72}")


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
    exists is still worth doing — it proves the Redis/OpenSearch data is or is
    not in the shape the adapter wants — but the caller has to say so, because
    a passing run against the template does not mean the endpoint works.

    BROKEN is its own state rather than an unhandled traceback because it is a
    real and recoverable office condition, not a bug in this script: a copy
    left behind by an older ``git pull`` can reference names that the tracked
    ``mock.py`` beside it has since dropped. That is worse than a 502 — the
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
        _bad("providers/office.py cannot be imported — the BACKEND WILL NOT BOOT.")
        _info("Blueprints are auto-discovered at app-factory time, so this is a")
        _info("startup failure, not a per-endpoint one. It means the copy predates")
        _info("a change to the tracked modules beside it. Refresh it:")
        _info("  python -m scripts.sync_office_adapters recipe_search")
        _info("Continuing against the tracked template so the data can still be checked.")
        return hasattr(adapter, "_locate_via_redis")

    if state == MISSING:
        _bad("providers/office.py does not exist — this feature is serving MOCK data.")
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
                _info(f"providers/office.py is {detail} — hand-edited, left alone.")
            break

    # The decisive check, independent of git: does this code have the registry
    # path at all? A pre-2026-07-29 copy goes straight to meas_hist, which is
    # exactly the 502 being diagnosed, and no Redis fix can reach it.
    has_registry = hasattr(adapter, "_locate_via_redis")
    if has_registry:
        _ok("It has the Redis registry path (_locate_via_redis).")
    else:
        _bad("It has NO Redis registry path — it only ever queries meas_hist.")
        _info("This alone explains a 502 on any recipe that has never been measured.")
        _info("  python -m scripts.sync_office_adapters recipe_search")
    return has_registry


# ── stage 1: Redis ────────────────────────────────────────────────────────


def _check_redis(adapter: ModuleType, family: str, fab: str, recipe: str) -> list[str]:
    """Walk the catalog and both registry hashes. Returns the eqp_ids found."""
    _rule("1. Redis — catalog and recipe-location registry")

    client = redis_client()
    client.ping()
    _ok(f"connected to {os.environ.get('REDIS_HOST')}:{os.environ.get('REDIS_PORT')}")

    catalog_key = f"v3_{family}_unique_rcp_list"
    fields = client.hkeys(catalog_key)
    if not fields:
        _bad(f"{catalog_key} is empty or absent — the recipe-list job has not run.")
        return []
    decoded = sorted(_text(field) for field in fields)
    _ok(f"{catalog_key} holds {len(decoded)} fab(s): {', '.join(decoded)}")

    if fab.lower() not in decoded:
        _bad(f"fab field {fab.lower()!r} is NOT one of them — check the fab spelling.")
        _info("Fields are lowercase here; the screen and routes use uppercase.")
        return []

    names = adapter._parse_str_list(client.hget(catalog_key, fab.lower()) or "")
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
            _bad(f"{key} does not exist — this fab has no {label} registry at all.")
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
        if key == loc_key:
            if len(parsed) < 2:
                _bad(f"{key} entry is {parsed} — needs 2 entries, read positionally.")
            else:
                _ok(f"{key} -> idw={parsed[0]!r} idp={parsed[1]!r}")
        else:
            eqp_ids = parsed
            if eqp_ids:
                _ok(f"{key} -> {len(eqp_ids)} tool(s): {', '.join(eqp_ids)}")
            else:
                _bad(f"{key} entry for {recipe!r} names no tool.")
    return eqp_ids


# ── stage 2: the eqp_id -> eqp_ip join through sem_list ───────────────────


def _check_roster(adapter: ModuleType, eqp_ids: list[str]) -> None:
    _rule("2. sem_list roster — eqp_id -> eqp_ip (FTP dials an IP, not an id)")

    if not eqp_ids:
        _info("skipped: stage 1 found no tool list to resolve.")
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
        _bad("no tool resolves to an IP — the registry path bails here.")


# ── stage 3: OpenSearch fallback ─────────────────────────────────────────


def _check_meas_hist(adapter: ModuleType, family: str, fab: str, recipe: str) -> None:
    _rule("3. meas_hist — the fallback, and the source the 502 message names")

    from back_dev_home.ebeam.hitachi._office_search import aggregate, fetch_hits, query

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
    _info("This is the sentence the browser shows. On its own it is NORMAL — a "
          "recipe that was never measured has no run to derive a path from.")

    # Split the miss: wrong fab, wrong recipe spelling, or genuinely unmeasured.
    any_fab = fetch_hits(
        index, query([{"term": {"full_name.keyword": recipe}}]),
        size=1, sort=[{"timestamp": "desc"}], source=["fab_name", "timestamp"],
    )
    if any_fab:
        _bad(f"but it EXISTS under fab {any_fab[0].get('fab_name')!r} — the "
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
        _bad("no exact match, but these look close — compare the spelling:")
        for bucket in buckets:
            _info(f"{bucket['key']}  ({bucket['doc_count']} docs)")
    else:
        _ok("and no near-miss spelling either, so this recipe genuinely has no "
            "measurement history. The Redis registry is the only source that "
            "can open it.")


# ── stage 4: the verdict the endpoint itself would reach ─────────────────


def _check_verdict(adapter: ModuleType, family: str, fab: str, recipe: str) -> None:
    _rule("4. Verdict — what /recipe-detail would do with this exact request")

    try:
        locations = adapter._locate_idp(_TOOL_TYPE[family], recipe, fab)
    except LookupError as exc:
        _bad("502 upstream_data_error. The browser would show:")
        _info(str(exc))
        return
    except Exception as exc:  # noqa: BLE001 — a diagnosis must not itself crash
        _bad(f"{type(exc).__name__}: {exc}")
        return

    _ok(f"located — {len(locations)} tool candidate(s), tried in this order:")
    for location in locations:
        _info(f"{location.eqp_id or '?'} @ {location.eqp_ip}  "
              f"{adapter._idp_remote_path(location)}")
    _info("Locating succeeded, so a 502 now would come from the FTP download "
          "instead. Probe that with scripts/probe_recipe_ftp.py.")


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

    if has_registry:
        eqp_ids = _check_redis(adapter, args.tool, fab, recipe)
        _check_roster(adapter, eqp_ids)
    else:
        _rule("1-2. Redis registry")
        _info("skipped: this adapter cannot read it. Refresh it first, then "
              "re-run — the Redis data is very likely fine.")

    _check_meas_hist(adapter, args.tool, fab, recipe)
    _check_verdict(adapter, args.tool, fab, recipe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
