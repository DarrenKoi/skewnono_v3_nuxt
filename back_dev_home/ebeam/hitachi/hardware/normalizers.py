"""Normalize environment-specific hardware data into the public API shape."""

from datetime import datetime, timezone

from back_dev_home.ebeam.hitachi.hardware.contracts import (
    HardwareMetricCard,
    HardwarePayload,
    HardwareTableSection,
    RecordValue,
    ServiceKey,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# bsm / reso-center / sce / sharpness are CD-SEM-only checks.
CDSEM_ONLY_SERVICES: frozenset[str] = frozenset({"bsm", "reso-center", "sce", "sharpness"})

_CDSEM_ONLY_MSG: dict[str, str] = {
    "bsm": "BSM는 CD-SEM 장비에서만 제공됩니다.",
    "reso-center": "Reso Center는 CD-SEM 장비에서만 제공됩니다.",
    "sce": "SCE는 CD-SEM 장비에서만 제공됩니다.",
    "sharpness": "Sharpness는 CD-SEM 장비에서만 제공됩니다.",
}

_EMPTY_HINT: dict[str, str] = {
    "bsm": "장비를 선택하면 BSM 추세와 360° 빔 형상을 확인할 수 있습니다.",
    "reso-center": "장비를 선택하면 Reso Center 추세를 확인할 수 있습니다.",
    "fdc": "장비를 선택하면 FDC 신호/판정 추세를 확인할 수 있습니다.",
    "mdc": "장비를 선택하면 MDC 보정 계수와 동일 fab skew를 확인할 수 있습니다.",
    "sce": "장비를 선택하면 SCE 설정과 계수 곡선을 확인할 수 있습니다.",
    "bm-pm": "장비를 선택하면 BM/PM 작업 이력과 예정 작업을 확인할 수 있습니다.",
    "sharpness": "장비를 선택하면 chamber stub sharpness 추세와 360° 빔 형상을 확인할 수 있습니다.",
}


def service_gate(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_name: str | None,
) -> HardwarePayload | None:
    """Provider-independent short-circuits shared by mock and office.

    Returns the finished payload when the request needs no data lookup
    (CD-SEM-only service on a non-CD-SEM tool, or no tool selected yet),
    else None so the provider dispatches per service.
    """
    if service in CDSEM_ONLY_SERVICES and tool_slug != "cdsem":
        return unavailable_payload(
            service, tool_slug, eqp_id, fab_name, _CDSEM_ONLY_MSG[service]
        )
    if eqp_id is None:
        # No tool picked yet — available-but-empty so the page shows a hint.
        return {
            "tool_slug": tool_slug,
            "service": service,
            "eqp_id": None,
            "fab_name": fab_name,
            "available": True,
            "fetched_at": now_iso(),
            "summary": _EMPTY_HINT[service],
            "cards": [],
            "tables": [],
        }
    return None


def unavailable_payload(
    service: ServiceKey,
    tool_slug: str,
    eqp_id: str | None,
    fab_name: str | None,
    summary: str,
) -> HardwarePayload:
    return {
        "tool_slug": tool_slug,
        "service": service,
        "eqp_id": eqp_id,
        "fab_name": fab_name,
        "available": False,
        "fetched_at": now_iso(),
        "summary": summary,
        "cards": [],
        "tables": [],
    }


def bm_pm_payload(
    tool_slug: str,
    eqp_id: str | None,
    fab_name: str | None,
    *,
    last_bm_date: str,
    next_pm_date: str,
    pm_window_hours: int,
    open_work_orders: int,
) -> HardwarePayload:
    cards: list[HardwareMetricCard] = [
        {
            "key": "last_bm_date",
            "label": "Last BM",
            "value": last_bm_date,
            "tone": "neutral",
        },
        {
            "key": "next_pm_date",
            "label": "Next PM",
            "value": next_pm_date,
            "tone": "ok",
        },
        {
            "key": "pm_window_hours",
            "label": "PM Window",
            "value": pm_window_hours,
            "unit": "hours",
            "tone": "neutral",
        },
        {
            "key": "open_work_orders",
            "label": "Open WO",
            "value": open_work_orders,
            "tone": "warning" if open_work_orders else "ok",
        },
    ]
    tables: list[HardwareTableSection] = [
        {
            "key": "maintenance_schedule",
            "title": "Maintenance Schedule",
            "columns": [
                {"key": "event", "label": "Event"},
                {"key": "date", "label": "Date"},
                {"key": "status", "label": "Status"},
            ],
            "rows": [
                {"event": "Last BM", "date": last_bm_date, "status": "closed"},
                {"event": "Next PM", "date": next_pm_date, "status": "planned"},
            ],
        }
    ]

    return {
        "tool_slug": tool_slug,
        "service": "bm-pm",
        "eqp_id": eqp_id,
        "fab_name": fab_name,
        "available": True,
        "fetched_at": now_iso(),
        "summary": (
            "BM/PM schedule and recent maintenance history are available."
            if eqp_id
            else "BM/PM data is available. Select equipment to inspect its schedule."
        ),
        "cards": cards,
        "tables": tables,
    }


def bm_pm_history_payload(
    tool_slug: str,
    eqp_id: str | None,
    fab_name: str | None,
    *,
    past_rows: list[dict[str, RecordValue]],
    future_rows: list[dict[str, RecordValue]],
    cards: dict[str, RecordValue],
) -> HardwarePayload:
    """Build the BM/PM payload from generated past/future work records.

    Rows arrive pre-sorted (timestamp desc) from the provider; this only maps
    them onto the canonical two-section table shape plus data-driven cards.
    """
    metric_cards: list[HardwareMetricCard] = [
        {
            "key": "last_bm",
            "label": "Last BM",
            "value": cards.get("last_bm", "—"),
            "tone": "neutral",
        },
        {
            "key": "next_pm",
            "label": "Next PM",
            "value": cards.get("next_pm", "—"),
            "tone": "ok",
        },
        {
            "key": "planned_count",
            "label": "예정 작업",
            "value": cards.get("planned_count", 0),
            "unit": "건",
            "tone": "warning" if cards.get("planned_count") else "neutral",
        },
        {
            "key": "recent_count",
            "label": "최근 작업",
            "value": cards.get("recent_count", 0),
            "unit": "건",
            "tone": "neutral",
        },
    ]

    tables: list[HardwareTableSection] = [
        {
            "key": "past_work",
            "title": "최근 작업 이력 (Past Work)",
            "columns": [
                {"key": "timestamp", "label": "Uploaded"},
                {"key": "eqp_id", "label": "EQP ID"},
                {"key": "category", "label": "Category"},
                {"key": "job_starts", "label": "Job Start"},
                {"key": "job_end", "label": "Job End"},
                {"key": "engr_note", "label": "Engineer Note", "expandable": True},
            ],
            "rows": past_rows,
        },
        {
            "key": "future_work",
            "title": "예정 작업 (Future Work)",
            "columns": [
                {"key": "eqp_id", "label": "EQP ID"},
                {"key": "category", "label": "Category"},
                {"key": "job_starts", "label": "Job Start"},
                {"key": "job_end", "label": "Job End"},
                {"key": "timestamp", "label": "Uploaded"},
            ],
            "rows": future_rows,
        },
    ]

    return {
        "tool_slug": tool_slug,
        "service": "bm-pm",
        "eqp_id": eqp_id,
        "fab_name": fab_name,
        "available": True,
        "fetched_at": now_iso(),
        "summary": "선택한 장비의 BM/PM 작업 이력과 예정 작업을 최신순으로 표시합니다.",
        "cards": metric_cards,
        "tables": tables,
    }


def docs_payload(
    service: ServiceKey,
    tool_slug: str,
    eqp_id: str | None,
    fab_name: str | None,
    *,
    docs: list[dict],
    summary: str,
    extra_cards: list[HardwareMetricCard] | None = None,
) -> HardwarePayload:
    """Wrap a faithful time-series doc list (bsm / reso-center / fdc).

    Thin summary cards only: doc count + latest timestamp. The page reads
    chart axes straight off `docs` (data-driven selectors).
    """
    latest = docs[-1].get("timestamp", "—") if docs else "—"
    cards: list[HardwareMetricCard] = [
        {"key": "doc_count", "label": "문서 수", "value": len(docs), "unit": "건", "tone": "neutral"},
        {"key": "latest_ts", "label": "최신 측정", "value": latest, "tone": "neutral"},
    ]
    if extra_cards:
        cards.extend(extra_cards)
    return {
        "tool_slug": tool_slug,
        "service": service,
        "eqp_id": eqp_id,
        "fab_name": fab_name,
        "available": True,
        "fetched_at": now_iso(),
        "summary": summary,
        "cards": cards,
        "tables": [],
        "docs": docs,
    }


def settings_payload(
    service: ServiceKey,
    tool_slug: str,
    eqp_id: str | None,
    fab_name: str | None,
    *,
    settings: dict[str, dict],
    as_of: str,
    summary: str,
    tables: list[HardwareTableSection] | None = None,
    docs: list[dict] | None = None,
) -> HardwarePayload:
    """Wrap a faithful dict-of-dict (mdc / sce): eqp + in-fab siblings.

    Thin cards: as-of date + sibling count. `tables` optional (e.g. the sce
    settings-compare is built frontend-side off `settings`). `docs` optionally
    carries the selected tool's timestamped history (mdc 시계열), ascending.
    """
    sibling_count = max(0, len(settings) - 1)
    cards: list[HardwareMetricCard] = [
        {"key": "as_of", "label": "기준일", "value": as_of, "tone": "neutral"},
        {"key": "sibling_count", "label": "동일 fab 장비", "value": sibling_count, "unit": "대", "tone": "neutral"},
    ]
    payload: HardwarePayload = {
        "tool_slug": tool_slug,
        "service": service,
        "eqp_id": eqp_id,
        "fab_name": fab_name,
        "available": True,
        "fetched_at": now_iso(),
        "summary": summary,
        "cards": cards,
        "tables": tables or [],
        "settings": settings,
    }
    if docs is not None:
        payload["docs"] = docs
    return payload
