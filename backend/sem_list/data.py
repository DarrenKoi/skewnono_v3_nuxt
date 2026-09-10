"""SWAP SURFACE for the SEM equipment list.

Routes import only this module. The selected adapter lives in
``providers/mock.py`` or ``providers/office.py`` and must return the shared
``SemListRow`` contract.
"""

from backend._runtime.data_provider import get_data_provider
from backend.sem_list.contracts import PendingToolRow, SemListRow


__all__ = ["PendingToolRow", "SemListRow", "get_pending_tools", "get_sem_list"]


def get_sem_list() -> list[SemListRow]:
    if get_data_provider("sem_list") == "office":
        from backend.sem_list.providers.office import (
            get_sem_list as load_sem_list,
        )
    else:
        from backend.sem_list.providers.mock import (
            get_sem_list as load_sem_list,
        )

    return load_sem_list()


def get_pending_tools() -> list[PendingToolRow]:
    if get_data_provider("sem_list") == "office":
        from backend.sem_list.providers.office import (
            get_pending_tools as load_pending_tools,
        )
    else:
        from backend.sem_list.providers.mock import (
            get_pending_tools as load_pending_tools,
        )

    return load_pending_tools()
