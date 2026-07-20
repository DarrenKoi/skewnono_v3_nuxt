# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 adapter for office storage sources.

Connect the office storage-monitoring index and PPID-unavailable Redis hash in
this module. Normalize source-specific documents to the contracts before
returning them so routes and frontend code remain unchanged.
"""

from back_dev_home.ebeam.hitachi._tool_specs import ToolSlug
from back_dev_home.ebeam.hitachi.storage.contracts import (
    PpidUnavailableSnapshot,
    StorageRow,
)


def get_storage(
    tool_slug: ToolSlug,
    fac_ids: list[str] | None = None,
) -> list[StorageRow]:
    """Return normalized rows from the office storage-monitoring index.

    Implementation checklist:
    - Use ``tool_slug`` to select the CD-SEM or HV-SEM equipment scope.
    - Treat missing/empty ``fac_ids`` as all facilities; otherwise filter them.
    - Map every source document to ``StorageRow`` exactly.
    - Represent failed storage collection with blank capacity fields and
      ``storage_mt=None`` while retaining recipe-count information.
    """
    _ = (tool_slug, fac_ids)
    raise NotImplementedError(
        "The storage office adapter has not been connected yet. "
        "Set SKEWNONO_STORAGE_PROVIDER=mock until it is ready."
    )


def get_ppid_unavailable(
    tool_slug: ToolSlug,
    fac_ids: list[str] | None = None,
) -> PpidUnavailableSnapshot:
    """Return the latest normalized PPID-unavailable snapshot from Redis.

    The expected office source is Redis hash
    ``v3_hitachi_sem_ppid_not_avail``. Its date field maps to a list of
    equipment IPs; join those IPs to the SEM list and preserve unmatched IPs as
    rows whose equipment fields are blank.
    """
    _ = (tool_slug, fac_ids)
    raise NotImplementedError(
        "The storage PPID office adapter has not been connected yet. "
        "Set SKEWNONO_STORAGE_PROVIDER=mock until it is ready."
    )