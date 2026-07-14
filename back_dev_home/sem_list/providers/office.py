"""Phase 2/3 adapter for the office SEM equipment source.

Replace the function body at the office with an OpenSearch, database, or
internal-interface query. Normalize every result to ``SemListRow`` before
returning it; callers and routes must not need to know the source format.
"""

from back_dev_home.sem_list.contracts import SemListRow


def get_sem_list() -> list[SemListRow]:
    raise NotImplementedError(
        "The sem_list office adapter has not been connected yet. "
        "Set SKEWNONO_SEM_LIST_PROVIDER=mock until it is ready."
    )
