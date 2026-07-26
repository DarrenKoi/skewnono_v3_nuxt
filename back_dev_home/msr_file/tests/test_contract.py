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

from back_dev_home.msr_file.providers import mock


# A synthetic MSR with explicit class/total so the contract does not depend on
# meas_hist fixture contents.
_MSR = "MSR-CONTRACT-0001"
_CLASS = "ADI"
_TOTAL_IMAGES = 40

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
    assert response["parameters"], "at least one parameter summary is required"
    for summary in response["parameters"]:
        assert summary.get("parameter")
        assert "unit" in summary, "each parameter summary must carry its own unit"


def test_per_row_acquisition_fields_are_emitted(response):
    assert response["rows"], "rows are required to derive acquisition context"
    fields = (
        "meas_method", "object_type", "meas_kind",
        "meas_condition_mag", "meas_condition_vac", "meas_condition_pixel",
    )
    for field in fields:
        assert field in response["rows"][0], f"rows[].{field} must be present"


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
