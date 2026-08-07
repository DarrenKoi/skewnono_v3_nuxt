"""Shared in-process measurement analytics primitives.

Recipe TAT and Fail Issue expose different aggregate contracts but operate on
the same measurement scope. This module owns only that common behavior.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterable, Mapping, TypeVar

from back_dev_home.ebeam.hitachi._tool_specs import ToolType


RowT = TypeVar("RowT", bound=Mapping[str, object])


@dataclass(frozen=True)
class MeasurementScope:
    tool_type: ToolType | None
    fab_names: tuple[str, ...] | None
    start_date: str | None
    end_date: str | None
    lot_cd: str | None = None


def fab_base(fab_name: str) -> str:
    """Return the workload-profile key for a fab or sub-fab."""
    if fab_name.startswith("R"):
        return fab_name
    return fab_name[:3] if len(fab_name) > 3 else fab_name


def parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def filter_measurements(
    rows: Iterable[RowT],
    scope: MeasurementScope,
) -> tuple[RowT, ...]:
    """Apply the shared tool/fab/lot/date semantics to measurement rows."""
    fab_norms = (
        {fab.upper() for fab in scope.fab_names} if scope.fab_names else None
    )
    out: list[RowT] = []

    for row in rows:
        if scope.tool_type and row["tool_type"] != scope.tool_type:
            continue
        if fab_norms and str(row["fab_name"]).upper() not in fab_norms:
            continue
        if scope.lot_cd and row["lot_cd"] != scope.lot_cd:
            continue

        date_key = str(row["timestamp"])[:10]
        if scope.start_date and date_key < scope.start_date:
            continue
        if scope.end_date and date_key > scope.end_date:
            continue
        out.append(row)

    return tuple(out)


@lru_cache(maxsize=1)
def lot_metadata() -> dict[str, dict[str, str | None]]:
    """Return device quick-filter metadata keyed by lot code."""
    from back_dev_home.ebeam.cdsem.device_statistics.providers.mock import (
        get_device_desc,
        get_r3_device_grp,
    )

    out: dict[str, dict[str, str | None]] = {}
    for row in get_r3_device_grp():
        out[row["lot_cd"]] = {
            "prod_catg_cd": row["prod_catg_cd"],
            "tech_nm": None,
        }
    for row in get_device_desc():
        out[row["lot_cd"]] = {
            "prod_catg_cd": None,
            "tech_nm": row["tech_nm"],
        }
    return out


_PERCENTILE_POINTS: tuple[tuple[str, float], ...] = (
    ("p10", 0.10), ("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p90", 0.90),
)


def percentile_summary(values: Iterable[float]) -> dict[str, float]:
    """p10/p25/p50/p75/p90을 nearest-rank로 계산합니다.

    보간이 아니라 nearest-rank인 이유는 결과가 항상 실제 표본값이고 단조가
    정의상 보장되기 때문입니다 — 프론트엔드가 "이 장비가 꼬리에 있는가"를
    이 값들과의 단순 비교로 묻습니다.

    표본이 없으면 빈 dict입니다. 호출자(그리고 UI)는 이걸 "판단 근거 없음"
    으로 읽어야 하며, 배지를 달지 않습니다.
    """
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {}

    def at(quantile: float) -> float:
        index = math.ceil(quantile * len(ordered)) - 1
        return ordered[max(0, min(index, len(ordered) - 1))]

    return {name: at(quantile) for name, quantile in _PERCENTILE_POINTS}
