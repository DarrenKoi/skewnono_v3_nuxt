"""`_shape` 의 집계 규칙. 손으로 적은 raw 행과 문자 그대로의 기댓값만 씁니다."""

from datetime import date

import pytest

from backend.ebeam.recipe_usage.providers._shape import (
    WindowError,
    build_catalog,
    build_recipe_detail,
    build_status,
    family_roster,
)


SEM_ROWS = [
    {"eqp_id": "VCD1", "eqp_model_cd": "VERITYSEM_4", "fab_name": "M14A", "fac_id": "M14"},
    # fac_id 로 fab 을 추측하면 틀리는 조합입니다.
    {"eqp_id": "VCD2", "eqp_model_cd": "VERITYSEM_5", "fab_name": "R4", "fac_id": "R3"},
    {"eqp_id": "VCD3", "eqp_model_cd": " veritysem_4 ", "fab_name": "M14A", "fac_id": "M14"},
    # sem_list mock 은 eqp_id 를 몇 개 반복합니다: 먼저 나온 행이 이깁니다.
    {"eqp_id": "VCD1", "eqp_model_cd": "VERITYSEM_4", "fab_name": "M16B", "fac_id": "M16"},
    {"eqp_id": "PCD9", "eqp_model_cd": "PROVISION_10", "fab_name": "M14A", "fac_id": "M14"},
    {"eqp_id": "ECDX1", "eqp_model_cd": "CG6300", "fab_name": "M14A", "fac_id": "M14"},
]
ROSTER = family_roster(SEM_ROWS, "veritysem")

RCP = "FI/S2/POM/S2_POM"
ODD = "MON/S2/DAILY"  # "/" 가 2개뿐인 VeritySEM id


def _listed(eqp_id, recipe_id, fab_id, n_uses, first_used, last_used, **extra):
    return {
        "eqp_id": eqp_id, "fac_id": "ignored", "fab_name": "ignored", "fab_id": fab_id,
        "recipe_id": recipe_id, "n_uses": n_uses,
        "first_used": first_used, "last_used": last_used, **extra,
    }


def _used(dt, eqp_id, recipe_id, runs, wafers, meas_min, fail_runs, last_start=None):
    return {
        "dt": dt, "eqp_id": eqp_id, "fac_id": "ignored", "fab_name": "ignored",
        "recipe_id": recipe_id, "runs": runs, "wafers": wafers,
        "meas_min": meas_min, "fail_runs": fail_runs,
        "first_start": f"{dt} 00:00:01",
        "last_start": last_start or f"{dt} 12:00:00",
    }


LIST_ROWS = [
    # 같은 (eqp_id, recipe_id) 가 fab_id 두 개에 걸쳐 있습니다.
    _listed("VCD1", RCP, "M14A", 10, "2026-03-01 08:00:00", "2026-11-10 09:00:00"),
    _listed("VCD1", RCP, "C2", 5, "2025-01-05 10:00:00", "2026-02-27 23:00:00"),
    _listed("VCD3", RCP, "M14A", 2, "2026-05-01 00:00:00", "2026-05-02 00:00:00"),
    _listed("VCD2", RCP, "X1", 7, "2026-06-01 00:00:00", "2026-06-09 00:00:00"),
    _listed("VCD1", ODD, "M14A", 1, "2026-07-01 00:00:00", "2026-07-01 00:00:00"),
    _listed("GHOST", RCP, "M14A", 999, "2020-01-01 00:00:00", "2026-11-11 00:00:00"),
]
RESIDENT = {
    "VCD1": [RCP, "MON/INTERNAL/ONLY/HERE"],
    "GHOST": ["NOT/IN/THE/ROSTER"],
}


def test_roster_is_the_family_only_and_one_row_per_eqp_id():
    assert {eqp_id: tool.fab_name for eqp_id, tool in ROSTER.items()} == {
        "VCD1": "M14A", "VCD2": "R4", "VCD3": "M14A",
    }
    assert ROSTER["VCD3"].eqp_model_cd == "veritysem_4"


def test_catalog_sums_across_fab_id_and_unions_the_resident_hash():
    catalog = build_catalog("veritysem", (), ROSTER, LIST_ROWS, RESIDENT)

    assert catalog["tool_type"] == "veritysem"
    assert catalog["fab_names"] == []
    assert catalog["total"] == 4
    assert catalog["rows"] == [
        {
            "recipe_id": RCP, "fab_name": "M14A",
            "product_id": "", "layer_id": "", "recipe_name": "",
            "eqp_ids": ["VCD1", "VCD3"],
            "n_uses": 17,
            "first_used": "2025-01-05 10:00:00",
            "last_used": "2026-11-10 09:00:00",
            "source": "both",
        },
        {
            "recipe_id": RCP, "fab_name": "R4",
            "product_id": "", "layer_id": "", "recipe_name": "",
            "eqp_ids": ["VCD2"],
            "n_uses": 7,
            "first_used": "2026-06-01 00:00:00",
            "last_used": "2026-06-09 00:00:00",
            "source": "mes",
        },
        {
            "recipe_id": "MON/INTERNAL/ONLY/HERE", "fab_name": "M14A",
            "product_id": "", "layer_id": "", "recipe_name": "",
            "eqp_ids": ["VCD1"],
            "n_uses": 0, "first_used": None, "last_used": None,
            "source": "tool",
        },
        {
            # 4조각이 아닌 id 도 통짜로 그대로 나옵니다.
            "recipe_id": ODD, "fab_name": "M14A",
            "product_id": "", "layer_id": "", "recipe_name": "",
            "eqp_ids": ["VCD1"],
            "n_uses": 1,
            "first_used": "2026-07-01 00:00:00",
            "last_used": "2026-07-01 00:00:00",
            "source": "mes",
        },
    ]


def test_catalog_fab_filter_follows_the_roster_not_the_key_columns():
    catalog = build_catalog("veritysem", ("R4",), ROSTER, LIST_ROWS, RESIDENT)

    assert catalog["fab_names"] == ["R4"]
    assert [(row["recipe_id"], row["eqp_ids"]) for row in catalog["rows"]] == [
        (RCP, ["VCD2"]),
    ]


def test_catalog_carries_the_provision_split_columns_from_the_key():
    roster = family_roster(SEM_ROWS, "provision")
    rows = [_listed(
        "PCD9", "4S8/4S8_CBL_C0A_UPH_4P/AVIS", "M14A", 3,
        "2026-01-01 00:00:00", "2026-01-02 00:00:00",
        product_id="4S8", layer_id="4S8_CBL_C0A_UPH_4P", recipe_name="AVIS",
    )]

    row = build_catalog("provision", (), roster, rows, {})["rows"][0]

    assert (row["product_id"], row["layer_id"], row["recipe_name"]) == (
        "4S8", "4S8_CBL_C0A_UPH_4P", "AVIS",
    )


USAGE_ROWS = [
    _used("2026-11-08", "VCD1", RCP, 4, 40, 60.0, 1, "2026-11-08 20:00:00"),
    _used("2026-11-10", "VCD1", RCP, 2, 10, 0.0, 2, "2026-11-10 07:30:00"),  # 전부 no_jobend
    _used("2026-11-10", "VCD2", RCP, 3, 30, 45.5, 0, "2026-11-10 22:15:00"),
    _used("2026-11-10", "VCD1", ODD, 1, 5, 12.25, 0, "2026-11-10 03:00:00"),
    _used("2026-09-01", "VCD1", RCP, 1, 1, 9.0, 0),      # 희박한 초반부
    _used("2026-11-11", "GHOST", RCP, 50, 500, 900.0, 0),  # 명부에 없는 장비
]


def test_recipe_detail_lists_each_roster_tool_once_and_every_loaded_day():
    detail = build_recipe_detail(
        "veritysem", RCP, (), ROSTER, LIST_ROWS, USAGE_ROWS, RESIDENT
    )

    assert detail["recipe_id"] == RCP
    assert detail["tools"] == [
        {
            "eqp_id": "VCD1", "fab_name": "M14A", "n_uses": 15,
            "first_used": "2025-01-05 10:00:00",
            "last_used": "2026-11-10 09:00:00", "on_tool": True,
        },
        {
            "eqp_id": "VCD2", "fab_name": "R4", "n_uses": 7,
            "first_used": "2026-06-01 00:00:00",
            "last_used": "2026-06-09 00:00:00", "on_tool": False,
        },
        {
            "eqp_id": "VCD3", "fab_name": "M14A", "n_uses": 2,
            "first_used": "2026-05-01 00:00:00",
            "last_used": "2026-05-02 00:00:00", "on_tool": False,
        },
    ]
    assert detail["daily"] == [
        {"date": "2026-09-01", "runs": 1, "wafers": 1, "meas_min": 9.0, "fail_runs": 0},
        {"date": "2026-11-08", "runs": 4, "wafers": 40, "meas_min": 60.0, "fail_runs": 1},
        {"date": "2026-11-10", "runs": 5, "wafers": 40, "meas_min": 45.5, "fail_runs": 2},
    ]


def test_recipe_detail_for_a_resident_only_or_unknown_recipe():
    resident_only = build_recipe_detail(
        "veritysem", "MON/INTERNAL/ONLY/HERE", (), ROSTER, LIST_ROWS, USAGE_ROWS, RESIDENT
    )
    unknown = build_recipe_detail(
        "veritysem", "NOT/IN/THE/ROSTER", (), ROSTER, LIST_ROWS, USAGE_ROWS, RESIDENT
    )

    assert resident_only["tools"] == [{
        "eqp_id": "VCD1", "fab_name": "M14A", "n_uses": 0,
        "first_used": None, "last_used": None, "on_tool": True,
    }]
    assert resident_only["daily"] == []
    assert (unknown["tools"], unknown["daily"]) == ([], [])


def test_status_default_window_is_14_days_ending_at_the_latest_dt_with_rows():
    status = build_status(
        "veritysem", (), ROSTER, USAGE_ROWS, None, None, today=date(2026, 11, 12)
    )

    # GHOST 의 2026-11-11 행은 명부에 없으므로 anchor 를 밀지 못합니다.
    assert status["anchor_date"] == "2026-11-10"
    assert status["data_start"] == "2026-09-01"
    assert (status["start_date"], status["end_date"]) == ("2026-10-28", "2026-11-10")
    assert status["summary"] == {
        "runs": 10, "wafers": 85, "meas_min": 117.75, "fail_runs": 3,
        "fail_rate": 0.3, "avg_meas_min": 11.78,
        "recipe_count": 2, "active_tool_count": 2, "tool_count": 3,
    }


def test_status_daily_is_zero_filled_over_the_requested_window():
    status = build_status(
        "veritysem", (), ROSTER, USAGE_ROWS,
        date(2026, 11, 8), date(2026, 11, 11), today=date(2026, 11, 12),
    )

    assert status["daily"] == [
        {"date": "2026-11-08", "runs": 4, "wafers": 40, "meas_min": 60.0, "fail_runs": 1},
        {"date": "2026-11-09", "runs": 0, "wafers": 0, "meas_min": 0.0, "fail_runs": 0},
        {"date": "2026-11-10", "runs": 6, "wafers": 45, "meas_min": 57.75, "fail_runs": 2},
        {"date": "2026-11-11", "runs": 0, "wafers": 0, "meas_min": 0.0, "fail_runs": 0},
    ]


def test_status_ranks_recipes_and_keeps_the_idle_roster_tool_with_zeros():
    status = build_status(
        "veritysem", (), ROSTER, USAGE_ROWS, None, None, today=date(2026, 11, 12)
    )

    assert status["recipes"] == [
        {
            "recipe_id": RCP, "runs": 9, "wafers": 80, "meas_min": 105.5,
            "fail_runs": 3, "fail_rate": 0.3333, "avg_meas_min": 11.72,
            "eqp_ids": ["VCD1", "VCD2"], "fab_names": ["M14A", "R4"],
            "last_start": "2026-11-10 22:15:00",
        },
        {
            "recipe_id": ODD, "runs": 1, "wafers": 5, "meas_min": 12.25,
            "fail_runs": 0, "fail_rate": 0.0, "avg_meas_min": 12.25,
            "eqp_ids": ["VCD1"], "fab_names": ["M14A"],
            "last_start": "2026-11-10 03:00:00",
        },
    ]
    assert status["equipments"] == [
        {
            "eqp_id": "VCD1", "fab_name": "M14A", "eqp_model_cd": "VERITYSEM_4",
            "runs": 7, "wafers": 55, "meas_min": 72.25,
            "fail_runs": 3, "fail_rate": 0.4286, "avg_meas_min": 10.32,
            "recipe_count": 2, "top_recipe": RCP,
            "last_start": "2026-11-10 07:30:00",
        },
        {
            "eqp_id": "VCD2", "fab_name": "R4", "eqp_model_cd": "VERITYSEM_5",
            "runs": 3, "wafers": 30, "meas_min": 45.5,
            "fail_runs": 0, "fail_rate": 0.0, "avg_meas_min": 15.17,
            "recipe_count": 1, "top_recipe": RCP,
            "last_start": "2026-11-10 22:15:00",
        },
        {
            "eqp_id": "VCD3", "fab_name": "M14A", "eqp_model_cd": "veritysem_4",
            "runs": 0, "wafers": 0, "meas_min": 0.0,
            "fail_runs": 0, "fail_rate": 0.0, "avg_meas_min": 0.0,
            "recipe_count": 0, "top_recipe": None, "last_start": None,
        },
    ]


def test_status_fab_filter_scopes_the_sums_but_not_the_loaded_date_range():
    status = build_status(
        "veritysem", ("R4",), ROSTER, USAGE_ROWS, None, None, today=date(2026, 11, 12)
    )

    assert status["fab_names"] == ["R4"]
    assert (status["anchor_date"], status["data_start"]) == ("2026-11-10", "2026-09-01")
    assert status["summary"]["runs"] == 3
    assert status["summary"]["tool_count"] == 1
    assert [row["eqp_id"] for row in status["equipments"]] == ["VCD2"]


def test_status_with_no_rows_ends_yesterday_and_still_lists_the_roster():
    status = build_status(
        "veritysem", (), ROSTER, [], None, None, today=date(2026, 11, 12)
    )

    assert (status["anchor_date"], status["data_start"]) == (None, None)
    assert (status["start_date"], status["end_date"]) == ("2026-10-29", "2026-11-11")
    assert len(status["daily"]) == 14
    assert [row["eqp_id"] for row in status["equipments"]] == ["VCD1", "VCD2", "VCD3"]
    assert status["summary"]["fail_rate"] == 0.0


@pytest.mark.parametrize(("start", "end"), [
    (date(2026, 11, 10), date(2026, 11, 9)),
    (date(2025, 1, 1), date(2026, 11, 10)),
])
def test_status_refuses_a_reversed_or_over_long_window(start, end):
    with pytest.raises(WindowError):
        build_status("veritysem", (), ROSTER, USAGE_ROWS, start, end, today=date(2026, 11, 12))
