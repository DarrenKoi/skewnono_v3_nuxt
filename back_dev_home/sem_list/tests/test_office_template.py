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
    return pd.DataFrame([{**base, **row} for row in rows])


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
