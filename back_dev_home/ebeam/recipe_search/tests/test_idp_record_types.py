"""The three IDP tables must reach the browser with the types they promise.

On 2026-08-05 the office parser returned `Coordinate.X` as a STRING. Nothing
raised: `_scalar` passes a str through untouched, the response was a valid 200,
and `WaferAlignInfoRow` went on declaring the field a `float`. The frontend
believed the contract and called `.toFixed(3)` on it, which threw inside a
computed — so the align table did not render AND the modal stopped responding
to its own close button. One wrong type, two symptoms, neither of which names
the cause.

The mock cannot produce this: it builds frames from a dtype map, so every cell
is already the declared type (see the value-domain blind spot in
`docs/datatables/recipe_idp.txt`). That is exactly why the coercion belongs in
the adapter and the test belongs here — `_records` is pure, so the office-only
failure is reproducible anywhere by handing it an object-dtype frame.

Types are read from `contracts.py` here, unlike `test_idp_mapping.py`, which
transcribes the COLUMN NAMES from the schema doc on purpose. Names are the
office's contract and must be reconciled against the doc; declared types are
OUR promise to the frontend, so deriving them is what keeps this test honest
when a field's type changes.
"""

import logging

import pandas as pd
import pytest

from back_dev_home.ebeam.recipe_search.contracts import (
    IdpImageInfoRow,
    WaferAlignInfoRow,
    WaferMpInfoRow,
)
from back_dev_home.ebeam.recipe_search.providers import office_example


ALIGN_TYPES = WaferAlignInfoRow.__annotations__


def _align_frame(**overrides) -> pd.DataFrame:
    """One align row, every cell a string — what the office actually sent."""
    row = {
        "Align_No": "1",
        "Chip.X": "2",
        "Chip.Y": "9",
        "Coordinate.X": "52.676",
        "Coordinate.Y": "-25.240",
        "P.No": "1",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_string_coordinates_become_floats():
    """The exact 2026-08-05 failure: a str where the contract promises float."""
    rows = office_example._records(_align_frame(), ALIGN_TYPES, "wafer_align_info")

    assert rows[0]["Coordinate.X"] == pytest.approx(52.676)
    assert isinstance(rows[0]["Coordinate.X"], float)
    assert isinstance(rows[0]["Coordinate.Y"], float)


def test_string_integers_become_ints():
    rows = office_example._records(_align_frame(), ALIGN_TYPES, "wafer_align_info")

    for column in ("Align_No", "Chip.X", "Chip.Y", "P.No"):
        assert isinstance(rows[0][column], int), column
    assert rows[0]["P.No"] == 1


def test_a_float_shaped_string_in_an_int_column_still_lands_as_int():
    """"1.0" is what a float64 column stringifies to; int("1.0") raises."""
    rows = office_example._records(
        _align_frame(**{"P.No": "2.0"}), ALIGN_TYPES, "wafer_align_info"
    )

    assert rows[0]["P.No"] == 2
    assert isinstance(rows[0]["P.No"], int)


def test_numbers_already_of_the_right_type_are_untouched():
    """Coercion must be a no-op on the shape the office usually sends.

    Otherwise this fix would be a second, unreviewed change to the path that
    was already working.
    """
    frame = pd.DataFrame([{
        "Align_No": 1, "Chip.X": 2, "Chip.Y": 9,
        "Coordinate.X": 52.676, "Coordinate.Y": -25.24, "P.No": 1,
    }])

    rows = office_example._records(frame, ALIGN_TYPES, "wafer_align_info")

    assert rows[0] == {
        "Align_No": 1, "Chip.X": 2, "Chip.Y": 9,
        "Coordinate.X": 52.676, "Coordinate.Y": -25.24, "P.No": 1,
    }


def test_a_missing_cell_stays_none_rather_than_becoming_zero():
    """NaN -> None -> null, NOT 0.0.

    A coordinate that silently reads 0.000 puts a measurement point at the
    wafer centre. Absent has to look absent; the frontend renders it as —.
    """
    rows = office_example._records(
        _align_frame(**{"Coordinate.X": None}), ALIGN_TYPES, "wafer_align_info"
    )

    assert rows[0]["Coordinate.X"] is None


def test_an_unparseable_value_becomes_none_and_is_logged(caplog):
    """Better a blank cell than a str that crashes the browser's formatter.

    The log names the column because the response cannot: a null is
    indistinguishable from a genuinely empty cell once it reaches the client.
    """
    with caplog.at_level(logging.WARNING):
        rows = office_example._records(
            _align_frame(**{"Coordinate.X": "n/a"}), ALIGN_TYPES, "wafer_align_info"
        )

    assert rows[0]["Coordinate.X"] is None
    assert "Coordinate.X" in caplog.text
    assert "wafer_align_info" in caplog.text


def test_one_log_line_per_column_not_per_row():
    """A 4000-row frame with one bad column must not write 4000 warnings."""
    frame = pd.concat([_align_frame(**{"Coordinate.X": "n/a"})] * 50, ignore_index=True)

    with pytest.MonkeyPatch.context():
        import logging as _logging
        records = []
        handler = _logging.Handler()
        handler.emit = records.append
        office_example._LOG.addHandler(handler)
        try:
            office_example._records(frame, ALIGN_TYPES, "wafer_align_info")
        finally:
            office_example._LOG.removeHandler(handler)

    coordinate_warnings = [r for r in records if "Coordinate.X" in r.getMessage()]
    assert len(coordinate_warnings) == 1


def test_bools_are_not_inferred_from_strings():
    """`bool("False")` is True — the one coercion that must NOT be attempted.

    idp_image_info's three flags drive colour on screen. Turning the string
    "False" into True would be worse than leaving the field alone, so an
    unrecognised bool is dropped to None and logged like any other.
    """
    frame = pd.DataFrame([{
        "Parameter": "CD1", "img_add1": "IMMP0001", "img_add2": "PRMP0001",
        "img_meas1": "IMMS0001", "img_meas2": "PRMS0001", "SEQ": 1,
        "Last_SEQ": 2, "Region": 1, "image_add3": "non",
        "Addressing": "False", "Mother_Para": True, "Double_Addressing": False,
        "Meas_Counting": 1, "dnumber_removed": False,
    }])

    rows = office_example._records(
        frame, IdpImageInfoRow.__annotations__, "idp_image_info"
    )

    assert rows[0]["Addressing"] is None
    assert rows[0]["Mother_Para"] is True


def test_a_number_in_a_str_column_becomes_text():
    """img_meas2 is a str in idp_image_info and an int in wafer_mp_info.

    Same name, unrelated meaning (docs/datatables/recipe_idp.txt). Driving the
    coercion off each table's own contract is what keeps that straight.
    """
    frame = pd.DataFrame([{
        "Parameter": "CD1", "img_add1": "IMMP0001", "img_add2": "PRMP0001",
        "img_meas1": "IMMS0001", "img_meas2": 7, "SEQ": 1,
        "Last_SEQ": 2, "Region": 1, "image_add3": "non",
        "Addressing": True, "Mother_Para": True, "Double_Addressing": False,
        "Meas_Counting": 1, "dnumber_removed": False,
    }])

    rows = office_example._records(
        frame, IdpImageInfoRow.__annotations__, "idp_image_info"
    )

    assert rows[0]["img_meas2"] == "7"


def test_wafer_mp_info_img_meas2_stays_an_int():
    frame = pd.DataFrame([{
        "ChipNo_X": 1, "ChipNo_Y": 2, "Coordinate_X": "1.5", "Coordinate_Y": "2.5",
        "P_No": "3", "D_No": "-1", "Diff": True, "Rel": False,
        "Rel_MoveX": "0.1", "Rel_MoveY": "0.2", "Coordinate_X_r": "1.6",
        "Coordinate_Y_r": "2.7", "Parameter": "CD1", "img_meas2": "3",
    }])

    rows = office_example._records(
        frame, WaferMpInfoRow.__annotations__, "wafer_mp_info"
    )

    assert rows[0]["img_meas2"] == 3
    assert isinstance(rows[0]["img_meas2"], int)
    assert rows[0]["Coordinate_X"] == pytest.approx(1.5)


def test_an_absent_column_is_still_none():
    """The pre-existing behaviour for a column the parser stopped sending."""
    frame = _align_frame().drop(columns=["Coordinate.Y"])

    rows = office_example._records(frame, ALIGN_TYPES, "wafer_align_info")

    assert rows[0]["Coordinate.Y"] is None
