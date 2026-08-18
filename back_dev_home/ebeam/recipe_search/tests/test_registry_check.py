"""registry-check: is a recipe backed by the Redis recipe registry?

The endpoint exists because the frontend was inferring that from catalog-list
membership. The two are different Redis hashes written by different jobs, so
this gate is about the ANSWER being asked of the right source — the tests below
pin the subset relation (registry ⊆ locatable) that makes a True answer safe to
act on, and the office adapter's use of `_locate_via_redis` rather than
`_locate_idp`, which is the same distinction on the other side of the swap.
"""

import pytest
from flask import Flask

from back_dev_home.ebeam.recipe_search import data, routes
from back_dev_home.ebeam.recipe_search.contracts import RegistryCheckResponse
from back_dev_home.ebeam.recipe_search.providers import mock, office_example
from back_dev_home._core.contract_check import assert_matches


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/api")
    return app.test_client()


def _catalog_name(fab: str = "R3") -> str:
    return mock.get_recipe_catalog("cd-sem", (fab,))["rows"][0]["recipe_name"]


# ── contract ──────────────────────────────────────────────────────────────


def test_registry_check_matches_contract():
    payload = data.check_recipe_registry("cd-sem", [
        {"recipe_name": _catalog_name(), "fab_name": "R3"},
    ])
    assert_matches(payload, RegistryCheckResponse)
    assert payload["tool_type"] == "cd-sem"


def test_result_order_and_length_follow_the_request():
    items = [
        {"recipe_name": "ADI/A", "fab_name": "R3"},
        {"recipe_name": "ADI/B", "fab_name": "M16B"},
        {"recipe_name": "ADI/A", "fab_name": "M16B"},
    ]
    results = data.check_recipe_registry("cd-sem", items)["results"]
    # Positional, not keyed: the same recipe name appears under two fabs, so a
    # caller that matched results back by name alone would cross the two.
    assert [(r["recipe_name"], r["fab_name"]) for r in results] == [
        ("ADI/A", "R3"), ("ADI/B", "M16B"), ("ADI/A", "M16B"),
    ]


def test_reason_is_empty_exactly_when_in_registry():
    names = [f"ADI/CD_BIAS_{index:03d}" for index in range(40)]
    results = data.check_recipe_registry(
        "cd-sem", [{"recipe_name": name, "fab_name": "R3"} for name in names]
    )["results"]
    assert any(row["in_registry"] for row in results), "mock never says yes"
    assert any(not row["in_registry"] for row in results), "mock never says no"
    for row in results:
        assert bool(row["reason"]) is not row["in_registry"]


# ── mock: the registry is a strict subset of what is locatable ────────────


def test_mock_registry_membership_implies_locatable():
    for index in range(200):
        name = f"ADI/SUBSET_{index:04d}"
        if mock._is_in_registry(name, "R3", "cd-sem"):
            assert mock._is_locatable(name, "R3", "cd-sem"), (
                f"{name} is registry-backed but not locatable — recipe-open "
                "would refuse a recipe this endpoint told the client to unlock"
            )


def test_mock_bare_recipe_name_is_never_in_the_registry():
    # The office keys the registry on full_name; the bare half names nothing.
    results = data.check_recipe_registry("cd-sem", [
        {"recipe_name": "ADI_CD_BIAS_001", "fab_name": "R3"},
    ])["results"]
    assert results[0]["in_registry"] is False
    assert "class prefix" in results[0]["reason"]


def test_mock_answer_is_stable_for_the_same_recipe():
    item = [{"recipe_name": "ADI/STABLE_0001", "fab_name": "R3"}]
    first = data.check_recipe_registry("cd-sem", item)["results"][0]
    second = data.check_recipe_registry("cd-sem", item)["results"][0]
    assert first == second


def test_mock_answer_is_per_fab():
    # A registry hash exists per (family, fab), so the same name can be in one
    # fab's and absent from another's.
    names = [f"ADI/PERFAB_{index:04d}" for index in range(60)]
    r3 = {
        row["recipe_name"]: row["in_registry"]
        for row in data.check_recipe_registry(
            "cd-sem", [{"recipe_name": n, "fab_name": "R3"} for n in names]
        )["results"]
    }
    m16b = {
        row["recipe_name"]: row["in_registry"]
        for row in data.check_recipe_registry(
            "cd-sem", [{"recipe_name": n, "fab_name": "M16B"} for n in names]
        )["results"]
    }
    assert r3 != m16b


# ── office: the registry only, never the meas_hist fallback ───────────────


def test_office_check_never_queries_meas_hist(monkeypatch):
    """The narrowness IS the contract.

    `_locate_idp` would answer "yes, findable" for a recipe only a measurement
    run can place. Promoting on that would hand recipe-open a recipe whose
    location came from history — reachable, but not Redis-backed, which is what
    the caller is asking about.
    """
    def _boom(*_args, **_kwargs):
        raise AssertionError("registry-check queried measurement history")

    monkeypatch.setattr(office_example, "_locate_via_meas_hist", _boom)
    monkeypatch.setattr(
        office_example, "_locate_via_redis",
        lambda _tool, _recipe, _fab, notes=None: None,
    )
    payload = office_example.check_recipe_registry(
        "cd-sem", [{"recipe_name": "ADI/X", "fab_name": "R3"}]
    )
    assert payload["results"][0]["in_registry"] is False


def test_office_check_carries_the_registry_bail_reason(monkeypatch):
    def _declines(_tool, _recipe, _fab, notes=None):
        if notes is not None:
            notes.append("v3_cdsem_rcp_loc_r3 has no usable [idw, idp] entry")
        return None

    monkeypatch.setattr(office_example, "_locate_via_redis", _declines)
    payload = office_example.check_recipe_registry(
        "cd-sem", [{"recipe_name": "ADI/X", "fab_name": "r3"}]
    )
    row = payload["results"][0]
    assert row["in_registry"] is False
    assert "v3_cdsem_rcp_loc_r3" in row["reason"]
    # Uppercased on the way in, like every other fab-carrying body.
    assert row["fab_name"] == "R3"


def test_office_check_reports_success_without_a_reason(monkeypatch):
    monkeypatch.setattr(
        office_example, "_locate_via_redis",
        lambda _tool, _recipe, _fab, notes=None: [object()],
    )
    payload = office_example.check_recipe_registry(
        "cd-sem", [{"recipe_name": "ADI/X", "fab_name": "R3"}]
    )
    assert payload["results"][0] == {
        "recipe_name": "ADI/X", "fab_name": "R3",
        "in_registry": True, "reason": "",
    }


# ── route ─────────────────────────────────────────────────────────────────


def test_route_returns_one_result_per_requested_recipe(client):
    res = client.post("/api/cdsem/recipe-search/registry-check", json={
        "recipes": [
            {"recipe_name": _catalog_name(), "fab_name": "R3"},
            {"recipe_name": "ADI_CD_BIAS_001", "fab_name": "R3"},
        ]
    })
    assert res.status_code == 200
    assert len(res.get_json()["results"]) == 2


def test_route_rejects_an_unknown_tool_slug(client):
    res = client.post("/api/nope/recipe-search/registry-check", json={
        "recipes": [{"recipe_name": "ADI/X", "fab_name": "R3"}]
    })
    assert res.status_code == 400


@pytest.mark.parametrize("body,message", [
    ({}, "non-empty list"),
    ({"recipes": []}, "non-empty list"),
    ({"recipes": ["ADI/X"]}, "must be objects"),
    ({"recipes": [{"fab_name": "R3"}]}, "need a recipe_name"),
])
def test_route_rejects_a_malformed_body(client, body, message):
    res = client.post("/api/cdsem/recipe-search/registry-check", json=body)
    assert res.status_code == 400
    assert message in res.get_json()["error"]


def test_route_caps_the_batch(client):
    res = client.post("/api/cdsem/recipe-search/registry-check", json={
        "recipes": [
            {"recipe_name": f"ADI/X{index}", "fab_name": "R3"}
            for index in range(routes._MAX_RECIPE_ITEMS + 1)
        ]
    })
    assert res.status_code == 400
    assert "200-recipe limit" in res.get_json()["error"]


def test_compare_still_rejects_a_malformed_body(client):
    # The body parser is now shared; compare's own guard must not have moved.
    res = client.post("/api/cdsem/recipe-search/compare", json={"recipes": []})
    assert res.status_code == 400
