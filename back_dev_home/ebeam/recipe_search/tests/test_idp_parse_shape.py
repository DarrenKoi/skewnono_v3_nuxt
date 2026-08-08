"""Gate for what `_parse_idp` accepts back from the 사내 IDP parser.

The parser itself is office-only, so the SHAPE it returns is the one thing
about it home can neither see nor reproduce — and on 2026-08-03 the cloud
proved the documented three-key mapping is not the only shape it produces. The
adapter met that with `sorted(frames)`, which raised
`'<' not supported between instances of 'dict' and 'dict'` and threw away the
diagnosis it was in the middle of writing.

So this file feeds `_normalize_frames` shapes the parser might plausibly return
and pins two properties: a recognisable one is recovered by COLUMNS (never by
position, which would map silently wrong), and an unrecognisable one raises a
`LookupError` that describes what actually arrived. Both matter more than they
look: every failure here happens where nobody can attach a debugger.

Columns are transcribed from `docs/datatables/recipe_idp.txt`, matching
`test_idp_mapping.py` — see that file's header for why they are not derived
from `contracts.py`.
"""

import pandas as pd
import pytest

from back_dev_home.ebeam.recipe_search.providers import office_example


MP_COLUMNS = [
    "ChipNo_X", "ChipNo_Y", "Coordinate_X", "Coordinate_Y", "P_No", "D_No",
    "Diff", "Rel", "Rel_MoveX", "Rel_MoveY", "Coordinate_X_r",
    "Coordinate_Y_r", "Parameter", "img_meas2",
]
ALIGN_COLUMNS = [
    "Align_No", "Chip.X", "Chip.Y", "Coordinate.X", "Coordinate.Y", "P.No",
]
IMAGE_COLUMNS = [
    "Parameter", "img_add1", "img_add2", "img_meas1", "img_meas2", "SEQ",
    "Last_SEQ", "Region", "image_add3", "Addressing", "Mother_Para",
    "Double_Addressing", "Meas_Counting", "dnumber_removed",
]


def _frame(columns: list[str], marker: str) -> pd.DataFrame:
    """A one-row frame with the documented columns; `marker` tags identity."""
    return pd.DataFrame([{column: marker for column in columns}])


@pytest.fixture
def tables() -> dict[str, pd.DataFrame]:
    return {
        "wafer_mp_info": _frame(MP_COLUMNS, "mp"),
        "wafer_align_info": _frame(ALIGN_COLUMNS, "align"),
        "idp_image_info": _frame(IMAGE_COLUMNS, "image"),
    }


def _markers(frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Which frame landed under which key, by the tag baked into its cells."""
    return {name: frame.iloc[0, 0] for name, frame in frames.items()}


def test_documented_mapping_passes_through_untouched(tables):
    """The office-confirmed shape must not take the recovery path at all."""
    result = office_example._normalize_frames(tables, "R3.idp")

    assert result == {name: tables[name] for name in tables}
    for name, frame in result.items():
        assert frame is tables[name]


def test_extra_keys_are_dropped_not_recovered(tables):
    """A parser that ADDS a key is still the documented shape, not a deviation."""
    result = office_example._normalize_frames({**tables, "future": "x"}, "R3.idp")

    assert sorted(result) == sorted(office_example._PARSED_TABLES)


def test_bare_list_is_recovered_by_columns_not_position(tables):
    """The order is scrambled on purpose: position must not decide the mapping."""
    scrambled = [
        tables["idp_image_info"], tables["wafer_align_info"], tables["wafer_mp_info"],
    ]

    result = office_example._normalize_frames(scrambled, "R3.idp")

    assert _markers(result) == {
        "wafer_mp_info": "mp",
        "wafer_align_info": "align",
        "idp_image_info": "image",
    }


def test_list_of_column_dicts_is_recovered(tables):
    """Tables handed back as plain dicts rather than DataFrames."""
    as_dicts = [frame.to_dict(orient="list") for frame in tables.values()]

    result = office_example._normalize_frames(as_dicts, "R3.idp")

    assert _markers(result) == {
        "wafer_mp_info": "mp",
        "wafer_align_info": "align",
        "idp_image_info": "image",
    }


def test_mapping_with_undocumented_keys_is_recovered(tables):
    """Right tables, renamed keys — recoverable, because columns still name them."""
    renamed = dict(zip(["mp", "align", "image"], tables.values(), strict=True))

    result = office_example._normalize_frames(renamed, "R3.idp")

    assert _markers(result)["wafer_align_info"] == "align"


def test_recovery_warns_that_the_doc_disagrees(tables, caplog):
    """Recovery must be loud: the schema of record is now wrong about the parser."""
    with caplog.at_level("WARNING"):
        office_example._normalize_frames(list(tables.values()), "R3.idp")

    assert "recipe_idp.txt" in caplog.text


def test_series_of_tables_is_recovered(tables):
    """A Series fits the cloud traceback as well as a list does.

    `sorted()` iterates ANY iterable, so `'<' not supported between instances
    of 'dict' and 'dict'` never narrowed the container to a list — only its
    elements to dicts.
    """
    result = office_example._normalize_frames(
        pd.Series([frame.to_dict(orient="list") for frame in tables.values()]),
        "R3.idp",
    )

    assert _markers(result)["wafer_mp_info"] == "mp"


def test_two_frames_claiming_one_table_is_an_error_not_a_coin_toss(tables):
    """First-wins would be exactly the positional guess columns are here to refuse."""
    doubled = [*tables.values(), _frame(MP_COLUMNS, "second-mp")]

    with pytest.raises(LookupError) as excinfo:
        office_example._normalize_frames(doubled, "R3.idp")

    assert "wafer_mp_info" in str(excinfo.value)


def test_documented_keys_holding_non_frames_are_diagnosed_here(tables):
    """Right keys, wrong values: catch it now, not later on `frame.columns`.

    `_records` would raise `AttributeError` — a 500 with a traceback pointing
    at the mapping code rather than at the parser that broke its contract.
    """
    with pytest.raises(LookupError) as excinfo:
        office_example._normalize_frames(
            {**tables, "wafer_align_info": "/tmp/align.csv"}, "R3.idp",
        )

    assert "wafer_align_info" in str(excinfo.value)


def test_documented_keys_holding_column_dicts_are_converted(tables):
    """The keys are documented, so the values are trusted enough to convert."""
    as_dicts = {name: frame.to_dict(orient="list") for name, frame in tables.items()}

    result = office_example._normalize_frames(as_dicts, "R3.idp")

    assert _markers(result)["idp_image_info"] == "image"


def test_list_of_dicts_reports_the_shape_instead_of_crashing(tables):
    """The 2026-08-03 cloud failure: `sorted()` over dicts raised TypeError.

    A bare `LookupError` is the contract: the app-wide handler
    (`back_dev_home/__init__.py`) turns it into a JSON 502 carrying the
    message, so the shape reaches the screen. A `TypeError` is an opaque 500.
    """
    rows = [{"whatever": 1}, {"whatever": 2}]

    with pytest.raises(LookupError) as excinfo:
        office_example._normalize_frames(rows, "R3.idp")

    assert "R3.idp" in str(excinfo.value)
    assert "whatever" in str(excinfo.value)


def test_partial_recovery_names_the_tables_it_could_not_find(tables):
    """Two of three is a failure, and the message has to say WHICH one is absent."""
    with pytest.raises(LookupError) as excinfo:
        office_example._normalize_frames(
            [tables["wafer_mp_info"], tables["idp_image_info"]], "R3.idp",
        )

    assert "wafer_align_info" in str(excinfo.value)


def test_non_container_return_is_reported(tables):
    """`None` is what a parser returns when it silently gave up."""
    with pytest.raises(LookupError) as excinfo:
        office_example._normalize_frames(None, "R3.idp")

    assert "NoneType" in str(excinfo.value)


def test_tuple_wrapping_the_documented_mapping_is_unwrapped(tables, caplog):
    """The second 2026-08-03 cloud failure: a tuple of TWO three-key dicts.

    The 502 message proved the shape — `(dict(keys [3 documented keys]),
    dict(keys [same]))` — but not the dicts' values. Whatever the shadow dict
    holds, a candidate whose three values identify as their own tables by
    columns IS the documented mapping, and must be recovered rather than fed
    to `pd.DataFrame()` and declared missing. The shadow comes first so the
    recovery cannot be a positional guess.
    """
    shadow = {name: "unparsed-section-text" for name in tables}

    with caplog.at_level("WARNING"):
        result = office_example._normalize_frames((shadow, tables), "R3.idp")

    assert _markers(result) == {
        "wafer_mp_info": "mp",
        "wafer_align_info": "align",
        "idp_image_info": "image",
    }
    assert "recipe_idp.txt" in caplog.text


def test_duplicate_documented_mappings_collapse_to_one(tables):
    """Equal copies carry no ambiguity — refusing here would kill a good parse."""
    copies = ({name: frame.copy() for name, frame in tables.items()}, tables)

    result = office_example._normalize_frames(copies, "R3.idp")

    assert _markers(result)["wafer_mp_info"] == "mp"


def test_two_distinct_documented_mappings_refuse_to_choose(tables):
    """Two full table sets (e.g. an OM/SEM split) — picking one would render a
    plausible screen over the wrong half of the data."""
    other = {
        "wafer_mp_info": _frame(MP_COLUMNS, "other-mp"),
        "wafer_align_info": _frame(ALIGN_COLUMNS, "other-align"),
        "idp_image_info": _frame(IMAGE_COLUMNS, "other-image"),
    }

    with pytest.raises(LookupError) as excinfo:
        office_example._normalize_frames((tables, other), "R3.idp")

    assert "documented mapping" in str(excinfo.value)


def test_unrecognisable_dicts_are_described_by_their_values(tables):
    """Keys alone told us nothing on 2026-08-03 — the next message must show
    what the dicts HOLD, so the office error is self-diagnosing."""
    shadow = {name: "unparsed-section-text" for name in tables}

    with pytest.raises(LookupError) as excinfo:
        office_example._normalize_frames((shadow,), "R3.idp")

    assert "unparsed-section-text" in str(excinfo.value)


def test_shared_columns_alone_cannot_identify_a_table():
    """`Parameter` + `img_meas2` sit in two tables; a frame of just those is ambiguous.

    Guessing here would put mp data under the image key — the failure mode the
    column threshold exists to prevent, and one that renders as a plausible
    screen rather than an error.
    """
    ambiguous = pd.DataFrame([{"Parameter": "CD1", "img_meas2": 1}])

    assert office_example._identify_table(ambiguous) is None
