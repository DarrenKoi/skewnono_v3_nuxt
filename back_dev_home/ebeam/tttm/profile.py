"""The per-(tool, parameter) offset profile — ONE derivation for both providers.

The 장비 그룹 배치도 places tools by PCA over this table (the client runs the
PCA; see `front-dev-home/app/utils/parameterPca.ts`). Each column is one
measured parameter of the picked recipe, each row a tool, and each entry the
tool's median CD for that parameter MINUS the fleet's median for it — the same
"tool − consensus" reading `fleet_today.consensus_deviation` gives for the fold,
taken per parameter instead of once.

Tracked and shared, not written twice: the mock fabricates its samples and the
office reads them off run pickles, but "samples → profile" is one formula, and a
guard added to one copy never reaches the other (2026-08 lesson, see
tests/test_office_adapter_parity.py's docstring).

Rules, in the order the client depends on them:

- **Columns are the recipe's whole catalogue, unfiltered** — the same names
  `parameters` lists — so a parameter selection changes which columns the
  client reads, never which columns the server sent. Selecting therefore never
  needs the profile refetched.
- **Consensus is the median across the tools that measured the parameter**,
  never the mean (the fab states its rule against a median; one drifted tool
  would drag a mean).
- **A parameter only one tool measured has no consensus**: its column is kept
  (the catalogue is the catalogue) but every entry is None — one reading
  against itself is not an offset.
- **None means "not measured", never 0** — the client drops a tool from the
  PCA when a selected column is None for it and says so, rather than placing
  it at the consensus as if it matched perfectly.
- **`median_cd_nm` per column** is the CD the offsets were read at, so the
  client can express each column as a fraction of that parameter's own action
  limit (1% of CD) before comparing columns measured at different pattern
  sizes — the same reason `CellSkew.median_cd_nm` exists.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import median

from back_dev_home.ebeam.tttm.contracts import ParameterAxis, ParameterProfile


def build_parameter_profile(
    roster: Sequence[str],
    parameters: Sequence[str],
    samples: Mapping[tuple[str, str], Sequence[float]],
) -> ParameterProfile:
    """``samples[(eqp_id, parameter)]`` → the tool × parameter offset table.

    ``roster`` fixes the row order (the payload's `tools`, so the client can
    align by position or by id alike) and ``parameters`` the column order (the
    payload's own sorted catalogue). A (tool, parameter) with no samples, or an
    empty sample list, is None.
    """
    per_cell: dict[tuple[str, str], float] = {
        key: round(median(values), 3) for key, values in samples.items() if values
    }
    by_parameter: dict[str, list[float]] = {}
    for (_, name), values in samples.items():
        by_parameter.setdefault(name, []).extend(values)
    axes: list[ParameterAxis] = []
    columns: list[dict[str, float]] = []
    for name in parameters:
        readings = {
            eqp_id: per_cell[(eqp_id, name)] for eqp_id in roster if (eqp_id, name) in per_cell
        }
        all_values = by_parameter.get(name, [])
        axes.append(
            ParameterAxis(
                name=name,
                median_cd_nm=round(median(all_values), 3) if all_values else None,
                tools=len(readings),
            )
        )
        if len(readings) < 2:
            columns.append({})
            continue
        consensus = median(readings.values())
        columns.append({eqp_id: round(v - consensus, 3) for eqp_id, v in readings.items()})

    return ParameterProfile(
        parameters=axes,
        tools=list(roster),
        values=[[column.get(eqp_id) for column in columns] for eqp_id in roster],
    )


def empty_parameter_profile() -> ParameterProfile:
    return ParameterProfile(parameters=[], tools=[], values=[])
