"""mock 응답이 계약과 맞는지, 그리고 mock 이 사무실 사실을 실제로 담는지.

두 번째 묶음이 있는 이유: 이 feature 의 규칙(fab_id 를 가로지른 합산, 4조각이
아닌 id, 실적 0 장비)은 mock 이 그 경우를 만들어 낼 때만 집에서 보입니다.
난수 범위를 건드려 그 경우가 사라지면 화면은 멀쩡해 보이고 규칙만 눈에서
사라집니다.
"""

from collections import Counter
from datetime import date, timedelta
from typing import get_type_hints

import pytest

from backend.ebeam.recipe_usage import contracts, data
from backend.ebeam.recipe_usage.providers import mock
from backend.ebeam.recipe_usage.providers._shape import (
    FAMILY_KEYS,
    USAGE_COLUMNS,
    family_roster,
)
from backend.sem_list.data import get_sem_list


FAMILIES = ("veritysem", "provision")


def _keys(typed_dict) -> set[str]:
    return set(get_type_hints(typed_dict))


def _assert_rows(rows, typed_dict):
    assert rows, f"no {typed_dict.__name__} rows to check"
    assert {frozenset(row) for row in rows} == {frozenset(_keys(typed_dict))}


@pytest.mark.parametrize("tool_type", FAMILIES)
def test_catalog_matches_the_contract(tool_type):
    catalog = data.get_catalog(tool_type, ())

    assert set(catalog) == _keys(contracts.CatalogResponse)
    assert catalog["total"] == len(catalog["rows"])
    _assert_rows(catalog["rows"], contracts.CatalogRow)
    assert {row["source"] for row in catalog["rows"]} == {"mes", "tool", "both"}
    for row in catalog["rows"]:
        assert (row["first_used"] is None) == (row["source"] == "tool")
        assert row["eqp_ids"] == sorted(row["eqp_ids"])


@pytest.mark.parametrize("tool_type", FAMILIES)
def test_recipe_detail_matches_the_contract(tool_type):
    recipe_id = mock.load_usage_rows(tool_type)[-1]["recipe_id"]

    detail = data.get_recipe_detail(tool_type, recipe_id, ())

    assert set(detail) == _keys(contracts.RecipeDetailResponse)
    _assert_rows(detail["tools"], contracts.RecipeToolRow)
    _assert_rows(detail["daily"], contracts.DailyPoint)
    assert all(point["runs"] > 0 for point in detail["daily"])


@pytest.mark.parametrize("tool_type", FAMILIES)
def test_status_matches_the_contract(tool_type):
    status = data.get_status(tool_type, (), None, None)

    assert set(status) == _keys(contracts.StatusResponse)
    assert set(status["summary"]) == _keys(contracts.StatusSummary)
    _assert_rows(status["daily"], contracts.DailyPoint)
    _assert_rows(status["recipes"], contracts.RecipeRankingRow)
    _assert_rows(status["equipments"], contracts.EquipmentRow)
    assert len(status["daily"]) == 14
    assert status["end_date"] == status["anchor_date"]
    # 최신 dt 는 전날입니다. 오늘 dt 는 없습니다.
    assert status["anchor_date"] == mock.ANCHOR_DATE.isoformat()
    assert mock.ANCHOR_DATE < date.today() + timedelta(days=1)
    roster = family_roster(get_sem_list(), tool_type)
    assert sorted(row["eqp_id"] for row in status["equipments"]) == sorted(roster)
    assert status["summary"]["tool_count"] == len(roster)
    assert status["summary"]["active_tool_count"] < len(roster)


def test_provision_ships_split_columns_and_veritysem_answers_blank():
    provision = data.get_catalog("provision", ())["rows"]
    verity = data.get_catalog("veritysem", ())["rows"]

    listed = [row for row in provision if row["source"] != "tool"]
    assert all(
        f"{row['product_id']}/{row['layer_id']}/{row['recipe_name']}" == row["recipe_id"]
        for row in listed
    )
    assert {
        (row["product_id"], row["layer_id"], row["recipe_name"]) for row in verity
    } == {("", "", "")}


@pytest.mark.parametrize("tool_type", FAMILIES)
def test_mock_rows_have_the_redis_column_shape(tool_type):
    keys = FAMILY_KEYS[tool_type]

    assert {frozenset(row) for row in mock.load_list_rows(tool_type)} == {
        frozenset(keys.list_columns)
    }
    assert {frozenset(row) for row in mock.load_usage_rows(tool_type)} == {
        frozenset(USAGE_COLUMNS)
    }


@pytest.mark.parametrize("tool_type", FAMILIES)
def test_mock_carries_the_office_facts(tool_type):
    listed = mock.load_list_rows(tool_type)
    used = mock.load_usage_rows(tool_type)
    roster = family_roster(get_sem_list(), tool_type)
    fab_names = {tool.fab_name for tool in roster.values()}

    pairs = Counter((row["eqp_id"], row["recipe_id"]) for row in listed)
    assert sum(1 for count in pairs.values() if count > 1) >= 5
    assert {"C2", "X1"} <= {row["fab_id"] for row in listed} - fab_names
    assert {(row["eqp_id"], row["recipe_id"]) for row in used} <= set(pairs)

    dts = sorted({row["dt"] for row in used})
    assert dts[-1] == mock.ANCHOR_DATE.isoformat()
    partition_start = mock.ANCHOR_DATE - timedelta(days=mock.PARTITION_DAYS - 1)
    assert dts[0] > partition_start.isoformat()
    per_day = Counter(row["dt"] for row in used)
    assert max(per_day[dt] for dt in dts[:5]) <= 2
    assert per_day[dts[-1]] > 10

    all_failed = [row for row in used if row["fail_runs"] == row["runs"]]
    assert len(all_failed) > len(used) // 10
    assert sum(1 for row in all_failed if row["meas_min"] == 0.0) > len(all_failed) // 2
    assert all(
        type(row["meas_min"]) is float and type(row["runs"]) is int for row in used
    )

    idle = set(roster) - {row["eqp_id"] for row in used}
    assert idle, "one roster tool must have no usage row"


def test_veritysem_mock_has_ids_that_are_not_four_parts_and_an_r3_r4_tool():
    listed = mock.load_list_rows("veritysem")

    slashes = Counter(row["recipe_id"].count("/") for row in listed)
    assert slashes[3] > 0
    assert sum(count for n, count in slashes.items() if n != 3) >= 4
    assert min(slashes) >= 2
    assert any(row["fac_id"] == "R3" and row["fab_name"] == "R4" for row in listed)


def test_mock_is_deterministic_per_family():
    mock._generate.cache_clear()
    first = mock.load_usage_rows("veritysem")
    mock._generate.cache_clear()

    assert mock.load_usage_rows("veritysem") == first
    assert mock.load_list_rows("veritysem") != mock.load_list_rows("provision")
