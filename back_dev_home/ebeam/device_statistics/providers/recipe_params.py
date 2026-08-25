"""recipe-params data surface (D22). device(lot_cd) 1개 = recipe 100~200개,
recipe 1개 = 파라미터 다수, 파라미터마다 측정 point 수가 다릅니다. 프론트
ruleEngine.ts 의 RecipeInput 형태와 1:1 로 맞춥니다 (lot_cd, recipe_id,
fac_id, ctn_desc, prod_catg_cd, recipe_class, family, phase,
memory_class_auto, parameters[{name, point_count}]).

설계:  docs/issues/ground_rules/grilling-log.md (D22), rule-editor-structure.md §8-bis(B)
소비:  front-dev-home/app/utils/ruleEngine.ts (evaluateLot) · outlierDetect.ts (detectDeviceOutliers)

Phase 1 mock: lot 당 결정론적 seed 로 recipe·parameter 생성. 일부 recipe 에
의도적으로 (a) point-count outlier 와 (b) cap 위반 파라미터를 심어 두 소비처
(outlier 뷰 · R3 compliance)가 모두 실데이터로 검증되게 합니다.

사무실 파생 규칙 (user-confirmed 2026-07-31) — 이 mock 이 난수로 고르는 분류
컬럼들은 실물에서 **파생**됩니다. 규칙 전문은
docs/datatables/hitachi/recipe_params.txt 의 "사무실 파생 규칙" 절이고, 요지는:

- recipe_class -> **recipe 이름이 "_S"/"SE" 로 끝나면 Sample**. 끝자리 고정
  이어야 합니다 — 이름 어디든 "SE" 를 찾으면 PHASE/BASE/SET 이 전부 Sample 이
  되고, recipe_class 가 프론트의 cap 선택 축(D2)이라 위반 판정까지 뒤집힙니다.
- family -> device ctn_desc 에서 파생하며 **VG·RTC·Cubic > Pool > Core** 순서
  입니다. VG 는 표기가 여럿이라("Vertical Gate"/"Vertical"/"VG"/"RTC"/"Cubic")
  office `_VG_TOKEN` 이 다섯을 모두 잡습니다 (user-confirmed 2026-08-25).
  2026-07-31 의 "VG 는 판별 근거가 없어 발행하지 않는다" 는 철회되었습니다.
- family 와 phase 는 **device 의** ctn_desc 한 문자열에 같이 실립니다
  ("DRAM Pool제 (@Spica PV)"). 둘 다 파생하되 룰 판정에서는 Pool 이 phase 를
  이깁니다(ruleEngine.ts `selectorMatches`). 그 문자열을 내는 것은 이 모듈이
  아니라 `mock.py` 의 device 행이고, 여기 `ctn_desc` 는 공정 스텝 이름입니다.
- prod_catg_cd -> R3 카탈로그에만 있습니다. 이 mock 은 M fab lot 에도 값을
  지어내지만(_prod_catg_for 의 fallback), 실물은 빈 값이고 따라서
  memory_class_auto 가 unknown(수동 분류) 으로 떨어집니다.

Internal module: callers outside this feature must import the public
surface from `device_statistics.data` (the provider switch), not this file
directly.
"""

import hashlib
import random
from typing import Literal

from back_dev_home.ebeam.device_statistics.contracts import (
    ParameterRow,
    RecipeParamsRow,
)
from back_dev_home.ebeam.device_statistics.para_buckets import (
    has_non_measurement_name,
)
from back_dev_home.ebeam.device_statistics.providers.recipe_population import (
    MOTHER_SHARE,
    RecipeIdentity,
    build_population,
    is_exempt_job,
    is_sample_recipe,
    mother_para_all,
)


# mother 표시를 point_count rng 와 갈라놓는 salt. 같은 rng 를 더 굴리면 뒤따르는
# recipe 의 파라미터 값이 전부 달라집니다 (recipe_population._MOTHER_SALT 와 같은
# 이유입니다).
_MOTHER_MARK_SALT = 70009


# recipe 수·이름은 이제 recipe_population 이 정합니다 — 여기서 따로 세면 두 표면의
# recipe_id 가 갈라져 조인이 깨집니다 (예전이 그랬습니다). 도메인 100~200 (D22) 은
# 그 모듈의 POOL_RANGE 와 주차 배율이 함께 만족합니다.

FAMILIES: tuple[str, ...] = ("Core", "Pool", "VG_RTC_Cubic")
PHASES: tuple[str, ...] = ("t-EV", "EV", "TV", "PV")

# Parameter-name templates per type, chosen to exercise ruleEngine.deriveType
# (longest-prefix EDGE_EX > EDGE > WAFER > LEVEL; everything else = OTHER).
WAFER_NAMES = ("WAFER_CD", "WAFER_2", "WAFER_OVL")
LEVEL_NAMES = ("LEVEL_1", "LEVEL_2", "LEVEL_3", "LEVEL_4")
EDGE_NAMES = ("EDGE_L", "EDGE_R", "EDGE_T", "EDGE_B")
EDGE_EX_NAMES = ("EDGE_EX_L", "EDGE_EX_R")
# OTHER bucket — the bag that balloons (D10). Includes a WAFER-companion
# (OVL_WF) so the Main DSPT/WF/WAFER name-override path is exercised.
OTHER_NAMES = ("OVL_X", "OVL_Y", "DSPT_1", "CD_BAR", "PITCH_A", "OVL_WF", "SPACE_1")

# CD 측정량을 논하는 자리에 낄 수 없는 파라미터들. 둘 다 실물에 있는 이름
# 입니다 (user-confirmed 2026-08-05).
#
# **대소문자가 이 값들의 핵심입니다.** 실물 파라미터 이름은 대체로 전부 대문자
# 인데(위 OTHER_NAMES 처럼) 이 둘만 그렇지 않습니다 — "Dummy", "Align" 입니다
# (user-confirmed 2026-08-05). 그래서 걸러 내는 쪽은 양쪽 모두 대소문자를
# 무시하고, mock 은 **실물 표기 그대로** 씁니다.
#
# 여기를 대문자로 적어 두면 두 가지를 동시에 잃습니다: 대소문자 무시 경로가
# 집에서 한 번도 실행되지 않고, mock 이 "이 이름도 대문자다" 라는 거짓을
# 가르칩니다. 규칙을 `name == "DUMMY"` 로 좁혀 놔도 집에서는 통과하고 사무실
# 에서만 조용히 새어 나가는 종류의 실수입니다.
#
# point_count 를 이렇게 고른 것은 **두 제외 경로가 집에서 눈에 보이게** 하기
# 위해서입니다. 값이 아무거나면 규칙을 지워도 화면이 똑같아 회귀가 조용히
# 통과합니다.
#
#   Dummy 1  — Sample 셀은 _other cap 이 0 이라 1 이면 곧바로 위반입니다.
#              면제가 빠지는 순간 위반 수가 눈에 띄게 늡니다.
#   Align 3  — 아래 ★★ 참고. 이 값은 **작아서** 일합니다.
#
# ★ 둘 다 point 수가 **1~3** 입니다 (user-confirmed 2026-08-10). 이 자리는
#   2026-08-05 에 Align 40, 2026-08-10 에 잠시 16 이었고, 둘 다 지어낸 값이었습니다.
#
#   40 이 오래 눈에 띄지 않은 이유가 기록해 둘 만합니다. 정확 일치 버킷 시절에는
#   40 이 16/13/9/5 어디에도 맞지 않아 **아무 버킷에도 안 들어가** 보이지
#   않았는데, 버킷이 구간이 되자 para_over_16 으로 들어갔습니다. Sample recipe 가
#   전체의 25% 라 그것만으로 "recipe 의 30% 가 16 초과 파라미터를 갖는" 그림이
#   됐고, 실물은 3% 입니다. 지어낸 값이 자고 있다가 정의가 바뀌는 순간 깨어난
#   경우입니다.
#
# ★★ outlier 제외 회귀의 방향이 **뒤집혔습니다.**
#
#   Align 40/16 시절의 논리는 "큰 point 수가 중앙값 기준선을 끌어올려 진짜 과다
#   측정을 가린다" 였습니다. 실물 값이 1~3 이면 그 일은 일어나지 않습니다 —
#   대신 **기준선을 끌어내립니다.** 제외를 지우면 중앙값이 내려가고 문턱
#   (중앙값×2)도 함께 내려가, 정상 범위의 파라미터가 outlier 로 잡힙니다.
#   즉 규칙이 막는 것은 이제 "가려짐" 이 아니라 "오검출" 입니다.
#
#   회귀가 살아 있으려면 문턱이 내려갈 때 그 사이에 걸리는 파라미터가 실제로
#   있어야 합니다. tests/test_non_measurement_params.py 가 그것을 셉니다 —
#   Align 값을 만질 때 그 테스트가 유일한 안전망입니다.
#
# 16 초과 신호는 이 둘이 아니라 **측정 파라미터 이름**이 나릅니다 (특수 측정
# job 의 EDGE_*/OVL_*, over_measured 의 EDGE_R). 비측정 파라미터로 그 신호를
# 만들면 통계에서 빠지는 이름이 통계를 만드는 모순이 됩니다.
#
# OFFICE-VERIFY: 1~3 안의 정확한 값은 확인된 바 없습니다. 이름의 표기는
# 확인된 사실입니다.
#
# OTHER_NAMES 에 넣지 않은 것은 저 풀이 rng 로 뽑히는 대상이라, 원소를 더하면
# 뒤따르는 모든 recipe 의 파라미터 값이 달라지기 때문입니다.
NON_MEASUREMENT_PARAMS: tuple[tuple[str, int], ...] = (
    ("Dummy", 1),
    ("Align", 3),
)

# Typical point counts per type (cap-respecting baseline so most recipes pass).
TYPICAL_POINTS = {
    "WAFER": (9, 13),
    "LEVEL": (1, 4),
    "EDGE": (6, 14),
    "EDGE_EX": (0, 0),
    "OTHER": (1, 8),
}

# 특수 측정 job(_*CDU/_FULL/_HALF/_MTX)의 측정 배율. 웨이퍼 전면을 훑는 job 이라
# 파라미터당 point 수가 정상 recipe 와 자릿수부터 다릅니다.
#
# 이 배율이 없으면 mock 의 CDU job 이 정상 recipe 와 똑같이 측정하는 것처럼
# 보여, **실물에 대해 거짓을 가르칩니다**. 동시에 이 job 들을 중앙값 기준선에서
# 빼는 outlierDetect 의 이유(큰 값이 기준선을 끌어올려 진짜 과다 측정을 가림)가
# 집에서는 한 번도 재현되지 않습니다 — 배율이 1 이면 빼나 마나 같은 값이라
# 회귀가 조용히 통과합니다.
#
# 이미 뽑은 값에 곱하기만 합니다. 여기서 rng 를 더 굴리면 뒤따르는 recipe 의
# 파라미터가 전부 다른 값으로 다시 태어납니다 (_mark_mothers 의 같은 주의).
#
# OFFICE-VERIFY: 실물 배율은 확인된 바 없습니다 — "자릿수가 다르다" 는 성질만
# 재현하고 절대값은 흉내 내지 않습니다.
EXEMPT_JOB_POINT_SCALE = 8


def _memory_class_auto(prod_catg_cd: str) -> str:
    # (x or "") like the office adapter: prod_catg_cd is R3-only, so an M-fab
    # lot can arrive with None and a bare .upper() would AttributeError.
    c = (prod_catg_cd or "").upper()
    if c == "DRAM":
        return "DRAM"
    if c in ("NAND", "FLASH"):
        return "NAND"
    return "unknown"  # Tech / Advanced / absent → 수동 (D7)


# Dummy·Align 이 붙는 recipe 비율. rng 가 아니라 이름 digest 로 고르므로 이 값을
# 바꿔도 다른 파라미터 값은 한 바이트도 움직이지 않습니다. 파이썬 hash() 는
# PYTHONHASHSEED 로 실행마다 달라져 쓸 수 없습니다.
#
# OFFICE-VERIFY: "가끔" 의 실제 비율은 확인된 바 없습니다 (user-confirmed
# 2026-08-10 은 "일부 recipe 에 가끔" 까지입니다).
HELPER_PARAM_RATIO = 0.20


def _has_helper_params(recipe_id: str) -> bool:
    """이 recipe 에 Dummy·Align 이 붙는가."""
    digest = hashlib.sha256(f"helpers:{recipe_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100 < HELPER_PARAM_RATIO * 100


def _build_parameters(
    rng: random.Random,
    bloated: bool,
    over_measured: bool,
    exempt_job: bool = False,
    helpers: bool = False,
) -> list[ParameterRow]:
    params: list[ParameterRow] = []

    def add(name: str, lo: int, hi: int) -> None:
        # mother·region 은 _assign_regions 가 나중에 채웁니다 — 여기서 굴리면 아래
        # 난수 순서가 밀려 기존 point_count 가 전부 다른 값이 됩니다.
        params.append({
            "name": name, "point_count": rng.randint(lo, hi),
            "mother": False, "region": None,
        })

    add(rng.choice(WAFER_NAMES), *TYPICAL_POINTS["WAFER"])
    for name in rng.sample(LEVEL_NAMES, rng.randint(1, 4)):
        add(name, *TYPICAL_POINTS["LEVEL"])
    for name in rng.sample(EDGE_NAMES, rng.randint(1, 4)):
        add(name, *TYPICAL_POINTS["EDGE"])

    # OTHER bag: normally a few; a "bloated" recipe carries many (D10 signal).
    other_pool = list(OTHER_NAMES)
    other_count = rng.randint(5, len(other_pool)) if bloated else rng.randint(1, 3)
    for i, name in enumerate(other_pool[:other_count]):
        suffix = f"_{i}" if i >= len(other_pool) else ""
        add(f"{name}{suffix}", *TYPICAL_POINTS["OTHER"])

    # over_measured recipe: push ONE EDGE param far above its peers so both the
    # within-device outlier detector and the R3 EDGE cap flag it.
    if over_measured and params:
        params[-1] = {
            "name": "EDGE_R", "point_count": rng.randint(40, 60),
            "mother": False, "region": None,
        }

    # 특수 측정 job 은 배율만 먹입니다 — 이름·개수·순서는 그대로 두어야 위 난수
    # 순서가 한 칸도 밀리지 않습니다. 아래 Dummy/Align 을 **붙이기 전에** 거는
    # 것이 중요합니다: 배율이 걸리면 Align 3 이 24 가 되어, "1~3" 이라는 실물
    # 사실도 "비측정 파라미터는 16 을 넘지 않는다" 도 함께 깨집니다.
    if exempt_job:
        for param in params:
            param["point_count"] *= EXEMPT_JOB_POINT_SCALE

    # Dummy·Align 은 recipe 마다 늘 있는 것이 아니라 **가끔** 나타나고, 나타날
    # 때는 측정 순서의 **맨 앞**에 옵니다 (user-confirmed 2026-08-10). 정렬은
    # 측정보다 먼저 하는 준비 작업이라 순서가 곧 그 뜻이고, para_* 집계도 그
    # 위치로 걸러냅니다 (para_buckets.measurement_parameters).
    #
    # 2026-08-05~2026-08-10 에는 Sample recipe 에만, 그것도 **맨 뒤**에 붙였습니다.
    # 위치가 뒤집혀 있었으므로 위치 기반 규칙이라면 아무것도 걸러지지 않았을
    # 자리입니다.
    #
    # 붙일 recipe 를 rng 가 아니라 이름 digest 로 고르는 것이 요점입니다 — 여기서
    # 난수를 한 번이라도 더 굴리면 lot 단위로 공유되는 rng 가 밀려 뒤따르는
    # recipe 의 파라미터가 전부 다른 값으로 다시 태어납니다(_mark_mothers 의 같은
    # 주의). point_count 도 같은 이유로 고정값입니다.
    #
    # OFFICE-VERIFY: "가끔" 의 실제 비율은 확인된 바 없습니다.
    if helpers:
        for name, point_count in reversed(NON_MEASUREMENT_PARAMS):
            params.insert(0, {
                "name": name, "point_count": point_count,
                "mother": False, "region": None,
            })

    return params


def _assign_regions(
    params: list[ParameterRow],
    has_mother: bool,
    mother_rng: random.Random,
    force_head_last: bool = False,
) -> None:
    """``parameters`` 를 **image definition 묶음**(region)으로 갈라, 각 묶음의 머리를
    mother 로 켭니다 (제자리 수정).

    실물에서 idp 의 한 ``Region`` 이 image definition 1개이고, 같은 region 인
    파라미터들이 한 SEQ 그룹입니다 — 화면의 "1/8, 2/8, 3/8 …" 이 그 묶음이고
    그 안의 ``Mother_Para`` 하나가 image 의 주인, 나머지는 son 입니다
    (user-confirmed 2026-08-18). son 은 mother 와 **같은 image** 에서 자기 cd_value
    를 꺼내므로, 프론트엔드의 계측 룰 판정은 son 을 자기 이름의 타입 cap 이 아니라
    그 묶음 mother 의 cap 으로 잽니다 (ruleEngine.groupCaps).

    그래서 mother 를 **흩어 놓으면 안 됩니다.** 2026-08-18 이전에는 index 를
    무작위로 골라 켰고, 그러면 "mother 가 자기 묶음의 머리" 라는 성질이 없어 son 을
    mother 에 이어 붙일 방법 자체가 없습니다. 묶음을 연속 구간으로 잡는 것은
    파라미터 순서가 곧 측정 순서(= SEQ 순서)이기 때문입니다
    (docs/datatables/hitachi/recipe_params.txt).

    ★ **son 의 point 수는 mother 를 따라가지 않고, 다만 넘지 않습니다.**

      실물 문서 1건이 ``{'EDGE': 10, 'LEVEL': 4, 'WAFER': 10}`` 이고 그 WAFER 가
      mother, LEVEL 이 son 입니다 (docs/datatables/hitachi/idp_ver.txt) — son 이 mother
      보다 **적게** 잰 경우입니다. 반대로 묶음이 통째로 같은 값인 경우(WAFER 13 에
      son 도 13)도 실물에 있습니다 (user-confirmed 2026-08-18). 둘 중 하나로
      고정하면 없는 규칙을 지어내는 셈이라, 뽑은 값을 그대로 두고 **머리보다 큰
      값만 머리에 맞춰 내립니다**.

      내리는 이유는 그러지 않으면 mock 이 거짓을 가르치기 때문입니다. 묶음의
      경계가 난수라 EDGE(6~14) son 이 LEVEL(1~4) mother 밑에 자주 들어가고, 그러면
      물려받은 cap 4 를 넘겨 **집에서만 존재하는 위반**이 무더기로 잡힙니다. 실물
      에서 son 은 mother 의 image 안에서 재므로 그 image 가 주는 point 보다 많이
      잴 수 없고, 따라서 son 위반은 mother 가 이미 자기 cap 을 넘었을 때나
      나타납니다.

      OFFICE-VERIFY: "son ≤ mother" 는 확인된 문서 1건과 "같은 image 를 쓴다" 는
      사실에서 따라오는 **추론**입니다. son 이 한 site 에서 여러 값을 재어 mother
      보다 point 가 많아지는 형태라면 틀립니다. 판정 자체는 어느 쪽이든 옳게
      동작하므로(넘으면 위반), 틀렸을 때 잃는 것은 mock 의 사실성뿐입니다.

    ``has_mother`` 는 :func:`recipe_population.build_population` 이 만든
    identity 가 정합니다 — 이 표면이 따로 굴리면 안 됩니다. recipe-statistics 의
    mother_normal 버킷 멤버십이 바로 그 identity 로 정해지므로, 두 표면이
    어긋나면 **버킷에는 있는데 mother 파라가 하나도 없는 recipe** 가 생기고
    프론트엔드의 health 가 조용히 0/0(판정 없음)으로 떨어집니다.

    region 은 ``has_mother`` 와 **무관하게** 붙입니다 — 실물의 Region 은 mother 를
    읽을 수 있는지와 상관없이 존재하고, mother 없는 묶음에서 프론트엔드가 각자 자기
    cap 으로 되돌아가는 경로가 집에서 실제로 실행되어야 합니다.

    ``mother_rng`` 를 따로 받는 이유는 위 point_count 를 뽑는 rng 를 여기서 더
    굴리면 뒤따르는 recipe 의 파라미터 값이 전부 달라지기 때문입니다.

    ``force_head_last`` 는 마지막 파라미터를 반드시 묶음의 머리로 둡니다 —
    over_measured recipe 가 심어 둔 EDGE_R 과다측정이 son 이 되면 mother 의 큰
    cap 뒤로 숨어, outlier·cap 두 신호가 함께 사라집니다.
    """
    # Dummy·Align 은 측정 파라미터가 아니라 image 묶음에 들지 않습니다. 맨 앞의
    # 연속된 것만 걷어내는 것은 para_buckets.measurement_parameters 와 같은
    # 규칙입니다 — 목록 뒤쪽의 "CD_ALIGN" 같은 진짜 측정 파라미터는 남깁니다.
    start = 0
    while start < len(params) and has_non_measurement_name(params[start]["name"]):
        params[start]["region"] = None
        start += 1

    body = len(params) - start
    if body <= 0:
        return

    # 묶음 개수 = mother 개수 (묶음마다 머리가 하나). son 이 mother 의 image 를 함께
    # 쓰므로 mother 는 소수이고, 따라서 한 묶음에 여럿이 들어갑니다.
    #
    # OFFICE-VERIFY: 실물에서 관찰된 묶음 하나는 8개짜리("1/8 … 8/8")로 이 비중이
    # 만드는 2~4 보다 큽니다. MOTHER_SHARE 는 recipe_population 과 **공유하는**
    # 값이라 여기서만 넓히면 두 표면의 mother 수가 갈라집니다.
    group_count = min(body, max(1, round(body * mother_rng.uniform(*MOTHER_SHARE))))
    heads = {start}
    if group_count > 1:
        heads.update(mother_rng.sample(range(start + 1, len(params)), group_count - 1))
    if force_head_last:
        heads.add(len(params) - 1)

    region = 0
    head_points = 0
    for index in range(start, len(params)):
        if index in heads:
            region += 1
            params[index]["mother"] = has_mother
            head_points = params[index]["point_count"]
        else:
            # son 은 머리의 image 안에서 재므로 그보다 많이 잴 수 없습니다.
            # 자르기만 하므로 rng 는 한 번도 더 굴리지 않습니다.
            params[index]["point_count"] = min(params[index]["point_count"], head_points)
        params[index]["region"] = region


def _build_recipe(
    rng: random.Random,
    mother_rng: random.Random,
    identity: RecipeIdentity,
    lot_cd: str,
    fac_id: str,
    prod_catg_cd: str,
    idx: int
) -> RecipeParamsRow:
    # recipe_class 는 굴리지 않고 **recipe 이름에서 파생**합니다 — 실물도 그렇고
    # (office_example.py: "only_sample 버킷과 같은 규칙"), 굴리면 같은 recipe 가
    # only_sample 버킷에는 있는데 recipe_class 는 Main 인 모순이 생깁니다.
    recipe_class: Literal["Main", "Sample"] = (
        "Sample" if is_sample_recipe(identity["recipe_id"]) else "Main"
    )
    family = rng.choice(FAMILIES)
    phase = rng.choice(PHASES)
    bloated = rng.random() < 0.08       # ~8% of recipes over-parameterized
    # 1% 입니다(예전 5%). 16 point 를 넘는 파라미터가 있는 recipe 는 전체의 3%
    # 뿐이고 그 대부분은 아래 exempt_job 이므로(user-confirmed 2026-08-10),
    # "정상 recipe 안의 외톨이 과다측정" 은 그보다 더 드물어야 합니다. lot 당
    # recipe 가 100~200 개라 1% 여도 outlier 경로는 매 lot 에서 실행됩니다.
    over_measured = rng.random() < 0.01  # ~1% with a point-count outlier
    parameters = _build_parameters(
        rng,
        bloated,
        over_measured,
        is_exempt_job(identity["recipe_id"]),
        _has_helper_params(identity["recipe_id"]),
    )
    # mother 보유 여부는 identity 가 정합니다 — recipe-statistics 의 mother_normal
    # 버킷 멤버십과 같은 원천이어야 두 표면이 갈라지지 않습니다.
    _assign_regions(
        parameters, mother_para_all(identity) > 0, mother_rng,
        force_head_last=over_measured,
    )

    return {
        "lot_cd": lot_cd,
        "recipe_id": identity["recipe_id"],
        "fac_id": fac_id,
        # 사무실에서 이 컬럼은 device 설명문이 아니라 그 recipe 가 걸린
        # **공정 스텝 이름**(R3 oper_desc)입니다 — office_example.py 는
        # step["oper_desc"] 를 싣습니다. statistics.py 의 recipe 행도 같은
        # identity["step_ctn_desc"] 를 쓰므로 두 mock 표면이 일치합니다.
        # device 쪽 설명문(Pool/phase 토큰이 있는 그것)은 mock.py 의
        # get_device_desc()/get_r3_device_grp() 가 냅니다.
        "ctn_desc": identity["step_ctn_desc"],
        "prod_catg_cd": prod_catg_cd,
        "recipe_class": recipe_class,
        "family": family,
        "phase": phase,
        "memory_class_auto": _memory_class_auto(prod_catg_cd),
        "parameters": parameters,
    }


def _prod_catg_for(lot_cd: str, fac_id: str) -> str:
    """Reuse the device's own prod_catg_cd when it is an R3 lot; M-fab device-desc
    rows carry no prod_catg_cd, so fall back to a deterministic pick."""
    from .mock import get_r3_device_grp  # deferred import — avoid circular load
    for row in get_r3_device_grp():
        if row["lot_cd"] == lot_cd:
            return row["prod_catg_cd"]
    rng = random.Random(_recipe_seed(lot_cd, 9991))
    return rng.choice(["DRAM", "NAND", "FLASH", "Tech", "Advanced"])


def _recipe_seed(lot_cd: str, salt: int) -> int:
    from .statistics import _seed_for  # deferred import
    return _seed_for(lot_cd, salt)


def get_recipe_params(lot_cds: list[str] | None = None) -> list[RecipeParamsRow]:
    """Flat list of recipe rows (RecipeInput shape) for the requested lots.

    Empty / None lot_cds → every known lot (can be large; callers should pass a
    selection). Deterministic per lot_cd via _seed_for."""
    from .statistics import (  # deferred import
        DEFAULT_TREND_POINTS, _lot_index, _resolve_lots, _seed_for,
    )
    index = _lot_index()
    selected = _resolve_lots(lot_cds)

    rows: list[RecipeParamsRow] = []
    for lot_cd in selected:
        fac_id = index[lot_cd]
        prod_catg_cd = _prod_catg_for(lot_cd, fac_id)
        # recipe-statistics 가 보여주는 것은 트렌드의 **마지막 주차**이므로
        # (routes.py recipe_statistics), 같은 주차의 모집단을 부릅니다. 이 한 줄이
        # 두 표면을 recipe_id 로 조인 가능하게 만듭니다.
        population = build_population(
            lot_cd, DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS
        )
        rng = random.Random(_seed_for(lot_cd, 4242))
        mother_rng = random.Random(_seed_for(lot_cd, 4242) ^ _MOTHER_MARK_SALT)
        # 모집단은 스텝 단위인데 이 표면은 **recipe 단위**입니다 — 실물의 원천이
        # cdsem_idp_ver 이고 거기서는 full_name(=recipe_id) 하나에 파라미터 한 벌뿐
        # 이기 때문입니다. 여러 스텝이 같은 recipe 를 쓰면 그 파라미터는 한 벌입니다.
        seen: set[str] = set()
        for idx, identity in enumerate(population):
            # 중복도 **일단 만듭니다.** 건너뛰면 rng 호출 수가 줄어 뒤따르는 recipe 의
            # 파라미터가 전부 다른 값으로 태어납니다 (_MOTHER_MARK_SALT 주석과 같은
            # 이유). 버리는 것은 만든 다음입니다.
            row = _build_recipe(rng, mother_rng, identity, lot_cd, fac_id, prod_catg_cd, idx)
            if row["recipe_id"] in seen:
                continue
            seen.add(row["recipe_id"])
            rows.append(row)
    return rows


if __name__ == "__main__":
    # 미리보기:  python -m back_dev_home.ebeam.device_statistics.providers.recipe_params
    import pprint
    rows = get_recipe_params(["R000"])
    print(f"R000 recipes: {len(rows)}  (expect 100~200)")
    print("\n--- first recipe ---")
    pprint.pprint(rows[0])
    edge_outliers = [
        (r["recipe_id"], p["name"], p["point_count"])
        for r in rows for p in r["parameters"] if p["point_count"] >= 40
    ]
    print(f"\npoint-count outliers (>=40): {len(edge_outliers)}")
    for o in edge_outliers[:5]:
        print(" ", o)
    classes = {}
    for r in rows:
        classes[r["recipe_class"]] = classes.get(r["recipe_class"], 0) + 1
    print(f"\nrecipe_class split: {classes}")
