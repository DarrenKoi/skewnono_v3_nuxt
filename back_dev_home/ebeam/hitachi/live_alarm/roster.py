"""Which fab an alarm belongs to, answered by the sem_list roster.

The office alarm feed is keyed by EQP_ID and carries no fab column, so fab
attribution is ours to compute. It is computed by LOOKUP, never by parsing the
id: `_tool_specs.py` records an outage where treating eqp prefixes as a
classifier silently dropped 8 real tools from a panel.

The roster is also where ``fab_name -> fac_id`` comes from. No mapping table
is hardcoded — ``SemListRow`` carries both columns, so a fab added at the
office works here the day it lands in sem_list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from back_dev_home.ebeam.hitachi._tool_specs import ToolType, model_to_tool_type
from back_dev_home.sem_list.contracts import SemListRow


__all__ = ["RosterIndex", "build_index", "load_index"]


def _norm(value) -> str:
    """Roster text arrives from parquet/Redis cells carrying case and spaces."""
    return str(value or "").strip().upper()


@dataclass(frozen=True)
class RosterIndex:
    """Two lookups over one pass of the roster.

    ``fac_id_by_fab`` is what makes the cache key coarse: M16A, M16B and M16C
    all resolve to M16, so they share one cache entry and one office call.
    ``placement_by_eqp`` is what puts an alarm on the right board.
    """

    fac_id_by_fab: dict[str, str]
    placement_by_eqp: dict[str, tuple[str, ToolType]]

    def fac_id_for(self, fab_name: str) -> str | None:
        return self.fac_id_by_fab.get(_norm(fab_name))

    def placement_of(self, eqp_id: str) -> tuple[str, ToolType] | None:
        return self.placement_by_eqp.get(_norm(eqp_id))

    def has_tools(self, tool_type: ToolType, fab_name: str) -> bool:
        fab = _norm(fab_name)
        return any(
            placed_fab == fab and placed_type == tool_type
            for placed_fab, placed_type in self.placement_by_eqp.values()
        )


def build_index(rows: Iterable[SemListRow]) -> RosterIndex:
    fac_id_by_fab: dict[str, str] = {}
    placement_by_eqp: dict[str, tuple[str, ToolType]] = {}

    for row in rows:
        fab = _norm(row.get("fab_name"))
        fac = _norm(row.get("fac_id"))
        if fab and fac:
            fac_id_by_fab.setdefault(fab, fac)

        # None for AMAT VeritySEM/Provision, which are not on this board.
        tool_type = model_to_tool_type(row.get("eqp_model_cd", ""))
        eqp = _norm(row.get("eqp_id"))
        if eqp and fab and tool_type is not None:
            placement_by_eqp[eqp] = (fab, tool_type)

    return RosterIndex(fac_id_by_fab, placement_by_eqp)


def load_index() -> RosterIndex:
    from back_dev_home.sem_list.data import get_sem_list

    return build_index(get_sem_list())
