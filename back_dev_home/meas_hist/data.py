"""측정 이력(meas_hist) — shared mock data for recipe-search 측정 이력 view and 스큐보아.

Spec: docs/datatables/meas_hist.txt
Each row = "장비가 특정 lot에 특정 recipe를 실행한 1회 측정 이력".
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi._tool_specs import ToolType, model_to_tool_type
from back_dev_home.sem_list.data import SemListRow, get_sem_list


__all__ = ["MeasHistRow", "MeasHistResponse", "ToolType", "get_meas_hist"]


class MeasHistRow(TypedDict):
    id: str
    fac_id: str
    fab_name: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    eqp_id: str
    eqp_model_cd: str
    tool_type: ToolType
    lot_cd: str
    lot_id: str
    class_name: str
    recipe_name: str
    full_name: str
    timestamp: str
    start_time: str
    end_time: str
    meastime: int
    msr: str
    msr_check: Literal["Yes", "No"]
    align_fail: Literal["Pass", "Fail", "NA"]
    total_images: int
    fail_images: int
    fail_ratio: float
    idp_name: str
    idw_name: str


class MeasHistResponse(TypedDict):
    tool_type: ToolType | None
    fab_name: str | None
    recipe_name: str | None
    total: int
    rows: list[MeasHistRow]


RECIPE_CATALOG: dict[str, tuple[str, ...]] = {
    "ADI": ("ADI_CD_BIAS_001", "ADI_PITCH_002", "ADI_CD_BIAS_ABC123_STD_00001", "ADI_CD_BIAS_ABC123_PROD_00006"),
    "AEI": ("AEI_OVERLAY_001", "AEI_CD_002", "AEI_OVERLAY_ABC123_MON_00002"),
    "OVL": ("OVL_BOX_001", "OVL_AIM_002"),
    "GATE": ("GATE_PITCH_001", "GATE_HEIGHT_002", "GATE_PITCH_MON_ABC123_ENG_00009"),
    "CNT": ("CNT_HOLE_001", "CNT_DEPTH_002", "CNT_CONTACT_CHECK_ABC123_QUAL_00008"),
    "QC": ("QC_DAILY_MATCH_001", "QC_DAILY_MATCH_007", "QC_DAILY_MATCH_ABC123_PROD_00007"),
    "DEF": ("DEF_REVIEW_001",),
    "EDGE": ("EDGE_PROFILE_001", "EDGE_PROFILE_SCAN_ABC123_STD_00010")
}

NOW = datetime(2026, 5, 10, tzinfo=timezone.utc)
HISTORY_DAYS = 60
MOCK_ROW_COUNT = 600
SYNTH_ROW_COUNT_RANGE = (8, 20)


def _seed(*values: str | None) -> int:
    digest = hashlib.sha256(":".join(value or "" for value in values).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _r_lot_cd(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTVWXY") for _ in range(3))
    return f"R{letters}"


def _m_lot_cd(rng: random.Random) -> str:
    return rng.choice(("4MJ", "5KP", "6LD", "7HA", "MJD", "KPB"))


def _make_lot_id(lot_cd: str, rng: random.Random) -> str:
    suffix = f"{rng.randint(2400, 2699):04d}{rng.randint(10, 99):02d}"
    return f"{lot_cd}{suffix}"


def _make_msr(date_str: str, recipe_name: str, lot_id: str, eqp_id: str) -> str:
    return f"{date_str}_{recipe_name}_{lot_id}_{eqp_id}"


def _build_row(eqp: SemListRow, rng: random.Random, index: int) -> MeasHistRow | None:
    tool_type = model_to_tool_type(eqp["eqp_model_cd"])
    if tool_type is None:
        return None

    lot_cd = _r_lot_cd(rng) if eqp["fac_id"] == "R3" else _m_lot_cd(rng)
    lot_id = _make_lot_id(lot_cd, rng)

    class_name = rng.choice(tuple(RECIPE_CATALOG.keys()))
    recipe_name = rng.choice(RECIPE_CATALOG[class_name])
    full_name = f"{class_name}/{recipe_name}"

    end_time = NOW - timedelta(
        days=rng.randint(0, HISTORY_DAYS),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59)
    )
    meastime = rng.randint(60, 1800)
    start_time = end_time - timedelta(seconds=meastime)
    timestamp = end_time

    msr_check: Literal["Yes", "No"] = "No" if rng.random() < 0.08 else "Yes"
    align_fail: Literal["Pass", "Fail", "NA"] = rng.choices(
        ("Pass", "Fail", "NA"),
        weights=(0.82, 0.12, 0.06),
        k=1
    )[0]

    if msr_check == "No" or align_fail == "Fail":
        fail_ratio = round(rng.uniform(0.15, 0.8), 4)
    else:
        fail_ratio = round(rng.uniform(0.0, 0.15), 4)

    total_images = rng.randint(40, 400)
    fail_images = int(total_images * fail_ratio)
    fail_ratio = round(fail_images / total_images, 4) if total_images else 0.0

    date_str = end_time.strftime("%Y%m%d")
    msr = _make_msr(date_str, recipe_name, lot_id, eqp["eqp_id"])

    return MeasHistRow(
        id=f"msr_{index:06d}",
        fac_id=eqp["fac_id"],
        fab_name=eqp["fab_name"],
        vendor_nm=eqp["vendor_nm"],
        eqp_id=eqp["eqp_id"],
        eqp_model_cd=eqp["eqp_model_cd"],
        tool_type=tool_type,
        lot_cd=lot_cd,
        lot_id=lot_id,
        class_name=class_name,
        recipe_name=recipe_name,
        full_name=full_name,
        timestamp=timestamp.isoformat().replace("+00:00", "Z"),
        start_time=start_time.isoformat().replace("+00:00", "Z"),
        end_time=end_time.isoformat().replace("+00:00", "Z"),
        meastime=meastime,
        msr=msr,
        msr_check=msr_check,
        align_fail=align_fail,
        total_images=total_images,
        fail_images=fail_images,
        fail_ratio=fail_ratio,
        idp_name=f"/Recipe/{class_name}/{recipe_name}.idp",
        idw_name=f"/Recipe/{class_name}/{recipe_name}.idw"
    )


@lru_cache(maxsize=1)
def _eligible_sem_rows() -> tuple[SemListRow, ...]:
    return tuple(row for row in get_sem_list() if model_to_tool_type(row["eqp_model_cd"]) is not None)


@lru_cache(maxsize=1)
def _all_rows() -> tuple[MeasHistRow, ...]:
    rng = random.Random(_seed("meas_hist", "v1"))
    sem_rows = _eligible_sem_rows()

    rows: list[MeasHistRow] = []
    for index in range(MOCK_ROW_COUNT):
        eqp = rng.choice(sem_rows)
        row = _build_row(eqp, rng, index)
        if row is not None:
            rows.append(row)

    return tuple(rows)


def _split_recipe(recipe_name: str) -> tuple[str, str]:
    if "/" in recipe_name:
        class_part, recipe_part = recipe_name.split("/", 1)
        return class_part, recipe_part
    return "ADI", recipe_name


def _synthesize_for_recipe(
    recipe_name: str,
    tool_type: ToolType | None,
    fab_name: str | None
) -> list[MeasHistRow]:
    rng = random.Random(_seed("synth", recipe_name, fab_name, tool_type))

    sem_rows: list[SemListRow] = list(_eligible_sem_rows())
    if tool_type:
        sem_rows = [row for row in sem_rows if model_to_tool_type(row["eqp_model_cd"]) == tool_type]
    if fab_name:
        sem_rows = [row for row in sem_rows if row["fab_name"].upper() == fab_name.upper()]

    if not sem_rows:
        return []

    class_part, recipe_part = _split_recipe(recipe_name)
    full_name = f"{class_part}/{recipe_part}"

    count = rng.randint(*SYNTH_ROW_COUNT_RANGE)
    rows: list[MeasHistRow] = []

    for index in range(count):
        eqp = rng.choice(sem_rows)
        base = _build_row(eqp, rng, 900_000 + index)
        if base is None:
            continue

        date_str = base["end_time"][:10].replace("-", "")
        rows.append({
            **base,
            "class_name": class_part,
            "recipe_name": recipe_part,
            "full_name": full_name,
            "idp_name": f"/Recipe/{class_part}/{recipe_part}.idp",
            "idw_name": f"/Recipe/{class_part}/{recipe_part}.idw",
            "msr": _make_msr(date_str, recipe_part, base["lot_id"], base["eqp_id"])
        })

    return rows


def _matches_recipe(row: MeasHistRow, recipe_name: str) -> bool:
    return row["full_name"] == recipe_name or row["recipe_name"] == recipe_name


def get_meas_hist(
    tool_type: ToolType | None = None,
    fab_name: str | None = None,
    recipe_name: str | None = None
) -> MeasHistResponse:
    fab_normalized = (fab_name or "").upper() or None

    rows: list[MeasHistRow] = [
        row for row in _all_rows()
        if (not tool_type or row["tool_type"] == tool_type)
        and (not fab_normalized or row["fab_name"].upper() == fab_normalized)
        and (not recipe_name or _matches_recipe(row, recipe_name))
    ]

    if recipe_name and not rows:
        rows = _synthesize_for_recipe(recipe_name, tool_type, fab_normalized)

    rows.sort(key=lambda r: r["timestamp"], reverse=True)

    return MeasHistResponse(
        tool_type=tool_type,
        fab_name=fab_normalized,
        recipe_name=recipe_name,
        total=len(rows),
        rows=rows
    )
