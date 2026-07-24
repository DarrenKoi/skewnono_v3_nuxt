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

from back_dev_home.msr_file.providers import mock

_CLASS = "ADI"
_TOTAL_IMAGES = 40

# Swept, not single. A one-MSR version of this test passes against a mock that
# ignores map_offset entirely: snapping tolerates error up to 0.5*pitch, and a
# lucky seed (MSR-CONTRACT-0001 draws 0.11*pitch) stays inside that basin even
# with the +-0.3*pitch within-die jitter on top. Only seeds whose offset/pitch
# ratio exceeds the basin expose the incoherence, so the sweep is what gives
# this test its teeth -- 0013 (0.56*pitch_y) and 0021 (0.50) are the detectors.
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
    geom = mock._wafer_geometry(msr)
    assert payload["exe_detail_info"]["map_offset"] == f"{geom.offset_x_nm},{geom.offset_y_nm}"
