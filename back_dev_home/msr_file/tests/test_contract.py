"""Contract pin for the msr_file signature boundary (Task 2).

Locks the exact set of fields the frontend compatibility signature is allowed to
read from, and — just as important — pins the fields that are INTENTIONALLY
absent in Phase-1 mock (site-layout hash, recipe revision, sequence timestamp,
coordinate-transform version). Those are office-gated: the analysis treats them
as UNKNOWN and never fabricates them, which is what forces layout-dependent
readiness (multi-MSR delta, site variability, same-site gallery) to
``unavailable`` offline. Fabricating any of them here would silently unlock those
capabilities against data that cannot support them.

Run from repo root:  .venv/bin/python -m pytest back_dev_home/msr_file
"""

import pytest

from back_dev_home.meas_hist.providers import mock as meas_hist_mock
from back_dev_home.msr_file.providers import mock


# A synthetic MSR with explicit class/total so the contract does not depend on
# meas_hist fixture contents.
_MSR = "MSR-CONTRACT-0001"
_CLASS = "ADI"
_TOTAL_IMAGES = 40

# A hand-seeded meas_hist row (providers/mock.py), so the parent lookup that
# supplies the tool address has something stable to resolve against.
_REAL_MSR = "20260509_ADI_CD_BIAS_001_6LD257421_ECXDX925"

# Keys that must NEVER appear in the mock response — the office-gated canonical
# metadata the analysis waits on. Checked against every dict in the payload.
_FORBIDDEN_KEYS = frozenset({
    "site_layout_hash",
    "layout_hash",
    "site_layout_id",
    "recipe_revision",
    "coordinate_transform_version",
    "sequence_timestamp",
    "timestamp",
})


@pytest.fixture(scope="module")
def response():
    result = mock.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)
    assert result is not None
    return result


def test_recipe_identity_is_emitted(response):
    exe = response["exe_detail_info"]
    for key in ("recipe_name", "idp_name", "idw_name"):
        assert exe.get(key), f"exe_detail_info.{key} must carry recipe identity"


def test_coordinate_metadata_is_emitted(response):
    exe = response["exe_detail_info"]
    for key in ("wafer_size", "chip_array", "chip_pitch", "map_offset", "map_origin"):
        assert key in exe, f"exe_detail_info.{key} must carry coordinate metadata"


def test_parameter_and_unit_are_emitted(response):
    """Every summary carries both keys, and every NAMED one is actually named.

    The `parameter` key may legitimately be "": that is the unnamed settling-shot
    summary, which test_dummy_mp_gets_its_own_unnamed_summary below requires to
    exist whenever a recipe opens with settling shots. Asserting a truthy name on
    every summary contradicted that test outright, and only passed because `_MSR`
    happened to draw zero settling shots — a coincidence of the seed, not a
    property of the contract. Scoping the name check to named summaries is what
    the assertion always meant.
    """
    assert response["parameters"], "at least one parameter summary is required"
    for summary in response["parameters"]:
        assert "parameter" in summary
        assert "unit" in summary, "each parameter summary must carry its own unit"

    named = [s for s in response["parameters"] if s["parameter"] != ""]
    assert named, "a measurement must summarize at least one named parameter"
    for summary in named:
        assert summary["parameter"].strip(), "a named summary cannot be whitespace"


def test_per_row_acquisition_fields_are_emitted(response):
    assert response["rows"], "rows are required to derive acquisition context"
    fields = (
        "meas_method", "object_type", "meas_kind",
        "meas_condition_mag", "meas_condition_vac", "meas_condition_pixel",
    )
    for field in fields:
        assert field in response["rows"][0], f"rows[].{field} must be present"


# ── The image-request tuple ──────────────────────────────────────────────────
# msr_image is addressed by (eqp_ip, class_name, msr). The frontend used to read
# eqp_ip off the meas_hist row it had cached from the landing list, so opening a
# measurement that was NOT in that list (a search hit, a shared deep link) left
# eqp_ip empty and every image on the analysis page rendered "이미지 없음". Both
# adapters already load the parent meas_hist row to resolve class_name /
# total_images, so the tool address rides along with it and the msr_file response
# answers the whole tuple on its own.


def test_tool_address_is_emitted_for_a_real_msr():
    """eqp_ip completes the (eqp_ip, class_name, msr) msr_image address."""
    parent = meas_hist_mock.find_meas_hist_by_msr(_REAL_MSR)
    assert parent is not None, "fixture drift: _REAL_MSR is not a mock meas_hist row"

    payload = mock.get_msr_file(_REAL_MSR)
    assert payload is not None
    assert payload["eqp_ip"] == parent["eqp_ip"], (
        "msr_file must carry the parent row's eqp_ip so the image URL can be "
        "built from the msr alone"
    )
    assert payload["class_name"] == parent["class_name"]


def test_tool_address_is_empty_when_the_msr_has_no_parent(response):
    """Synthesized MSRs have no meas_hist row — say so rather than inventing one."""
    assert response["eqp_ip"] == ""


def _iter_dicts(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_dicts(item)


def test_office_gated_fields_are_absent(response):
    """No layout hash / recipe revision / sequence timestamp anywhere."""
    for scope in _iter_dicts(response):
        leaked = _FORBIDDEN_KEYS.intersection(scope.keys())
        assert not leaked, f"office-gated key(s) leaked into the mock response: {leaked}"


# The former test_office_adapter_raises_until_connected is retired: the office
# adapter is now CONNECTED — it reads the processed pickle at the meas_hist
# doc's `minio_pkl` path (see providers/office_example.py). Its normalization
# and gated-metadata derivations are pinned in tests/test_office_template.py.


# ── Unnamed dummy MP (settling shots) ────────────────────────────────────────
# Real measurements often open with measurement points that carry NO parameter
# name. They are real rows with real images, so the mock has to produce them or
# the home phase can never exercise the frontend paths that handle them (the
# default-parameter pick, the selection sentinel, the stand-in chip label).


def _msr_with_dummy() -> str:
    """The first synthetic MSR whose seeded draw includes settling shots."""
    for i in range(60):
        msr = f"MSR-DUMMY-{i:04d}"
        payload = mock.get_msr_file(msr, _CLASS, _TOTAL_IMAGES)
        assert payload is not None
        if any(row["parameter"] == "" for row in payload["rows"]):
            return msr
    pytest.fail("no synthetic MSR drew a dummy MP — the generator stopped emitting them")


def test_some_measurements_carry_unnamed_dummy_mps_and_some_do_not():
    """Both paths must exist at home, or one of them is never exercised."""
    with_dummy, without_dummy = 0, 0
    for i in range(40):
        payload = mock.get_msr_file(f"MSR-DUMMY-MIX-{i:04d}", _CLASS, _TOTAL_IMAGES)
        assert payload is not None
        if any(row["parameter"] == "" for row in payload["rows"]):
            with_dummy += 1
        else:
            without_dummy += 1
    assert with_dummy, "no measurement carried a dummy MP"
    assert without_dummy, "every measurement carried a dummy MP"


def test_dummy_mp_is_measured_first_and_carries_an_image():
    payload = mock.get_msr_file(_msr_with_dummy(), _CLASS, _TOTAL_IMAGES)
    assert payload is not None
    dummies = [row for row in payload["rows"] if row["parameter"] == ""]
    named = [row for row in payload["rows"] if row["parameter"] != ""]

    # Measured FIRST — this is what makes it the trap a naive "first parameter"
    # default falls into, so the ordering is part of the contract.
    assert max(row["sequence"] for row in dummies) < min(row["sequence"] for row in named)
    assert all(row["mp_number"] == 0 for row in dummies)

    for row in dummies:
        assert row["cd_value"] is not None, "a settling shot is measured, not empty"
        assert row["mp_image_name_01"], "the reviewer's reason to open it is the image"
        assert row["no_of_mp_image"] == 1
        assert row["meas_condition_mag"] > 0
        assert row["meas_condition_pixel"] != "0,0"


def test_dummy_mp_gets_its_own_unnamed_summary():
    payload = mock.get_msr_file(_msr_with_dummy(), _CLASS, _TOTAL_IMAGES)
    assert payload is not None
    summary = next(s for s in payload["parameters"] if s["parameter"] == "")
    dummies = [row for row in payload["rows"] if row["parameter"] == ""]
    assert summary["count"] == len(dummies)
    assert summary["unit"] == "", "an unnamed point has no unit to report"


# ── sequence is a global per-row counter (Task 3) ────────────────────────────
# `_MSR`'s seeded draw happens to select exactly ONE parameter (verified: seed
# 1471759110 draws num_params=1 for ("MSR-CONTRACT-0001", "ADI", 40)). With one
# parameter, a step's parameter loop runs once, so the old cartesian bug (one
# sequence number shared across a step's parameter rows) and the fix produce
# IDENTICAL output — testing only against _MSR asserts nothing about this fix.
# _msr_with_multi_param() finds an MSR whose draw selects 2+ parameters, which
# is the only shape where a step's parameter loop runs more than once and the
# bug (or the fix) is observable at all.


def _msr_with_multi_param() -> str:
    """The first synthetic MSR whose seeded draw selects 2+ parameters."""
    for i in range(60):
        msr = f"MSR-MULTI-PARAM-{i:04d}"
        payload = mock.get_msr_file(msr, _CLASS, _TOTAL_IMAGES)
        assert payload is not None
        params = {row["parameter"] for row in payload["rows"] if row["parameter"] != ""}
        if len(params) >= 2:
            return msr
    pytest.fail("no synthetic MSR drew 2+ parameters — the generator stopped varying num_params")


def _sequence_test_msrs() -> list[str]:
    """A handful of MSRs covering different draws (single-param, multi-param,
    with dummy settling shots) so the invariant is checked across shapes
    rather than one seed that may or may not exercise the bug."""
    return [_MSR, _msr_with_multi_param(), _msr_with_dummy()]


def test_sequence_is_unique_per_row():
    """`sequence` is a global running counter: one number per measurement."""
    for msr in _sequence_test_msrs():
        result = mock.get_msr_file(msr, _CLASS, _TOTAL_IMAGES)
        assert result is not None
        sequences = [row["sequence"] for row in result["rows"]]
        assert len(sequences) == len(set(sequences)), \
            f"{msr}: a sequence number is reused across rows"
        assert sequences == sorted(sequences), f"{msr}: rows are not in measurement order"


def test_row_count_matches_dynamic_fdc_count():
    """The office invariant: one row, one measurement, one dynamic_fdc entry."""
    for msr in _sequence_test_msrs():
        result = mock.get_msr_file(msr, _CLASS, _TOTAL_IMAGES)
        assert result is not None
        assert len(result["rows"]) == len(result["dynamic_fdc"]), \
            f"{msr}: len(rows) != len(dynamic_fdc)"


def test_dynamic_fdc_keys_are_exactly_the_row_sequences():
    for msr in _sequence_test_msrs():
        result = mock.get_msr_file(msr, _CLASS, _TOTAL_IMAGES)
        assert result is not None
        assert {str(row["sequence"]) for row in result["rows"]} == set(result["dynamic_fdc"]), \
            f"{msr}: dynamic_fdc keys do not match row sequences"


def test_parameters_measured_at_one_point_share_its_die():
    """Parameters measured at the same point (die) share its chip/stage
    coordinates, but each is still its own measurement — so two parameters at
    one die must never share a sequence number either.

    Runs against _msr_with_multi_param(), not _MSR: this property has nothing
    to pair up under a single-parameter draw, and previously the test silently
    returned without asserting anything for exactly that reason. The sequence
    check (not just the parameter-name check) is what actually fails if the
    mock reverts to sharing one sequence number across a step's parameters —
    a die carrying two DIFFERENT parameter names was already true before this
    fix, so asserting only that would prove nothing about the fix itself.
    """
    result = mock.get_msr_file(_msr_with_multi_param(), _CLASS, _TOTAL_IMAGES)
    assert result is not None
    by_chip: dict[str, list[dict]] = {}
    for row in result["rows"]:
        by_chip.setdefault(row["chip_number"], []).append(row)
    shared = [rows for rows in by_chip.values() if len({r["parameter"] for r in rows}) > 1]
    assert shared, "no die carries more than one parameter — points are not shared"
    for rows in shared:
        seqs = [row["sequence"] for row in rows]
        assert len(seqs) == len(set(seqs)), \
            "rows sharing a die must not share a sequence number"
