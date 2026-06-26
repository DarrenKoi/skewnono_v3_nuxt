"""Canonical hardware API contract.

Raw beam_shape / reso_center / FDC / MDC / SCE sources can use different field
names per environment. This module defines the stable shape the Flask route
returns. Faithful raw docs ride in `docs` (time-series) / `settings`
(dict-of-dict); `cards`/`tables` carry the thin summary the page header reads.
"""

from typing import Literal, NotRequired, TypeAlias, TypedDict


ServiceKey = Literal["bsm", "reso-center", "fdc", "mdc", "sce", "bm-pm", "sharpness"]
VALID_SERVICES: frozenset[str] = frozenset(
    {"bsm", "reso-center", "fdc", "mdc", "sce", "bm-pm", "sharpness"}
)

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


class HardwarePayload(TypedDict):
    tool_slug: str
    service: ServiceKey
    eqp_id: str | None
    fab_name: str | None
    available: bool
    fetched_at: str
    summary: str
    cards: list[HardwareMetricCard]
    tables: list[HardwareTableSection]
    # Faithful time-series raw docs (bsm / reso-center / fdc), ascending time.
    docs: NotRequired[list[dict]]
    # Faithful dict-of-dict (mdc / sce): selected eqp + in-fab siblings.
    settings: NotRequired[dict[str, dict]]
    raw: NotRequired[dict]
