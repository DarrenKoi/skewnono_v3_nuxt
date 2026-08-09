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

from back_dev_home.ebeam._tool_specs import SEM_TOOL_TYPES, ToolType, model_to_tool_type
from back_dev_home.sem_list.contracts import SemListRow


__all__ = ["RosterIndex", "build_index", "load_index", "norm"]


def norm(value: object) -> str:
    """Roster text arrives from parquet/Redis cells carrying case and spaces.

    Public because callers compare their own inputs against index keys, and a
    caller that normalized differently would simply match nothing — an empty
    board, not an error.
    """
    return str(value or "").strip().upper()


@dataclass(frozen=True)
class RosterIndex:
    """Two lookups over one pass of the roster.

    ``fac_id_by_placement`` answers both questions the reader has, in one
    call: is this (fab, tool family) a thing we serve, and which facility's
    cache holds it. Keying it by the PAIR is what makes "configured" and
    "which fac_id" impossible to disagree — a fab that resolves is guaranteed
    to have a fac_id, so no caller can build a key out of ``None``.

    ``placement_by_eqp`` is what puts an individual alarm on the right board.
    """

    fac_id_by_placement: dict[tuple[str, ToolType], str]
    placement_by_eqp: dict[str, tuple[str, ToolType]]

    def fac_id_for(self, fab_name: str, tool_type: ToolType) -> str | None:
        """The facility whose board serves this fab, or None if we serve none."""
        return self.fac_id_by_placement.get((norm(fab_name), tool_type))

    def placement_of(self, eqp_id: str) -> tuple[str, ToolType] | None:
        return self.placement_by_eqp.get(norm(eqp_id))

    def eqp_ids_in(self, fab_name: str, tool_type: ToolType) -> list[str]:
        """Every tool of this family in this fab, sorted. Used by the mock."""
        wanted = (norm(fab_name), tool_type)
        return sorted(
            eqp for eqp, placement in self.placement_by_eqp.items()
            if placement == wanted
        )


def build_index(rows: Iterable[SemListRow]) -> RosterIndex:
    fac_id_by_placement: dict[tuple[str, ToolType], str] = {}
    placement_by_eqp: dict[str, tuple[str, ToolType]] = {}

    for row in rows:
        fab = norm(row.get("fab_name"))
        fac = norm(row.get("fac_id"))
        eqp = norm(row.get("eqp_id"))
        # The alarm feed is Hitachi-only (CD-SEM/HV-SEM); AMAT veritysem/
        # provision tools have no alarm board here, so they are excluded on
        # purpose rather than because the classifier used to return None for
        # them. `in SEM_TOOL_TYPES` states that intent directly instead of
        # riding on the classifier's old None-for-AMAT behavior.
        tool_type = model_to_tool_type(row.get("eqp_model_cd", ""))
        if not (fab and tool_type in SEM_TOOL_TYPES):
            continue

        if eqp:
            placement_by_eqp[eqp] = (fab, tool_type)
        # Requires fac too: a row with a blank fac_id cannot name a cache key,
        # so it must not make the fab look servable.
        if fac:
            fac_id_by_placement.setdefault((fab, tool_type), fac)

    return RosterIndex(fac_id_by_placement, placement_by_eqp)


def load_index() -> RosterIndex:
    from back_dev_home.sem_list.data import get_sem_list

    return build_index(get_sem_list())
