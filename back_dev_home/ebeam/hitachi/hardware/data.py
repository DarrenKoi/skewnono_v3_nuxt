"""SWAP SURFACE — hardware-page mock payloads (BSM / FDC / BM-PM).

Phase 1 returns stub responses so the frontend can wire its pill row to
real network calls. Office implementation should replace each branch with
the corresponding OpenSearch/Redis query while keeping the response shape
stable (the frontend types live in `composables/useHardwareApi.ts`).

Service semantics:
  * bm-pm — BM/PM info is expected to exist for every tool (maintenance
    schedule is universal), so this branch always returns populated rows.
  * bsm / fdc — Beam-shape-matching and FDC may be missing for tools that
    don't run those subsystems. The stub indicates `available=False` for
    those cases; office should report the same flag.
"""

from datetime import datetime, timezone
from typing import Literal, TypedDict


ServiceKey = Literal["bsm", "fdc", "bm-pm"]
VALID_SERVICES: frozenset[str] = frozenset({"bsm", "fdc", "bm-pm"})


class HardwarePayload(TypedDict):
    tool_slug: str
    service: ServiceKey
    eqp_id: str | None
    fab_id: str | None
    available: bool
    fetched_at: str
    summary: str
    details: dict


_UNAVAILABLE_SUMMARIES: dict[ServiceKey, str] = {
    "bsm": "BSM 데이터는 일부 장비에서만 제공됩니다. (Phase 1 mock)",
    "fdc": "FDC signal/alarm trend은 office 연동 후 표시됩니다. (Phase 1 mock)"
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bm_pm_payload(tool_slug: str, eqp_id: str | None, fab_id: str | None) -> HardwarePayload:
    return {
        "tool_slug": tool_slug,
        "service": "bm-pm",
        "eqp_id": eqp_id,
        "fab_id": fab_id,
        "available": True,
        "fetched_at": _now_iso(),
        "summary": "BM/PM 일정과 최근 maintenance 이력을 조회했습니다." if eqp_id
                   else "BM/PM 데이터는 항상 제공됩니다. 장비를 선택하면 상세 일정을 표시합니다.",
        "details": {
            "last_bm_date": "2026-04-22",
            "next_pm_date": "2026-06-10",
            "pm_window_hours": 8,
            "open_work_orders": 0
        }
    }


def _unavailable_payload(
    service: ServiceKey,
    tool_slug: str,
    eqp_id: str | None,
    fab_id: str | None
) -> HardwarePayload:
    return {
        "tool_slug": tool_slug,
        "service": service,
        "eqp_id": eqp_id,
        "fab_id": fab_id,
        "available": False,
        "fetched_at": _now_iso(),
        "summary": _UNAVAILABLE_SUMMARIES[service],
        "details": {}
    }


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_id: str | None
) -> HardwarePayload:
    if service == "bm-pm":
        return _bm_pm_payload(tool_slug, eqp_id, fab_id)
    return _unavailable_payload(service, tool_slug, eqp_id, fab_id)
