"""``_to_rows`` must survive whatever container the office reader returns.

The only part of the office raw-folder adapter testable from home — and the part
most likely to be wrong, because the readers' return CONTAINER is OFFICE-VERIFY,
not merely their field names. A wrong guess here must degrade to oddly-ordered
rows, never to a 500 on a screen that used to work.
"""

import pandas as pd

from back_dev_home.ebeam.hitachi.recipe_search.providers import office_example as office


def test_a_dict_becomes_rows_in_insertion_order():
    """Order is the reader's own — nothing sorts or renames."""
    assert office._to_rows({"B": 2, "A": "x"}) == [
        {"key": "B", "value": "2"},
        {"key": "A", "value": "x"},
    ]


def test_a_single_row_dataframe_becomes_column_rows():
    frame = pd.DataFrame([{"Mag": "50.0K", "Vacc": 800}])
    assert office._to_rows(frame) == [
        {"key": "Mag", "value": "50.0K"},
        {"key": "Vacc", "value": "800"},
    ]


def test_a_wide_single_row_dataframe_keeps_every_column():
    frame = pd.DataFrame([{f"F{i}": i for i in range(8)}])
    assert len(office._to_rows(frame)) == 8


def test_a_two_column_dataframe_is_read_as_key_value_pairs():
    frame = pd.DataFrame({"item": ["Mag", "Vacc"], "value": ["50.0K", 800]})
    assert office._to_rows(frame) == [
        {"key": "Mag", "value": "50.0K"},
        {"key": "Vacc", "value": "800"},
    ]


def test_a_one_by_two_frame_is_read_as_columns_not_as_one_pair():
    """The one genuinely ambiguous shape: 1x2 satisfies both readings and they
    disagree. Columns win — a settings file holding a single setting is rarer
    than one holding two. Documented as OFFICE-VERIFY; flip the branch in
    _to_rows if the office turns out to emit 1x2 pair frames."""
    frame = pd.DataFrame([{"Mag": "50.0K", "Vacc": "800"}])
    rows = office._to_rows(frame)
    assert rows == [
        {"key": "Mag", "value": "50.0K"},
        {"key": "Vacc", "value": "800"},
    ]
    assert rows != [{"key": "50.0K", "value": "800"}]


def test_a_list_of_pairs_becomes_rows():
    assert office._to_rows([("Mag", "50.0K"), ["Vacc", 800]]) == [
        {"key": "Mag", "value": "50.0K"},
        {"key": "Vacc", "value": "800"},
    ]


def test_none_and_empty_become_no_rows():
    assert office._to_rows(None) == []
    assert office._to_rows({}) == []
    assert office._to_rows([]) == []
    assert office._to_rows(pd.DataFrame()) == []


def test_an_unrecognised_container_is_empty_rather_than_an_exception():
    assert office._to_rows(42) == []


def test_every_value_is_stringified_for_json_safety():
    """numpy scalars are not JSON-serialisable; str() is what makes them so."""
    frame = pd.DataFrame([{"Frame": 8, "WD": 5.5, "On": True}])
    assert all(
        isinstance(row["value"], str) for row in office._to_rows(frame)
    )


# ── _read_block ───────────────────────────────────────────────────────────


def test_read_block_returns_none_when_the_file_is_absent():
    """Absent is normal, not an error: a parameter may simply lack the file."""
    assert office._read_block("PRMS0001", None, lambda _: {"a": 1}) is None
    assert office._read_block(None, b"data", lambda _: {"a": 1}) is None


def test_read_block_returns_none_when_the_reader_raises():
    """One malformed file must not take the whole parameter down with it."""
    def _explode(_payload):
        raise ValueError("not a recognised amp file")

    assert office._read_block("PRMS0001", b"junk", _explode) is None


def test_read_block_names_the_file_it_parsed():
    block = office._read_block("PRMS0001", b"x", lambda _: {"Mag": "50K"})
    assert block == {
        "source": "PRMS0001",
        "rows": [{"key": "Mag", "value": "50K"}],
    }


# ── _slot_sources ─────────────────────────────────────────────────────────


def test_slot_sources_matches_the_naming_rules():
    amp, af_pr, images = office._slot_sources({
        "img_add1": "IMMP0001",
        "img_add2": "PRMP0001",
        "image_add3": "I2MP0001",
        "img_meas1": "IMMS0001",
        "img_meas2": "PRMS0001",
    })
    assert amp == "PRMS0001"
    assert af_pr == "ENMP0001"
    assert images == [
        ("img_add1", "IMMP0001.jpeg", ".IMMP0001.jpeg/cond.txt"),
        ("image_add3", "I2MP0001.jpeg", ".I2MP0001.jpeg/cond.txt"),
        ("img_meas1", "IMMS0001.jpeg", ".IMMS0001.jpeg/cond.txt"),
    ]


def test_slot_sources_drops_the_empty_sentinel():
    amp, af_pr, images = office._slot_sources({
        "img_add1": "non", "img_add2": "non", "img_meas2": "non",
    })
    assert amp is None
    assert af_pr is None
    assert images == []


def test_fetch_raw_with_no_names_opens_no_session():
    """Guards the empty-slot case from costing an FTP connection."""
    assert office._fetch_raw(
        {"eqp_ip": "10.1.2.3", "class_name": "C", "idw": "W", "idp": "P"}, []
    ) == {}
