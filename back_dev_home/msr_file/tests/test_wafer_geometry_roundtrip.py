"""Phase-1 proof that the mock's wafer geometry is self-consistent.

Every measured row's stage_coordinate must snap back to the chip_number the mock
assigned it, using ONLY the geometry the payload reports (chip_pitch, wafer_size,
map_offset). This is the mock-side mirror of utils/waferGeometry.ts snapToDieCell
-- the two languages cannot share code, so the formula is re-derived here on
purpose. It is what makes Spec 2's Position pairing key trustworthy offline: if
map_offset is reported but not encoded, the snap lands on the wrong die.

Run from repo root:  .venv/bin/python -m pytest back_dev_home/msr_file
"""

import pytest

from back_dev_home.meas_hist.providers.mock import find_meas_hist_by_msr
from back_dev_home.msr_file.providers import mock

_CLASS = "ADI"
_TOTAL_IMAGES = 40

# Swept, not single -- the sweep is what gives this test its teeth.
#
# Snapping rounds, so it absorbs any placement error below 0.5*pitch. A mock
# that reports map_offset without encoding it is therefore invisible to any MSR
# whose offset (<=0.3*pitch) plus that row's within-die jitter (<=0.3*pitch)
# happens to stay inside that basin. Only the seeds where the two compound past
# 0.5*pitch expose the incoherence, and which seeds those are is pure luck of
# the draw: re-running the broken generator against the current geometry, 15 of
# these 30 MSRs catch it and 15 do not. A single-MSR version of this test would
# be a coin flip.
_MSRS = tuple(f"MSR-CONTRACT-{i:04d}" for i in range(1, 31))


def _snap(stage: str, center_nm: float, pitch: tuple[int, int], offset: tuple[int, int]) -> str:
    """Mirror of utils/waferGeometry.ts snapToDieCell, in nm."""
    sx, sy = (float(v) for v in stage.split(","))
    col = round((sx - center_nm - offset[0]) / pitch[0])
    row = round((sy - center_nm - offset[1]) / pitch[1])
    return f"{col},{row}"


@pytest.mark.parametrize("msr", _MSRS)
def test_stage_coordinate_snaps_back_to_chip_number(msr):
    payload = mock.get_msr_file(msr, _CLASS, _TOTAL_IMAGES)
    info = payload["exe_detail_info"]

    center_nm = float(info["wafer_size"]) / 2
    pitch = tuple(int(v) for v in info["chip_pitch"].split(","))
    offset = tuple(int(v) for v in info["map_offset"].split(","))

    measured = [r for r in payload["rows"] if r["cd_value"] is not None]
    assert measured, "fixture must contain measured rows"

    snapped = [
        (r["chip_number"], _snap(r["stage_coordinate"], center_nm, pitch, offset))
        for r in measured
    ]
    mismatched = [(chip, got) for chip, got in snapped if got != chip]
    assert not mismatched, f"{len(mismatched)}/{len(measured)} rows snap to the wrong die: {mismatched[:5]}"


@pytest.mark.parametrize("msr", _MSRS)
def test_map_offset_is_the_offset_actually_encoded(msr):
    """The reported map_offset must equal the shared geometry's offset -- the
    regression guard against reintroducing a decorative random value."""
    payload = mock.get_msr_file(msr, _CLASS, _TOTAL_IMAGES)
    # The geometry is keyed on the PROGRAM, so resolve the key the provider used
    # rather than passing the msr and relying on these fixtures happening to be
    # parentless. Spelled out because the two coincide here: a future fixture
    # WITH a parent would otherwise compare against the wrong geometry and pass
    # or fail for reasons that have nothing to do with map_offset.
    parent = find_meas_hist_by_msr(msr)
    program_key = parent["recipe_name"] if parent else msr
    geom = mock._wafer_geometry(program_key)
    assert payload["exe_detail_info"]["map_offset"] == f"{geom.offset_x_nm},{geom.offset_y_nm}"
