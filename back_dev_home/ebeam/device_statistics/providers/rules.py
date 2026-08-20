"""계측 룰(파라미터 cap 정책) 데이터 표면입니다 — **모든 Phase 의 단일 원천**.

office 어댑터도 이 seed 를 그대로 반환합니다 (user-confirmed 2026-08-04).
앱 내 편집 저장(D12 save/history/rollback)은 하지 않기로 결정했고, 룰을 바꿀
때는 이 파일을 직접 고쳐 배포합니다 — git 이력이 곧 버전 이력입니다. 예전
계획이던 Redis 발행/DB 교체는 폐기했습니다(발행 전 404 만 낳는 운영 함정).

설계:   docs/issues/ground_rules/rule-editor-structure.md (§2 데이터 모델, §6 백엔드)
결정:   docs/issues/ground_rules/grilling-log.md (D8 cap 표 · D6 Sample · D15 M-fab · D16 threshold)
계약:   docs/api-contracts/cdsem-device-statistics.yaml (RuleCell / RuleVersion)
엔진:   front-dev-home/app/utils/ruleEngine.ts (이 셀들을 client-side 로 소비·판정)

원칙(§8-bis): 백엔드는 raw 룰만 보낸다. 위반 판정·신호등 색은 프론트(ruleEngine)가
client-side 로 계산한다.

Internal module: callers outside this feature must import the public
surface from `device_statistics.data` (the provider switch), not this file
directly.
"""

from typing import Literal

from back_dev_home.ebeam.device_statistics.contracts import (
    NameOverride,
    RuleCell,
    RuleVersion,
    Selector,
    Thresholds,
)


# Main 공통: WAFER 13, LEVEL 4, _other 9 — 이름 DSPT/WF/WAFER → 13 (D8 L157).
_MAIN_OVERRIDES: list[NameOverride] = [
    {"patterns": ["DSPT", "WF", "WAFER"], "match": "contains", "cap": 13},
]
# Sample: 비-WAFER 0, 단 WF/WAFER affix 면제 (D6).
#
# DUMMY 도 면제입니다 (user-confirmed 2026-08-05). Sample 셀의 ``_other`` 가 0
# 이라, 자리를 채우는 placeholder 파라미터인 DUMMY 가 **측정 point 가 1 이라도
# 있으면 자동으로 위반**이 됩니다. 실제로 그렇게 잡히고 있었고, 그 위반은
# recipe 를 고쳐서 없앨 수 있는 종류가 아닙니다 — 재는 대상이 아니라 자리
# 표시이기 때문입니다. 위반 목록에 남겨 두면 고칠 수 있는 진짜 위반이 그만큼
# 묻힙니다.
#
# cap=None 은 "상한 없음 = 절대 위반 아님" 입니다(D9) — 목록에서 빼는 것이
# 아니라 판정에서만 빼므로, recipe 의 파라미터 수에는 그대로 남습니다.
#
# match 를 affix 로 둔 것은 바로 위 WAFER/WF 규칙과 같은 의미를 쓰기 위해서
# 입니다 — "Dummy", "Dummy_1", "CD_Dummy" 는 잡고, 이름 한복판에 우연히 든
# 경우는 잡지 않습니다.
#
# 패턴을 대문자로 적었지만 **실물 표기는 "Dummy"** 입니다 (user-confirmed
# 2026-08-05) — 다른 파라미터가 대체로 전부 대문자인데 이 이름만 그렇지
# 않습니다. ruleEngine.matchName 이 양쪽을 대문자로 올려 비교하므로 어느 표기든
# 걸립니다. 여기 대문자는 비교용 정규형이지 데이터의 모습이 아닙니다.
#
# ALIGN 도 같은 이유로 면제입니다. 정렬(addressing)은 **측정이 아니라 측정을
# 위한 준비**라 "얼마나 많이 쟀는가" 라는 질문의 답에 들어가면 안 됩니다 —
# 설비 알람조차 align(9006)과 meas(9007)를 다른 사건으로 셉니다. 프론트엔드는
# 이 둘을 이미 한 벌로 다룹니다(``outlierDetect.NON_MEASUREMENT_PARAMS`` 의
# DUMMY·ALIGN, 그리고 ``para_buckets.measurement_parameters``). 룰 쪽만 DUMMY
# 하나로 남아 있어서, Sample recipe 의 Align 이 point 1~3 개로 자동 위반이
# 되고 있었습니다 — 집 mock 에서만 2,607 건입니다.
#
# 실물 표기는 "Align" 입니다 (user-confirmed 2026-08-10) — DUMMY 와 마찬가지로
# 대문자 표기가 아니고, ``matchName`` 이 양쪽을 올려 비교하므로 상관없습니다.
_SAMPLE_OVERRIDES: list[NameOverride] = [
    {"patterns": ["WAFER", "WF"], "match": "affix", "cap": None},
    {"patterns": ["DUMMY"], "match": "affix", "cap": None},
    {"patterns": ["ALIGN"], "match": "affix", "cap": None},
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


def _sample_cell(cell_id: str, fac_id: str, memory_class: Literal["DRAM", "NAND"], edge: int) -> RuleCell:
    return {
        "id": cell_id,
        "selector": {"fac_id": fac_id, "recipe_class": "Sample", "memory_class": memory_class},
        "caps": {"WAFER": 13, "LEVEL": 4, "EDGE": edge, "EDGE_EX": 0, "_other": 0},
        "name_overrides": list(_SAMPLE_OVERRIDES),
    }


def _r3_cells() -> list[RuleCell]:
    """R3(개발) — family × (phase | yield_check) × memory_class 풀 매트릭스 (D8)."""
    f = "R3"
    return [
        # Core — phase 로 키잉 (t-EV·EV vs TV·PV)
        _main_cell("r3-core-early-dram",
                   {"fac_id": f, "recipe_class": "Main", "family": "Core",
                    "phase_in": ["t-EV", "EV"], "memory_class": "DRAM"}, edge=10, edge_ex=0),
        _main_cell("r3-core-early-nand",
                   {"fac_id": f, "recipe_class": "Main", "family": "Core",
                    "phase_in": ["t-EV", "EV"], "memory_class": "NAND"}, edge=8, edge_ex=0),
        # TV·PV 는 EDGE 16 고정 — memory_class 분기 없음 (D8)
        _main_cell("r3-core-tvpv",
                   {"fac_id": f, "recipe_class": "Main", "family": "Core",
                    "phase_in": ["TV", "PV"]}, edge=16, edge_ex=16),
        # Pool — yield_check 로 키잉, phase 무시 (D8)
        _main_cell("r3-pool-before-dram",
                   {"fac_id": f, "recipe_class": "Main", "family": "Pool",
                    "yield_check": "before", "memory_class": "DRAM"}, edge=10, edge_ex=0),
        _main_cell("r3-pool-before-nand",
                   {"fac_id": f, "recipe_class": "Main", "family": "Pool",
                    "yield_check": "before", "memory_class": "NAND"}, edge=8, edge_ex=0),
        _main_cell("r3-pool-after-dram",
                   {"fac_id": f, "recipe_class": "Main", "family": "Pool",
                    "yield_check": "after", "memory_class": "DRAM"}, edge=10, edge_ex=10),
        _main_cell("r3-pool-after-nand",
                   {"fac_id": f, "recipe_class": "Main", "family": "Pool",
                    "yield_check": "after", "memory_class": "NAND"}, edge=8, edge_ex=8),
        # VG·RTC·Cubic — 잠정 DRAM-side/Core 차용 (D7). 자체 cap 분기는 추후.
        # memory_class 생략: VG 는 항상 DRAM-side 라 EDGE 분기 불필요(ruleEngine 가
        # family=VG → memory_class DRAM 으로 환원하므로 Gray-B 도 안 남).
        _main_cell("r3-vg-early",
                   {"fac_id": f, "recipe_class": "Main", "family": "VG_RTC_Cubic",
                    "phase_in": ["t-EV", "EV"]}, edge=10, edge_ex=0),
        _main_cell("r3-vg-tvpv",
                   {"fac_id": f, "recipe_class": "Main", "family": "VG_RTC_Cubic",
                    "phase_in": ["TV", "PV"]}, edge=16, edge_ex=16),
        # Sample — fab 공통, memory_class 로 분기 (D2·D6).
        # D19: Core TV·PV 만 EDGE 16 으로 상향 (ground_rules.txt L40). memory-blind
        # (Main Core TV·PV 와 동일하게 분기 없음). 일반 Sample 셀보다 **먼저** 둬야
        # ruleEngine 의 first-match 가 이 specific 셀을 고른다 (phase-blind 셀이
        # 앞서면 EDGE 10/8 로 잡혀 D19 가 무력화됨).
        {
            "id": "r3-sample-core-tvpv",
            "selector": {"fac_id": f, "recipe_class": "Sample", "family": "Core", "phase_in": ["TV", "PV"]},
            "caps": {"WAFER": 13, "LEVEL": 4, "EDGE": 16, "EDGE_EX": 0, "_other": 0},
            "name_overrides": list(_SAMPLE_OVERRIDES),
        },
        _sample_cell("r3-sample-dram", f, "DRAM", edge=10),
        _sample_cell("r3-sample-nand", f, "NAND", edge=8),
    ]


# 현재 버전 seed. R3 전용 (D22 — M-fab 룰 폐기, D15 supersede).
_SEED: dict[str, RuleVersion] = {
    "R3": {
        "fac_id": "R3", "version": 1, "edited_by": "seed", "edited_at": "2026-05-20T10:00:00Z",
        "cells": _r3_cells(), "thresholds": dict(_SEED_THRESHOLDS),
    },
}


def get_rules(fac_id: str) -> RuleVersion | None:
    """현재 룰 버전(seed). 알 수 없는 fac_id 이면 None — 라우터가 404 로 변환."""
    return _SEED.get(fac_id.strip().upper())
