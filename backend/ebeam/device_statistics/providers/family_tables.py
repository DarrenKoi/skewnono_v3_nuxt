"""Rule 없는 장비 계열(HV-SEM / VeritySEM / Provision)의 mock 표 A~D.

사무실 요청서: docs/office-migration/to-office-device-statistics-families-261102.md
계약:        contracts.py 의 Family*Row

사무실 회신: docs/office-migration/reply-device-statistics-families-261104.md
규칙:        family_rules.py (only_normal 표식, Sample 꼬리, prod_id -> lot_cd)

화면·라우트는 아직 없습니다. 사무실 데이터가 오기 전에 집에서 같은 모양의 데이터를
먼저 갖춰 두려는 모듈입니다.

사무실에서 확인된 것 (office 확인 2026-11-04 — 회신 기록)

- 규모: 표 A lots / steps / recipes, 표 D lots 가 :data:`FAMILY_SPECS` 위 주석의
  숫자입니다. recipes / steps 가 0.44~0.49 라 step 의 절반 넘게 recipe 를
  공유합니다(CD-SEM mock 의 4% 와 전혀 다릅니다). M fab 에도 세 계열 step 이
  있습니다(Q2 AAA). R3 / M fab 비율은 모르므로 그 split 은 지어낸 값입니다.
- skip_yn 은 "Y" / "N" / "D" 이고 **빈 값은 0건**입니다. D 는 N 과 같은 성격.
- prod_id 는 "_BASE" 만이 아니라 "RH0V_CAP_BASE" 형태가 있습니다. lot_cd 는
  ``family_rules.lot_cd_from_prod_id`` 로 둘 다 떼어 얻습니다.
- (prod_id, oper_seq, samp_seq) 가 겹치는 행이 hv 3 / verity 30 / provision 27
  있고, 전부 oper_desc 가 다른 별개 step 입니다 — 정체성에 oper_desc 가 듭니다.
- only_normal 표식: hv-sem HV / veritysem CD·VERITY·VRT / provision CD·PROV.
  HV-SEM 에는 CD 로 끝나는 step 이 0건입니다. step 이름은 CD-SEM 어휘의 끝 "CD"
  를 이 표식으로 바꿔 만듭니다.
- Sample 은 recipe 이름이 "_S" / "_SE" 로 끝납니다. "_DENSE" 가 CD-SEM 규칙
  ``(_S|SE)$`` 의 오검출이라 mock 이 섞어 냅니다.
- 카탈로그에 없는 device 가 있습니다(Q11 BBB) — "RZ.." lot 으로 대역합니다.
- HV-SEM 파라미터: hvsem_idp_ver 에서 읽고(커버리지 40% — ok 575 / not_found
  868, empty·failed 0), param_seq 는 raw_data 행 순서, 빈 Parameter 4.9%,
  이름이 겹치는 문서 52.7%. mother 있음·포인트 수 고정·Dummy/Align 맨 앞(Q5, Q6,
  Q15 의 HV 칸 A). param_type 은 원천에 없어 이름에서 파생합니다(Q4 HV = B, 아래 R4).
- VeritySEM·Provision 은 측정 결과 파싱 전이라 사무실 표 C 가 **전부 not_found**
  입니다. mock 의 ok 비율은 화면 경로를 돌리려는 가정값입니다.
- 시각(chg_tm / source_tm / as_of)은 offset 없는 KST wall-clock 입니다.

2차 회신에서 확인된 것 (office 확인 2026-11-04 — reply-device-statistics-families-261104-r2.md)

- HV-SEM 에는 "CD_HV" / "CD2_HV" / "CD3_HV" 로 끝나는 step 이 53건 있습니다(R1).
  규칙 F 표식에 이 셋을 더했고, mock 이 같은 비율로 냅니다.
- HV-SEM param_type 은 이름 안의 토큰에서 파생합니다(R4 B) — CD-SEM 접두사 규칙이
  5.68%, 토큰 규칙(EX > ED/EDGE > WF > LV)이 41.1% 를 **따로** 덮어 합쳐서 약
  46.8% 입니다(S6). 토큰 → 종류 대응은 사무실이 맞다고 했습니다(S5). mock 은 CD-SEM
  이름을 그 비율로 접두사형 / 토큰형("L_ED", "P2_WF") / 종류 없음("PT_2")으로
  바꿉니다. 이름 자체는 지어낸 값이고 비율만 사무실 숫자입니다.
- 빈 Parameter 행은 빼지 않고 param_seq 그대로 둡니다(R3 A).
- **R4 device 가 계열 index 에 섞여 있습니다.** fac_id 로 R3 만 고르면 R7QA / R7QC
  두 device 가 표 A 에서 사라집니다. 둘은 세 계열 index 모두에 있고 r3_device_grp
  에도 있습니다(S8 ABC, S9 A). mock 은 R3 카탈로그의 같은 두 lot 을 세 계열 모두에
  fac_id "R4" 로 냅니다 — planstep 경로인지는 fac_id 가 아니라 prod_id 로 가립니다.
- AVIS/ICANS 는 step 행 비율로 hv 33.6% / verity 1.6% / provision 18.2% 입니다(S11).
- 같은 (recipe, version) 인데 파라미터가 다른 경우가 40건이고, 그중 33건은 fab
  마다 하나로 정해집니다(R2). idp 의 eqp_id 는 배열이고 94.5% 가 IP 주소라 eqp_id
  로 대표를 고를 수 없습니다. 표 B 는 (recipe_id, fac_id) 마다 한 벌이고(S2 A),
  fab 으로도 안 정해지는 나머지는 가장 최근 문서를 씁니다(S3 A). mock 은 M fab
  step 15% 가 R3 recipe 를 쓰게 해 여러 fab 에 걸린 recipe 를 만들고, 그 절반에서
  뒤 fab 의 마지막 파라미터를 뺍니다(두 비율 모두 지어낸 값).
- VeritySEM·Provision 에도 "CD_HV" 처럼 붙은 표식 꼬리가 있습니다(S7 B). 꼬리
  목록과 step 수는 아직 받지 못해 규칙 F 표식에 넣지 않았습니다 — OFFICE-VERIFY.

3차 회신 숫자 (office 확인 2026-11-04 — reply-device-statistics-families-261104-r3.md)

- 표 A 숫자(lots / steps / recipes)는 planstep index 만의 값이고 M fab device 는 따로
  셉니다(hv 64 / verity 74 / provision 71). 카탈로그 밖 device 33 / 19 / 47,
  _CAP_BASE device 계열마다 3, skip D 2.51% / 7.24% / 1.42%, "_DENSE" recipe
  0 / 2 / 0. :data:`FAMILY_SPECS` 가 이 숫자를 따릅니다.
- 표 B·C·D 는 저장된 곳이 없습니다. 사무실 추출이 매번 계산합니다(B = hvsem_idp_ver
  조회, C = 계산, D = ebeam_tas_lot_hist dt.keyword 90일 창).

일부러 남긴 성질

- **계열 간 recipe 이름 충돌.** 이름 조각을 CD-SEM 과 같은 digest 로 고르므로, 같은
  device 를 두 계열이 재면 같은 recipe_id 가 계열마다 다른 파라미터로 나옵니다.
  조인 키가 (tool_type, recipe_id) 여야 하는 이유를 집에서 보이게 하려는 것입니다.
- **네 상태가 모두 나옵니다** (ok / empty / not_found / failed) — 다만 HV-SEM 은
  사무실 비율대로 ok / not_found 만 냅니다. empty·failed 는 AMAT 가정값에서 나옵니다.
- **param_type 이 빈 행이 섞입니다.** HV-SEM 은 이름 파생이라 약 59% 가 빈 값,
  AMAT 은 원천 column(추정)으로 채움 — 두 경로가 모두 집에서 실행됩니다.
- **표 A 에 있는데 표 D 에 없는 device**(계획은 있는데 최근 90일 측정 없음)와
  **표 D 에만 있는 device**(측정은 있는데 step 원본 없음 — CD-SEM 의 RX1R)가 섞입니다.

OFFICE-VERIFY

- AMAT 의 param_type(Q4 / R9), 포인트 수 고정(Q5), mother(Q6), Dummy/Align 위치(Q15),
  상태 비율 — 측정 결과 파싱 후 확정합니다.
- 같은 (tool_type, recipe_id) 가 장비마다 다른 파라미터를 가질 수 있습니다(Q10 B,
  R2 — 위 2차 회신 절). 표 B 의 대표 규칙은 아직 없어, mock 은 recipe 당 한 벌만
  만듭니다.
- 비율만 모르는 것: 계열 index 의 skip "Y" 비율, M fab step 수.

eqp_id 는 sem_list mock 에서 **그 계열·그 fab 의 장비**만 고릅니다. 장비가 없는 fab
에는 step 을 만들지 않습니다.

Internal module: mock.py 가 재노출합니다.
"""

from __future__ import annotations

import hashlib
import random
from datetime import timedelta
from functools import lru_cache
from typing import TypedDict

from backend.ebeam._tool_specs import model_to_tool_type
from backend.ebeam.device_statistics.para_buckets import has_non_measurement_name
from backend.ebeam.device_statistics.contracts import (
    FamilyActivityRow,
    FamilyParamRow,
    FamilyRecipeStatusRow,
    FamilyStepRow,
    FamilyToolType,
)
from backend.ebeam.device_statistics.providers.recipe_params import (
    _assign_regions,
    _build_parameters,
    _has_helper_params,
)
from backend.ebeam.device_statistics.family_rules import (
    hv_param_type,
    is_family_sample_recipe,
    lot_cd_from_prod_id,
)
from backend.ebeam.device_statistics.providers.recipe_population import (
    _OPER_PREFIXES,
    IMAGE_STEP_SUFFIXES,
    is_exempt_job,
)
from backend.ebeam.device_statistics.providers.recipe_population import (
    _recipe_name as _cd_recipe_name,
)
from backend.ebeam.device_statistics.providers.recipe_population import (
    _step_name as _cd_step_name,
)


class _Spec(TypedDict):
    seed: int
    r3_lots: int                     # planstep index 의 device 수 = 표 A lots (office)
    r3_steps: tuple[int, int]        # 평균이 표 A steps / lots 가 되게 (office)
    off_catalog: int                 # r3_lots 중 카탈로그에 없는 device (office)
    m_lots: int                      # M fab device 합 — 5 fab 에 나눕니다 (office)
    m_steps: tuple[int, int]         # OFFICE-VERIFY
    skip_d_ratio: float              # skip_yn "D" / 표 A steps (office)
    dense_per_mille: int             # "_DENSE" recipe 비율 ‰ (office 수에 맞춤)
    shared_recipe_ratio: float       # 표 A recipes / steps ≈ 0.44~0.49 (office)
    dup_identity_ratio: float        # (prod_id, oper_seq, samp_seq) 중복 / steps (office)
    active_ratio: float              # 표 D lots / 표 A lots (office)
    markers: tuple[str, ...]         # step 이름 마지막 토큰 후보 = only_normal 표식 (Q7)
    marker_weights: tuple[float, ...]
    image_step_ratio: float          # AVIS/ICANS step 비율 (Q17 / 2차 회신)
    source_kind: str                 # "idp" | "measurement"
    has_mother: bool                 # OFFICE-VERIFY (Q6) — AMAT
    typed_params: bool               # OFFICE-VERIFY (Q4) — AMAT
    status_weights: tuple[float, float, float, float]  # ok, empty, not_found, failed


# 규모는 사무실 회신 2026-11-04 의 숫자입니다(표 A lots / steps / recipes, 표 D lots).
# 표 A 숫자는 planstep index(R3 경로)만의 값이고, M fab device 는 따로 셉니다(3차):
#   hv-sem    193 / 3,310 / 1,443   D 99    M 64   카탈로그 밖 33   AVIS·ICANS 1,112
#   veritysem 216 / 4,250 / 2,074   D 138   M 74   카탈로그 밖 19   AVIS·ICANS 68
#   provision 294 / 8,156 / 3,487   D 126   M 71   카탈로그 밖 47   AVIS·ICANS 1,481
# skip "D": hv 83 (2.51%) / verity 310 (7.24%) / provision 116 (1.42%).
# "_DENSE" recipe: hv 0 / verity 2 / provision 0. "_CAP_BASE" device: 계열마다 3.
FAMILY_SPECS: dict[FamilyToolType, _Spec] = {
    "hv-sem": {
        "seed": 20261102, "r3_lots": 193, "r3_steps": (10, 24), "off_catalog": 33,
        "m_lots": 64, "m_steps": (4, 12), "skip_d_ratio": 0.0251, "dense_per_mille": 0,
        "shared_recipe_ratio": 0.60, "dup_identity_ratio": 0.001, "active_ratio": 0.38,
        # CD_HV 계열 53 / 3,310 step (R1, office 확인 2026-11-04).
        "markers": ("HV", "CD_HV", "CD2_HV", "CD3_HV"),
        "marker_weights": (0.952, 0.024, 0.012, 0.012),
        "image_step_ratio": 0.336,   # office 확인 2026-11-04
        # typed_params=False: 원천 column 이 없습니다. 이름 파생은 family_rules.hv_param_type.
        "source_kind": "idp", "has_mother": True, "typed_params": False,
        # office: ok 575 / not_found 868 / empty 0 / failed 0 (idp 커버리지 40%).
        "status_weights": (0.40, 0.0, 0.60, 0.0),
    },
    "veritysem": {
        "seed": 20261103, "r3_lots": 216, "r3_steps": (12, 27), "off_catalog": 19,
        "m_lots": 74, "m_steps": (3, 8), "skip_d_ratio": 0.0724, "dense_per_mille": 1,
        "shared_recipe_ratio": 0.56, "dup_identity_ratio": 0.007, "active_ratio": 0.45,
        "markers": ("CD", "VERITY", "VRT"), "marker_weights": (1, 1, 1),
        "image_step_ratio": 0.016,   # 68 / 4,250 (office 확인 2026-11-04)
        "source_kind": "measurement", "has_mother": False, "typed_params": True,
        # office 는 아직 전부 not_found 입니다(측정 결과 파싱 전). 화면 경로를 집에서
        # 돌리려고 ok 를 둔 가정값입니다 — OFFICE-VERIFY (파싱 후 비율).
        "status_weights": (0.85, 0.02, 0.10, 0.03),
    },
    "provision": {
        "seed": 20261104, "r3_lots": 294, "r3_steps": (18, 38), "off_catalog": 47,
        "m_lots": 71, "m_steps": (4, 12), "skip_d_ratio": 0.0142, "dense_per_mille": 0,
        "shared_recipe_ratio": 0.61, "dup_identity_ratio": 0.0033, "active_ratio": 0.30,
        "markers": ("CD", "PROV"), "marker_weights": (1, 1),
        "image_step_ratio": 0.182,   # 1,481 / 8,156 (office 확인 2026-11-04)
        "source_kind": "measurement", "has_mother": False, "typed_params": True,
        "status_weights": (0.88, 0.02, 0.07, 0.03),   # veritysem 과 같은 이유의 가정값
    },
}

STATUSES = ("ok", "empty", "not_found", "failed")
NO_STEP_RATIO = 0.03             # 표 D 에만 있는 device 비율 (표 A device 수 대비)
WINDOW_DAYS = 90
# 계열 index 의 skip "Y" 비율은 모릅니다 — OFFICE-VERIFY. CD-SEM(-cd)은 47.7% 라
# recipe_population.SKIPPED_RATIO 와 일부러 갈라 둡니다.
FAMILY_SKIPPED_RATIO = 0.15
CAP_LOTS = 3                     # prod_id 가 "_CAP_BASE" 인 device, 계열마다 3 (office 확인 2026-11-04)
HV_BLANK_PARAM_RATIO = 0.049     # hvsem_idp_ver 빈 Parameter 4.9% (office 확인 2026-11-04)
HV_DUP_NAME_RATIO = 0.527        # 이름이 겹치는 파라미터가 있는 recipe 52.7% (같음)
# HV-SEM param_type 커버리지 (R4·S6, office 확인 2026-11-04) — 접두사 5.68% 와 토큰
# 41.1% 는 별개라 합쳐서 약 46.8% 입니다. 확률은 CD-SEM 이름 중 종류가 있는 것(약 71%)
# 에 거는 값이라 전체 비율로는 5.7% / 41% 가 됩니다.
HV_PREFIX_NAME_P = 0.08
HV_TOKEN_NAME_P = 0.58
# R4 device R7QA / R7QC — 세 계열 index 모두에 있고 r3_device_grp 에도 있습니다
# (S8 ABC, S9 A). mock 은 R3 카탈로그의 같은 두 lot 을 세 계열 모두에 R4 로 냅니다.
R4_LOTS = 2
_R4_SEED = 20261104
# 표 B fab 축을 집에서 보이게 하는 두 값. 사무실 숫자는 "같은 (recipe, version) 인데
# 파라미터가 다른 경우 40건(HV-SEM recipe 1,443 중), 33건은 fab 마다 정해짐" 뿐이라,
# 여러 fab 에 걸린 recipe 수와 그중 다른 비율은 지어낸 값입니다 — OFFICE-VERIFY.
CROSS_FAB_STEP_RATIO = 0.15      # M fab step 중 R3 recipe 를 그대로 쓰는 비율
FAB_DIFF_RATIO = 0.5             # 여러 fab 에 걸린 recipe 중 fab 마다 파라미터가 다른 비율
_HV_TOKEN = {"WAFER": "WF", "LEVEL": "LV", "EDGE": "ED", "EDGE_EX": "EDGE_EX"}


def _kst(dt) -> str:
    """offset 없는 KST wall-clock — 실물 chg_tm 의 모양(statistics.py 와 같음)."""
    return (dt + timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")


def _digest(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def _param_type(name: str) -> str:
    """AMAT 원천에 종류 column 이 있다고 가정하고 채울 값(Q4). 비측정은 빈 값."""
    upper = name.upper()
    for kind in ("WAFER", "LEVEL", "EDGE_EX", "EDGE"):
        if upper.startswith(kind):
            return kind
    return "" if upper in ("DUMMY", "ALIGN") else "OTHER"


def _skip_yn(rng: random.Random, spec: _Spec) -> str:
    """계열 index 의 값 도메인 — "Y" / "N" / "D", 빈 값 0건 (office 확인 2026-11-04).

    CD-SEM(-cd)은 "Y" / "N" / 빈 값이라 recipe_population._skip_yn 과 다릅니다.
    D 는 N 과 같은 성격이므로 판정은 그대로 ``!= "Y"`` 입니다.
    """
    roll = rng.random()
    if roll < FAMILY_SKIPPED_RATIO:
        return "Y"
    return "D" if roll < FAMILY_SKIPPED_RATIO + spec["skip_d_ratio"] else "N"


def _step_name(rng: random.Random, spec: _Spec) -> str:
    """CD-SEM 어휘의 끝 "CD" 를 그 계열 표식으로 바꿉니다 (Q7).

    HV-SEM 에는 CD 로 끝나는 step 이 0건이라 늘 "HV" 가 됩니다. 괄호 꼬리는
    "HV(E)" 처럼 남아 only_normal 에서 빠집니다.
    """
    name = _cd_step_name(rng)
    head, _, last = name.rpartition(" ")
    if last.startswith("CD"):
        marker = rng.choices(spec["markers"], weights=spec["marker_weights"])[0]
        name = f"{head} {marker}{last[2:]}"
    if rng.random() < spec["image_step_ratio"]:
        name += " " + rng.choice(sorted(IMAGE_STEP_SUFFIXES))
    return name


def _recipe_name(rng: random.Random, spec: _Spec, lot_cd: str, idx: int) -> str:
    """CD-SEM 이름에서 출발해 계열의 Sample 꼬리("_S" / "_SE")로 맞춥니다 (Q16).

    CD-SEM mock 은 "...SE" 로도 Sample 을 만드는데 이 계열에서 그것은 Sample 이
    아니므로 "_SE" 로 바꿉니다. 그리고 "_DENSE" 처럼 SE 로 끝나는 **정상** recipe 를
    섞어, CD-SEM 규칙 ``(_S|SE)$`` 를 잘못 쓰면 집에서 드러나게 합니다.
    """
    name = _cd_recipe_name(rng, lot_cd, idx)
    if name.endswith("SE") and not name.endswith("_SE"):
        return name[:-2] + "_SE"
    if not is_family_sample_recipe(name) and _digest(f"dense:{lot_cd}:{idx}") % 1000 < spec["dense_per_mille"]:
        return name + "_DENSE"
    return name


def _tools_by_fab(tool_type: FamilyToolType) -> dict[str, list[str]]:
    from backend.sem_list.providers import mock as sem_list_mock

    tools: dict[str, list[str]] = {}
    for row in sem_list_mock.get_sem_list():
        if model_to_tool_type(row["eqp_model_cd"]) == tool_type:
            tools.setdefault(row["fac_id"], []).append(row["eqp_id"])
    return {fab: sorted(set(ids)) for fab, ids in tools.items()}


def _pick_recipe(rng, spec, rows, lot_cd, idx) -> str:
    """앞 step 의 recipe 를 다시 쓰거나 새로 짓습니다 — 계열 index 에서는 step 의
    절반 넘게 recipe 를 공유합니다(recipes / steps ≈ 0.45)."""
    if rows and rng.random() < spec["shared_recipe_ratio"]:
        return rng.choice(rows)["recipe_id"]
    return _recipe_name(rng, spec, lot_cd, idx)


def _r3_steps(rng, tool_type, spec, fac_id, lot_cd, prod_id, n, eqps, base_time) -> list[FamilyStepRow]:
    rows: list[FamilyStepRow] = []
    oper_seq, samp_seq = 0, 1
    for idx in range(n):
        dup = rows and rng.random() < spec["dup_identity_ratio"]
        if dup:
            pass                           # 같은 (oper_seq, samp_seq) 에 다른 step (아래)
        elif rows and rng.random() < 0.2:
            samp_seq += 1                  # 같은 공정의 두 번째 sample
        else:
            oper_seq, samp_seq = oper_seq + 10, 1
        oper_desc = _step_name(rng, spec)
        while dup and oper_desc == rows[-1]["oper_desc"]:
            oper_desc = _step_name(rng, spec)
        rows.append({
            "tool_type": tool_type, "fac_id": fac_id, "prod_id": prod_id, "lot_cd": lot_cd,
            "oper_id": f"{rng.choice(_OPER_PREFIXES)}-{rng.randint(100, 999)}",
            "oper_desc": oper_desc, "oper_seq": oper_seq, "samp_seq": samp_seq,
            "recipe_id": _pick_recipe(rng, spec, rows, lot_cd, idx), "eqp_id": rng.choice(eqps),
            "skip_yn": _skip_yn(rng, spec),
            "chg_tm": _kst(base_time - timedelta(hours=rng.randint(0, 24 * 120))),
        })
    return rows


def _m_steps(rng, tool_type, spec, fac_id, lot_cd, n, eqps) -> list[FamilyStepRow]:
    """M fab — 90일 창의 unique oper_det_desc. 순서·skip·chg_tm·prod_id 가 없습니다."""
    rows: list[FamilyStepRow] = []
    seen: set[str] = set()
    for idx in range(n * 3):               # 이름이 겹치면 다시 뽑되 무한히는 아님
        if len(rows) == n:
            break
        oper_desc = _step_name(rng, spec)
        if oper_desc in seen:
            continue
        seen.add(oper_desc)
        rows.append({
            "tool_type": tool_type, "fac_id": fac_id, "prod_id": "", "lot_cd": lot_cd,
            "oper_id": f"{rng.choice(_OPER_PREFIXES)}-{rng.randint(100, 999)}",
            "oper_desc": oper_desc, "oper_seq": None, "samp_seq": None,
            "recipe_id": _pick_recipe(rng, spec, rows, lot_cd, idx), "eqp_id": rng.choice(eqps),
            "skip_yn": "", "chg_tm": "",
        })
    return rows


def _recipe_tables(
    tool_type: FamilyToolType, spec: _Spec, steps: list[FamilyStepRow], base_time,
) -> tuple[list[FamilyParamRow], list[FamilyRecipeStatusRow]]:
    first_eqp: dict[str, str] = {}
    fabs: dict[str, list[str]] = {}
    for step in steps:
        first_eqp.setdefault(step["recipe_id"], step["eqp_id"])
        if step["fac_id"] not in fabs.setdefault(step["recipe_id"], []):
            fabs[step["recipe_id"]].append(step["fac_id"])

    params: list[FamilyParamRow] = []
    statuses: list[FamilyRecipeStatusRow] = []
    kind = spec["source_kind"]
    for recipe_id in sorted(first_eqp):
        prng = random.Random(spec["seed"] ^ _digest(f"{tool_type}:{recipe_id}"))
        status = prng.choices(STATUSES, weights=spec["status_weights"])[0]
        when = base_time - timedelta(hours=prng.randint(0, 24 * 60))
        ref = f"v{prng.randint(1, 30)}" if kind == "idp" else (
            f"{first_eqp[recipe_id]}:{(when + timedelta(hours=9)):%Y%m%d%H%M%S}"
        )
        has_source = status in ("ok", "empty")
        statuses.append({
            "tool_type": tool_type, "recipe_id": recipe_id, "status": status,
            "source_kind": kind,  # type: ignore[typeddict-item]
            "source_ref": ref if has_source else "",
            "source_tm": _kst(when) if has_source else "",
            "note": "parse error: unexpected parameter block" if status == "failed" else "",
        })
        if status != "ok":
            continue

        built = _build_parameters(
            prng, bloated=prng.random() < 0.1, over_measured=False,
            exempt_job=is_exempt_job(recipe_id),
            helpers=_has_helper_params(f"{tool_type}:{recipe_id}"),
        )
        if spec["has_mother"]:
            _assign_regions(built, True, prng)
        if tool_type == "hv-sem":
            _hv_raw_names(built, prng)
        # 표 B 는 (tool_type, recipe_id, fac_id) 마다 한 벌입니다 (S2 A). 대부분 fab 이
        # 달라도 같은 벌이고, 일부 recipe 만 뒤 fab 에서 마지막 파라미터가 빠집니다(R2).
        diff = len(fabs[recipe_id]) > 1 and prng.random() < FAB_DIFF_RATIO
        for nth, fac_id in enumerate(sorted(fabs[recipe_id])):
            rows = built[:-1] if diff and nth and len(built) > 1 else built
            params += _param_rows(tool_type, spec, recipe_id, fac_id, rows)
    return params, statuses


def _param_rows(tool_type, spec, recipe_id, fac_id, built) -> list[FamilyParamRow]:
    out: list[FamilyParamRow] = []
    for seq, param in enumerate(built, start=1):
        out.append({
            "tool_type": tool_type, "recipe_id": recipe_id, "fac_id": fac_id, "param_seq": seq,
            "param_name": param["name"],
            "param_type": (
                hv_param_type(param["name"]) if tool_type == "hv-sem"
                else _param_type(param["name"]) if spec["typed_params"] else ""
            ),
            "point_count": param["point_count"],
            "mother": param["mother"] if spec["has_mother"] else None,
            "region": param["region"] if spec["has_mother"] else None,
        })
    return out


def _hv_raw_names(built: list, prng: random.Random) -> None:
    """hvsem_idp_ver raw_data 의 이름 성질을 옮깁니다 (office 확인 2026-11-04).

    빈 Parameter 가 행의 4.9%, 이름이 겹치는 파라미터가 있는 문서가 52.7% 입니다.
    종류는 이름 안의 토큰으로만 드러납니다(R4) — CD-SEM 접두사형 이름은 일부만
    남기고 나머지를 토큰형·종류 없음으로 바꿉니다.
    표 B 의 정체성은 (recipe_id, param_seq) 라 이름은 키가 아닙니다 — 이름으로
    접거나 dict 키로 쓰는 코드가 집에서 깨지게 합니다. 맨 앞 Dummy·Align 은
    건드리지 않습니다(그 판정은 이름 + 위치).
    """
    measured = [p for p in built if not has_non_measurement_name(p["name"])]
    for param in measured:
        kind = _param_type(param["name"])
        if kind not in _HV_TOKEN:
            continue
        rest = param["name"][len(kind):].strip("_") or "1"
        roll = prng.random()
        if roll < HV_PREFIX_NAME_P:
            continue                                   # CD-SEM 접두사 규칙으로 잡히는 5.7%
        param["name"] = (
            f"{rest}_{_HV_TOKEN[kind]}" if roll < HV_PREFIX_NAME_P + HV_TOKEN_NAME_P
            else f"PT_{rest}"                          # 어느 규칙으로도 종류가 없음
        )
    if prng.random() < HV_DUP_NAME_RATIO and len(measured) >= 2:
        measured[-1]["name"] = measured[0]["name"]
    for param in measured:
        if prng.random() < HV_BLANK_PARAM_RATIO:
            param["name"] = ""


def _share_recipes_across_fabs(steps: list[FamilyStepRow], seed: int) -> None:
    """M fab step 일부가 R3 recipe 를 씁니다 — 같은 recipe 가 fab 마다 표 B 한 벌씩.

    rng 를 따로 둬 기존 step·recipe 값이 다시 태어나지 않게 합니다.
    """
    rng = random.Random(seed ^ 0xFAB)
    r3_recipes = sorted({s["recipe_id"] for s in steps if s["prod_id"]})
    for step in steps:
        if not step["prod_id"] and rng.random() < CROSS_FAB_STEP_RATIO:
            step["recipe_id"] = rng.choice(r3_recipes)


@lru_cache(maxsize=None)
def _tables(tool_type: FamilyToolType):
    # 순환 import 회피: mock.py 가 이 모듈을 맨 아래에서 재노출합니다.
    from backend.ebeam.device_statistics.providers import mock

    spec = FAMILY_SPECS[tool_type]
    rng = random.Random(spec["seed"])
    tools = _tools_by_fab(tool_type)
    catalog: dict[str, list[str]] = {"R3": [r["lot_cd"] for r in mock.get_r3_device_grp()]}
    for row in mock.get_device_desc():
        catalog.setdefault(row["fac_id"], []).append(row["lot_cd"])

    steps: list[FamilyStepRow] = []
    lots_by_fab: dict[str, list[str]] = {}
    for fac_id in sorted(tools):
        pool = catalog.get(fac_id, [])
        m_fabs = len(tools) - 1
        size = (spec["r3_lots"] - spec["off_catalog"] if fac_id == "R3"
                else round(spec["m_lots"] / m_fabs))
        lots = sorted(rng.sample(pool, min(size, len(pool))))
        if fac_id == "R3":
            # R4 device 는 세 계열에 같은 두 lot 입니다 — 계열 seed 와 무관하게 고릅니다.
            r4_lots = set(random.Random(_R4_SEED).sample(sorted(pool), R4_LOTS))
            lots = sorted(set(lots[: size - R4_LOTS]) | r4_lots)
            cap_lots = set(rng.sample(sorted(set(lots) - r4_lots), CAP_LOTS))
            # 카탈로그에 없는 device (Q11 B) — 카탈로그에 없는 이름으로 지어 붙입니다.
            extra = [f"RZ{i:02d}" for i in range(spec["off_catalog"])]
            assert not set(pool) & set(extra)
            lots += extra
        lots_by_fab[fac_id] = lots
        for lot_cd in lots:
            if fac_id == "R3":
                prod_id = lot_cd + ("_CAP_BASE" if lot_cd in cap_lots else "_BASE")
                assert lot_cd_from_prod_id(prod_id) == lot_cd
                det_fac_id = "R4" if lot_cd in r4_lots else "R3"
                steps += _r3_steps(rng, tool_type, spec, det_fac_id, lot_cd, prod_id,
                                   rng.randint(*spec["r3_steps"]), tools[fac_id], mock.BASE_TIME)
            else:
                steps += _m_steps(rng, tool_type, spec, fac_id, lot_cd,
                                  rng.randint(*spec["m_steps"]), tools[fac_id])

    _share_recipes_across_fabs(steps, spec["seed"])
    params, statuses = _recipe_tables(tool_type, spec, steps, mock.BASE_TIME)

    activity: list[FamilyActivityRow] = []
    for fac_id, lots in lots_by_fab.items():
        active = [lot for lot in lots if rng.random() < spec["active_ratio"]]
        spare = sorted(set(catalog.get(fac_id, [])) - set(lots))
        extra = rng.sample(spare, min(len(spare), max(1, round(len(lots) * NO_STEP_RATIO))))
        ranked = [
            {
                "tool_type": tool_type, "fac_id": fac_id, "lot_cd": lot_cd,
                "meas_count": mock._meas_count(f"{tool_type}:{lot_cd}"),
                "window_days": WINDOW_DAYS, "as_of": _kst(mock.BASE_TIME),
            }
            for lot_cd in active + extra
        ]
        ranked.sort(key=lambda r: (-r["meas_count"], r["lot_cd"]))
        activity += ranked  # type: ignore[arg-type]

    return tuple(steps), tuple(params), tuple(statuses), tuple(activity)


def get_family_steps(tool_type: FamilyToolType) -> list[FamilyStepRow]:
    """표 A."""
    return list(_tables(tool_type)[0])


def get_family_params(tool_type: FamilyToolType) -> list[FamilyParamRow]:
    """표 B — status == "ok" 인 recipe 만 행이 있습니다."""
    return list(_tables(tool_type)[1])


def get_family_recipe_status(tool_type: FamilyToolType) -> list[FamilyRecipeStatusRow]:
    """표 C — 표 A 의 distinct recipe 마다 한 행."""
    return list(_tables(tool_type)[2])


def get_family_activity(tool_type: FamilyToolType) -> list[FamilyActivityRow]:
    """표 D — fab 별로 meas_count 내림차순."""
    return list(_tables(tool_type)[3])
