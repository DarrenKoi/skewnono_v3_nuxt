"""Rule 없는 계열(HV-SEM / VeritySEM / Provision)의 화면 묶음 규칙과 키 정규화.

mock(``providers/family_tables.py``)과 앞으로 쓸 office 어댑터가 **같이** 부르는
판정입니다. CD-SEM 규칙(``providers/recipe_population.py``)은 건드리지 않습니다 —
사무실이 확인한 차이는 이 계열들에만 해당합니다.

근거: 사무실 회신 2026-11-04 (docs/office-migration/reply-device-statistics-families-261104.md,
2차는 reply-device-statistics-families-261104-r2.md).
"""

from __future__ import annotations

import re

from backend.ebeam.device_statistics.contracts import FamilyToolType

# only_normal — 스텝명의 마지막 토큰이 이 계열의 표식 중 하나인가 (Q7 BBB,
# 사무실 권고 "규칙 F", office 확인 2026-11-04). CD-SEM 의 "마지막 토큰 == CD" 를
# 계열 표식으로 넓힌 규칙입니다. HV-SEM 에는 CD 로 끝나는 step 이 0건이라 CD 를
# 넣지 않았습니다. 괄호 꼬리("HV(E)")는 CD-SEM 과 같은 이유로 걸러집니다.
#
# HV-SEM 의 "CD_HV" / "CD2_HV" / "CD3_HV" 는 띄어쓰기 없이 붙은 한 토큰이라 "HV"
# 만으로는 빠집니다 — 53 step (R1, office 확인 2026-11-04). 토큰을 "_" 로 더 쪼개지
# 않고 세 이름을 그대로 넣은 것은, 쪼개면 VeritySEM·Provision 의 "..._CD" 까지
# Normal 이 되어 사무실이 검증한 규칙 F 숫자가 움직이기 때문입니다.
# 붙은 꼬리는 Provision 에 "CD2_PROV" 12 step 이 있고 VeritySEM 에는 없습니다
# (V1, office 확인 2026-11-04).
FAMILY_NORMAL_TOKENS: dict[FamilyToolType, frozenset[str]] = {
    "hv-sem": frozenset({"HV", "CD_HV", "CD2_HV", "CD3_HV"}),
    "veritysem": frozenset({"CD", "VERITY", "VRT"}),
    "provision": frozenset({"CD", "PROV", "CD2_PROV"}),
}

# only_sample — recipe 이름이 "_S" 또는 "_SE" 로 끝나는가 (Q16 BBB, office 확인
# 2026-11-04). CD-SEM 의 ``(_S|SE)$`` 는 "_DENSE" 같은 정상 recipe 를 Sample 로
# 잘못 잡아, 이 계열에서는 밑줄까지 요구합니다.
_SAMPLE_ENDINGS = ("_S", "_SE")

# prod_id -> lot_cd. "_BASE" 만이 아니라 "RH0V_CAP_BASE" 형태가 있습니다
# (계열 index 에서 175건, office 확인 2026-11-04). "_CAP" 까지 떼야 카탈로그와
# 맞습니다. 떼는 순서가 중요합니다 — "_BASE" 를 먼저 떼야 "_CAP" 이 끝에 옵니다.
_PROD_ID_SUFFIXES = ("_BASE", "_CAP")


def lot_cd_from_prod_id(prod_id: str) -> str:
    """R3 planstep 의 prod_id 에서 카탈로그 lot_cd 를 얻습니다."""
    lot_cd = (prod_id or "").strip()
    for suffix in _PROD_ID_SUFFIXES:
        lot_cd = lot_cd.removesuffix(suffix)
    return lot_cd


def _last_token(oper_desc: str) -> str:
    stripped = (oper_desc or "").strip().rstrip(")]} \t")
    return stripped.split()[-1].upper() if stripped else ""


def is_family_normal_step(tool_type: FamilyToolType, oper_desc: str, skip_yn: str) -> bool:
    """only_normal / mother_normal 이 공유하는 스텝 필터의 계열판.

    skip 판정은 CD-SEM 과 같은 ``!= "Y"`` 입니다. 이 계열의 값은 Y / N / D 이고
    D 는 N 과 같은 성격입니다 (office 확인 2026-11-04).
    """
    measuring = (skip_yn or "").strip().upper() != "Y"
    return measuring and _last_token(oper_desc) in FAMILY_NORMAL_TOKENS[tool_type]


def is_family_sample_recipe(recipe_id: str) -> bool:
    return (recipe_id or "").strip().upper().endswith(_SAMPLE_ENDINGS)


# HV-SEM param_type — 원천에 종류 column 이 없어 이름에서 파생합니다 (R4 B, office
# 확인 2026-11-04). CD-SEM 의 접두사 규칙(이름 앞 WAFER/LEVEL/EDGE)은 HV-SEM 파라미터의
# 5.68% 만 덮고, 이름 **안의** 토큰을 EX > ED/EDGE > WF > LV 순서로 보면 41.1% 를
# 덮습니다. 순서가 핵심입니다 — "EDGE_EX" 는 EDGE 토큰도 가지므로 EX 를 먼저 봅니다.
# 나머지 약 59% 는 "" (종류 모름)로 남습니다.
# 토큰 → 종류 이름 대응(EX → EDGE_EX 등)은 사무실이 맞다고 했습니다 (S5, 2026-11-04).
_HV_TYPE_TOKENS: tuple[tuple[str, frozenset[str]], ...] = (
    ("EDGE_EX", frozenset({"EX"})),
    ("EDGE", frozenset({"ED", "EDGE"})),
    ("WAFER", frozenset({"WF", "WAFER"})),
    ("LEVEL", frozenset({"LV", "LEVEL"})),
)
_CD_TYPE_PREFIXES = ("EDGE_EX", "EDGE", "WAFER", "LEVEL")   # CD-SEM 접두사, longest 먼저


def hv_param_type(name: str) -> str:
    """HV-SEM 파라미터 이름 → WAFER / LEVEL / EDGE / EDGE_EX, 모르면 ""."""
    upper = (name or "").strip().upper()
    tokens = set(re.split(r"[^A-Z0-9]+", upper))
    for kind, marks in _HV_TYPE_TOKENS:      # 토큰이 먼저 — "EDGE_L_EX" 도 EDGE_EX
        if tokens & marks:
            return kind
    for kind in _CD_TYPE_PREFIXES:           # "WAFER1" 처럼 토큰이 아닌 접두사
        if upper.startswith(kind):
            return kind
    return ""
