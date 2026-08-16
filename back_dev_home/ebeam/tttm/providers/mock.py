"""Phase-1 TTTM mock provider — serves a deterministic fixture per fab.

The fixture IS the mock data: there is no generator here, and
`scripts/capture_fixtures.py` merely round-trips this provider's own output, so
`__fixtures__/tttm_<slug>_<fab>.json` is edited by hand and is the thing to
change when the demo should show a different situation.

Deliberate properties of `tttm_cdsem_r3.json`, so a later edit does not flatten
them by accident:

- **EQP05 is the drifted tool.** It sits furthest from consensus and carries the
  widest pairwise skews. The 01/02/04 cluster is what the N배화 recommendation
  is built from.
- **One pair exceeds `tolerance_range.max`** — EQP01↔EQP05 in cell
  `bc1-Y-25-50-e7` is 0.24 nm against a 0.20 nm ceiling. Without it the demo
  could never show a failing pair, because the knob at full travel passed
  everything; the tolerance control looked like it had no negative state.
  The cell is `direct`/`High` on purpose, so the failure reads as real rather
  than as low-confidence noise, and it is the Y axis only — an axis-specific
  drift is more plausible than a uniform one.
- **EQP05's row is entirely null in `bc2-X-50-100-e7`.** That is the
  "no overlapping measurement" case the frontend must not place on the fleet
  map; see `utils/fleetMap.ts`.

OFFICE-VERIFY: every number here is fabricated. Real pairwise skew magnitudes
and the true spread across cells are unknown until an office run — item 3 of
`docs/research/2026-08-16-skew-tttm-feasibility.md` section 6.

Known departure from reality, left as-is: `fleet_today.matrix` is not consistent
with `fleet_today.consensus_deviation` (e.g. EQP03 at +0.09 and EQP05 at -0.13
imply a ~0.22 nm gap, while the matrix says 0.08). The two are independent
views in the contract, and no screen cross-checks them today.
"""

import json
from pathlib import Path

from back_dev_home.ebeam.tttm.contracts import TttmCheckPayload

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "__fixtures__"


def _empty_payload(tool_slug: str, fab_name: str, recipe_id: str | None) -> TttmCheckPayload:
    return {
        "tool_slug": tool_slug,  # type: ignore[typeddict-item]
        "fab_name": fab_name,
        "recipe_id": recipe_id,
        "available": False,
        "fetched_at": "",
        "summary": f"{fab_name} {tool_slug} 장비 그룹의 스큐 mock 데이터가 아직 없습니다.",
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


def get_tttm_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
) -> TttmCheckPayload:
    fixture = _FIXTURE_DIR / f"tttm_{tool_slug}_{fab_name.lower()}.json"
    if not fixture.exists():
        return _empty_payload(tool_slug, fab_name, recipe_id)
    payload: TttmCheckPayload = json.loads(fixture.read_text(encoding="utf-8"))
    payload["recipe_id"] = recipe_id or payload.get("recipe_id")
    return payload
