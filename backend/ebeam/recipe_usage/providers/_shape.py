"""Redis 키 레지스트리와 mock·office 공용 집계.

provider 는 세 가지 raw 로더만 제공합니다 -- `load_list_rows`,
`load_usage_rows`, `load_resident`. 값은 Redis 키의 컬럼 모양 그대로이고,
여기서 계약(`contracts.py`) 모양으로 접습니다. 집계가 한 곳에 있으므로 office
어댑터는 "Redis 를 읽고 타입을 맞추는" 일만 합니다(`office.py` 는 gitignore 된
사본이라, 거기 든 규칙은 한 대의 기계에만 배포됩니다).

스키마 원본: docs/datatables/veritysem/recipe_usage.txt

여기서 지키는 규칙 (user-confirmed 2026-11-12):

* 명부는 sem_list 뿐입니다. 키에는 있으나 명부에 없는 장비의 행은 버리고,
  명부에는 있으나 실적이 없는 장비는 0 으로 남깁니다.
* fab 범위는 명부의 fab_name 으로 정합니다. 키의 fab_name / fac_id 컬럼은 읽지
  않습니다(fac_id=R3 · fab_name=R4 조합이 실재합니다).
* list 키의 grain 은 (eqp_id, recipe_id, fab_id) 입니다. (eqp_id, recipe_id) 는
  유일하지 않으므로 fab_id 를 가로질러 n_uses 는 더하고 first/last 는 min/max
  합니다. fab_id 는 응답에 나가지 않습니다.
* recipe_id 는 통짜 문자열입니다. 어디서도 "/" 로 자르지 않습니다 -- VeritySEM
  은 4조각이 아닌 id 가 실재합니다. Provision 의 split 컬럼은 키가 준 값만
  옮깁니다.
* usage 의 기간은 행의 dt 로만 셉니다. 90일 창을 가정하지 않습니다.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Iterable, Mapping, NamedTuple, NotRequired, TypedDict

from backend.ebeam._tool_specs import model_to_tool_type
from backend.ebeam.recipe_usage.contracts import (
    AmatToolType,
    CatalogResponse,
    RecipeDetailResponse,
    StatusResponse,
)


SPLIT_COLUMNS = ("product_id", "layer_id", "recipe_name")
_LIST_COLUMNS = (
    "eqp_id", "fac_id", "fab_name", "fab_id", "recipe_id",
    "n_uses", "first_used", "last_used",
)
USAGE_COLUMNS = (
    "dt", "eqp_id", "fac_id", "fab_name", "recipe_id",
    "runs", "wafers", "meas_min", "fail_runs", "first_start", "last_start",
)

DEFAULT_WINDOW_DAYS = 14
MAX_WINDOW_DAYS = 366


class WindowError(ValueError):
    """요청한 기간이 뒤집혔거나 너무 깁니다. 라우트가 400 으로 답합니다."""


class FamilyKeys(NamedTuple):
    list_key: str
    list_columns: tuple[str, ...]
    usage_key: str
    resident_hash: str
    # 문서에만 있고 읽지 않습니다: recipe -> [eqp_id] 는 resident_hash 를 뒤집은
    # 것과 같은 관계라서, 읽으면 fab 마다 키 하나씩 왕복만 늘어납니다.
    tools_in_rcp_pattern: str


FAMILY_KEYS: dict[AmatToolType, FamilyKeys] = {
    "veritysem": FamilyKeys(
        list_key="v3_df_verity_recipes",
        list_columns=_LIST_COLUMNS,
        usage_key="v3_df_verity_recipe_usage",
        resident_hash="v3_verity_unique_rcp_list",
        tools_in_rcp_pattern="v3_verity_tools_in_rcp_{fab}",
    ),
    "provision": FamilyKeys(
        list_key="v3_df_provision_recipes",
        list_columns=_LIST_COLUMNS + SPLIT_COLUMNS,
        usage_key="v3_df_provision_recipe_usage",
        # OFFICE-VERIFY: Provision 에도 같은 모양의 키가 있다는 것까지만
        # 확인되었고(user-confirmed 2026-11-12) 이름은 VeritySEM 에서 유추했습니다.
        resident_hash="v3_provision_unique_rcp_list",
        tools_in_rcp_pattern="v3_provision_tools_in_rcp_{fab}",
    ),
}


class ListRow(TypedDict):
    eqp_id: str
    fac_id: str
    fab_name: str
    fab_id: str
    recipe_id: str
    n_uses: int
    first_used: str
    last_used: str
    product_id: NotRequired[str]
    layer_id: NotRequired[str]
    recipe_name: NotRequired[str]


class UsageRow(TypedDict):
    dt: str
    eqp_id: str
    fac_id: str
    fab_name: str
    recipe_id: str
    runs: int
    wafers: int
    meas_min: float
    fail_runs: int
    first_start: str
    last_start: str


Resident = Mapping[str, Iterable[str]]


class RosterTool(NamedTuple):
    eqp_id: str
    fab_name: str
    eqp_model_cd: str


Roster = dict[str, RosterTool]


def family_roster(sem_rows: Iterable[Mapping], tool_type: AmatToolType) -> Roster:
    """sem_list 에서 이 계열 장비만, eqp_id 당 한 행(먼저 나온 행)으로."""
    roster: Roster = {}
    for row in sem_rows:
        if model_to_tool_type(row["eqp_model_cd"]) != tool_type:
            continue
        eqp_id = str(row["eqp_id"]).strip()
        if eqp_id:
            roster.setdefault(eqp_id, RosterTool(
                eqp_id, str(row["fab_name"]).strip(), str(row["eqp_model_cd"]).strip(),
            ))
    return roster


def _in_fabs(roster: Roster, fab_names: Iterable[str]) -> Roster:
    wanted = {name.strip().upper() for name in fab_names if name.strip()}
    if not wanted:
        return roster
    return {
        eqp_id: tool for eqp_id, tool in roster.items()
        if tool.fab_name.upper() in wanted
    }


def _earliest(a: str | None, b: str | None) -> str | None:
    return min(filter(None, (a, b)), default=None)


def _latest(a: str | None, b: str | None) -> str | None:
    return max(filter(None, (a, b)), default=None)


class _Seen:
    """list 키의 여러 행(fab_id 별)을 하나로 접은 것."""

    def __init__(self) -> None:
        self.n_uses = 0
        self.first_used: str | None = None
        self.last_used: str | None = None
        self.in_mes = False
        self.on_tool = False

    def add(self, row: ListRow) -> None:
        self.n_uses += row["n_uses"]
        self.first_used = _earliest(self.first_used, row["first_used"])
        self.last_used = _latest(self.last_used, row["last_used"])
        self.in_mes = True


class _CatalogCell(_Seen):
    def __init__(self) -> None:
        super().__init__()
        self.eqp_ids: set[str] = set()
        self.split = ("", "", "")


def build_catalog(
    tool_type: AmatToolType,
    fab_names: tuple[str, ...],
    roster: Roster,
    list_rows: Iterable[ListRow],
    resident: Resident,
) -> CatalogResponse:
    """(recipe_id, 명부 fab_name) 당 한 행. list 키와 장비 상주 hash 의 합집합."""
    scope = _in_fabs(roster, fab_names)
    cells: dict[tuple[str, str], _CatalogCell] = defaultdict(_CatalogCell)

    for row in list_rows:
        tool = scope.get(row["eqp_id"])
        if tool is None:
            continue
        cell = cells[(row["recipe_id"], tool.fab_name)]
        cell.add(row)
        cell.eqp_ids.add(tool.eqp_id)
        cell.split = tuple(row.get(column, "") for column in SPLIT_COLUMNS)

    for eqp_id, recipe_ids in resident.items():
        tool = scope.get(eqp_id)
        if tool is None:
            continue
        for recipe_id in recipe_ids:
            cell = cells[(recipe_id, tool.fab_name)]
            cell.on_tool = True
            cell.eqp_ids.add(tool.eqp_id)

    rows = [
        {
            "recipe_id": recipe_id,
            "fab_name": fab_name,
            "product_id": cell.split[0],
            "layer_id": cell.split[1],
            "recipe_name": cell.split[2],
            "eqp_ids": sorted(cell.eqp_ids),
            "n_uses": cell.n_uses,
            "first_used": cell.first_used,
            "last_used": cell.last_used,
            "source": (
                "both" if cell.in_mes and cell.on_tool
                else "mes" if cell.in_mes else "tool"
            ),
        }
        for (recipe_id, fab_name), cell in sorted(cells.items())
    ]
    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names),
        "total": len(rows),
        "rows": rows,
    }


class _Totals:
    def __init__(self) -> None:
        self.runs = 0
        self.wafers = 0
        self.meas_min = 0.0
        self.fail_runs = 0
        self.last_start: str | None = None

    def add(self, row: UsageRow) -> None:
        self.runs += row["runs"]
        self.wafers += row["wafers"]
        self.meas_min += row["meas_min"]
        self.fail_runs += row["fail_runs"]
        self.last_start = _latest(self.last_start, row["last_start"])

    def sums(self) -> dict:
        return {
            "runs": self.runs,
            "wafers": self.wafers,
            "meas_min": round(self.meas_min, 2),
            "fail_runs": self.fail_runs,
        }

    def rated(self) -> dict:
        # avg_meas_min 은 fail_runs 가 많으면 낮게 나옵니다: JobEnd 가 없는 작업은
        # meas_min 이 0 인 채로 runs 에는 들어갑니다. 키가 이유를 저장하지 않으므로
        # 보정하지 않고 그대로 냅니다.
        return {
            **self.sums(),
            "fail_rate": round(self.fail_runs / self.runs, 4) if self.runs else 0.0,
            "avg_meas_min": round(self.meas_min / self.runs, 2) if self.runs else 0.0,
        }


def build_recipe_detail(
    tool_type: AmatToolType,
    recipe_id: str,
    fab_names: tuple[str, ...],
    roster: Roster,
    list_rows: Iterable[ListRow],
    usage_rows: Iterable[UsageRow],
    resident: Resident,
) -> RecipeDetailResponse:
    scope = _in_fabs(roster, fab_names)
    seen: dict[str, _Seen] = defaultdict(_Seen)

    for row in list_rows:
        if row["recipe_id"] == recipe_id and row["eqp_id"] in scope:
            seen[row["eqp_id"]].add(row)
    for eqp_id, recipe_ids in resident.items():
        if eqp_id in scope and recipe_id in recipe_ids:
            seen[eqp_id].on_tool = True

    daily: dict[str, _Totals] = defaultdict(_Totals)
    for row in usage_rows:
        if row["recipe_id"] == recipe_id and row["eqp_id"] in scope:
            daily[row["dt"]].add(row)

    return {
        "tool_type": tool_type,
        "recipe_id": recipe_id,
        "fab_names": list(fab_names),
        "tools": [
            {
                "eqp_id": eqp_id,
                "fab_name": scope[eqp_id].fab_name,
                "n_uses": tool.n_uses,
                "first_used": tool.first_used,
                "last_used": tool.last_used,
                "on_tool": tool.on_tool,
            }
            for eqp_id, tool in sorted(seen.items())
        ],
        "daily": [{"date": dt, **daily[dt].sums()} for dt in sorted(daily)],
    }


def _window(
    start: date | None, end: date | None, anchor: str | None, today: date
) -> tuple[date, date]:
    if end is None:
        # 오늘 dt 는 존재하지 않습니다 -- 행이 하나도 없을 때의 기본값도 전날입니다.
        end = date.fromisoformat(anchor) if anchor else today - timedelta(days=1)
    if start is None:
        start = end - timedelta(days=DEFAULT_WINDOW_DAYS - 1)
    if end < start:
        raise WindowError("end_date is before start_date")
    if (end - start).days >= MAX_WINDOW_DAYS:
        raise WindowError(f"date window is longer than {MAX_WINDOW_DAYS} days")
    return start, end


def build_status(
    tool_type: AmatToolType,
    fab_names: tuple[str, ...],
    roster: Roster,
    usage_rows: Iterable[UsageRow],
    start: date | None,
    end: date | None,
    today: date,
) -> StatusResponse:
    """기간 요약. 기본 기간은 anchor_date 로 끝나는 14일입니다.

    `anchor_date` / `data_start` 는 fab 필터와 무관하게 이 계열 명부 장비의 행
    전체에서 구합니다 -- 적재된 데이터의 범위이지 선택한 fab 의 실적이 아니라서,
    fab 을 바꿀 때마다 날짜 선택기의 한계가 움직이면 안 됩니다.

    기간이 뒤집혔거나 `MAX_WINDOW_DAYS` 를 넘으면 `WindowError` 입니다.
    """
    family_rows = [row for row in usage_rows if row["eqp_id"] in roster]
    anchor = max((row["dt"] for row in family_rows), default=None)
    data_start = min((row["dt"] for row in family_rows), default=None)
    start, end = _window(start, end, anchor, today)
    start_date, end_date = start.isoformat(), end.isoformat()
    scope = _in_fabs(roster, fab_names)

    total = _Totals()
    by_day: dict[str, _Totals] = defaultdict(_Totals)
    by_recipe: dict[str, _Totals] = defaultdict(_Totals)
    by_tool: dict[str, _Totals] = defaultdict(_Totals)
    recipe_tools: dict[str, set[str]] = defaultdict(set)
    tool_recipe_runs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in family_rows:
        eqp_id, recipe_id = row["eqp_id"], row["recipe_id"]
        if eqp_id not in scope or not start_date <= row["dt"] <= end_date:
            continue
        for totals in (total, by_day[row["dt"]], by_recipe[recipe_id], by_tool[eqp_id]):
            totals.add(row)
        recipe_tools[recipe_id].add(eqp_id)
        tool_recipe_runs[eqp_id][recipe_id] += row["runs"]

    days = [
        (start + timedelta(days=offset)).isoformat()
        for offset in range((end - start).days + 1)
    ]
    recipes = [
        {
            "recipe_id": recipe_id,
            **totals.rated(),
            "eqp_ids": sorted(recipe_tools[recipe_id]),
            "fab_names": sorted({scope[e].fab_name for e in recipe_tools[recipe_id]}),
            "last_start": totals.last_start,
        }
        for recipe_id, totals in by_recipe.items()
    ]
    equipments = []
    for eqp_id, tool in scope.items():
        totals = by_tool.get(eqp_id) or _Totals()
        recipe_runs = tool_recipe_runs.get(eqp_id, {})
        equipments.append({
            "eqp_id": eqp_id,
            "fab_name": tool.fab_name,
            "eqp_model_cd": tool.eqp_model_cd,
            **totals.rated(),
            "recipe_count": len(recipe_runs),
            "top_recipe": min(
                recipe_runs, key=lambda r: (-recipe_runs[r], r), default=None
            ),
            "last_start": totals.last_start,
        })

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names),
        "start_date": start_date,
        "end_date": end_date,
        "anchor_date": anchor,
        "data_start": data_start,
        "summary": {
            **total.rated(),
            "recipe_count": len(by_recipe),
            "active_tool_count": sum(1 for t in by_tool.values() if t.runs > 0),
            "tool_count": len(scope),
        },
        "daily": [
            {"date": day, **(by_day.get(day) or _Totals()).sums()} for day in days
        ],
        "recipes": sorted(recipes, key=lambda r: (-r["meas_min"], r["recipe_id"])),
        "equipments": sorted(equipments, key=lambda r: (-r["meas_min"], r["eqp_id"])),
    }
