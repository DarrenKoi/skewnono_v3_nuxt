"""Program / tool / run seed identities in the msr_file mock.

The mock generates from three identities, not one (see providers/mock.py's
module docstring): what a RECIPE measures, how a TOOL reads it, and what varies
per RUN. This file pins that split, because collapsing it back onto md5(msr) is
a silent regression — the payload stays contract-valid and every existing test
still passes, while 스큐보아's multi-MSR Time-Series quietly goes back to
excluding most of a selected set.

What each test guards:

* PROGRAM  Runs of one recipe must agree on WHAT was measured. The frontend
           drops a candidate whose unit is unknown for the focus parameter
           (app/utils/skewvoirAnalysis/compatibility.ts::compareToReference),
           so a per-run parameter draw does not merely look untidy — it removes
           MSRs from the analysis the user explicitly selected.
* TOOL     A tool's measurement bias must be the same across every recipe it
           runs, or a skew finding is an artifact of one program rather than a
           property of the tool.
* RUN      Parentless MSRs must still vary. With no parent there is no recipe,
           so each is its own program; if that fallback were dropped they would
           all collapse onto one shared draw.

Run from repo root:  .venv/bin/python -m pytest back_dev_home/msr_file
"""

import statistics
from collections import defaultdict

import pytest

from back_dev_home.meas_hist.providers.mock import _all_rows
from back_dev_home.msr_file.providers import mock


def _runs_by_recipe(min_runs: int = 5) -> dict[str, list[dict]]:
    """meas_hist rows grouped by recipe, keeping recipes with enough runs to
    say anything about a set. These are real parented rows, so they exercise
    the same path the skewvoir search feeds."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in _all_rows():
        grouped[row["recipe_name"]].append(row)
    return {name: rows for name, rows in grouped.items() if len(rows) >= min_runs}


def _named_params(msr: str) -> tuple[str, ...]:
    payload = mock.get_msr_file(msr)
    assert payload is not None, f"{msr} has no detail payload"
    return tuple(p["parameter"] for p in payload["parameters"] if p["parameter"])


# ── PROGRAM: what a recipe measures ──────────────────────────────────────────


def test_every_run_of_a_recipe_measures_the_same_parameters():
    recipes = _runs_by_recipe()
    assert recipes, "no recipe had enough runs — the meas_hist universe changed"

    for recipe_name, rows in recipes.items():
        sets = {_named_params(row["msr"]) for row in rows}
        assert len(sets) == 1, (
            f"{recipe_name} measured {len(sets)} different parameter sets across "
            f"{len(rows)} runs: {sorted(sets)}. A recipe is a fixed measurement "
            "program — this is the per-run draw that excludes a selected set "
            "from Time-Series."
        )


def test_recipe_parameter_set_is_never_empty():
    """An analysis needs something to plot. `parameters` may additionally carry
    the unnamed settling-shot summary, which is why this checks NAMED ones."""
    for recipe_name, rows in _runs_by_recipe().items():
        assert _named_params(rows[0]["msr"]), f"{recipe_name} measures nothing"


def test_settling_shot_count_is_a_recipe_property():
    """A program either opens with settling shots or it does not."""
    for recipe_name, rows in _runs_by_recipe().items():
        counts = set()
        for row in rows:
            payload = mock.get_msr_file(row["msr"])
            assert payload is not None
            counts.add(sum(1 for r in payload["rows"] if r["parameter"] == ""))
        assert len(counts) == 1, (
            f"{recipe_name} opened with {sorted(counts)} settling shots across runs"
        )


def test_runs_of_a_recipe_cluster_around_one_target():
    """The trend needs a centre line.

    A per-run uniform draw spread means across the parameter's whole physical
    range (a ~30 nm span for CD), so a Time-Series across a set was scatter with
    no centre. Layered generation must keep healthy runs inside a small fraction
    of that span. Unhealthy runs are excluded on purpose: health drift is the
    excursion the chart exists to show, not noise to be averaged away.
    """
    checked = 0
    for recipe_name, rows in _runs_by_recipe().items():
        by_param: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            payload = mock.get_msr_file(row["msr"])
            assert payload is not None
            if payload["health"] >= 0.15:
                continue
            for summary in payload["parameters"]:
                if summary["parameter"]:
                    by_param[summary["parameter"]].append(summary["mean"])

        for parameter, means in by_param.items():
            if len(means) < 5:
                continue
            lo, hi, _ = mock._param_spec(parameter)
            span = hi - lo
            spread = statistics.pstdev(means)
            assert spread < span * 0.08, (
                f"{recipe_name}/{parameter}: healthy-run means scatter by "
                f"{spread:.2f} over a {span:.0f} span — no shared target"
            )
            checked += 1

    assert checked, "no (recipe, parameter) pair had enough healthy runs to judge"


# ── TOOL: how a tool reads a feature ─────────────────────────────────────────


@pytest.mark.parametrize("parameter", ["CD_TOP", "GATE_CD", "CONTACT_DEPTH"])
def test_tool_bias_is_identical_across_recipes(parameter):
    """Tool skew is keyed on (eqp, parameter) and NOT the recipe.

    Averaging over many run keys cancels the per-run wobble, leaving the tool
    layer alone. Comparing that against the no-tool baseline isolates the bias,
    which must not move when the program changes.
    """
    programs = ("RECIPE_ALPHA", "RECIPE_BETA", "RECIPE_GAMMA")
    runs = [f"MSR-TOOL-BIAS-{i:04d}" for i in range(300)]

    for tool in ("ECDX285", "HCDX268", "VCD690"):
        offsets = []
        for program in programs:
            base = statistics.fmean(
                mock._cd_field(msr, program, "", parameter, 0.0).mean for msr in runs
            )
            biased = statistics.fmean(
                mock._cd_field(msr, program, tool, parameter, 0.0).mean for msr in runs
            )
            offsets.append(biased - base)

        assert max(offsets) - min(offsets) < 1e-9, (
            f"{tool}/{parameter} biased differently per recipe ({offsets}) — a "
            "skew finding would then be an artifact of the program, not the tool"
        )


def test_tool_bias_outweighs_within_wafer_noise():
    """The tool-skew panel can only separate tools if a tool's bias is larger
    than the site noise it has to be read through. This pins the ORDER of the
    layer magnitudes, which is the load-bearing part — not the exact values."""
    assert mock._TOOL_SKEW_FRAC > mock._SITE_SIGMA_FRAC > mock._RUN_OFFSET_FRAC


def test_a_run_without_a_parent_carries_no_tool_skew():
    """No parent row means no tool. Borrowing one would attribute a bias to
    equipment the measurement was never linked to."""
    for parameter in ("CD_TOP", "GATE_CD"):
        assert (
            mock._cd_field("MSR-ORPHAN-0001", "PROGRAM_X", "", parameter, 0.0).mean
            == mock._cd_field("MSR-ORPHAN-0001", "PROGRAM_X", "", parameter, 0.0).mean
        )
        with_tool = mock._cd_field("MSR-ORPHAN-0001", "PROGRAM_X", "ECDX285", parameter, 0.0)
        without = mock._cd_field("MSR-ORPHAN-0001", "PROGRAM_X", "", parameter, 0.0)
        assert with_tool.mean != without.mean, "the tool layer did nothing at all"


# ── RUN: the parentless fallback ─────────────────────────────────────────────


def test_parentless_msrs_are_each_their_own_program():
    """With no parent there is no recipe to belong to, so these must keep
    varying. Seeding them off a shared fallback display name (`ADI_UNKNOWN`)
    would collapse all of them onto one identical draw — and silently disarm
    the contract tests that rely on this variety to exercise both the
    with-settling-shots and without-settling-shots paths."""
    sets = set()
    dummy_counts = set()
    for i in range(40):
        payload = mock.get_msr_file(f"MSR-ORPHAN-VARY-{i:04d}", "ADI", 40)
        assert payload is not None
        sets.add(tuple(p["parameter"] for p in payload["parameters"] if p["parameter"]))
        dummy_counts.add(sum(1 for r in payload["rows"] if r["parameter"] == ""))

    assert len(sets) > 1, "parentless MSRs collapsed onto one parameter set"
    assert len(dummy_counts) > 1, "parentless MSRs collapsed onto one settling-shot count"
