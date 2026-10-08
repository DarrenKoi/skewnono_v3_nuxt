"""The mock's fabricated value model (OFFICE-VERIFY, see the mock docstring).

Not office facts: these pin the structure the 시계열 비교 page relies on at home —
a site pattern that repeats across lots, re-measurements that agree, a slow drift
with the odd excursion, and values that do not move as a file ages.
"""

import statistics
from datetime import date, timedelta

from backend.afm.providers import mock

TOOLS = ("MAP608", "MAPC01", "5EAP1501")


def _series(tool, recipe_name):
    """(row, first-block MEAN, per-point values) of every measurement of a recipe."""
    out = []
    for row in mock.list_afm_files(tool):
        if row["recipe_name"] != recipe_name:
            continue
        detail = mock.get_afm_file_detail(row["filename"], tool)
        if not detail["summary"] or not detail["data"]:
            continue
        column = next(k for k in detail["summary"][0] if k.endswith("(nm)"))
        block = detail["summary"][0]["Site"]
        mean = next(r[column] for r in detail["summary"] if r["Site"] == block and r["ITEM"] == "MEAN")
        # By point, not by row: stored order differs from one measurement to the next.
        first_lap = sorted(detail["data"][:row["point_count"]], key=lambda r: r["measurement_point"])
        values = [r[column] for r in first_lap]
        out.append((row, mean, values))
    return out


def test_the_site_pattern_repeats_across_lots():
    series = _series("MAP608", "BSOXCMP_CORRELATION_36PT")
    assert len(series) >= 2
    deviations = [[v - statistics.fmean(values) for v in values] for _, _, values in series]
    first = deviations[0]
    for other in deviations[1:]:
        assert statistics.correlation(first, other) > 0.5


def test_a_remeasured_sample_agrees_with_itself():
    by_sample = {}
    for row, mean, values in _series("MAPC01", "RL1C_L1_XDEC_5MM_LINE"):
        by_sample.setdefault((row["lot_id"], row["slot_number"]), []).append((row, mean, values))
    pairs = [runs for runs in by_sample.values() if len(runs) > 1]
    assert pairs
    for runs in pairs:
        if any(mock._is_excursion(row) for row, *_ in runs):
            continue
        means = [mean for _, mean, _ in runs]
        within = statistics.fmean(statistics.stdev(values) for _, _, values in runs)
        assert max(means) - min(means) < 2 * within


def test_the_series_drifts_and_holds_an_excursion():
    # Which files fall in the window moves daily, so look across every recipe.
    found = 0
    for tool in TOOLS:
        for recipe_name in {row["recipe_name"] for row in mock.list_afm_files(tool)}:
            series = _series(tool, recipe_name)
            excursions = [row for row, _, _ in series if mock._is_excursion(row)]
            if len(series) < 3 or not excursions:
                continue
            found += 1
            centre = statistics.median(mean for _, mean, _ in series)
            assert all(mean - centre > 4 for row, mean, _ in series if mock._is_excursion(row))
            # An excursion brings the tool-health signals with it.
            detail = mock.get_afm_file_detail(excursions[0]["filename"], tool)
            assert any(r["State"] == "FAILED" or not r["Valid"] for r in detail["data"])
    assert found


def test_a_file_reads_the_same_as_it_ages(monkeypatch):
    day = date(2026, 10, 3)
    monkeypatch.setattr(mock, "_today", lambda: day)
    row = mock.list_afm_files("MAP608")[3]
    before = mock.get_afm_file_detail(row["filename"], "MAP608")
    monkeypatch.setattr(mock, "_today", lambda: day + timedelta(days=2))
    assert mock.get_afm_file_detail(row["filename"], "MAP608") == before
