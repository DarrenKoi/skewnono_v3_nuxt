"""Shared UTC-ISO-Z timestamp formatting.

Four call sites (admin_logs, activity's two providers, health's probes) each
hand-rolled ``value.astimezone(timezone.utc).isoformat(...).replace("+00:00",
"Z")``, differing only in ``timespec``. One helper, one place to fix a bug.
"""

from __future__ import annotations

from datetime import datetime, timezone


def iso_z(value: datetime, timespec: str = "seconds") -> str:
    """UTC ISO-8601 string with a literal ``Z`` suffix instead of ``+00:00``."""
    return value.astimezone(timezone.utc).isoformat(timespec=timespec).replace("+00:00", "Z")
