"""Office storage adapter tests.

These exercise the TRACKED template (`office_example`), never the gitignored
`office.py`, and never touch a cluster: every test feeds a fabricated
DataFrame to the pure normalizer and monkeypatches `get_sem_list`.

Regression context: at the office the storage DataFrame's own fab_name
column carried fac-level names (e.g. "M16"), so the sidebar's fab_name
filter ("M16A") matched nothing — every fab except R3 (whose fab_name
equals its fac_id) rendered an empty 스토리지 table while the sem_list
tool list worked. The adapter now resolves fab_name/fac_id from sem_list
by eqp_ip, the same join get_ppid_unavailable already relies on.
"""

import pandas as pd
import pytest

from back_dev_home.ebeam.hitachi.storage.providers import office_example as office


def _df(rows: list[dict]) -> pd.DataFrame:
    base = {
        "eqp_id": "ECDX100",
        "eqp_ip": "177.1.1.1",
        "fac_id": "M16",
        "total": "800G",
        "used": "400G",
        "avail": "400G",
        "percent": "50%",
        "storage_mt": "2026-07-20T04:30:00",
        "rcp_counts": 1000,
        "rcp_counts_mt": "2026-07-20T04:30:00",
        "storage_mt_date": "2026-07-20",
        "fab_name": "M16",
        "eqp_model_cd": "CG6300",
    }
    return pd.DataFrame([{**base, **row} for row in rows])


def _sem_row(**overrides) -> dict:
    row = {
        "fac_id": "M16",
        "eqp_id": "ECDX100",
        "eqp_model_cd": "CG6300",
        "eqp_grp_id": "G-ECD-01",
        "vendor_nm": "HITACHI",
        "eqp_ip": "177.1.1.1",
        "fab_name": "M16A",
        "updt_dt": "2026-07-20T00:00:00Z",
        "available": "On",
        "version": "1A",
    }
    row.update(overrides)
    return row


def test_fab_filter_matches_via_sem_list_when_the_df_carries_fac_level_names(monkeypatch):
    # The office DF says "M16" (fac-level); sem_list knows the tool lives in M16A.
    monkeypatch.setattr(office, "get_sem_list", lambda: [_sem_row()])
    df = _df([{"fab_name": "M16", "fac_id": "M16"}])

    rows = office._normalize_storage(df, "v3_df_ppid_storage_cdsem", ["M16A"])

    assert len(rows) == 1
    assert rows[0]["fab_name"] == "M16A"


def test_unfiltered_rows_also_carry_the_sem_list_fab_name(monkeypatch):
    # StorageView re-asserts row.fab_name === props.fab client-side, so the
    # correction must apply even when no fab filter reaches the adapter.
    monkeypatch.setattr(office, "get_sem_list", lambda: [_sem_row()])
    df = _df([{"fab_name": "M16"}])

    rows = office._normalize_storage(df, "v3_df_ppid_storage_cdsem", None)

    assert rows[0]["fab_name"] == "M16A"
    assert rows[0]["fac_id"] == "M16"


def test_rows_without_a_sem_list_match_keep_their_own_fab_name(monkeypatch):
    # A decommissioned tool still reporting storage must stay visible under
    # whatever fab the DF claims, not vanish because the fleet forgot it.
    monkeypatch.setattr(office, "get_sem_list", lambda: [])
    df = _df([{"fab_name": "R3", "fac_id": "R3", "eqp_ip": "177.9.9.9"}])

    rows = office._normalize_storage(df, "v3_df_ppid_storage_cdsem", ["R3"])

    assert len(rows) == 1
    assert rows[0]["fab_name"] == "R3"


def test_blank_sem_list_fab_name_falls_back_to_the_df_value(monkeypatch):
    monkeypatch.setattr(
        office, "get_sem_list", lambda: [_sem_row(fab_name="")]
    )
    df = _df([{"fab_name": "M16"}])

    rows = office._normalize_storage(df, "v3_df_ppid_storage_cdsem", None)

    assert rows[0]["fab_name"] == "M16"


def test_missing_columns_still_raise(monkeypatch):
    monkeypatch.setattr(office, "get_sem_list", lambda: [])
    df = _df([{}]).drop(columns=["percent"])

    with pytest.raises(ValueError, match="missing columns"):
        office._normalize_storage(df, "v3_df_ppid_storage_cdsem", None)
