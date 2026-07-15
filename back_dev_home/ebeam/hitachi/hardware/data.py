"""SWAP SURFACE for hardware-page provider selection.

Routes import only this module. Phase-specific source wiring belongs in
`providers/mock.py` or `providers/office.py`, then both paths normalize to the
canonical contract in `contracts.py`.
"""

from datetime import datetime

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.hardware.contracts import (
    HardwarePayload,
    ServiceKey,
    VALID_SERVICES,
)


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> HardwarePayload:
    if get_data_provider("hardware") == "office":
        from back_dev_home.ebeam.hitachi.hardware.providers.office import (
            get_hardware_service as load_hardware_service,
        )
    else:
        from back_dev_home.ebeam.hitachi.hardware.providers.mock import (
            get_hardware_service as load_hardware_service,
        )

    return load_hardware_service(
        tool_slug, service, eqp_id, fab_name, start, end
    )
