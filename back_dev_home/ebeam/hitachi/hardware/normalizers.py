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


def normalize_office_rows(
    service: ServiceKey,
    tool_slug: str,
    eqp_id: str | None,
    fab_name: str | None,
    raw_rows: list[dict[str, RecordValue]],
) -> HardwarePayload:
    """Temporary adapter for unknown office BSM/FDC row shapes."""
    if not raw_rows:
        return unavailable_payload(
            service,
            tool_slug,
            eqp_id,
            fab_name,
            f"{service.upper()} office data is not available for the selected equipment.",
        )

    first_row = raw_rows[0]
    columns = [
        {"key": key, "label": key.replace("_", " ").title()}
        for key in first_row.keys()
    ]
    return {
        "tool_slug": tool_slug,
        "service": service,
        "eqp_id": eqp_id,
        "fab_name": fab_name,
        "available": True,
        "fetched_at": now_iso(),
        "summary": f"{service.upper()} office rows were normalized into a table payload.",
        "cards": [
            {
                "key": "row_count",
                "label": "Rows",
                "value": len(raw_rows),
                "tone": "neutral",
            }
        ],
        "tables": [
            {
                "key": f"{service}_office_rows",
                "title": f"{service.upper()} Rows",
                "columns": columns,
                "rows": raw_rows,
            }
        ],
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
) -> HardwarePayload:
    """Wrap a faithful dict-of-dict (mdc / sce): eqp + in-fab siblings.

    Thin cards: as-of date + sibling count. `tables` optional (e.g. the mdc
    matrix or sce settings-compare are built frontend-side off `settings`).
    """
    sibling_count = max(0, len(settings) - 1)
    cards: list[HardwareMetricCard] = [
        {"key": "as_of", "label": "기준일", "value": as_of, "tone": "neutral"},
        {"key": "sibling_count", "label": "동일 fab 장비", "value": sibling_count, "unit": "대", "tone": "neutral"},
    ]
    return {
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
