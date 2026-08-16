"""The fleet-roster law: which sem_list rows make up one (fab, tool family) fleet.

sem_list is the roster of record (see ebeam/_tool_specs.py's module docstring),
and several features derive a per-fab fleet from it — tttm and pm_planning join
their payloads BY eqp_id, so they must derive that fleet identically or the
join silently intersects toward zero. This module is the one statement of the
law; a provider that re-implements it is the bug this file exists to prevent.

The law, and why each clause is what it is:

- **Filter by `fab_name`, never `fac_id`**: `fac_id` is fac-level (`M16` for
  `M16A`) and would fold three fabs into one roster. See the fab_name/fac_id
  note in ebeam/tttm/tests/test_contract.py.
- **Classify by `model_to_tool_type(eqp_model_cd)`**: never parse the eqp_id
  prefix — _tool_specs owns the model→family mapping.
- **Deduplicate by `eqp_id`**: eqp_id INDEXES downstream structures (tttm's
  skew matrix axes, pm_planning's per-tool blocks). A roster naming the same
  tool twice yields two identical axes, and clique grouping would then report
  a tool as matching itself. The mock roster really does collide (sem_list
  rolls ids at random — ~10 of its 300 rows share an id), and an office roster
  joined across two frames can just as easily hand back a tool twice.
- **Sorted by `eqp_id`**: so the roster order is a property of the fab, not of
  sem_list's row order (mock demos rely on "the last tool" being stable).

Pure over rows on purpose — same shape as ebeam/live_alarm/roster.py. It must
NOT call get_sem_list() itself: mock providers import
sem_list.providers.mock.get_sem_list directly while office adapters go through
sem_list.data, and a helper that picked its own source would break that split.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from back_dev_home.ebeam._tool_specs import model_to_tool_type


__all__ = ["fleet_rows"]


def fleet_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    fab_name: str,
    tool_type: str,
) -> list[Mapping[str, Any]]:
    """Deduplicated, eqp_id-sorted roster rows for one (fab, tool family)."""
    target = fab_name.strip().upper()
    kept = [
        row for row in rows
        if row["fab_name"].strip().upper() == target
        and model_to_tool_type(row["eqp_model_cd"]) == tool_type
    ]
    seen: set[str] = set()
    fleet: list[Mapping[str, Any]] = []
    for row in sorted(kept, key=lambda r: r["eqp_id"]):
        if row["eqp_id"] in seen:
            continue
        seen.add(row["eqp_id"])
        fleet.append(row)
    return fleet
