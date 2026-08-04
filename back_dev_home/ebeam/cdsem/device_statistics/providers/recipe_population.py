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

분류 규칙 (user-confirmed 2026-07-31, docs/datatables/planstep_r3.txt L105-111)
──────────────────────────────────────────────────────────────────────────────
  all            모든 Step
  only_normal    스텝명에 CD 가 토큰으로 등장하는 Step
  mother_normal  skip 되지 않은(skip_yn != "Y") Step 중 스텝명 끝이 **순수한 CD**
                 ("CD(E)", "CD(F)" 는 제외)
  only_sample    **recipe 이름**이 "_S" 또는 "SE" 로 끝나는 Step

아래 세 판정 함수는 office_example.py 의 동명 함수와 같은 규칙입니다. 두 벌이
갈라지면 집에서 만든 화면이 사무실에서 다르게 나오므로, tests 가 같은 예시 표로
양쪽을 함께 검증합니다.

Internal module: 이 feature 밖에서는 device_statistics.data 를 통해 쓰십시오.
"""

import random
import re
from typing import TypedDict


# ── 분류 규칙 (office_example.py 와 동일) ──────────────────────────────────
# recipe 이름이 "_S"/"SE" 로 끝나면 Sample. 축이 스텝명이 아니라 **recipe 이름**
# 인 것이 핵심입니다.
_SAMPLE_SUFFIX = re.compile(r"(_S|SE)$", re.IGNORECASE)

# 이름 어디든 CD 가 토큰으로 등장하면 정규(Normal) step.
_CD_TOKEN = re.compile(r"\bCD\b", re.IGNORECASE)


def is_sample_recipe(recipe_id: str) -> bool:
    """recipe 이름이 "_S"/"SE" 로 끝나는가."""
    return bool(_SAMPLE_SUFFIX.search((recipe_id or "").strip()))


def is_normal_step(oper_desc: str) -> bool:
    """스텝명 어디든 CD 가 토큰으로 있는가."""
    return bool(_CD_TOKEN.search(oper_desc or ""))


def ends_with_pure_cd(oper_desc: str) -> bool:
    """스텝명 끝이 **순수한 CD** 인가 — "CD(E)" / "CD(F)" 는 제외.

    실제 스텝명은 "SNC2(CELL OPEN ETCH CLN CD)" 처럼 괄호로 닫히므로, 닫는
    괄호를 벗긴 뒤 마지막 토큰이 정확히 "CD" 인지 봅니다. "…CLN CD(E))" 는
    벗겨도 마지막 토큰이 "CD(E" 라 걸러집니다.
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


class RecipeIdentity(TypedDict):
    """statistics 와 recipe_params 가 공유하는 recipe 한 건."""

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


# ── 이름 어휘 ────────────────────────────────────────────────────────────
# 실제 스텝명은 "SNC2(CELL OPEN ETCH CLN CD)" 처럼 코드(설명 … 접미)입니다.
_STEP_CODES = ("SNC2", "SNB1", "PLD3", "MTC1", "GTE2", "ACT4", "VIA1", "CNT3")
_STEP_WORDS = (
    "CELL OPEN ETCH CLN", "GATE POLY ETCH", "ACTIVE TRENCH CLN",
    "METAL1 CMP", "CONTACT OPEN", "VIA ETCH CLN", "SPACER DEPO",
    "HARD MASK OPEN", "BIT LINE ETCH",
)

# 스텝명 접미 비율이 곧 버킷 크기입니다 — only_normal 은 CD 가 들어간 전부(약 67%),
# mother_normal 은 그중 "순수한 CD" 이면서 측정 중인 것(약 38%)입니다. 예전
# RECIPE_COUNT_RANGES 가 만들던 상대 서열(all > only_normal > mother_normal >
# only_sample)을 유지해 비교 페이지의 막대 순서가 바뀌지 않습니다.
_PURE_CD_RATIO = 0.45      # "… CLN CD)"     -> only_normal + mother_normal 후보
_PAREN_CD_RATIO = 0.22     # "… CLN CD(E))"  -> only_normal 만
# 나머지 33% 는 CD 없는 스텝 -> 어느 CD 버킷에도 안 들어갑니다.

_CD_VARIANTS = ("CD(E)", "CD(F)")

# recipe 이름이 "_S"/"SE" 로 끝나는 비율 = only_sample 버킷 크기.
_SAMPLE_RATIO = 0.25

# 판정 외(exempt) job 접미사 — CDU·full-map 측정 job 은 recipe 이름이 이렇게
# 끝납니다 (user-confirmed 2026-08-04). 프론트엔드 lotHealth.isJudgeExempt 가
# 이 접미사를 판정 범위(분자·분모 모두)에서 뺍니다 — mock 이 이 이름을 만들지
# 않으면 그 경로가 집에서 한 번도 실행되지 않습니다.
_JUDGE_EXEMPT_SUFFIXES = ("_WCDU", "_FCDU", "_FULL")
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
        })

    return pool


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

    return [
        {
            **identity,
            "para_16": _scaled(identity["para_16"], para_scale, jitter_rng.uniform(0.94, 1.06)),
            "para_13": _scaled(identity["para_13"], para_scale, jitter_rng.uniform(0.94, 1.06)),
            "para_9": _scaled(identity["para_9"], para_scale, jitter_rng.uniform(0.94, 1.06)),
            "para_5": _scaled(identity["para_5"], para_scale, jitter_rng.uniform(0.94, 1.06)),
        }
        for identity in present
    ]


def bucket_members(
    population: list[RecipeIdentity]
) -> dict[str, list[RecipeIdentity]]:
    """네 버킷의 recipe 집합. 한 recipe 가 여러 버킷에 들어갈 수 있습니다."""
    return {
        "all": list(population),
        "only_normal": [r for r in population if is_normal_step(r["oper_desc"])],
        "mother_normal": [
            r for r in population
            if is_measuring(r["skip_yn"]) and ends_with_pure_cd(r["oper_desc"])
        ],
        "only_sample": [r for r in population if is_sample_recipe(r["recipe_id"])],
    }
