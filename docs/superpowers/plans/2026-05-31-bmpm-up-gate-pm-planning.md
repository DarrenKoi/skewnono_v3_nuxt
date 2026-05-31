# BM/PM Up Gate & PM-Planning Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/ebeam/cd-sem/[fab]/pm-planning` dashboard — a per-tool BM/PM **Up gate** and a fleet **focus-target ranking** for the next PM — backed by a new Flask mock feature, following the spec at `docs/superpowers/specs/2026-05-31-bmpm-up-gate-pm-planning-design.md`.

**Architecture:** One Flask feature folder (`back_dev_home/ebeam/hitachi/pm_planning/`) returns a fab-scoped **fleet snapshot** — per-tool gate inputs (CD_MONITORING value + spec range, BSM in-spec, epoch context) and per-cell (beam×axis) signed skew + consensus + median. The spec range is sourced from a new hardware-feature module (reuse seam), and BSM/BM-PM context reuses the existing hardware mock generators. The Nuxt page fetches that one snapshot and computes everything else **client-side**: the gate verdict for a selected tool, and the focus ranking via `max-axis skew → advisory-threshold gate → bottom-N`, with N and per-beam thresholds as engineer knobs.

**Tech Stack:** Flask blueprint (auto-registered under `/api` by `back_dev_home/__init__.py`), deterministic mock generators (`random.Random(seed_from_id)` + `pandas`), Nuxt 4 + NuxtUI page/View/components, `useAsyncData` + `$fetch`, pure TypeScript ranking logic tested with Node's built-in test runner.

---

## Testing Philosophy (read first — this project has no pytest/vitest)

This repo does **not** use pytest or a component test framework. Match the existing conventions:

- **Backend (Python):** there is no test runner. Correctness is verified two ways: (1) a `if __name__ == "__main__":` **preview block** at the bottom of each `data.py` that prints samples and runs `assert` statements (mirrors `recipe_tat/data.py`), run with `python -m <module>`; (2) a live **curl** against the Flask dev server on port **5050**. Determinism (same input → byte-identical output) is the contract.
- **Frontend pure logic (TypeScript):** extract the ranking/gate math into `app/utils/pmPlanning.ts` and test it with **Node's built-in runner** — `node --test app/utils/pmPlanning.test.ts` — exactly like the existing `app/utils/ruleEngine.test.ts`. Node 24+ strips types, so `.test.ts` imports `.ts` directly. This is where real red-green-refactor TDD applies.
- **Vue components:** no unit tests. Verify by running the app (user runs Flask :5050 + Nuxt :3000 in PyCharm) and, where useful, a Playwright MCP screenshot saved under `.playwright-mcp/screenshots/`.

So: TDD the TypeScript utils; preview-block + curl the Python; run-the-app the Vue. Do not add pytest or vitest.

---

## File Structure

**Backend (create):**
- `back_dev_home/ebeam/hitachi/hardware/providers/spec_range_mock.py` — **reuse seam.** Per-tool CD_MONITORING spec range + the BSM in-spec band. Hardware owns the spec; pm_planning imports it.
- `back_dev_home/ebeam/hitachi/pm_planning/__init__.py` — re-exports `bp`.
- `back_dev_home/ebeam/hitachi/pm_planning/contracts.py` — `FleetPayload` TypedDicts (the stable API shape).
- `back_dev_home/ebeam/hitachi/pm_planning/data.py` — SWAP SURFACE. Synthesizes the fleet snapshot; reuses hardware `build_bsm_data` / `build_bm_pm_data` / `spec_range_mock`.
- `back_dev_home/ebeam/hitachi/pm_planning/routes.py` — blueprint `bp` + the `/<tool_slug>/pm-planning/fleet` endpoint.
- `back_dev_home/ebeam/hitachi/pm_planning/__fixtures__/fleet-cdsem-m14.json` — sample response for reference.

**Frontend (create):**
- `front-dev-home/app/composables/usePmPlanningApi.ts` — types mirroring the contract + `fetchPmPlanningFleet`.
- `front-dev-home/app/utils/pmPlanning.ts` — pure logic: `maxAxisSkew`, `rankFocusTargets`, `gateVerdict`.
- `front-dev-home/app/utils/pmPlanning.test.ts` — Node `--test` coverage for the pure logic.
- `front-dev-home/app/pages/ebeam/cd-sem/[fab]/pm-planning.vue` — route page (mirrors `hardware.vue`).
- `front-dev-home/app/components/ebeam/PmPlanningView.vue` — top-level View: MetaBar + gate strip + focus body, owns fetch + knob state.
- `front-dev-home/app/components/ebeam/pmPlanning/GateStrip.vue` — per-tool Up-gate strip (auto-import name `EbeamPmPlanningGateStrip`).
- `front-dev-home/app/components/ebeam/pmPlanning/FocusRanking.vue` — per-beam ranked list + N/threshold knobs (`EbeamPmPlanningFocusRanking`).
- `front-dev-home/app/components/ebeam/pmPlanning/ConvergencePanel.vue` — selected-tool cell detail + epoch history (`EbeamPmPlanningConvergencePanel`).

**Note on component naming:** Nuxt prefixes the folder into the auto-import name. A file at `components/ebeam/pmPlanning/GateStrip.vue` is referenced as `<EbeamPmPlanningGateStrip>`. Do **not** repeat the prefix in the filename.

---

# PART A — Backend mock + contract

Produces a working, curl-able `/api/cdsem/pm-planning/fleet?fab_id=M14` endpoint. No frontend needed to verify.

### Task A1: Hardware spec-range source (the reuse seam)

**Files:**
- Create: `back_dev_home/ebeam/hitachi/hardware/providers/spec_range_mock.py`

- [ ] **Step 1: Write the module**

CD_MONITORING is measured at ~16 nm. Each tool carries its own self-referential spec window (that self-reference is what lets the gate pass without the App engineer). BSM in-spec uses a fixed band matching `bsm_mock.py`'s generated ranges (sharpness 7.80–8.10, noise 6.60–7.00).

```python
"""Per-tool measurement spec ranges — the hardware feature owns these.

The BM/PM Up gate compares a tool's post-PM CD_MONITORING value and its BSM
profile against *that tool's own* spec window. Keeping the spec here (next to
the BM/PM and BSM mock sources) means pm_planning imports one seam instead of
duplicating spec numbers. Office swaps this module for the real spec system.
"""

import hashlib


__all__ = [
    "CD_MON_NOMINAL_NM",
    "get_cd_monitoring_spec",
    "get_bsm_spec",
    "bsm_in_spec",
]


CD_MON_NOMINAL_NM = 16.0
# Half-width of each tool's CD_MONITORING spec window (nm). 16.0 ± 0.5.
_CD_SPEC_HALF_WIDTH = 0.5

# BSM in-spec band. Matches the physically-plausible ranges bsm_mock.py
# generates so a healthy tool reads in-spec.
_BSM_SHARPNESS_LOWER = 7.85
_BSM_SHARPNESS_UPPER = 8.05
_BSM_NOISE_LOWER = 6.65
_BSM_NOISE_UPPER = 6.95


def _seed_for(eqp_id: str) -> int:
    digest = hashlib.md5(eqp_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def get_cd_monitoring_spec(eqp_id: str) -> dict[str, float]:
    """That tool's CD_MONITORING spec window (target/lower/upper, nm).

    Target drifts a few hundredths of a nm per tool so the fleet isn't a
    single shared number, but every window is centered near 16.0 nm.
    """
    offset = ((_seed_for(eqp_id) % 21) - 10) / 100.0  # -0.10 .. +0.10 nm
    target = round(CD_MON_NOMINAL_NM + offset, 3)
    return {
        "target": target,
        "lower": round(target - _CD_SPEC_HALF_WIDTH, 3),
        "upper": round(target + _CD_SPEC_HALF_WIDTH, 3),
    }


def get_bsm_spec() -> dict[str, float]:
    """Fleet-wide BSM acceptance band (sharpness + noise)."""
    return {
        "sharpness_lower": _BSM_SHARPNESS_LOWER,
        "sharpness_upper": _BSM_SHARPNESS_UPPER,
        "noise_lower": _BSM_NOISE_LOWER,
        "noise_upper": _BSM_NOISE_UPPER,
    }


def bsm_in_spec(sharpness_avg: float, noise_avg: float) -> bool:
    spec = get_bsm_spec()
    return (
        spec["sharpness_lower"] <= sharpness_avg <= spec["sharpness_upper"]
        and spec["noise_lower"] <= noise_avg <= spec["noise_upper"]
    )
```

- [ ] **Step 2: Verify in a REPL**

Run: `python -c "from back_dev_home.ebeam.hitachi.hardware.providers.spec_range_mock import get_cd_monitoring_spec, bsm_in_spec; print(get_cd_monitoring_spec('ECXDX-01')); print(get_cd_monitoring_spec('ECXDX-01')); print(bsm_in_spec(7.95, 6.80), bsm_in_spec(8.20, 6.80))"`

Expected: the two `get_cd_monitoring_spec('ECXDX-01')` lines are **identical** (determinism), each a dict with `target` near 16.0 and `lower`/`upper` ±0.5; then `True False`.

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/hitachi/hardware/providers/spec_range_mock.py
git commit -m "feat(hardware): add per-tool CD_MONITORING + BSM spec-range source"
```

---

### Task A2: pm_planning contract (TypedDicts)

**Files:**
- Create: `back_dev_home/ebeam/hitachi/pm_planning/contracts.py`

- [ ] **Step 1: Write the contract**

This is the stable API shape. The engine ships **raw signed skew** + per-beam defaults; the client computes ranking/gate. `verdict` is a server convenience (`cd_in_spec and bsm_in_spec`); the client still recomputes it for display.

```python
"""Canonical pm-planning API contract — the stable shape the route returns.

The fab-scoped fleet snapshot carries (a) per-tool Up-gate inputs and (b)
per-cell (beam x axis) signed skew + consensus/median. Ranking, the advisory
threshold gate, and bottom-N selection are computed CLIENT-SIDE from this raw
data (see front-dev-home/app/utils/pmPlanning.ts), so the contract never bakes
in N or the threshold beyond shipping their defaults.
"""

from typing import Literal, TypedDict


BeamCondition = Literal["500V", "800V"]
ScanAxis = Literal["X", "Y"]
GateVerdict = Literal["up", "hold"]


class GateBlock(TypedDict):
    cd_monitoring_value: float   # post-PM CD_MONITORING reading (nm)
    cd_spec_lower: float
    cd_spec_upper: float
    cd_in_spec: bool
    bsm_in_spec: bool
    bsm_sharpness_avg: float
    bsm_noise_avg: float
    post_pm_at: str | None       # ISO; null if no PM on record
    prev_post_delta: float | None  # signed before->after delta (nm), CONTEXT only
    mdc_changed: bool            # epoch marker, CONTEXT only — never gates
    verdict: GateVerdict         # = cd_in_spec and bsm_in_spec


class CellSkew(TypedDict):
    beam: BeamCondition
    axis: ScanAxis
    skew: float           # signed residual from consensus (nm)
    current_value: float  # this tool's value in the cell (nm)
    median: float         # fleet median for the cell = convergence target (nm)
    gap: float            # signed current_value - median (nm)


class EpochPoint(TypedDict):
    epoch_start: str           # ISO date the epoch began
    mdc: float                 # MDC value in that epoch (this tool's own history)
    bsm_sharpness_avg: float


class ToolBlock(TypedDict):
    eqp_id: str
    gate: GateBlock
    cells: list[CellSkew]
    epoch_history: list[EpochPoint]


class ConsensusCell(TypedDict):
    beam: BeamCondition
    axis: ScanAxis
    consensus: float


class FleetDefaults(TypedDict):
    focus_n: int                          # default bottom-N per beam
    advisory_threshold: dict[str, float]  # per-beam nm, keyed by beam condition


class FleetPayload(TypedDict):
    tool_type: str          # "cd-sem"
    fab_id: str
    fetched_at: str
    anchor_date: str
    beam_conditions: list[BeamCondition]
    axes: list[ScanAxis]
    defaults: FleetDefaults
    consensus: list[ConsensusCell]
    tools: list[ToolBlock]
```

- [ ] **Step 2: Verify it imports**

Run: `python -c "from back_dev_home.ebeam.hitachi.pm_planning.contracts import FleetPayload; print('ok')"`
Expected: `ok` (no `ModuleNotFoundError` — note an empty `__init__.py` is added in Task A4; for this step the import of `contracts` alone works because Python treats the folder as a namespace once it exists).

If the import fails because the package has no `__init__.py` yet, create an empty `back_dev_home/ebeam/hitachi/pm_planning/__init__.py` now — Task A4 fills it in.

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/hitachi/pm_planning/contracts.py back_dev_home/ebeam/hitachi/pm_planning/__init__.py
git commit -m "feat(pm-planning): define fleet snapshot contract"
```

---

### Task A3: pm_planning data layer (fleet synthesizer)

**Files:**
- Create: `back_dev_home/ebeam/hitachi/pm_planning/data.py`

The skew core is docs-only, so this mock **synthesizes** consensus/skew itself (consistent with "Phase-1 proves contract + UX"). It reuses the hardware mock for BSM, BM/PM timing, and spec range.

- [ ] **Step 1: Write the data layer with a preview block**

```python
"""SWAP SURFACE — office reimplements with the same signature/TypedDicts.

Synthesizes a fab-scoped CD-SEM fleet snapshot for the pm-planning dashboard:
per-tool Up-gate inputs and per-cell (beam x axis) signed skew. The skew core
(consensus/residual/epoch) is not yet built, so this module fabricates that
data deterministically from each eqp_id — the same seed-from-id trick the
hardware mocks use. Gate inputs REUSE the hardware feature:
  * BSM avg/3sigma -> hardware.providers.bsm_mock.build_bsm_data
  * post-PM timing -> hardware.providers.bm_pm_mock.build_bm_pm_data
  * CD/BSM spec    -> hardware.providers.spec_range_mock

Determinism is the contract: same fab -> byte-identical payload.
"""

import hashlib
import random
import statistics
from datetime import datetime, timezone

from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm_mock import build_bm_pm_data
from back_dev_home.ebeam.hitachi.hardware.providers.bsm_mock import build_bsm_data
from back_dev_home.ebeam.hitachi.hardware.providers.spec_range_mock import (
    bsm_in_spec,
    get_cd_monitoring_spec,
)
from back_dev_home.ebeam.hitachi.pm_planning.contracts import (
    BeamCondition,
    CellSkew,
    ConsensusCell,
    EpochPoint,
    FleetPayload,
    GateBlock,
    ScanAxis,
    ToolBlock,
)


__all__ = ["BEAM_CONDITIONS", "AXES", "DEFAULTS", "get_pm_planning_fleet"]


BEAM_CONDITIONS: list[BeamCondition] = ["500V", "800V"]
AXES: list[ScanAxis] = ["X", "Y"]

# Implementation-time defaults (spec §7.3: placeholder now, office-calibrated
# later). N=3 per beam; per-beam advisory thresholds in nm (500V tighter scale).
DEFAULTS = {
    "focus_n": 3,
    "advisory_threshold": {"500V": 0.30, "800V": 0.40},
}

# Per-cell consensus base values (nm). Skew is residual around these; the exact
# base is cosmetic since the dashboard works in skew/gap space.
_CONSENSUS_BASE = {"500V": 16.0, "800V": 16.0}

# Fleet size per fab and the CD-SEM eqp_id prefixes (mirrors _tool_specs.py).
_FLEET_SIZE = 8
_CD_PREFIXES = ("ECXDX", "ECDX", "HCDX")

# Anchor "today" so generated dates are stable regardless of wall clock,
# matching the hardware mocks' NOW.
NOW = datetime(2026, 5, 24, 9, 0)


def _seed_for(text: str) -> int:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _fleet_eqp_ids(fab_id: str) -> list[str]:
    """Deterministic CD-SEM tool pool for a fab — e.g. ECXDX-M14-01."""
    rng = random.Random(_seed_for(f"fleet::{fab_id.upper()}"))
    fab = fab_id.upper()
    ids: list[str] = []
    for i in range(_FLEET_SIZE):
        prefix = _CD_PREFIXES[i % len(_CD_PREFIXES)]
        ids.append(f"{prefix}-{fab}-{i + 1:02d}")
    rng.shuffle(ids)  # so position != prefix order
    return ids


def _tool_cells(eqp_id: str) -> list[CellSkew]:
    """Per (beam x axis) signed skew + consensus/median/gap for one tool.

    Most tools sit near consensus (~N(0, 0.12)); a deterministic subset get an
    inflated skew on one beam/axis so the focus ranking has real outliers.
    """
    rng = random.Random(_seed_for(f"cells::{eqp_id}"))
    # 1-in-3 tools is an outlier on a specific (beam, axis) cell.
    outlier = rng.random() < 0.34
    outlier_beam = rng.choice(BEAM_CONDITIONS)
    outlier_axis = rng.choice(AXES)

    cells: list[CellSkew] = []
    for beam in BEAM_CONDITIONS:
        base = _CONSENSUS_BASE[beam]
        for axis in AXES:
            skew = round(rng.gauss(0.0, 0.12), 3)
            if outlier and beam == outlier_beam and axis == outlier_axis:
                # Push 0.45-0.75 nm off consensus, signed.
                skew = round(rng.choice([-1, 1]) * rng.uniform(0.45, 0.75), 3)
            current = round(base + skew, 3)
            cells.append({
                "beam": beam,
                "axis": axis,
                "skew": skew,
                "current_value": current,
                "median": base,   # provisional; replaced with true fleet median below
                "gap": skew,      # provisional; recomputed below
            })
    return cells


def _epoch_history(eqp_id: str) -> list[EpochPoint]:
    """A few past MDC epochs for this tool (its own history, not a target)."""
    rng = random.Random(_seed_for(f"epoch::{eqp_id}"))
    points: list[EpochPoint] = []
    mdc = round(rng.uniform(0.990, 1.010), 4)
    for k in range(3):
        days_ago = 60 * (3 - k) + rng.randint(0, 20)
        start = NOW.fromordinal(NOW.toordinal() - days_ago)
        mdc = round(mdc + rng.uniform(-0.004, 0.004), 4)
        points.append({
            "epoch_start": start.date().isoformat(),
            "mdc": mdc,
            "bsm_sharpness_avg": round(rng.uniform(7.90, 8.00), 3),
        })
    return points


def _latest_daily_bsm(eqp_id: str) -> tuple[float, float]:
    """Most-recent daily BSM (sharpness_avg, noise_avg) from the hardware mock."""
    bsm = build_bsm_data(eqp_id)
    daily = next(c for c in bsm["categories"] if c["key"] == "daily")
    summary = daily["summary"]
    if not summary:
        return (7.95, 6.80)
    latest = summary[0]  # bsm_mock sorts timestamp desc
    return (float(latest["sharpness_avg"]), float(latest["noise_avg"]))


def _latest_pm_at(eqp_id: str) -> str | None:
    """Most-recent completed PM job_end from the hardware BM/PM mock (ISO)."""
    data = build_bm_pm_data(eqp_id)
    past = data["past"]  # already timestamp desc
    for row in past:
        if row.get("category") == "PM":
            # bm_pm_mock formats "%Y-%m-%d %H:%M"; normalize to ISO-ish.
            return str(row["job_end"]).replace(" ", "T")
    return None


def _build_gate(eqp_id: str) -> GateBlock:
    rng = random.Random(_seed_for(f"gate::{eqp_id}"))
    spec = get_cd_monitoring_spec(eqp_id)
    # Post-PM CD_MONITORING value: usually inside spec, occasionally just out.
    value = round(spec["target"] + rng.gauss(0.0, 0.18), 3)
    cd_ok = spec["lower"] <= value <= spec["upper"]

    sharp, noise = _latest_daily_bsm(eqp_id)
    bsm_ok = bsm_in_spec(sharp, noise)

    verdict = "up" if (cd_ok and bsm_ok) else "hold"
    return {
        "cd_monitoring_value": value,
        "cd_spec_lower": spec["lower"],
        "cd_spec_upper": spec["upper"],
        "cd_in_spec": cd_ok,
        "bsm_in_spec": bsm_ok,
        "bsm_sharpness_avg": sharp,
        "bsm_noise_avg": noise,
        "post_pm_at": _latest_pm_at(eqp_id),
        "prev_post_delta": round(rng.gauss(0.0, 0.08), 3),
        "mdc_changed": rng.random() < 0.4,
        "verdict": verdict,
    }


def _apply_fleet_median(tools: list[ToolBlock]) -> list[ConsensusCell]:
    """Replace each cell's median/gap with the true fleet median per cell.

    consensus == fleet median here (robust center). skew was generated around
    the consensus base, so after this pass gap == current_value - median.
    """
    consensus: list[ConsensusCell] = []
    for beam in BEAM_CONDITIONS:
        for axis in AXES:
            values = [
                cell["current_value"]
                for tool in tools
                for cell in tool["cells"]
                if cell["beam"] == beam and cell["axis"] == axis
            ]
            median = round(statistics.median(values), 3) if values else _CONSENSUS_BASE[beam]
            consensus.append({"beam": beam, "axis": axis, "consensus": median})
            for tool in tools:
                for cell in tool["cells"]:
                    if cell["beam"] == beam and cell["axis"] == axis:
                        cell["median"] = median
                        cell["gap"] = round(cell["current_value"] - median, 3)
    return consensus


def get_pm_planning_fleet(fab_id: str) -> FleetPayload:
    """Fab-scoped CD-SEM fleet snapshot — gate inputs + per-cell skew."""
    fab = fab_id.upper()
    tools: list[ToolBlock] = []
    for eqp_id in _fleet_eqp_ids(fab):
        tools.append({
            "eqp_id": eqp_id,
            "gate": _build_gate(eqp_id),
            "cells": _tool_cells(eqp_id),
            "epoch_history": _epoch_history(eqp_id),
        })

    consensus = _apply_fleet_median(tools)

    return {
        "tool_type": "cd-sem",
        "fab_id": fab,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "anchor_date": NOW.date().isoformat(),
        "beam_conditions": BEAM_CONDITIONS,
        "axes": AXES,
        "defaults": DEFAULTS,
        "consensus": consensus,
        "tools": tools,
    }


if __name__ == "__main__":
    # Preview + determinism check:
    #   python -m back_dev_home.ebeam.hitachi.pm_planning.data
    import json

    a = get_pm_planning_fleet("M14")
    b = get_pm_planning_fleet("M14")
    # `fetched_at` is wall-clock; compare everything else for determinism.
    a_cmp = {k: v for k, v in a.items() if k != "fetched_at"}
    b_cmp = {k: v for k, v in b.items() if k != "fetched_at"}
    assert json.dumps(a_cmp, sort_keys=True) == json.dumps(b_cmp, sort_keys=True), \
        "fleet snapshot is not deterministic"
    assert len(a["tools"]) == _FLEET_SIZE
    for tool in a["tools"]:
        assert len(tool["cells"]) == len(BEAM_CONDITIONS) * len(AXES)
        assert tool["gate"]["verdict"] in ("up", "hold")

    print(f"fab={a['fab_id']}  tools={len(a['tools'])}  "
          f"beams={a['beam_conditions']}  defaults={a['defaults']}")
    t0 = a["tools"][0]
    print(f"\nsample tool: {t0['eqp_id']}")
    print(f"  gate: verdict={t0['gate']['verdict']} "
          f"cd={t0['gate']['cd_monitoring_value']} "
          f"in[{t0['gate']['cd_spec_lower']},{t0['gate']['cd_spec_upper']}] "
          f"bsm_in_spec={t0['gate']['bsm_in_spec']}")
    for cell in t0["cells"]:
        print(f"  {cell['beam']:>5} {cell['axis']}  skew={cell['skew']:+.3f}  "
              f"gap={cell['gap']:+.3f}")
    print("\nconsensus:", a["consensus"])
```

- [ ] **Step 2: Run the preview + determinism assertions**

Run: `python -m back_dev_home.ebeam.hitachi.pm_planning.data`
Expected: no `AssertionError`; prints `fab=M14 tools=8 …`, a sample tool's gate line, four `500V/800V × X/Y` skew lines, and the consensus list. Running it twice prints identical fleet content (only the live `fetched_at` differs, which the assertion excludes).

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/hitachi/pm_planning/data.py
git commit -m "feat(pm-planning): synthesize fab fleet snapshot (gate + per-cell skew)"
```

---

### Task A4: Route + blueprint registration

**Files:**
- Create: `back_dev_home/ebeam/hitachi/pm_planning/routes.py`
- Modify: `back_dev_home/ebeam/hitachi/pm_planning/__init__.py`

- [ ] **Step 1: Write the route**

Mirrors `hardware/routes.py`: validate `tool_slug`, resolve `fab_id`, return the payload. The app factory auto-registers any `routes.py` exporting `bp` under `/api`, so the endpoint becomes `/api/<tool_slug>/pm-planning/fleet`.

```python
from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import VALID_TOOL_SLUGS
from back_dev_home.ebeam.hitachi.pm_planning.data import get_pm_planning_fleet


bp = Blueprint("ebeam_pm_planning", __name__)


def _resolve_fab_id() -> str:
    return (request.args.get("fab_id") or "").strip()


@bp.get("/<tool_slug>/pm-planning/fleet")
def pm_planning_fleet(tool_slug: str):
    # pm-planning is a CD-SEM-only dashboard, but validate against the shared
    # slug set for a consistent 400 message across features.
    if tool_slug not in VALID_TOOL_SLUGS:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    if tool_slug != "cdsem":
        return jsonify({"error": "pm-planning is available for CD-SEM only"}), 400

    fab_id = _resolve_fab_id()
    if not fab_id:
        return jsonify({"error": "fab_id query parameter is required"}), 400

    return jsonify(get_pm_planning_fleet(fab_id))
```

- [ ] **Step 2: Fill in `__init__.py`**

```python
from back_dev_home.ebeam.hitachi.pm_planning.routes import bp

__all__ = ["bp"]
```

- [ ] **Step 3: Verify the blueprint registers and the endpoint responds**

Start the Flask dev server (if not already running on 5050):
Run: `python index.py` (in a separate terminal; serves on `127.0.0.1:5050`)

Then in another shell:
Run: `curl -s "http://localhost:5050/api/cdsem/pm-planning/fleet?fab_id=M14" | python -m json.tool | head -40`
Expected: a JSON object with `tool_type: "cd-sem"`, `fab_id: "M14"`, `defaults`, `consensus`, and a `tools` array of 8 entries each having `gate` and `cells`.

Validation checks:
Run: `curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5050/api/cdsem/pm-planning/fleet"` → `400` (missing fab_id)
Run: `curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5050/api/hvsem/pm-planning/fleet?fab_id=M14"` → `400` (CD-SEM only)

- [ ] **Step 4: Commit**

```bash
git add back_dev_home/ebeam/hitachi/pm_planning/routes.py back_dev_home/ebeam/hitachi/pm_planning/__init__.py
git commit -m "feat(pm-planning): expose GET /api/cdsem/pm-planning/fleet"
```

---

### Task A5: Reference fixture

**Files:**
- Create: `back_dev_home/ebeam/hitachi/pm_planning/__fixtures__/fleet-cdsem-m14.json`

- [ ] **Step 1: Capture a sample response**

Run: `curl -s "http://localhost:5050/api/cdsem/pm-planning/fleet?fab_id=M14" | python -m json.tool > back_dev_home/ebeam/hitachi/pm_planning/__fixtures__/fleet-cdsem-m14.json`

- [ ] **Step 2: Sanity-check the file**

Run: `python -c "import json; d=json.load(open('back_dev_home/ebeam/hitachi/pm_planning/__fixtures__/fleet-cdsem-m14.json')); print(len(d['tools']), 'tools', d['defaults'])"`
Expected: `8 tools {'focus_n': 3, 'advisory_threshold': {'500V': 0.3, '800V': 0.4}}`

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/hitachi/pm_planning/__fixtures__/fleet-cdsem-m14.json
git commit -m "test(pm-planning): add reference fleet fixture (cdsem/M14)"
```

---

# PART B — Frontend Up-gate (page shell + gate strip)

Produces a working page at `/ebeam/cd-sem/M14/pm-planning` showing the MetaBar and the per-tool Up-gate strip. Focus ranking lands in Part C.

### Task B1: Pure ranking/gate logic — RED

**Files:**
- Create: `front-dev-home/app/utils/pmPlanning.ts`
- Test: `front-dev-home/app/utils/pmPlanning.test.ts`

This is the real TDD task: the `max-axis → threshold-gate → bottom-N` math, isolated and tested.

- [ ] **Step 1: Write the failing test**

```typescript
// Pure-logic tests for pmPlanning. Zero deps — run with Node's built-in runner:
//   node --test app/utils/pmPlanning.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  maxAxisSkew, rankFocusTargets, gateVerdict,
  type ToolCells, type GateInputs,
} from './pmPlanning.ts'

const cells = (sx500: number, sy500: number, sx800: number, sy800: number): ToolCells['cells'] => [
  { beam: '500V', axis: 'X', skew: sx500, current_value: 16 + sx500, median: 16, gap: sx500 },
  { beam: '500V', axis: 'Y', skew: sy500, current_value: 16 + sy500, median: 16, gap: sy500 },
  { beam: '800V', axis: 'X', skew: sx800, current_value: 16 + sx800, median: 16, gap: sx800 },
  { beam: '800V', axis: 'Y', skew: sy800, current_value: 16 + sy800, median: 16, gap: sy800 },
]

test('maxAxisSkew picks the worst axis by absolute skew, keeping its axis label', () => {
  const c = cells(0.5, -0.2, 0.1, 0.1)
  assert.deepEqual(maxAxisSkew(c, '500V'), { score: 0.5, axis: 'X' })
  // Negative magnitude still wins if larger in absolute value.
  const c2 = cells(0.1, -0.6, 0.1, 0.1)
  assert.deepEqual(maxAxisSkew(c2, '500V'), { score: 0.6, axis: 'Y' })
})

test('rankFocusTargets gates by threshold then takes bottom-N, sorted desc', () => {
  const tools: ToolCells[] = [
    { eqp_id: 'T1', cells: cells(0.62, 0.1, 0.1, 0.1) },   // 500V score 0.62
    { eqp_id: 'T2', cells: cells(0.55, 0.1, 0.1, 0.1) },   // 0.55
    { eqp_id: 'T3', cells: cells(0.47, 0.1, 0.1, 0.1) },   // 0.47
    { eqp_id: 'T4', cells: cells(0.38, 0.1, 0.1, 0.1) },   // 0.38 < 0.40 threshold
    { eqp_id: 'T5', cells: cells(0.10, 0.1, 0.1, 0.1) },   // 0.10
  ]
  const ranked = rankFocusTargets(tools, '500V', 0.40, 3)
  // Only scores > 0.40 are candidates; T4/T5 excluded. Bottom-3 of candidates.
  assert.deepEqual(ranked.map(r => r.eqp_id), ['T1', 'T2', 'T3'])
  assert.deepEqual(ranked.map(r => r.nominated), [true, true, true])
  assert.equal(ranked[0].score, 0.62)
  assert.equal(ranked[0].axis, 'X')
})

test('rankFocusTargets self-limits: fewer than N candidates when fleet is tight', () => {
  const tools: ToolCells[] = [
    { eqp_id: 'T1', cells: cells(0.45, 0.1, 0.1, 0.1) },
    { eqp_id: 'T2', cells: cells(0.20, 0.1, 0.1, 0.1) },
    { eqp_id: 'T3', cells: cells(0.10, 0.1, 0.1, 0.1) },
  ]
  const ranked = rankFocusTargets(tools, '500V', 0.40, 3)
  assert.deepEqual(ranked.map(r => r.eqp_id), ['T1'])  // only one over threshold
})

test('rankFocusTargets returns empty when the whole fleet is inside the line', () => {
  const tools: ToolCells[] = [
    { eqp_id: 'T1', cells: cells(0.10, 0.1, 0.1, 0.1) },
    { eqp_id: 'T2', cells: cells(0.20, 0.1, 0.1, 0.1) },
  ]
  assert.deepEqual(rankFocusTargets(tools, '500V', 0.40, 3), [])
})

test('gateVerdict is up only when both CD and BSM are in spec', () => {
  const base: GateInputs = { cd_in_spec: true, bsm_in_spec: true }
  assert.equal(gateVerdict(base), 'up')
  assert.equal(gateVerdict({ cd_in_spec: false, bsm_in_spec: true }), 'hold')
  assert.equal(gateVerdict({ cd_in_spec: true, bsm_in_spec: false }), 'hold')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run (from `front-dev-home/`): `node --test app/utils/pmPlanning.test.ts`
Expected: FAIL — cannot find module `./pmPlanning.ts` (it doesn't exist yet).

- [ ] **Step 3: Write the minimal implementation**

```typescript
// Pure client-side logic for the pm-planning dashboard. Kept dependency-free
// and framework-free so it runs under `node --test` and is the single source
// of truth for the ranking math the UI renders.

export type BeamCondition = '500V' | '800V'
export type ScanAxis = 'X' | 'Y'

export interface CellSkew {
  beam: BeamCondition
  axis: ScanAxis
  skew: number
  current_value: number
  median: number
  gap: number
}

export interface ToolCells {
  eqp_id: string
  cells: CellSkew[]
}

export interface GateInputs {
  cd_in_spec: boolean
  bsm_in_spec: boolean
}

export interface RankedTool {
  eqp_id: string
  score: number       // max-axis skew magnitude for the beam
  axis: ScanAxis      // which axis drove the score (the calibration unit)
  nominated: boolean  // in the bottom-N focus set
}

/**
 * Worst-axis skew for one beam: max(|skew_X|, |skew_Y|), keeping the axis label
 * so the drilldown's "fix this coil" reads off the same number as the rank.
 */
export const maxAxisSkew = (
  cells: CellSkew[],
  beam: BeamCondition,
): { score: number, axis: ScanAxis } => {
  let best: { score: number, axis: ScanAxis } = { score: 0, axis: 'X' }
  for (const cell of cells) {
    if (cell.beam !== beam) continue
    const mag = Math.abs(cell.skew)
    if (mag >= best.score) best = { score: mag, axis: cell.axis }
  }
  return best
}

/**
 * Focus-target selection: advisory-threshold gate -> bottom-N.
 * Only tools whose max-axis score exceeds `threshold` are candidates; the
 * worst `n` of those (sorted desc) are nominated. Returns just the candidates
 * (so the fleet self-limits: a tight fleet yields fewer than N, or none).
 */
export const rankFocusTargets = (
  tools: ToolCells[],
  beam: BeamCondition,
  threshold: number,
  n: number,
): RankedTool[] => {
  const candidates = tools
    .map((tool) => {
      const { score, axis } = maxAxisSkew(tool.cells, beam)
      return { eqp_id: tool.eqp_id, score, axis, nominated: false }
    })
    .filter(c => c.score > threshold)
    .sort((a, b) => b.score - a.score)

  return candidates.slice(0, n).map(c => ({ ...c, nominated: true }))
}

export const gateVerdict = (gate: GateInputs): 'up' | 'hold' =>
  gate.cd_in_spec && gate.bsm_in_spec ? 'up' : 'hold'
```

- [ ] **Step 4: Run the test to verify it passes**

Run (from `front-dev-home/`): `node --test app/utils/pmPlanning.test.ts`
Expected: PASS — all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/pmPlanning.ts front-dev-home/app/utils/pmPlanning.test.ts
git commit -m "feat(pm-planning): pure max-axis -> threshold-gate -> bottom-N logic (TDD)"
```

---

### Task B2: API composable

**Files:**
- Create: `front-dev-home/app/composables/usePmPlanningApi.ts`

- [ ] **Step 1: Write the composable**

Types mirror `contracts.py` exactly. Pattern follows `useRecipeTatApi.ts` (`useRuntimeConfig().public.apiBase` + `joinApiPath` + `$fetch`).

```typescript
import { joinApiPath } from '~/utils/apiPath'
import type { BeamCondition, ScanAxis, CellSkew } from '~/utils/pmPlanning'

export interface GateBlock {
  cd_monitoring_value: number
  cd_spec_lower: number
  cd_spec_upper: number
  cd_in_spec: boolean
  bsm_in_spec: boolean
  bsm_sharpness_avg: number
  bsm_noise_avg: number
  post_pm_at: string | null
  prev_post_delta: number | null
  mdc_changed: boolean
  verdict: 'up' | 'hold'
}

export interface EpochPoint {
  epoch_start: string
  mdc: number
  bsm_sharpness_avg: number
}

export interface ToolBlock {
  eqp_id: string
  gate: GateBlock
  cells: CellSkew[]
  epoch_history: EpochPoint[]
}

export interface ConsensusCell {
  beam: BeamCondition
  axis: ScanAxis
  consensus: number
}

export interface FleetDefaults {
  focus_n: number
  advisory_threshold: Record<string, number>
}

export interface FleetResponse {
  tool_type: 'cd-sem'
  fab_id: string
  fetched_at: string
  anchor_date: string
  beam_conditions: BeamCondition[]
  axes: ScanAxis[]
  defaults: FleetDefaults
  consensus: ConsensusCell[]
  tools: ToolBlock[]
}

export const usePmPlanningApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchPmPlanningFleet = async (fabId: string): Promise<FleetResponse> => {
    return await $fetch<FleetResponse>(
      joinApiPath(base, '/cdsem/pm-planning/fleet'),
      { query: { fab_id: fabId } },
    )
  }

  return { fetchPmPlanningFleet }
}
```

- [ ] **Step 2: Verify it typechecks**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: no new errors referencing `usePmPlanningApi.ts` or `pmPlanning.ts`. (Pre-existing unrelated errors elsewhere, if any, are out of scope.)

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/composables/usePmPlanningApi.ts
git commit -m "feat(pm-planning): add usePmPlanningApi fleet fetcher + types"
```

---

### Task B3: Route page

**Files:**
- Create: `front-dev-home/app/pages/ebeam/cd-sem/[fab]/pm-planning.vue`

- [ ] **Step 1: Write the page**

Mirrors `hardware.vue`'s `[fab]` handling exactly (extract param, update nav store, render the View). Per global CLAUDE.md, `<template>` first, then `<script setup>`.

```vue
<template>
  <EbeamPmPlanningView
    :fab="fabId"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>

<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next as Fab)
}

setToolType('cd-sem')
applyFab(fabId.value)

watch(fabId, (next) => {
  applyFab(next)
})
</script>
```

- [ ] **Step 2: Verify the route resolves**

With Flask (:5050) and Nuxt (:3000) running, open `http://localhost:3000/ebeam/cd-sem/M14/pm-planning`.
Expected: the page renders without a 404/500. It will be blank/error until `EbeamPmPlanningView` exists (Task B4) — that's fine; the goal here is that the route file is picked up. If Nuxt reports an unknown component `EbeamPmPlanningView`, proceed to B4.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/pages/ebeam/cd-sem/[fab]/pm-planning.vue
git commit -m "feat(pm-planning): add [fab]/pm-planning route page"
```

---

### Task B4: View shell + MetaBar + fetch

**Files:**
- Create: `front-dev-home/app/components/ebeam/PmPlanningView.vue`

The View owns the fetch (one fleet snapshot), knob state (N + per-beam thresholds), the selected beam, and the selected tool for the gate. Part B renders the MetaBar + gate strip; Part C adds the focus body.

- [ ] **Step 1: Write the View shell**

```vue
<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="identity"
      title="PM Planning"
      subtitle="BM/PM Up 게이트와 다음 PM 집중 관리 대상을 한곳에서 관리합니다."
      :as-of="fleet?.anchor_date"
      cadence="일 1회 갱신"
      :stats="metaStats"
    />

    <!-- 가 · Up 게이트 (슬림 상단 스트립) -->
    <EbeamPmPlanningGateStrip
      :tools="tools"
      :selected-eqp-id="selectedEqpId"
      @update:selected-eqp-id="selectedEqpId = $event"
    />

    <!-- 나 · 집중 관리 본문 — Part C mounts here -->
    <div
      v-if="status === 'pending' && !tools.length"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="mx-auto h-5 w-5 animate-spin text-zinc-400"
      />
      <p class="mt-2">
        함대 스큐 현황 불러오는 중…
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { usePmPlanningApi, type ToolBlock } from '~/composables/usePmPlanningApi'

const props = defineProps<{
  fab: string
  toolLabel: string
  toolType: 'cd-sem'
}>()

const identity = computed(() => `${props.toolLabel} · ${props.fab || '—'}`)

const { fetchPmPlanningFleet } = usePmPlanningApi()

const cacheKey = computed(() => `pm-planning:${props.fab || 'NONE'}`)

const { data: fleet, status } = await useAsyncData(
  () => cacheKey.value,
  () => props.fab ? fetchPmPlanningFleet(props.fab) : Promise.resolve(null),
  { watch: [cacheKey] },
)

const tools = computed<ToolBlock[]>(() => fleet.value?.tools ?? [])

// Selected tool for the gate — defaults to the first tool that is currently
// on HOLD (the one most likely being inspected), else the first tool.
const selectedEqpId = ref<string | null>(null)
watch(tools, (list) => {
  if (selectedEqpId.value && list.some(t => t.eqp_id === selectedEqpId.value)) return
  const hold = list.find(t => t.gate.verdict === 'hold')
  selectedEqpId.value = hold?.eqp_id ?? list[0]?.eqp_id ?? null
}, { immediate: true })

const metaStats = computed(() => {
  const list = tools.value
  const upCount = list.filter(t => t.gate.verdict === 'up').length
  return [
    { key: 'fleet', label: '함대 장비', value: String(list.length) },
    { key: 'up', label: 'Up 가능', value: String(upCount), tone: 'ok' as const },
    { key: 'hold', label: 'Hold', value: String(list.length - upCount), tone: list.length - upCount ? 'warning' as const : 'neutral' as const },
  ]
})
</script>
```

- [ ] **Step 2: Verify the View loads with the MetaBar**

With both servers running, reload `http://localhost:3000/ebeam/cd-sem/M14/pm-planning`.
Expected: the `EbeamMetaBar` renders with title "PM Planning", eyebrow "CD-SEM · M14", and stats (함대 장비 / Up 가능 / Hold). The page may warn about an unknown `EbeamPmPlanningGateStrip` until Task B5 — acceptable within this task; the MetaBar + fetch are what's being verified. Check the browser network tab shows a 200 from `/api/cdsem/pm-planning/fleet?fab_id=M14`.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/PmPlanningView.vue
git commit -m "feat(pm-planning): View shell with MetaBar, fleet fetch, knob/selection state"
```

---

### Task B5: Gate strip component

**Files:**
- Create: `front-dev-home/app/components/ebeam/pmPlanning/GateStrip.vue`

The per-tool Up-gate: a tool selector, the two hard-gate condition tiles (CD_MONITORING ∈ spec, BSM ∈ spec), the verdict, and the advisory + context (delta, MDC-changed) shown as non-blocking info.

- [ ] **Step 1: Write the gate strip**

```vue
<template>
  <div class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="flex flex-wrap items-center gap-x-5 gap-y-3">
      <!-- Tool selector -->
      <div class="flex items-center gap-2">
        <span class="font-mono text-[10px] text-zinc-400">장비</span>
        <USelect
          :model-value="selectedEqpId ?? undefined"
          :items="toolOptions"
          size="sm"
          class="w-[13rem]"
          @update:model-value="(v: string) => emit('update:selectedEqpId', v)"
        />
      </div>

      <template v-if="gate">
        <!-- Verdict -->
        <div class="flex items-center gap-2">
          <span
            class="inline-flex h-7 items-center gap-1.5 rounded-md px-3 text-sm font-semibold"
            :class="gate.verdict === 'up'
              ? 'bg-green-500/15 text-green-600 dark:text-green-400'
              : 'bg-red-500/15 text-red-600 dark:text-red-400'"
          >
            <UIcon
              :name="gate.verdict === 'up' ? 'i-lucide-circle-check' : 'i-lucide-circle-slash'"
              class="h-4 w-4"
            />
            {{ gate.verdict === 'up' ? 'Up 가능' : 'Hold' }}
          </span>
        </div>

        <!-- Hard-gate condition tiles -->
        <div class="flex items-center gap-2">
          <span
            class="inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium ring-1"
            :class="conditionClass(gate.cd_in_spec)"
            :title="`spec [${gate.cd_spec_lower}, ${gate.cd_spec_upper}] nm`"
          >
            <UIcon
              :name="gate.cd_in_spec ? 'i-lucide-check' : 'i-lucide-x'"
              class="h-3.5 w-3.5"
            />
            CD_MON {{ gate.cd_monitoring_value.toFixed(2) }}
          </span>
          <span
            class="inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium ring-1"
            :class="conditionClass(gate.bsm_in_spec)"
            :title="`sharpness ${gate.bsm_sharpness_avg}, noise ${gate.bsm_noise_avg}`"
          >
            <UIcon
              :name="gate.bsm_in_spec ? 'i-lucide-check' : 'i-lucide-x'"
              class="h-3.5 w-3.5"
            />
            BSM
          </span>
        </div>

        <!-- Advisory + context (never blocks Up) -->
        <div class="flex items-center gap-2 text-[11px] text-(--sk-ink-muted)">
          <span
            class="inline-flex h-6 items-center gap-1 rounded px-2"
            :class="advisory.beyond ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400' : ''"
          >
            <UIcon
              name="i-lucide-radar"
              class="h-3.5 w-3.5"
            />
            advisory {{ advisory.score.toFixed(2) }}nm ({{ advisory.beam }}·{{ advisory.axis }})
            <template v-if="advisory.beyond">⚠ 다음 PM 후보</template>
          </span>
          <span
            v-if="gate.prev_post_delta !== null"
            class="font-mono"
            title="전후 변화량 — 게이트 항목 아님(참고)"
          >Δ{{ gate.prev_post_delta >= 0 ? '+' : '' }}{{ gate.prev_post_delta.toFixed(2) }}</span>
          <span
            v-if="gate.mdc_changed"
            class="inline-flex h-6 items-center gap-1 rounded bg-zinc-500/10 px-2"
            title="이 epoch에 MDC 변경됨 — 게이트 항목 아님(epoch 마커)"
          >
            <UIcon
              name="i-lucide-git-commit-horizontal"
              class="h-3.5 w-3.5"
            />
            MDC 변경
          </span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ToolBlock } from '~/composables/usePmPlanningApi'
import { maxAxisSkew, type BeamCondition } from '~/utils/pmPlanning'

const props = defineProps<{
  tools: ToolBlock[]
  selectedEqpId: string | null
}>()

const emit = defineEmits<{ 'update:selectedEqpId': [value: string] }>()

const toolOptions = computed(() =>
  props.tools.map(t => ({
    label: `${t.eqp_id}${t.gate.verdict === 'hold' ? ' · Hold' : ''}`,
    value: t.eqp_id,
  })),
)

const selectedTool = computed(() =>
  props.tools.find(t => t.eqp_id === props.selectedEqpId) ?? null)

const gate = computed(() => selectedTool.value?.gate ?? null)

const conditionClass = (ok: boolean) =>
  ok
    ? 'bg-green-500/10 text-green-600 ring-green-500/30 dark:text-green-400'
    : 'bg-red-500/10 text-red-600 ring-red-500/30 dark:text-red-400'

// Advisory = the tool's worst max-axis skew across both beams. Shown beside
// the gate; "beyond" the default threshold flags it as a next-PM candidate
// but never changes the verdict.
const ADVISORY_DEFAULT: Record<BeamCondition, number> = { '500V': 0.30, '800V': 0.40 }

const advisory = computed(() => {
  const tool = selectedTool.value
  if (!tool) return { score: 0, beam: '500V' as BeamCondition, axis: 'X' as const, beyond: false }
  let worst = { score: 0, beam: '500V' as BeamCondition, axis: 'X' as 'X' | 'Y', beyond: false }
  for (const beam of ['500V', '800V'] as BeamCondition[]) {
    const { score, axis } = maxAxisSkew(tool.cells, beam)
    if (score >= worst.score) {
      worst = { score, beam, axis, beyond: score > ADVISORY_DEFAULT[beam] }
    }
  }
  return worst
})
</script>
```

- [ ] **Step 2: Verify the gate strip end-to-end**

Reload `http://localhost:3000/ebeam/cd-sem/M14/pm-planning`.
Expected: the strip shows a tool dropdown (defaulting to a Hold tool if one exists), an Up/Hold verdict, two condition tiles (CD_MON value + BSM, green when in-spec / red when not), and the advisory chip with `Δ` and possibly an "MDC 변경" marker. Switching tools in the dropdown updates every field. Confirm a Hold tool shows at least one red condition tile, and an Up tool shows both green.

- [ ] **Step 3: Screenshot for the record**

Use Playwright MCP `browser_take_screenshot` with filename `.playwright-mcp/screenshots/pm-planning-gate.png`.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/pmPlanning/GateStrip.vue
git commit -m "feat(pm-planning): per-tool Up-gate strip (verdict + conditions + advisory)"
```

---

# PART C — Frontend focus-ranking (knobs + drilldown + convergence)

Adds the full-width focus-target body: per-beam ranked lists, the N + threshold knobs, axis drilldown, and the convergence panel.

### Task C1: Focus-ranking component (ranked list + knobs)

**Files:**
- Create: `front-dev-home/app/components/ebeam/pmPlanning/FocusRanking.vue`
- Modify: `front-dev-home/app/components/ebeam/PmPlanningView.vue` (mount the component + own knob state)

- [ ] **Step 1: Write the FocusRanking component**

Renders one ranked bar list per beam condition, using `rankFocusTargets`. Bars are styled divs (no chart lib needed). Emits a tool/beam selection for the convergence panel.

```vue
<template>
  <div class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
          집중 관리 대상 — 다음 PM
        </h3>
        <span class="text-[10.5px] text-zinc-400">
          임계선 초과 후보 중 빔별 상위 {{ focusN }}대
        </span>
      </div>
      <!-- Knobs: N + per-beam threshold -->
      <div class="flex items-center gap-3">
        <label class="flex items-center gap-1.5 text-[11px] text-(--sk-ink-muted)">
          N
          <USelect
            :model-value="String(focusN)"
            :items="['1', '2', '3', '4', '5']"
            size="xs"
            class="w-[4.5rem]"
            @update:model-value="(v: string) => emit('update:focusN', Number(v))"
          />
        </label>
        <label
          v-for="beam in beamConditions"
          :key="beam"
          class="flex items-center gap-1.5 text-[11px] text-(--sk-ink-muted)"
        >
          {{ beam }} 임계
          <UInput
            :model-value="String(threshold[beam] ?? 0)"
            size="xs"
            type="number"
            step="0.05"
            class="w-[5rem]"
            @update:model-value="(v: string) => emit('update:threshold', { beam, value: Number(v) })"
          />
        </label>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <div
        v-for="beam in beamConditions"
        :key="beam"
      >
        <div class="mb-1.5 flex items-center gap-2">
          <span class="text-[12px] font-semibold text-zinc-700 dark:text-zinc-300">{{ beam }}</span>
          <span class="font-mono text-[10px] text-zinc-400">임계 {{ (threshold[beam] ?? 0).toFixed(2) }}nm</span>
        </div>

        <div
          v-if="!rankedByBeam[beam].length"
          class="rounded-lg border border-dashed border-zinc-300/70 px-3 py-4 text-center text-[11px] text-(--sk-ink-muted) dark:border-zinc-700/70"
        >
          임계선을 넘는 장비가 없습니다 — 이 빔은 수렴 상태입니다.
        </div>

        <ul
          v-else
          class="space-y-1"
        >
          <li
            v-for="(row, idx) in rankedByBeam[beam]"
            :key="row.eqp_id"
          >
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-zinc-100/70 dark:hover:bg-zinc-800/50"
              :class="isSelected(beam, row.eqp_id) ? 'ring-1 ring-(--sk-accent)' : ''"
              @click="emit('select', { beam, eqpId: row.eqp_id })"
            >
              <span class="w-4 shrink-0 font-mono text-[11px] text-zinc-400">{{ idx + 1 }}</span>
              <span class="w-[7.5rem] shrink-0 truncate font-mono text-[11.5px] text-zinc-800 dark:text-zinc-200">{{ row.eqp_id }}</span>
              <span class="relative h-4 flex-1 overflow-hidden rounded bg-zinc-100 dark:bg-zinc-800">
                <span
                  class="absolute inset-y-0 left-0 rounded bg-red-500/70"
                  :style="{ width: barWidth(beam, row.score) }"
                />
              </span>
              <span class="w-[3rem] shrink-0 text-right font-mono text-[11px] tabular-nums text-red-600 dark:text-red-400">{{ row.score.toFixed(2) }}</span>
              <span class="w-[1.5rem] shrink-0 text-center font-mono text-[10px] text-zinc-400">{{ row.axis }}</span>
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ToolBlock } from '~/composables/usePmPlanningApi'
import { rankFocusTargets, type BeamCondition, type RankedTool } from '~/utils/pmPlanning'

const props = defineProps<{
  tools: ToolBlock[]
  beamConditions: BeamCondition[]
  focusN: number
  threshold: Record<string, number>
  selected: { beam: BeamCondition, eqpId: string } | null
}>()

const emit = defineEmits<{
  'update:focusN': [value: number]
  'update:threshold': [payload: { beam: BeamCondition, value: number }]
  'select': [payload: { beam: BeamCondition, eqpId: string }]
}>()

const rankedByBeam = computed<Record<string, RankedTool[]>>(() => {
  const out: Record<string, RankedTool[]> = {}
  for (const beam of props.beamConditions) {
    out[beam] = rankFocusTargets(props.tools, beam, props.threshold[beam] ?? 0, props.focusN)
  }
  return out
})

// Bar width is relative to the worst score in that beam so the strip fills.
const barWidth = (beam: BeamCondition, score: number): string => {
  const rows = rankedByBeam.value[beam] ?? []
  const max = rows.length ? rows[0].score : 1
  return `${Math.max(6, Math.round((score / max) * 100))}%`
}

const isSelected = (beam: BeamCondition, eqpId: string) =>
  props.selected?.beam === beam && props.selected?.eqpId === eqpId
</script>
```

- [ ] **Step 2: Wire it into the View**

In `PmPlanningView.vue`, add knob + selection state and mount the component. Add this state block to `<script setup>` (after the `metaStats` computed):

```typescript
import type { BeamCondition } from '~/utils/pmPlanning'

// Knobs — seeded from the server defaults, then engineer-adjustable (client-only).
const focusN = ref(3)
const threshold = ref<Record<string, number>>({ '500V': 0.30, '800V': 0.40 })
const beamConditions = computed<BeamCondition[]>(() => fleet.value?.beam_conditions ?? ['500V', '800V'])

watch(fleet, (f) => {
  if (!f) return
  focusN.value = f.defaults.focus_n
  threshold.value = { ...f.defaults.advisory_threshold }
}, { immediate: true })

const setThreshold = ({ beam, value }: { beam: BeamCondition, value: number }) => {
  threshold.value = { ...threshold.value, [beam]: value }
}

// Selected (beam, tool) for the convergence panel — defaults to the top
// nominee once data arrives.
const focusSelection = ref<{ beam: BeamCondition, eqpId: string } | null>(null)
const selectFocus = (payload: { beam: BeamCondition, eqpId: string }) => {
  focusSelection.value = payload
}
```

Then replace the Part-C placeholder `<div v-if="status === 'pending' …>` block in the template with:

```vue
    <template v-if="tools.length">
      <EbeamPmPlanningFocusRanking
        :tools="tools"
        :beam-conditions="beamConditions"
        :focus-n="focusN"
        :threshold="threshold"
        :selected="focusSelection"
        @update:focus-n="focusN = $event"
        @update:threshold="setThreshold"
        @select="selectFocus"
      />
    </template>
    <div
      v-else-if="status === 'pending'"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
    >
      <UIcon name="i-lucide-loader-2" class="mx-auto h-5 w-5 animate-spin text-zinc-400" />
      <p class="mt-2">함대 스큐 현황 불러오는 중…</p>
    </div>
```

- [ ] **Step 3: Verify ranking + knobs**

Reload the page.
Expected: two beam columns (500V/800V), each with a ranked list of red bars (worst at top, score + axis label), capped at N=3. Changing **N** adds/removes rows; raising a beam's **임계** threshold drops tools below the line (and a fully-converged beam shows the "임계선을 넘는 장비가 없습니다" message). Clicking a row highlights it (ring).

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/pmPlanning/FocusRanking.vue front-dev-home/app/components/ebeam/PmPlanningView.vue
git commit -m "feat(pm-planning): focus ranking with N + per-beam threshold knobs"
```

---

### Task C2: Convergence panel (axis drilldown + epoch history)

**Files:**
- Create: `front-dev-home/app/components/ebeam/pmPlanning/ConvergencePanel.vue`
- Modify: `front-dev-home/app/components/ebeam/PmPlanningView.vue` (mount below FocusRanking)

Shows the selected tool's cells for the selected beam: `현재값 · median(목표) · 부호 있는 gap` with a qualitative arrow, both axes (drilldown), and the tool's MDC/BSM epoch history. MDC is explicitly **not** an absolute target.

- [ ] **Step 1: Write the convergence panel**

```vue
<template>
  <div
    v-if="tool"
    class="dashboard-surface rounded-2xl px-3.5 py-3"
  >
    <div class="mb-2 flex items-center gap-2">
      <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
        수렴 추천 — {{ tool.eqp_id }} · {{ beam }}
      </h3>
      <span class="text-[10.5px] text-zinc-400">축별 현재값 → fleet median</span>
    </div>

    <!-- Axis drilldown: one row per axis -->
    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <div
        v-for="cell in beamCells"
        :key="cell.axis"
        class="rounded-lg border border-zinc-200/70 px-3 py-2 dark:border-zinc-800/70"
      >
        <div class="flex items-center justify-between">
          <span class="font-mono text-[11px] text-zinc-500">{{ beam }}·{{ cell.axis }}</span>
          <span
            class="inline-flex items-center gap-1 text-[11px] font-semibold"
            :class="Math.abs(cell.gap) > 0.4 ? 'text-amber-600 dark:text-amber-400' : 'text-zinc-500'"
          >
            <UIcon
              :name="cell.gap > 0 ? 'i-lucide-arrow-down' : 'i-lucide-arrow-up'"
              class="h-3.5 w-3.5"
            />
            {{ directionText(cell.gap) }}
          </span>
        </div>
        <div class="mt-1 flex items-baseline gap-3 font-mono text-[12px] tabular-nums">
          <span class="text-zinc-800 dark:text-zinc-200">현재 {{ cell.current_value.toFixed(3) }}</span>
          <span class="text-(--sk-ink-muted)">median {{ cell.median.toFixed(3) }}</span>
          <span :class="cell.gap >= 0 ? 'text-red-500' : 'text-blue-500'">
            gap {{ cell.gap >= 0 ? '+' : '' }}{{ cell.gap.toFixed(3) }}
          </span>
        </div>
      </div>
    </div>

    <!-- Epoch history — this tool's own MDC record (not a target) -->
    <div class="mt-3">
      <div class="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-zinc-400">
        MDC · BSM 이력 (이 장비 자신의 기록 — 절대 목표값 아님)
      </div>
      <div class="flex flex-wrap gap-2">
        <div
          v-for="ep in tool.epoch_history"
          :key="ep.epoch_start"
          class="rounded-md bg-zinc-100/70 px-2.5 py-1.5 text-[11px] dark:bg-zinc-800/60"
        >
          <span class="font-mono text-zinc-500">{{ ep.epoch_start }}</span>
          <span class="ml-2 font-mono text-zinc-800 dark:text-zinc-200">MDC {{ ep.mdc.toFixed(4) }}</span>
          <span class="ml-2 font-mono text-(--sk-ink-muted)">sharp {{ ep.bsm_sharpness_avg.toFixed(3) }}</span>
        </div>
      </div>
    </div>
  </div>
  <div
    v-else
    class="dashboard-surface rounded-2xl px-6 py-8 text-center text-[12px] text-(--sk-ink-muted)"
  >
    위 순위에서 장비를 클릭하면 축별 수렴 추천과 epoch 이력이 표시됩니다.
  </div>
</template>

<script setup lang="ts">
import type { ToolBlock } from '~/composables/usePmPlanningApi'
import type { BeamCondition } from '~/utils/pmPlanning'

const props = defineProps<{
  tools: ToolBlock[]
  selection: { beam: BeamCondition, eqpId: string } | null
}>()

const tool = computed(() =>
  props.selection
    ? props.tools.find(t => t.eqp_id === props.selection!.eqpId) ?? null
    : null)

const beam = computed<BeamCondition>(() => props.selection?.beam ?? '500V')

const beamCells = computed(() =>
  (tool.value?.cells ?? []).filter(c => c.beam === beam.value))

// Qualitative arrow only (no computed MDC target — office regression deferred).
const directionText = (gap: number): string => {
  if (Math.abs(gap) < 0.05) return 'median 근접'
  return gap > 0
    ? `median보다 +${gap.toFixed(2)}nm 높음 → 낮추는 쪽`
    : `median보다 ${gap.toFixed(2)}nm 낮음 → 높이는 쪽`
}
</script>
```

- [ ] **Step 2: Mount it in the View**

In `PmPlanningView.vue`, inside the `<template v-if="tools.length">` block, add the panel right after `EbeamPmPlanningFocusRanking`:

```vue
      <EbeamPmPlanningConvergencePanel
        :tools="tools"
        :selection="focusSelection"
      />
```

Also default the selection to the top nominee so the panel isn't empty on load. Update `selectFocus`/add a watcher in `<script setup>`:

```typescript
import { rankFocusTargets } from '~/utils/pmPlanning'

// Auto-select the worst nominee of the first beam once data + knobs settle,
// so the convergence panel shows something without a click.
watch([tools, beamConditions, focusN, threshold], () => {
  if (focusSelection.value
    && tools.value.some(t => t.eqp_id === focusSelection.value!.eqpId)) return
  for (const beam of beamConditions.value) {
    const ranked = rankFocusTargets(tools.value, beam, threshold.value[beam] ?? 0, focusN.value)
    if (ranked.length) {
      focusSelection.value = { beam, eqpId: ranked[0].eqp_id }
      return
    }
  }
  focusSelection.value = null
}, { immediate: true })
```

- [ ] **Step 3: Verify the convergence panel**

Reload the page.
Expected: below the ranking, a panel for the auto-selected top nominee shows two axis cards (X/Y) each with `현재 / median / gap` and a qualitative arrow ("median보다 +0.xx nm 높음 → 낮추는 쪽"), plus an MDC·BSM epoch history strip. Clicking a different ranked tool/beam swaps the panel. Confirm the worst axis (the one that drove the rank) shows the largest `gap`.

- [ ] **Step 4: Screenshot the full page**

Use Playwright MCP `browser_take_screenshot` with filename `.playwright-mcp/screenshots/pm-planning-full.png`.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/pmPlanning/ConvergencePanel.vue front-dev-home/app/components/ebeam/PmPlanningView.vue
git commit -m "feat(pm-planning): convergence panel (axis drilldown + epoch history)"
```

---

### Task C3: Final verification sweep

**Files:** none (verification only)

- [ ] **Step 1: Re-run the pure-logic tests**

Run (from `front-dev-home/`): `node --test app/utils/pmPlanning.test.ts`
Expected: all tests PASS.

- [ ] **Step 2: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: no new errors in any `pmPlanning`/`PmPlanning` file.

- [ ] **Step 3: Lint**

Run (from `front-dev-home/`): `npm run lint`
Expected: no new lint errors in the created files. Fix any that appear (commonly import ordering or `<template>`-before-`<script>` per global CLAUDE.md — already satisfied here).

- [ ] **Step 4: Backend determinism re-check**

Run: `python -m back_dev_home.ebeam.hitachi.pm_planning.data`
Expected: no `AssertionError`.

- [ ] **Step 5: End-to-end manual pass**

With both servers running, walk `http://localhost:3000/ebeam/cd-sem/M14/pm-planning`:
- Gate strip: switch tools, confirm Up/Hold + condition tiles + advisory update.
- Ranking: change N and a threshold; confirm rows and the "수렴 상태" empty message react.
- Convergence: click rows; confirm axis drilldown + epoch history swap.
- Try another fab: `…/cd-sem/M16/pm-planning` returns a different (but deterministic) fleet.

- [ ] **Step 6: Commit any lint/typecheck fixes**

```bash
git add -A
git commit -m "chore(pm-planning): lint/typecheck/verification fixes"
```

---

## Self-Review notes (for the implementer)

- **Spec coverage:** Up gate (post-value ∈ spec, advisory non-blocking, delta/MDC as context) → Tasks A3/B5. Focus ranking (max-axis → threshold-gate → bottom-N, knobs) → Tasks B1/C1. Axis drilldown + convergence (qualitative arrow, MDC-not-a-target, epoch history) → Task C2. Spec-range reuse seam (hardware owns it) → Task A1. Layout A (slim gate strip + full-width body) → Tasks B4/C1/C2. Contract/swap surface → A2/A4.
- **Deferred (not in this plan, per spec §7.2):** computed MDC target values, special-angle validation, alarm channel.
- **Type consistency:** `CellSkew`/`BeamCondition`/`ScanAxis` are defined once in `pmPlanning.ts` and re-used by the composable; `ToolBlock`/`GateBlock` are defined once in the composable and consumed by all three components. The Python `contracts.py` field names match the TypeScript interfaces 1:1 (snake_case preserved across the wire).
