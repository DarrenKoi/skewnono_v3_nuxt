"""Rule 없는 계열 mock 표 A~D 가 사무실 요청서의 불변식을 지키는가.

요청서: docs/office-migration/to-office-device-statistics-families-261102.md
"""

from collections import Counter

import pytest

from backend.ebeam._tool_specs import model_to_tool_type
from backend.ebeam.device_statistics.contracts import (
    FamilyActivityRow,
    FamilyParamRow,
    FamilyRecipeStatusRow,
    FamilyStepRow,
)
from backend.ebeam.device_statistics.para_buckets import has_non_measurement_name
from backend.ebeam.device_statistics.providers import mock
from backend.sem_list.providers import mock as sem_list_mock

FAMILIES = ("hv-sem", "veritysem", "provision")


@pytest.mark.parametrize("family", FAMILIES)
def test_rows_match_contract_keys(family):
    for rows, contract in (
        (mock.get_family_steps(family), FamilyStepRow),
        (mock.get_family_params(family), FamilyParamRow),
        (mock.get_family_recipe_status(family), FamilyRecipeStatusRow),
        (mock.get_family_activity(family), FamilyActivityRow),
    ):
        assert rows, contract.__name__
        assert all(set(r) == set(contract.__annotations__) for r in rows), contract.__name__
        assert all(r["tool_type"] == family for r in rows)


@pytest.mark.parametrize("family", FAMILIES)
def test_status_covers_every_step_recipe_exactly_once(family):
    step_recipes = {r["recipe_id"] for r in mock.get_family_steps(family)}
    statuses = mock.get_family_recipe_status(family)
    assert sorted(s["recipe_id"] for s in statuses) == sorted(step_recipes)

    with_params = {p["recipe_id"] for p in mock.get_family_params(family)}
    ok = {s["recipe_id"] for s in statuses if s["status"] == "ok"}
    assert with_params == ok   # empty / not_found / failed 는 표 B 에 행이 없습니다
    for s in statuses:
        has_source = s["status"] in ("ok", "empty")
        assert bool(s["source_ref"]) == has_source and bool(s["source_tm"]) == has_source
        assert bool(s["note"]) == (s["status"] == "failed")


def test_all_four_statuses_appear_somewhere():
    seen = Counter(s["status"] for f in FAMILIES for s in mock.get_family_recipe_status(f))
    assert set(seen) == {"ok", "empty", "not_found", "failed"}


@pytest.mark.parametrize("family", FAMILIES)
def test_param_seq_is_dense_and_helpers_lead(family):
    by_recipe: dict[str, list[dict]] = {}
    for p in mock.get_family_params(family):
        by_recipe.setdefault(p["recipe_id"], []).append(p)
    helper_recipes = 0
    for params in by_recipe.values():
        assert [p["param_seq"] for p in params] == list(range(1, len(params) + 1))
        names = [has_non_measurement_name(p["param_name"]) for p in params]
        # Dummy·Align 은 맨 앞에 연속으로만 옵니다.
        assert names == sorted(names, reverse=True)
        helper_recipes += names[0]
    assert helper_recipes, "맨 앞 Dummy·Align 경로가 집에서 실행되지 않습니다"


def test_hvsem_has_mother_and_amat_has_type():
    hv = mock.get_family_params("hv-sem")
    assert any(p["mother"] for p in hv) and all(p["param_type"] == "" for p in hv)
    for family in ("veritysem", "provision"):
        rows = mock.get_family_params(family)
        assert all(p["mother"] is None and p["region"] is None for p in rows)
        assert any(p["param_type"] for p in rows)


@pytest.mark.parametrize("family", FAMILIES)
def test_steps_follow_r3_vs_mfab_shape(family):
    steps = mock.get_family_steps(family)
    r3 = [s for s in steps if s["fac_id"] == "R3"]
    m = [s for s in steps if s["fac_id"] != "R3"]
    assert r3 and m
    assert {s["skip_yn"] for s in r3} == {"Y", "N", ""}
    assert all(s["oper_seq"] is None and s["samp_seq"] is None and s["skip_yn"] == "" for s in m)
    keys = [(s["lot_cd"], s["oper_seq"], s["samp_seq"]) for s in r3]
    assert len(keys) == len(set(keys))
    # 한 device 안에서 recipe 재사용 — recipe_id 는 step 정체성이 아닙니다.
    assert len({(s["lot_cd"], s["recipe_id"]) for s in r3}) < len(r3)


@pytest.mark.parametrize("family", FAMILIES)
def test_eqp_ids_belong_to_the_family(family):
    family_eqps = {
        r["eqp_id"] for r in sem_list_mock.get_sem_list()
        if model_to_tool_type(r["eqp_model_cd"]) == family
    }
    assert {s["eqp_id"] for s in mock.get_family_steps(family)} <= family_eqps


def test_recipe_ids_collide_across_families():
    """같은 이름이 계열마다 다른 recipe — 조인 키가 (tool_type, recipe_id) 인 이유."""
    hv = {s["recipe_id"] for s in mock.get_family_steps("hv-sem")}
    pv = {s["recipe_id"] for s in mock.get_family_steps("provision")}
    assert hv & pv


@pytest.mark.parametrize("family", FAMILIES)
def test_activity_differs_from_step_devices_both_ways(family):
    step_lots = {(s["fac_id"], s["lot_cd"]) for s in mock.get_family_steps(family)}
    activity = mock.get_family_activity(family)
    act_lots = {(a["fac_id"], a["lot_cd"]) for a in activity}
    assert step_lots - act_lots, "계획은 있는데 최근 측정 없는 device"
    assert act_lots - step_lots, "측정은 있는데 step 원본 없는 device"
    for fab in {a["fac_id"] for a in activity}:
        counts = [a["meas_count"] for a in activity if a["fac_id"] == fab]
        assert counts == sorted(counts, reverse=True)
