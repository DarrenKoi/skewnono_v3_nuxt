"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

계측 룰(파라미터 cap 정책) 데이터 표면입니다. Phase 1 은 in-memory seed,
Phase 2/3 은 동일 시그니처로 DB(버전 이력 테이블) 교체.

설계:   docs/issues/ground_rules/rule-editor-structure.md (§2 데이터 모델, §6 백엔드)
결정:   docs/issues/ground_rules/grilling-log.md (D8 cap 표 · D6 Sample · D15 M-fab · D16 threshold)
계약:   docs/api-contracts/cdsem-device-statistics.yaml (RuleCell / RuleVersion)
엔진:   front-dev-home/app/utils/ruleEngine.ts (이 셀들을 client-side 로 소비·판정)

원칙(§8-bis): 백엔드는 raw 룰만 보낸다. 위반 판정·신호등 색은 프론트(ruleEngine)가
client-side 로 계산한다. 본 모듈은 현재 버전(seed)만 노출한다 — save/history/rollback
(D12)은 step 3/5 에서 추가.
"""

from typing import Literal, TypedDict


class NameOverride(TypedDict):
    patterns: list[str]
    match: Literal["contains", "affix"]
    cap: int | None  # None = 면제(무제한)


class SelectorBase(TypedDict):
    # Always present. Split out so total=False below applies only to the
    # optional keying axes — fab/recipe_class stay structurally required
    # (ruleEngine.selectorMatches compares both and a missing fab never matches).
    fab: str
    recipe_class: Literal["Main", "Sample"]


class Selector(SelectorBase, total=False):
    family: Literal["Core", "Pool", "VG_RTC_Cubic"]
    phase_in: list[str]
    yield_check: Literal["before", "after"]
    memory_class: Literal["DRAM", "NAND"]


class RuleCell(TypedDict):
    id: str
    selector: Selector
    caps: dict[str, int]  # WAFER/LEVEL/EDGE/EDGE_EX/_other (누락 type = 해당 없음)
    name_overrides: list[NameOverride]


class Thresholds(TypedDict):
    yellow_at: float
    red_at: float


class RuleVersion(TypedDict):
    fab: str
    version: int
    edited_by: str
    edited_at: str
    cells: list[RuleCell]
    thresholds: Thresholds


# Main 공통: WAFER 13, LEVEL 4, _other 9 — 이름 DSPT/WF/WAFER → 13 (D8 L157).
_MAIN_OVERRIDES: list[NameOverride] = [
    {"patterns": ["DSPT", "WF", "WAFER"], "match": "contains", "cap": 13},
]
# Sample: 비-WAFER 0, 단 WF/WAFER affix 면제 (D6).
_SAMPLE_OVERRIDES: list[NameOverride] = [
    {"patterns": ["WAFER", "WF"], "match": "affix", "cap": None},
]

# D16 — fab-level 신호등 경계 seed 기본값. 편집 가능하되 거의 안 바꿈(D18).
_SEED_THRESHOLDS: Thresholds = {"yellow_at": 0.1, "red_at": 0.2}

# D8 — 모든 Main 셀 공통 cap (WAFER/LEVEL/_other). EDGE/EDGE_EX 만 셀별로 다름.
_MAIN_COMMON = {"WAFER": 13, "LEVEL": 4, "_other": 9}


def _main_cell(cell_id: str, selector: Selector, edge: int, edge_ex: int) -> RuleCell:
    return {
        "id": cell_id,
        "selector": selector,
        "caps": {**_MAIN_COMMON, "EDGE": edge, "EDGE_EX": edge_ex},
        "name_overrides": list(_MAIN_OVERRIDES),
    }


def _sample_cell(cell_id: str, fab: str, memory_class: Literal["DRAM", "NAND"], edge: int) -> RuleCell:
    return {
        "id": cell_id,
        "selector": {"fab": fab, "recipe_class": "Sample", "memory_class": memory_class},
        "caps": {"WAFER": 13, "LEVEL": 4, "EDGE": edge, "EDGE_EX": 0, "_other": 0},
        "name_overrides": list(_SAMPLE_OVERRIDES),
    }


def _r3_cells() -> list[RuleCell]:
    """R3(개발) — family × (phase | yield_check) × memory_class 풀 매트릭스 (D8)."""
    f = "R3"
    return [
        # Core — phase 로 키잉 (t-EV·EV vs TV·PV)
        _main_cell("r3-core-early-dram",
                   {"fab": f, "recipe_class": "Main", "family": "Core",
                    "phase_in": ["t-EV", "EV"], "memory_class": "DRAM"}, edge=10, edge_ex=0),
        _main_cell("r3-core-early-nand",
                   {"fab": f, "recipe_class": "Main", "family": "Core",
                    "phase_in": ["t-EV", "EV"], "memory_class": "NAND"}, edge=8, edge_ex=0),
        # TV·PV 는 EDGE 16 고정 — memory_class 분기 없음 (D8)
        _main_cell("r3-core-tvpv",
                   {"fab": f, "recipe_class": "Main", "family": "Core",
                    "phase_in": ["TV", "PV"]}, edge=16, edge_ex=16),
        # Pool — yield_check 로 키잉, phase 무시 (D8)
        _main_cell("r3-pool-before-dram",
                   {"fab": f, "recipe_class": "Main", "family": "Pool",
                    "yield_check": "before", "memory_class": "DRAM"}, edge=10, edge_ex=0),
        _main_cell("r3-pool-before-nand",
                   {"fab": f, "recipe_class": "Main", "family": "Pool",
                    "yield_check": "before", "memory_class": "NAND"}, edge=8, edge_ex=0),
        _main_cell("r3-pool-after-dram",
                   {"fab": f, "recipe_class": "Main", "family": "Pool",
                    "yield_check": "after", "memory_class": "DRAM"}, edge=10, edge_ex=10),
        _main_cell("r3-pool-after-nand",
                   {"fab": f, "recipe_class": "Main", "family": "Pool",
                    "yield_check": "after", "memory_class": "NAND"}, edge=8, edge_ex=8),
        # VG·RTC·Cubic — 잠정 DRAM-side/Core 차용 (D7). 자체 cap 분기는 추후.
        # memory_class 생략: VG 는 항상 DRAM-side 라 EDGE 분기 불필요(ruleEngine 가
        # family=VG → memory_class DRAM 으로 환원하므로 Gray-B 도 안 남).
        _main_cell("r3-vg-early",
                   {"fab": f, "recipe_class": "Main", "family": "VG_RTC_Cubic",
                    "phase_in": ["t-EV", "EV"]}, edge=10, edge_ex=0),
        _main_cell("r3-vg-tvpv",
                   {"fab": f, "recipe_class": "Main", "family": "VG_RTC_Cubic",
                    "phase_in": ["TV", "PV"]}, edge=16, edge_ex=16),
        # Sample — fab 공통, memory_class 로 분기 (D2·D6).
        # D19: Core TV·PV 만 EDGE 16 으로 상향 (ground_rules.txt L40). memory-blind
        # (Main Core TV·PV 와 동일하게 분기 없음). 일반 Sample 셀보다 **먼저** 둬야
        # ruleEngine 의 first-match 가 이 specific 셀을 고른다 (phase-blind 셀이
        # 앞서면 EDGE 10/8 로 잡혀 D19 가 무력화됨).
        {
            "id": "r3-sample-core-tvpv",
            "selector": {"fab": f, "recipe_class": "Sample", "family": "Core", "phase_in": ["TV", "PV"]},
            "caps": {"WAFER": 13, "LEVEL": 4, "EDGE": 16, "EDGE_EX": 0, "_other": 0},
            "name_overrides": list(_SAMPLE_OVERRIDES),
        },
        _sample_cell("r3-sample-dram", f, "DRAM", edge=10),
        _sample_cell("r3-sample-nand", f, "NAND", edge=8),
    ]


def _mfab_cells(fab: str) -> list[RuleCell]:
    """M-fab(양산) — recipe_class × memory_class 만 (family·phase·Pool 없음, D15).

    의미가 R3 와 다름: R3='기대 분포', M-fab='이상감지 임계치'. cap 도 더 느슨.
    """
    return [
        _main_cell(f"{fab.lower()}-main-dram",
                   {"fab": fab, "recipe_class": "Main", "memory_class": "DRAM"}, edge=16, edge_ex=16),
        _main_cell(f"{fab.lower()}-main-nand",
                   {"fab": fab, "recipe_class": "Main", "memory_class": "NAND"}, edge=12, edge_ex=12),
        _sample_cell(f"{fab.lower()}-sample-dram", fab, "DRAM", edge=10),
        _sample_cell(f"{fab.lower()}-sample-nand", fab, "NAND", edge=8),
    ]


M_FAB_IDS = ["M11", "M12", "M14", "M15", "M16"]

# 현재 버전 seed. step 3/5 에서 버전 이력 리스트로 확장(append-only, D12).
_SEED: dict[str, RuleVersion] = {
    "R3": {
        "fab": "R3", "version": 1, "edited_by": "seed", "edited_at": "2026-05-20T10:00:00Z",
        "cells": _r3_cells(), "thresholds": dict(_SEED_THRESHOLDS),
    },
    **{
        fab: {
            "fab": fab, "version": 1, "edited_by": "seed", "edited_at": "2026-05-20T10:00:00Z",
            "cells": _mfab_cells(fab), "thresholds": dict(_SEED_THRESHOLDS),
        }
        for fab in M_FAB_IDS
    },
}


def list_rule_fabs() -> list[str]:
    return ["R3", *M_FAB_IDS]


def get_rules(fab: str) -> RuleVersion | None:
    """현재 룰 버전(seed). 알 수 없는 fab 이면 None — 라우터가 404 로 변환."""
    return _SEED.get(fab.strip().upper())
