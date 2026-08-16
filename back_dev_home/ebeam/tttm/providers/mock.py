"""Phase-1 TTTM mock provider — generates a fleet-shaped payload per fab.

The fleet is NOT invented here. It is `sem_list` filtered to the requested
`fab_name` and to the tool family the slug names, exactly the way
`ebeam/storage/providers/mock.py` derives its rows, so the eqp_ids the skew
screen offers for selection are the same physical tools every other screen
shows for that fab. The previous version of this module read one hand-written
fixture (`__fixtures__/tttm_cdsem_r3.json`, five tools called `EQP01…EQP05`),
which meant every fab but R3 answered `available: false` and R3 itself offered
a roster no other page had ever heard of. `__fixtures__` is still written, but
now by `scripts/capture_fixtures.py` capturing this generator's output — the
frozen shape example for the office side, not an input.

Deliberate properties of the generated payload, so a later edit does not
flatten them by accident:

- **One latent bias per tool drives everything.** `consensus_deviation`,
  `fleet_today.matrix`, every cell matrix and the trend all derive from the
  same per-tool bias, so a tool that reads high against consensus also reads
  high against each of its partners. The old fixture had the two views
  disagree (documented there as a known departure); a generator has no reason
  to, and the frontend's N배화 grouping only means something when the pairwise
  numbers actually contain clusters.
- **The last tool of the roster is the drifted one.** It sits furthest from
  consensus and carries the widest pairwise skews; the tight cluster is what
  the N배화 recommendation is built from.
- **One pair exceeds `tolerance_range.max`** — the first tool against the
  drifted one in the `-Y-` cell, pinned at 0.24 nm against the 0.20 nm
  ceiling. Without it the knob at full travel passes everything and the
  tolerance control looks like it has no negative state. That cell is
  `direct`/`High` on purpose, so the failure reads as real rather than as
  low-confidence noise, and it is the Y axis only — an axis-specific drift is
  more plausible than a uniform one.
- **The drifted tool's row is entirely null in the predicted cell.** That is
  the "no overlapping measurement" case the frontend must not place on the
  fleet map; see `utils/fleetMap.ts`.
- **The three cells sit at three different CDs** (32.4 / 31.8 / 68.0 nm), and
  the third is in a different `cd_band` from the other two on purpose. The
  PM/BM limit is 1% of CD, so those cells carry limits of 0.324 / 0.318 /
  0.680 nm — spread wide enough that a screen quietly reusing one absolute
  limit is visibly wrong rather than plausibly close.
- **The over-tolerance pair is still INSIDE its own PM/BM limit.** 0.24 nm
  exceeds the 0.20 nm tolerance ceiling but sits under that cell's 0.318 nm
  action limit. The contrast is the point: the tolerance knob is a matching
  goal for N배화, the action limit is fab policy about one tool against
  consensus, and a fixture at smaller CDs would teach them as one number.
- **`consensus_deviation` is kept inside ±0.15 nm**, the fab's tool management
  limit — a tool outside it goes to PM/BM (user-confirmed 2026-08-16). The
  widest is the drifted tool at -0.13, so the demo fleet is "all in spec, but
  one tool is close to the edge" rather than "one tool already needs PM". The
  frontend derives that limit as 1% of `fleet_today.median_cd_nm` (15.1 nm
  here, the monitor wafer → 0.151 nm) rather than from a constant, so raising
  the fleet CD raises the limit too. Pushing a deviation past it turns that
  tool red and says PM/BM, so move these knowing what you are asserting.
- **A fab with fewer than two tools answers `available: false`.** One tool is
  not a comparison, and the frontend's picker refuses to drop below two
  anyway; some HV-SEM fabs really do hold a single tool.
- **The seed includes `recipe_id`**, so picking a recipe visibly recomputes —
  which is what the picker promises. The numbers move; the shape does not.

OFFICE-VERIFY: every number here is fabricated. Real pairwise skew magnitudes
and the true spread across cells are unknown until an office run — item 3 of
`docs/research/2026-08-16-skew-tttm-feasibility.md` section 6.

OFFICE-VERIFY: `consensus` is assumed to be the **median** (the fab states the
rule against a median). The office adapter must not use a mean — one drifted
tool would drag the reference and shift every other tool's deviation.
"""

import random
import zlib
from datetime import date, timedelta
from statistics import median
from typing import NamedTuple

from back_dev_home.ebeam._tool_specs import (
    SLUG_TO_TOOL_TYPE,
    model_to_tool_type,
)
from back_dev_home.ebeam.tttm.contracts import (
    CellSkew,
    ConsensusDeviation,
    EpochMarker,
    MdcHistoryEntry,
    ProductionCorroboration,
    ProductionOverlapRow,
    SkewMatrixBlock,
    ToolRef,
    TrendPoint,
    TttmCheckPayload,
)
from back_dev_home.sem_list.providers.mock import get_sem_list


# Frozen "today" — the mock is a demo, and a payload whose dates move with the
# wall clock makes one screenshot impossible to compare against the next.
_TODAY = date(2026, 5, 31)
_FETCHED_AT = "2026-05-31T14:30:00"

# Monitor-wafer CD behind today's fleet check. 1% of it is the ±0.151 nm PM/BM
# line the frontend draws.
_FLEET_MEDIAN_CD_NM = 15.1

_TOLERANCE_RANGE = {"min": 0.01, "max": 0.2, "step": 0.005}
_CURRENT_TOLERANCE = 0.05
# The one pair pinned above `_TOLERANCE_RANGE["max"]`; see the module docstring.
_BREACH_SKEW = 0.24
_DRIFTED_DEVIATION = -0.13


class _CellSpec(NamedTuple):
    cell_id: str
    beam_condition: str
    axis: str
    cd_band: str
    median_cd_nm: float
    mdc_epoch: str
    tier: str
    confidence: str
    # Multiplies every tool's bias in this cell, so the cells are not three
    # copies of one matrix.
    bias_scale: float


_CELLS: tuple[_CellSpec, ...] = (
    _CellSpec("bc1-X-25-50-e7", "BC1", "X", "25-50", 32.4, "e7", "direct", "High", 0.9),
    _CellSpec("bc1-Y-25-50-e7", "BC1", "Y", "25-50", 31.8, "e7", "direct", "High", 1.1),
    _CellSpec("bc2-X-50-100-e7", "BC2", "X", "50-100", 68.0, "e7", "predicted", "Med", 1.0),
)


def _seed(tool_slug: str, fab_name: str, recipe_id: str | None) -> int:
    # crc32, not hash(): PYTHONHASHSEED is randomised per process, so hash()
    # would hand a different fleet to every worker and to every restart.
    key = f"{tool_slug}|{fab_name.upper()}|{recipe_id or ''}"
    return zlib.crc32(key.encode("utf-8"))


def _fleet(tool_slug: str, fab_name: str) -> list[ToolRef]:
    """The fab's roster for this tool family, straight from sem_list."""
    tool_type = SLUG_TO_TOOL_TYPE.get(tool_slug)  # type: ignore[arg-type]
    if tool_type is None:
        return []
    target = fab_name.strip().upper()
    rows = [
        row for row in get_sem_list()
        # fab_name, not fac_id: fac_id is fac-level (`M16` for `M16A`) and
        # would fold three fabs into one roster. See the fab_name/fac_id note
        # in tests/test_contract.py.
        if row["fab_name"].strip().upper() == target
        and model_to_tool_type(row["eqp_model_cd"]) == tool_type
    ]
    # Deduplicated by eqp_id, because eqp_id INDEXES the skew matrix: a roster
    # naming the same tool twice yields two identical axes, and the client's
    # clique grouping would then report a tool as matching itself. The mock
    # roster really does collide (sem_list rolls ids at random — 10 of its 300
    # rows share an id with another), and an office roster joined across two
    # frames can just as easily hand back a tool twice.
    seen: set[str] = set()
    fleet: list[ToolRef] = []
    # Sorted by eqp_id so "the last tool is the drifted one" is a stable
    # property of the fab rather than of sem_list's row order.
    for row in sorted(rows, key=lambda r: r["eqp_id"]):
        eqp_id = row["eqp_id"]
        if eqp_id in seen:
            continue
        seen.add(eqp_id)
        fleet.append(
            ToolRef(eqp_id=eqp_id, label=eqp_id, eqp_model_cd=row["eqp_model_cd"])
        )
    return fleet


def _biases(rng: random.Random, fleet: list[ToolRef]) -> dict[str, float]:
    """Per-tool latent skew (nm) against the fleet consensus.

    Mostly tight, a few middling, one wide — a fleet whose tools all sit the
    same distance apart has no clusters, and the whole N배화 recommendation is
    about finding the cluster.
    """
    biases: dict[str, float] = {}
    for tool in fleet:
        draw = rng.random()
        if draw < 0.6:
            spread = 0.02
        elif draw < 0.9:
            spread = 0.06
        else:
            spread = 0.11
        biases[tool["eqp_id"]] = round(rng.uniform(-spread, spread), 3)
    # The drifted tool is pinned, not drawn: the demo has to show one tool near
    # (but inside) the ±0.15 nm management limit for every fab.
    biases[fleet[-1]["eqp_id"]] = _DRIFTED_DEVIATION
    return biases


def _matrix(
    ids: list[str],
    biases: dict[str, float],
    rng: random.Random,
    scale: float,
    *,
    null_id: str | None = None,
) -> SkewMatrixBlock:
    """|bias difference| + a little noise, symmetric with a zero diagonal.

    Built triangle-first and mirrored, so symmetry is structural rather than
    something a later edit could break — the client's maximal-clique grouping
    reads both halves and would silently produce different groups.
    """
    size = len(ids)
    values: list[list[float | None]] = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1, size):
            if null_id is not None and null_id in (ids[i], ids[j]):
                # "This pair was never measured together in this cell" — null,
                # not zero, which would read as a perfect match.
                values[i][j] = values[j][i] = None
                continue
            gap = abs(biases[ids[i]] - biases[ids[j]]) * scale
            skew = round(gap + rng.uniform(0.0, 0.02), 3)
            values[i][j] = values[j][i] = skew
    return SkewMatrixBlock(tools=list(ids), values=values)


def _cells(fleet: list[ToolRef], biases: dict[str, float], seed: int) -> list[CellSkew]:
    ids = [tool["eqp_id"] for tool in fleet]
    drifted = ids[-1]
    cells: list[CellSkew] = []
    for index, spec in enumerate(_CELLS):
        rng = random.Random(seed + 101 * (index + 1))
        predicted = spec.tier == "predicted"
        block = _matrix(
            ids,
            biases,
            rng,
            spec.bias_scale,
            null_id=drifted if predicted else None,
        )
        if spec.axis == "Y":
            # The one deliberate failure, pinned after the fact so it survives
            # any change to the bias distribution.
            drifted_index = ids.index(drifted)
            block["values"][0][drifted_index] = _BREACH_SKEW
            block["values"][drifted_index][0] = _BREACH_SKEW
        cells.append(
            CellSkew(
                cell_id=spec.cell_id,
                beam_condition=spec.beam_condition,
                axis=spec.axis,  # type: ignore[typeddict-item]
                cd_band=spec.cd_band,
                median_cd_nm=spec.median_cd_nm,
                mdc_epoch=spec.mdc_epoch,
                tier=spec.tier,  # type: ignore[typeddict-item]
                confidence=spec.confidence,  # type: ignore[typeddict-item]
                labels=["특수각 포함"] if predicted else [],
                direct_skew_matrix=None if predicted else block,
                predicted_skew_matrix=block if predicted else None,
            )
        )
    return cells


def _trend(fleet: list[ToolRef], biases: dict[str, float], rng: random.Random) -> list[TrendPoint]:
    dates = [(_TODAY - timedelta(days=7 * back)).isoformat() for back in range(4, -1, -1)]
    return [
        TrendPoint(
            eqp_id=tool["eqp_id"],
            date=day,
            skew=round(biases[tool["eqp_id"]] + rng.uniform(-0.015, 0.015), 3),
        )
        for tool in fleet
        for day in dates
    ]


def _markers(fleet: list[ToolRef]) -> list[EpochMarker]:
    markers = [
        EpochMarker(
            eqp_id=fleet[-1]["eqp_id"],
            date=(_TODAY - timedelta(days=3)).isoformat(),
            kind="hard",
            mdc_changed=True,
            label="PM + MDC 변경 (epoch 리셋)",
        )
    ]
    if len(fleet) > 2:
        markers.append(
            EpochMarker(
                eqp_id=fleet[1]["eqp_id"],
                date=(_TODAY - timedelta(days=4)).isoformat(),
                kind="soft",
                mdc_changed=False,
                label="BM (MDC 불변)",
            )
        )
    return markers


def _mdc_history(fleet: list[ToolRef]) -> list[MdcHistoryEntry]:
    drifted = fleet[-1]["eqp_id"]
    changed_on = (_TODAY - timedelta(days=3)).isoformat()
    return [
        MdcHistoryEntry(
            eqp_id=drifted,
            beam_condition="BC1",
            axis="X",
            date=changed_on,
            old_value=1.0012,
            new_value=1.0007,
        ),
        MdcHistoryEntry(
            eqp_id=drifted,
            beam_condition="BC1",
            axis="Y",
            date=changed_on,
            old_value=1.0009,
            new_value=1.0005,
        ),
    ]


def _corroboration(fleet: list[ToolRef], biases: dict[str, float]) -> ProductionCorroboration:
    """Production overlap for the three best-matched pairs.

    OFFICE-VERIFY: production data is not TTTM data, hence the permanent
    "TTTM 미반영" note. The overlap standing in here is derived from the same
    biases, which is a fabricated correlation — at the office the two come
    from genuinely different measurements and may disagree.
    """
    ids = [tool["eqp_id"] for tool in fleet]
    pairs = sorted(
        (abs(biases[a] - biases[b]), a, b)
        for i, a in enumerate(ids)
        for b in ids[i + 1:]
    )[:3]
    return ProductionCorroboration(
        level="mid",
        note="TTTM 미반영",
        detail=[
            ProductionOverlapRow(pair=f"{a}·{b}", overlap=round(0.9 - gap * 2, 2))
            for gap, a, b in pairs
        ],
    )


def _unavailable(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
    summary: str,
) -> TttmCheckPayload:
    return {
        "tool_slug": tool_slug,  # type: ignore[typeddict-item]
        "fab_name": fab_name,
        "recipe_id": recipe_id,
        "available": False,
        "fetched_at": "",
        "summary": summary,
        "tools": [],
        "current_tolerance": _CURRENT_TOLERANCE,
        "tolerance_range": _TOLERANCE_RANGE,  # type: ignore[typeddict-item]
        "occupied_cells": [],
        "production_corroboration": {"level": "low", "note": "TTTM 미반영", "detail": []},
        "fleet_today": {
            "matrix": {"tools": [], "values": []},
            "consensus_deviation": [],
            "median_cd_nm": None,
        },
        "trend": [],
        "epoch_markers": [],
        "mdc_history": [],
    }


def get_tttm_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
) -> TttmCheckPayload:
    fleet = _fleet(tool_slug, fab_name)
    if not fleet:
        return _unavailable(
            tool_slug,
            fab_name,
            recipe_id,
            f"{fab_name} 에는 이 계열의 장비가 없습니다.",
        )
    if len(fleet) < 2:
        return _unavailable(
            tool_slug,
            fab_name,
            recipe_id,
            f"{fab_name} 에는 이 계열 장비가 1대뿐이라 장비간 스큐를 볼 수 없습니다.",
        )

    seed = _seed(tool_slug, fab_name, recipe_id)
    biases = _biases(random.Random(seed), fleet)
    ids = [tool["eqp_id"] for tool in fleet]

    consensus = median(biases.values())
    deviations = [
        ConsensusDeviation(eqp_id=eqp_id, deviation=round(biases[eqp_id] - consensus, 3))
        for eqp_id in ids
    ]

    cells = _cells(fleet, biases, seed)
    direct = sum(1 for cell in cells if cell["tier"] == "direct")

    return {
        "tool_slug": tool_slug,  # type: ignore[typeddict-item]
        "fab_name": fab_name,
        "recipe_id": recipe_id,
        "available": True,
        "fetched_at": _FETCHED_AT,
        "summary": (
            f"{fab_name} 장비 그룹 {len(fleet)}대 · 점유 셀 {len(cells)}개"
            f"(직접 {direct} · 예측 {len(cells) - direct}) 기준 추천입니다."
        ),
        "tools": fleet,
        "current_tolerance": _CURRENT_TOLERANCE,
        "tolerance_range": _TOLERANCE_RANGE,  # type: ignore[typeddict-item]
        "occupied_cells": cells,
        "production_corroboration": _corroboration(fleet, biases),
        "fleet_today": {
            "matrix": _matrix(ids, biases, random.Random(seed + 7), 1.0),
            "consensus_deviation": deviations,
            "median_cd_nm": _FLEET_MEDIAN_CD_NM,
        },
        "trend": _trend(fleet, biases, random.Random(seed + 11)),
        "epoch_markers": _markers(fleet),
        "mdc_history": _mdc_history(fleet),
    }
