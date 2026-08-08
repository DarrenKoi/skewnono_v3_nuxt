"""Align files must reach the ALIGN readers, not the parameter lookalikes.

Until 2026-07-29 ``get_align_detail`` sent ENAP settings to
``read_af_pr_condition`` and align cond.txt files to
``read_meas_image_condition``. Both are real functions, both accept what they
were handed, and both return something renderable — so the screen filled in,
nothing raised, and every existing test passed. The bug was invisible precisely
because it could only be seen at the office, in the values.

That is what these tests exist to stop: they assert WHICH reader was called and
WITH WHAT, not merely that a block came back.

``office_utils`` is gitignored and absent from a clean checkout (see
``test_param_detail_mock.test_the_mock_does_not_import_the_office_only_parser``),
so the readers are injected into ``sys.modules`` rather than imported. That is
also what makes the call arguments observable — the home stand-in would happily
return a block for a wrong ``which`` and tell us nothing.
"""

import logging
import sys
import types

import pytest

from back_dev_home.ebeam.recipe_search import rawfiles
from back_dev_home.ebeam.recipe_search.providers import office_example as office

LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}


@pytest.fixture
def readers(monkeypatch):
    """Fake ``office_utils.idp_amp_reader``, recording every call."""
    calls: dict[str, list] = {"batch": [], "image": []}

    def get_align_beam_pr_conditions(sources):
        calls["batch"].append(list(sources))
        return [{"PR": index} for index in range(len(sources))]

    def read_align_image_condition(source, which):
        calls["image"].append((source, which))
        return {"OPTIC": which}

    module = types.ModuleType("office_utils.idp_amp_reader")
    module.get_align_beam_pr_conditions = get_align_beam_pr_conditions
    module.read_align_image_condition = read_align_image_condition
    # Both readers the align path must NOT use. Present so a regression calls a
    # real function and fails on the assertion rather than on an ImportError,
    # which would read as a broken test instead of a broken adapter.
    module.read_af_pr_condition = lambda source: pytest.fail(
        "read_af_pr_condition is the parameter-side reader; align settings go "
        "to get_align_beam_pr_conditions"
    )
    module.read_meas_image_condition = lambda source: pytest.fail(
        "read_meas_image_condition is the parameter-side reader; align image "
        "conditions go to read_align_image_condition"
    )
    monkeypatch.setitem(sys.modules, "office_utils", types.ModuleType("office_utils"))
    monkeypatch.setitem(sys.modules, "office_utils.idp_amp_reader", module)
    return calls


@pytest.fixture
def fetched(monkeypatch):
    """Stand in for the FTP fetch: every requested name resolves to bytes."""
    def _install(present: set[str] | None = None) -> dict[str, bytes]:
        blob: dict[str, bytes] = {}

        def _fetch_raw(locator, names):
            blob.clear()
            blob.update({
                name: f"bytes-of-{name}".encode()
                for name in names
                if present is None or name in present
            })
            return dict(blob)

        monkeypatch.setattr(office, "_fetch_raw", _fetch_raw)
        return blob
    return _install


# ── which optic, and where it comes from ──────────────────────────────────


def test_point_one_is_read_as_om_and_point_two_as_sem(readers, fetched):
    """The optic comes from the align point NUMBER — nothing in the cond.txt
    says which instrument took the image (user-confirmed 2026-07-29)."""
    fetched()
    office.get_align_detail(LOCATOR, [1, 2])

    assert [which for _, which in readers["image"]] == ["OM", "SEM"]


def test_the_cond_file_read_for_each_optic_is_that_points_own(readers, fetched):
    fetched()
    office.get_align_detail(LOCATOR, [1, 2])

    sources = [source for source, _ in readers["image"]]
    assert sources == [b"bytes-of-.IMAP0001.jpeg/cond.txt",
                       b"bytes-of-.IMAP0002.jpeg/cond.txt"]


def test_an_unknown_point_number_is_not_guessed_into_an_optic(readers, fetched, caplog):
    """P.No 3 has no documented optic. Guessing either one would render the
    other instrument's settings as ordinary data, so the condition is dropped
    and the point still carries its image name and ENAP setting."""
    fetched()
    with caplog.at_level(logging.WARNING):
        point = office.get_align_detail(LOCATOR, [3])["points"][0]

    assert readers["image"] == []
    assert point["cond"] is None
    assert point["setting"] is not None
    assert point["image"] == "IMAP0003.jpeg"
    assert "P.No=3" in caplog.text


# ── the ENAP settings are read ONCE for the whole set ─────────────────────


def test_align_settings_are_read_in_one_call_for_every_point(readers, fetched):
    """``get_align_beam_pr_conditions`` takes the whole ENAP list, so a recipe
    with two align points must produce ONE call carrying two sources — not two
    calls, which is what a per-point loop would emit."""
    fetched()
    office.get_align_detail(LOCATOR, [1, 2])

    assert len(readers["batch"]) == 1
    assert readers["batch"][0] == [b"bytes-of-ENAP0001", b"bytes-of-ENAP0002"]


def test_an_absent_enap_file_is_not_sent_to_the_reader(readers, fetched):
    """A recipe with only point 1 must not send a hole for point 2. The reader
    would have to interpret it, and a positional return could then be zipped
    onto the wrong point."""
    fetched(present={"ENAP0001", ".IMAP0001.jpeg/cond.txt", ".IMAP0002.jpeg/cond.txt"})
    points = office.get_align_detail(LOCATOR, [1, 2])["points"]

    assert readers["batch"][0] == [b"bytes-of-ENAP0001"]
    assert points[0]["setting"] is not None
    assert points[1]["setting"] is None


def test_a_reader_that_raises_costs_only_the_settings(readers, fetched, monkeypatch):
    """The align popup keeps its images and beam conditions when the ENAP read
    fails — the same containment ``_read_block`` gives a per-file failure."""
    def boom(sources):
        raise ValueError("unreadable")

    sys.modules["office_utils.idp_amp_reader"].get_align_beam_pr_conditions = boom
    fetched()
    points = office.get_align_detail(LOCATOR, [1, 2])["points"]

    assert [point["setting"] for point in points] == [None, None]
    assert all(point["cond"] is not None for point in points)


# ── splitting one batch return across the points ──────────────────────────


def test_an_optic_keyed_return_is_split_by_optic():
    """THE confirmed shape (office 확인 2026-07-30): the reader keys its return
    {"OM": ..., "SEM": ...}, which is what makes it splittable at all — P.No 1
    is OM and P.No 2 is SEM."""
    parsed = {"OM": {"Acceptance": "200"}, "SEM": {"Acceptance": "150"}}
    blocks = office._split_align_settings(
        parsed, ["ENAP0001", "ENAP0002"], {"ENAP0001": "OM", "ENAP0002": "SEM"},
    )

    assert blocks["ENAP0001"]["rows"] == [{"key": "Acceptance", "value": "200"}]
    assert blocks["ENAP0002"]["rows"] == [{"key": "Acceptance", "value": "150"}]
    assert blocks["ENAP0001"]["source"] == "ENAP0001"


def test_the_optic_branch_wins_over_the_positional_guess():
    """Both readings apply to a 2-key dict for 2 files, and they disagree: by
    optic ENAP0002 gets SEM's value, positionally it would get whichever key
    came second. The confirmed shape has to be the one that fires."""
    parsed = {"SEM": {"Acceptance": "150"}, "OM": {"Acceptance": "200"}}
    blocks = office._split_align_settings(
        parsed, ["ENAP0001", "ENAP0002"], {"ENAP0001": "OM", "ENAP0002": "SEM"},
    )

    assert blocks["ENAP0001"]["rows"] == [{"key": "Acceptance", "value": "200"}]


def test_a_point_with_no_optic_is_left_out_rather_than_guessed(caplog):
    """P.No 3 has no optic, so there is no key to look its settings up under.
    Attaching either optic's block would show one instrument's settings under
    another's heading — the same rule the image condition follows."""
    parsed = {"OM": {"Acceptance": "200"}, "SEM": {"Acceptance": "150"}}
    with caplog.at_level(logging.INFO):
        blocks = office._split_align_settings(
            parsed,
            ["ENAP0001", "ENAP0003"],
            {"ENAP0001": "OM", "ENAP0003": None},
        )

    assert "ENAP0001" in blocks
    assert "ENAP0003" not in blocks
    assert "ENAP0003" in caplog.text


def test_the_optic_lookup_tolerates_a_casing_difference():
    """"OM"/"SEM" is a label the adapter passes IN to the sibling reader;
    nothing guarantees this one echoes the same casing back."""
    blocks = office._split_align_settings(
        {"om": {"Acceptance": "200"}}, ["ENAP0001"], {"ENAP0001": "OM"},
    )

    assert blocks["ENAP0001"]["rows"] == [{"key": "Acceptance", "value": "200"}]


def test_a_parallel_sequence_is_zipped_onto_the_points_in_order():
    blocks = office._split_align_settings([{"A": 1}, {"B": 2}], ["ENAP0001", "ENAP0002"])

    assert blocks["ENAP0001"]["rows"] == [{"key": "A", "value": "1"}]
    assert blocks["ENAP0002"]["rows"] == [{"key": "B", "value": "2"}]
    assert blocks["ENAP0001"]["source"] == "ENAP0001"


def test_a_name_keyed_mapping_is_split_by_name():
    parsed = {"ENAP0002": {"B": 2}, "ENAP0001": {"A": 1}}
    blocks = office._split_align_settings(parsed, ["ENAP0001", "ENAP0002"])

    assert blocks["ENAP0001"]["rows"] == [{"key": "A", "value": "1"}]


def test_an_unsplittable_return_goes_to_every_point_and_is_logged(caplog):
    """One merged value cannot be divided per point without inventing a
    correspondence, so every point shows the whole thing and the type reaches
    the log — that is the report that answers the OFFICE-VERIFY item."""
    with caplog.at_level(logging.WARNING):
        blocks = office._split_align_settings({"Mag": "50K"}, ["ENAP0001", "ENAP0002"])

    assert blocks["ENAP0001"] == blocks["ENAP0002"]
    assert blocks["ENAP0001"]["source"] == "ENAP0001, ENAP0002"
    assert "could not be split" in caplog.text


def test_a_sequence_of_the_wrong_length_is_not_zipped(caplog):
    """Three results for two files means the correspondence is not positional.
    Zipping anyway would silently attach point 1's settings to point 2."""
    with caplog.at_level(logging.WARNING):
        blocks = office._split_align_settings([{"A": 1}], ["ENAP0001", "ENAP0002"])

    assert blocks["ENAP0001"] == blocks["ENAP0002"]


# ── the rule itself ───────────────────────────────────────────────────────


@pytest.mark.parametrize(("p_no", "expected"), [(1, "OM"), (2, "SEM")])
def test_align_optics_maps_the_two_documented_points(p_no, expected):
    assert rawfiles.align_optics(p_no) == expected


@pytest.mark.parametrize("p_no", [0, 3, 12, -1])
def test_align_optics_refuses_to_answer_for_anything_else(p_no):
    assert rawfiles.align_optics(p_no) is None
