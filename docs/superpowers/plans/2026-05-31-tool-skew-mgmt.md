# 장비간 스큐(Tool-to-Tool Skew) 관리 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase-1 mock backend contract + a single `/ebeam/cd-sem/[fab]/skew-check` dashboard that recommends the best mutually-matched (N배화) tool group for a recipe, with a pairwise-skew matrix, a client-side tolerance knob, a production "참고" chip, and fleet/trend/MDC sections.

**Architecture:** A new Flask feature folder `back_dev_home/ebeam/hitachi/skew/` serves a raw 3-tier skew contract from deterministic JSON fixtures (no real statistics — office swaps `data.py` later). The Nuxt page fetches that raw payload once and does **all grouping on the client**: a pure TS util (`app/utils/skewGrouping.ts`) computes maximal cliques (= N배화) at the current tolerance, picks the primary answer by the §4.2 tiebreakers, and the UI redraws instantly when the tolerance knob moves — no refetch. Phase-1 proves **contract + UX only**; correctness of recommendations is verified later with office data.

**Tech Stack:** Flask Blueprint + TypedDict contracts + JSON fixtures (backend); Nuxt 4 + NuxtUI 4 + Tailwind v4 (`--sk-*` tokens) + ECharts 6 (frontend); `node --test` with `node:test`/`node:assert` for the algorithm.

**Source spec:** `docs/superpowers/specs/2026-05-31-tool-skew-mgmt-design.md`
**Decisions/terms:** `docs/issues/hardware_mgmt/skew_check_next_steps.md`, `docs/issues/hardware_mgmt/skew_check_terminology_and_stats.md`

---

## Conventions locked from the existing codebase

- **Backend folder** mirrors `back_dev_home/ebeam/hitachi/hardware/`: `routes.py` + `data.py` (swap surface) + `contracts.py` (TypedDict) + `providers/mock.py` + `providers/office.py` (stub) + `__fixtures__/*.json`. `__init__.py` re-exports `bp`. App factory auto-discovers via `rglob("routes.py")` and mounts at `/api`.
- **Backend route shape** copies hardware exactly: `@bp.get("/<tool_slug>/skew/check")` where `tool_slug ∈ {cdsem, hvsem}` (validated against `VALID_TOOL_SLUGS` from `back_dev_home.ebeam.hitachi._tool_specs`). Final URL: `/api/cdsem/skew/check?fab_id=R3&recipe_id=...`.
- **Provider selection** copies `hardware/data.py`: `os.environ.get("SKEWNONO_SKEW_PROVIDER")` else `is_cloud()` → `office` else `mock`.
- **Frontend page** is a thin wrapper (copy `app/pages/ebeam/cd-sem/[fab]/hardware.vue`): extract `route.params.fab`, `setToolType('cd-sem')`, delegate to a `<EbeamSkewCheckView>` component.
- **Component auto-import prefix:** files in `app/components/ebeam/skewCheck/Foo.vue` import as `<EbeamSkewCheckFoo>`. Never repeat the folder name in the filename.
- **Composable** copies `app/composables/useAfmDetailApi.ts`: `useRuntimeConfig().public.apiBase` + `joinApiPath(base, path)` + `useAsyncData(key, fn)`.
- **Feature slug** `skew-check` must be registered in `app/utils/features.ts` (`FEATURE_SLUGS`) and gated in `app/composables/useNavigation.ts` (`featureEnabledForToolType`).
- **Colors:** semantic tokens only — `var(--sk-ink)`, `var(--sk-ink-muted)`, `var(--sk-ok)`/`--sk-ok-soft`, `var(--sk-bad)`/`--sk-bad-soft`, `var(--sk-accent)`. No raw `text-zinc-*` for muted text.
- **Tests:** colocated `app/**/*.test.ts`, run with `npm test` (`node --test "app/**/*.test.ts"`). Import the unit under test with an explicit `.ts` extension (see `app/utils/ruleEngine.test.ts`).

## File structure (created/modified)

**Backend (new folder `back_dev_home/ebeam/hitachi/skew/`):**
- `__init__.py` — re-export `bp`
- `contracts.py` — `SkewCheckPayload` + nested TypedDicts (the swap contract)
- `data.py` — swap surface (provider dispatch)
- `routes.py` — Blueprint `ebeam_skew`, route `/<tool_slug>/skew/check`
- `providers/__init__.py`, `providers/mock.py` (loads fixtures), `providers/office.py` (raises `NotImplementedError`)
- `__fixtures__/skew_cdsem_r3.json` — deterministic mock payload

**Frontend:**
- Modify `app/utils/features.ts` — add `'skew-check'` slug
- Modify `app/composables/useNavigation.ts` — gate `skew-check` to cd-sem
- Create `app/utils/skewGrouping.ts` + `app/utils/skewGrouping.test.ts` — the algorithm (TDD)
- Create `app/composables/useSkewCheckApi.ts` — fetch wrapper + TS types
- Create `app/pages/ebeam/cd-sem/[fab]/skew-check.vue` — thin page wrapper
- Create `app/components/ebeam/SkewCheckView.vue` — `<EbeamSkewCheckView>` (orchestrator)
- Create `app/components/ebeam/skewCheck/RecommendationCard.vue`
- Create `app/components/ebeam/skewCheck/PairMatrix.vue`
- Create `app/components/ebeam/skewCheck/ToleranceKnob.vue`
- Create `app/components/ebeam/skewCheck/ProductionChip.vue`
- Create `app/components/ebeam/skewCheck/FleetStatus.vue`
- Create `app/components/ebeam/skewCheck/TrendChart.vue`
- Create `app/components/ebeam/skewCheck/MdcTimeline.vue`

---

## Slice 1 — Backend contract + fixtures (the swap surface)

### Task 1: Skew contract (`contracts.py`)

**Files:**
- Create: `back_dev_home/ebeam/hitachi/skew/contracts.py`

- [ ] **Step 1: Write the contract TypedDicts**

```python
"""Canonical tool-to-tool skew API contract (Phase-1).

The route returns RAW per-cell pairwise skew matrices + a current tolerance.
The client computes N배화 (maximal-clique) grouping; the server never groups.
Office swaps `data.py` to produce these same shapes from real statistics.
"""

from typing import Literal, NotRequired, TypedDict


ToolSlug = Literal["cdsem", "hvsem"]
Tier = Literal["direct", "predicted"]
Confidence = Literal["High", "Med", "Low"]
Axis = Literal["X", "Y"]
ProductionLevel = Literal["high", "mid", "low"]
EpochKind = Literal["hard", "soft"]


class ToolRef(TypedDict):
    eqp_id: str
    label: str


class SkewMatrixBlock(TypedDict):
    # `tools` indexes both axes of `values`. `values` is symmetric, diagonal 0.
    # A null cell means that tool-pair has no data in this cell (not TTTM-able).
    tools: list[str]
    values: list[list[float | None]]


class CellSkew(TypedDict):
    cell_id: str
    beam_condition: str
    axis: Axis
    cd_band: str  # one of "<25" | "25-50" | "50-100" | "100-200" | ">=200"
    mdc_epoch: str
    tier: Tier
    confidence: Confidence
    labels: list[str]  # e.g. ["특수각 포함"] — informational flags
    direct_skew_matrix: SkewMatrixBlock | None
    predicted_skew_matrix: SkewMatrixBlock | None


class ProductionOverlapRow(TypedDict):
    pair: str  # "EQP01·EQP02"
    overlap: float  # 0..1 distribution-overlap score


class ProductionCorroboration(TypedDict):
    level: ProductionLevel
    note: str  # always "TTTM 미반영"
    detail: list[ProductionOverlapRow]


class ConsensusDeviation(TypedDict):
    eqp_id: str
    deviation: float  # tool − consensus (nm), signed


class FleetToday(TypedDict):
    matrix: SkewMatrixBlock
    consensus_deviation: list[ConsensusDeviation]


class TrendPoint(TypedDict):
    eqp_id: str
    date: str  # YYYY-MM-DD
    skew: float


class EpochMarker(TypedDict):
    eqp_id: str
    date: str
    kind: EpochKind  # hard = MDC changed (epoch reset); soft = BM/PM, MDC unchanged
    mdc_changed: bool
    label: str


class MdcHistoryEntry(TypedDict):
    eqp_id: str
    beam_condition: str
    axis: Axis
    date: str
    old_value: float
    new_value: float


class ToleranceRange(TypedDict):
    min: float
    max: float
    step: float


class SkewCheckPayload(TypedDict):
    tool_slug: ToolSlug
    fab_id: str
    recipe_id: str | None
    available: bool
    fetched_at: str
    summary: str
    tools: list[ToolRef]
    current_tolerance: float  # default 0.05 (nm)
    tolerance_range: ToleranceRange  # {min:0.01, max:0.20, step:0.005}
    occupied_cells: list[CellSkew]
    production_corroboration: ProductionCorroboration
    fleet_today: FleetToday
    trend: list[TrendPoint]
    epoch_markers: list[EpochMarker]
    mdc_history: list[MdcHistoryEntry]
    raw: NotRequired[dict[str, object]]
```

- [ ] **Step 2: Verify it imports**

Run: `cd C:\Code\skewnono_v3_nuxt; python -c "from back_dev_home.ebeam.hitachi.skew import contracts; print(contracts.SkewCheckPayload.__name__)"`
Expected: prints `SkewCheckPayload` (no import error).

> Note: the package import requires `back_dev_home/ebeam/hitachi/skew/__init__.py` to exist. Create an empty placeholder first if Step 2 fails with `ModuleNotFoundError`; Task 4 fills it with the real re-export.

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/hitachi/skew/contracts.py
git commit -m "feat(skew): add Phase-1 tool-skew API contract (TypedDicts)"
```

---

### Task 2: Deterministic mock fixture (`__fixtures__/skew_cdsem_r3.json`)

**Files:**
- Create: `back_dev_home/ebeam/hitachi/skew/__fixtures__/skew_cdsem_r3.json`

This fixture must exercise every contract branch the UI renders: a 5-tool fleet, 3 occupied cells (2 `direct`, 1 `predicted`), one `null` pair, a production chip with drilldown, fleet/trend rows, and both a hard and a soft epoch marker. The pairwise values are hand-picked so that at the default tolerance `0.05` the maximal N배화 group is `{EQP01, EQP02, EQP04}` (N=3) — used as the expected primary answer in the algorithm tests (Task 7).

- [ ] **Step 1: Write the fixture**

```json
{
  "tool_slug": "cdsem",
  "fab_id": "R3",
  "recipe_id": "CD_MON_16",
  "available": true,
  "fetched_at": "2026-05-31T14:30:00",
  "summary": "R3 CD-SEM 함대 5대 · 점유 셀 3개(직접 2 · 예측 1) 기준 추천입니다.",
  "tools": [
    { "eqp_id": "EQP01", "label": "CD-SEM 01" },
    { "eqp_id": "EQP02", "label": "CD-SEM 02" },
    { "eqp_id": "EQP03", "label": "CD-SEM 03" },
    { "eqp_id": "EQP04", "label": "CD-SEM 04" },
    { "eqp_id": "EQP05", "label": "CD-SEM 05" }
  ],
  "current_tolerance": 0.05,
  "tolerance_range": { "min": 0.01, "max": 0.2, "step": 0.005 },
  "occupied_cells": [
    {
      "cell_id": "bc1-X-25-50-e7",
      "beam_condition": "BC1",
      "axis": "X",
      "cd_band": "25-50",
      "mdc_epoch": "e7",
      "tier": "direct",
      "confidence": "High",
      "labels": [],
      "direct_skew_matrix": {
        "tools": ["EQP01", "EQP02", "EQP03", "EQP04", "EQP05"],
        "values": [
          [0.0, 0.02, 0.12, 0.03, 0.18],
          [0.02, 0.0, 0.1, 0.04, 0.16],
          [0.12, 0.1, 0.0, 0.11, 0.08],
          [0.03, 0.04, 0.11, 0.0, 0.15],
          [0.18, 0.16, 0.08, 0.15, 0.0]
        ]
      },
      "predicted_skew_matrix": null
    },
    {
      "cell_id": "bc1-Y-25-50-e7",
      "beam_condition": "BC1",
      "axis": "Y",
      "cd_band": "25-50",
      "mdc_epoch": "e7",
      "tier": "direct",
      "confidence": "High",
      "labels": [],
      "direct_skew_matrix": {
        "tools": ["EQP01", "EQP02", "EQP03", "EQP04", "EQP05"],
        "values": [
          [0.0, 0.03, 0.14, 0.04, 0.2],
          [0.03, 0.0, 0.13, 0.045, 0.19],
          [0.14, 0.13, 0.0, 0.12, 0.09],
          [0.04, 0.045, 0.12, 0.0, 0.17],
          [0.2, 0.19, 0.09, 0.17, 0.0]
        ]
      },
      "predicted_skew_matrix": null
    },
    {
      "cell_id": "bc2-X-50-100-e7",
      "beam_condition": "BC2",
      "axis": "X",
      "cd_band": "50-100",
      "mdc_epoch": "e7",
      "tier": "predicted",
      "confidence": "Low",
      "labels": ["대역 외삽"],
      "direct_skew_matrix": null,
      "predicted_skew_matrix": {
        "tools": ["EQP01", "EQP02", "EQP03", "EQP04", "EQP05"],
        "values": [
          [0.0, 0.03, 0.13, 0.04, null],
          [0.03, 0.0, 0.12, 0.045, null],
          [0.13, 0.12, 0.0, 0.11, null],
          [0.04, 0.045, 0.11, 0.0, null],
          [null, null, null, null, 0.0]
        ]
      }
    }
  ],
  "production_corroboration": {
    "level": "mid",
    "note": "TTTM 미반영",
    "detail": [
      { "pair": "EQP01·EQP02", "overlap": 0.86 },
      { "pair": "EQP01·EQP04", "overlap": 0.78 },
      { "pair": "EQP02·EQP04", "overlap": 0.74 }
    ]
  },
  "fleet_today": {
    "matrix": {
      "tools": ["EQP01", "EQP02", "EQP03", "EQP04", "EQP05"],
      "values": [
        [0.0, 0.02, 0.12, 0.03, 0.18],
        [0.02, 0.0, 0.1, 0.04, 0.16],
        [0.12, 0.1, 0.0, 0.11, 0.08],
        [0.03, 0.04, 0.11, 0.0, 0.15],
        [0.18, 0.16, 0.08, 0.15, 0.0]
      ]
    },
    "consensus_deviation": [
      { "eqp_id": "EQP01", "deviation": -0.01 },
      { "eqp_id": "EQP02", "deviation": 0.01 },
      { "eqp_id": "EQP03", "deviation": 0.09 },
      { "eqp_id": "EQP04", "deviation": 0.0 },
      { "eqp_id": "EQP05", "deviation": -0.13 }
    ]
  },
  "trend": [
    { "eqp_id": "EQP01", "date": "2026-05-24", "skew": 0.0 },
    { "eqp_id": "EQP01", "date": "2026-05-27", "skew": 0.01 },
    { "eqp_id": "EQP01", "date": "2026-05-31", "skew": -0.01 },
    { "eqp_id": "EQP03", "date": "2026-05-24", "skew": 0.05 },
    { "eqp_id": "EQP03", "date": "2026-05-27", "skew": 0.06 },
    { "eqp_id": "EQP03", "date": "2026-05-31", "skew": 0.09 },
    { "eqp_id": "EQP05", "date": "2026-05-24", "skew": -0.04 },
    { "eqp_id": "EQP05", "date": "2026-05-28", "skew": -0.12 },
    { "eqp_id": "EQP05", "date": "2026-05-31", "skew": -0.13 }
  ],
  "epoch_markers": [
    { "eqp_id": "EQP05", "date": "2026-05-28", "kind": "hard", "mdc_changed": true, "label": "PM + MDC 변경 (epoch 리셋)" },
    { "eqp_id": "EQP03", "date": "2026-05-26", "kind": "soft", "mdc_changed": false, "label": "BM (MDC 불변)" }
  ],
  "mdc_history": [
    { "eqp_id": "EQP05", "beam_condition": "BC1", "axis": "X", "date": "2026-05-28", "old_value": 1.0012, "new_value": 1.0007 },
    { "eqp_id": "EQP05", "beam_condition": "BC1", "axis": "Y", "date": "2026-05-28", "old_value": 1.0009, "new_value": 1.0005 }
  ]
}
```

- [ ] **Step 2: Verify it is valid JSON**

Run: `cd C:\Code\skewnono_v3_nuxt; python -c "import json; json.load(open('back_dev_home/ebeam/hitachi/skew/__fixtures__/skew_cdsem_r3.json', encoding='utf-8')); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/hitachi/skew/__fixtures__/skew_cdsem_r3.json
git commit -m "feat(skew): add deterministic Phase-1 skew fixture (R3 cd-sem)"
```

---

### Task 3: Mock + office providers

**Files:**
- Create: `back_dev_home/ebeam/hitachi/skew/providers/__init__.py`
- Create: `back_dev_home/ebeam/hitachi/skew/providers/mock.py`
- Create: `back_dev_home/ebeam/hitachi/skew/providers/office.py`

- [ ] **Step 1: Write `providers/__init__.py`**

```python
from back_dev_home.ebeam.hitachi.skew.providers import mock, office

__all__ = ["mock", "office"]
```

- [ ] **Step 2: Write `providers/mock.py`**

```python
"""Phase-1 skew mock provider — serves a deterministic fixture per fab."""

import json
from pathlib import Path

from back_dev_home.ebeam.hitachi.skew.contracts import SkewCheckPayload

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "__fixtures__"


def _empty_payload(tool_slug: str, fab_id: str, recipe_id: str | None) -> SkewCheckPayload:
    return {
        "tool_slug": tool_slug,  # type: ignore[typeddict-item]
        "fab_id": fab_id,
        "recipe_id": recipe_id,
        "available": False,
        "fetched_at": "",
        "summary": f"{fab_id} {tool_slug} 함대의 스큐 mock 데이터가 아직 없습니다.",
        "tools": [],
        "current_tolerance": 0.05,
        "tolerance_range": {"min": 0.01, "max": 0.2, "step": 0.005},
        "occupied_cells": [],
        "production_corroboration": {"level": "low", "note": "TTTM 미반영", "detail": []},
        "fleet_today": {"matrix": {"tools": [], "values": []}, "consensus_deviation": []},
        "trend": [],
        "epoch_markers": [],
        "mdc_history": [],
    }


def get_skew_check(
    tool_slug: str,
    fab_id: str,
    recipe_id: str | None,
) -> SkewCheckPayload:
    fixture = _FIXTURE_DIR / f"skew_{tool_slug}_{fab_id.lower()}.json"
    if not fixture.exists():
        return _empty_payload(tool_slug, fab_id, recipe_id)
    payload: SkewCheckPayload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["recipe_id"] = recipe_id or payload.get("recipe_id")
    return payload
```

- [ ] **Step 3: Write `providers/office.py` (stub)**

```python
"""Office skew provider — wired against real statistics during Phase-2/3 swap."""

from back_dev_home.ebeam.hitachi.skew.contracts import SkewCheckPayload


def get_skew_check(
    tool_slug: str,
    fab_id: str,
    recipe_id: str | None,
) -> SkewCheckPayload:
    raise NotImplementedError(
        "office skew provider is wired during the office data swap (Phase-2/3)"
    )
```

- [ ] **Step 4: Verify the mock loads the fixture**

Run: `cd C:\Code\skewnono_v3_nuxt; python -c "from back_dev_home.ebeam.hitachi.skew.providers import mock; p = mock.get_skew_check('cdsem','R3','X'); print(p['available'], len(p['occupied_cells']), p['current_tolerance'])"`
Expected: prints `True 3 0.05`.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/skew/providers/
git commit -m "feat(skew): add mock (fixture-backed) + office-stub skew providers"
```

---

### Task 4: Swap surface (`data.py`), Blueprint (`routes.py`), package re-export

**Files:**
- Create: `back_dev_home/ebeam/hitachi/skew/data.py`
- Create: `back_dev_home/ebeam/hitachi/skew/routes.py`
- Create/replace: `back_dev_home/ebeam/hitachi/skew/__init__.py`

- [ ] **Step 1: Write `data.py` (provider dispatch — copy hardware/data.py shape)**

```python
"""SWAP SURFACE — skew-check provider selection.

Routes import only this module. Phase-specific wiring lives in
`providers/mock.py` (fixture) or `providers/office.py` (real stats).
"""

import os
from typing import Literal

from back_dev_home._runtime.env import is_cloud
from back_dev_home.ebeam.hitachi.skew.contracts import SkewCheckPayload
from back_dev_home.ebeam.hitachi.skew.providers import mock, office

ProviderKey = Literal["mock", "office"]


def _provider_key() -> ProviderKey:
    raw = os.environ.get("SKEWNONO_SKEW_PROVIDER", "").strip().lower()
    if raw in {"mock", "office"}:
        return raw  # type: ignore[return-value]
    return "office" if is_cloud() else "mock"


def get_skew_check(
    tool_slug: str,
    fab_id: str,
    recipe_id: str | None,
) -> SkewCheckPayload:
    provider = office if _provider_key() == "office" else mock
    return provider.get_skew_check(tool_slug, fab_id, recipe_id)
```

- [ ] **Step 2: Write `routes.py` (copy hardware/routes.py validation pattern)**

```python
from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import VALID_TOOL_SLUGS
from back_dev_home.ebeam.hitachi.skew.data import get_skew_check

bp = Blueprint("ebeam_skew", __name__)


def _arg(name: str) -> str | None:
    raw = (request.args.get(name) or "").strip()
    return raw or None


@bp.get("/<tool_slug>/skew/check")
def skew_check(tool_slug: str):
    if tool_slug not in VALID_TOOL_SLUGS:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    fab_id = _arg("fab_id")
    if fab_id is None:
        return jsonify({"error": "fab_id is required"}), 400
    payload = get_skew_check(tool_slug, fab_id, _arg("recipe_id"))
    return jsonify(payload)
```

- [ ] **Step 3: Write `__init__.py` (re-export `bp`)**

```python
from back_dev_home.ebeam.hitachi.skew.routes import bp

__all__ = ["bp"]
```

- [ ] **Step 4: Verify the Blueprint registers and the route resolves**

Run: `cd C:\Code\skewnono_v3_nuxt; python -c "from back_dev_home import create_app; c = create_app().test_client(); r = c.get('/api/cdsem/skew/check?fab_id=R3&recipe_id=X'); print(r.status_code, r.get_json()['available'], len(r.get_json()['occupied_cells']))"`
Expected: prints `200 True 3`.

- [ ] **Step 5: Verify validation paths**

Run: `cd C:\Code\skewnono_v3_nuxt; python -c "from back_dev_home import create_app; c = create_app().test_client(); print(c.get('/api/foo/skew/check?fab_id=R3').status_code, c.get('/api/cdsem/skew/check').status_code)"`
Expected: prints `400 400`.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/ebeam/hitachi/skew/data.py back_dev_home/ebeam/hitachi/skew/routes.py back_dev_home/ebeam/hitachi/skew/__init__.py
git commit -m "feat(skew): add /api/<tool_slug>/skew/check route + swap surface"
```

---

## Slice 2 — The N배화 grouping algorithm (client-side, full TDD)

This is the analytical core. It is pure and deterministic, so it gets red-green-refactor with `node:test`. All grouping logic lives here; components only render its output.

### Task 5: Types + adjacency (TTTM pairs) — TDD

**Files:**
- Create: `app/utils/skewGrouping.ts`
- Test: `app/utils/skewGrouping.test.ts`

- [ ] **Step 1: Write the failing test for `buildAdjacency`**

```ts
// Pure-logic tests — run with: npm test  (node --test, Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildAdjacency, type SkewMatrix } from './skewGrouping.ts'

const m: SkewMatrix = {
  tools: ['A', 'B', 'C'],
  values: [
    [0, 0.02, 0.12],
    [0.02, 0, 0.10],
    [0.12, 0.10, 0],
  ],
}

test('buildAdjacency: pairs <= tolerance are TTTM, diagonal false, null not TTTM', () => {
  const adj = buildAdjacency(m, 0.05)
  assert.deepEqual(adj, [
    [false, true, false],
    [true, false, false],
    [false, false, false],
  ])
})

test('buildAdjacency: null pair is never TTTM', () => {
  const withNull: SkewMatrix = { tools: ['A', 'B'], values: [[0, null], [null, 0]] }
  assert.deepEqual(buildAdjacency(withNull, 0.2), [[false, false], [false, false]])
})
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm test`
Expected: FAIL — `Cannot find module './skewGrouping.ts'` (or export missing).

- [ ] **Step 3: Implement types + `buildAdjacency`**

```ts
// Pure, dependency-free skew-grouping engine. The server sends raw pairwise
// skew matrices; the client computes N배화 (= maximal cliques) at a tolerance.

export type ToleranceNm = number

export interface SkewMatrix {
  tools: string[]
  // Symmetric, diagonal 0. null = the pair has no data (never TTTM).
  values: (number | null)[][]
}

export type Confidence = 'High' | 'Med' | 'Low'
export type Tier = 'direct' | 'predicted'

// Two tools are mutually TTTM when their pairwise skew is <= tolerance.
export function buildAdjacency(matrix: SkewMatrix, tolerance: ToleranceNm): boolean[][] {
  const n = matrix.tools.length
  const adj: boolean[][] = Array.from({ length: n }, () => Array<boolean>(n).fill(false))
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const v = matrix.values[i]?.[j]
      const tttm = v !== null && v !== undefined && v <= tolerance
      adj[i]![j] = tttm
      adj[j]![i] = tttm
    }
  }
  return adj
}
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm test`
Expected: PASS (both `buildAdjacency` tests).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/skewGrouping.ts front-dev-home/app/utils/skewGrouping.test.ts
git commit -m "feat(skew): TTTM adjacency from pairwise skew matrix (TDD)"
```

---

### Task 6: Maximal cliques (Bron–Kerbosch) — TDD

**Files:**
- Modify: `app/utils/skewGrouping.ts`
- Modify: `app/utils/skewGrouping.test.ts`

The spec (§3.3) mandates **clique** grouping, not transitive: if A·B and B·C are TTTM but A·C is not, `{A,B,C}` is NOT a group. Bron–Kerbosch enumerates maximal cliques.

- [ ] **Step 1: Add the failing test for `maximalCliques`**

```ts
import { maximalCliques } from './skewGrouping.ts'

test('maximalCliques: a TTTM triangle is one clique', () => {
  const adj = [
    [false, true, true],
    [true, false, true],
    [true, true, false],
  ]
  assert.deepEqual(maximalCliques(adj), [[0, 1, 2]])
})

test('maximalCliques: chain A-B-C without A-C yields two pairs, never the triple', () => {
  const adj = [
    [false, true, false],
    [true, false, true],
    [false, true, false],
  ]
  const cliques = maximalCliques(adj).map(c => c.join(',')).sort()
  assert.deepEqual(cliques, ['0,1', '1,2'])
})

test('maximalCliques: isolated vertex is its own clique', () => {
  const adj = [
    [false, true, false],
    [true, false, false],
    [false, false, false],
  ]
  const cliques = maximalCliques(adj).map(c => c.join(',')).sort()
  assert.deepEqual(cliques, ['0,1', '2'])
})
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm test`
Expected: FAIL — `maximalCliques` is not exported.

- [ ] **Step 3: Implement `maximalCliques`**

```ts
// Bron–Kerbosch (no pivot — fleets are small, ~5-12 tools). Returns every
// MAXIMAL clique, including singletons (a tool TTTM with nobody).
export function maximalCliques(adj: boolean[][]): number[][] {
  const n = adj.length
  const all = new Set<number>(Array.from({ length: n }, (_, i) => i))
  const out: number[][] = []

  const neighbors = (v: number): Set<number> => {
    const s = new Set<number>()
    for (let u = 0; u < n; u++) if (adj[v]![u]) s.add(u)
    return s
  }

  const bk = (R: Set<number>, P: Set<number>, X: Set<number>) => {
    if (P.size === 0 && X.size === 0) {
      out.push([...R].sort((a, b) => a - b))
      return
    }
    for (const v of [...P]) {
      const Nv = neighbors(v)
      bk(
        new Set([...R, v]),
        new Set([...P].filter(u => Nv.has(u))),
        new Set([...X].filter(u => Nv.has(u))),
      )
      P.delete(v)
      X.add(v)
    }
  }

  bk(new Set(), all, new Set())
  return out
}
```

- [ ] **Step 4: Run to confirm pass**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm test`
Expected: PASS (all clique tests, plus Task 5 tests still green).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/skewGrouping.ts front-dev-home/app/utils/skewGrouping.test.ts
git commit -m "feat(skew): maximal-clique enumeration (Bron-Kerbosch) for N배화 (TDD)"
```

---

### Task 7: Cell-intersection grouping + primary pick (tiebreakers) — TDD

**Files:**
- Modify: `app/utils/skewGrouping.ts`
- Modify: `app/utils/skewGrouping.test.ts`

Implements spec §4.2-4: intersect TTTM across **all occupied cells** (a pair is TTTM only if ≤tolerance in every cell that has data), enumerate maximal cliques = candidate N배화 groups, then pick the primary by **max N → smaller weakest-pair skew → higher confidence**. A group inherits the **weakest** confidence among contributing cells (§4.2-5).

- [ ] **Step 1: Add the failing tests**

```ts
import { groupFromCells, pickPrimary, type GroupCell, type NbaGroup } from './skewGrouping.ts'

const CONF_DIRECT = { tier: 'direct' as Tier, confidence: 'High' as Confidence }

// Two direct cells whose intersection makes {A,B,D} the only triangle at tol=0.05.
const cellsFixture: GroupCell[] = [
  {
    ...CONF_DIRECT,
    matrix: {
      tools: ['A', 'B', 'C', 'D', 'E'],
      values: [
        [0, 0.02, 0.12, 0.03, 0.18],
        [0.02, 0, 0.10, 0.04, 0.16],
        [0.12, 0.10, 0, 0.11, 0.08],
        [0.03, 0.04, 0.11, 0, 0.15],
        [0.18, 0.16, 0.08, 0.15, 0],
      ],
    },
  },
  {
    ...CONF_DIRECT,
    matrix: {
      tools: ['A', 'B', 'C', 'D', 'E'],
      values: [
        [0, 0.03, 0.14, 0.04, 0.20],
        [0.03, 0, 0.13, 0.045, 0.19],
        [0.14, 0.13, 0, 0.12, 0.09],
        [0.04, 0.045, 0.12, 0, 0.17],
        [0.20, 0.19, 0.09, 0.17, 0],
      ],
    },
  },
]

test('groupFromCells: intersection yields {A,B,D} as the max clique at 0.05', () => {
  const groups = groupFromCells(cellsFixture, 0.05)
  const top = groups.map(g => g.tools.join(',')).sort()
  assert.ok(top.includes('A,B,D'))
  const abd = groups.find(g => g.tools.join(',') === 'A,B,D')!
  assert.equal(abd.n, 3)
  // weakest pair across both cells for A,B,D = max(A-B,A-D,B-D) = 0.045 (cell 2 B-D)
  assert.equal(abd.weakestPairSkew, 0.045)
  assert.equal(abd.confidence, 'High')
})

test('pickPrimary: larger N wins', () => {
  const g: NbaGroup[] = [
    { tools: ['A', 'B'], n: 2, weakestPairSkew: 0.01, confidence: 'High', tier: 'direct' },
    { tools: ['A', 'B', 'D'], n: 3, weakestPairSkew: 0.045, confidence: 'High', tier: 'direct' },
  ]
  assert.equal(pickPrimary(g)!.tools.join(','), 'A,B,D')
})

test('pickPrimary: equal N breaks on smaller weakest-pair skew, then higher confidence', () => {
  const g: NbaGroup[] = [
    { tools: ['A', 'B', 'C'], n: 3, weakestPairSkew: 0.04, confidence: 'Low', tier: 'predicted' },
    { tools: ['A', 'B', 'D'], n: 3, weakestPairSkew: 0.03, confidence: 'Low', tier: 'predicted' },
    { tools: ['A', 'B', 'E'], n: 3, weakestPairSkew: 0.03, confidence: 'High', tier: 'direct' },
  ]
  // tie on N(3); 0.03 beats 0.04; among the two 0.03s, High beats Low
  assert.equal(pickPrimary(g)!.tools.join(','), 'A,B,E')
})
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm test`
Expected: FAIL — `groupFromCells` / `pickPrimary` not exported.

- [ ] **Step 3: Implement the intersection grouping + primary pick**

```ts
export interface GroupCell {
  tier: Tier
  confidence: Confidence
  matrix: SkewMatrix // use direct_skew_matrix ?? predicted_skew_matrix at the call site
}

export interface NbaGroup {
  tools: string[]
  n: number
  weakestPairSkew: number // max pairwise skew inside the group, across all cells
  confidence: Confidence // weakest among contributing cells
  tier: Tier // 'predicted' if any contributing cell is predicted
}

const CONF_RANK: Record<Confidence, number> = { High: 3, Med: 2, Low: 1 }

// Weakest (lowest) confidence / predicted-dominant tier across cells (§4.2-5).
function inheritConfidence(cells: GroupCell[]): { confidence: Confidence; tier: Tier } {
  let confidence: Confidence = 'High'
  let tier: Tier = 'direct'
  for (const c of cells) {
    if (CONF_RANK[c.confidence] < CONF_RANK[confidence]) confidence = c.confidence
    if (c.tier === 'predicted') tier = 'predicted'
  }
  return { confidence, tier }
}

export function groupFromCells(cells: GroupCell[], tolerance: ToleranceNm): NbaGroup[] {
  if (cells.length === 0) return []
  const tools = cells[0]!.matrix.tools
  const n = tools.length

  // Intersect adjacency: a pair is TTTM only if <= tolerance in EVERY cell.
  const inter: boolean[][] = Array.from({ length: n }, () => Array<boolean>(n).fill(true))
  for (let i = 0; i < n; i++) inter[i]![i] = false
  for (const cell of cells) {
    const adj = buildAdjacency(cell.matrix, tolerance)
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (!adj[i]![j]) inter[i]![j] = false
  }

  const { confidence, tier } = inheritConfidence(cells)

  // Worst (max) pairwise skew across all cells, for a given index pair.
  const worst = (i: number, j: number): number => {
    let w = 0
    for (const cell of cells) {
      const v = cell.matrix.values[i]?.[j]
      if (v !== null && v !== undefined) w = Math.max(w, v)
    }
    return w
  }

  return maximalCliques(inter).map((clique): NbaGroup => {
    let weakest = 0
    for (let a = 0; a < clique.length; a++)
      for (let b = a + 1; b < clique.length; b++)
        weakest = Math.max(weakest, worst(clique[a]!, clique[b]!))
    return {
      tools: clique.map(idx => tools[idx]!),
      n: clique.length,
      weakestPairSkew: Number(weakest.toFixed(6)),
      confidence,
      tier,
    }
  })
}

// §4.2-4: max N → smaller weakest-pair skew → higher confidence.
export function pickPrimary(groups: NbaGroup[]): NbaGroup | null {
  if (groups.length === 0) return null
  return [...groups].sort((a, b) => {
    if (b.n !== a.n) return b.n - a.n
    if (a.weakestPairSkew !== b.weakestPairSkew) return a.weakestPairSkew - b.weakestPairSkew
    return CONF_RANK[b.confidence] - CONF_RANK[a.confidence]
  })[0]!
}
```

- [ ] **Step 4: Run to confirm pass**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm test`
Expected: PASS (all Slice-2 tests green).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/skewGrouping.ts front-dev-home/app/utils/skewGrouping.test.ts
git commit -m "feat(skew): cell-intersection N배화 grouping + tiebreaker pick (TDD)"
```

---

## Slice 3 — Wiring: feature registration, page, composable

### Task 8: Register the `skew-check` feature slug + nav gating

**Files:**
- Modify: `app/utils/features.ts:4-12`
- Modify: `app/composables/useNavigation.ts:10-21`

- [ ] **Step 1: Add `'skew-check'` to `FEATURE_SLUGS`**

In `app/utils/features.ts`, change the array:

```ts
export const FEATURE_SLUGS = [
  'storage',
  'recipe-search',
  'recipe-tat',
  'fail-issue',
  'hardware',
  'device-statistics',
  'skewvoir',
  'skew-check'
] as const
```

- [ ] **Step 2: Gate `skew-check` to CD-SEM in `useNavigation.ts`**

In `featureEnabledForToolType`, add a branch (skew-check is CD-SEM-only per spec §7.1):

```ts
  const featureEnabledForToolType = (feature: string, toolType: ToolType) => {
    if (
      feature === 'storage'
      || feature === 'recipe-search'
      || feature === 'recipe-tat'
      || feature === 'fail-issue'
      || feature === 'hardware'
      || feature === 'skewvoir'
    ) return toolType === 'cd-sem' || toolType === 'hv-sem'
    if (feature === 'device-statistics') return toolType === 'cd-sem'
    if (feature === 'skew-check') return toolType === 'cd-sem'
    return false
  }
```

- [ ] **Step 3: Typecheck**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm run typecheck`
Expected: no new errors referencing `features.ts` or `useNavigation.ts`.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/utils/features.ts front-dev-home/app/composables/useNavigation.ts
git commit -m "feat(skew): register skew-check feature slug, gate to cd-sem"
```

---

### Task 9: API composable + TS payload types

**Files:**
- Create: `app/composables/useSkewCheckApi.ts`

- [ ] **Step 1: Write the composable (mirror `useAfmDetailApi.ts`)**

```ts
import { joinApiPath } from '~/utils/apiPath'
import type { SkewMatrix, Confidence, Tier } from '~/utils/skewGrouping'

export interface ToolRef { eqp_id: string; label: string }

export interface CellSkew {
  cell_id: string
  beam_condition: string
  axis: 'X' | 'Y'
  cd_band: string
  mdc_epoch: string
  tier: Tier
  confidence: Confidence
  labels: string[]
  direct_skew_matrix: SkewMatrix | null
  predicted_skew_matrix: SkewMatrix | null
}

export interface ProductionCorroboration {
  level: 'high' | 'mid' | 'low'
  note: string
  detail: { pair: string; overlap: number }[]
}

export interface FleetToday {
  matrix: SkewMatrix
  consensus_deviation: { eqp_id: string; deviation: number }[]
}

export interface TrendPoint { eqp_id: string; date: string; skew: number }
export interface EpochMarker {
  eqp_id: string; date: string; kind: 'hard' | 'soft'; mdc_changed: boolean; label: string
}
export interface MdcHistoryEntry {
  eqp_id: string; beam_condition: string; axis: 'X' | 'Y'
  date: string; old_value: number; new_value: number
}

export interface SkewCheckPayload {
  tool_slug: string
  fab_id: string
  recipe_id: string | null
  available: boolean
  fetched_at: string
  summary: string
  tools: ToolRef[]
  current_tolerance: number
  tolerance_range: { min: number; max: number; step: number }
  occupied_cells: CellSkew[]
  production_corroboration: ProductionCorroboration
  fleet_today: FleetToday
  trend: TrendPoint[]
  epoch_markers: EpochMarker[]
  mdc_history: MdcHistoryEntry[]
}

// Frontend tool-type 'cd-sem' maps to backend tool_slug 'cdsem'.
const toSlug = (toolType: string) => toolType.replace('-', '')

export const useSkewCheckApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchSkewCheck = (toolType: string, fabId: string, recipeId?: string) =>
    $fetch<SkewCheckPayload>(
      joinApiPath(base, `/${toSlug(toolType)}/skew/check`),
      { query: { fab_id: fabId, ...(recipeId ? { recipe_id: recipeId } : {}) } }
    )

  const useSkewCheck = (toolType: string, fabId: string, recipeId?: string) =>
    useAsyncData(
      `skew-check:${toolType}:${fabId}:${recipeId ?? 'all'}`,
      () => fetchSkewCheck(toolType, fabId, recipeId)
    )

  return { fetchSkewCheck, useSkewCheck }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm run typecheck`
Expected: no errors in `useSkewCheckApi.ts`.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/composables/useSkewCheckApi.ts
git commit -m "feat(skew): add useSkewCheckApi composable + payload types"
```

---

### Task 10: Page wrapper

**Files:**
- Create: `app/pages/ebeam/cd-sem/[fab]/skew-check.vue`

- [ ] **Step 1: Write the page (copy `hardware.vue`)**

Per global rule, `<template>` first then `<script setup>`:

```vue
<template>
  <EbeamSkewCheckView
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

- [ ] **Step 2: Commit (view component arrives in Task 11; route will 404 its component until then)**

```bash
git add front-dev-home/app/pages/ebeam/cd-sem/[fab]/skew-check.vue
git commit -m "feat(skew): add skew-check page wrapper"
```

---

## Slice 4 — Dashboard ① finder (primary deliverable)

### Task 11: Orchestrator view + recommendation card + tolerance knob

**Files:**
- Create: `app/components/ebeam/skewCheck/ToleranceKnob.vue`
- Create: `app/components/ebeam/skewCheck/RecommendationCard.vue`
- Create: `app/components/ebeam/SkewCheckView.vue`

- [ ] **Step 1: Write `ToleranceKnob.vue` (`<EbeamSkewCheckToleranceKnob>`)**

```vue
<template>
  <div class="flex items-center gap-3">
    <label class="text-sm text-(--sk-ink-muted)">tolerance</label>
    <input
      type="range"
      :min="range.min"
      :max="range.max"
      :step="range.step"
      :value="modelValue"
      class="accent-(--sk-accent)"
      @input="onInput"
    >
    <span class="tabular-nums text-sm font-medium text-(--sk-ink)">
      {{ modelValue.toFixed(3) }} nm
    </span>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue: number
  range: { min: number; max: number; step: number }
}>()
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const onInput = (e: Event) => {
  emit('update:modelValue', Number((e.target as HTMLInputElement).value))
}
// reference props.range to satisfy lints if template tree-shakes
void props
</script>
```

- [ ] **Step 2: Write `RecommendationCard.vue` (`<EbeamSkewCheckRecommendationCard>`)**

```vue
<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">1차 추천 (최대 N배화)</p>

    <div v-if="primary" class="mt-2">
      <div class="flex items-center gap-2 flex-wrap">
        <span
          v-for="t in primary.tools"
          :key="t"
          class="px-2.5 py-1 rounded-lg text-sm font-medium"
          :style="{ background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)' }"
        >{{ labelFor(t) }}</span>
        <span class="ml-1 text-sm text-(--sk-ink-muted)">N = {{ primary.n }}</span>
      </div>
      <p class="mt-2 text-sm text-(--sk-ink-muted)">
        최약 장비쌍 스큐 {{ primary.weakestPairSkew.toFixed(3) }} nm ·
        신뢰도 <span :style="{ color: confColor }">{{ primary.confidence }}</span>
        <span v-if="primary.tier === 'predicted'"> · 예측 tier</span>
      </p>
    </div>

    <p v-else class="mt-2 text-sm text-(--sk-bad)">
      현재 tolerance에서 모든 점유 셀을 동시에 만족하는 N배화 그룹이 없습니다.
    </p>

    <div v-if="others.length" class="mt-4">
      <p class="text-xs text-(--sk-ink-subtle)">다른 후보 그룹</p>
      <div class="mt-1 flex flex-wrap gap-2">
        <span
          v-for="(g, i) in others"
          :key="i"
          class="px-2 py-0.5 rounded-md text-xs text-(--sk-ink-muted)"
          :style="{ background: 'var(--sk-muted-surface)' }"
        >{{ g.tools.map(labelFor).join(' · ') }} (N={{ g.n }})</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { NbaGroup } from '~/utils/skewGrouping'
import type { ToolRef } from '~/composables/useSkewCheckApi'

const props = defineProps<{
  primary: NbaGroup | null
  others: NbaGroup[]
  tools: ToolRef[]
}>()

const labelFor = (eqp: string) =>
  props.tools.find(t => t.eqp_id === eqp)?.label ?? eqp

const confColor = computed(() => {
  if (!props.primary) return 'var(--sk-ink)'
  return props.primary.confidence === 'High'
    ? 'var(--sk-ok)'
    : props.primary.confidence === 'Low'
      ? 'var(--sk-bad)'
      : 'var(--sk-accent)'
})
</script>
```

- [ ] **Step 3: Write `SkewCheckView.vue` (`<EbeamSkewCheckView>`) — wires data → algorithm → cards**

```vue
<template>
  <div class="space-y-4">
    <EbeamMetaBar
      :eyebrow="`CD-SEM · ${fab}`"
      title="장비간 스큐 관리"
      subtitle="Recipe가 점유하는 셀에서 서로 잘 맞는(N배화) 측정 장비 조합을 추천합니다."
      cadence="1주 윈도우"
      :as-of="asOf"
      :stats="metaStats"
    />

    <div v-if="pending" class="text-sm text-(--sk-ink-muted)">불러오는 중…</div>
    <div v-else-if="!payload?.available" class="text-sm text-(--sk-bad)">
      {{ payload?.summary ?? '데이터가 없습니다.' }}
    </div>

    <template v-else>
      <div class="dashboard-surface rounded-2xl p-4">
        <EbeamSkewCheckToleranceKnob v-model="tolerance" :range="payload.tolerance_range" />
      </div>

      <EbeamSkewCheckRecommendationCard
        :primary="primary"
        :others="others"
        :tools="payload.tools"
      />

      <EbeamSkewCheckProductionChip :corroboration="payload.production_corroboration" />

      <EbeamSkewCheckPairMatrix
        :cells="payload.occupied_cells"
        :tools="payload.tools"
        :tolerance="tolerance"
      />

      <EbeamSkewCheckFleetStatus :fleet="payload.fleet_today" :tools="payload.tools" />
      <EbeamSkewCheckTrendChart :trend="payload.trend" :markers="payload.epoch_markers" />
      <EbeamSkewCheckMdcTimeline :history="payload.mdc_history" />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { groupFromCells, pickPrimary, type GroupCell, type NbaGroup } from '~/utils/skewGrouping'

const props = defineProps<{ fab: string; toolLabel: string; toolType: string }>()

const { useSkewCheck } = useSkewCheckApi()
const { data: payload, pending } = useSkewCheck(props.toolType, props.fab)

const tolerance = ref(0.05)
watch(payload, (p) => { if (p) tolerance.value = p.current_tolerance }, { immediate: true })

// occupied cells → GroupCell[] (direct matrix preferred, else predicted).
const groupCells = computed<GroupCell[]>(() =>
  (payload.value?.occupied_cells ?? [])
    .map((c) => {
      const matrix = c.direct_skew_matrix ?? c.predicted_skew_matrix
      return matrix ? { tier: c.tier, confidence: c.confidence, matrix } : null
    })
    .filter((c): c is GroupCell => c !== null)
)

const groups = computed<NbaGroup[]>(() =>
  groupFromCells(groupCells.value, tolerance.value).filter(g => g.n >= 2)
)
const primary = computed(() => pickPrimary(groups.value))
const others = computed(() =>
  groups.value.filter(g => g !== primary.value).sort((a, b) => b.n - a.n)
)

const asOf = computed(() => (payload.value?.fetched_at ?? '').replace('T', ' ').slice(0, 16))
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'tools', label: '함대', value: payload.value?.tools.length ?? 0, tone: 'neutral' },
  { key: 'cells', label: '점유 셀', value: payload.value?.occupied_cells.length ?? 0, tone: 'neutral' },
  { key: 'n', label: '최대 N배화', value: primary.value?.n ?? 0, tone: 'ok' }
])
</script>
```

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewCheck/ToleranceKnob.vue front-dev-home/app/components/ebeam/skewCheck/RecommendationCard.vue front-dev-home/app/components/ebeam/SkewCheckView.vue
git commit -m "feat(skew): finder orchestrator + recommendation card + tolerance knob"
```

> Note: the view references `EbeamSkewCheckProductionChip`, `PairMatrix`, `FleetStatus`, `TrendChart`, `MdcTimeline` which are created in Tasks 12-14. The page will not render until those exist; that is expected mid-slice. Do not run the page until Task 14.

---

### Task 12: Pairwise matrix heatmap + production chip

**Files:**
- Create: `app/components/ebeam/skewCheck/PairMatrix.vue`
- Create: `app/components/ebeam/skewCheck/ProductionChip.vue`

- [ ] **Step 1: Write `PairMatrix.vue` (`<EbeamSkewCheckPairMatrix>`) — per-cell heatmap, TTTM-highlighted**

```vue
<template>
  <div class="dashboard-surface rounded-2xl p-5 space-y-5">
    <p class="text-xs text-(--sk-ink-subtle)">장비쌍 스큐 행렬 (TTTM 근거 · 셀별)</p>

    <div v-for="cell in cells" :key="cell.cell_id" class="space-y-2">
      <div class="flex items-center gap-2 text-sm">
        <span class="font-medium text-(--sk-ink)">{{ cell.beam_condition }} · {{ cell.axis }} · {{ cell.cd_band }}nm</span>
        <span
          class="px-1.5 py-0.5 rounded text-xs"
          :style="tierStyle(cell.tier)"
        >{{ cell.tier === 'direct' ? '직접' : '예측' }} · {{ cell.confidence }}</span>
        <span v-for="l in cell.labels" :key="l" class="text-xs text-(--sk-ink-muted)">{{ l }}</span>
      </div>

      <div class="overflow-x-auto">
        <table class="border-collapse text-xs tabular-nums">
          <thead>
            <tr>
              <th class="p-1" />
              <th v-for="t in matrixOf(cell).tools" :key="t" class="p-1 text-(--sk-ink-muted) font-normal">
                {{ shortLabel(t) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in matrixOf(cell).values" :key="i">
              <th class="p-1 pr-2 text-right text-(--sk-ink-muted) font-normal">
                {{ shortLabel(matrixOf(cell).tools[i]!) }}
              </th>
              <td
                v-for="(v, j) in row"
                :key="j"
                class="p-1 text-center rounded"
                :style="cellStyle(v, i, j)"
                :title="pairTitle(cell, i, j, v)"
              >{{ i === j ? '—' : (v === null ? '·' : v.toFixed(3)) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CellSkew, ToolRef } from '~/composables/useSkewCheckApi'
import type { SkewMatrix } from '~/utils/skewGrouping'

const props = defineProps<{ cells: CellSkew[]; tools: ToolRef[]; tolerance: number }>()

const matrixOf = (cell: CellSkew): SkewMatrix =>
  (cell.direct_skew_matrix ?? cell.predicted_skew_matrix)!

const shortLabel = (eqp: string) =>
  props.tools.find(t => t.eqp_id === eqp)?.label?.replace('CD-SEM ', '') ?? eqp

const tierStyle = (tier: string) =>
  tier === 'direct'
    ? { background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)' }
    : { background: 'var(--sk-muted-surface)', color: 'var(--sk-ink-muted)' }

const cellStyle = (v: number | null, i: number, j: number) => {
  if (i === j || v === null) return { color: 'var(--sk-ink-subtle)' }
  const tttm = v <= props.tolerance
  return tttm
    ? { background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)', fontWeight: 600 }
    : { background: 'var(--sk-bad-soft)', color: 'var(--sk-bad)' }
}

const pairTitle = (cell: CellSkew, i: number, j: number, v: number | null) => {
  if (i === j || v === null) return ''
  const m = matrixOf(cell)
  const state = v <= props.tolerance ? 'TTTM' : 'tolerance 초과'
  return `${m.tools[i]} · ${m.tools[j]} = ${v.toFixed(3)} nm (${state})`
}
</script>
```

- [ ] **Step 2: Write `ProductionChip.vue` (`<EbeamSkewCheckProductionChip>`) — 참고 summary chip + drilldown**

```vue
<template>
  <div class="dashboard-surface rounded-2xl p-4">
    <button class="flex items-center gap-2 w-full text-left" @click="open = !open">
      <span class="text-xs text-(--sk-ink-subtle)">양산 정합도 (참고)</span>
      <span class="px-2 py-0.5 rounded text-xs font-medium" :style="levelStyle">
        {{ levelLabel }}
      </span>
      <span class="text-xs text-(--sk-ink-muted)">{{ corroboration.note }}</span>
      <UIcon
        :name="open ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
        class="ml-auto text-(--sk-ink-muted)"
      />
    </button>

    <div v-if="open" class="mt-3 space-y-1">
      <div
        v-for="row in corroboration.detail"
        :key="row.pair"
        class="flex items-center gap-2 text-xs"
      >
        <span class="w-28 text-(--sk-ink-muted)">{{ row.pair }}</span>
        <div class="flex-1 h-2 rounded" :style="{ background: 'var(--sk-muted-surface)' }">
          <div class="h-2 rounded" :style="{ width: `${row.overlap * 100}%`, background: 'var(--sk-accent)' }" />
        </div>
        <span class="tabular-nums text-(--sk-ink)">{{ (row.overlap * 100).toFixed(0) }}%</span>
      </div>
      <p class="pt-1 text-[11px] text-(--sk-ink-subtle)">
        다른 Wafer 분포 중첩이라 Wafer 산포와 엉켜 N배화 판정에는 쓰지 않습니다.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ProductionCorroboration } from '~/composables/useSkewCheckApi'

const props = defineProps<{ corroboration: ProductionCorroboration }>()
const open = ref(false)

const levelLabel = computed(
  () => ({ high: '높음', mid: '중간', low: '낮음' }[props.corroboration.level])
)
const levelStyle = computed(() => {
  const l = props.corroboration.level
  if (l === 'high') return { background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)' }
  if (l === 'low') return { background: 'var(--sk-bad-soft)', color: 'var(--sk-bad)' }
  return { background: 'var(--sk-accent-tint)', color: 'var(--sk-accent)' }
})
</script>
```

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewCheck/PairMatrix.vue front-dev-home/app/components/ebeam/skewCheck/ProductionChip.vue
git commit -m "feat(skew): pairwise skew heatmap + production 참고 chip"
```

---

## Slice 5 — Dashboards ②③④

### Task 13: Fleet status (② today's matrix + consensus deviation)

**Files:**
- Create: `app/components/ebeam/skewCheck/FleetStatus.vue`

- [ ] **Step 1: Write `FleetStatus.vue` (`<EbeamSkewCheckFleetStatus>`)**

```vue
<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">오늘 함대 skew 현황</p>
    <div class="mt-3 space-y-2">
      <div
        v-for="d in sorted"
        :key="d.eqp_id"
        class="flex items-center gap-3 text-sm"
      >
        <span class="w-24 text-(--sk-ink-muted)">{{ labelFor(d.eqp_id) }}</span>
        <div class="flex-1 relative h-4">
          <div class="absolute inset-y-0 left-1/2 w-px" :style="{ background: 'var(--sk-border)' }" />
          <div
            class="absolute inset-y-0.5 rounded"
            :style="barStyle(d.deviation)"
          />
        </div>
        <span
          class="w-16 text-right tabular-nums"
          :style="{ color: Math.abs(d.deviation) > 0.05 ? 'var(--sk-bad)' : 'var(--sk-ink)' }"
        >{{ d.deviation >= 0 ? '+' : '' }}{{ d.deviation.toFixed(3) }}</span>
      </div>
    </div>
    <p class="mt-2 text-[11px] text-(--sk-ink-subtle)">
      잔차 = tool − consensus(기준값). 0 = 함대 합의와 일치.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { FleetToday, ToolRef } from '~/composables/useSkewCheckApi'

const props = defineProps<{ fleet: FleetToday; tools: ToolRef[] }>()

const labelFor = (eqp: string) => props.tools.find(t => t.eqp_id === eqp)?.label ?? eqp

const maxAbs = computed(() =>
  Math.max(0.05, ...props.fleet.consensus_deviation.map(d => Math.abs(d.deviation)))
)
const sorted = computed(() =>
  [...props.fleet.consensus_deviation].sort((a, b) => a.deviation - b.deviation)
)

// Bar grows from the center line toward the sign direction.
const barStyle = (dev: number) => {
  const half = (Math.abs(dev) / maxAbs.value) * 50
  const ok = Math.abs(dev) <= 0.05
  const bg = ok ? 'var(--sk-ok)' : 'var(--sk-bad)'
  return dev >= 0
    ? { left: '50%', width: `${half}%`, background: bg }
    : { right: '50%', width: `${half}%`, background: bg }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewCheck/FleetStatus.vue
git commit -m "feat(skew): fleet status — consensus deviation diverging bars"
```

---

### Task 14: Trend + epoch markers (③, ECharts) and MDC timeline (④)

**Files:**
- Create: `app/components/ebeam/skewCheck/TrendChart.vue`
- Create: `app/components/ebeam/skewCheck/MdcTimeline.vue`

ECharts 6 is already a dependency. Mirror existing usage (charts are rendered in `app/components/ebeam/hardware/BsmRadarChart.vue` — check it for the project's init/dispose pattern and reuse it).

- [ ] **Step 1: Write `TrendChart.vue` (`<EbeamSkewCheckTrendChart>`)**

```vue
<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">장비별 skew 트렌드 · BM/PM 마커</p>
    <div ref="el" class="mt-3 h-64 w-full" />
    <div class="mt-2 flex flex-wrap gap-3 text-[11px] text-(--sk-ink-muted)">
      <span>● hard = MDC 변경(epoch 리셋)</span>
      <span>○ soft = BM/PM(MDC 불변)</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import type { TrendPoint, EpochMarker } from '~/composables/useSkewCheckApi'

const props = defineProps<{ trend: TrendPoint[]; markers: EpochMarker[] }>()
const el = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

const byTool = computed(() => {
  const map = new Map<string, TrendPoint[]>()
  for (const p of props.trend) {
    if (!map.has(p.eqp_id)) map.set(p.eqp_id, [])
    map.get(p.eqp_id)!.push(p)
  }
  return map
})

const buildOption = (): echarts.EChartsOption => {
  const dates = [...new Set(props.trend.map(p => p.date))].sort()
  const series: echarts.SeriesOption[] = [...byTool.value.entries()].map(([eqp, pts]) => ({
    name: eqp,
    type: 'line',
    showSymbol: true,
    data: dates.map(d => pts.find(p => p.date === d)?.skew ?? null),
    markPoint: {
      symbolSize: 14,
      data: props.markers
        .filter(m => m.eqp_id === eqp)
        .map(m => ({
          xAxis: m.date,
          yAxis: pts.find(p => p.date === m.date)?.skew ?? 0,
          itemStyle: { color: m.kind === 'hard' ? '#b91c1c' : 'transparent', borderColor: '#b45309', borderWidth: 1 },
          value: m.kind === 'hard' ? 'PM' : 'BM'
        }))
    }
  }))
  return {
    grid: { top: 16, right: 16, bottom: 28, left: 40 },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, type: 'scroll' },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'skew (nm)', scale: true },
    series
  }
}

const render = () => {
  if (!el.value) return
  chart ??= echarts.init(el.value)
  chart.setOption(buildOption(), true)
}

onMounted(render)
watch(() => props.trend, render, { deep: true })
onBeforeUnmount(() => { chart?.dispose(); chart = null })
</script>
```

- [ ] **Step 2: Write `MdcTimeline.vue` (`<EbeamSkewCheckMdcTimeline>`)**

```vue
<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">MDC 이력 (빔 조건 × 축)</p>
    <table v-if="history.length" class="mt-3 w-full text-sm">
      <thead>
        <tr class="text-(--sk-ink-muted) text-xs">
          <th class="text-left font-normal py-1">날짜</th>
          <th class="text-left font-normal py-1">장비</th>
          <th class="text-left font-normal py-1">빔·축</th>
          <th class="text-right font-normal py-1">이전</th>
          <th class="text-right font-normal py-1">이후</th>
          <th class="text-right font-normal py-1">Δ</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(h, i) in sorted" :key="i" class="border-t" :style="{ borderColor: 'var(--sk-border-soft)' }">
          <td class="py-1 tabular-nums text-(--sk-ink-muted)">{{ h.date }}</td>
          <td class="py-1 text-(--sk-ink)">{{ h.eqp_id }}</td>
          <td class="py-1 text-(--sk-ink-muted)">{{ h.beam_condition }} · {{ h.axis }}</td>
          <td class="py-1 text-right tabular-nums text-(--sk-ink-muted)">{{ h.old_value.toFixed(4) }}</td>
          <td class="py-1 text-right tabular-nums text-(--sk-ink)">{{ h.new_value.toFixed(4) }}</td>
          <td
            class="py-1 text-right tabular-nums"
            :style="{ color: h.new_value - h.old_value >= 0 ? 'var(--sk-ok)' : 'var(--sk-bad)' }"
          >{{ (h.new_value - h.old_value >= 0 ? '+' : '') + (h.new_value - h.old_value).toFixed(4) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="mt-3 text-sm text-(--sk-ink-muted)">기록된 MDC 변경이 없습니다.</p>
  </div>
</template>

<script setup lang="ts">
import type { MdcHistoryEntry } from '~/composables/useSkewCheckApi'

const props = defineProps<{ history: MdcHistoryEntry[] }>()
const sorted = computed(() => [...props.history].sort((a, b) => b.date.localeCompare(a.date)))
</script>
```

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewCheck/TrendChart.vue front-dev-home/app/components/ebeam/skewCheck/MdcTimeline.vue
git commit -m "feat(skew): skew trend chart (epoch markers) + MDC history timeline"
```

---

### Task 15: End-to-end verification + lint/typecheck

**Files:** none (verification only)

- [ ] **Step 1: Confirm the full unit suite is green**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm test`
Expected: all `skewGrouping.test.ts` tests pass (PASS lines, 0 fail).

- [ ] **Step 2: Typecheck + lint**

Run: `cd C:\Code\skewnono_v3_nuxt\front-dev-home; npm run typecheck; npm run lint`
Expected: no errors in any `skew`/`skewCheck` file.

- [ ] **Step 3: Backend smoke against the running server**

With Flask running on :5050 (PyCharm) and Nuxt on :3000, verify the proxy path end-to-end:

Run (PowerShell): `Invoke-RestMethod 'http://localhost:3000/api/cdsem/skew/check?fab_id=R3' | Select-Object available, current_tolerance, @{n='cells';e={$_.occupied_cells.Count}}`
Expected: `available=True`, `current_tolerance=0.05`, `cells=3`.

- [ ] **Step 4: Visual check (Playwright MCP) — primary answer + knob reactivity**

Navigate to `http://localhost:3000/ebeam/cd-sem/r3/skew-check`. Confirm:
- Recommendation card shows the **CD-SEM 01 · 02 · 04** group with **N = 3** at default tolerance 0.05.
- Dragging the tolerance knob **down to ~0.025** shrinks the group (EQP04's worst pair 0.045 drops out → N=2); dragging **up past 0.08** grows it. No network refetch fires (grouping is client-side).
- Pair matrix highlights TTTM cells green / over-tolerance red; production chip expands to the 3 overlap rows with `TTTM 미반영`.

Save screenshot: `browser_take_screenshot` with `filename: ".playwright-mcp/screenshots/skew-check-finder.png"`.

- [ ] **Step 5: Markdown lint (this plan + any docs touched)**

Run: `cd C:\Code\skewnono_v3_nuxt; npm run lint:md`
Expected: no errors.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test(skew): verify finder e2e — grouping, knob reactivity, contract"
```

---

## Self-review against the spec

**Spec coverage:**
- §3.1 3-tier signals → contract `CellSkew.tier` (`direct`/`predicted`) + `production_corroboration` (참고); never merged into one score. ✅ (Tasks 1, 11, 12)
- §3.2 pipeline (consensus/residual/skew/epoch) → served pre-computed by mock (`fleet_today.consensus_deviation`, `trend`, `epoch_markers`); office computes for real. ✅ (Task 2)
- §3.3 TTTM/N배화 = clique, **client-side**, tolerance 0.05 / 0.01–0.20 / step 0.005 → `skewGrouping.ts` + `ToleranceKnob`. ✅ (Tasks 5–7, 11)
- §4.2 cell-intersection → max N → tiebreakers → `groupFromCells` + `pickPrimary`. ✅ (Task 7)
- §4.2-5 group inherits weakest confidence → `inheritConfidence`. ✅ (Task 7)
- §4.3 특수각/참고 → `labels` flags rendered in PairMatrix; `ProductionChip` with `TTTM 미반영`. ✅ (Tasks 12)
- §5 four dashboard sections → finder / fleet / trend+epoch / MDC. ✅ (Tasks 11–14)
- §6 swap surface (contracts/data/mock/office, fixtures, raw matrices, client grouping, reuse hardware data) → Slice 1. ✅ (BSM/MDC reuse is honored by serving `mdc_history`/`epoch_markers` shapes that office wires from the existing hardware feature — noted for office swap.)
- §7.1 X/Y only, both fabs via data density → fixture uses X/Y cells; gating is per-tool, fab via route param. ✅

**Placeholder scan:** no `TODO`/`TBD`; every code step shows complete code; every run step shows expected output. ✅

**Type consistency:** `SkewMatrix`, `NbaGroup`, `GroupCell`, `Confidence`, `Tier` are defined once in `skewGrouping.ts` and imported everywhere; `SkewCheckPayload` field names match between `contracts.py` (Python) and `useSkewCheckApi.ts` (TS) one-to-one; backend `get_skew_check(tool_slug, fab_id, recipe_id)` signature is identical across `data.py`/`mock.py`/`office.py`/`routes.py`. ✅

**Known follow-ups (out of Phase-1 scope, per next_steps §5 / terminology §8):** consensus estimator form, confidence tier numeric boundaries, exact cd_band nm edges, min-fleet / min-residual thresholds, BM/PM soft-marker step-test — all resolved with office real data during the `data.py` swap.
