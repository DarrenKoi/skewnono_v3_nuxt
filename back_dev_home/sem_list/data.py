"""SWAP SURFACE for the SEM equipment list.

Routes import only this module. The selected adapter lives in
``providers/mock.py`` or ``providers/office.py`` and must return the shared
``SemListRow`` contract.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.sem_list.contracts import SemListRow


__all__ = ["SemListRow", "get_sem_list"]


def get_sem_list() -> list[SemListRow]:
    if get_data_provider("sem_list") == "office":
        from back_dev_home.sem_list.providers.office import (
            get_sem_list as load_sem_list,
        )
    else:
        from back_dev_home.sem_list.providers.mock import (
            get_sem_list as load_sem_list,
        )

    return load_sem_list()
