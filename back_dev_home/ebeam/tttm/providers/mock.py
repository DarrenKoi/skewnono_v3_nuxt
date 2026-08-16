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
- **The measured cells sit at three different CDs** (32.4 / 31.8 / 68.0 nm),
  and `bc2` is in a different `cd_band` from the other two on purpose. The
  PM/BM limit is 1% of CD, so those cells carry limits of 0.324 / 0.318 /
  0.680 nm — spread wide enough that a screen quietly reusing one absolute
  limit is visibly wrong rather than plausibly close.
- **`bc3-X-lt25-e7` has `median_cd_nm: null`.** The office may return skew
  statistics with no CD beside them, and the client has a whole assumed-CD
  path for that (`resolveNominalCd` → monitor wafer, captions saying it
  assumed). Without a null here that path is dead code at home and the first
  time it runs is at the office. Its skews keep 01/02/04 inside the default
  knob so adding it does not quietly dismantle the N배화 recommendation the
  rest of the fixture is built around.
- **The over-tolerance pair is still INSIDE its own PM/BM limit.** EQP01↔EQP05
  at 0.24 nm exceeds the 0.20 nm tolerance ceiling but sits under that cell's
  0.318 nm action limit. The contrast is the point: the tolerance knob is a
  matching goal for N배화, the action limit is fab policy about one tool
  against consensus, and a fixture at smaller CDs would teach them as one
  number.

OFFICE-VERIFY: every number here is fabricated. Real pairwise skew magnitudes
and the true spread across cells are unknown until an office run — item 3 of
`docs/research/2026-08-16-skew-tttm-feasibility.md` section 6.

`consensus_deviation` is deliberately kept inside **±0.15 nm**, the fab's tool
management limit — a tool outside it goes to PM/BM (user-confirmed 2026-08-16).
The widest here is EQP05 at -0.13, so the demo fleet is "all in spec, but one
tool is close to the edge" rather than "one tool already needs PM". The
frontend derives that limit as 1% of `fleet_today.median_cd_nm` (15.1 nm here,
the monitor wafer → 0.151 nm) rather than from a constant, so **raising the
fleet CD raises the limit too**. If these deviations are ever pushed past it,
the screen turns that tool red and says PM/BM, so move them knowing what you
are asserting — and if you move the CD instead, you have moved the line.

OFFICE-VERIFY: `consensus` is assumed to be the **median** (the fab states the
rule against a median). The office adapter must not use a mean — one drifted
tool would drag the reference and shift every other tool's deviation.

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
        "fleet_today": {
            "matrix": {"tools": [], "values": []},
            "consensus_deviation": [],
            "median_cd_nm": None,
        },
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
