"""SWAP SURFACE for storage-page provider selection.

Routes import only this module. The selected adapter lives in
``providers/mock.py`` or ``providers/office.py`` and must return the shared
contracts from ``contracts.py``.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi._tool_specs import ToolSlug
from back_dev_home.ebeam.hitachi.storage.contracts import (
    PpidUnavailableRow,
    PpidUnavailableSnapshot,
    StorageRow,
)


__all__ = [
    "StorageRow",
    "PpidUnavailableRow",
    "PpidUnavailableSnapshot",
    "get_storage",
    "get_ppid_unavailable",
]


def get_storage(
    tool_slug: ToolSlug,
    fac_ids: list[str] | None = None,
) -> list[StorageRow]:
    if get_data_provider("storage") == "office":
        from back_dev_home.ebeam.hitachi.storage.providers.office import (
            get_storage as load_storage,
        )
    else:
        from back_dev_home.ebeam.hitachi.storage.providers.mock import (
            get_storage as load_storage,
        )

    return load_storage(tool_slug, fac_ids)


def get_ppid_unavailable(
    tool_slug: ToolSlug,
    fac_ids: list[str] | None = None,
) -> PpidUnavailableSnapshot:
    if get_data_provider("storage") == "office":
        from back_dev_home.ebeam.hitachi.storage.providers.office import (
            get_ppid_unavailable as load_ppid_unavailable,
        )
    else:
        from back_dev_home.ebeam.hitachi.storage.providers.mock import (
            get_ppid_unavailable as load_ppid_unavailable,
        )

    return load_ppid_unavailable(tool_slug, fac_ids)
