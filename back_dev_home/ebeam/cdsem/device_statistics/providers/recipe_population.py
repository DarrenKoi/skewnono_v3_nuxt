"""한 lot 의 recipe 모집단, 주차별 변화, 그리고 네 버킷의 분류 규칙입니다.

왜 이 모듈이 따로 있는가
────────────────────────
``recipe_id`` 는 실물에서 **DB 를 가로지르는 조인 키**입니다 —
sknn-planstep-r3 의 recipe_id 가 cdsem_idp_ver 의 full_name 과 같은 값이고
(docs/datatables/idp_ver.txt L55), ebeam_tas_lot_hist 의 recipe_id 도 "다른 DB 의
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

주차별 변화 모델 (docs/datatables/device_statistics_weekly_trend.txt)
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

분류 규칙 (user-confirmed 2026-08-04, docs/datatables/planstep_r3.txt)
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

mother 파라미터 (docs/datatables/recipe_idp.txt L182, office 확인 2026-07-28)
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

OFFICE-VERIFY: mother 발생률(여기서는 recipe 의 약 85%가 보유, 보유 시 각 bin 의
25~45%)은 실물에서 확인된 바 없습니다. 사무실에서는 **원천 자체가 미해결**입니다
— ``cdsem_idp_ver.parameters`` 는 ``{name: point_count}`` 라 mother 플래그를 담을
자리가 없고, ``Mother_Para`` 가 확인된 곳은 장비 FTP 의 ``.idp`` 원본 파일뿐입니다
(recipe 1건당 파일 1개라 device 4000개 규모로는 조회 불가). MIGRATION.md 의
"mother_para 출처" 절을 보십시오.

Internal module: 이 feature 밖에서는 device_statistics.data 를 통해 쓰십시오.
"""

import random
import re
from typing import TypedDict


# ── 분류 규칙 (office_example.py 와 동일) ──────────────────────────────────
# recipe 이름이 "_S"/"SE" 로 끝나면 Sample. 축이 스텝명이 아니라 **recipe 이름**
# 인 것이 핵심입니다.
_SAMPLE_SUFFIX = re.compile(r"(_S|SE)$", re.IGNORECASE)

# 특수 측정 job 접미사. CDU 는 **목록이 아니라 패턴**입니다 — 앞 글자는 어떤
# map 을 재는지를 뜻할 뿐이라(W=wafer, F=field, B=…) 종류가 늘 수 있고, 실제로
# _WCDU/_FCDU 만 적어 두었더니 _BCDU 가 새어 나왔습니다 (user-confirmed
# 2026-08-05). _FULL/_HALF/_MTX 는 CDU 가 아닌 별개 job 이라 이름으로 답니다.
# 프론트엔드 lotHealth.EXEMPT_JOB_SUFFIX 와 같은 식이어야 합니다.
_EXEMPT_JOB_SUFFIX = re.compile(r"(_[A-Z]*CDU|_FULL|_HALF|_MTX)$", re.IGNORECASE)


def is_sample_recipe(recipe_id: str) -> bool:
    """recipe 이름이 "_S"/"SE" 로 끝나는가."""
    return bool(_SAMPLE_SUFFIX.search((recipe_id or "").strip()))


def is_exempt_job(recipe_id: str) -> bool:
    """recipe 이름이 특수 측정 job 접미사로 끝나는가.

    프론트엔드 ``lotHealth.isExemptJob`` 과 **같은 정규식**입니다. 이 표면에서도
    공개 함수인 이유는 소비처가 둘이기 때문입니다 — 이름을 만드는
    :func:`_recipe_name` 과, 그 job 의 측정 규모를 정하는 ``recipe_params``.

    :data:`_JUDGE_EXEMPT_SUFFIXES` 로 판정하지 **않는** 것이 중요합니다. 그
    튜플은 mock 이 만들어 볼 표본일 뿐이고, 판정 기준은 패턴입니다 — 표본에
    없는 "_BCDU" 도 걸러야 하기 때문입니다.
    """
    return bool(_EXEMPT_JOB_SUFFIX.search((recipe_id or "").strip()))


def ends_with_pure_cd(oper_desc: str) -> bool:
    """스텝명 끝이 **순수한 CD** 인가 — "CD(E)"/"CD(F)"/"CD(BENDING)" 은 제외.

    실제 스텝명은 "SNC2(CELL OPEN ETCH CLN CD)" 처럼 괄호로 닫히므로, 닫는
    괄호를 벗긴 뒤 마지막 토큰이 정확히 "CD" 인지 봅니다. "…CLN CD(E))" 는
    벗겨도 마지막 토큰이 "CD(E" 라 걸러집니다. 꼬리가 단어인
    "…CLN CD(BENDING))" 도 같은 이유로 "CD(BENDING" 이 되어 걸러집니다 —
    규칙이 꼬리의 길이를 가정하지 않는 것이 핵심입니다.
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
    para_16: int
    para_13: int
    para_9: int
    para_5: int
    mother_para_16: int
    mother_para_13: int
    mother_para_9: int
    mother_para_5: int


# ── 이름 어휘 ────────────────────────────────────────────────────────────
# 실제 스텝명은 "SNC2(CELL OPEN ETCH CLN CD)" 처럼 코드(설명 … 접미)입니다.
_STEP_CODES = ("SNC2", "SNB1", "PLD3", "MTC1", "GTE2", "ACT4", "VIA1", "CNT3")
_STEP_WORDS = (
    "CELL OPEN ETCH CLN", "GATE POLY ETCH", "ACTIVE TRENCH CLN",
    "METAL1 CMP", "CONTACT OPEN", "VIA ETCH CLN", "SPACER DEPO",
    "HARD MASK OPEN", "BIT LINE ETCH",
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

# recipe 이름이 "_S"/"SE" 로 끝나는 비율 = only_sample 버킷 크기.
_SAMPLE_RATIO = 0.25

# 만들어 볼 특수 측정 job 접미사 **표본**입니다 — 판정 기준이 아닙니다.
# 기준은 :data:`_EXEMPT_JOB_SUFFIX` 패턴이고, 여기 있는 것은 그 패턴이 집에서
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
# _WCDU/_FCDU/_FULL user-confirmed 2026-08-04,
# _HALF/_BCDU/_MTX user-confirmed 2026-08-05.
_JUDGE_EXEMPT_SUFFIXES = ("_WCDU", "_FCDU", "_BCDU", "_FULL", "_HALF", "_MTX")
_JUDGE_EXEMPT_RATIO = 0.10

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
POOL_RANGE = (175, 200)

PARA_RANGES = {
    "para_16": (10, 50),
    "para_13": (6, 32),
    "para_9": (3, 16),
    "para_5": (1, 9),
}

SKIPPED_RATIO = 0.15
BLANK_SKIP_YN_RATIO = 0.15

# 정체성 풀 seed 를 주차 seed 와 갈라놓는 salt. 주차별 rng 와 섞이면 풀이 주차마다
# 달라져 recipe_id 안정성이 깨집니다.
_IDENTITY_SALT = 90001

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

_PARA_KEYS = ("para_16", "para_13", "para_9", "para_5")


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
    code = rng.choice(_STEP_CODES)
    words = rng.choice(_STEP_WORDS)
    roll = rng.random()
    if roll < _PURE_CD_RATIO:
        return f"{code}({words} CD)"
    if roll < _PURE_CD_RATIO + _PAREN_CD_RATIO:
        return f"{code}({words} {rng.choice(_CD_VARIANTS)})"
    return f"{code}({words})"


def _recipe_name(rng: random.Random, lot_cd: str, idx: int) -> str:
    """base + Sample 이면 "_S"/"SE", 일부는 판정 외 job 접미사(_WCDU 등).

    비-Sample·비-exempt id 는 숫자로 끝나므로 ``(_S|SE)$`` 에 우연히 걸리지
    않습니다. exempt 분기는 **같은 roll 을 나눠 쓰고** 접미사를 idx 로 골라
    rng 호출 수를 바꾸지 않습니다 — 호출 수가 달라지면 풀의 뒤쪽 recipe 전부가
    다른 값으로 다시 태어나, 결정론에 기대는 화면·테스트가 통째로 흔들립니다.
    """
    base = f"RCP-{lot_cd}-{idx:03d}"
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
            "para_16": rng.randint(*PARA_RANGES["para_16"]),
            "para_13": rng.randint(*PARA_RANGES["para_13"]),
            "para_9": rng.randint(*PARA_RANGES["para_9"]),
            "para_5": rng.randint(*PARA_RANGES["para_5"]),
            # 바로 아래 별도 rng 가 채웁니다. 여기서 굴리면 위 난수 순서가 밀려
            # 풀 전체가 다른 값으로 다시 태어납니다 (_MOTHER_SALT 주석 참고).
            "mother_para_16": 0,
            "mother_para_13": 0,
            "mother_para_9": 0,
            "mother_para_5": 0,
        })

    _assign_mother_counts(pool, lot_cd)
    return pool


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


def _scaled(value: int, factor: float, jitter: float) -> int:
    """파라미터 개수에 주차 배율 + 약간의 흔들림. 최소 1 은 유지합니다."""
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
