"""Office hardware provider — NOT CONNECTED YET.

Wire OpenSearch, Redis, files, or internal APIs here per hardware/MIGRATION.md,
then normalize each service's raw docs to the canonical HardwarePayload using
``normalizers.py`` (bm_pm_payload / unavailable_payload are ready for that).

Until every service has a real source, this adapter FAILS FAST: returning empty
placeholders here (the previous behaviour) let office mode silently report
services as available with blank/zero data, so flipping SKEWNONO_HARDWARE_PROVIDER
to office looked connected when it was not. Fail fast so the gate and the app
surface the missing wiring instead of hiding it.
"""

from datetime import datetime

from back_dev_home.ebeam.hitachi.hardware.contracts import (
    HardwarePayload,
    ServiceKey,
)


def _not_connected() -> HardwarePayload:
    raise NotImplementedError(
        "The hardware office adapter has not been connected yet. "
        "Set SKEWNONO_HARDWARE_PROVIDER=mock until it is ready."
    )


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> HardwarePayload:
    return _not_connected()
