"""한 lot 의 recipe 모집단, 주차별 변화, 그리고 네 버킷의 분류 규칙입니다.

왜 이 모듈이 따로 있는가
────────────────────────
``recipe_id`` 는 실물에서 **DB 를 가로지르는 조인 키**입니다 —
sknn-planstep-r3 의 recipe_id 가 cdsem_idp_ver 의 full_name 과 같은 값이고
(docs/datatables/hitachi/idp_ver.txt L55), ebeam_tas_lot_hist 의 recipe_id 도 "다른 DB 의
full_name 과 동일 체계"입니다 (ebeam_tas_lot_hist.txt L34). 우리가 가공 접미사를
덧붙이지 않습니다 — 단, 실물 recipe **이름 자체**는 "_S"/"SE"(Sample) 외에
"_WCDU"/"_FCDU"/"_FULL"(CDU·full-map job, user-confirmed 2026-08-04)로 끝날 수
있고, 이는 이름의 일부이므로 조인 키를 깨지 않습니다. 프론트엔드는 이 세 접미사의
recipe 를 판정 범위에서 뺍니다 (lotHealth.isJudgeExempt).

예전 mock 은 버킷마다, 그리고 주차마다 recipe 를 **따로** 만들고 id 에 버킷 이름을
박았습니다 (``RCP-R000-ALL-000`` / ``RCP-R000-MOT-000``). 그래서

* recipe-statistics 와 recipe-params 를 recipe_id 로 조인할 수 없었고(교집합 0건),
* 버킷이 한 모집단의 부분집합이 아니라 서로 무관한 네 덩어리였으며,
* ``bucket[:3]`` 이 only_normal 과 only_sample 을 똑같이 ``ONL`` 로 잘라 두 버킷의
  id 가 충돌했고,
* **주차마다 recipe 가 새로 태어나** 트렌드가 추세 없는 잡음이었습니다.

실물에서 버킷은 **한 모집단 위의 겹치는 필터**입니다 — 한 스텝이 여러 버킷에 동시에
들어갑니다 (office_example.py ``_bucket_members``).

주차별 변화 모델 (docs/datatables/hitachi/device_statistics_weekly_trend.txt)
────────────────────────────────────────────────────────────────────
그 문서가 말하는 트렌드 화면의 질문은 하나입니다 — "이 device 의 **파라미터 규모가
주 단위로 어떻게 변해 왔는가**". 원천(sknn-planstep-r3)은 현재 계획만 있는 index 라
주차별 스냅샷을 쌓아 읽습니다. 즉 주차별로 보이는 것은 **같은 계획이 자라거나 줄어든
모습**이지, 매주 새로 뽑은 표본이 아닙니다.

그래서 이 모듈은 lot 마다

1. 창 전체에서 쓸 **정체성 풀**을 lot_cd 만으로 만들고(주차와 무관 → recipe_id 가
   주차를 가로질러 안정적입니다),
2. lot 마다 하나씩 **궤적**(성장/감소/안정/도약)을 배정해 주차별 recipe 수와 파라미터
   규모를 그 궤적대로 움직입니다.

덕분에 트렌드 차트가 실제로 방향을 갖고, 3주 전에 있던 recipe 가 이번 주에도 같은
recipe_id 로 남아 있습니다.

분류 규칙 (user-confirmed 2026-08-04, docs/datatables/hitachi/planstep_r3.txt)
─────────────────────────────────────────────────────────────────────
  all            모든 Step
  only_normal    skip 되지 않은(skip_yn != "Y") Step 중 스텝명 끝이 **순수한 CD**
                 ("CD(E)", "CD(F)" 는 제외)
  mother_normal  only_normal 과 **같은 스텝 필터** + mother 파라미터를 1개 이상
                 가진 recipe 만. para_* 집계도 **mother 파라만** 셉니다.
  only_sample    **recipe 이름**이 "_S" 또는 "SE" 로 끝나는 Step

only_normal 과 mother_normal 이 같은 스텝 필터를 공유하는 것이 핵심입니다 —
mother_normal 은 스텝을 더 좁히는 것이 아니라 **한 단계 아래(파라미터)로**
들어갑니다. CONTEXT.md 의 "mother_normal = Main(Mother 파라 view)" 가 그 뜻입니다.

정정 이력 (2026-08-04): 이전에는 only_normal 이 이름 **어디든** CD 토큰이 있으면
통과시켜 "CD(E)"/"CD(F)" 인 추가계측까지 Main 으로 셌고, mother_normal 은
파라미터를 전혀 보지 않고 스텝만 갈랐습니다. 둘 다 틀렸습니다. 그때 쓰던
``is_normal_step``(CD 토큰 아무 위치)은 소비처가 사라져 삭제했습니다 — 안 쓰는
판정 함수를 남기는 것이 두 정의가 다시 갈라지는 경로이기 때문입니다.

아래 판정 함수는 office_example.py 의 동명 함수와 같은 규칙입니다. 두 벌이
갈라지면 집에서 만든 화면이 사무실에서 다르게 나오므로, tests 가 같은 예시 표로
양쪽을 함께 검증합니다.

mother 파라미터 (docs/datatables/hitachi/recipe_idp.txt L182, office 확인 2026-07-28)
─────────────────────────────────────────────────────────────────────────────
``Mother_Para`` 는 **파라미터 1개당 bool** 입니다 — True 면 그 파라미터가 mother
이고, son 들은 mother 와 같은 image 에서 자기 cd_value 를 얻습니다. 측정
시간(TAT)을 움직이는 것은 mother 수이므로 mother_normal 이 "TAT 최적화 대상" 을
보는 view 입니다.

이 mock 은 recipe 마다 mother 파라 개수를 :class:`RecipeIdentity` 에 실어 둡니다.
그 값이 **단일 진실 원천**인 것이 중요합니다 — 요약의 para_* 와 health 가 읽는
recipe_params 의 parameters 는 서로 다른 모듈이 각자 난수로 만들기 때문에, "이
recipe 에 mother 가 있는가" 를 두 곳에서 따로 정하면 *para 합계는 줄었는데
health 는 그대로*인, 오류 없이 조용히 어긋나는 화면이 됩니다.

사무실 출처는 ``cdsem_idp_ver`` 의 **``raw_data``** 입니다 — parameter 별 row 에
``Mother_Para`` 가 실려 있습니다 (office 확인 2026-08-10, docs/datatables/hitachi/
idp_ver.txt). 2026-08-04 까지 이 자리에는 "사무실 원천 미해결" 이라고 적혀
있었는데, ``parameters`` 만 열어 보고 판단한 오진이었습니다.

OFFICE-VERIFY: mother 발생률(여기서는 recipe 의 약 85%가 보유, 보유 시 각 bin 의
25~45%)은 실물에서 확인된 바 없습니다.

이 mock 이 실물보다 좁은 지점 둘 — 사무실 경로에서만 나는 사고를 집에서 재현하지
못하는 자리입니다.

  1. ``mother`` 를 처음부터 **bool** 로 만듭니다. index 쪽이 문자열("False")로
     적재되어 있으면 순진한 캐스팅이 모든 파라미터를 mother 로 만드는데
     (``bool("False")`` 는 True), 그 사고는 여기서 절대 재현되지 않습니다.
     office adapter 의 ``_flag`` 와 그 단위 테스트가 그 자리를 대신합니다.
  2. 파라미터를 **이미 측정 순서대로** 냅니다(WAFER -> LEVEL -> EDGE). 실물은
     ``parameters`` dict 의 key 순서가 측정 순서가 아니고 ``parameters_list``
     가 따로 순서를 싣습니다 — 그래서 "재배열" 이라는 단계 자체가 집에는
     없습니다 (idp_ver.txt "순서는 parameters_list 가 정합니다").

Internal module: 이 feature 밖에서는 device_statistics.data 를 통해 쓰십시오.
"""

import hashlib
import random
import re
from typing import TypedDict

from back_dev_home.ebeam.device_statistics.oper_order import OPER_PREFIX_ORDER
from back_dev_home.ebeam.device_statistics.para_buckets import (
    OVERFLOW_BUCKET,
    PARA_BUCKETS,
)


# ── 분류 규칙 (office_example.py 와 동일) ──────────────────────────────────
# recipe 이름이 "_S"/"SE" 로 끝나면 Sample. 축이 스텝명이 아니라 **recipe 이름**
# 인 것이 핵심입니다.
_SAMPLE_SUFFIX = re.compile(r"(_S|SE)$", re.IGNORECASE)

# 특수 측정 job 토큰. CDU 는 **목록이 아니라 패턴**입니다 — 앞 글자는 어떤
# map 을 재는지를 뜻할 뿐이라(W=wafer, F=field, B=…) 종류가 늘 수 있고, 실제로
# _WCDU/_FCDU 만 적어 두었더니 _BCDU 가 새어 나왔습니다 (user-confirmed
# 2026-08-05). _FULL/_HALF/_MTX 는 CDU 가 아닌 별개 job 이라 이름으로 답니다.
#
# 끝에 고정하지 **않습니다** — 실물에 "_BCDU_NEW" 처럼 토큰 뒤에 꼬리가 더 붙는
# 이름이 있습니다 (user-confirmed 2026-08-11). 이 job 을 가리키는 것은 이름의
# 위치가 아니라 토큰 자체입니다. 앞의 밑줄만은 남깁니다 — 그 경계까지 놓으면
# 이름 안에서 우연히 만들어진 글자 조합에 정상 recipe 가 조용히 빠집니다.
#
# 프론트엔드 lotHealth.EXEMPT_JOB_TOKEN 과 같은 식이어야 합니다.
_EXEMPT_JOB_TOKEN = re.compile(r"(_[A-Z]*CDU|_FULL|_HALF|_MTX)", re.IGNORECASE)


def is_sample_recipe(recipe_id: str) -> bool:
    """recipe 이름이 "_S"/"SE" 로 끝나는가."""
    return bool(_SAMPLE_SUFFIX.search((recipe_id or "").strip()))


def is_exempt_job(recipe_id: str) -> bool:
    """recipe 이름에 특수 측정 job 토큰이 들어 있는가.

    프론트엔드 ``lotHealth.isExemptJob`` 과 **같은 정규식**입니다. 이 표면에서도
    공개 함수인 이유는 소비처가 둘이기 때문입니다 — 이름을 만드는
    :func:`_recipe_name` 과, 그 job 의 측정 규모를 정하는 ``recipe_params``.

    :data:`_JUDGE_EXEMPT_SUFFIXES` 로 판정하지 **않는** 것이 중요합니다. 그
    튜플은 mock 이 만들어 볼 표본일 뿐이고, 판정 기준은 패턴입니다 — 표본에
    없는 "_BCDU" 도 걸러야 하기 때문입니다.
    """
    return bool(_EXEMPT_JOB_TOKEN.search((recipe_id or "").strip()))


def ends_with_pure_cd(oper_desc: str) -> bool:
    """스텝명 끝이 **순수한 CD** 인가 — "CD(E)"/"CD(F)"/"CD(BENDING)" 은 제외.

    실제 스텝명은 "CBL ETCH CD" 처럼 공정 접두사로 시작해 띄어쓰기로 이어지는
    문자열이고, 추가계측은 "ISO PTN CD(E)" 처럼 꼬리가 괄호로 닫힙니다
    (user-confirmed 2026-08-09). 그래서 닫는 괄호를 벗긴 뒤 마지막 토큰이 정확히
    "CD" 인지 봅니다 — "ISO PTN CD(E)" 는 벗겨도 마지막 토큰이 "CD(E" 라
    걸러지고, 꼬리가 단어인 "ISO PTN CD(BENDING)" 도 "CD(BENDING" 이 되어
    같은 이유로 걸러집니다. 규칙이 꼬리의 길이를 가정하지 않는 것이 핵심입니다.
    """
    stripped = (oper_desc or "").strip().rstrip(")]} \t")
    if not stripped:
        return False
    return stripped.split()[-1].upper() == "CD"


def is_measuring(skip_yn: str) -> bool:
    """이 스텝이 skip 되지 않았는가 — ``skip_yn != "Y"``.

    실물 값 도메인은 "Y"/"N"/빈 값 세 가지라 판정은 ``!= "Y"`` 하나뿐입니다.
    """
    return (skip_yn or "").strip().upper() != "Y"


def is_normal_bucket_step(oper_desc: str, skip_yn: str) -> bool:
    """only_normal / mother_normal 이 **공유**하는 스텝 필터.

    두 버킷이 같은 스텝 집합을 쓴다는 사실은 도메인 규칙이지 우연이 아니므로
    (mother_normal 은 스텝이 아니라 파라미터를 좁힙니다), 조건을 두 군데에
    복사하지 않고 이 한 함수를 양쪽이 부릅니다.
    """
    return is_measuring(skip_yn) and ends_with_pure_cd(oper_desc)


class RecipeIdentity(TypedDict):
    """statistics 와 recipe_params 가 공유하는 recipe 한 건.

    ``mother_para_*`` 는 같은 bin 의 ``para_*`` 중 mother 인 개수이며 항상
    ``<= para_*`` 입니다. 넷이 모두 0 이면 이 recipe 에는 mother 가 없고,
    따라서 mother_normal 버킷에 들어가지 않습니다.
    """

    recipe_id: str
    oper_id: str
    oper_desc: str
    oper_seq: int
    samp_seq: int
    eqp_id: str
    skip_yn: str
    step_ctn_desc: str
    para_5: int
    para_9: int
    para_13: int
    para_16: int
    para_over_16: int
    mother_para_5: int
    mother_para_9: int
    mother_para_13: int
    mother_para_16: int
    mother_para_over_16: int


# ── 이름 어휘 ────────────────────────────────────────────────────────────
# 실제 스텝명은 "CBL ETCH CD" · "ISO PTN CD(E)" 처럼 **공정 접두사로 시작해
# 띄어쓰기로 이어지는** 문자열입니다 (user-confirmed 2026-08-09). "/" 는 쓰이지
# 않습니다 — 슬래시가 들어가는 것은 recipe_id 쪽(full_name)입니다.
#
# 접두사는 :data:`OPER_PREFIX_ORDER` 에서 골라 씁니다 — 그 tuple 이 실물 접두사의
# 단일 원천(user-confirmed 2026-07-30)이므로 여기서 목록을 다시 적으면 두 벌이
# 갈라질 뿐입니다. 예전 mock 의 코드(SNB1·PLD3·MTC1…)는 지어낸 값이라 그 목록에
# 없었고, 그래서 M 계열 정렬이 집에서 전부 UNKNOWN_RANK 로 떨어져 접두사 rank
# 경로가 사실상 검증되지 않았습니다.
#
# **개수가 8 인 것이 load-bearing 입니다.** ``random.choice`` 는 시퀀스 길이만큼의
# 난수 비트를 소비하므로(``_randbelow`` 의 bit_length + 거절 재시도), 길이를 바꾸면
# 그 뒤의 모든 값이 다시 태어납니다 — 실제로 20개로 늘렸더니 exempt job 접미사
# 하나(_WCDU)가 풀에서 사라져 그 판정 경로의 집 커버리지가 조용히 없어졌습니다.
# 어휘를 늘리고 싶다면 값 변화가 의도된 변경일 때 하고, 그때 픽스처·비율 테스트를
# 함께 확인하십시오.
#
# 공정 순서의 앞·중간·뒤에서 고르게 뽑았습니다(ISO 가 가장 앞, RDL 이 가장 뒤).
# SNC2 를 넣은 것은 longest-prefix 함정(SNC2 가 SNC·SN 으로 잡히면 안 됨)이 집에서
# 실제 데이터로 지나가게 하려는 것입니다.
_STEP_PREFIXES = ("ISO", "BLC", "GT", "CBL", "SNC2", "ILD", "M2", "RDL")
assert set(_STEP_PREFIXES) <= set(OPER_PREFIX_ORDER)

# 접두사와 "CD" 사이의 설명 토큰. 실물 예시("CBL ETCH CD", "ISO PTN CD(E)")처럼
# 한 단어짜리와 여러 단어짜리가 섞입니다 — 길이를 하나로 고정하면 스텝명을 공백으로
# 자르는 코드가 집에서 한 가지 형태로만 검증됩니다. 개수 9 는 위와 같은 이유로
# 바꾸지 마십시오.
_STEP_WORDS = (
    "ETCH", "PTN", "CLN", "CMP",
    "CELL OPEN ETCH CLN", "GATE POLY ETCH", "ACTIVE TRENCH CLN",
    "METAL1 CMP", "VIA ETCH CLN",
)

# 스텝명 접미 비율이 곧 버킷 크기입니다. only_normal 은 "순수한 CD" 이면서 측정
# 중인 것(0.45 × 0.85 ≈ 38%), mother_normal 은 그중 mother 를 가진 것
# (38% × 85% ≈ 32%)입니다. 비교 페이지의 막대 서열
# (all > only_normal > mother_normal > only_sample)이 이 비율에서 나오므로,
# only_sample(25%)보다 mother_normal 이 커야 서열이 유지됩니다.
_PURE_CD_RATIO = 0.45      # "… CLN CD)"     -> only_normal 후보
_PAREN_CD_RATIO = 0.22     # "… CLN CD(E))"  -> 추가계측, 이제 어느 CD 버킷에도 없음
# 나머지 33% 는 CD 없는 스텝 -> 어느 CD 버킷에도 안 들어갑니다.

# 추가계측 스텝명의 괄호 꼬리. "CD(BENDING)" 은 user-confirmed 2026-08-05 —
# 실물의 꼬리는 한 글자(E/F)만이 아니라 단어일 수 있습니다. 여기에 단어형이
# 하나도 없으면 `ends_with_pure_cd` 의 "닫는 괄호를 벗긴 뒤 마지막 토큰" 규칙이
# 한 글자 꼬리에서만 검증되어, only_normal 버킷이 집에서 좁게 확인됩니다.
_CD_VARIANTS = ("CD(E)", "CD(F)", "CD(BENDING)")

# recipe 이름의 두 조각. 실물 full_name 이 "class_name/recipe_name" 이고 "/" 앞이
# class_name 입니다 (docs/datatables/hitachi/recipe_name_list.txt L56, user-confirmed
# 2026-07-29). 어휘 자체는 지어낸 것이며 사무실의 실제 class 목록이 아닙니다
# (OFFICE-VERIFY) — 형태만 실물을 따릅니다.
#
# 개수가 서로 소여야(8 과 9) digest 의 두 자리가 독립적으로 퍼집니다. 같은 수면
# class 와 base 가 함께 움직여 이름의 다양성이 8분의 1로 접힙니다.
_RECIPE_CLASSES = ("ADI", "AEI", "ACI", "CNT", "GATE", "EDGE", "VIA", "QC")
_RECIPE_BASES = (
    "CD_BIAS", "OVERLAY", "PITCH_MON", "PROFILE_SCAN", "CONTACT_CHECK",
    "DAILY_MATCH", "SPACE_CD", "LINE_CD", "HOLE_CD",
)

# recipe 이름이 "_S"/"SE" 로 끝나는 비율 = only_sample 버킷 크기.
_SAMPLE_RATIO = 0.25

# 만들어 볼 특수 측정 job 접미사 **표본**입니다 — 판정 기준이 아닙니다.
# 기준은 :data:`_EXEMPT_JOB_TOKEN` 패턴이고, 여기 있는 것은 그 패턴이 집에서
# 실제로 지나가도록 이름을 찍어 내기 위한 목록입니다.
#
# _BCDU 가 들어 있는 이유가 그 구분을 말해 줍니다. 이 이름은 어느 열거 목록에도
# 없었고 그래서 조용히 새어 나갔습니다 (user-confirmed 2026-08-05) — 표본에
# 넣어 두면 "_*CDU 라면 무엇이든" 이라는 규칙이 회귀로 고정됩니다. 표본을 늘려도
# 판정은 바뀌지 않는다는 점이 핵심입니다.
#
# 프론트엔드 lotHealth.isExemptJob 이 이 job 을 판정 범위(분자·분모 모두)에서,
# outlierDetect 가 중앙값 기준선과 초과 목록에서 뺍니다 — mock 이 이 이름을
# 만들지 않으면 그 두 경로가 집에서 한 번도 실행되지 않습니다.
#
# "_BCDU_NEW" 는 토큰 **뒤에 꼬리가 붙는** 실물 이름입니다 (user-confirmed
# 2026-08-11). 표본에 넣어 두는 이유는 앞의 여섯과 다릅니다 — 다른 이름들은
# 토큰으로 끝나므로 끝에 고정한 옛 규칙으로도 잡혔고, 그래서 집에서는
# :data:`_EXEMPT_JOB_TOKEN` 이 "끝" 이 아니라 "어디든" 을 본다는 사실이 한 번도
# 관찰되지 않았습니다. 이 이름 하나가 그 경로를 매 lot 에서 실행시킵니다.
#
# _WCDU/_FCDU/_FULL user-confirmed 2026-08-04,
# _HALF/_BCDU/_MTX user-confirmed 2026-08-05,
# _BCDU_NEW user-confirmed 2026-08-11.
_JUDGE_EXEMPT_SUFFIXES = (
    "_WCDU", "_FCDU", "_BCDU", "_FULL", "_HALF", "_MTX", "_BCDU_NEW",
)

# 특수 측정 job 의 비율. 0.10 이었다가 **0.03** 으로 내렸습니다 — "16 point 를
# 넘는 파라미터는 전체 파라미터의 2~5% 이고, 그것이 recipe 의 3% 에 몰려 있다"
# (user-confirmed 2026-08-10). 그 3% 가 곧 이 job 들입니다: 웨이퍼 전면을 훑으므로
# 파라미터당 point 수가 정상 recipe 와 자릿수부터 다릅니다.
#
# 이 비율이 곧 para_over_16 이 채워지는 recipe 의 비율입니다(_apply_sweep_jobs).
# 예전에는 0.10 에 더해 PARA_RANGES 가 recipe 마다 0~3 을 따로 뿌려서, 집에서는
# recipe 의 약 75% 가 16 초과 파라미터를 갖고 있었습니다 — 실물의 25배입니다.
_JUDGE_EXEMPT_RATIO = 0.03

_OPER_PREFIXES = (
    "ETCH", "DEPO", "LITH", "IMPL", "CLEAN", "ANNL", "INSP", "MEAS",
    "CMP", "STRIP", "OXID", "DIFF",
)
_EQP_FAMILIES = ("CDSEM", "CDS2", "MET", "VS", "INSP")

# 창 전체에서 쓸 정체성 풀의 크기. 주차별 recipe 수는 이 풀에서 궤적만큼 잘라
# 씁니다 — 풀 자체는 주차와 무관하게 lot_cd 로만 정해집니다.
#
# 하한 175 는 궤적의 최저 배율(0.58)을 곱해도 recipe 수가 **100 아래로 내려가지
# 않도록** 잡은 값이고, 상한 200 은 배율 1.0 일 때 200 을 넘지 않도록 한 값입니다.
# device 당 recipe 100~200 이 확인된 도메인이기 때문입니다 (D22).
#
# 실물과 좁은 지점 — 이 풀의 크기는 **스텝 수**이고, 그중 몇 건은
# :func:`_apply_shared_recipes` 가 같은 recipe 로 묶어 recipe 수를 스텝 수보다
# 작게 만듭니다. office 의 sknn-planstep-r3 은 문서 1건이 recipe 가 아니라 plan
# step 이고, 한 device 가 2000건을 넘습니다 (office 확인 2026-08-10 — RJ1B 가
# 어댑터 상한을 쳤습니다; docs/datatables/hitachi/planstep_r3.txt). 차이는 skip 되는 스텝과
# 같은 recipe 를 여러 스텝에서 재사용하는 몫입니다. 재사용은 이제 재현하지만 **스텝
# 수는 여전히 실물의 1/10** 이므로, 스텝 규모에 좌우되는 것(어댑터의 조회 상한,
# payload 크기)은 집에서 관찰되지 않습니다.
POOL_RANGE = (175, 200)

# 같은 recipe 를 다른 스텝에서 다시 쓰는 비율.
#
# 실물에서 한 device 의 plan step 은 recipe 보다 많습니다 — 위 주석의 "재사용하는
# 몫" 이 이것입니다. 비율 자체는 확인되지 않았고(OFFICE-VERIFY), 0.04 는 lot 당
# 175~200 스텝에서 7~8 쌍이 나와 **모든 lot 에서 공유 경로가 반드시 한 번은
# 그려지도록** 고른 값입니다.
#
# 이 재사용이 없던 동안 mock 은 "recipe_id 가 lot 안에서 유일하다" 는 실물에 없는
# 불변식을 가르쳤고, 프론트엔드가 그 위에 올라섰습니다 — lot 상세 팝업이
# recipe_id 를 ``v-for`` 의 :key 로 써서, 사무실 데이터에서 카드가 조용히 한 장씩
# 사라졌습니다 (Vue "Duplicate keys found during update").
SHARED_RECIPE_RATIO = 0.04

# 버킷별 파라미터 개수. 키는 point 수 **구간**이고 경계는 para_buckets.py 가
# 정합니다 — 2026-08-10 에 "정확히 16/13/9/5" 에서 구간으로 바뀌었습니다.
#
# 분포는 recipe_params.py 의 TYPICAL_POINTS(WAFER 9~13, LEVEL 1~4, EDGE 6~14,
# OTHER 1~8)가 실제로 만들어 내는 모양을 따릅니다. 두 표면이 각자 난수를 굴리므로
# 값까지 같아질 수는 없지만, **모양이 반대이면** 요약과 상세가 서로 다른 이야기를
# 하는 화면이 됩니다 — 예전 값(para_16 이 가장 큼)은 구간 해석에서 "대부분의
# 파라미터가 14~16 point" 라는 뜻이 되어 상세 화면과 정면으로 어긋났습니다.
#
# para_over_16 의 하한이 0 인 것은 의도입니다. 이 버킷이 비는 recipe 가 있어야
# 화면의 "구간 하나가 0" 경로가 집에서 실행됩니다.
PARA_RANGES = {
    "para_5": (4, 20),
    "para_9": (6, 28),
    "para_13": (8, 34),
    "para_16": (1, 10),
    # 보통 recipe 에는 16 point 를 넘는 파라미터가 **없습니다.** 이 구간을 채우는
    # 것은 특수 측정 job 뿐이고, 그것은 :func:`_apply_sweep_jobs` 가 이름을 보고
    # 나중에 넣습니다 (user-confirmed 2026-08-10 — 전체 파라미터의 2~5%,
    # recipe 의 3%).
    #
    # (0, 0) 이 낭비처럼 보이지만 **난수 호출 한 번을 유지**합니다. 여기서 호출을
    # 빼면 풀 뒷부분 recipe 가 전부 다른 값으로 다시 태어납니다(_recipe_name 주석).
    "para_over_16": (0, 0),
}

SKIPPED_RATIO = 0.15
BLANK_SKIP_YN_RATIO = 0.15

# 정체성 풀 seed 를 주차 seed 와 갈라놓는 salt. 주차별 rng 와 섞이면 풀이 주차마다
# 달라져 recipe_id 안정성이 깨집니다.
_IDENTITY_SALT = 90001

# recipe 재사용 쌍을 고르는 rng 를 정체성 rng 와 갈라놓는 salt. _MOTHER_SALT 와
# 같은 이유입니다 — 공유 쌍을 정체성 루프 안에서 굴리면 풀 전체가 다시 태어납니다.
_SHARED_SALT = 5150

# mother 파라 개수를 만드는 rng 를 정체성 rng 와 갈라놓는 salt.
#
# 이 분리는 편의가 아니라 **필수**입니다. mother 값을 `_identity_pool` 루프 안에서
# 굴리면 난수 호출 수가 recipe 당 늘어나 풀 뒷부분 recipe 가 전부 다른 값으로 다시
# 태어나고, recipe_id 와 oper_desc 까지 바뀝니다 — 결정론에 기대는 화면·테스트가
# 통째로 흔들립니다(`_recipe_name` 의 같은 주의 참고). 완성된 풀을 별도 rng 로 한 번
# 더 훑으면 기존 값은 한 바이트도 움직이지 않습니다.
_MOTHER_SALT = 70003

# mother 파라를 1개 이상 가진 recipe 비율. 100% 로 두면 mother_normal 의 recipe
# 집합이 only_normal 과 항상 같아져, "mother 없는 recipe 는 빠진다" 는 경로가
# 집에서 한 번도 실행되지 않습니다 (OFFICE-VERIFY — 실물 비율 미확인).
_MOTHER_RECIPE_RATIO = 0.85

# mother 를 가진 recipe 에서 각 bin 의 mother 비중. son 이 mother 의 image 를
# 함께 쓰므로 mother 는 소수입니다 (OFFICE-VERIFY — 실물 비중 미확인).
MOTHER_SHARE = (0.25, 0.45)

# 계약·office 어댑터와 같은 목록을 씁니다. 여기서 따로 적어 두면 버킷이
# 늘 때 한쪽만 늘어납니다.
_PARA_KEYS = PARA_BUCKETS

# 같은 recipe 를 쓰는 두 스텝이 **함께 갖는** field — recipe 에서 유래한 것뿐입니다.
# :func:`_apply_shared_recipes` 가 복사하는 목록이고, 테스트가 같은 이름을 읽어
# "코드가 복사하는 것" 과 "테스트가 검사하는 것" 이 갈라지지 않게 합니다.
SHARED_RECIPE_FIELDS = (
    "recipe_id",
    *_PARA_KEYS,
    *(f"mother_{key}" for key in _PARA_KEYS),
)


# ── 주차별 궤적 ──────────────────────────────────────────────────────────
# lot 마다 하나씩 배정되는 성장 곡선. 트렌드 화면이 답하는 질문이 "파라미터 규모가
# 주 단위로 어떻게 변해 왔는가" 이므로, 방향이 있어야 화면이 의미를 갖습니다.
TRAJECTORIES = ("growing", "shrinking", "stable", "ramp")


def lot_trajectory(lot_cd: str) -> str:
    """lot 하나의 궤적. lot_cd 만으로 정해지므로 주차가 바뀌어도 같습니다."""
    digest = 0
    for ch in lot_cd:
        digest = (digest * 131 + ord(ch)) & 0xFFFFFFFF
    return TRAJECTORIES[digest % len(TRAJECTORIES)]


def week_scale(trajectory: str, point_index: int, points: int) -> float:
    """0 번째(가장 오래된) ~ 마지막 주차에서의 규모 배율.

    창 밖으로 나가지 않도록 0.55~1.0 안에서만 움직입니다. 마지막 주차가 항상
    1.0 은 아닙니다 — shrinking lot 은 최근이 더 작아야 감소로 읽힙니다.
    """
    if points <= 1:
        return 1.0
    t = point_index / (points - 1)  # 0.0 (가장 오래) → 1.0 (최신)

    if trajectory == "growing":
        return 0.58 + 0.42 * t
    if trajectory == "shrinking":
        return 1.0 - 0.38 * t
    if trajectory == "ramp":
        # 중반에 계단 하나 — 신규 tech node 가 붙는 모습.
        return 0.60 if t < 0.5 else 0.98
    return 0.90 + 0.10 * t  # stable — 거의 평평하지만 죽어 있지는 않게


def _skip_yn(rng: random.Random) -> str:
    """실물의 세 값("Y" / "N" / 빈 값)을 그 비율대로 만듭니다."""
    roll = rng.random()
    if roll < SKIPPED_RATIO:
        return "Y"
    if roll < SKIPPED_RATIO + BLANK_SKIP_YN_RATIO:
        return ""
    return "N"


def _step_name(rng: random.Random) -> str:
    """"CBL ETCH CD" · "ISO PTN CD(E)" — 접두사 + 설명 토큰 + CD 꼬리.

    이름 전체를 괄호로 감싸지 않습니다. 예전 mock 의 "SNC2(CELL OPEN ETCH CLN CD)"
    형태는 실물이 아니었고(user-confirmed 2026-08-09), 괄호가 늘 이름 끝에 있다는
    잘못된 인상을 줬습니다 — 실물에서 닫는 괄호는 추가계측 꼬리 "CD(E)" 에만
    붙습니다.

    rng 호출 순서(choice → choice → random → 조건부 choice)는 그대로입니다.
    """
    prefix = rng.choice(_STEP_PREFIXES)
    words = rng.choice(_STEP_WORDS)
    roll = rng.random()
    if roll < _PURE_CD_RATIO:
        return f"{prefix} {words} CD"
    if roll < _PURE_CD_RATIO + _PAREN_CD_RATIO:
        return f"{prefix} {words} {rng.choice(_CD_VARIANTS)}"
    return f"{prefix} {words}"


def _name_digest(lot_cd: str, idx: int) -> int:
    """이름 조각을 고르는 안정 digest. ``rng`` 를 쓰지 않는 것이 핵심입니다.

    :func:`_recipe_name` 의 rng 호출 수를 한 번도 바꾸지 않으므로, 이름을 바꿔도
    풀의 나머지 값(oper_id·samp_seq·para 개수…)은 한 바이트도 움직이지 않습니다.
    파이썬 ``hash()`` 는 PYTHONHASHSEED 로 실행마다 달라져 쓸 수 없습니다.
    """
    digest = hashlib.sha256(f"{lot_cd}:{idx}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _recipe_name(rng: random.Random, lot_cd: str, idx: int) -> str:
    """실물 형태의 recipe_id — ``class_name/recipe_name`` + 이름의 일부인 접미사.

    실물 recipe_id 는 idp registry 의 ``full_name`` 이고 "/" 앞이 class_name 인
    슬래시 형태입니다 (docs/datatables/hitachi/recipe_name_list.txt L56, user-confirmed
    2026-07-29). recipe_search mock 도 같은 shape 를 씁니다.

    **class 를 idx 가 아니라 digest 로 고르는 것이 이 함수의 요점**입니다.
    사무실에서 recipe 이름은 MMDM 이 부여한 것이라 공정 순서와 아무 관계가
    없는데, 예전 ``RCP-{lot}-{idx:03d}`` 는 이름의 사전순이 곧 ``oper_seq``
    순이었습니다. 두 축이 완전상관이면 lot 상세의 정렬 토글("공정순" /
    "recipe 이름")이 집에서 **같은 표를 두 번** 보여 주고, 두 축을 가르는 코드
    경로가 한 번도 관찰되지 않습니다. 실물에서 독립인 축은 mock 에서도 독립이어야
    합니다.

    비-Sample·비-exempt id 는 숫자로 끝나므로 ``(_S|SE)$`` 에 우연히 걸리지
    않습니다. exempt 분기는 **같은 roll 을 나눠 쓰고** 접미사를 idx 로 골라
    rng 호출 수를 바꾸지 않습니다 — 호출 수가 달라지면 풀의 뒤쪽 recipe 전부가
    다른 값으로 다시 태어나, 결정론에 기대는 화면·테스트가 통째로 흔들립니다.

    lot_cd 를 이름에 남겨 **여기서 찍히는** 이름이 lot 안에서 유일하도록 둡니다.
    다만 그것이 곧 "lot 안에서 recipe_id 가 유일하다" 는 뜻은 아닙니다 —
    :func:`_apply_shared_recipes` 가 뒤에서 일부 스텝의 이름을 앞 스텝의 것으로
    덮어써, 한 recipe 가 여러 스텝에 걸리는 실물 모습을 만듭니다. lot 을 가로지르는
    공유(한 recipe 가 여러 device 에 걸리는 것)는 아직 재현하지 않습니다
    (OFFICE-VERIFY — 비율 미확인).
    """
    digest = _name_digest(lot_cd, idx)
    class_name = _RECIPE_CLASSES[digest % len(_RECIPE_CLASSES)]
    base_name = _RECIPE_BASES[(digest // len(_RECIPE_CLASSES)) % len(_RECIPE_BASES)]

    base = f"{class_name}/{base_name}_{lot_cd}_{idx:03d}"
    roll = rng.random()
    if roll < _SAMPLE_RATIO:
        return base + rng.choice(("_S", "SE"))
    if roll < _SAMPLE_RATIO + _JUDGE_EXEMPT_RATIO:
        return base + _JUDGE_EXEMPT_SUFFIXES[idx % len(_JUDGE_EXEMPT_SUFFIXES)]
    return base


def _identity_seed(lot_cd: str) -> int:
    digest = 0
    for ch in lot_cd:
        digest = (digest * 131 + ord(ch)) & 0xFFFFFFFF
    return (digest * 1009 + _IDENTITY_SALT * 7919) & 0xFFFFFFFF


def _identity_pool(lot_cd: str) -> list[RecipeIdentity]:
    """이 lot 이 창 전체에서 쓸 recipe 정체성. **주차와 무관**합니다.

    주차별 모집단은 이 풀의 앞에서부터 잘라 씁니다. 그래서 3주 전에 있던 recipe 가
    이번 주에도 같은 recipe_id 로 남고, 자라는 lot 은 뒤쪽 recipe 가 새로 등장하는
    모습이 됩니다 — 실물에서 스텝이 계획에 추가되는 것과 같은 방향입니다.
    """
    rng = random.Random(_identity_seed(lot_cd))
    pool: list[RecipeIdentity] = []

    for idx in range(rng.randint(*POOL_RANGE)):
        oper_prefix = rng.choice(_OPER_PREFIXES)
        pool.append({
            "recipe_id": _recipe_name(rng, lot_cd, idx),
            "oper_id": f"{oper_prefix}-{rng.randint(100, 999)}",
            "oper_desc": _step_name(rng),
            "oper_seq": idx + 1,
            "samp_seq": rng.randint(1, 5),
            "eqp_id": f"{rng.choice(_EQP_FAMILIES)}-{rng.randint(1, 24):02d}",
            "skip_yn": _skip_yn(rng),
            "step_ctn_desc": f"{oper_prefix} step",
            # 버킷 목록을 손으로 적지 않고 돌립니다 — 버킷이 늘 때 여기와
            # 아래 mother 초기화가 따로 놀 수 없게 하기 위해서입니다.
            **{key: rng.randint(*PARA_RANGES[key]) for key in _PARA_KEYS},
            # mother 는 바로 아래 별도 rng 가 채웁니다. 여기서 굴리면 위 난수
            # 순서가 밀려 풀 전체가 다른 값으로 다시 태어납니다
            # (_MOTHER_SALT 주석 참고).
            **{f"mother_{key}": 0 for key in _PARA_KEYS},
        })  # type: ignore[typeddict-item]

    _apply_sweep_jobs(pool)
    _assign_mother_counts(pool, lot_cd)
    return pool


# 특수 측정 job 에서도 16 point **이하**로 남는 파라미터의 비중. 배율이 8배라도
# point 가 1~2 인 LEVEL 계열은 8~16 에 머물기 때문에 전부가 넘지는 않습니다
# (recipe_params 의 EXEMPT_JOB_POINT_SCALE × TYPICAL_POINTS 를 계산해 보면
# 그렇습니다). 그 몫을 가장 낮은 구간에 남깁니다 — 0 으로 만들면 "이 job 은
# 파라미터가 전부 16 을 넘는다" 는, 확인되지 않은 더 강한 주장이 됩니다.
_SWEEP_JOB_RESIDUAL = 0.15


def _apply_sweep_jobs(pool: list[RecipeIdentity]) -> None:
    """특수 측정 job 의 파라미터를 ``para_over_16`` 으로 옮깁니다 (제자리 수정).

    **난수를 쓰지 않습니다.** 이미 만들어진 개수를 옮기기만 하므로 풀의 다른 값은
    한 바이트도 움직이지 않습니다 (:func:`_assign_mother_counts` 와 같은 이유).

    대상을 :func:`is_exempt_job` 으로 고르는 것이 요점입니다 — 같은 판정을
    ``recipe_params`` 가 point 수에 배율을 걸 때, 프론트엔드가 판정 범위에서 뺄 때
    씁니다. 세 표면이 같은 recipe 를 가리켜야 "요약은 16 초과가 많다는데 상세에는
    그런 파라미터가 없는" 화면이 생기지 않습니다.
    """
    for identity in pool:
        if not is_exempt_job(identity["recipe_id"]):
            continue
        total = sum(identity[key] for key in _PARA_KEYS)  # type: ignore[literal-required]
        if total <= 0:
            continue
        residual = max(1, round(total * _SWEEP_JOB_RESIDUAL))
        for key in _PARA_KEYS:
            identity[key] = 0  # type: ignore[literal-required]
        identity["para_5"] = residual
        identity[OVERFLOW_BUCKET] = total - residual  # type: ignore[literal-required]


def _assign_mother_counts(pool: list[RecipeIdentity], lot_cd: str) -> None:
    """완성된 풀에 mother 파라 개수를 채웁니다 (제자리 수정).

    별도 rng 를 쓰는 이유는 :data:`_MOTHER_SALT` 의 주석에 있습니다.
    """
    mother_rng = random.Random(_identity_seed(lot_cd) ^ _MOTHER_SALT)

    for identity in pool:
        has_mother = mother_rng.random() < _MOTHER_RECIPE_RATIO
        for key in _PARA_KEYS:
            total = identity[key]  # type: ignore[literal-required]
            share = mother_rng.uniform(*MOTHER_SHARE)
            # bin 이 비어 있으면 mother 도 0. 비어 있지 않은데 반올림이 0 이면
            # 1 로 올립니다 — share <= 0.45 라 total 을 넘을 수 없습니다.
            count = max(1, round(total * share)) if has_mother and total > 0 else 0
            identity[f"mother_{key}"] = count  # type: ignore[literal-required]


def _shared_recipe_pairs(lot_cd: str, pool_size: int) -> list[tuple[int, int]]:
    """``(원본 스텝, 같은 recipe 를 다시 쓰는 스텝)`` 인덱스 쌍.

    **풀 크기만으로 정해집니다 — 주차와 무관합니다.** 그래야 이번 주에 한 recipe 를
    공유하던 두 스텝이 다음 주에도 그대로 공유합니다. 주차는
    :func:`_apply_shared_recipes` 에서 "borrower 가 이번 주 계획에 들어왔는가" 로만
    걸립니다.

    donor 는 언제나 borrower **앞의** 스텝입니다. 실물에서 재사용은 "앞 공정에서
    쓰던 recipe 를 뒤 공정에서 또 쓴다" 이지 두 스텝이 동시에 태어나는 것이 아니고,
    그 방향이 "borrower 가 계획에 있으면 donor 도 있다" 를 공짜로 보장합니다.
    """
    if pool_size < 2:
        return []

    rng = random.Random(_identity_seed(lot_cd) ^ _SHARED_SALT)
    borrowers = sorted(
        rng.sample(range(1, pool_size), round(pool_size * SHARED_RECIPE_RATIO))
    )
    # donor 는 borrower 앞에서 고르고, 이미 borrower 인 스텝은 피합니다 — 빌린 이름을
    # 다시 빌려주면 세 스텝이 한 recipe 를 쓰게 되어 비율이 조용히 커집니다. 0 은
    # borrower 로 뽑히지 않으므로(sample 이 1 부터입니다) 후보는 늘 하나 이상입니다.
    #
    # 후보를 borrower 마다 다시 훑는 것은 O(k·n) 이지만 풀이 175~200 이라 lot 당
    # 17µs 입니다. POOL_RANGE 를 실물 규모(스텝 2000+)로 넓히는 날에는 donor 목록을
    # 누적해 가며 훑도록 바꾸십시오 — 그 크기에서는 49ms 가 됩니다.
    taken = set(borrowers)
    return [
        (rng.choice([i for i in range(borrower) if i not in taken]), borrower)
        for borrower in borrowers
    ]


def _apply_shared_recipes(rows: list[RecipeIdentity], pairs: list[tuple[int, int]]) -> None:
    """재사용 스텝에 원본의 **recipe 유래 field** 를 복사합니다 (제자리 수정).

    **난수를 쓰지 않습니다** (:func:`_apply_sweep_jobs` 와 같은 이유). 쌍은 이미
    :func:`_shared_recipe_pairs` 가 별도 rng 로 골라 두었습니다.

    복사 범위(:data:`SHARED_RECIPE_FIELDS`)가 이 함수의 요점입니다. 실물에서
    ``para_*`` 는 스텝의 성질이 아니라 **recipe 의 파라미터를 센 값**이므로
    (office_example ``_recipe_row`` 가 ``params_by_recipe[recipe_id]`` 를 셉니다),
    같은 recipe 를 쓰는 두 스텝은 para 블록이 완전히 같습니다. 반대로
    oper_*·eqp_id·skip_yn 은 스텝의 것이라 다릅니다.
    ``is_sample_recipe``·``is_exempt_job`` 은 recipe_id 만 보므로 복사와 함께
    자동으로 따라옵니다 — 두 스텝이 다른 버킷 규칙을 타는 모순이 생기지 않습니다.

    lot 요약의 ``para_all`` 은 그만큼 겹쳐 세어집니다. 실물이 그렇습니다 —
    office ``_summarize`` 도 스텝 행을 그대로 더합니다.
    """
    for donor, borrower in pairs:
        if borrower >= len(rows):
            continue  # 이번 주 계획 밖의 스텝. donor < borrower 라 donor 는 늘 안입니다.
        for key in SHARED_RECIPE_FIELDS:
            rows[borrower][key] = rows[donor][key]  # type: ignore[literal-required]


def _scaled(value: int, factor: float, jitter: float) -> int:
    """파라미터 개수에 주차 배율 + 약간의 흔들림.

    **0 은 0 으로 둡니다.** 비어 있는 버킷(보통 para_over_16)을 1 로 올리면
    "구간 하나가 0" 인 화면이 집에서 한 번도 나오지 않습니다. 0 이 아닌 값만
    최소 1 을 지킵니다 — 배율 때문에 있던 파라미터가 사라지면 안 됩니다.
    """
    if value <= 0:
        return 0
    return max(1, round(value * factor * jitter))


def build_population(
    lot_cd: str,
    point_index: int = 0,
    points: int = 1
) -> list[RecipeIdentity]:
    """이 (lot, 주차) 의 recipe 모집단. 버킷은 이 위의 필터입니다.

    ``points == 1`` 이면 궤적을 적용하지 않은 만기 모집단(=최신 주차)입니다 —
    recipe-params 처럼 주차 축이 없는 표면이 그렇게 부릅니다.
    """
    pool = _identity_pool(lot_cd)
    scale = week_scale(lot_trajectory(lot_cd), point_index, points)

    # 이번 주차에 계획에 들어 있는 recipe 수.
    count = max(12, round(len(pool) * scale))
    present = pool[:count]

    # 파라미터 규모도 같은 방향으로 움직입니다 — recipe 수만 움직이면 para_all 이
    # 계단처럼만 변해 "규모" 트렌드로 읽히지 않습니다.
    jitter_rng = random.Random(_identity_seed(lot_cd) ^ (point_index * 7919))

    # 주차 전체를 한 번에 흔드는 배율. recipe 별 jitter 만으로는 200 건이 평균으로
    # 상쇄돼 곡선이 자로 그은 듯 매끈해집니다 — 실물 주차 스냅샷은 그렇지 않으므로
    # lot·주차 단위의 흔들림을 따로 겁니다.
    week_wobble = jitter_rng.uniform(0.96, 1.04)
    para_scale = (0.82 + 0.18 * scale) * week_wobble

    scaled: list[RecipeIdentity] = []
    for identity in present:
        row = dict(identity)
        for key in _PARA_KEYS:
            # bin 하나당 jitter 를 **한 번만** 뽑아 total 과 mother 에 함께 씁니다.
            # 따로 뽑으면 recipe 당 난수 호출이 4 -> 8 로 늘어 기존 para_* 가 전부
            # 다른 값이 됩니다 (_MOTHER_SALT 주석의 같은 이유).
            jitter = jitter_rng.uniform(0.94, 1.06)
            total = _scaled(identity[key], para_scale, jitter)  # type: ignore[literal-required]
            mother = identity[f"mother_{key}"]  # type: ignore[literal-required]
            row[key] = total
            # 같은 배율을 걸어도 반올림 때문에 total 을 넘을 수 있으므로 잘라 둡니다 —
            # mother > total 은 계약 위반이고, 화면에서는 100% 넘는 막대가 됩니다.
            row[f"mother_{key}"] = min(total, _scaled(mother, para_scale, jitter)) if mother else 0
        scaled.append(row)  # type: ignore[arg-type]

    # 배율을 **먹인 뒤에** 공유를 적용합니다. 앞에서 하면 두 스텝이 서로 다른
    # jitter 를 맞아 같은 recipe 인데 para 블록이 갈라집니다 — 실물에서는 한 recipe
    # 의 파라미터를 두 번 센 값이라 반드시 같습니다.
    _apply_shared_recipes(scaled, _shared_recipe_pairs(lot_cd, len(pool)))

    return scaled


def mother_para_all(identity: RecipeIdentity) -> int:
    """이 recipe 의 mother 파라 총 개수. 0 이면 mother_normal 에서 빠집니다."""
    return sum(identity[f"mother_{key}"] for key in _PARA_KEYS)  # type: ignore[literal-required]


def bucket_members(
    population: list[RecipeIdentity]
) -> dict[str, list[RecipeIdentity]]:
    """네 버킷의 recipe 집합. 한 recipe 가 여러 버킷에 들어갈 수 있습니다.

    only_normal 과 mother_normal 은 **같은 스텝 필터**를 씁니다 — mother_normal
    은 거기서 mother 파라가 없는 recipe 만 더 떨어뜨립니다. para_* 를 mother
    기준으로 다시 세는 것은 statistics.py 의 몫입니다(여기서는 멤버십만 정합니다).
    """
    normal = [
        r for r in population
        if is_normal_bucket_step(r["oper_desc"], r["skip_yn"])
    ]
    return {
        "all": list(population),
        "only_normal": normal,
        "mother_normal": [r for r in normal if mother_para_all(r) > 0],
        "only_sample": [r for r in population if is_sample_recipe(r["recipe_id"])],
    }
