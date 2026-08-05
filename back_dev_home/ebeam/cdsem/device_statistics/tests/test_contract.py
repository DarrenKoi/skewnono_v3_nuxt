"""Contract gate for device_statistics. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/cdsem/device_statistics
Office: SKEWNONO_DEVICE_STATISTICS_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/cdsem/device_statistics

providers/office_example.py is still a stub, so the office command above fails
with its NotImplementedError rather than a contract violation — that is the
adapter being unwritten, not this gate being wrong.

This is the one feature of the seven that legitimately keys on `fac_id` rather
than `fab_name` (MIGRATION.md), and the join across r3_device_grp /
device_desc / recipe_params has to hold under either provider — that is
asserted unfenced. What is NOT provider-independent is that the tables have
ROWS at all: the mock fabricates them from a fixed RNG seed, while the office
source can return nothing for a lot list. Those assumptions are fenced behind
get_data_provider("device_statistics") == "mock", and the lookups that need a
sample row skip instead of failing when the active provider has none.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.cdsem.device_statistics import data
from back_dev_home.ebeam.cdsem.device_statistics.contracts import (
    DeviceDescRow,
    MeasActivityRow,
    R3DeviceGrpRow,
    RecipeParamsRow,
    RuleVersion,
    TrendBucket,
)
from back_dev_home.ebeam.cdsem.device_statistics.providers.recipe_population import (
    is_exempt_job,
)


def _is_mock() -> bool:
    return get_data_provider("device_statistics") == "mock"


def _sample_lot_cd() -> str:
    """A real lot code, derived from live data rather than hardcoded.

    The mock's r3_device_grp is generated from a fixed RNG seed and always has
    rows; an office source can return none, and there is then no lot_cd to key
    the recipe/trend lookups off.
    """
    rows = data.get_r3_device_grp()
    if not rows:
        pytest.skip("active provider returned no r3_device_grp rows")
    return rows[0]["lot_cd"]


def test_r3_device_grp_matches_contract():
    rows = data.get_r3_device_grp()
    assert_matches(rows, list[R3DeviceGrpRow])
    if _is_mock():
        # Fixed RNG seed (20260426) — an empty table means the generator broke.
        assert rows, "mock r3_device_grp must not be empty"


def test_device_desc_matches_contract():
    rows = data.get_device_desc()
    assert_matches(rows, list[DeviceDescRow])
    if _is_mock():
        # Same fabricated source as r3_device_grp above.
        assert rows, "mock device_desc must not be empty"


def test_meas_activity_matches_contract():
    rows = data.get_meas_activity("R3")
    assert_matches(rows, list[MeasActivityRow])

    # 계약이 정렬(meas_count 내림차순)을 약속합니다 — 화면의 "측정 상위 N" 이
    # 앞에서 N 개를 자르는 근거이므로, 순서가 깨지면 필터가 조용히 틀립니다.
    counts = [row["meas_count"] for row in rows]
    assert counts == sorted(counts, reverse=True), "meas-activity must be sorted desc"
    assert all(count >= 0 for count in counts)

    if _is_mock():
        assert rows, "mock meas_activity must not be empty for R3"
        # mock 순위는 카탈로그의 lot 만 다룹니다. office 는 카탈로그에 없는
        # lot_cd 가 순위에 있을 수 있어(hist 에만 존재) 이 포함관계를
        # 강제하지 않습니다 — 화면이 교집합을 취합니다.
        catalog = {row["lot_cd"] for row in data.get_r3_device_grp()}
        assert {row["lot_cd"] for row in rows} <= catalog


def test_meas_activity_unknown_fab_is_empty():
    # fab 축이 없는 순위는 의미가 없고, 알 수 없는 fab 이 다른 fab 의 순위로
    # 해석되면 안 됩니다. 어느 provider 든 빈 배열이 정답입니다.
    assert data.get_meas_activity("does-not-exist") == []


def test_recipe_params_matches_contract():
    # Narrowed to a single lot_cd — an unfiltered call fans out over every
    # known lot (thousands) and is not a real usage pattern; the frontend
    # always joins a user-selected lot list before calling. See MIGRATION.md.
    lot_cd = _sample_lot_cd()
    rows = data.get_recipe_params([lot_cd])
    assert_matches(rows, list[RecipeParamsRow])

    # The lot_cd filter is the join key the whole feature is built on
    # (MIGRATION.md: fac_id/lot_cd must stay joinable across all three tables).
    # A row for a lot nobody asked for would land in the wrong device panel.
    for row in rows:
        assert row["lot_cd"] == lot_cd
        assert all(param["point_count"] >= 0 for param in row["parameters"])

    if _is_mock():
        # Every mock lot has fabricated recipes behind it; a real lot can have
        # no recipe rows yet.
        assert rows, "mock recipe_params must not be empty for a known lot"


def test_parameter_order_is_the_recipe_order_not_alphabetical():
    """``parameters`` 순서는 recipe 가 적어 둔 순서 그대로여야 합니다.

    순서 자체가 정보입니다 — WAFER 계열이 맨 앞에 오는 것이 관례이고, drill 을
    펼친 엔지니어가 위에서부터 읽습니다 (user-confirmed 2026-08-05). 이름순으로
    정렬하면 "WAFER" 가 알파벳상 거의 끝이라 **가장 중요한 파라미터가 목록 맨
    아래로** 밀립니다. office 어댑터가 실제로 그랬습니다.

    두 표면 모두에 걸리는 계약이라 여기서 지킵니다 — mock 은 WAFER 를 먼저
    만들고, office 는 _source dict 의 삽입 순서를 그대로 냅니다.
    """
    rows = data.get_recipe_params([_sample_lot_cd()])
    if not rows:
        pytest.skip("no recipe rows for this lot")

    for row in rows:
        names = [param["name"] for param in row["parameters"]]
        if len(names) < 2:
            continue
        assert names != sorted(names) or len(set(names)) == 1, (
            f"{row['recipe_id']} 의 파라미터가 이름순입니다 — 원본 순서가 "
            f"정렬로 덮였을 수 있습니다: {names}"
        )
        if _is_mock():
            # mock 은 WAFER → LEVEL → EDGE → OTHER 순으로 만듭니다.
            assert names[0].startswith("WAFER"), names


def test_exempt_jobs_measure_at_a_different_scale():
    """특수 측정 job(_WCDU/_FCDU/_FULL/_HALF)은 정상 recipe 보다 훨씬 크게 잽니다.

    프론트엔드가 이 job 들을 outlier 중앙값 기준선에서 빼는 이유가 바로 이
    규모 차이입니다 (outlierDetect.ts). mock 이 같은 규모로 만들면 그 회귀가
    집에서 조용히 통과합니다.
    """
    if not _is_mock():
        pytest.skip("office 값은 우리가 정하지 않습니다")

    rows = data.get_recipe_params([_sample_lot_cd()])
    exempt_points: list[int] = []
    normal_points: list[int] = []
    for row in rows:
        target = (
            exempt_points
            if is_exempt_job(row["recipe_id"])
            else normal_points
        )
        target.extend(param["point_count"] for param in row["parameters"])

    assert exempt_points, "mock 이 특수 job 을 하나도 만들지 않았습니다"
    assert normal_points
    assert max(exempt_points) > max(normal_points), (
        "특수 job 이 정상 recipe 와 같은 규모면 outlier 제외 규칙이 무의미합니다"
    )


def test_weekly_trend_data_matches_contract():
    # Same narrowing rationale as recipe_params above.
    lot_cd = _sample_lot_cd()
    trend = data.get_weekly_trend_data([lot_cd])
    assert_matches(trend, dict[str, TrendBucket])

    # Whatever the source, every summary row in a bucket must belong to the
    # lot that was asked for — the route keys the chart series off it.
    for bucket in trend.values():
        for summary in bucket["all_summary"]:
            assert summary["lot_cd"] == lot_cd
            assert summary["avail_recipe"] <= summary["total_recipe"]

    if _is_mock():
        # Byte-identical per (lot_cd, date_index) from the seeded generator, so
        # an empty trend means it broke. An office lot can have no history.
        assert trend, "mock weekly trend must not be empty for a known lot"


def test_rules_matches_contract():
    # Provider-independent: BOTH providers serve the same in-code seed
    # (providers/rules.py) — in-app rule editing was dropped 2026-08-04, so
    # there is no "published elsewhere" state and R3 must always resolve.
    rules = data.get_rules("R3")
    assert rules is not None, "the R3 rule seed must resolve under any provider"

    assert_matches(rules, RuleVersion)
    assert rules["thresholds"]["yellow_at"] <= rules["thresholds"]["red_at"]
    # ruleEngine.selectorMatches does first-match selection over `cells`, so a
    # duplicated cell id makes which rule wins depend on load order.
    ids = [cell["id"] for cell in rules["cells"]]
    assert len(set(ids)) == len(ids), "rule cell ids must be unique"


def test_rules_unknown_fab_returns_none():
    # Provider-independent: the route turns None into a 404, so an unknown fab
    # must never resolve to some other fab's caps.
    assert data.get_rules("does-not-exist") is None
