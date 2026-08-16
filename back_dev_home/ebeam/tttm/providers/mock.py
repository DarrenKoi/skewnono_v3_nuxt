"""Phase-1 skew mock provider — serves a deterministic fixture per fab."""

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
