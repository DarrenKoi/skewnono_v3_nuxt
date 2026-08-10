"""SCE mock shape + office_example normalization tests.

Pins the contract both providers share: the snapshot is a per-eqp
FileInfo/SemCond/ImgCond/SCEParam block plus a 360-entry Coefficients curve
(`docs/datatables/hardware_sce_setting.txt`); the history is one such block per
bidaily collection date for the selected tool, ascending, each carrying
``date``. A history doc for date D must equal a snapshot taken as-of D —
office-side both views come from the same collection run.
"""

import json
from datetime import datetime, timedelta

from back_dev_home.ebeam.hardware.providers.sce import mock, office_example


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


def _fingerprint(doc: dict, block: str) -> str:
    return json.dumps(doc[block], sort_keys=True)


def test_config_blocks_stable_for_the_tools_whole_life():
    # SemCond/ImgCond are tool configuration: in production they hold the same
    # values collection after collection AND across re-tunes, so the 시계열
    # param trend must render them as a flat "stable" line, not re-rolled noise.
    docs = _history(days=30)
    assert len(docs) >= 3, "need several collection dates to compare"
    for block in ("SemCond", "ImgCond"):
        assert len({_fingerprint(doc, block) for doc in docs}) == 1


def test_retune_outputs_step_at_retunes_rather_than_drifting_per_collection():
    # SCE is re-tuned at PM: between two re-tunes the tool serves the same
    # SharpChar file, so consecutive collections read back identical. A value
    # that changed on every collection date would be the old (wrong) model —
    # and would make the 버전 revision picker collapse nothing.
    docs = _history(days=120)
    assert len(docs) >= 10, "need a long window to span more than one re-tune"

    retunes = {day.isoformat() for day in mock._retune_dates("CDX001", ANCHOR.date())}
    for block in ("FileInfo", "SCEParam", "Coefficients"):
        prints = [_fingerprint(doc, block) for doc in docs]
        assert len(set(prints)) > 1, f"{block} must step at least once"
        assert len(set(prints)) < len(prints), f"{block} must hold between re-tunes"
        # Every step lands on a collection date whose era changed — i.e. a
        # re-tune happened in the gap since the previous collection.
        # strict=False: the pairwise idiom — docs[1:] is one shorter by design.
        for prev, cur in zip(docs, docs[1:], strict=False):
            if _fingerprint(prev, block) == _fingerprint(cur, block):
                continue
            assert any(
                prev["date"] < day <= cur["date"] for day in retunes
            ), f"{block} changed on {cur['date']} with no re-tune since {prev['date']}"


def test_retune_schedule_is_a_prefix_so_the_past_never_changes():
    # The property that makes history reproducible: extending the horizon only
    # APPENDS re-tunes, it never re-rolls earlier ones.
    short = mock._retune_dates("CDX001", ANCHOR.date())
    long = mock._retune_dates("CDX001", ANCHOR.date() + timedelta(days=400))
    assert len(long) > len(short), "a later horizon must reveal more re-tunes"
    assert long[: len(short)] == short
    # Every window a caller can ask for contains re-tunes, so the picker always
    # has something to collapse — the origin sits far enough back.
    assert [d for d in long if d > ANCHOR.date()]


def test_siblings_are_re_tuned_on_their_own_schedules():
    # The 비교 tab exists to show curves of differing ages side by side, which
    # only works if siblings do not all share one revision.
    settings = mock.build_sce_settings("CDX001", "R3", ANCHOR)
    assert len(settings) > 2
    curves = {_fingerprint(entry, "Coefficients") for entry in settings.values()}
    assert len(curves) > 1


def test_history_doc_matches_snapshot_for_every_date():
    # EVERY doc, not just the last. Checking only the newest hid a real
    # regression: when the revision salt was derived from the request window's
    # end, the two builders disagreed on every doc except the one whose date
    # happened to equal that end.
    docs = _history(days=60)
    assert len(docs) >= 10
    for doc in docs:
        as_of = datetime.fromisoformat(doc["date"])
        snapshot = mock.build_sce_settings("CDX001", "R3", as_of)["CDX001"]
        assert {k: v for k, v in doc.items() if k != "date"} == snapshot, doc["date"]


def test_history_values_do_not_change_when_the_window_moves():
    # The office archive file for a collection date is immutable — asking for a
    # different range must not rewrite the past. Guards the salt against being
    # re-derived from anything window-shaped.
    wide = {d["date"]: d for d in _history(days=120)}
    narrow = {d["date"]: d for d in _history(days=14)}
    later = {
        d["date"]: d
        for d in mock.build_sce_history(
            "CDX001", "R3", ANCHOR - timedelta(days=30), ANCHOR + timedelta(days=10)
        )
    }
    assert narrow and set(narrow) <= set(wide)
    for date_key, doc in narrow.items():
        assert doc == wide[date_key], date_key
    overlap = set(narrow) & set(later)
    assert overlap
    for date_key in overlap:
        assert narrow[date_key] == later[date_key], date_key


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


def test_office_coefficients_are_coerced_to_floats():
    """자매 계열(bsm/reso_center)은 이미 _as_float 를 거치는데 sce 만 원본을
    그대로 넘겼습니다.

    이 인덱스들은 측정값을 float 또는 숫자 문자열로 저장하므로, 문자열로 온
    커브가 `values: list[float]` 계약에 문자열인 채로 도달했습니다. mock 은
    반올림된 float 만 내보내므로 집에서는 볼 수 없습니다.
    """
    from back_dev_home.ebeam.hardware.providers.sce import office_example

    out = office_example._normalize_coefficients([
        {"index": 1, "values": ["1.5", 2, "bad", None]},
        {"index": 0, "values": [0.25]},
    ])

    assert [c["index"] for c in out] == [0, 1]      # index 순 정렬 유지
    assert out[1]["values"] == [1.5, 2.0, None, None]
    assert all(isinstance(v, float) or v is None for c in out for v in c["values"])
