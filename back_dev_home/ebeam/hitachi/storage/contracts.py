"""Stable Python contracts for storage-page responses."""

from typing import TypedDict


__all__ = [
    "StorageRow",
    "PpidUnavailableRow",
    "PpidUnavailableSnapshot",
]


class StorageRow(TypedDict):
    eqp_id: str
    eqp_ip: str
    fac_id: str
    total: str              # "" when storage collection failed
    used: str               # "" when storage collection failed
    avail: str              # "" when storage collection failed
    percent: str            # "" when storage collection failed
    storage_mt: str | None  # None when storage collection failed
    rcp_counts: int
    rcp_counts_mt: str
    storage_mt_date: str    # "" when storage collection failed
    fab_name: str
    eqp_model_cd: str


class PpidUnavailableRow(TypedDict):
    eqp_id: str
    eqp_ip: str
    fac_id: str
    fab_name: str
    eqp_model_cd: str
    missing_days_streak: int


class PpidUnavailableSnapshot(TypedDict):
    latest_date: str
    rows: list[PpidUnavailableRow]
