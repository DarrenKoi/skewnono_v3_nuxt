# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 adapter for the office recipe catalog (Redis).

Only the recipe *name list* is wired to the office source. The office Redis
stores one hash per tool family::

    v3_cdsem_unique_rcp_list   # CD-SEM
    v3_hvsem_unique_rcp_list   # HV-SEM

Each hash is keyed by **lowercase** fab name and holds that fab's recipe-name
list::

    {"m14a": ["1/AC_M2_TAT", ...], "r3": [...]}

``routes.py`` uppercases ``?fab_name=`` before it reaches this module, so the
lowercasing happens here — at the Redis boundary — and never leaks into the
routes. The response echoes the caller's (uppercase) spelling so the contract
matches the mock.

Recipe-open detail (``get_recipe_open_data``) and compare
(``get_recipe_compare_data``) have NO office source yet: the raw IDP payload
is not prepared office-side. Both are re-exported from the mock below so the
UI stays usable and the contract gate stays green. See the TODO there.

Connection settings come from ``REDIS_HOST`` / ``REDIS_PORT`` /
``REDIS_PASSWORD`` in ``back_dev_home/.env``. At the office: fill in .env,
then `cp office_example.py office.py` — that file's existence is the switch,
no env var needed — and run the Verify command in MIGRATION.md.
"""

import ast
import json

from back_dev_home._runtime.office_redis import redis_client as _redis_client
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    RecipeSearchResponse,
    RecipeSearchRow,
    ToolType,
)
# TODO(office): replace these two with real IDP-backed implementations once the
# recipe-open raw data is prepared office-side. Re-exported (not reimplemented)
# so compare stays derived from open — the invariant the mock guarantees.
from back_dev_home.ebeam.hitachi.recipe_search.providers.mock import (
    get_recipe_compare_data,
    get_recipe_open_data,
)


__all__ = [
    "get_recipe_catalog",
    "get_recipe_compare_data",
    "get_recipe_open_data",
]


_RECIPE_HASH: dict[ToolType, str] = {
    "cd-sem": "v3_cdsem_unique_rcp_list",
    "hv-sem": "v3_hvsem_unique_rcp_list",
}


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


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.ebeam.hitachi.recipe_search.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    for tool in ("cd-sem", "hv-sem"):
        catalog = get_recipe_catalog(tool, "R3")
        print(f"{tool}: {catalog['total']} recipes for R3")
        if catalog["rows"]:
            print("  first:", catalog["rows"][0])
