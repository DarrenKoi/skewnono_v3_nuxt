"""SWAP SURFACE - hardware-page provider selection.

Routes import only this module. Phase-specific source wiring belongs in
`providers/mock.py` or `providers/office.py`, then both paths normalize to the
canonical contract in `contracts.py`.
"""

import os
from datetime import datetime
from typing import Literal

from back_dev_home._runtime.env import is_cloud
from back_dev_home.ebeam.hitachi.hardware.contracts import (
    HardwarePayload,
    ServiceKey,
    VALID_SERVICES,
)
from back_dev_home.ebeam.hitachi.hardware.providers import mock, office


ProviderKey = Literal["mock", "office"]


def _provider_key() -> ProviderKey:
    raw = os.environ.get("SKEWNONO_HARDWARE_PROVIDER", "").strip().lower()
    if raw in {"mock", "office"}:
        return raw  # type: ignore[return-value]
    return "office" if is_cloud() else "mock"


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> HardwarePayload:
    provider = office if _provider_key() == "office" else mock
    return provider.get_hardware_service(
        tool_slug, service, eqp_id, fab_name, start, end
    )
