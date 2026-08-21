"""Contract gate for recipe_search. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/recipe_search
Office: SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/recipe_search

`get_recipe_catalog` (Redis) and `get_recipe_open_data` (tool FTP + the 사내 IDP
parser) both swap; only `get_recipe_compare_data` is still re-exported from
providers/mock.py behind a TODO(office). So under the office provider this file
does REAL I/O — an OpenSearch lookup and an FTP download per detail call — and
is the closest thing recipe_search has to an end-to-end office check.

The mapping itself is gated separately and without infrastructure, in
`test_idp_mapping.py`, which feeds hand-built DataFrames to the pure
`_to_detail_response`. That file is where a column or JSON-safety regression
should be caught; this one answers "does the real chain still run".

The shape and self-consistency checks hold under both providers — MIGRATION.md
requires `total == len(rows)` of the office adapter too. What is NOT
provider-independent is the SIZE of the catalog: the mock synthesizes 50,000
sha256-seeded names, while office looks the fab up in a Redis hash where a
missing *field* (unknown fab) is a legitimate empty result. That assumption is
fenced behind get_data_provider("recipe_search") == "mock".
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.recipe_search import data
from back_dev_home.ebeam.recipe_search.contracts import (
    ParamDetailResponse,
    RecipeCompareResponse,
    RecipeDetailResponse,
    RecipeSearchResponse,
)
from back_dev_home.ebeam.recipe_search.providers import mock, office_example


TOOL_TYPE = "cd-sem"


def _is_mock() -> bool:
    return get_data_provider("recipe_search") == "mock"


def test_recipe_catalog_matches_contract():
    catalog = data.get_recipe_catalog(TOOL_TYPE)
    assert_matches(catalog, RecipeSearchResponse)

    # `total` is what the UI shows above a virtualised list it scrolls through
    # `rows`; MIGRATION.md pins the two together for the office adapter as
    # well, so a drift here is a bug under either provider.
    assert catalog["total"] == len(catalog["rows"])
    assert catalog["tool_type"] == TOOL_TYPE
    # De-dup is per (recipe, fab), not per name: an omitted fab_name is now a
    # union across fabs, and the two default mock fabs share ~20% of their
    # names by construction (see test_mock_catalog_duplicate_names_stay_per_fab).
    pairs = [(row["recipe_name"], row["fab_name"]) for row in catalog["rows"]]
    assert len(set(pairs)) == len(pairs), "(recipe, fab) rows must be de-duped"

    if _is_mock():
        # The mock synthesizes a fixed 50,000-name catalog, so an empty one
        # means the generator broke. Office returns an empty list for a fab
        # with no hash field, which MIGRATION.md calls valid (the LookupError
        # 502 is reserved for a missing hash KEY — the upstream job never ran).
        assert catalog["rows"], "mock recipe catalog must not be empty"


def test_recipe_open_and_compare_match_contract():
    # Prefer a real catalog recipe, but never silently skip on an empty catalog
    # — get_recipe_open_data accepts any id, so a deterministic fallback keeps
    # detail/compare exercised even when the catalog is empty.
    catalog = data.get_recipe_catalog(TOOL_TYPE)
    rows = catalog["rows"]
    recipe_name = rows[0]["recipe_name"] if rows else "RECIPE-CONTRACT-0001"
    recipe_fab_name = rows[0]["fab_name"] if rows else ""

    try:
        detail = data.get_recipe_open_data(recipe_id=recipe_name)
    except LookupError as exc:
        # Office only, and only for this one cause: the catalog lists every
        # recipe that EXISTS, while recipe open needs one that has RUN — the
        # .idp location is derived from a measurement document. Picking an
        # unmeasured name is a property of the fixture, not a contract break,
        # so it must not read as a failing gate. Any other exception still
        # fails, and under mock this path is unreachable.
        if _is_mock():
            raise
        pytest.skip(f"catalog recipe {recipe_name!r} has no measurement doc: {exc}")

    assert_matches(detail, RecipeDetailResponse)
    assert detail["recipe_id"] == recipe_name, "detail must answer for the id asked for"

    # AMP no longer rides on the detail response — it is fetched per click from
    # the raw-recipe folder (spec 2026-07-29). What the detail response owes the
    # follow-up calls is the locator, so that is what is pinned here.
    assert set(detail["locator"]) == {"eqp_ip", "class_name", "idw", "idp"}
    assert all(detail["locator"][field] for field in detail["locator"]), (
        "an empty locator field would make param-detail unaddressable"
    )

    # The per-parameter panel posts a parameter's own img_* values back as
    # `slots`, so every declared parameter must carry all five.
    for row in detail["idp_image_info"]:
        for slot in ("img_add1", "img_add2", "image_add3", "img_meas1", "img_meas2"):
            assert slot in row, f"{row['Parameter']!r} is missing {slot}"

    param_detail = data.get_param_detail([{
        "locator": detail["locator"],
        "parameter": detail["idp_image_info"][0]["Parameter"],
        "slots": {
            slot: detail["idp_image_info"][0][slot]
            for slot in ("img_add1", "img_add2", "image_add3", "img_meas1", "img_meas2")
        },
    }]) if detail["idp_image_info"] else []
    for entry in param_detail:
        assert_matches(entry, ParamDetailResponse)

    # A PARTIAL `slots` dict is part of the contract, not an accident: it is how
    # param-info's `include=` narrows what the adapter READS rather than merely
    # what it returns. Omitting img_meas2 must yield amp=None with that file
    # never fetched, and must do so under BOTH providers — an office adapter
    # that indexed `slots` directly instead of planning through
    # rawfiles.slot_sources would KeyError here rather than silently costing a
    # full FTP session.
    if detail["idp_image_info"]:
        row = detail["idp_image_info"][0]
        partial = data.get_param_detail([{
            "locator": detail["locator"],
            "parameter": row["Parameter"],
            "slots": {"img_add1": row["img_add1"]},
        }])
        assert len(partial) == 1, "one entry per requested item, partial slots or not"
        assert_matches(partial[0], ParamDetailResponse)
        assert partial[0]["amp"] is None, "img_meas2 was not asked for; AMP must be unread"
        assert partial[0]["af_pr"] is None, "img_add2 was not asked for"

    compare = data.get_recipe_compare_data(
        TOOL_TYPE, [{"recipe_name": recipe_name, "fab_name": recipe_fab_name}]
    )
    assert_matches(compare, RecipeCompareResponse)
    assert compare["tool_type"] == TOOL_TYPE
    # The compare view columns the recipes side by side under the headers the
    # caller passed; a recipe nobody asked for has no column to land in.
    assert {entry["recipe_id"] for entry in compare["recipes"]} <= {recipe_name}


# ── catalog rows carry their owning fab (multi-fab phase B, task 1) ────────


def test_mock_catalog_rows_carry_owning_fab():
    payload = mock.get_recipe_catalog("cd-sem", ("R3", "M16B"))
    assert payload["fab_names"] == ["R3", "M16B"]
    assert payload["total"] == len(payload["rows"])
    assert {row["fab_name"] for row in payload["rows"]} == {"R3", "M16B"}
    assert all(row["recipe_name"] for row in payload["rows"])


def test_mock_catalog_duplicate_names_stay_per_fab():
    payload = mock.get_recipe_catalog("cd-sem", ("R3", "M16B"))
    r3 = {r["recipe_name"] for r in payload["rows"] if r["fab_name"] == "R3"}
    m16b = {r["recipe_name"] for r in payload["rows"] if r["fab_name"] == "M16B"}
    shared = r3 & m16b
    # ~20% of mock names overlap by construction; both copies must survive.
    assert shared
    rows_for_shared = [
        r for r in payload["rows"] if r["recipe_name"] in shared
    ]
    assert len(rows_for_shared) == 2 * len(shared)


def test_mock_catalog_single_fab_rows_match_union_slice():
    solo = mock.get_recipe_catalog("cd-sem", ("R3",))
    union = mock.get_recipe_catalog("cd-sem", ("R3", "M16B"))
    union_r3 = [r for r in union["rows"] if r["fab_name"] == "R3"]
    assert solo["rows"] == union_r3


def test_mock_catalog_omitted_fab_uses_default_fabs_and_empty_echo():
    payload = mock.get_recipe_catalog("cd-sem", None)
    assert payload["fab_names"] == []
    assert {row["fab_name"] for row in payload["rows"]} == {"R3", "M16B"}


class _FakeCatalogRedis:
    def __init__(self, entries):
        self._entries = entries  # {b"r3": b'["A", "B"]', ...}

    def hget(self, key, field):
        return self._entries.get(field.encode())

    def hgetall(self, key):
        return self._entries

    def exists(self, key):
        return 1 if self._entries else 0


def test_office_catalog_tags_rows_per_requested_fab(monkeypatch):
    fake = _FakeCatalogRedis({b"r3": b'["A", "B"]', b"m16b": b'["B", "C"]'})
    monkeypatch.setattr(office_example, "_redis_client", lambda: fake)
    payload = office_example.get_recipe_catalog("cd-sem", ("R3", "M16B"))
    assert payload["fab_names"] == ["R3", "M16B"]
    assert payload["rows"] == [
        {"recipe_name": "A", "fab_name": "R3"},
        {"recipe_name": "B", "fab_name": "R3"},
        {"recipe_name": "B", "fab_name": "M16B"},
        {"recipe_name": "C", "fab_name": "M16B"},
    ]


def test_office_catalog_union_preserves_provenance(monkeypatch):
    fake = _FakeCatalogRedis({b"r3": b'["A", "B"]', b"m16b": b'["B"]'})
    monkeypatch.setattr(office_example, "_redis_client", lambda: fake)
    payload = office_example.get_recipe_catalog("cd-sem", None)
    assert payload["fab_names"] == []
    # (B, R3) and (B, M16B) both survive — the union no longer dedupes names.
    names = [(r["recipe_name"], r["fab_name"]) for r in payload["rows"]]
    assert ("B", "R3") in names and ("B", "M16B") in names


# ── compare takes per-recipe fabs (multi-fab phase B, task 2) ──────────────


def test_mock_compare_cross_fab_recipes_differ():
    # Same name in two fabs => two genuinely different generated tables, because
    # the mock's seeded random stream includes fab_name. The cross-fab
    # duplication is deliberate — the office catalog has it too.
    payload = mock.get_recipe_compare_data("cd-sem", [
        {"recipe_name": "RACE/DEAE_ABC123_PROD_00001", "fab_name": "R3"},
        {"recipe_name": "RACE/DEAE_ABC123_PROD_00001", "fab_name": "M16B"},
    ])
    assert payload["fab_names"] == ["R3", "M16B"]
    assert [r["fab_name"] for r in payload["recipes"]] == ["R3", "M16B"]
    # Same name, different fab => genuinely different generated tables.
    assert payload["recipes"][0]["parameters"] != payload["recipes"][1]["parameters"]


# ── recipe open can FAIL at home, the way it fails at the office ─────────────


def test_mock_refuses_a_bare_recipe_name_the_way_the_office_does():
    """`recipe_id` is the `class/recipe` full_name; the bare half names nothing.

    Confirmed office behaviour, not a mock invention: the location sources key
    on full_name, so a caller that dropped the class gets a LookupError -> 502.
    Home used to answer a confident 200 for the bare half, which is how the
    `recipeView.ts` class-name defect reached the office on 2026-08-18 with every
    home test green.
    """
    with pytest.raises(LookupError, match="No .idp location"):
        mock.get_recipe_open_data("DEAE_ABC123_PROD_00001", "R3", "cd-sem")


def test_mock_locatability_is_stable_for_a_given_recipe():
    # A mock that failed at random would be untestable and would teach nothing.
    name = "RACE/DEAE_ABC123_PROD_00001"
    first = mock.get_recipe_open_data(name, "R3", "cd-sem")
    second = mock.get_recipe_open_data(name, "R3", "cd-sem")
    assert first["idp_image_info"] == second["idp_image_info"]
    assert all(
        mock._is_locatable(name, "R3", "cd-sem") for _ in range(5)
    )


def test_mock_all_well_formed_recipes_are_locatable():
    """Every well-formed name this mock generates is openable.

    Home dev used to hit a 502 on ~1 in 5 recipe opens (the seeded
    never-measured, never-registered slice). The fabrication added no
    value — the office adapter handles its own location resolution — and
    made the home path painful to develop against. The bare-name refusal
    (no `class/` prefix) still applies, because that one mirrors a real
    office contract: location hashes key on `full_name`, the `class/recipe`
    form.
    """
    rows = [r["recipe_name"] for r in mock.get_recipe_catalog("cd-sem", ["R3"])["rows"]]
    assert rows, "mock catalog must not be empty"
    unlocatable = [n for n in rows if not mock._is_locatable(n, "R3", "cd-sem")]
    assert not unlocatable, (
        f"mock has {len(unlocatable)} unlocatable well-formed name(s); the "
        "home dev path should never refuse a name the catalog returned. "
        f"First 3: {unlocatable[:3]}"
    )
    # And every well-formed name the catalog returns actually opens.
    for name in rows[:20]:
        detail = mock.get_recipe_open_data(name, "R3", "cd-sem")
        assert detail["recipe_id"] == name
