"""The tttm and pm_planning office ADAPTERS, exercised at home against doubles.

These two templates are the only office adapters that COMPUTE rather than
reshape: pairwise tool skew, recipe-centred offsets, MDC epoch boundaries, a
fleet-relative spec window. Every other adapter's bugs are shape bugs that
`tests/test_office_adapter_parity.py` or the office run itself would catch;
these have arithmetic that is wrong silently and only at the office, where the
feedback loop is a plane ride long.

So the sources are replaced by doubles and the maths is checked here. What is
faked is exactly the three network boundaries — the run index (`recent_runs`),
the object store (`load_points`), and the roster/MDC/maintenance reads. Nothing
inside the adapters is stubbed, so the estimator, the epoch filter, the matrix
construction and the contract assembly all run for real.

Home skip rule: none. Both modules import cleanly without company access (their
network calls are all inside functions), which is the property that makes this
file possible — see `project_importorskip_hides_broken_office_tests`, the
failure mode where an office-gated test file silently collects nothing.

Run:  .venv/bin/python -m pytest tests/test_office_tttm_pm_planning.py
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatch

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam._analysis_window import (
    DEFAULT_WINDOW_WEEKS,
    WINDOW_WEEKS_CHOICES,
    window_days,
)
from back_dev_home.ebeam._office_mdc import MdcChange
from back_dev_home.ebeam._office_msr_cd import Point, RunRef, RunSet
from back_dev_home.ebeam.pm_planning.contracts import FleetPayload
from back_dev_home.ebeam.pm_planning.providers import office_example as pm_office
from back_dev_home.ebeam.tttm import contracts as tttm_contracts
from back_dev_home.ebeam.tttm.contracts import TttmCheckPayload
from back_dev_home.ebeam.tttm.providers import office_example as tttm_office


KST = timezone(timedelta(hours=9))

# UTC-labelled, and that is not a shortcut. The office indices store KST wall
# clock with no offset and `_office_search.parse_dt` labels such a string UTC,
# so every timestamp an adapter sees is a KST reading wearing a UTC tag. Doubles
# that handed back honestly-KST datetimes would silently absorb a nine-hour
# error in any adapter that mixed the two conventions — which is exactly the
# defect this file exists to catch, so the doubles must lie the same way the
# source does.
ANCHOR = datetime(2026, 5, 31, 14, 0, tzinfo=timezone.utc)

# Three tools with a known truth: B reads 0.10 nm high and C 0.20 nm low. Every
# assertion about a skew below is that truth read back out of the estimator.
TOOLS = ("ECXDX001", "ECXDX002", "ECXDX003")
BIAS = {"ECXDX001": 0.0, "ECXDX002": 0.10, "ECXDX003": -0.20}
BASE_CD = 32.0  # sits in the 25-50 band, like the mock's measured cells
# The window every adapter call below gathers over unless the test is ABOUT
# the window. The doubles carry 6 days of runs, inside every choice.
WEEKS = DEFAULT_WINDOW_WEEKS


def _roster_rows(eqp_ids=TOOLS, fab_name="R3", model="CG6300"):
    """sem_list rows in the shape `fleet_rows` filters."""
    return [
        {
            "eqp_id": eqp_id,
            "eqp_model_cd": model,
            "fab_name": fab_name,
            "fac_id": "R3",
            "vendor_nm": "HITACHI",
        }
        for eqp_id in eqp_ids
    ]


def _points(eqp_id: str, *, parameters=("CD_X", "CD_Y"), vac=500, cd=None):
    """A run's measured sites: 5 per parameter, scattered around the tool's CD.

    Five points per parameter, not one, because collapsing a run to a median is
    the property under test in `test_a_run_is_one_sample_not_hundreds`.
    """
    value = BASE_CD + BIAS.get(eqp_id, 0.0) if cd is None else cd
    return tuple(
        Point(
            parameter=parameter,
            # Symmetric scatter, so the median is exactly `value` and an
            # assertion can be an equality rather than an approximation.
            cd_value=value + offset,
            vac=vac,
            mag=250030,
            chip=f"{index},0",
            mp=index + 1,
            method="Width",
            object_type="Line",
        )
        for parameter in parameters
        for index, offset in enumerate((-0.2, -0.1, 0.0, 0.1, 0.2))
    )


def _runs(eqp_ids=TOOLS, recipes=("ADI/R1", "ADI/R2"), days=6):
    """`days` runs per tool per recipe, one a day, oldest first."""
    out = []
    for eqp_id in eqp_ids:
        for recipe in recipes:
            for back in range(days):
                at = ANCHOR - timedelta(days=back)
                out.append(
                    RunRef(
                        msr=f"{at:%Y%m%d}_{recipe.split('/')[-1]}_{eqp_id}",
                        eqp_id=eqp_id,
                        recipe_name=recipe.split("/")[-1],
                        full_name=recipe,
                        lot_id=f"LOT{back:03d}",
                        at=at,
                        pkl=f"pkl/{eqp_id}/{recipe}/{back}",
                    )
                )
    return tuple(out)


@pytest.fixture(autouse=True)
def _fresh_axis_map():
    """Clear the process-wide axis-map cache around every test.

    `_axis_rules` is `lru_cache(maxsize=1)` over a function taking no
    arguments, so the FIRST call in a process fixes the mapping for the rest of
    it — correct in production (the env is read once at boot) but it makes test
    order load-bearing here, and an ordering-dependent suite is one that passes
    until someone adds a test above yours.
    """
    from back_dev_home.ebeam._office_msr_cd import _axis_rules

    _axis_rules.cache_clear()
    yield
    _axis_rules.cache_clear()


@pytest.fixture
def sources(monkeypatch):
    """Patch the three network boundaries of BOTH adapters at once.

    Returns a mutable dict the test edits before calling the adapter, so each
    case reads as "these are the measurements, this is the payload" rather than
    as a stack of monkeypatch calls.
    """
    # pm_planning filters meas_hist down to the fab's CD-monitoring recipe, and
    # which recipe that is has no office source — it is an env knob. Point it at
    # a recipe the doubles actually carry, which exercises the knob too.
    monkeypatch.setenv("SKEWNONO_CD_MONITOR_RECIPE", "ADI/R1")

    state: dict = {
        "roster": _roster_rows(),
        "runs": _runs(),
        "points": _points,
        "mdc": [],
        "maintenance": {},
        "bsm": {},
    }

    def fake_recent_runs(tool_type, fab_name, eqp_ids, start, end, *, recipe=None, per_tool=12):
        keep = [
            run
            for run in state["runs"]
            if run.eqp_id in eqp_ids
            and start <= run.at <= end
            and (recipe is None or recipe in (run.full_name, run.recipe_name))
        ]
        return RunSet(tuple(keep), ())

    def fake_load_points(pkl: str):
        eqp_id = pkl.split("/")[1]
        return state["points"](eqp_id)

    for module in (tttm_office, pm_office):
        monkeypatch.setattr(module, "get_sem_list", lambda: state["roster"])
        monkeypatch.setattr(module, "get_anchor_time", lambda: ANCHOR)
        monkeypatch.setattr(module, "recent_runs", fake_recent_runs)
        monkeypatch.setattr(module, "load_points", fake_load_points)
        monkeypatch.setattr(module, "mdc_changes", lambda *a, **k: state["mdc"])

    monkeypatch.setattr(
        tttm_office, "maintenance_events", lambda *a, **k: state["maintenance"]
    )
    monkeypatch.setattr(
        pm_office, "maintenance_events", lambda *a, **k: state["maintenance"]
    )
    monkeypatch.setattr(pm_office, "_bsm_by_tool", lambda *a, **k: state["bsm"])
    return state


# ── tttm ──────────────────────────────────────────────────────────────────


def _spy_recent_runs(monkeypatch, module, state):
    """Record what the adapter asked `recent_runs` for, still answering the doubles."""
    asked: dict = {}

    def spy(tool_type, fab_name, eqp_ids, start, end, *, recipe=None, per_tool=12):
        asked["start"], asked["end"], asked["per_tool"] = start, end, per_tool
        keep = [
            run
            for run in state["runs"]
            if run.eqp_id in eqp_ids
            and start <= run.at <= end
            and (recipe is None or recipe in (run.full_name, run.recipe_name))
        ]
        return RunSet(tuple(keep), ())

    monkeypatch.setattr(module, "recent_runs", spy)
    return asked


@pytest.mark.parametrize("weeks", WINDOW_WEEKS_CHOICES)
def test_tttm_window_moves_the_lookback_and_the_run_cap_together(sources, monkeypatch, weeks):
    """The knob must widen the EVIDENCE, not just the cut-off.

    The lookback used to be a fixed 60 days behind a fixed cap of 10 runs, which
    made the cap the real window: a daily-monitoring tool contributed its last
    ten days whatever the lookback said. Asserted per choice so a cap that
    stopped scaling — the regression that would make "4주" gather a week —
    fails on the widest window rather than passing on the default.
    """
    asked = _spy_recent_runs(monkeypatch, tttm_office, sources)
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, weeks)

    assert payload["window_weeks"] == weeks
    assert (asked["end"] - asked["start"]).days == window_days(weeks)
    assert asked["per_tool"] == tttm_office.runs_per_tool(weeks)
    assert asked["per_tool"] == tttm_office.RUNS_PER_TOOL_PER_WEEK * weeks


def test_tttm_trend_spans_the_window_not_a_private_cut_off(sources):
    """Every day the window gathered is a day the trend may show.

    The doubles carry six days of runs; a one-week window keeps them all, so
    the trend must too. There was a fixed 30-day trend cut-off separate from
    the window — harmless while the window was wider than it, and a silent
    truncation the moment the window became the user's to choose.
    """
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, 1)
    days = {point["date"] for point in payload["trend"]}
    assert len(days) == 6


def test_tttm_unavailable_branches_echo_the_window(sources):
    sources["runs"] = ()
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, 2)
    assert payload["available"] is False
    assert payload["window_weeks"] == 2
    assert "14일간" in payload["summary"], "the empty answer names the span it was empty over"


def test_tttm_payload_matches_the_contract(sources):
    assert_matches(tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS), TttmCheckPayload)


def test_tttm_recovers_the_pairwise_skew_it_was_given(sources):
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    assert payload["available"] is True
    cells = payload["occupied_cells"]
    assert cells, "three tools running two shared recipes must occupy cells"

    cell = cells[0]
    assert cell["tier"] == "direct", "a recipe both tools ran is direct evidence"
    assert cell["confidence"] == "High", "6 runs/tool is above HIGH_CONFIDENCE_RUNS"
    block = cell["direct_skew_matrix"]
    assert block is not None
    index = {eqp_id: i for i, eqp_id in enumerate(block["tools"])}

    # The truth injected in BIAS, read back out: |0.10 - 0.00|, |0.00 - -0.20|,
    # |0.10 - -0.20|. Exact, because the fake scatter is symmetric.
    assert block["values"][index["ECXDX001"]][index["ECXDX002"]] == pytest.approx(0.10)
    assert block["values"][index["ECXDX001"]][index["ECXDX003"]] == pytest.approx(0.20)
    assert block["values"][index["ECXDX002"]][index["ECXDX003"]] == pytest.approx(0.30)


def test_tttm_matrices_are_symmetric_with_a_zero_diagonal(sources):
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    blocks = [payload["fleet_today"]["matrix"]]
    for cell in payload["occupied_cells"]:
        blocks += [b for b in (cell["direct_skew_matrix"], cell["predicted_skew_matrix"]) if b]
    for block in blocks:
        size = len(block["tools"])
        for row in range(size):
            assert len(block["values"][row]) == size
            assert block["values"][row][row] == 0
            for col in range(row):
                assert block["values"][row][col] == block["values"][col][row]


def test_tttm_median_cd_stays_inside_the_band_it_is_filed_under(sources):
    # The cross-field law tests/test_contract.py enforces: band and median must
    # come from ONE row set. Derived from the same values here by construction,
    # and asserted so a future edit cannot separate them.
    for cell in tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)["occupied_cells"]:
        assert cell["cd_band"] == "25-50"
        assert 25.0 <= cell["median_cd_nm"] < 50.0


def test_a_run_is_one_sample_not_hundreds(sources):
    """Ten points per parameter must weigh the same as two.

    The pseudo-replication guard, stated as a behaviour: if the adapter pooled
    raw points instead of collapsing each run to a median, doubling the points
    of one tool would move its offset. It must not.
    """
    baseline = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)

    def fat_points(eqp_id: str):
        return _points(eqp_id) * 4  # same distribution, 4x the rows

    sources["points"] = fat_points
    fattened = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)

    assert [cell["cell_id"] for cell in fattened["occupied_cells"]] == [
        cell["cell_id"] for cell in baseline["occupied_cells"]
    ]
    for fat, thin in zip(
        fattened["occupied_cells"], baseline["occupied_cells"], strict=True
    ):
        assert fat["direct_skew_matrix"] == thin["direct_skew_matrix"]


def test_a_recipe_only_one_tool_ran_yields_no_skew_rather_than_zero(sources):
    """The `contrastRecipes === 0` refusal, which is the worst way to be wrong.

    Give every tool its OWN recipe: centring each against itself would report
    0.000 for every pair, which reads as a perfectly matched fleet. The adapter
    must decline instead.
    """
    sources["runs"] = (
        _runs(("ECXDX001",), ("ADI/ONLY_A",))
        + _runs(("ECXDX002",), ("ADI/ONLY_B",))
        + _runs(("ECXDX003",), ("ADI/ONLY_C",))
    )
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    assert_matches(payload, TttmCheckPayload)
    assert payload["occupied_cells"] == []
    for row in payload["fleet_today"]["matrix"]["values"]:
        assert all(value in (0.0, None) for value in row)


def test_an_unresolvable_axis_empties_the_cells_and_says_so(sources):
    """Caveat 1 of the module docstring, as behaviour rather than prose."""
    sources["points"] = lambda eqp_id: _points(eqp_id, parameters=("Para_13",))
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)

    assert_matches(payload, TttmCheckPayload)
    assert payload["available"] is True, "the fleet view still works"
    assert payload["occupied_cells"] == [], "no axis, no cell — never a default X"
    assert "측정 방향" in payload["summary"]
    # The axis-free parts of the payload must survive: that is the whole reason
    # this degrades instead of erroring.
    assert payload["fleet_today"]["consensus_deviation"]
    assert payload["trend"]


def test_an_mdc_change_cuts_the_comparison_window(sources):
    """Rule 3: nothing before the fab's last MDC edit may enter a cell."""
    cutoff = (ANCHOR - timedelta(days=2)).date()
    sources["mdc"] = [
        MdcChange(
            eqp_id="ECXDX002",
            condition="500V_HR_0Deg",
            beam_condition="500V_HR",
            axis="X",
            on=cutoff,
            old_value=1.0041,
            new_value=1.0032,
        )
    ]
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)

    epochs = {cell["mdc_epoch"] for cell in payload["occupied_cells"]}
    labelled = f"e{cutoff:%Y%m%d}"
    assert labelled in epochs, "the X cells must be filed under the new epoch"
    # Y is untouched by a 0Deg edit, so it keeps the open epoch.
    by_axis = {cell["axis"]: cell["mdc_epoch"] for cell in payload["occupied_cells"]}
    assert by_axis["X"] == labelled
    assert by_axis["Y"] == "e0"

    assert payload["mdc_history"], "the edit is shown to the engineer"
    assert any(m["kind"] == "hard" for m in payload["epoch_markers"])


def test_tttm_echoes_the_triple_it_was_asked_about_on_every_branch(sources):
    asked = tttm_office.get_tttm_check("cdsem", "R3", "ADI/R1", "CD_X", WEEKS)
    assert (asked["fab_name"], asked["recipe_id"], asked["parameter"]) == (
        "R3", "ADI/R1", "CD_X",
    )
    # ... including where there is nothing to answer with.
    sources["roster"] = _roster_rows(eqp_ids=("ECXDX001",))
    lonely = tttm_office.get_tttm_check("cdsem", "R3", "ADI/R1", "CD_X", WEEKS)
    assert lonely["available"] is False
    assert (lonely["fab_name"], lonely["recipe_id"], lonely["parameter"]) == (
        "R3", "ADI/R1", "CD_X",
    )
    # The ROSTER survives — one tool is not a comparison, but it is still the
    # fab's tool, and the client's picker is drawn from this list. What must
    # stay empty is the comparison itself, asserted just below. (An unknown
    # fab does answer `tools: []`, because there is no roster to carry — see
    # test_an_unknown_fab_is_available_false_not_an_error.)
    assert [tool["eqp_id"] for tool in lonely["tools"]] == ["ECXDX001"]
    assert lonely["occupied_cells"] == []
    assert lonely["fleet_today"]["matrix"]["tools"] == []


def test_a_parameter_filter_narrows_the_rows(sources):
    """One feature, not a relabelling: the X cell survives and Y disappears."""
    payload = tttm_office.get_tttm_check("cdsem", "R3", "ADI/R1", "CD_X", WEEKS)
    assert {cell["axis"] for cell in payload["occupied_cells"]} == {"X"}


def test_an_unknown_fab_is_available_false_not_an_error(sources):
    sources["roster"] = _roster_rows(fab_name="M16A")
    payload = tttm_office.get_tttm_check("cdsem", "ZZZ-NOT-A-FAB", None, None, WEEKS)
    assert_matches(payload, TttmCheckPayload)
    assert payload["available"] is False
    assert payload["tools"] == []
    assert payload["fab_name"] == "ZZZ-NOT-A-FAB"


def test_the_roster_names_each_tool_once(sources):
    # sem_list really does hand back duplicate eqp_ids (~10 of 300 mock rows),
    # and a repeated id would give the matrix two identical axes.
    sources["roster"] = _roster_rows() + _roster_rows(eqp_ids=("ECXDX002",))
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    ids = [tool["eqp_id"] for tool in payload["tools"]]
    assert len(ids) == len(set(ids))


def test_matrix_axes_stay_inside_the_advertised_roster(sources):
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    roster = {tool["eqp_id"] for tool in payload["tools"]}
    assert set(payload["fleet_today"]["matrix"]["tools"]) <= roster
    for deviation in payload["fleet_today"]["consensus_deviation"]:
        assert deviation["eqp_id"] in roster
    for cell in payload["occupied_cells"]:
        for block in (cell["direct_skew_matrix"], cell["predicted_skew_matrix"]):
            if block is not None:
                assert set(block["tools"]) <= roster


def test_current_tolerance_sits_inside_its_own_range(sources):
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    bounds = payload["tolerance_range"]
    assert bounds["min"] <= payload["current_tolerance"] <= bounds["max"]
    assert bounds["step"] > 0


# ── pm_planning ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("weeks", WINDOW_WEEKS_CHOICES)
def test_pm_window_moves_the_lookback_and_the_run_cap_together(sources, monkeypatch, weeks):
    """pm-tune joins this payload with the tttm check — one span, one label."""
    asked = _spy_recent_runs(monkeypatch, pm_office, sources)
    sources["bsm"] = _bsm()
    fleet = pm_office.get_pm_planning_fleet("R3", weeks)

    assert fleet["window_weeks"] == weeks
    assert (asked["end"] - asked["start"]).days == window_days(weeks)
    assert asked["per_tool"] == pm_office.runs_per_tool(weeks)


@pytest.mark.parametrize("weeks", (min(WINDOW_WEEKS_CHOICES), max(WINDOW_WEEKS_CHOICES)))
def test_pm_events_keep_their_own_lookback_whatever_the_window(sources, monkeypatch, weeks):
    """`post_pm_at` is "when was this tool last touched", not sized evidence.

    The window request bounded PM events along with the runs, so at the 2-week
    default a PM three weeks old disappeared and pm-tune's "freshest out of PM"
    pick moved — a widening nobody asked for (oc-review 2026-08-26). Asserted at
    both ends of the choices so the lookback is provably independent of them.
    """
    captured = {}

    def spy(fab, eqp_ids, start, end):
        captured["span"] = (end - start).days
        return {}

    monkeypatch.setattr(pm_office, "maintenance_events", spy)
    sources["bsm"] = _bsm()
    pm_office.get_pm_planning_fleet("R3", weeks)

    assert captured["span"] == pm_office.PM_LOOKBACK_DAYS
    assert captured["span"] > window_days(weeks) or weeks == max(WINDOW_WEEKS_CHOICES)


def test_pm_empty_roster_echoes_the_window(sources):
    sources["roster"] = []
    fleet = pm_office.get_pm_planning_fleet("R3", 1)
    assert fleet["tools"] == []
    assert fleet["window_weeks"] == 1


def _bsm(eqp_ids=TOOLS, sharpness=8.00, noise=6.28, days=3, start=None):
    """BSM readings in the shape `_bsm_by_tool` returns them (UTC-tagged)."""
    origin = start or ANCHOR
    return {
        eqp_id: [(origin - timedelta(days=back), sharpness, noise) for back in range(days)]
        for eqp_id in eqp_ids
    }


def test_pm_payload_matches_the_contract(sources):
    sources["bsm"] = _bsm()
    assert_matches(pm_office.get_pm_planning_fleet("R3", WEEKS), FleetPayload)


def test_pm_cells_are_keyed_on_the_advertised_grid(sources):
    sources["bsm"] = _bsm()
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    beams, axes = set(fleet["beam_conditions"]), set(fleet["axes"])
    for tool in fleet["tools"]:
        seen = set()
        for cell in tool["cells"]:
            assert (cell["beam"], cell["axis"]) not in seen
            seen.add((cell["beam"], cell["axis"]))
            assert cell["beam"] in beams and cell["axis"] in axes
    for cell in fleet["consensus"]:
        assert cell["beam"] in beams and cell["axis"] in axes


def test_pm_gap_is_measured_against_the_fleet_median(sources):
    sources["bsm"] = _bsm()
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    consensus = {(c["beam"], c["axis"]): c["consensus"] for c in fleet["consensus"]}
    # BIAS is 0.0 / +0.10 / -0.20, so the fleet median is the unbiased tool.
    assert consensus[("500V", "X")] == pytest.approx(BASE_CD)

    gaps = {
        tool["eqp_id"]: {(c["beam"], c["axis"]): c["gap"] for c in tool["cells"]}
        for tool in fleet["tools"]
    }
    assert gaps["ECXDX002"][("500V", "X")] == pytest.approx(0.10)
    assert gaps["ECXDX003"][("500V", "X")] == pytest.approx(-0.20)
    for tool in fleet["tools"]:
        for cell in tool["cells"]:
            assert cell["skew"] == cell["gap"], "one signed distance, not two"


def test_pm_spec_window_is_ordered_and_fleet_relative(sources):
    sources["bsm"] = _bsm()
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    for tool in fleet["tools"]:
        gate = tool["gate"]
        assert gate["cd_spec_lower"] <= gate["cd_spec_upper"]
        # Docstring note 2: the window is the fleet median ±1%, the fab's
        # stated action limit — not the mock's fabricated ±0.5 nm.
        width = gate["cd_spec_upper"] - gate["cd_spec_lower"]
        assert width == pytest.approx(2 * BASE_CD * pm_office.ACTION_LIMIT_RATIO, abs=0.01)


def test_pm_a_tool_with_no_measurement_holds(sources):
    """An absent reading is not a passed one."""
    sources["bsm"] = _bsm()
    sources["runs"] = _runs(eqp_ids=("ECXDX001", "ECXDX002"))
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    silent = next(t for t in fleet["tools"] if t["eqp_id"] == "ECXDX003")
    assert silent["gate"]["verdict"] == "hold"
    assert silent["gate"]["cd_in_spec"] is False
    assert silent["cells"] == []


def test_pm_bsm_outlier_is_judged_against_the_fleet_not_a_fixed_band(sources):
    """Docstring note 3: the mock's absolute band would hold the whole fab."""
    readings = _bsm()
    # Every tool sits at the real doc's Ave. Noise (6.277), which is OUTSIDE
    # spec_range_mock's 6.65-6.95. A fleet-relative test must pass them all.
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    sources["bsm"] = readings
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    assert all(tool["gate"]["bsm_in_spec"] for tool in fleet["tools"])

    # Now move one tool far off its siblings: it alone must fail.
    readings["ECXDX003"] = [(ANCHOR, 8.00, 9.50)]
    sources["bsm"] = readings
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    verdicts = {t["eqp_id"]: t["gate"]["bsm_in_spec"] for t in fleet["tools"]}
    assert verdicts["ECXDX003"] is False
    assert verdicts["ECXDX001"] is True


def test_pm_a_fab_with_no_roster_is_empty_not_an_error(sources):
    sources["roster"] = _roster_rows(fab_name="M16A")
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    assert_matches(fleet, FleetPayload)
    assert fleet["tools"] == []
    assert fleet["consensus"] == []
    assert fleet["fab_name"] == "R3"


def test_pm_and_tttm_agree_on_the_roster(sources):
    """pm-tune joins the two payloads BY eqp_id — a divergence empties the page."""
    sources["bsm"] = _bsm()
    pm_ids = {tool["eqp_id"] for tool in pm_office.get_pm_planning_fleet("R3", WEEKS)["tools"]}
    tttm_ids = {
        tool["eqp_id"]
        for tool in tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)["tools"]
    }
    assert pm_ids == tttm_ids


def test_pm_epoch_history_carries_the_edit_that_opened_it(sources):
    sources["bsm"] = _bsm()
    when = date(2026, 5, 20)
    sources["mdc"] = [
        MdcChange(
            eqp_id="ECXDX001",
            condition="500V_HR_0Deg",
            beam_condition="500V_HR",
            axis="X",
            on=when,
            old_value=1.0041,
            new_value=1.0032,
        )
    ]
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    edited = next(t for t in fleet["tools"] if t["eqp_id"] == "ECXDX001")
    untouched = next(t for t in fleet["tools"] if t["eqp_id"] == "ECXDX002")

    assert edited["gate"]["mdc_changed"] is True
    assert untouched["gate"]["mdc_changed"] is False
    assert edited["epoch_history"] == [
        {"epoch_start": when.isoformat(), "mdc": 1.0032, "bsm_sharpness_avg": 8.0}
    ]
    assert untouched["epoch_history"] == []


# ── the fixes the outside review found ────────────────────────────────────


def test_features_at_different_cds_do_not_share_a_band(sources):
    """Per-feature grain: a run measuring 31 nm and 68 nm occupies TWO bands.

    Feasibility note 3.2 — a run carries several parameters at different
    nominal CDs. Reduced per RUN instead of per FEATURE, the two collapse to a
    ~50 nm median that lands in whichever band the mixture falls in, and the
    cell's action limit (1% of CD) is then drawn for a pattern size nobody
    measured. The contract law still passes, because band and median came from
    one row set — which is why this needs its own test.
    """
    def two_sizes(eqp_id: str):
        bias = BIAS.get(eqp_id, 0.0)
        return _points(eqp_id, parameters=("FINE_X",), cd=31.0 + bias) + _points(
            eqp_id, parameters=("WIDE_X",), cd=68.0 + bias
        )

    sources["points"] = two_sizes
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)

    bands = {cell["cd_band"] for cell in payload["occupied_cells"]}
    assert bands == {"25-50", "50-100"}, f"expected both bands, got {bands}"
    for cell in payload["occupied_cells"]:
        low, high = (25.0, 50.0) if cell["cd_band"] == "25-50" else (50.0, 100.0)
        assert low <= cell["median_cd_nm"] < high

    # And the skew is still the injected truth in BOTH bands — the feature
    # centring must not have absorbed the 37 nm size difference into an offset.
    for cell in payload["occupied_cells"]:
        block = cell["direct_skew_matrix"]
        index = {eqp_id: i for i, eqp_id in enumerate(block["tools"])}
        assert block["values"][index["ECXDX002"]][index["ECXDX003"]] == pytest.approx(0.30)


def test_fleet_today_leaves_a_bridged_pair_null(sources):
    """Section 4's failure: a 2-hop estimate must not enter with equal standing.

    A and B share a recipe; C shares none. C's offset is still estimable, so a
    matrix that filled every pair with an offset difference would present the
    A-C cell as measured evidence. It has to be null — "not TTTM-able", which
    is what the contract already says a null means.
    """
    sources["runs"] = _runs(("ECXDX001", "ECXDX002"), ("ADI/SHARED",)) + _runs(
        ("ECXDX003",), ("ADI/ALONE",)
    )
    matrix = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)["fleet_today"]["matrix"]
    index = {eqp_id: i for i, eqp_id in enumerate(matrix["tools"])}

    assert matrix["values"][index["ECXDX001"]][index["ECXDX002"]] == pytest.approx(0.10)
    assert matrix["values"][index["ECXDX001"]][index["ECXDX003"]] is None
    assert matrix["values"][index["ECXDX002"]][index["ECXDX003"]] is None


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        ("no_parameter", "측정한 이력이 없어"),
        ("no_axis", "측정 방향"),
        ("no_contrast", "함께 측정한"),
    ],
)
def test_an_empty_grid_names_its_own_cause(sources, setup, expected):
    """Three causes render identically on screen; each must say which it was."""
    if setup == "no_parameter":
        payload = tttm_office.get_tttm_check("cdsem", "R3", "ADI/R1", "NOT_A_PARAM", WEEKS)
    elif setup == "no_axis":
        sources["points"] = lambda eqp_id: _points(eqp_id, parameters=("Para_13",))
        payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    else:
        sources["runs"] = (
            _runs(("ECXDX001",), ("ADI/ONLY_A",))
            + _runs(("ECXDX002",), ("ADI/ONLY_B",))
            + _runs(("ECXDX003",), ("ADI/ONLY_C",))
        )
        payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)

    assert payload["occupied_cells"] == []
    assert expected in payload["summary"], payload["summary"]


def test_pm_epoch_window_reads_past_the_measurement_window(sources):
    """MDC changes are rare; a 30-day lookback would empty every history.

    The measurement window is at most four weeks, the mock's own epoch
    spacing is 60+ days, so
    an adapter that reused one window for both would report "never changed" for
    a tool edited two months ago.
    """
    captured = {}

    def spy(fab, start, end):
        captured["span"] = (end - start).days
        return []

    import back_dev_home.ebeam.pm_planning.providers.office_example as mod
    original, mod.mdc_changes = mod.mdc_changes, spy
    try:
        sources["bsm"] = _bsm()
        pm_office.get_pm_planning_fleet("R3", WEEKS)
    finally:
        mod.mdc_changes = original

    assert captured["span"] > window_days(max(WINDOW_WEEKS_CHOICES))
    assert captured["span"] == pm_office.EPOCH_LOOKBACK_DAYS


def test_pm_epoch_bsm_window_is_on_the_sources_clock(sources):
    """The nine hours: an epoch boundary must be compared tag-to-tag.

    `parse_dt` hands back KST wall clock labelled UTC. A KST-labelled midnight
    would sit nine hours earlier than those readings, so a reading from 15:00
    the previous day would count as opening this epoch. The reading below is
    placed in exactly that gap.
    """
    when = date(2026, 5, 20)
    # 23:00 on the 19th, as stored (KST wall clock) and therefore UTC-tagged.
    # Under a KST-labelled boundary (= 15:00Z on the 19th) this counts as after
    # the change; under the correct UTC-tagged one it does not.
    sources["bsm"] = {
        "ECXDX001": [
            (datetime(2026, 5, 22, 9, 0, tzinfo=timezone.utc), 8.00, 6.28),
            (datetime(2026, 5, 19, 23, 0, tzinfo=timezone.utc), 7.10, 6.28),
        ]
    }
    sources["mdc"] = [
        MdcChange(
            eqp_id="ECXDX001",
            condition="500V_HR_0Deg",
            beam_condition="500V_HR",
            axis="X",
            on=when,
            old_value=1.0041,
            new_value=1.0032,
        )
    ]
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    edited = next(t for t in fleet["tools"] if t["eqp_id"] == "ECXDX001")
    # 8.00 only — the 19th's 7.10 belongs to the PREVIOUS epoch.
    assert edited["epoch_history"][0]["bsm_sharpness_avg"] == pytest.approx(8.00)


def test_pm_prev_post_delta_splits_the_runs_at_the_pm(sources):
    """The before/after split must parse both sides, not compare ISO strings."""
    from back_dev_home.ebeam._office_bm_pm import MaintEvent

    boundary = ANCHOR - timedelta(days=3)
    sources["bsm"] = _bsm()
    sources["maintenance"] = {
        "ECXDX001": [
            MaintEvent(
                eqp_id="ECXDX001",
                category="PM",
                down_at=(boundary - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S"),
                # Stored offset-less, the way the index carries it.
                up_at=boundary.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        ]
    }

    def shifted(eqp_id: str):
        # Every tool reads BASE_CD; the post-PM half of ECXDX001 reads 0.5 high.
        return _points(eqp_id)

    sources["points"] = shifted
    fleet = pm_office.get_pm_planning_fleet("R3", WEEKS)
    gate = next(t for t in fleet["tools"] if t["eqp_id"] == "ECXDX001")["gate"]

    assert gate["post_pm_at"] == boundary.strftime("%Y-%m-%dT%H:%M:%S")
    # Runs sit on both sides of the boundary and read identically, so the delta
    # is 0.0 — not None, which is what a split that put every run on one side
    # would produce.
    assert gate["prev_post_delta"] == pytest.approx(0.0)


# ── the fixes the second review pass found ────────────────────────────────


def test_a_disconnected_pair_gets_no_bridged_skew(sources):
    """Feasibility 3.5: a bridge needs a path, not merely two offsets.

    A+B share one recipe, C+D another, and the two groups share nothing. Each
    pair centres on ITS OWN recipe median, so those two reference points are
    set by disjoint sets of tools and the difference between an A offset and a
    C offset measures the gap between two unrelated origins. Emitting it as a
    `predicted` skew is worse than emitting nothing: the client cannot tell an
    artifact from a bridged estimate.
    """
    quad = ("ECXDX001", "ECXDX002", "ECXDX003", "ECXDX004")
    sources["roster"] = _roster_rows(eqp_ids=quad)
    sources["runs"] = _runs(("ECXDX001", "ECXDX002"), ("ADI/LEFT",)) + _runs(
        ("ECXDX003", "ECXDX004"), ("ADI/RIGHT",)
    )
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)

    for cell in payload["occupied_cells"]:
        for block in (cell["direct_skew_matrix"], cell["predicted_skew_matrix"]):
            if block is None:
                continue
            index = {eqp_id: i for i, eqp_id in enumerate(block["tools"])}
            if "ECXDX001" in index and "ECXDX003" in index:
                assert block["values"][index["ECXDX001"]][index["ECXDX003"]] is None, (
                    "tools in disconnected components must not be compared"
                )
            if "ECXDX001" in index and "ECXDX002" in index:
                # Within a component the comparison is still made.
                assert block["values"][index["ECXDX001"]][index["ECXDX002"]] is not None


def test_confidence_counts_runs_not_features(sources):
    """The pseudo-replication guard must also guard the number that vouches.

    One run measuring seven features is one wafer, not seven. Counting rows
    would clear HIGH_CONFIDENCE_RUNS on a single run — the estimator avoids
    exactly that, and the confidence label must not smuggle it back in.
    """
    features = tuple(f"{letter}_X" for letter in "ABCDEFG")
    sources["points"] = lambda eqp_id: _points(eqp_id, parameters=features)
    sources["runs"] = _runs(recipes=("ADI/ONE",), days=1)

    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    assert payload["occupied_cells"]
    for cell in payload["occupied_cells"]:
        assert cell["confidence"] != "High", (
            f"{cell['cell_id']}: one run per tool cannot be High confidence"
        )
        assert "실행 3건" in cell["labels"][0], cell["labels"]


def test_fleet_median_cd_is_none_when_the_day_spans_pattern_sizes(sources):
    """The client divides by 1% of this; a mixture puts the line between sizes."""
    def two_sizes(eqp_id: str):
        return _points(eqp_id, parameters=("FINE_X",), cd=31.0) + _points(
            eqp_id, parameters=("WIDE_X",), cd=68.0
        )

    sources["points"] = two_sizes
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    assert payload["fleet_today"]["median_cd_nm"] is None

    # One size only -> the number is meaningful and is reported.
    sources["points"] = lambda eqp_id: _points(eqp_id, parameters=("FINE_X",), cd=31.0)
    single = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    assert single["fleet_today"]["median_cd_nm"] == pytest.approx(31.0)


def test_a_band_edge_median_stays_inside_its_band(sources):
    """Band on the rounded value, or the law breaks exactly at the boundary.

    24.9997 bands as "<25" and then rounds to 25.0, which is outside "<25".
    Only at an edge, which is where nobody looks.
    """
    sources["points"] = lambda eqp_id: _points(eqp_id, parameters=("CD_X",), cd=24.9997)
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    assert payload["occupied_cells"]
    for cell in payload["occupied_cells"]:
        low, high = (0.0, 25.0) if cell["cd_band"] == "<25" else (25.0, 50.0)
        assert low <= cell["median_cd_nm"] < high, (
            f"{cell['median_cd_nm']} is outside {cell['cd_band']}"
        )


def test_missing_and_unrecorded_values_do_not_reach_the_payload(sources):
    """The value-domain the office really has: None CDs and a zero voltage.

    A double that only ever emits clean numbers leaves `as_float`'s None path
    and `beam_label`'s empty-label branch untested at home, which is where they
    would first run at the office.
    """
    def ragged(eqp_id: str):
        good = _points(eqp_id, parameters=("CD_X",))
        blank_cd = tuple(point._replace(cd_value=None) for point in good)
        no_voltage = tuple(point._replace(vac=0) for point in good)
        return good + blank_cd + no_voltage

    sources["points"] = ragged
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)
    assert_matches(payload, TttmCheckPayload)

    # The rows with no voltage have no beam to be filed under and are dropped;
    # the surviving cells are all real beams, and the CD is the clean one.
    assert payload["occupied_cells"]
    for cell in payload["occupied_cells"]:
        assert cell["beam_condition"] == "500V"
        assert cell["median_cd_nm"] == pytest.approx(BASE_CD, abs=0.25)
    assert payload["raw"]["dropped"]["no_cd"] > 0


# ── the office facts confirmed 2026-08-18 ─────────────────────────────────


def test_the_monitor_recipe_default_is_a_discovery_rule(monkeypatch):
    """CD monitoring is several recipes found by prefix, not one configured name.

    Each fab runs its own under its own name and they all start with
    CD_MONITOR (user-confirmed 2026-08-18), so the default has to FIND them
    rather than stand in for one. A default that matched a single literal name
    would answer 200 with an empty fleet at every fab but one.
    """
    from back_dev_home.ebeam import _office_msr_cd as shared

    monkeypatch.delenv(shared.MONITOR_RECIPE_ENV_VAR, raising=False)
    pattern = shared.monitor_recipe_pattern()
    assert "*" in pattern, "the default must be a wildcard, not a literal name"

    clause = shared._recipe_clause(pattern)
    kinds = {next(iter(term)) for term in clause["bool"]["should"]}
    assert kinds == {"wildcard"}
    fields = {
        field
        for term in clause["bool"]["should"]
        for field in term["wildcard"]
    }
    # All three identities, because different callers hold different ones.
    assert fields == {"full_name.keyword", "recipe_name.keyword", "class_name.keyword"}
    for term in clause["bool"]["should"]:
        # .keyword sub-fields are analyzed-text traps otherwise, and the fab's
        # casing is not something we get to assume.
        assert next(iter(term["wildcard"].values()))["case_insensitive"] is True

    # A per-fab name really does match the prefix.
    assert fnmatch("CD_MONITOR_M14A_001".casefold(), pattern.casefold())


def test_an_axis_glob_covers_a_family(monkeypatch):
    """The direction is in the name, but the naming varies widely per fab.

    A fab needing forty exact entries normally needs two or three patterns, so
    the map takes globs. An exact name still wins, so one odd parameter can be
    corrected without disturbing the family rule.
    """
    from back_dev_home.ebeam._office_msr_cd import AXIS_ENV_VAR, resolve_axis

    monkeypatch.setenv(AXIS_ENV_VAR, "*_HOR=X,*_VER=Y,GATE_HOR=Y")
    assert resolve_axis("TOP_HOR") == "X"
    assert resolve_axis("BOT_VER") == "Y"
    # Exact beats glob, even when they disagree.
    assert resolve_axis("GATE_HOR") == "Y"
    # Still no guessing for a name nothing matches.
    assert resolve_axis("Para_13") is None
    # The built-in table still fills gaps the env did not cover.
    assert resolve_axis("CD_X") == "X"


def test_the_axis_map_never_invents_a_direction(monkeypatch):
    """A malformed entry is ignored, not coerced into an axis."""
    from back_dev_home.ebeam._office_msr_cd import AXIS_ENV_VAR, resolve_axis

    monkeypatch.setenv(AXIS_ENV_VAR, "Para_13=Z,Para_14=,=X,Para_15=y")
    assert resolve_axis("Para_13") is None, "Z is not an axis"
    assert resolve_axis("Para_14") is None, "a blank axis is not an axis"
    assert resolve_axis("Para_15") == "Y", "lowercase is accepted"


def test_the_axis_map_is_scoped_to_the_recipe(monkeypatch):
    """One recipe's Para_13 is not another's — the same law routes.py enforces.

    `tttm/routes.py` refuses a `parameter` without a `recipe_id` because "the
    same name in another recipe measures something else entirely"
    (contracts.py). A map keyed on the bare name would contradict that: it
    files every recipe's Para_13 under one direction and is silently wrong for
    all but the one it was written against.
    """
    from back_dev_home.ebeam._office_msr_cd import AXIS_ENV_VAR, resolve_axis

    monkeypatch.setenv(
        AXIS_ENV_VAR,
        "ADI/CD_MONITOR_001:Para_13=X,ADI/*:Para_13=Y,Para_13=Y,*_HOR=X",
    )
    # Most specific wins: exact recipe > recipe glob > unscoped.
    assert resolve_axis("Para_13", "ADI/CD_MONITOR_001") == "X"
    assert resolve_axis("Para_13", "ADI/SOMETHING_ELSE") == "Y"
    assert resolve_axis("Para_13", "ETC/UNRELATED") == "Y"
    # An unscoped rule still applies to every recipe.
    assert resolve_axis("TOP_HOR", "ETC/UNRELATED") == "X"
    # A scoped rule cannot be judged without a recipe, so it does not apply;
    # the unscoped fallback still can.
    assert resolve_axis("Para_13") == "Y"


def test_a_scoped_rule_does_not_leak_to_another_recipe(monkeypatch):
    """The failure the scoping exists to prevent, stated directly."""
    from back_dev_home.ebeam._office_msr_cd import AXIS_ENV_VAR, resolve_axis

    monkeypatch.setenv(AXIS_ENV_VAR, "ADI/CD_MONITOR_001:Para_13=X")
    assert resolve_axis("Para_13", "ADI/CD_MONITOR_001") == "X"
    # No rule and no built-in pattern reaches this one: unknown, not "X".
    assert resolve_axis("Para_13", "ETC/OTHER") is None


def test_scoped_axis_rules_reach_the_payload(sources, monkeypatch):
    """End to end: the same parameter splits by recipe, not by name alone."""
    from back_dev_home.ebeam._office_msr_cd import AXIS_ENV_VAR

    monkeypatch.setenv(AXIS_ENV_VAR, "ADI/R1:Para_9=X,ADI/R2:Para_9=Y")
    sources["points"] = lambda eqp_id: _points(eqp_id, parameters=("Para_9",))
    payload = tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)

    # Both recipes measure "Para_9"; the map sends R1's rows to X and R2's to Y.
    assert {cell["axis"] for cell in payload["occupied_cells"]} == {"X", "Y"}


def test_no_aggregation_asks_for_more_inner_hits_than_opensearch_allows():
    """The 400 that took down the page: top_hits is capped at 100, not 10,000.

    `index.max_inner_result_window` (100) bounds a top_hits sub-aggregation and
    is a different, much smaller limit than the `index.max_result_window`
    (10,000) that bounds a top-level search. Exceeding it is a 400
    `search_phase_execution_exception` — the whole request fails rather than
    returning less — and nothing about writing `size: 200` looks wrong.

    So every per-tool cap in the office adapters is asserted against the real
    ceiling here, at home, where it costs a test rather than an office trip.
    """
    from back_dev_home.ebeam import _office_bm_pm, _office_msr_cd
    from back_dev_home.ebeam._office_search import MAX_INNER_RESULT_WINDOW, top_hits

    caps = {
        "runs/tool (shared)": _office_msr_cd.DEFAULT_RUNS_PER_TOOL,
        # The caps grow with the window, so the WIDEST choice is what must fit.
        "runs/tool (tttm)": tttm_office.runs_per_tool(max(WINDOW_WEEKS_CHOICES)),
        "runs/tool (pm)": pm_office.runs_per_tool(max(WINDOW_WEEKS_CHOICES)),
        "bsm docs/tool": pm_office.BSM_DOCS_PER_TOOL,
        "maintenance/tool": _office_bm_pm._DOCS_PER_TOOL,
    }
    for label, size in caps.items():
        assert size <= MAX_INNER_RESULT_WINDOW, (
            f"{label}={size} exceeds index.max_inner_result_window "
            f"({MAX_INNER_RESULT_WINDOW}) — OpenSearch answers 400, not a "
            "truncated list"
        )

    # And the builder refuses, so a future adapter cannot reintroduce it.
    with pytest.raises(ValueError, match="max_inner_result_window"):
        top_hits(MAX_INNER_RESULT_WINDOW + 1, sort=[{"timestamp": "desc"}])


class TestTttmUnavailableKeepsTheRoster:
    """`available: false` must not also mean "this fab has no tools".

    The client draws its tool picker from `tools`, and that picker shares a rail
    with the recipe picker — the control the user needs to LEAVE an empty answer.
    Blanking the roster removes both at exactly the moment they are needed.

    The rule used to live in two ~40-line copies of the payload constructor, one
    per provider, and on 2026-08-18 they diverged: the office template accepted a
    `tools` argument and returned a hardcoded `[]`, so home stayed green while
    the office served a blank rail. The constructor now lives once in
    `contracts.unavailable_payload`, which is what these tests exercise.
    """

    @staticmethod
    def _roster() -> list[dict[str, str]]:
        return [
            {"eqp_id": "ECDX172", "label": "ECDX172", "eqp_model_cd": "CG6300"},
            {"eqp_id": "ECDX261", "label": "ECDX261", "eqp_model_cd": "CG6300"},
        ]

    def test_the_roster_it_is_given_is_the_roster_it_returns(self):
        payload = tttm_contracts.unavailable_payload(
            "cdsem", "R3", "CD_MONITOR/NEVER_RUN", None, "측정 이력이 없습니다.",
            self._roster(),  # type: ignore[arg-type]
            window_weeks=WEEKS,
        )
        assert_matches(payload, TttmCheckPayload)
        assert payload["available"] is False
        assert [tool["eqp_id"] for tool in payload["tools"]] == ["ECDX172", "ECDX261"]

    def test_the_comparison_stays_empty_even_though_the_roster_does_not(self):
        # The distinction the branch exists to hold: a roster is not a
        # comparison. Carrying tools must not smuggle in a matrix the client
        # would render as a real pairwise result.
        payload = tttm_contracts.unavailable_payload(
            "cdsem", "R3", None, None, "장비가 1대뿐입니다.",
            self._roster(),  # type: ignore[arg-type]
            window_weeks=WEEKS,
        )
        assert payload["occupied_cells"] == []
        assert payload["fleet_today"]["matrix"]["tools"] == []
        assert payload["fleet_today"]["consensus_deviation"] == []
        assert payload["trend"] == []

    def test_an_empty_roster_is_passed_not_omitted(self):
        # A fab with no tool of this family answers `[]` — but by handing over an
        # empty fleet, not by leaving the argument out. `tools` is required
        # precisely so a branch cannot quietly decline to state a roster.
        payload = tttm_contracts.unavailable_payload(
            "cdsem", "ZZZ", None, None, "이 계열의 장비가 없습니다.", [], window_weeks=WEEKS
        )
        assert_matches(payload, TttmCheckPayload)
        assert payload["tools"] == []

        with pytest.raises(TypeError):
            tttm_contracts.unavailable_payload(  # type: ignore[call-arg]
                "cdsem", "ZZZ", None, None, "…", window_weeks=WEEKS
            )

    def test_the_window_is_required_and_echoed(self):
        # Same rule as the roster, for the same reason: an empty answer still
        # says which window it was empty over, and a branch cannot quietly
        # decline to state one.
        payload = tttm_contracts.unavailable_payload(
            "cdsem", "ZZZ", None, None, "…", [], window_weeks=1
        )
        assert payload["window_weeks"] == 1
        with pytest.raises(TypeError):
            tttm_contracts.unavailable_payload(  # type: ignore[call-arg]
                "cdsem", "ZZZ", None, None, "…", []
            )

    def test_neither_provider_keeps_a_private_copy_of_the_constructor(self):
        """The drift guard, stated as the thing that actually went wrong.

        Comparing the two providers' output would now be a tautology — they call
        one function. What is still possible, and is exactly what happened
        before, is a provider growing its OWN `_unavailable` again and drifting
        from the shared one. `office.py` is a gitignored copy, so this is a live
        risk every time someone edits a template in isolation.
        """
        from back_dev_home.ebeam.tttm.providers import mock as tttm_mock

        for adapter in (tttm_office, tttm_mock):
            assert not hasattr(adapter, "_unavailable"), (
                f"{adapter.__name__} re-declared a local _unavailable; the "
                "unavailable payload has ONE definition, in contracts.py"
            )
            assert adapter.unavailable_payload is tttm_contracts.unavailable_payload


def test_a_recipe_payload_lists_the_parameters_its_runs_measured(sources):
    """The picker's catalogue comes from the pickles, not from the .idp.

    Same rows the skew is computed from, so every name offered is one the
    parameter filter can match — and the list is the UNFILTERED set even when
    a filter is applied, or the picker would collapse to its own pick.
    """
    sources["points"] = lambda eqp_id: _points(eqp_id, parameters=("CD_Y", "CD_X", "WIDE_X"))
    payload = tttm_office.get_tttm_check("cdsem", "R3", "ADI/R1", None, WEEKS)
    assert payload["parameters"] == ["CD_X", "CD_Y", "WIDE_X"]
    narrowed = tttm_office.get_tttm_check("cdsem", "R3", "ADI/R1", "CD_X", WEEKS)
    assert narrowed["parameters"] == ["CD_X", "CD_Y", "WIDE_X"]


def test_without_a_recipe_the_office_offers_no_parameter_list(sources):
    # Recipe-local names must not be pooled across recipes.
    assert tttm_office.get_tttm_check("cdsem", "R3", None, None, WEEKS)["parameters"] == []


def test_unnamed_points_do_not_reach_the_parameter_list(sources):
    # A recipe's stabilisation shots carry CDs but no feature name; they are
    # kept by load_points and must not surface as an empty picker entry.
    sources["points"] = lambda eqp_id: _points(eqp_id, parameters=("", "CD_X"))
    payload = tttm_office.get_tttm_check("cdsem", "R3", "ADI/R1", None, WEEKS)
    assert payload["parameters"] == ["CD_X"]
