"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본 테이블:  docs/datatables/meas_hist.txt
계약:        docs/api-contracts/recipe-tat.yaml
픽스처:      back_dev_home/ebeam/hitachi/recipe_tat/__fixtures__/

Recipe TAT mock data — measurement-history rows aggregated per recipe.

One row in `_generate_meas_hist()` represents a single measurement execution
on one lot, by one tool, of one recipe. The TAT dashboard groups these rows
by (tool_type, recipe_name, class_name) over a date range to surface which
recipes consume the most measurement time.

Schema follows `docs/datatables/meas_hist.txt`. We intentionally drop the
wider columns (msr / align / image counts / idp paths) — TAT only needs
timing, so adding them would bloat payloads without changing the dashboard.

장비 플릿은 sem_list mock에서 옵니다 (_tool_fleet). eqp_id / fab_name /
eqp_model_cd / vendor_nm 을 sem_list row에서 그대로 복사하며, 지어내지
않습니다 — meas_hist.txt 생성 규칙 1과 _tool_specs.py 모듈 docstring이
요구하는 방식입니다. 행 생성 순서는 장비 → lot → 레시피이고, lot은 장비가
선 fab(fac_id)의 것만 뽑습니다.

lot 색인(_lot_index)은 6개 fac_id를 모두 덮습니다 (R3 2000건, M10/M11/M14/
M15/M16 각 400건 — Task 1의 M12→M10 정정 이후). 그래도 lot이 없는 fac이
생기면 그 장비는 측정 없이 남습니다: 다른 fab의 lot으로 조용히 폴백하면
lot이 속한 fab과 장비가 선 fab이 어긋난 행이 생기는데, 그것이야말로 이
mock이 없애려는 비정합입니다.

장비별 고정 스칼라(speed / workload / recipe_lock)가 흉내내는 것은 사무실
데이터의 *값*이 아니라 *장비 사이에 편차가 존재한다는 사실*입니다. 정상
장비의 폭은 speed ±4 %(U(0.96, 1.04)), workload ±8 %(U(0.92, 1.08))입니다.
meastime 식에 들어가는 항은 speed 쪽이므로, "정상 장비의 TAT 편차"로 읽어야
할 숫자는 ±4 %입니다. 이렇게 좁게 둔 근거는 실 플릿의 가동률이 대부분 90 %
이상으로 몰려 있다는 현업 확인입니다(user-confirmed 2026-08-07) — 측정된
분포가 아니라 운영자의 경험칙이며, 여기서 파생되는 배지 임계값은 사무실에서
확인해야 합니다(OFFICE-VERIFY). 자세한 내용은 meas_hist.txt 의 "장비 가동률"
절을 보십시오. R3의 거의 놀고 있는 장비 한 대는 tat_index=None(표본 미달)
경로를 UI에서 밟기 위해 의도적으로 과장한 사례이지 실 데이터에 대한 주장이
아닙니다.

meastime 합으로 계산하는 측정 점유율은 MES 가동률과 같은 수가 아닙니다.
load/unload/idle/PM 이 빠져 있어 언제나 더 낮게 읽힙니다. 그 격차의 크기는
OFFICE-VERIFY 이며, 가동률 기준 임계값을 이 mock 의 점유율에 그대로 옮겨
쓰면 안 됩니다.

측정 물량(TOTAL_MEAS_ROWS)은 집계와 화면을 제대로 돌려보기 위한 최소치이지
사무실 물량이 아닙니다. 실제 CD-SEM은 이보다 훨씬 많이 측정합니다.

사무실 주의사항: ANCHOR_TIME 은 모듈 로드 시점의 wall-clock 입니다. 사무실
구현은 wall-clock 대신 실 인덱스의 max(timestamp) 를 anchor 로 사용해야
합니다. (routes.py 의 _resolve_dates 가 ANCHOR_TIME.date() 를 기본 윈도
끝점으로 사용함을 인지)

Multi-fab filtering (`fab_names`) is a case-insensitive set union — a row
passes if its `fab_name` matches ANY entry; an empty tuple or `None` means
no fab filter at all.
"""

import bisect
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from back_dev_home.ebeam.cdsem.device_statistics.providers.mock import _lot_index
from back_dev_home.ebeam.hitachi._analytics import (
    MeasurementScope,
    fab_base,
    filter_measurements,
    lot_metadata,
    parse_iso_date,
)
from back_dev_home.ebeam.hitachi._tool_specs import model_to_tool_type
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    DailyTrendPoint,
    DeviceRow,
    EquipmentsPayload,
    MeasHistRow,
    RankingRow,
    SummaryPayload,
    ToolType,
)
from back_dev_home.ebeam.hitachi.recipe_tat.providers._shape import (
    build_equipments_payload,
)
from back_dev_home.sem_list.providers import mock as sem_list_mock


__all__ = [
    "ANCHOR_TIME",
    "ToolType",
    "MeasHistRow",
    "get_meas_hist",
    "get_ranking",
    "get_summary",
    "get_daily_trend",
    "get_devices",
    "get_equipments",
]


# Anchor the mock-data window on wall-clock now (captured once per process)
# instead of device_statistics' BASE_TIME. The TAT dashboard defaults to
# "today minus 30 days" in any deployment phase per CLAUDE.md's cross-phase
# principle — anchoring on a fixed mock date would force the frontend to
# special-case Phase 1 vs 2/3.
#
# KST, not UTC: every deployment phase serves Korean fabs, and a UTC anchor
# makes anchor_date (the 데이터 기준 badge and the default window's end) read
# yesterday's date between 00:00 and 09:00 KST. Korea has no DST, so a fixed
# +09:00 offset is exact and avoids zoneinfo/tzdata availability concerns on
# Windows office hosts.
KST = timezone(timedelta(hours=9), "KST")
ANCHOR_TIME = datetime.now(KST).replace(microsecond=0)


# Recipe class -> baseline meastime range (seconds). QC is fast, ADI/AEI
# are heaviest. This shapes the TAT ranking — without per-class spread the
# dashboard would be uniform noise.
CLASS_MEASTIME_BANDS: dict[str, tuple[int, int]] = {
    "ADI":  (320, 900),
    "AEI":  (280, 820),
    "OVL":  (200, 540),
    "GATE": (240, 700),
    "CNT":  (180, 480),
    "QC":   (60, 200),
    "DEF":  (140, 360),
    "EDGE": (220, 560)
}

# Each fab has a recognizable workload personality so switching fab_name in
# the UI changes both ranking composition and KPI scale, not only row counts.
DEFAULT_CLASS_MIX = tuple(CLASS_MEASTIME_BANDS.keys())
# Keyed by `_fab_base` (e.g. M15A/M15B/M15C all share "M15"); `R3`/`R4`
# stay full names since they have no sub-fab variants.
FAB_CLASS_MIX: dict[str, tuple[str, ...]] = {
    "R3": ("ADI", "ADI", "AEI", "GATE", "OVL", "QC"),
    "R4": ("QC", "QC", "OVL", "CNT", "EDGE", "DEF"),
    "M11": ("DEF", "DEF", "EDGE", "QC", "CNT", "OVL"),
    "M10": ("GATE", "GATE", "CNT", "OVL", "QC", "ADI"),
    "M14": ("ADI", "GATE", "GATE", "EDGE", "AEI", "OVL"),
    "M15": ("AEI", "AEI", "OVL", "QC", "CNT", "DEF"),
    "M16": ("ADI", "ADI", "DEF", "CNT", "GATE", "QC")
}

FAB_MEASTIME_MULTIPLIER: dict[str, float] = {
    "R3": 1.12,
    "R4": 0.82,
    "M11": 0.74,
    "M10": 0.95,
    "M14": 1.25,
    "M15": 1.03,
    "M16": 1.18
}

# Per-class recipe-name templates. {n} is filled with a 3-digit running
# number per recipe instance.
CLASS_RECIPE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "ADI":  ("ADI_CD_BIAS_{n}", "ADI_LINEWIDTH_{n}", "ADI_PROFILE_{n}"),
    "AEI":  ("AEI_CD_BIAS_{n}", "AEI_OVERLAY_{n}"),
    "OVL":  ("OVL_M2M_{n}", "OVL_M2P_{n}"),
    "GATE": ("GATE_CD_{n}", "GATE_PITCH_{n}"),
    "CNT":  ("CNT_DIAM_{n}", "CNT_MATCH_{n}"),
    "QC":   ("QC_DAILY_MATCH_{n}", "QC_PM_{n}"),
    "DEF":  ("DEF_REVIEW_{n}",),
    "EDGE": ("EDGE_PROFILE_{n}",)
}

RECIPE_DEFINITIONS_PER_TOOL = 60      # distinct recipes per tool_type
TOTAL_MEAS_ROWS = 55_000              # 기본 조회(fab 1개·14일)에서 장비당 ~25건
HISTORY_WINDOW_DAYS = 180             # 90일 프리셋에 2배 여유

ACTIVE_TOOLS_PER_FAB = 5    # (tool_type, fab_name) 칸마다 실제로 측정하는 장비 수


@lru_cache(maxsize=1)
def _tool_fleet() -> dict[ToolType, tuple[dict, ...]]:
    """sem_list 명부에서 활성 장비를 뽑고 장비별 고정 스칼라를 붙입니다.

    eqp_id는 절대 지어내지 않습니다 — sem_list가 장비 명부의 진실이고
    (_tool_specs.py 모듈 docstring), fab_name/eqp_model_cd/vendor_nm은 그
    장비의 sem_list row에서 그대로 복사합니다(meas_hist.txt 생성 규칙 1).

    sem_list mock은 eqp_id가 중복될 수 있으므로(300행 중 고유 290개)
    첫 행이 이기도록 dedupe합니다. dedupe하지 않으면 한 eqp_id가 두 fab에
    속하게 되어 "장비는 fab 하나에 산다"는 불변식이 첫날부터 깨집니다.

    장비별 스칼라(speed/workload/recipe_lock)가 흉내내는 것은 실 데이터의 *값*이
    아니라 *편차가 존재한다는 사실*입니다. 정상 장비의 폭은 speed ±4 %,
    workload ±8 %로 좁게 뒀습니다 — meastime 에 들어가는 항은 speed 이므로
    "정상 장비의 TAT 편차"는 ±4 %입니다. 근거는 실 플릿의 가동률이 대부분
    90 % 이상으로 몰려 있다는 현업 확인이며(user-confirmed 2026-08-07,
    운영자 경험칙 — 파생 임계값은 OFFICE-VERIFY), meas_hist.txt 의
    "장비 가동률" 절에 기록돼 있습니다. 칸마다 역할을 고정 배정하는
    이유는 어느 fab을 보더라도 UI의 모든 배지 상태를 한 번씩 밟아보기
    위해서이지, 실제로 5대 중 1대가 느리다는 주장이 아닙니다.
    """
    rng = random.Random(20260807)

    roster: dict[str, dict] = {}
    for row in sem_list_mock._generate_rows():
        roster.setdefault(row["eqp_id"], row)

    cells: dict[tuple[ToolType, str], list[dict]] = {}
    for eqp_id in sorted(roster):                 # 정렬 = 결정론
        row = roster[eqp_id]
        tool_type = model_to_tool_type(row["eqp_model_cd"])
        if tool_type is None:                     # AMAT VeritySEM/Provision — 2027년 이후
            continue
        cells.setdefault((tool_type, row["fab_name"]), []).append(row)

    fleet: dict[ToolType, list[dict]] = {"cd-sem": [], "hv-sem": []}
    for (tool_type, fab_name), members in sorted(cells.items()):
        # 보유분보다 많이 뽑지 않습니다 — hv-sem에는 5대 미만인 칸이 여럿입니다
        # (예: M10B는 1대). 없는 장비를 지어내지 않습니다.
        active = members[:ACTIVE_TOOLS_PER_FAB]
        for index, row in enumerate(active):
            fleet[tool_type].append({
                "eqp_id": row["eqp_id"],
                "fab_name": row["fab_name"],
                "fac_id": row["fac_id"],
                "eqp_model_cd": row["eqp_model_cd"],
                "vendor_nm": row["vendor_nm"],
                **_tool_scalars(rng, index, fab_name),
            })

    return {tool_type: tuple(tools) for tool_type, tools in fleet.items()}


def _tool_scalars(rng: random.Random, index: int, fab_name: str) -> dict:
    """칸 안의 순번으로 역할을 고정 배정합니다 (0=느림, 1=저사용, 2=편중).

    순번 배정이므로 **칸에 장비가 충분히 있을 때에만** 배지 상태가 하나씩
    나타납니다. 느림/저사용은 2대, 편중은 3대, R3의 표본 미달 사례는 4대가
    있어야 합니다. 보유분이 그보다 적으면 뒤쪽 역할은 아예 생기지 않습니다:
    sem_list 기준 cd-sem 은 17개 칸이 모두 4대 이상이라 세 배지가 다 뜨지만,
    hv-sem 에는 3대 미만인 칸이 넷 있어(M10B 1대, M11C·M15C·M16B 각 2대)
    그 fab 의 HV-SEM recipe-status 화면에서는 편중 배지가 구조적으로 뜰 수
    없습니다. 브라우저 검증은 이 칸들을 피해야 합니다.

    R3의 순번 3만 예외적으로 거의 놀게 두어 tat_index=None 경로(표본 미달)를
    기본 화면에서 밟을 수 있게 합니다 — 실 데이터에 그런 장비가 있다는
    주장이 아니라 UI 상태를 시연하기 위해 의도적으로 과장한 사례입니다.
    """
    normal_speed = round(rng.uniform(0.96, 1.04), 4)
    normal_workload = round(rng.uniform(0.92, 1.08), 4)

    if index == 0:
        return {"speed": round(rng.uniform(1.12, 1.20), 4),
                "workload": normal_workload, "recipe_lock": 0}
    if index == 1:
        return {"speed": normal_speed,
                "workload": round(rng.uniform(0.70, 0.80), 4), "recipe_lock": 0}
    if index == 2:
        # 편중은 class가 아니라 **레시피** 단위로 좁혀야 합니다. class 하나에도
        # 레시피가 7~8개 있어서, class만 고정하면 recipe_count가 여전히 7~8이고
        # top_recipe_share는 0.15 언저리라 '편중'으로 보이지 않습니다.
        return {"speed": normal_speed, "workload": normal_workload, "recipe_lock": 2}
    if index == 3 and fab_name == "R3":
        return {"speed": normal_speed, "workload": 0.30, "recipe_lock": 0}
    return {"speed": normal_speed, "workload": normal_workload, "recipe_lock": 0}


@lru_cache(maxsize=1)
def _lots_by_fac() -> dict[str, tuple[str, ...]]:
    """fac_id -> 그 fab의 lot_cd들. 측정은 장비가 있는 fab에서 일어납니다."""
    grouped: dict[str, list[str]] = {}
    for lot_cd, fac_id in sorted(_lot_index().items()):
        grouped.setdefault(fac_id, []).append(lot_cd)
    return {fac_id: tuple(lots) for fac_id, lots in grouped.items()}


@lru_cache(maxsize=1)
def _recipe_definitions() -> tuple[dict, ...]:
    """Stable per-recipe metadata generated once.

    Each entry pins a tool_type, class, recipe_name and a baseline meastime —
    every measurement row for that recipe samples meastime around the baseline
    so a single recipe has a recognizable "size" on the chart. Equipment
    identity is NOT pinned here: it comes from the tool the row runs on
    (`_tool_fleet`), because a recipe is not owned by one model.
    """
    rng = random.Random(20260508)
    classes = tuple(CLASS_MEASTIME_BANDS.keys())
    recipes: list[dict] = []

    for tool_type in ("cd-sem", "hv-sem"):
        for index in range(RECIPE_DEFINITIONS_PER_TOOL):
            class_name = rng.choice(classes)
            template = rng.choice(CLASS_RECIPE_TEMPLATES[class_name])
            recipe_name = template.format(n=f"{index + 1:03d}")
            full_name = f"{class_name}/{recipe_name}"

            min_t, max_t = CLASS_MEASTIME_BANDS[class_name]
            baseline = rng.randint(min_t, max_t)

            recipes.append({
                "tool_type": tool_type,
                "class_name": class_name,
                "recipe_name": recipe_name,
                "full_name": full_name,
                "baseline_meastime": baseline
            })

    return tuple(recipes)


def _format_iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _build_lot_id(rng: random.Random, lot_cd: str) -> str:
    suffix = f"{rng.randint(1, 999999):06d}"
    return f"{lot_cd}{suffix}"


def _recipe_indexes(
    recipes: tuple[dict, ...]
) -> tuple[dict[tuple[ToolType, str], tuple[dict, ...]], dict[ToolType, tuple[dict, ...]]]:
    by_tool_class: dict[tuple[ToolType, str], list[dict]] = {}
    by_tool: dict[ToolType, list[dict]] = {"cd-sem": [], "hv-sem": []}

    for recipe in recipes:
        tool_type = recipe["tool_type"]
        class_name = recipe["class_name"]
        by_tool[tool_type].append(recipe)
        by_tool_class.setdefault((tool_type, class_name), []).append(recipe)

    return (
        {key: tuple(value) for key, value in by_tool_class.items()},
        {key: tuple(value) for key, value in by_tool.items()}
    )


def _pick_recipe_for_tool(
    rng: random.Random,
    by_tool_class: dict[tuple[ToolType, str], tuple[dict, ...]],
    by_tool: dict[ToolType, tuple[dict, ...]],
    tool_type: ToolType,
    tool: dict
) -> dict:
    # 편중 장비는 자기 레시피 몇 개만 돕니다 — recipe_count가 작고
    # top_recipe_share가 큰, 커버리지 신호가 실제로 보이는 형태입니다.
    locked = _locked_recipes(by_tool, tool_type, tool)
    if locked:
        return locked[rng.randrange(len(locked))]

    mix = FAB_CLASS_MIX.get(fab_base(tool["fab_name"]), DEFAULT_CLASS_MIX)
    class_name = rng.choice(mix)
    candidates = by_tool_class.get((tool_type, class_name)) or by_tool[tool_type]
    return candidates[rng.randrange(len(candidates))]


@lru_cache(maxsize=256)
def _locked_recipe_indexes(eqp_id: str, pool_size: int, count: int) -> tuple[int, ...]:
    """편중 장비가 고정으로 도는 레시피 인덱스. eqp_id로 시드해 안정적입니다."""
    if count <= 0 or pool_size <= 0:
        return ()
    picker = random.Random(f"recipe-lock:{eqp_id}")
    return tuple(picker.sample(range(pool_size), min(count, pool_size)))


def _locked_recipes(
    by_tool: dict[ToolType, tuple[dict, ...]],
    tool_type: ToolType,
    tool: dict
) -> tuple[dict, ...]:
    pool = by_tool[tool_type]
    indexes = _locked_recipe_indexes(tool["eqp_id"], len(pool), tool["recipe_lock"])
    return tuple(pool[index] for index in indexes)


@lru_cache(maxsize=1)
def _generate_meas_hist() -> tuple[MeasHistRow, ...]:
    """meas_hist mock 전체를 생성합니다.

    순서가 중요합니다: **장비 → lot → 레시피**. 측정은 어떤 fab의 어떤
    장비에서 일어나고, lot이 거기 들어오고, 그 lot에 레시피가 돕니다.
    예전 구현은 lot에서 시작해 fab을 고르고 장비를 지어냈는데, 그러면
    같은 장비가 여러 fab에 나타나고 meastime이 장비와 무관해집니다.

    결정론이 계약입니다: 같은 (tool_type, 기간) 질의는 항상 같은 집계를
    돌려줘야 대시보드가 렌더 사이에 흔들리지 않습니다.
    """
    rng = random.Random(20260508)
    recipes = _recipe_definitions()
    by_tool_class, by_tool = _recipe_indexes(recipes)
    fleet = _tool_fleet()
    lots_by_fac = _lots_by_fac()

    if not recipes or not any(fleet.values()):
        return ()

    # workload 가중 추출용 누적 가중치 (tool_type별로 한 번 계산)
    weighted: dict[ToolType, tuple[list[dict], list[float]]] = {}
    for tool_type, tools in fleet.items():
        if not tools:
            continue
        cumulative: list[float] = []
        running = 0.0
        for tool in tools:
            running += tool["workload"]
            cumulative.append(running)
        weighted[tool_type] = (list(tools), cumulative)

    rows: list[MeasHistRow] = []
    history_start = ANCHOR_TIME - timedelta(days=HISTORY_WINDOW_DAYS)
    window_seconds = HISTORY_WINDOW_DAYS * 24 * 3600

    for index in range(TOTAL_MEAS_ROWS):
        tool_type: ToolType = "cd-sem" if index % 2 == 0 else "hv-sem"
        if tool_type not in weighted:
            continue
        tools, cumulative = weighted[tool_type]
        tool = tools[bisect.bisect_left(cumulative, rng.uniform(0, cumulative[-1]))]

        # lot은 장비가 선 fab의 것만. Task 1에서 fac 어휘를 통일했으므로
        # 여기서 비는 fac은 없어야 하지만, sem_list에만 있고 lot이 없는
        # fac이 생기면 그 장비는 측정 없이 남습니다(조용한 폴백 금지).
        lots = lots_by_fac.get(tool["fac_id"])
        if not lots:
            continue
        lot_cd = lots[rng.randrange(len(lots))]

        recipe = _pick_recipe_for_tool(rng, by_tool_class, by_tool, tool_type, tool)

        offset = rng.randint(0, window_seconds - 1)
        end_dt = history_start + timedelta(seconds=offset)

        # meastime = 레시피 baseline × fab 성격 × **장비 speed** × jitter.
        # 장비 항이 여기 들어와야 tat_index가 잡음이 아닌 신호가 됩니다.
        jitter = rng.uniform(-0.25, 0.25)
        fab_multiplier = FAB_MEASTIME_MULTIPLIER.get(fab_base(tool["fab_name"]), 1.0)
        meastime = max(
            30,
            int(recipe["baseline_meastime"] * fab_multiplier * tool["speed"] * (1 + jitter))
        )

        start_dt = end_dt - timedelta(seconds=meastime)

        rows.append({
            "id": f"MEAS-{index + 1:06d}",
            "fac_id": tool["fac_id"],
            "fab_name": tool["fab_name"],
            "vendor_nm": tool["vendor_nm"],
            "eqp_id": tool["eqp_id"],
            "eqp_model_cd": tool["eqp_model_cd"],
            "tool_type": tool_type,
            "lot_cd": lot_cd,
            "lot_id": _build_lot_id(rng, lot_cd),
            "class_name": recipe["class_name"],
            "recipe_name": recipe["recipe_name"],
            "full_name": recipe["full_name"],
            "timestamp": _format_iso(end_dt),
            "start_time": _format_iso(start_dt),
            "end_time": _format_iso(end_dt),
            "meastime": meastime
        })

    return tuple(rows)


def get_meas_hist() -> list[MeasHistRow]:
    """Public accessor — callers may filter with the helpers below."""
    return list(_generate_meas_hist())


@lru_cache(maxsize=256)
def _filter_rows(
    tool_type: ToolType | None,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> tuple[MeasHistRow, ...]:
    # Each page load hits ranking + summary + daily-trend with the same
    # filter args. Memoizing here cuts the 55,000-row scan from 3× to 1× per
    # unique window. Sized for ~tool_type × fab × preset_window × lot_cd —
    # keeps the unfiltered (lot_cd=None) entry warm even when the user
    # cycles through many devices. `fab_names` must be a tuple (hashable),
    # never a list — lru_cache requires hashable arguments.
    return filter_measurements(
        _generate_meas_hist(),
        MeasurementScope(tool_type, fab_names, start_date, end_date, lot_cd),
    )


def get_ranking(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None
) -> list[RankingRow]:
    rows = _filter_rows(tool_type, fab_names, start_date, end_date, lot_cd)

    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["class_name"], row["recipe_name"])
        bucket = grouped.setdefault(key, {
            "class_name": row["class_name"],
            "recipe_name": row["recipe_name"],
            "full_name": row["full_name"],
            "meas_counts": 0,
            "total_meastime": 0,
            "lot_cds": set(),
            "eqp_ids": set()
        })
        bucket["meas_counts"] += 1
        bucket["total_meastime"] += row["meastime"]
        bucket["lot_cds"].add(row["lot_cd"])
        bucket["eqp_ids"].add(row["eqp_id"])

    ranked = sorted(
        grouped.values(),
        key=lambda b: b["total_meastime"],
        reverse=True
    )
    if limit > 0:
        ranked = ranked[:limit]

    out: list[RankingRow] = []
    for index, bucket in enumerate(ranked):
        meas_counts = bucket["meas_counts"]
        total = bucket["total_meastime"]
        avg = round(total / meas_counts, 2) if meas_counts else 0.0
        # Cap the example lists so the JSON response stays compact even when
        # a recipe ran on many lots.
        sample_lots = sorted(bucket["lot_cds"])[:5]
        sample_eqps = sorted(bucket["eqp_ids"])[:5]

        out.append({
            "rank": index + 1,
            "class_name": bucket["class_name"],
            "recipe_name": bucket["recipe_name"],
            "full_name": bucket["full_name"],
            "meas_counts": meas_counts,
            "total_meastime": total,
            "avg_meastime": avg,
            "sample_lot_cds": sample_lots,
            "sample_eqp_ids": sample_eqps
        })

    return out


def get_summary(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> SummaryPayload:
    rows = _filter_rows(tool_type, fab_names, start_date, end_date, lot_cd)

    total_executions = len(rows)
    total_tat_seconds = sum(row["meastime"] for row in rows)
    avg_meastime = round(total_tat_seconds / total_executions, 2) if total_executions else 0.0
    total_recipes = len({(row["class_name"], row["recipe_name"]) for row in rows})

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "anchor_date": ANCHOR_TIME.date().isoformat(),
        "total_tat_seconds": total_tat_seconds,
        "total_recipes": total_recipes,
        "total_executions": total_executions,
        "avg_meastime": avg_meastime
    }


def get_daily_trend(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> list[DailyTrendPoint]:
    rows = _filter_rows(tool_type, fab_names, start_date, end_date, lot_cd)

    bucket: dict[str, dict] = {}
    for row in rows:
        date_key = row["timestamp"][:10]   # YYYY-MM-DD slice from ISO string
        entry = bucket.setdefault(date_key, {"total_meastime": 0, "exec_count": 0})
        entry["total_meastime"] += row["meastime"]
        entry["exec_count"] += 1

    # Backfill empty days inside the requested range so the trend chart
    # renders a continuous x-axis instead of skipping silent days.
    start_dt = parse_iso_date(start_date)
    end_dt = parse_iso_date(end_date)
    if start_dt is not None and end_dt is not None and start_dt <= end_dt:
        cursor = start_dt
        while cursor <= end_dt:
            key = cursor.date().isoformat()
            bucket.setdefault(key, {"total_meastime": 0, "exec_count": 0})
            cursor += timedelta(days=1)

    return [
        {
            "date": date_key,
            "total_meastime": entry["total_meastime"],
            "exec_count": entry["exec_count"]
        }
        for date_key, entry in sorted(bucket.items())
    ]


def get_devices(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None
) -> list[DeviceRow]:
    """Distinct lot_cds with measurements in scope, sorted by total TAT desc.

    Drives the `디바이스별` view's quick-filter chip strip — only surfacing
    devices that actually have data in the window keeps the picker honest
    (no zero-result chips).
    """
    rows = _filter_rows(tool_type, fab_names, start_date, end_date)
    metadata = lot_metadata()

    bucket: dict[str, dict] = {}
    for row in rows:
        entry = bucket.setdefault(row["lot_cd"], {"exec_count": 0, "total_meastime": 0})
        entry["exec_count"] += 1
        entry["total_meastime"] += row["meastime"]

    return [
        {
            "lot_cd": lot_cd,
            "exec_count": entry["exec_count"],
            "total_meastime": entry["total_meastime"],
            "prod_catg_cd": metadata.get(lot_cd, {}).get("prod_catg_cd"),
            "tech_nm": metadata.get(lot_cd, {}).get("tech_nm")
        }
        for lot_cd, entry in sorted(
            bucket.items(),
            key=lambda kv: kv[1]["total_meastime"],
            reverse=True
        )
    ]


def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None
) -> EquipmentsPayload:
    """범위 안의 행을 (장비, 레시피) 격자로 접어 공용 조립기에 넘깁니다.

    office 어댑터는 같은 격자를 OpenSearch composite 집계로 만들어 같은
    조립기를 부릅니다 — 두 provider 의 숫자가 정의상 일치합니다.
    """
    cells: dict[tuple[str, str], list] = {}
    for row in _filter_rows(tool_type, fab_names, start_date, end_date):
        key = (row["eqp_id"], row["full_name"])
        cell = cells.get(key)
        if cell is None:
            cells[key] = [
                row["eqp_id"], row["fab_name"], row["eqp_model_cd"],
                row["full_name"], 1, row["meastime"]
            ]
            continue
        cell[4] += 1
        cell[5] += row["meastime"]

    return build_equipments_payload(
        tool_type, fab_names, start_date, end_date,
        [tuple(cell) for cell in cells.values()]
    )


if __name__ == "__main__":
    # Standalone preview:
    #   python -m back_dev_home.ebeam.hitachi.recipe_tat.data
    import pprint

    print("=" * 72)
    print("MEAS_HIST SCALE")
    print("=" * 72)
    rows = _generate_meas_hist()
    print(f"Total rows: {len(rows)}")
    by_tool: dict[str, int] = {}
    for row in rows:
        by_tool[row["tool_type"]] = by_tool.get(row["tool_type"], 0) + 1
    print(f"By tool_type: {by_tool}")

    print("\n" + "=" * 72)
    print("SAMPLE ROW")
    print("=" * 72)
    pprint.pprint(rows[0])

    print("\n" + "=" * 72)
    print("CD-SEM RANKING (last 30 days from ANCHOR_TIME), top 5")
    print("=" * 72)
    end = ANCHOR_TIME.date().isoformat()
    start = (ANCHOR_TIME - timedelta(days=30)).date().isoformat()
    ranking = get_ranking("cd-sem", None, start, end, limit=5)
    for entry in ranking:
        print(
            f"#{entry['rank']:>2}  {entry['full_name']:<28}  "
            f"counts={entry['meas_counts']:>4}  "
            f"total={entry['total_meastime']:>7}s  "
            f"avg={entry['avg_meastime']:>6.1f}s"
        )

    print("\nSUMMARY")
    pprint.pprint(get_summary("cd-sem", None, start, end))

    trend = get_daily_trend("cd-sem", None, start, end)
    print(f"\nDAILY TREND points: {len(trend)} (range {trend[0]['date']} -> {trend[-1]['date']})")
