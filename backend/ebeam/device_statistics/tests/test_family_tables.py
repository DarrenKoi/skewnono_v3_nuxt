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
from backend.ebeam.device_statistics.family_rules import (
    FAMILY_NORMAL_TOKENS,
    hv_param_type,
    is_family_normal_step,
    is_family_sample_recipe,
    lot_cd_from_prod_id,
)
from backend.ebeam.device_statistics.para_buckets import has_non_measurement_name
from backend.ebeam.device_statistics.providers.recipe_population import (
    IMAGE_STEP_SUFFIXES,
    ends_with_pure_cd,
    is_measuring,
    is_sample_recipe,
)
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
    by_recipe: dict[tuple[str, str], list[dict]] = {}
    for p in mock.get_family_params(family):
        by_recipe.setdefault((p["recipe_id"], p["fac_id"]), []).append(p)   # 표 B 한 벌
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
    assert any(p["mother"] for p in hv)
    # R4·S6 — 이름 파생이라 약 47% (접두사 5.68% + 토큰 41.1%) 만 종류가 있습니다.
    typed = sum(1 for p in hv if p["param_type"]) / len(hv)
    assert 0.40 < typed < 0.55, typed
    assert {p["param_type"] for p in hv} <= {"", "WAFER", "LEVEL", "EDGE", "EDGE_EX"}
    for family in ("veritysem", "provision"):
        rows = mock.get_family_params(family)
        assert all(p["mother"] is None and p["region"] is None for p in rows)
        assert any(p["param_type"] for p in rows)


@pytest.mark.parametrize("family", FAMILIES)
def test_steps_follow_r3_vs_mfab_shape(family):
    steps = mock.get_family_steps(family)
    # planstep 경로는 fac_id 가 아니라 prod_id 로 가립니다 — R4 device 가 섞여 있습니다.
    r3 = [s for s in steps if s["prod_id"]]
    m = [s for s in steps if not s["prod_id"]]
    assert r3 and m
    assert {s["fac_id"] for s in r3} == {"R3", "R4"}
    assert len({s["lot_cd"] for s in r3 if s["fac_id"] == "R4"}) == 2
    assert all(
        s["oper_seq"] is None and s["samp_seq"] is None and s["skip_yn"] == "" and s["prod_id"] == ""
        for s in m
    )
    keys = [(s["prod_id"], s["oper_seq"], s["samp_seq"], s["oper_desc"]) for s in r3]
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


# ── 사무실 회신 2026-11-04 ────────────────────────────────────────────────


def test_skip_yn_domain_is_y_n_d():
    """계열 index 는 Y / N / D, 빈 값 0건. D 는 측정 중(N 과 같음)."""
    for family in FAMILIES:
        r3 = [s for s in mock.get_family_steps(family) if s["fac_id"] == "R3"]
        assert {s["skip_yn"] for s in r3} == {"Y", "N", "D"}, family
    assert is_measuring("D") and is_measuring("N") and not is_measuring("Y")
    assert is_family_normal_step("hv-sem", "CBL ETCH HV", "D")
    assert not is_family_normal_step("hv-sem", "CBL ETCH HV", "Y")


def test_cap_prod_ids_map_to_catalog_lot():
    assert lot_cd_from_prod_id("RH0V_CAP_BASE") == "RH0V"
    assert lot_cd_from_prod_id("REXA_BASE") == "REXA"
    assert lot_cd_from_prod_id("RCAP_BASE") == "RCAP"      # 이름 안의 CAP 은 그대로
    catalog = {r["lot_cd"] for r in mock.get_r3_device_grp()}
    for family in FAMILIES:
        r3 = [s for s in mock.get_family_steps(family) if s["fac_id"] == "R3"]
        cap = [s for s in r3 if s["prod_id"].endswith("_CAP_BASE")]
        assert cap, family
        assert all(lot_cd_from_prod_id(s["prod_id"]) == s["lot_cd"] for s in r3)
        assert {s["lot_cd"] for s in cap} <= catalog


def test_off_catalog_devices_appear():
    """Q11 B — 계열이 재는 device 일부는 카탈로그에 없습니다."""
    catalog = {r["lot_cd"] for r in mock.get_r3_device_grp()}
    for family in FAMILIES:
        r3_lots = {s["lot_cd"] for s in mock.get_family_steps(family) if s["fac_id"] == "R3"}
        assert r3_lots - catalog, family


def test_family_sample_rule_rejects_dense():
    assert is_family_sample_recipe("C/X_REXA_001_S")
    assert is_family_sample_recipe("C/X_REXA_001_SE")
    assert not is_family_sample_recipe("C/X_REXA_001_DENSE")
    assert not is_family_sample_recipe("C/X_REXA_001SE")
    recipes = {s["recipe_id"] for f in FAMILIES for s in mock.get_family_steps(f)}
    dense = {r for r in recipes if r.endswith("_DENSE")}
    assert dense and all(is_sample_recipe(r) for r in dense)      # CD-SEM 규칙은 오검출
    assert not any(is_family_sample_recipe(r) for r in dense)
    assert any(is_family_sample_recipe(r) for r in recipes)
    # 계열 Sample 은 전부 "_S" / "_SE" — "...1SE" 같은 CD-SEM 꼬리가 남지 않습니다.
    assert not any(r.endswith("SE") and not r.endswith(("_SE", "_DENSE")) for r in recipes)


def test_identity_duplicates_differ_by_oper_desc():
    for family in FAMILIES:
        r3 = [s for s in mock.get_family_steps(family) if s["fac_id"] == "R3"]
        by_key: dict = {}
        for s in r3:
            by_key.setdefault((s["prod_id"], s["oper_seq"], s["samp_seq"]), []).append(s["oper_desc"])
        dups = [descs for descs in by_key.values() if len(descs) > 1]
        assert dups, family
        assert all(len(set(descs)) == len(descs) for descs in dups)


def test_family_normal_rule_markers():
    assert is_family_normal_step("hv-sem", "CBL ETCH HV", "N")
    for desc in ("GT LINE CD_HV", "GT LINE CD2_HV", "GT LINE CD3_HV"):   # R1 — 53 step
        assert is_family_normal_step("hv-sem", desc, "N"), desc
    assert not is_family_normal_step("hv-sem", "GT LINE CD_HV(E)", "N")
    assert not is_family_normal_step("provision", "GT LINE X_CD", "N")  # "_" 로 쪼개지 않음
    assert not is_family_normal_step("hv-sem", "CBL ETCH CD", "N")    # HV 에 CD 표식 없음
    assert not is_family_normal_step("hv-sem", "ISO PTN HV(E)", "N")
    assert not is_family_normal_step("hv-sem", "CBL ETCH HV AVIS", "N")
    for desc in ("GT LINE CD", "GT LINE VERITY", "GT LINE VRT"):
        assert is_family_normal_step("veritysem", desc, "N"), desc
    assert is_family_normal_step("provision", "GT LINE PROV", "N")
    assert not is_family_normal_step("provision", "GT LINE VRT", "N")
    # CD-SEM 규칙은 그대로 — 계열 표식으로 넓어지지 않습니다.
    assert not ends_with_pure_cd("CBL ETCH HV") and ends_with_pure_cd("CBL ETCH CD")
    # mock 은 각 계열의 표식으로 끝나는 step 을 내고, HV-SEM 에는 CD 로 끝나는 step 이 없습니다.
    for family in FAMILIES:
        steps = mock.get_family_steps(family)
        normal = [s for s in steps if is_family_normal_step(family, s["oper_desc"], s["skip_yn"])]
        assert 0 < len(normal) < len(steps), family
        lasts = {s["oper_desc"].split()[-1] for s in normal}
        assert lasts == set(FAMILY_NORMAL_TOKENS[family]), family
    assert not any(ends_with_pure_cd(s["oper_desc"]) for s in mock.get_family_steps("hv-sem"))


def test_hv_params_carry_blank_and_duplicate_names():
    by_recipe: dict = {}
    for p in mock.get_family_params("hv-sem"):
        by_recipe.setdefault((p["recipe_id"], p["fac_id"]), []).append(p["param_name"])
    rows = [n for names in by_recipe.values() for n in names]
    assert 0.02 < rows.count("") / len(rows) < 0.08
    dup = sum(1 for names in by_recipe.values() if len([n for n in names if n]) > len({n for n in names if n}))
    assert 0.35 < dup / len(by_recipe) < 0.65


def test_hv_param_type_from_name_tokens():
    """R4 — 토큰 EX > ED/EDGE > WF > LV, 그다음 CD-SEM 접두사."""
    assert hv_param_type("L_EDGE_EX") == "EDGE_EX"      # EDGE 토큰도 있지만 EX 가 먼저
    assert hv_param_type("EDGE_L_EX") == "EDGE_EX"
    assert hv_param_type("L_ED") == "EDGE" and hv_param_type("EDGE_T") == "EDGE"
    assert hv_param_type("P2_WF") == "WAFER" and hv_param_type("WAFER1") == "WAFER"
    assert hv_param_type("P1_LV") == "LEVEL"
    assert hv_param_type("PT_2") == "" and hv_param_type("") == ""
    assert hv_param_type("WFX_1") == ""                 # 토큰 단위 — 부분 문자열이 아님


def test_hv_image_steps_are_a_third():
    steps = mock.get_family_steps("hv-sem")
    image = sum(1 for s in steps if s["oper_desc"].split()[-1] in IMAGE_STEP_SUFFIXES)
    assert 0.28 < image / len(steps) < 0.40


def test_r4_devices_are_the_same_two_in_every_family_and_in_r3_catalog():
    """S8 ABC / S9 A — R7QA·R7QC 는 세 계열 index 모두에, r3_device_grp 에 있습니다."""
    catalog = {r["lot_cd"] for r in mock.get_r3_device_grp()}
    per_family = [
        {s["lot_cd"] for s in mock.get_family_steps(f) if s["fac_id"] == "R4"} for f in FAMILIES
    ]
    assert per_family[0] == per_family[1] == per_family[2]
    assert len(per_family[0]) == 2 and per_family[0] <= catalog


@pytest.mark.parametrize("family", FAMILIES)
def test_table_b_has_one_set_per_recipe_and_fab(family):
    """S2 A — 표 B 는 (recipe_id, fac_id) 마다 한 벌이고, fab 은 그 recipe 를 쓰는 step 의 fab."""
    used: dict[str, set[str]] = {}
    for s in mock.get_family_steps(family):
        used.setdefault(s["recipe_id"], set()).add(s["fac_id"])
    sets: dict[str, dict[str, list[str]]] = {}
    for p in mock.get_family_params(family):
        sets.setdefault(p["recipe_id"], {}).setdefault(p["fac_id"], []).append(p["param_name"])
    assert all(set(fabs) == used[recipe] for recipe, fabs in sets.items())
    multi = [fabs for fabs in sets.values() if len(fabs) > 1]
    assert multi, "여러 fab 에 걸린 recipe 가 없으면 fab 축이 집에서 보이지 않습니다"
    differ = [fabs for fabs in multi if len({tuple(v) for v in fabs.values()}) > 1]
    assert 0 < len(differ) < len(multi)


def test_sizes_follow_office_counts():
    """3차 회신 숫자 — planstep lots / 카탈로그 밖 / _CAP_BASE / M fab lots."""
    catalog = {r["lot_cd"] for r in mock.get_r3_device_grp()}
    office = {"hv-sem": (193, 33, 64), "veritysem": (216, 19, 74), "provision": (294, 47, 71)}
    for family, (lots, off, m_lots) in office.items():
        steps = mock.get_family_steps(family)
        planstep = {s["lot_cd"] for s in steps if s["prod_id"]}
        assert len(planstep) == lots and len(planstep - catalog) == off, family
        assert len({s["lot_cd"] for s in steps if s["prod_id"].endswith("_CAP_BASE")}) == 3
        assert abs(len({(s["fac_id"], s["lot_cd"]) for s in steps if not s["prod_id"]}) - m_lots) <= 3
