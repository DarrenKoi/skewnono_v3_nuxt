"""Office hardware provider.

Wire OpenSearch, Redis, files, or internal APIs here. Keep source-specific keys
inside this module and `normalizers.py`; the route must keep returning the
canonical hardware contract. New raw-doc services (bsm/reso-center/fdc/mdc/sce)
are stubbed unavailable until office data is wired.
"""

from datetime import datetime

from back_dev_home.ebeam.hitachi.hardware.contracts import (
    HardwarePayload,
    ServiceKey,
)
from back_dev_home.ebeam.hitachi.hardware.normalizers import (
    bm_pm_payload,
    unavailable_payload,
)


_OFFICE_PENDING: dict[str, str] = {
    "bsm": "BSM beam_shape office wiring is pending.",
    "reso-center": "Reso Center office wiring is pending.",
    "fdc": "FDC office wiring is pending.",
    "mdc": "MDC office wiring is pending.",
    "sce": "SCE office wiring is pending.",
    "sharpness": "Sharpness office wiring is pending.",
}


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> HardwarePayload:
    _ = (start, end)
    if service == "bm-pm":
        return bm_pm_payload(
            tool_slug,
            eqp_id,
            fab_name,
            last_bm_date="",
            next_pm_date="",
            pm_window_hours=0,
            open_work_orders=0,
        )
    return unavailable_payload(
        service, tool_slug, eqp_id, fab_name,
        _OFFICE_PENDING.get(service, f"{service} office wiring is pending."),
    )
