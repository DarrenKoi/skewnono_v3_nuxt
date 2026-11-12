"""Office adapter template (`providers/office_example.py`), without a cluster.

The tests import the tracked template, never the gitignored `office.py`, and
feed fabricated DataFrames / hash payloads to its normalizers. What they pin
is the adapter's whole job: hand `_shape` rows a mock could have produced,
whatever pandas made of the parquet (NaN, NaT, Timestamp, numpy ints).

The adapter has never run at the office; these cases are the nulls and dtypes
the home mock cannot emit.
"""

import datetime as dt

import pandas as pd
import pytest

from backend.ebeam.recipe_usage.providers import office_example as office
from backend.ebeam.recipe_usage.providers._shape import (
    FAMILY_KEYS,
    USAGE_COLUMNS,
    build_status,
    family_roster,
)


class _FakeRedis:
    def __init__(self, values=None, hashes=None):
        self.values = values or {}
        self.hashes = hashes or {}

    def get(self, key):
        return self.values.get(key)

    def hgetall(self, key):
        return self.hashes.get(key, {})


def _parquet(rows: list[dict]) -> bytes:
    return pd.DataFrame(rows).to_parquet()


USAGE = {
    "dt": "2026-11-10", "eqp_id": "VCD1", "fac_id": "M14", "fab_name": "M14A",
    "recipe_id": "FI/S2/POM/S2_POM", "runs": 3, "wafers": 30, "meas_min": 45.5,
    "fail_runs": 1, "first_start": "2026-11-10 01:00:00",
    "last_start": "2026-11-10 22:15:00",
}


def test_usage_key_round_trips_through_parquet_into_plain_python(monkeypatch):
    key = FAMILY_KEYS["veritysem"].usage_key
    monkeypatch.setattr(office, "redis_client", lambda: _FakeRedis({key: _parquet([USAGE])}))

    rows = office.load_usage_rows("veritysem")

    assert rows == [USAGE]
    assert [type(rows[0][c]) for c in ("runs", "wafers", "fail_runs", "meas_min")] == [
        int, int, int, float,
    ]


def test_list_key_reads_the_family_columns(monkeypatch):
    listed = {
        "eqp_id": "PCD9", "fac_id": "R3", "fab_name": "R4", "fab_id": "C2",
        "recipe_id": "4S8/4S8_CBL_C0A_UPH_4P/AVIS", "n_uses": 12,
        "first_used": "2026-01-01 00:00:00", "last_used": "2026-02-01 00:00:00",
        "product_id": "4S8", "layer_id": "4S8_CBL_C0A_UPH_4P", "recipe_name": "AVIS",
    }
    key = FAMILY_KEYS["provision"].list_key
    monkeypatch.setattr(
        office, "redis_client",
        lambda: _FakeRedis({key: _parquet([{**listed, "extra_column": 1}])}),
    )

    assert office.load_list_rows("provision") == [listed]


def test_nulls_and_datetime_columns_are_normalized_at_the_boundary():
    df = pd.DataFrame([
        {**USAGE, "dt": dt.date(2026, 11, 10), "runs": 3.0, "meas_min": None,
         "last_start": pd.Timestamp("2026-11-10 22:15:00"), "first_start": pd.NaT},
        {**USAGE, "eqp_id": None},
        {**USAGE, "recipe_id": float("nan")},
        {**USAGE, "eqp_id": " VCD2 ", "wafers": float("nan")},
    ])

    rows = office._normalize(df, "some_key", USAGE_COLUMNS)

    assert rows == [
        {**USAGE, "meas_min": 0.0, "first_start": "", "last_start": "2026-11-10 22:15:00"},
        {**USAGE, "eqp_id": "VCD2", "wafers": 0},
    ]
    assert type(rows[0]["runs"]) is int


def test_normalized_rows_feed_the_shared_shaping():
    df = pd.DataFrame([USAGE, {**USAGE, "eqp_id": "NOT_IN_ROSTER", "runs": 99}])
    roster = family_roster(
        [{"eqp_id": "VCD1", "eqp_model_cd": "VERITYSEM_4", "fab_name": "M14A"}],
        "veritysem",
    )

    status = build_status(
        "veritysem", (), roster, office._normalize(df, "k", USAGE_COLUMNS),
        None, None, today=dt.date(2026, 11, 12),
    )

    assert status["anchor_date"] == "2026-11-10"
    assert status["summary"]["runs"] == 3
    assert status["equipments"][0]["avg_meas_min"] == 15.17


def test_a_missing_key_is_an_upstream_error(monkeypatch):
    monkeypatch.setattr(office, "redis_client", lambda: _FakeRedis())

    with pytest.raises(LookupError, match="v3_df_verity_recipe_usage") as caught:
        office.load_usage_rows("veritysem")
    # The app factory maps only the bare type to a 502.
    assert type(caught.value) is LookupError


def test_missing_columns_are_an_upstream_error_naming_them():
    df = pd.DataFrame([USAGE]).drop(columns=["fail_runs"])

    with pytest.raises(LookupError, match="fail_runs") as caught:
        office._normalize(df, "some_key", USAGE_COLUMNS)
    assert type(caught.value) is LookupError


def test_resident_hash_is_json_per_tool_and_tolerates_junk(monkeypatch):
    name = FAMILY_KEYS["veritysem"].resident_hash
    monkeypatch.setattr(office, "redis_client", lambda: _FakeRedis(hashes={name: {
        b"VCD1": b'["FI/S2/POM/S2_POM", "MON/S2/DAILY", " "]',
        b"VCD2": b"not json",
        b"VCD3": b'{"a": 1}',
        b"VCD4": b"[]",
    }}))

    assert office.load_resident("veritysem") == {
        "VCD1": ["FI/S2/POM/S2_POM", "MON/S2/DAILY"],
        "VCD4": [],
    }


def test_an_absent_resident_hash_is_empty_not_an_error(monkeypatch):
    monkeypatch.setattr(office, "redis_client", lambda: _FakeRedis())

    assert office.load_resident("provision") == {}
