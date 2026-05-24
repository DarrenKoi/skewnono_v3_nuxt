"""Office hardware provider.

Wire OpenSearch, Redis, files, or internal APIs here. Keep source-specific keys
inside this module and `normalizers.py`; the route must keep returning the
canonical hardware contract.
"""

from back_dev_home.ebeam.hitachi.hardware.contracts import (
    HardwarePayload,
    RecordValue,
    ServiceKey,
)
from back_dev_home.ebeam.hitachi.hardware.normalizers import (
    bm_pm_payload,
    normalize_office_rows,
)


def _fetch_bsm_rows(
    tool_slug: str,
    eqp_id: str | None,
    fab_id: str | None,
) -> list[dict[str, RecordValue]]:
    _ = (tool_slug, eqp_id, fab_id)
    return []


def _fetch_fdc_rows(
    tool_slug: str,
    eqp_id: str | None,
    fab_id: str | None,
) -> list[dict[str, RecordValue]]:
    _ = (tool_slug, eqp_id, fab_id)
    return []


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_id: str | None,
) -> HardwarePayload:
    if service == "bm-pm":
        return bm_pm_payload(
            tool_slug,
            eqp_id,
            fab_id,
            last_bm_date="",
            next_pm_date="",
            pm_window_hours=0,
            open_work_orders=0,
        )
    if service == "bsm":
        return normalize_office_rows(
            service,
            tool_slug,
            eqp_id,
            fab_id,
            _fetch_bsm_rows(tool_slug, eqp_id, fab_id),
        )
    return normalize_office_rows(
        service,
        tool_slug,
        eqp_id,
        fab_id,
        _fetch_fdc_rows(tool_slug, eqp_id, fab_id),
    )
