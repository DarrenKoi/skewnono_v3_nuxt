"""SCE mock shape + office_example normalization tests.

Pins the contract both providers share: the snapshot is a per-eqp
FileInfo/SemCond/ImgCond/SCEParam block plus a 360-entry Coefficients curve
(`docs/datatables/sce_setting.txt`); the history is one such block per
bidaily collection date for the selected tool, ascending, each carrying
``date``. A history doc for date D must equal a snapshot taken as-of D —
office-side both views come from the same collection run.
"""

from datetime import datetime, timedelta

from back_dev_home.ebeam.hitachi.hardware.providers.sce import mock, office_example


ANCHOR = datetime(2026, 5, 20, 9, 0)

BLOCKS = {"FileInfo", "SemCond", "ImgCond", "SCEParam", "Coefficients"}


# --- mock: snapshot ---------------------------------------------------------


def test_snapshot_blocks_and_faithful_file_info_keys():
    settings = mock.build_sce_settings("CDX001", "R3", ANCHOR)
    assert "CDX001" in settings
    for entry in settings.values():
        assert set(entry.keys()) == BLOCKS
        # Real FileInfo carries the SharpChar file pair, not FileName/Updated.
        assert set(entry["FileInfo"].keys()) == {"SharpCharFile", "BaseSharpCharFile"}
        coeffs = entry["Coefficients"]
        assert len(coeffs) == 360
        assert [c["index"] for c in coeffs] == list(range(360))
        assert all(len(c["values"]) == 2 for c in coeffs)


# --- mock: history ----------------------------------------------------------


def _history(days: int = 14):
    return mock.build_sce_history("CDX001", "R3", ANCHOR - timedelta(days=days), ANCHOR)


def test_history_is_bidaily_ascending_with_date():
    docs = _history()
    assert docs, "a 14-day window must contain bidaily snapshots"
    dates = [d["date"] for d in docs]
    assert dates == sorted(dates)
    parsed = [datetime.fromisoformat(d).date() for d in dates]
    assert all(day.toordinal() % 2 == 0 for day in parsed)
    for doc in docs:
        assert set(doc.keys()) == BLOCKS | {"date"}


def test_history_dates_stable_across_windows():
    # The office archive has fixed collection dates; a wider request window
    # must extend the series, not shift the existing dates.
    short = {d["date"] for d in _history(days=7)}
    long = {d["date"] for d in _history(days=21)}
    assert short <= long


def test_history_doc_matches_snapshot_for_same_date():
    doc = _history()[-1]
    as_of = datetime.fromisoformat(doc["date"])
    snapshot = mock.build_sce_settings("CDX001", "R3", as_of)["CDX001"]
    assert {k: v for k, v in doc.items() if k != "date"} == snapshot


# --- office_example: pure normalization helpers -----------------------------


def test_parse_fab_blob_json_and_pickle():
    import pickle

    fab_map = {"ECX001": {"SemCond": {"SemCond_No": "6"}}}
    assert office_example._parse_fab_blob(b'{"ECX001": {}}', "M15A") == {"ECX001": {}}
    assert office_example._parse_fab_blob(pickle.dumps(fab_map), "M15A") == fab_map


def test_parse_fab_blob_rejects_garbage_with_lookup_error():
    import pytest

    with pytest.raises(LookupError):
        office_example._parse_fab_blob(b"\x00\x01not-a-payload", "M15A")
    with pytest.raises(LookupError):  # valid pickle, wrong type
        import pickle

        office_example._parse_fab_blob(pickle.dumps([1, 2]), "M15A")


def test_normalize_coefficients_canonical_and_alternate_shapes():
    canonical = [{"index": 1, "values": [0.1, 0.9]}, {"index": 0, "values": [0.2, 0.8]}]
    out = office_example._normalize_coefficients(canonical)
    assert [c["index"] for c in out] == [0, 1]  # re-sorted ascending

    as_dict = {"0": [0.2, 0.8], "1": [0.1, 0.9]}
    assert office_example._normalize_coefficients(as_dict) == out

    bare_lists = [[0.2, 0.8], [0.1, 0.9]]
    assert office_example._normalize_coefficients(bare_lists) == out

    # Unparseable index / non-list values drop instead of crashing the tab.
    assert office_example._normalize_coefficients(
        [{"index": "x", "values": [1]}, {"index": 2, "values": "bad"}]
    ) == []
    assert office_example._normalize_coefficients(None) == []


def test_normalize_entry_keeps_blocks_and_drops_unknown():
    entry = {
        "FileInfo": {"SharpCharFile": "/HITACHI/a.dat"},
        "SemCond": {"SemCond_No": "6"},
        "ImgCond": "not-a-dict",
        "Coefficients": [{"index": 0, "values": [0.1, 0.9]}],
        "SomethingElse": {"x": 1},
    }
    out = office_example._normalize_entry(entry)
    assert set(out.keys()) == {"FileInfo", "SemCond", "Coefficients"}
