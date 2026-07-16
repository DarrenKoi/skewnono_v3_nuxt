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


def test_office_adapter_raises_until_connected():
    """The office adapter is the entry gate downstream tasks wait on: it must
    refuse until the canonical layout/coordinate metadata source is connected."""
    from back_dev_home.msr_file.providers import office

    with pytest.raises(NotImplementedError):
        office.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)
    with pytest.raises(NotImplementedError):
        office.get_msr_image("anything.tif")
