"""Office sem_list adapter tests.

These exercise the TRACKED template (`office_example`), never the gitignored
`office.py`, and never touch a cluster: every test feeds fabricated
DataFrames to the pure selector.
"""

import pandas as pd
import pytest

from back_dev_home.sem_list.providers import office_example as office


def _roster(rows: list[dict]) -> pd.DataFrame:
    base = {
        "fac_id": "M16",
        "eqp_id": "ECDX100",
        "eqp_model_cd": "CG6300",
        "eqp_grp_id": "G-ECD-01",
        "vendor_nm": "HITACHI",
        "eqp_ip": "177.1.1.1",
        "fab_name": "M16A",
        "updt_dt": "2026-07-20T00:00:00Z",
    }
    # `columns=` keeps the 8 identity columns even when `rows` is empty —
    # `pd.DataFrame([])` on its own has zero columns, which would make an
    # empty roster indistinguishable from a schema-less one. A real parquet
    # read of an empty office table always keeps its column names, so this
    # fixture should too.
    return pd.DataFrame(
        [{**base, **row} for row in rows], columns=list(base.keys())
    )


def _connected(eqp_ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"eqp_id": eqp_ids})


def test_pending_is_the_roster_minus_the_reachable_subset():
    roster = _roster([{"eqp_id": "ECDX100"}, {"eqp_id": "ECDX200"}])

    rows = office._select_pending(roster, _connected(["ECDX100"]))

    assert [row["eqp_id"] for row in rows] == ["ECDX200"]


def test_no_pending_tools_is_an_empty_list_not_an_error():
    roster = _roster([{"eqp_id": "ECDX100"}])

    assert office._select_pending(roster, _connected(["ECDX100"])) == []


def test_an_empty_roster_is_an_empty_list():
    assert office._select_pending(_roster([]), _connected([])) == []


def test_diff_is_on_eqp_id_not_eqp_ip():
    # eqp_id is the tool's name and always present; diffing on eqp_ip would
    # misclassify a tool whose IP was reassigned.
    roster = _roster([{"eqp_id": "ECDX200", "eqp_ip": "177.1.1.1"}])
    connected = pd.DataFrame({"eqp_id": ["ECDX100"], "eqp_ip": ["177.1.1.1"]})

    rows = office._select_pending(roster, connected)

    assert [row["eqp_id"] for row in rows] == ["ECDX200"]


def test_missing_roster_column_names_the_column():
    roster = _roster([{"eqp_id": "ECDX200"}]).drop(columns=["fab_name"])

    with pytest.raises(ValueError) as err:
        office._select_pending(roster, _connected([]))

    assert "fab_name" in str(err.value)
    assert office._ROSTER_KEY in str(err.value)


def test_missing_eqp_id_on_the_connected_frame_names_the_key():
    with pytest.raises(ValueError) as err:
        office._select_pending(_roster([{}]), pd.DataFrame({"eqp_ip": ["1.1.1.1"]}))

    assert "eqp_id" in str(err.value)
    assert office._REDIS_KEY in str(err.value)


def test_an_empty_roster_still_validates_the_connected_frame():
    # Regression: an early `roster.empty` return placed ahead of the
    # `connected` schema check would let a malformed `connected` frame slip
    # through silently whenever the roster happens to be empty. Schema
    # validation must not depend on how many rows the roster has.
    with pytest.raises(ValueError) as err:
        office._select_pending(_roster([]), pd.DataFrame({"eqp_ip": ["1.1.1.1"]}))

    assert "eqp_id" in str(err.value)
    assert office._REDIS_KEY in str(err.value)


def test_an_unknown_vendor_is_passed_through_not_rejected():
    # The opposite of get_sem_list's rule. This screen exists to surface tools
    # we have not onboarded, so a new vendor must appear rather than 502.
    roster = _roster([{"eqp_id": "ECDX200", "vendor_nm": "NEWVENDOR"}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["vendor_nm"] == "NEWVENDOR"


def test_a_blank_fab_name_survives_for_the_ui_to_bucket():
    roster = _roster([{"eqp_id": "ECDX200", "fab_name": ""}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["fab_name"] == ""


def test_a_timestamp_arrival_becomes_an_iso_string():
    roster = _roster([{"eqp_id": "ECDX200", "updt_dt": pd.Timestamp("2026-07-20")}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["updt_dt"] == "2026-07-20T00:00:00"


def test_bytes_cells_are_decoded_as_utf8():
    roster = _roster([{"eqp_id": "ECDX200", "fab_name": "R3".encode()}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["fab_name"] == "R3"


def test_a_nan_fab_name_normalizes_to_blank_not_the_string_nan():
    # Regression: a missing fab_name must bucket into the UI's 미배정 group,
    # not render as a fab row literally named "nan".
    roster = _roster([{"eqp_id": "ECDX200", "fab_name": float("nan")}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["fab_name"] == ""


def test_a_nan_eqp_ip_normalizes_to_blank_not_the_string_nan():
    # Regression: a missing eqp_ip must never reach the firewall-request IP
    # list as the fake value "nan".
    roster = _roster([{"eqp_id": "ECDX200", "eqp_ip": float("nan")}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["eqp_ip"] == ""


def test_a_none_text_field_normalizes_to_blank():
    roster = _roster([{"eqp_id": "ECDX200", "eqp_grp_id": None}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["eqp_grp_id"] == ""


def test_a_nat_updt_dt_normalizes_to_blank_not_the_string_nat():
    roster = _roster([{"eqp_id": "ECDX200", "updt_dt": pd.NaT}])

    rows = office._select_pending(roster, _connected([]))

    assert rows[0]["updt_dt"] == ""


def _normalizable(rows: list[dict]) -> pd.DataFrame:
    """`_roster` 에 `_normalize` 가 추가로 요구하는 두 컬럼을 더한 것입니다."""
    df = _roster([{"available": "on", "version": "1.2.3", **row} for row in rows])
    return df.assign(
        available=[row.get("available", "on") for row in rows],
        version=[row.get("version", "1.2.3") for row in rows],
    )


# ---------------------------------------------------------------------------
# NaN 셀 — parquet 의 미할당 값입니다. mock 은 "" 밖에 낼 수 없으므로 집에서는
# 이 분기가 보이지 않습니다.


def test_unassigned_cells_become_blank_not_the_string_nan():
    """`_to_text` 의 맨 `str()` 은 NaN 을 리터럴 "nan" 으로 만들었습니다.

    `_normalize_pending` 은 필드마다 이 가드를 이미 걸고 있었고, 그 docstring
    이 'a fake "nan" value must never appear' 라고 못박고 있습니다 — 정작
    주 경로인 `_normalize` 만 빠져 있었습니다. 새어 나가면 roster.norm("nan")
    이 "NAN" 이라는 유령 fab 을 만들고, storage 의 fleet 이 IP "nan" 으로
    키를 잡습니다.
    """
    roster = _normalizable([{"eqp_id": "ECDX100"}])
    for column in ("fac_id", "eqp_model_cd", "eqp_grp_id", "eqp_ip", "fab_name"):
        roster.loc[0, column] = None

    row = office._normalize(roster)[0]

    assert row["fac_id"] == ""
    assert row["eqp_model_cd"] == ""
    assert row["eqp_grp_id"] == ""
    assert row["eqp_ip"] == ""
    assert row["fab_name"] == ""
    assert "nan" not in repr(row).lower()


def test_surrounding_whitespace_is_stripped_from_identity_fields():
    roster = _normalizable([{"eqp_id": "  ECDX100 ", "fab_name": " M16A "}])
    row = office._normalize(roster)[0]
    assert row["eqp_id"] == "ECDX100"
    assert row["fab_name"] == "M16A"
