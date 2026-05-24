"""Canonical hardware API contract.

Raw BSM/FDC/BM-PM sources can use different field names in each environment.
This module defines the stable shape returned by the Flask route.
"""

from typing import Literal, NotRequired, TypeAlias, TypedDict


ServiceKey = Literal["bsm", "fdc", "bm-pm"]
VALID_SERVICES: frozenset[str] = frozenset({"bsm", "fdc", "bm-pm"})

MetricTone = Literal["neutral", "ok", "warning", "bad"]
RecordValue: TypeAlias = str | int | float | bool | None


class HardwareMetricCard(TypedDict):
    key: str
    label: str
    value: RecordValue
    unit: NotRequired[str]
    tone: NotRequired[MetricTone]


class HardwareTableColumn(TypedDict):
    key: str
    label: str
    # Long free-text columns (e.g. engr_note) render truncated with a
    # click-to-expand toggle instead of forcing a wide nowrap cell.
    expandable: NotRequired[bool]


class HardwareTableSection(TypedDict):
    key: str
    title: str
    columns: list[HardwareTableColumn]
    rows: list[dict[str, RecordValue]]


class BsmSummaryRow(TypedDict):
    timestamp: str
    eqp_id: str
    sharpness_avg: float
    sharpness_3std: float
    noise_avg: float
    noise_3std: float


class BsmProfile(TypedDict):
    # Parallel to the angle list: one value per 22.5deg step.
    sharpness: list[float]
    noise: list[float]


class BsmCategory(TypedDict):
    key: str  # "daily" | "pm"
    label: str
    summary: list[BsmSummaryRow]
    # Raw 360deg profiles keyed by the summary row's timestamp (the join key
    # the frontend uses to drive the radar chart on row/point click).
    profiles: dict[str, BsmProfile]


class BsmBlock(TypedDict):
    angles: list[str]
    categories: list[BsmCategory]


class HardwarePayload(TypedDict):
    tool_slug: str
    service: ServiceKey
    eqp_id: str | None
    fab_id: str | None
    available: bool
    fetched_at: str
    summary: str
    cards: list[HardwareMetricCard]
    tables: list[HardwareTableSection]
    # Present only for the BSM service (charts + radar source).
    bsm: NotRequired[BsmBlock]
    raw: NotRequired[dict[str, RecordValue]]
