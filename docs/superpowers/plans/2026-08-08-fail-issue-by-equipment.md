# Align / Meas Fail 장비별 뷰 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recipe 현황의 `Align Fail`·`Meas Fail` 두 탭에 `장비별`(eqp_id 기준)
뷰를 추가해, 레시피 구성으로 정규화한 실패 지수로 장비를 비교하고 최대 5대를
골라 추이와 레시피 구성을 겹쳐 볼 수 있게 합니다.

**Architecture:** 2026-08-07 에 `Recipe TAT` 탭에 넣은 장비별 뷰와 같은 3층
구조입니다. provider(mock/office)가 격자만 만들고, 공용 조립기
(`fail_issue/providers/_shape.py`)가 지수·신뢰구간·분위수를 계산하며,
프론트엔드는 배지 경계값 두 개만 갖습니다. 실패 지수는 역학의 간접표준화
비(SMR)와 같은 양이므로 잡음 판정을 Byar 신뢰구간으로 합니다 — 상수 하나와
비교하는 방식은 이 화면의 표본 크기에서 동작하지 않습니다.

**Tech Stack:** Flask blueprint + TypedDict 계약 (백엔드), Nuxt 4 + NuxtUI
`UTable` + ECharts (프론트엔드), pytest (백엔드 테스트), `node --test`
(프론트엔드 순수 함수 테스트).

**설계 문서:** `docs/superpowers/specs/2026-08-08-fail-issue-by-equipment-design.md`
— 이 계획이 무엇을 왜 만드는지에 대한 판단은 전부 거기 있습니다. 계획과
설계가 어긋나면 설계가 맞습니다.

## Global Constraints

- **`data.py` 를 편집하지 마십시오** — 는 이 저장소의 일반 규칙이지만
  `fail_issue/data.py` 는 dispatcher 이므로 **새 함수 2개를 추가합니다**
  (Task 5). 기존 6개 함수는 손대지 않습니다.
- **`providers/office.py` 를 만들지 마십시오.** gitignore 대상이며 사무실에서
  `office_example.py` 를 `cp` 해서 만듭니다.
- 계약 타입은 전부 `TypedDict` 이고 `contracts.py` 에만 정의합니다.
- 백엔드 소수 반올림은 전부 `round(x, 4)` 입니다 (기존 `_rate()` 와 동일).
- 프론트엔드 색은 `--sk-*` 토큰만 씁니다. inline hex 금지 (`DESIGN.md`).
- 새 surface 의 모서리는 `rounded-[var(--sk-r-card)]` 입니다.
- 프론트엔드 utils 끼리의 import 는 `./name.ts` (값) / `./name` (타입 전용)
  형태여야 합니다 — `node --test` 가 `~` 별칭을 모릅니다.
- Markdown 을 고쳤으면 저장소 루트에서 `npm run lint:md` 를 돌립니다.
- 커밋은 **직접 편집한 파일만** 명시적 경로로 스테이징합니다.
  `git add -A` / `git add .` / `git commit -a` 는 금지입니다 — 이 작업 트리에
  다른 세션이 동시에 붙어 있습니다.

**작업 트리:** 이 작업은 15개 파일을 건드리므로 격리된 worktree 에서
진행합니다.

```bash
git worktree add ../skewnono-fail-eqp -b work/fail-eqp   # 저장소 루트에서
# ...../skewnono-fail-eqp 안에서 전부 편집·테스트·커밋...
git -C . merge --ff-only work/fail-eqp && git push        # main 으로 복귀 후
git worktree remove ../skewnono-fail-eqp && git branch -d work/fail-eqp
```

**명령어** (worktree 루트에서):

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue -q
.venv/bin/python -m pytest -q                    # 전체 (~2180개, ~72초)
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

`.venv` 는 메인 체크아웃에 있습니다. worktree 에서는 절대 경로로 부르거나
메인 체크아웃 경로의 `.venv/bin/python` 을 씁니다.

---

## File Structure

| 파일 | 책임 |
| --- | --- |
| `back_dev_home/ebeam/hitachi/fail_issue/providers/_shape.py` (신규) | mock·office 공용 조립. Byar 구간, 간접표준화, 분위수. 이 기능에서 유일하게 자명하지 않은 수식이 전부 여기 있습니다. |
| `.../fail_issue/contracts.py` (수정) | 새 TypedDict 9개와 상수 2개. |
| `.../fail_issue/providers/mock.py` (수정) | 격자 2종을 만드는 함수 2개 추가. 기존 집계 함수는 불변. |
| `.../fail_issue/providers/office_example.py` (수정) | 같은 격자를 composite 집계로 만드는 템플릿 2개. |
| `.../fail_issue/data.py` (수정) | dispatcher 2개. |
| `.../fail_issue/routes.py` (수정) | GET 2개. |
| `.../fail_issue/tests/test_byar.py` (신규) | 신뢰구간 함수 단독. |
| `.../fail_issue/tests/test_shape.py` (신규) | 조립기 단독 — provider 를 거치지 않습니다. |
| `.../fail_issue/tests/test_contract.py` (수정) | 활성 provider 를 통한 계약 검사. |
| `front-dev-home/app/composables/useFailIssueApi.ts` (수정) | 응답 타입 + fetcher 2개. |
| `front-dev-home/app/utils/failEquipmentSignals.ts` (신규) | 배지 판정 정책. 경계값 2개. |
| `front-dev-home/app/utils/failEquipmentSignals.test.ts` (신규) | 위 파일의 경계 검사. |
| `front-dev-home/app/components/ebeam/FailIssueFleetTable.vue` (신규) | 플릿 표. 검색·정렬·체크박스·배지. |
| `front-dev-home/app/components/ebeam/FailIssueEquipmentCompare.vue` (신규) | 선택 요약 + 추이 오버레이 + 레시피 매트릭스. |
| `front-dev-home/app/components/ebeam/FailIssueEquipmentView.vue` (신규) | 데이터 로드 + 빈 상태 + 선택 상태 소유. |
| `front-dev-home/app/components/ebeam/FailIssueView.vue` (수정) | 세 번째 모드 분기 + SkNavPill 전환. |
| `docs/api-contracts/fail-issue.yaml` (수정) | 두 엔드포인트 계약. |
| `.../fail_issue/MIGRATION.md` (수정) | office 어댑터 지침 + OFFICE-VERIFY 목록. |

---

### Task 1: Byar 신뢰구간

**Files:**

- Create: `back_dev_home/ebeam/hitachi/fail_issue/providers/_shape.py`
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/contracts.py`
- Test: `back_dev_home/ebeam/hitachi/fail_issue/tests/test_byar.py`

**Interfaces:**

- Consumes: 없음 (표준 라이브러리 `math.sqrt` 만).
- Produces:
  - `contracts.FAIL_INDEX_MIN_EXPECTED: float = 1.0`
  - `contracts.CONFIDENCE_Z: float = 1.96`
  - `_shape.byar_interval(observed: int, expected: float, z: float = CONFIDENCE_Z) -> tuple[float, float]`
  - `_shape.standardised(observed: int, expected: float) -> tuple[float | None, float | None, float | None]`
    — `(index, low, high)`. `expected < FAIL_INDEX_MIN_EXPECTED` 이면 `(None, None, None)`.

- [ ] **Step 1: 상수 2개를 `contracts.py` 에 추가**

`contracts.py` 의 `__all__` 바로 아래, `AlignOutcome` 정의 위에 넣습니다.

```python
# 지수를 만들 수 있는 최소 기대 실패 건수. 기대가 1건 미만이면 비율의 분모가
# 사실상 없습니다.
#
# recipe_tat 의 TAT_INDEX_MIN_SAMPLE(=12, 실행 횟수) 과 달리 **OFFICE-VERIFY 가
# 아닙니다.** 튜닝 대상이 아니라 정의의 경계이기 때문입니다. 잡음 판정은 이
# 상수가 아니라 신뢰구간이 합니다 — 설계 3.2절.
FAIL_INDEX_MIN_EXPECTED = 1.0

# Byar 구간의 신뢰수준. 95 % 관례값이며 튜닝 대상이 아닙니다. payload 에
# 에코하는 이유는 프론트엔드가 구간의 의미를 추측하지 않게 하기 위해서입니다.
CONFIDENCE_Z = 1.96
```

`__all__` 에 두 이름을 추가합니다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`back_dev_home/ebeam/hitachi/fail_issue/tests/test_byar.py` 를 만듭니다.

```python
"""Byar 근사 신뢰구간 단독 검증.

이 함수는 이 기능에서 **유일하게 자명하지 않은 수식**입니다. 나머지는 합계와
나눗셈이라 눈으로 검증되지만, Byar 근사는 틀려도 그럴듯한 숫자를 냅니다 —
지수 하나만 잘못 써도 구간이 좁아지거나 넓어질 뿐 예외가 나지 않고, 그
결과는 "배지가 좀 덜/더 뜨네" 로만 보입니다. 그래서 문헌값 대조를 겁니다.
"""

import math

import pytest

from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    CONFIDENCE_Z,
    FAIL_INDEX_MIN_EXPECTED,
)
from back_dev_home.ebeam.hitachi.fail_issue.providers._shape import (
    byar_interval,
    standardised,
)


def test_matches_the_published_approximation():
    """관측 11 · 기대 5 → 약 [1.10, 3.94].

    Byar 의 근사식을 손으로 계산한 값입니다. 이 하나가 지수·계수 오타를
    전부 잡습니다.
    """
    low, high = byar_interval(11, 5.0)
    assert low == pytest.approx(1.0967, abs=1e-4)
    assert high == pytest.approx(3.9367, abs=1e-4)


def test_zero_observed_has_a_zero_lower_bound_and_does_not_raise():
    """obs=0 은 log/sqrt 가 정의되지 않는 자리입니다.

    분기를 빼면 ZeroDivisionError 가 납니다. 하한은 정확히 0 이어야 하며
    ('실패가 0건이면 진짜 0일 수도 있다'), 상한은 유한해야 합니다.
    """
    low, high = byar_interval(0, 4.0)
    assert low == 0.0
    assert high == pytest.approx(0.917, abs=1e-3)


def test_interval_always_brackets_the_point_estimate():
    for observed in range(0, 200):
        expected = 37.5
        low, high = byar_interval(observed, expected)
        index = observed / expected
        assert low <= index <= high, (observed, low, index, high)


def test_interval_narrows_as_the_sample_grows():
    """같은 지수(=1.0)를 유지한 채 규모만 키우면 구간이 좁아져야 합니다.

    이 단조성이 깨지면 '조용한 장비는 극단적이어야 배지를 받는다'는 설계의
    핵심 성질이 사라집니다.
    """
    widths = []
    for scale in (5, 20, 80, 320):
        low, high = byar_interval(scale, float(scale))
        widths.append(high - low)
    assert widths == sorted(widths, reverse=True), widths


def test_standardised_withholds_a_verdict_below_the_display_floor():
    assert standardised(0, 0.8) == (None, None, None)
    assert standardised(1, 0.5) == (None, None, None)


def test_standardised_reports_at_and_above_the_display_floor():
    index, low, high = standardised(3, FAIL_INDEX_MIN_EXPECTED)
    assert index == 3.0
    assert low is not None and high is not None
    assert low <= index <= high


def test_z_is_the_two_sided_95_percent_value():
    # 구간의 의미가 조용히 바뀌는 것을 막습니다. 이 값을 바꾸려면 설계 3.2절
    # 과 payload 의 confidence_z 에코를 함께 바꿔야 합니다.
    assert CONFIDENCE_Z == 1.96
    assert math.isclose(FAIL_INDEX_MIN_EXPECTED, 1.0)
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue/tests/test_byar.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named
'back_dev_home.ebeam.hitachi.fail_issue.providers._shape'`

- [ ] **Step 4: 최소 구현**

`back_dev_home/ebeam/hitachi/fail_issue/providers/_shape.py` 를 만듭니다.

```python
"""mock·office 공용 payload 조립.

provider 는 자기 소스에서 격자(grid)만 만들고 여기로 넘깁니다. 지수·구간·
분위수를 두 provider 가 각자 계산하면 언젠가 어긋나고, 그때 어느 쪽이 맞는지
판정할 방법이 없습니다 — 집에서는 office 를 실행할 수 없으므로 그 판정자가
아예 존재하지 않습니다. recipe_tat/providers/_shape.py 와 같은 규약입니다.
"""

from __future__ import annotations

from math import sqrt

from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    CONFIDENCE_Z,
    FAIL_INDEX_MIN_EXPECTED,
)


def byar_interval(
    observed: int,
    expected: float,
    z: float = CONFIDENCE_Z,
) -> tuple[float, float]:
    """관측/기대 건수비의 신뢰구간 (Byar 근사).

    이 지수는 역학의 간접표준화 비(SMR)와 같은 양이고, Byar 근사는 그쪽의
    표준 처방입니다. 정확한 Garwood 구간(카이제곱 분위수)을 쓰지 않는 이유는
    scipy 의존을 들이지 않기 위해서이며, 근사 오차는 observed >= 1 에서
    소수 셋째 자리 수준이라 배지 판정에 영향을 주지 않습니다.

    observed == 0 은 sqrt(0) 로 0 나눗셈이 나는 자리라 분기가 필요합니다.
    하한은 그 경우 정확히 0 입니다 — 실패가 0건이면 참값이 0일 수도 있습니다.
    """
    if expected <= 0:
        return (0.0, 0.0)

    if observed <= 0:
        low = 0.0
    else:
        low = observed * (1 - 1 / (9 * observed) - z / (3 * sqrt(observed))) ** 3 / expected
        low = max(0.0, low)

    upper_n = observed + 1
    high = upper_n * (1 - 1 / (9 * upper_n) + z / (3 * sqrt(upper_n))) ** 3 / expected

    return (round(low, 4), round(high, 4))


def standardised(
    observed: int,
    expected: float,
) -> tuple[float | None, float | None, float | None]:
    """(index, low, high). 기대가 표시 하한 미만이면 셋 다 None.

    None 은 "실패하지 않았다"가 아니라 **"모른다"** 입니다. 호출자는 어느
    쪽으로도 판정하면 안 되며, 특히 0 으로 채우면 안 됩니다.
    """
    if expected < FAIL_INDEX_MIN_EXPECTED:
        return (None, None, None)
    low, high = byar_interval(observed, expected)
    return (round(observed / expected, 4), low, high)
```

- [ ] **Step 5: 테스트가 통과하는지 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue/tests/test_byar.py -q`

Expected: PASS (7 passed)

- [ ] **Step 6: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/fail_issue/providers/_shape.py \
        back_dev_home/ebeam/hitachi/fail_issue/contracts.py \
        back_dev_home/ebeam/hitachi/fail_issue/tests/test_byar.py
git commit -m "feat(fail-issue): 실패 지수의 신뢰구간(Byar 근사)을 더한다

이 지수는 간접표준화 비(SMR)라 점추정값을 상수와 비교하면 표본이 작을 때
잡음이 그대로 배지가 됩니다. 구간이 1.0 을 넘겼는지로 판정하기 위한
기반입니다. observed=0 분기가 없으면 0 나눗셈입니다."
```

---

### Task 2: 장비별 집계 조립기

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/fail_issue/contracts.py`
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/providers/_shape.py`
- Test: `back_dev_home/ebeam/hitachi/fail_issue/tests/test_shape.py`

**Interfaces:**

- Consumes: `_shape.standardised` (Task 1),
  `back_dev_home.ebeam.hitachi._analytics.percentile_summary`.
- Produces:
  - `_shape.EquipmentGridRow = tuple[str, str, str, str, int, int, int]`
    — `(eqp_id, fab_name, eqp_model_cd, full_name, exec_count, align_fails, meas_fails)`
  - `_shape.build_equipments_payload(tool_type, fab_names, start_date, end_date, grid) -> EquipmentsPayload`
  - `contracts.EquipmentRow`, `contracts.FleetReference`, `contracts.EquipmentsPayload`

- [ ] **Step 1: 계약 타입 3개를 `contracts.py` 에 추가**

`DeviceRow` 정의 아래에 붙이고, 세 이름을 `__all__` 에 추가합니다.

```python
class EquipmentRow(TypedDict):
    eqp_id: str
    fab_name: str
    eqp_model_cd: str
    exec_count: int
    # align --------------------------------------------------------------
    align_fail_count: int
    align_fail_rate: float          # fraction, 0..1
    # 이 장비의 레시피 구성이면 나왔어야 할 실패 건수. 표의 툴팁이 이 값을
    # 그대로 보여줍니다 — 배지가 켜진 근거를 사용자가 확인할 수 없으면
    # 배지를 믿지 않거나, 더 나쁘게는 근거 없이 믿습니다.
    align_expected: float
    align_index: float | None       # actual / expected. 표시 하한 미만이면 None
    align_index_low: float | None   # Byar 95 % 하한
    align_index_high: float | None
    # meas ---------------------------------------------------------------
    meas_fail_count: int
    meas_fail_rate: float
    meas_expected: float
    meas_index: float | None
    meas_index_low: float | None
    meas_index_high: float | None
    # 구성 ---------------------------------------------------------------
    recipe_count: int
    top_recipe: str | None
    # 실행 **횟수** 비중입니다(recipe_tat 은 TAT 비중). 실패 화면에서 "이
    # 장비는 사실상 한 레시피만 돈다"의 근거는 시간이 아니라 횟수입니다.
    top_recipe_share: float


class FleetReference(TypedDict):
    tool_count: int
    total_executions: int
    align_fail_count: int
    meas_fail_count: int
    align_fail_rate: float
    meas_fail_rate: float
    median_exec_count: float
    median_recipe_count: float
    min_expected_fails: float
    confidence_z: float
    # 사무실에서 FAIL_INDEX_CEIL 을 정하기 위한 분포 참고용입니다.
    # **배지 판정에는 쓰이지 않습니다** — 잡음 판정은 신뢰구간이 합니다.
    # 키: "align_fail_rate" | "align_index" | "meas_fail_rate" | "meas_index"
    #     | "recipe_count" | "exec_count"
    # 값: {"p10","p25","p50","p75","p90"}. 지수는 None 인 장비를 제외하고
    # 계산하며, 대상 장비가 없으면 빈 dict.
    percentiles: dict[str, dict[str, float]]


class EquipmentsPayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    fleet: FleetReference
    equipments: list[EquipmentRow]
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`back_dev_home/ebeam/hitachi/fail_issue/tests/test_shape.py` 를 만듭니다.

```python
"""`build_equipments_payload` 자체를 격자 하나로 직접 검증합니다.

test_contract.py 는 활성 provider 를 통해서만 이 함수에 닿습니다. 그런데
office 어댑터는 mock 을 전혀 거치지 않고 이 함수를 부르므로, 조립기의
불변식은 provider 와 무관하게 고정되어야 합니다.

여기서 지키는 것은 **간접표준화 그 자체**입니다. 계약 검사와 분위수 단조성
테스트는 `expected(t) = Σ_r exec(t,r) × base(r)` 를
`expected(t) = exec_count(t) × 플릿전체실패율` 이라는 순진한 식으로 바꿔도
그대로 통과합니다 — 즉 이 지수가 존재하는 이유(레시피 난이도가 아니라 장비를
재는 것)를 그 테스트들은 하나도 지키지 못합니다. 아래 격자들은 두 식의 답이
**설계상 달라지도록** 만들어져 있어서, 순진한 식으로 바꾸면 실패합니다.
"""

import pytest

from back_dev_home.ebeam.hitachi.fail_issue.providers._shape import (
    build_equipments_payload,
)


MODEL = "CG6300"
FAB = "R3"
START, END = "2026-07-25", "2026-08-08"


def _payload(grid):
    return build_equipments_payload("cd-sem", (FAB,), START, END, grid)


def _by_id(payload) -> dict:
    return {row["eqp_id"]: row for row in payload["equipments"]}


# 레시피 난이도가 다른 두 레시피를 정반대 비율로 도는 두 장비. 각 레시피에서
# 둘 다 **정확히 플릿 평균 실패율**입니다.
#
#   L/EASY  기저 5 %,  L/HARD  기저 30 %
#   EQ-EASYMIX : EASY 1000회(50 실패) + HARD  100회( 30 실패)
#   EQ-HARDMIX : EASY  100회( 5 실패) + HARD 1000회(300 실패)
#
# 원 실패율은 7.27 % 대 27.73 % 로 4배 가까이 벌어지지만 장비 상태는 동일
# 합니다. 지수는 둘 다 정확히 1.0 이어야 합니다.
MIX_GRID = [
    ("EQ-EASYMIX", FAB, MODEL, "L/EASY", 1000, 50, 50),
    ("EQ-EASYMIX", FAB, MODEL, "L/HARD", 100, 30, 30),
    ("EQ-HARDMIX", FAB, MODEL, "L/EASY", 100, 5, 5),
    ("EQ-HARDMIX", FAB, MODEL, "L/HARD", 1000, 300, 300),
]


def test_recipe_mix_cancels_out_so_equal_tools_both_score_one():
    rows = _by_id(_payload(MIX_GRID))

    easy = rows["EQ-EASYMIX"]
    hard = rows["EQ-HARDMIX"]

    # 원 비율은 크게 다릅니다 — 이 차이를 지수가 흡수하는 것이 요점입니다.
    assert easy["align_fail_rate"] == pytest.approx(0.0727, abs=1e-4)
    assert hard["align_fail_rate"] == pytest.approx(0.2773, abs=1e-4)

    assert easy["align_expected"] == pytest.approx(80.0, abs=1e-6)
    assert hard["align_expected"] == pytest.approx(305.0, abs=1e-6)
    assert easy["align_index"] == pytest.approx(1.0, abs=1e-4)
    assert hard["align_index"] == pytest.approx(1.0, abs=1e-4)

    # meas 는 같은 격자 열이므로 같은 답이 나와야 합니다. align 열을 실수로
    # 두 번 읽는 오타를 잡습니다.
    assert easy["meas_index"] == pytest.approx(1.0, abs=1e-4)
    assert hard["meas_index"] == pytest.approx(1.0, abs=1e-4)


def test_an_average_tool_gets_an_interval_that_straddles_one():
    """지수가 1.0 이면 구간이 1.0 을 걸쳐야 하고, 그래서 배지가 없습니다."""
    rows = _by_id(_payload(MIX_GRID))
    easy = rows["EQ-EASYMIX"]
    assert easy["align_index_low"] < 1.0 < easy["align_index_high"]
    assert easy["align_index_low"] == pytest.approx(0.7929, abs=1e-4)
    assert easy["align_index_high"] == pytest.approx(1.2446, abs=1e-4)


# 세 장비가 **같은 레시피만** 돕니다 — 레시피 구성이 동일하므로 지수 차이는
# 순수하게 장비 차이입니다. EQ-C 만 3배 실패합니다.
SAME_MIX_GRID = [
    ("EQ-A", FAB, MODEL, "L/EASY", 1000, 50, 50),
    ("EQ-B", FAB, MODEL, "L/EASY", 1000, 50, 50),
    ("EQ-C", FAB, MODEL, "L/EASY", 1000, 150, 150),
]


def test_a_genuinely_worse_tool_gets_an_interval_clear_of_one():
    rows = _by_id(_payload(SAME_MIX_GRID))

    # base = (50+50+150)/3000 = 0.08333 → expected = 83.333 for each
    assert rows["EQ-C"]["align_expected"] == pytest.approx(83.3333, abs=1e-3)
    assert rows["EQ-C"]["align_index"] == pytest.approx(1.8, abs=1e-3)
    assert rows["EQ-C"]["align_index_low"] == pytest.approx(1.5235, abs=1e-3)
    # 하한이 1.0 위 — 잡음으로 설명되지 않습니다.
    assert rows["EQ-C"]["align_index_low"] > 1.0

    assert rows["EQ-A"]["align_index"] == pytest.approx(0.6, abs=1e-3)
    assert rows["EQ-A"]["align_index_high"] == pytest.approx(0.791, abs=1e-3)
    # 상한이 1.0 아래 — 진짜로 좋습니다.
    assert rows["EQ-A"]["align_index_high"] < 1.0


def test_index_is_none_below_the_display_floor():
    """기대 실패가 1건 미만이면 지수도 구간도 없습니다."""
    grid = [
        ("EQ-BUSY", FAB, MODEL, "L/RARE", 10_000, 10, 10),
        ("EQ-QUIET", FAB, MODEL, "L/RARE", 5, 0, 0),
    ]
    rows = _by_id(_payload(grid))

    # base = 10/10005 ≈ 0.001 → EQ-QUIET 의 기대는 0.005건
    quiet = rows["EQ-QUIET"]
    assert quiet["align_index"] is None
    assert quiet["align_index_low"] is None
    assert quiet["align_index_high"] is None
    # 원 수치는 그대로 남습니다 — 판단만 보류하지 정보를 지우지 않습니다.
    assert quiet["exec_count"] == 5
    assert quiet["align_fail_count"] == 0


def test_percentiles_exclude_tools_without_an_index():
    """None 을 0 으로 채우면 p10 이 통째로 무너집니다."""
    grid = [
        ("EQ-BUSY", FAB, MODEL, "L/RARE", 10_000, 10, 10),
        ("EQ-QUIET", FAB, MODEL, "L/RARE", 5, 0, 0),
    ]
    payload = _payload(grid)
    percentiles = payload["fleet"]["percentiles"]["align_index"]
    # 지수를 가진 장비가 EQ-BUSY 하나뿐이므로 모든 분위수가 그 값입니다.
    # (base = 10/10005 이라 EQ-BUSY 의 지수는 정확히 1 이 아니라 1.0005 입니다 —
    #  EQ-QUIET 의 실행 5건이 분모에 들어가기 때문입니다.)
    assert set(percentiles) == {"p10", "p25", "p50", "p75", "p90"}
    assert all(v == pytest.approx(1.0, abs=1e-2) for v in percentiles.values())
    assert len(set(percentiles.values())) == 1


def test_percentiles_are_empty_when_nothing_qualifies():
    grid = [("EQ-QUIET", FAB, MODEL, "L/RARE", 5, 0, 0)]
    payload = _payload(grid)
    # base=0 → expected=0 → 하한 미달 → 대상 없음 → 빈 dict("판단 근거 없음")
    assert payload["fleet"]["percentiles"]["align_index"] == {}


def test_top_recipe_is_by_execution_count_with_a_deterministic_tiebreak():
    """동률이면 full_name 사전순 뒤가 이깁니다.

    tat 만으로 비교하면 dict 삽입 순서가 승자를 정하는데, 그 순서는
    mock(행 스캔)과 office(composite 버킷)가 서로 다릅니다.
    """
    grid = [
        ("EQ-TIE", FAB, MODEL, "A/FIRST", 100, 5, 5),
        ("EQ-TIE", FAB, MODEL, "Z/LAST", 100, 5, 5),
    ]
    row = _by_id(_payload(grid))["EQ-TIE"]
    assert row["top_recipe"] == "Z/LAST"
    assert row["top_recipe_share"] == pytest.approx(0.5, abs=1e-4)
    assert row["recipe_count"] == 2


def test_fleet_totals_match_the_sum_of_rows():
    payload = _payload(MIX_GRID)
    fleet = payload["fleet"]
    rows = payload["equipments"]

    assert fleet["tool_count"] == len(rows) == 2
    assert fleet["total_executions"] == sum(r["exec_count"] for r in rows)
    assert fleet["align_fail_count"] == sum(r["align_fail_count"] for r in rows)
    assert fleet["meas_fail_count"] == sum(r["meas_fail_count"] for r in rows)
    assert fleet["min_expected_fails"] == 1.0
    assert fleet["confidence_z"] == 1.96


def test_rows_sort_by_execution_count_desc_then_eqp_id():
    grid = [
        ("EQ-B", FAB, MODEL, "L/X", 100, 10, 10),
        ("EQ-A", FAB, MODEL, "L/X", 100, 10, 10),
        ("EQ-C", FAB, MODEL, "L/X", 500, 50, 50),
    ]
    ids = [r["eqp_id"] for r in _payload(grid)["equipments"]]
    assert ids == ["EQ-C", "EQ-A", "EQ-B"]


def test_empty_grid_yields_an_empty_but_well_formed_payload():
    payload = _payload([])
    assert payload["equipments"] == []
    assert payload["fleet"]["tool_count"] == 0
    assert payload["fleet"]["align_fail_rate"] == 0.0
    assert payload["fleet"]["median_exec_count"] == 0.0
    assert payload["fleet"]["percentiles"]["exec_count"] == {}
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue/tests/test_shape.py -q`

Expected: FAIL — `ImportError: cannot import name 'build_equipments_payload'`

- [ ] **Step 4: 최소 구현**

`_shape.py` 의 import 블록을 아래로 바꾸고, 파일 끝에 함수를 추가합니다.

```python
from __future__ import annotations

import statistics
from math import sqrt
from typing import Sequence

from back_dev_home.ebeam.hitachi._analytics import percentile_summary
from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    CONFIDENCE_Z,
    EquipmentRow,
    EquipmentsPayload,
    FAIL_INDEX_MIN_EXPECTED,
    ToolType,
)
```

`contracts.py` 는 `ToolType` 을 recipe_tat 의 mock 에서 재수출하고 있으므로
그대로 import 됩니다.

```python
# (eqp_id, fab_name, eqp_model_cd, full_name, exec_count, align_fails, meas_fails)
EquipmentGridRow = tuple[str, str, str, str, int, int, int]


def build_equipments_payload(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    grid: Sequence[EquipmentGridRow],
) -> EquipmentsPayload:
    """장비별 집계 + 배지 판정을 위한 구간과 분포.

    `align_index`/`meas_index`는 간접표준화입니다: 실제 실패 건수를, 이 장비의
    레시피 구성이면 나왔어야 할 건수(레시피별 플릿 실패율 × 이 장비의 실행 수)
    로 나눕니다. 원 실패율로 장비를 줄세우면 정렬이 까다로운 레이어를 맡은
    장비가 저절로 불량 장비가 됩니다 — 장비 상태가 아니라 일감의 난이도를
    잰 것입니다.

    어떤 레시피를 장비 한 대만 돌았다면 그 레시피의 플릿 실패율이 곧 그
    장비의 실패율이라 해당 항이 정확히 1.0 을 기여합니다. 비교 정보가 없는
    일감은 지수를 1.0 쪽으로 희석시킬 뿐 없는 경보를 만들지 않습니다.

    **지수는 fab 하나 안에서만 비교 가능합니다.** `base(r)`이 조회 범위 전체의
    레시피별 평균이라, 여러 fab 을 함께 조회하면 fab 단위의 실패율 차이가 그
    fab 장비 *전부*의 지수가 됩니다. mock 의 FAB_ALIGN_FAIL_RATE 는 fab 별로
    0.05~0.15 로 3배 차이가 나므로 이 편향은 집에서 즉시 재현됩니다. 그래서
    프론트엔드는 조회 범위에 fab 이 2개 이상이면 배지를 아예 달지 않습니다
    (front-dev-home/app/utils/equipmentSignals.ts 의 isPeerGroupComparable).
    사무실에서도 같은 상관이 나타나는지는 OFFICE-VERIFY 입니다(MIGRATION.md).
    """
    per_tool: dict[str, dict] = {}
    per_recipe: dict[str, dict] = {}

    for eqp_id, fab_name, model_cd, full_name, execs, align_f, meas_f in grid:
        tool = per_tool.setdefault(eqp_id, {
            "eqp_id": eqp_id,
            "fab_name": fab_name,
            "eqp_model_cd": model_cd,
            "exec_count": 0,
            "align_fail_count": 0,
            "meas_fail_count": 0,
            "recipes": {},
        })
        tool["exec_count"] += execs
        tool["align_fail_count"] += align_f
        tool["meas_fail_count"] += meas_f

        cell = tool["recipes"].setdefault(full_name, {"execs": 0, "align": 0, "meas": 0})
        cell["execs"] += execs
        cell["align"] += align_f
        cell["meas"] += meas_f

        recipe = per_recipe.setdefault(full_name, {"execs": 0, "align": 0, "meas": 0})
        recipe["execs"] += execs
        recipe["align"] += align_f
        recipe["meas"] += meas_f

    # base(r) = 레시피 r 의 플릿 실패율
    base_align = {
        name: agg["align"] / agg["execs"]
        for name, agg in per_recipe.items() if agg["execs"]
    }
    base_meas = {
        name: agg["meas"] / agg["execs"]
        for name, agg in per_recipe.items() if agg["execs"]
    }

    equipments: list[EquipmentRow] = []
    for tool in per_tool.values():
        execs = tool["exec_count"]
        cells = tool["recipes"]

        # `if name in base` — execs 가 0 인 레시피는 base 에 없습니다. mock 은
        # 행마다 1 을 더하므로 도달할 수 없지만, office 의 composite 는
        # doc_count 0 인 버킷을 낼 수 있습니다. 0.0 으로 채우지 않고 건너뛰는
        # 이유: 기여할 실행이 없는 항은 분모에서 빠져야 하고, 0.0 을 더하면
        # 분모만 작아져 지수가 조용히 부풀어 오릅니다.
        expected_align = sum(
            cell["execs"] * base_align[name]
            for name, cell in cells.items() if name in base_align
        )
        expected_meas = sum(
            cell["execs"] * base_meas[name]
            for name, cell in cells.items() if name in base_meas
        )

        align_index, align_low, align_high = standardised(
            tool["align_fail_count"], expected_align
        )
        meas_index, meas_low, meas_high = standardised(
            tool["meas_fail_count"], expected_meas
        )

        # 2차 키로 full_name 을 명시합니다. execs 만으로 비교하면 동률에서 dict
        # 삽입 순서가 승자를 정하는데, 그 순서는 mock(행 스캔 순서)과
        # office(composite 버킷 순서)가 서로 다릅니다 — 같은 장비의 top_recipe
        # (표시값이자 `편중` 배지의 입력)가 provider 에 따라 달라집니다. max
        # 이므로 동률이면 full_name 이 사전순으로 뒤인 쪽이 이깁니다. 어느
        # 쪽을 고르든 상관없고, 정해져 있다는 것만 중요합니다.
        top_name, top_cell = max(
            cells.items(), key=lambda item: (item[1]["execs"], item[0]),
            default=(None, None)
        )

        equipments.append({
            "eqp_id": tool["eqp_id"],
            "fab_name": tool["fab_name"],
            "eqp_model_cd": tool["eqp_model_cd"],
            "exec_count": execs,
            "align_fail_count": tool["align_fail_count"],
            "align_fail_rate": round(tool["align_fail_count"] / execs, 4) if execs else 0.0,
            "align_expected": round(expected_align, 4),
            "align_index": align_index,
            "align_index_low": align_low,
            "align_index_high": align_high,
            "meas_fail_count": tool["meas_fail_count"],
            "meas_fail_rate": round(tool["meas_fail_count"] / execs, 4) if execs else 0.0,
            "meas_expected": round(expected_meas, 4),
            "meas_index": meas_index,
            "meas_index_low": meas_low,
            "meas_index_high": meas_high,
            "recipe_count": len(cells),
            "top_recipe": top_name,
            "top_recipe_share": (
                round(top_cell["execs"] / execs, 4) if execs and top_cell else 0.0
            ),
        })

    # 방향이 서로 달라 한 번에 정렬할 수 없습니다. 파이썬 정렬은 안정적이므로
    # 2차 키를 먼저 오름차순으로 깔고 1차 키를 내림차순으로 덮습니다.
    equipments.sort(key=lambda row: row["eqp_id"])
    equipments.sort(key=lambda row: row["exec_count"], reverse=True)

    total_execs = sum(row["exec_count"] for row in equipments)
    total_align = sum(row["align_fail_count"] for row in equipments)
    total_meas = sum(row["meas_fail_count"] for row in equipments)

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "fleet": {
            "tool_count": len(equipments),
            "total_executions": total_execs,
            "align_fail_count": total_align,
            "meas_fail_count": total_meas,
            "align_fail_rate": round(total_align / total_execs, 4) if total_execs else 0.0,
            "meas_fail_rate": round(total_meas / total_execs, 4) if total_execs else 0.0,
            "median_exec_count": float(
                statistics.median([row["exec_count"] for row in equipments])
            ) if equipments else 0.0,
            "median_recipe_count": float(
                statistics.median([row["recipe_count"] for row in equipments])
            ) if equipments else 0.0,
            "min_expected_fails": FAIL_INDEX_MIN_EXPECTED,
            "confidence_z": CONFIDENCE_Z,
            "percentiles": {
                "exec_count": percentile_summary(r["exec_count"] for r in equipments),
                "recipe_count": percentile_summary(r["recipe_count"] for r in equipments),
                "align_fail_rate": percentile_summary(
                    r["align_fail_rate"] for r in equipments
                ),
                "meas_fail_rate": percentile_summary(
                    r["meas_fail_rate"] for r in equipments
                ),
                # None 장비는 제외 — 표본 미달은 "실패하지 않았다"가 아니라
                # "모른다"이고, 0 으로 채우면 p10 이 통째로 무너집니다.
                "align_index": percentile_summary(
                    r["align_index"] for r in equipments if r["align_index"] is not None
                ),
                "meas_index": percentile_summary(
                    r["meas_index"] for r in equipments if r["meas_index"] is not None
                ),
            },
        },
        "equipments": equipments,
    }
```

- [ ] **Step 5: 테스트가 통과하는지 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue/tests/ -q`

Expected: PASS (test_byar 7 + test_shape 10 + 기존 test_contract 전부)

- [ ] **Step 6: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/fail_issue/providers/_shape.py \
        back_dev_home/ebeam/hitachi/fail_issue/contracts.py \
        back_dev_home/ebeam/hitachi/fail_issue/tests/test_shape.py
git commit -m "feat(fail-issue): 장비별 집계 조립기를 더한다

레시피 난이도가 다른 두 레시피를 정반대 비율로 도는 두 장비가 원 실패율은
7% 대 28% 로 갈리면서 지수는 둘 다 정확히 1.0 이 나오는 격자를 테스트로
박았습니다. 이 테스트는 expected 를 '실행수 × 플릿 전체 실패율' 이라는
순진한 식으로 바꾸면 실패합니다 — 지수가 존재하는 이유를 지키는 유일한
테스트입니다."
```

---

### Task 3: 장비 비교 조립기

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/fail_issue/contracts.py`
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/providers/_shape.py`
- Test: `back_dev_home/ebeam/hitachi/fail_issue/tests/test_shape.py`

**Interfaces:**

- Consumes: `recipe_tat.providers._shape.days_in_range` (기존 함수, 재사용).
- Produces:
  - `_shape.TrendGridRow = tuple[str, str, int, int, int]` — `(eqp_id, date, exec_count, align_fails, meas_fails)`
  - `_shape.RecipeGridRow = tuple[str, str, int, int, int]` — `(eqp_id, full_name, exec_count, align_fails, meas_fails)`
  - `_shape.build_equipment_compare_payload(tool_type, fab_names, start_date, end_date, eqp_ids, trend_rows, recipe_rows) -> EquipmentComparePayload`
  - `contracts.EquipmentTrendPoint`, `EquipmentTrendSeries`, `EquipmentRecipeCell`, `EquipmentRecipeRow`, `EquipmentComparePayload`

- [ ] **Step 1: 계약 타입 5개를 `contracts.py` 에 추가**

`EquipmentsPayload` 아래에 붙이고 `__all__` 에 다섯 이름을 추가합니다.

```python
class EquipmentTrendPoint(TypedDict):
    date: str
    exec_count: int
    align_fail_count: int
    meas_fail_count: int


class EquipmentTrendSeries(TypedDict):
    eqp_id: str
    points: list[EquipmentTrendPoint]


class EquipmentRecipeCell(TypedDict):
    eqp_id: str
    exec_count: int
    align_fail_count: int
    meas_fail_count: int


class EquipmentRecipeRow(TypedDict):
    class_name: str
    recipe_name: str
    full_name: str
    # 선택된 장비 전체의 합.
    total_exec_count: int
    total_align_fail_count: int
    total_meas_fail_count: int
    # 선택된 장비 수만큼, 요청 순서 그대로. 그 장비가 이 레시피를 돌지
    # 않았으면 0 으로 채웁니다 — 열이 밀리면 비교표가 거짓말을 합니다.
    cells: list[EquipmentRecipeCell]


class EquipmentComparePayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    # 실제로 사용된 목록(상한 적용 후). 절단을 조용히 하지 않기 위한 에코입니다.
    eqp_ids: list[str]
    trends: list[EquipmentTrendSeries]
    recipes: list[EquipmentRecipeRow]
```

`EquipmentTrendPoint` 는 기존 `DailyTrendPoint` 와 필드가 같지만 **별도
타입으로 둡니다.** 기존 타입은 페이지 전역 추이의 계약이고 이 타입은 장비
단위 추이의 계약이라, 한쪽에 필드를 더할 때 다른 쪽이 따라 움직여야 할
이유가 없습니다. 이 주석을 `EquipmentTrendPoint` 정의 위에 그대로 넣습니다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`test_shape.py` 의 import 에 `build_equipment_compare_payload` 를 더하고,
파일 끝에 아래를 추가합니다.

```python
# --- 비교 payload -----------------------------------------------------------

COMPARE_START, COMPARE_END = "2026-08-01", "2026-08-03"   # 3일


def _compare(eqp_ids, trend_rows, recipe_rows):
    return build_equipment_compare_payload(
        "cd-sem", (FAB,), COMPARE_START, COMPARE_END,
        eqp_ids, trend_rows, recipe_rows,
    )


def test_cells_follow_the_requested_order_and_zero_fill_absentees():
    """열이 밀리면 비교표가 다른 장비의 숫자를 보여줍니다.

    EQ-TWO 는 R/ONLYONE 을 돌지 않았으므로 그 칸이 0 이어야 하고, cells 의
    순서는 요청 순서(EQ-ONE, EQ-TWO)를 그대로 따라야 합니다.
    """
    payload = _compare(
        ["EQ-ONE", "EQ-TWO"],
        [],
        [
            ("EQ-ONE", "R/ONLYONE", 100, 10, 12),
            ("EQ-ONE", "R/SHARED", 50, 5, 6),
            ("EQ-TWO", "R/SHARED", 70, 7, 8),
        ],
    )

    assert payload["eqp_ids"] == ["EQ-ONE", "EQ-TWO"]
    by_name = {row["full_name"]: row for row in payload["recipes"]}

    only = by_name["R/ONLYONE"]
    assert [c["eqp_id"] for c in only["cells"]] == ["EQ-ONE", "EQ-TWO"]
    assert only["cells"][0]["align_fail_count"] == 10
    assert only["cells"][1] == {
        "eqp_id": "EQ-TWO",
        "exec_count": 0,
        "align_fail_count": 0,
        "meas_fail_count": 0,
    }

    shared = by_name["R/SHARED"]
    assert shared["total_exec_count"] == 120
    assert shared["total_align_fail_count"] == 12
    assert shared["total_meas_fail_count"] == 14


def test_full_name_splits_into_class_and_recipe_on_the_first_slash():
    payload = _compare(
        ["EQ-ONE"], [], [("EQ-ONE", "ADI/M1/CD", 10, 1, 1)]
    )
    row = payload["recipes"][0]
    assert row["class_name"] == "ADI"
    assert row["recipe_name"] == "M1/CD"
    assert row["full_name"] == "ADI/M1/CD"


def test_trends_cover_every_day_in_range_even_when_silent():
    """조용한 날을 건너뛰면 x축이 거짓말을 합니다."""
    payload = _compare(
        ["EQ-ONE"],
        [("EQ-ONE", "2026-08-02", 30, 3, 4)],
        [],
    )
    points = payload["trends"][0]["points"]
    assert [p["date"] for p in points] == ["2026-08-01", "2026-08-02", "2026-08-03"]
    assert points[0]["exec_count"] == 0
    assert points[1]["align_fail_count"] == 3
    assert points[2]["meas_fail_count"] == 0


def test_rows_outside_the_selection_are_ignored():
    """범위 밖 장비의 행이 섞여 들어와도 합계를 오염시키면 안 됩니다."""
    payload = _compare(
        ["EQ-ONE"],
        [("EQ-GHOST", "2026-08-02", 999, 99, 99)],
        [("EQ-GHOST", "R/SHARED", 999, 99, 99)],
    )
    assert payload["recipes"] == []
    assert all(p["exec_count"] == 0 for p in payload["trends"][0]["points"])


def test_duplicate_eqp_ids_collapse_while_preserving_order():
    payload = _compare(["EQ-B", "EQ-A", "EQ-B"], [], [])
    assert payload["eqp_ids"] == ["EQ-B", "EQ-A"]


def test_empty_selection_returns_an_empty_payload():
    payload = _compare([], [], [])
    assert payload["eqp_ids"] == []
    assert payload["trends"] == []
    assert payload["recipes"] == []


def test_recipes_sort_by_combined_fails_then_name():
    """백엔드는 활성 탭을 모르므로 두 지표를 합친 결정적 순서만 보장합니다.

    프론트엔드가 활성 aspect 로 다시 정렬하지만, 페이지네이션이 안정적이려면
    백엔드 순서에 동률 파훼가 있어야 합니다.
    """
    payload = _compare(
        ["EQ-ONE"],
        [],
        [
            ("EQ-ONE", "R/LOW", 100, 1, 1),
            ("EQ-ONE", "R/HIGH", 100, 20, 30),
            ("EQ-ONE", "B/TIE", 100, 5, 5),
            ("EQ-ONE", "A/TIE", 100, 5, 5),
        ],
    )
    assert [r["full_name"] for r in payload["recipes"]] == [
        "R/HIGH", "A/TIE", "B/TIE", "R/LOW"
    ]
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue/tests/test_shape.py -q`

Expected: FAIL — `ImportError: cannot import name 'build_equipment_compare_payload'`

- [ ] **Step 4: 최소 구현**

`_shape.py` 의 import 블록에 추가합니다.

```python
from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    CONFIDENCE_Z,
    EquipmentComparePayload,
    EquipmentRecipeRow,
    EquipmentRow,
    EquipmentsPayload,
    FAIL_INDEX_MIN_EXPECTED,
    ToolType,
)
# 날짜 채움 규칙은 recipe_tat 이 이미 갖고 있습니다. 복제하면 두 화면의 x축이
# 서로 다른 날 개수를 그리게 되고, 그 어긋남은 조용합니다.
from back_dev_home.ebeam.hitachi.recipe_tat.providers._shape import days_in_range
```

파일 끝에 추가합니다.

```python
# (eqp_id, date, exec_count, align_fails, meas_fails)
TrendGridRow = tuple[str, str, int, int, int]
# (eqp_id, full_name, exec_count, align_fails, meas_fails)
RecipeGridRow = tuple[str, str, int, int, int]


def build_equipment_compare_payload(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: Sequence[str],
    trend_rows: Sequence[TrendGridRow],
    recipe_rows: Sequence[RecipeGridRow],
) -> EquipmentComparePayload:
    """선택된 장비들의 일별 추이와 레시피별 실패 구성을 한 응답에 담습니다.

    레시피 행은 선택 장비들의 **합집합**이고, 돌지 않은 장비 칸은 0 으로
    채웁니다. 클라이언트가 장비별 응답 여러 개를 조인하면 이 합집합과 0채움을
    매번 다시 만들어야 하고, 한 번 어긋나면 열이 밀려 다른 장비의 숫자를
    보여주게 됩니다.
    """
    selected = list(dict.fromkeys(eqp_ids))     # 순서 보존 dedupe
    if not selected:
        return {
            "tool_type": tool_type,
            "fab_names": list(fab_names or []),
            "start_date": start_date,
            "end_date": end_date,
            "eqp_ids": [],
            "trends": [],
            "recipes": [],
        }

    days = days_in_range(start_date, end_date)
    trend: dict[str, dict[str, dict]] = {
        eqp_id: {
            day: {"exec_count": 0, "align_fail_count": 0, "meas_fail_count": 0}
            for day in days
        }
        for eqp_id in selected
    }
    for eqp_id, day, execs, align_f, meas_f in trend_rows:
        bucket = trend.get(eqp_id, {}).get(day)
        if bucket is not None:
            bucket["exec_count"] += execs
            bucket["align_fail_count"] += align_f
            bucket["meas_fail_count"] += meas_f

    grid: dict[str, dict] = {}
    for eqp_id, full_name, execs, align_f, meas_f in recipe_rows:
        if eqp_id not in trend:
            continue
        # office 문서에는 class_name/recipe_name 이 따로 있지만 격자 키는
        # full_name 하나입니다. full_name = f"{class_name}/{recipe_name}" 이
        # 계약이므로 첫 '/' 로 되살립니다.
        class_name, _, recipe_name = full_name.partition("/")
        recipe = grid.setdefault(full_name, {
            "class_name": class_name,
            "recipe_name": recipe_name,
            "full_name": full_name,
            "total_exec_count": 0,
            "total_align_fail_count": 0,
            "total_meas_fail_count": 0,
            "cells": {
                picked: {"execs": 0, "align": 0, "meas": 0} for picked in selected
            },
        })
        recipe["total_exec_count"] += execs
        recipe["total_align_fail_count"] += align_f
        recipe["total_meas_fail_count"] += meas_f
        cell = recipe["cells"][eqp_id]
        cell["execs"] += execs
        cell["align"] += align_f
        cell["meas"] += meas_f

    # 활성 탭을 백엔드가 모르므로 두 지표의 합으로 정렬하고, 동률은 full_name
    # 으로 파훼합니다. 프론트엔드가 활성 aspect 로 다시 정렬하지만, 이 순서가
    # 결정적이지 않으면 페이지네이션이 흔들립니다.
    ordered = sorted(
        grid.values(),
        key=lambda e: (
            -(e["total_align_fail_count"] + e["total_meas_fail_count"]),
            e["full_name"],
        ),
    )

    recipes: list[EquipmentRecipeRow] = [
        {
            "class_name": entry["class_name"],
            "recipe_name": entry["recipe_name"],
            "full_name": entry["full_name"],
            "total_exec_count": entry["total_exec_count"],
            "total_align_fail_count": entry["total_align_fail_count"],
            "total_meas_fail_count": entry["total_meas_fail_count"],
            "cells": [
                {
                    "eqp_id": eqp_id,
                    "exec_count": entry["cells"][eqp_id]["execs"],
                    "align_fail_count": entry["cells"][eqp_id]["align"],
                    "meas_fail_count": entry["cells"][eqp_id]["meas"],
                }
                for eqp_id in selected
            ],
        }
        for entry in ordered
    ]

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "eqp_ids": selected,
        "trends": [
            {
                "eqp_id": eqp_id,
                "points": [
                    {
                        "date": day,
                        "exec_count": trend[eqp_id][day]["exec_count"],
                        "align_fail_count": trend[eqp_id][day]["align_fail_count"],
                        "meas_fail_count": trend[eqp_id][day]["meas_fail_count"],
                    }
                    for day in days
                ],
            }
            for eqp_id in selected
        ],
        "recipes": recipes,
    }
```

- [ ] **Step 5: 테스트가 통과하는지 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue/tests/ -q`

Expected: PASS (test_shape 17개 포함 전부)

- [ ] **Step 6: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/fail_issue/providers/_shape.py \
        back_dev_home/ebeam/hitachi/fail_issue/contracts.py \
        back_dev_home/ebeam/hitachi/fail_issue/tests/test_shape.py
git commit -m "feat(fail-issue): 장비 비교 조립기를 더한다

합집합·0채움·정렬을 조립기가 소유합니다. 클라이언트가 장비별 응답을
조인하면 이 셋을 매번 다시 만들어야 하고, 한 번 어긋나면 열이 밀려 다른
장비의 숫자를 보여줍니다. 날짜 채움은 recipe_tat 의 days_in_range 를
재사용합니다 — 복제하면 두 화면의 x축이 조용히 갈라집니다."
```

---

### Task 4: mock provider

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/fail_issue/providers/mock.py`

**Interfaces:**

- Consumes: `_shape.build_equipments_payload`, `_shape.build_equipment_compare_payload`
  (Task 2·3), 기존 `mock._filter_rows`, `mock._is_align_fail`, `mock._is_meas_fail`.
- Produces:
  - `mock.get_equipments(tool_type, fab_names, start_date, end_date) -> EquipmentsPayload`
  - `mock.get_equipment_compare(tool_type, fab_names, start_date, end_date, eqp_ids) -> EquipmentComparePayload`

- [ ] **Step 1: import 와 `__all__` 갱신**

`mock.py` 의 contracts import 블록에 다섯 타입을 추가합니다.

```python
from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    AlignOutcome,
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    EquipmentComparePayload,
    EquipmentsPayload,
    FailRow,
    MeasRankingRow,
    MsrCheck,
    SummaryPayload,
)
from back_dev_home.ebeam.hitachi.fail_issue.providers._shape import (
    build_equipment_compare_payload,
    build_equipments_payload,
)
```

`__all__` 에 `"get_equipments"`, `"get_equipment_compare"` 를 추가합니다.

- [ ] **Step 2: 모듈 docstring 에 장비별 뷰가 무엇을 대신하는지 적는다**

`mock.py` 최상단 docstring 의 "사무실 주의사항" 문단 **바로 앞**에 넣습니다.

```text
장비별 뷰(get_equipments / get_equipment_compare)가 흉내내는 것:

이 mock 의 실패는 FAB_ALIGN_FAIL_RATE · FAB_MEAS_FAIL_RATE 라는 **fab 단위
고정 스칼라**에서 나옵니다. 즉 mock 에는 "장비 개체차"가 존재하지 않으며,
같은 fab 안의 장비 지수는 순수하게 표본 변동만으로 흩어집니다. 그래서
집에서는 배지가 켜지는 것을 안정적으로 재현할 수 없습니다 — 지수 산식과
0채움·정렬 같은 **모양**은 여기서 검증되지만, 임계값이 실제로 맞는지는
사무실에서만 알 수 있습니다(OFFICE-VERIFY, MIGRATION.md).

fab 간에는 반대로 3배 차이(0.05~0.15)가 있어서, 여러 fab 을 함께 조회하면
지수가 장비가 아니라 fab 을 가리키는 편향이 즉시 재현됩니다. 프론트엔드가
다중 fab 조회에서 배지를 끄는 이유가 이것입니다.

장비별 편차를 여기에 지어내지 마십시오. 사무실 데이터에 대해 거짓을
가르치게 됩니다.
```

- [ ] **Step 3: 두 함수를 `get_devices` 아래, `if __name__ == "__main__":` 위에 추가**

```python
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
                row["full_name"], 0, 0, 0
            ]
            cell = cells[key]
        cell[4] += 1
        if _is_align_fail(row):
            cell[5] += 1
        if _is_meas_fail(row):
            cell[6] += 1

    return build_equipments_payload(
        tool_type, fab_names, start_date, end_date,
        [tuple(cell) for cell in cells.values()]
    )


def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...]
) -> EquipmentComparePayload:
    """선택된 장비들의 (장비, 날짜) · (장비, 레시피) 두 격자를 만듭니다.

    합집합·0채움·정렬은 전부 공용 조립기가 합니다 — office 어댑터는 같은 두
    격자를 composite 집계로 만들어 같은 조립기를 부릅니다.
    """
    selected = list(dict.fromkeys(eqp_ids))
    if not selected:
        return build_equipment_compare_payload(
            tool_type, fab_names, start_date, end_date, [], [], []
        )

    wanted = set(selected)
    rows = [
        row for row in _filter_rows(tool_type, fab_names, start_date, end_date)
        if row["eqp_id"] in wanted
    ]

    trend_cells: dict[tuple[str, str], list] = {}
    recipe_cells: dict[tuple[str, str], list] = {}
    for row in rows:
        is_align = _is_align_fail(row)
        is_meas = _is_meas_fail(row)
        day = row["timestamp"][:10]

        day_key = (row["eqp_id"], day)
        day_cell = trend_cells.get(day_key)
        if day_cell is None:
            trend_cells[day_key] = [row["eqp_id"], day, 0, 0, 0]
            day_cell = trend_cells[day_key]
        day_cell[2] += 1
        day_cell[3] += int(is_align)
        day_cell[4] += int(is_meas)

        recipe_key = (row["eqp_id"], row["full_name"])
        recipe_cell = recipe_cells.get(recipe_key)
        if recipe_cell is None:
            recipe_cells[recipe_key] = [row["eqp_id"], row["full_name"], 0, 0, 0]
            recipe_cell = recipe_cells[recipe_key]
        recipe_cell[2] += 1
        recipe_cell[3] += int(is_align)
        recipe_cell[4] += int(is_meas)

    return build_equipment_compare_payload(
        tool_type, fab_names, start_date, end_date, selected,
        [tuple(cell) for cell in trend_cells.values()],
        [tuple(cell) for cell in recipe_cells.values()]
    )
```

- [ ] **Step 4: 조립기를 실 데이터로 한 번 돌려 본다**

Run:

```bash
.venv/bin/python -c "
from datetime import timedelta
from back_dev_home.ebeam.hitachi.fail_issue.providers import mock as m
end = m.ANCHOR_TIME.date().isoformat()
start = (m.ANCHOR_TIME - timedelta(days=90)).date().isoformat()
p = m.get_equipments('cd-sem', ('M14A',), start, end)
print('tools', p['fleet']['tool_count'], 'execs', p['fleet']['total_executions'])
for r in p['equipments'][:3]:
    print(r['eqp_id'], r['exec_count'], r['align_fail_count'],
          r['align_expected'], r['align_index'], r['align_index_low'], r['align_index_high'])
c = m.get_equipment_compare('cd-sem', ('M14A',), start, end,
                            tuple(r['eqp_id'] for r in p['equipments'][:2]))
print('trend days', len(c['trends'][0]['points']), 'recipes', len(c['recipes']))
print('cells per row', len(c['recipes'][0]['cells']))
"
```

Expected: 장비 5대, 각 행의 `align_index_low <= align_index <= align_index_high`,
`trend days` 는 91, `cells per row` 는 2.

- [ ] **Step 5: 전체 테스트**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue -q`

Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/fail_issue/providers/mock.py
git commit -m "feat(fail-issue): mock 에 장비별 격자 2종을 더한다

기존 _filter_rows(lru_cache)를 그대로 쓰고 행을 격자로 접기만 합니다.
docstring 에 이 mock 이 흉내내지 **못하는** 것을 적었습니다: 실패가 fab
단위 스칼라에서 나오므로 장비 개체차가 없고, 배지가 실제로 켜지는지는
사무실에서만 알 수 있습니다."
```

---

### Task 5: dispatcher · 라우트 · 계약 테스트

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/fail_issue/data.py`
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/routes.py`
- Test: `back_dev_home/ebeam/hitachi/fail_issue/tests/test_contract.py`

**Interfaces:**

- Consumes: `mock.get_equipments`, `mock.get_equipment_compare` (Task 4),
  `_analytics_routes.resolve_analytics_scope` (기존 — `eqp_ids` 를 이미 파싱하고
  `MAX_EQP_IDS = 5` 로 자릅니다).
- Produces:
  - `data.get_equipments(...)`, `data.get_equipment_compare(...)`
  - `GET /<tool_slug>/fail-issue/equipments`
  - `GET /<tool_slug>/fail-issue/equipment-compare`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`test_contract.py` 의 contracts import 에 세 타입을 추가합니다.

```python
from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    EquipmentComparePayload,
    EquipmentRow,
    EquipmentsPayload,
    MeasRankingRow,
    SummaryPayload,
)
```

파일 끝에 추가합니다.

```python
# --- 장비별 뷰 ---------------------------------------------------------------


def test_equipments_payload_matches_the_contract():
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipments(tool_type, fabs, start, end)

    assert_matches(payload, EquipmentsPayload)
    for row in payload["equipments"]:
        assert_matches(row, EquipmentRow)


def test_each_tool_belongs_to_exactly_one_fab():
    """물리 장비는 fab 하나에 있습니다.

    이게 깨지면 장비별 표에서 한 장비가 여러 행으로 쪼개지고, 지수가 각
    조각의 부분 실행 수로 계산되어 전부 틀립니다.
    """
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipments(tool_type, fabs, start, end)

    seen: dict[str, str] = {}
    for row in payload["equipments"]:
        assert row["eqp_id"] not in seen, row["eqp_id"]
        seen[row["eqp_id"]] = row["fab_name"]


def test_fleet_totals_agree_with_the_rows():
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipments(tool_type, fabs, start, end)
    rows = payload["equipments"]
    fleet = payload["fleet"]

    assert fleet["tool_count"] == len(rows)
    assert fleet["total_executions"] == sum(r["exec_count"] for r in rows)
    assert fleet["align_fail_count"] == sum(r["align_fail_count"] for r in rows)
    assert fleet["meas_fail_count"] == sum(r["meas_fail_count"] for r in rows)


def test_index_and_its_interval_are_present_or_absent_together():
    """셋 중 하나만 None 인 상태는 있을 수 없습니다."""
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipments(tool_type, fabs, start, end)

    for row in payload["equipments"]:
        for aspect in ("align", "meas"):
            triple = (
                row[f"{aspect}_index"],
                row[f"{aspect}_index_low"],
                row[f"{aspect}_index_high"],
            )
            assert all(v is None for v in triple) or all(v is not None for v in triple), row
            if triple[0] is not None:
                assert triple[1] <= triple[0] <= triple[2], row


def test_equipment_compare_payload_matches_the_contract():
    tool_type, fabs, start, end = _default_scope()
    fleet = data.get_equipments(tool_type, fabs, start, end)
    picked = tuple(r["eqp_id"] for r in fleet["equipments"][:3])

    payload = data.get_equipment_compare(tool_type, fabs, start, end, picked)
    assert_matches(payload, EquipmentComparePayload)

    assert payload["eqp_ids"] == list(picked)
    for series in payload["trends"]:
        assert series["eqp_id"] in picked
    for recipe in payload["recipes"]:
        assert [c["eqp_id"] for c in recipe["cells"]] == list(picked)


def test_compare_trends_cover_the_whole_window():
    tool_type, fabs, start, end = _default_scope()
    fleet = data.get_equipments(tool_type, fabs, start, end)
    picked = tuple(r["eqp_id"] for r in fleet["equipments"][:2])
    if not picked:
        pytest.skip("no equipment in scope")

    payload = data.get_equipment_compare(tool_type, fabs, start, end, picked)
    expected_days = DEFAULT_DAYS + 1        # 양 끝 포함
    for series in payload["trends"]:
        assert len(series["points"]) == expected_days


def test_compare_with_no_selection_is_empty_not_everything():
    """빈 선택에 전체 플릿을 돌려주면 화면이 조용히 거짓말을 합니다."""
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipment_compare(tool_type, fabs, start, end, ())
    assert payload["eqp_ids"] == []
    assert payload["trends"] == []
    assert payload["recipes"] == []
```

`import pytest` 가 없으면 파일 상단에 추가합니다.

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue/tests/test_contract.py -q`

Expected: FAIL — `AttributeError: module '...fail_issue.data' has no attribute 'get_equipments'`

- [ ] **Step 3: dispatcher 2개를 `data.py` 에 추가**

contracts import 블록에 두 타입을 추가하고 `__all__` 에 두 이름을 넣은 뒤,
`get_devices` 아래에 붙입니다.

```python
def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> EquipmentsPayload:
    return _provider().get_equipments(tool_type, fab_names, start_date, end_date)


def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...],
) -> EquipmentComparePayload:
    return _provider().get_equipment_compare(
        tool_type, fab_names, start_date, end_date, eqp_ids
    )
```

- [ ] **Step 4: 라우트 2개를 `routes.py` 에 추가**

`data` import 목록에 두 이름을 넣고, 파일 끝에 붙입니다.

```python
@bp.get("/<tool_slug>/fail-issue/equipments")
def fail_issue_equipments(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    # /devices 와 같은 이유로 lot_cd 를 받지 않습니다: 이 엔드포인트는 범위
    # 안에 어떤 장비가 있는지에 대한 진실이라 선택으로 걸러지면 안 됩니다.
    return jsonify(get_equipments(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
    ))


@bp.get("/<tool_slug>/fail-issue/equipment-compare")
def fail_issue_equipment_compare(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    return jsonify(get_equipment_compare(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
        scope.eqp_ids,
    ))
```

- [ ] **Step 5: 테스트가 통과하는지 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue -q`

Expected: PASS

- [ ] **Step 6: HTTP 로 직접 확인 — 특히 5대 절단**

Flask 를 띄웁니다: `.venv/bin/python index.py`

별도 셸에서:

```bash
curl -s -b 'LASTUSER=local-dev' \
  'http://localhost:5050/api/cdsem/fail-issue/equipments?fab_name=M14A' \
  | .venv/bin/python -m json.tool | head -40

# 6개를 보내면 5개로 잘리고, 응답이 그 사실을 에코해야 합니다.
curl -s -b 'LASTUSER=local-dev' \
  'http://localhost:5050/api/cdsem/fail-issue/equipment-compare?fab_name=M14A&eqp_id=A,B,C,D,E,F' \
  | .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["eqp_ids"])'
```

Expected: 첫 응답은 `fleet` 과 `equipments` 를 가진 200. 두 번째는 원소 5개짜리
리스트 (`['A','B','C','D','E']`).

`/api/*` 는 5초에 20요청으로 제한됩니다 — curl 을 반복할 때 간격을 두십시오.

- [ ] **Step 7: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/fail_issue/data.py \
        back_dev_home/ebeam/hitachi/fail_issue/routes.py \
        back_dev_home/ebeam/hitachi/fail_issue/tests/test_contract.py
git commit -m "feat(fail-issue): 장비별 엔드포인트 2개를 연다

resolve_analytics_scope 가 eqp_id 를 이미 파싱하고 5개로 자르므로 요청
파싱 쪽에 새로 만든 것이 없습니다. /equipments 는 /devices 와 같은 이유로
lot_cd 를 받지 않습니다 — 범위 안에 어떤 장비가 있는지에 대한 진실이라
선택으로 걸러지면 안 됩니다."
```

---

### Task 6: office 어댑터 템플릿

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/fail_issue/providers/office_example.py`

**Interfaces:**

- Consumes: `_office_meas_hist.composite_buckets` (다중 소스 지원),
  `_shape.build_equipments_payload`, `_shape.build_equipment_compare_payload`.
- Produces: `office_example.get_equipments`, `office_example.get_equipment_compare`
  — mock 과 동일한 시그니처.

**주의:** `office.py` 를 만들지 마십시오. gitignore 대상입니다.

- [ ] **Step 1: import 와 `__all__` 갱신**

`_office_meas_hist` import 블록에 `EQP_MODEL_CD_KW as _EQP_MODEL_KW` 를
추가하고, `_shape` 의 두 조립기와 격자 타입을 import 합니다.

```python
from back_dev_home.ebeam.hitachi.fail_issue.providers._shape import (
    EquipmentGridRow,
    RecipeGridRow,
    TrendGridRow,
    build_equipment_compare_payload,
    build_equipments_payload,
)
```

`contracts` import 에 `EquipmentComparePayload`, `EquipmentsPayload` 를 넣고,
`__all__` 에 `"get_equipments"`, `"get_equipment_compare"` 를 넣습니다.

- [ ] **Step 2: 모듈 docstring 의 엔드포인트 목록에 두 줄 추가**

기존 `* devices  — composite over ...` 아래에 붙입니다.

```text
* equipments   — composite over (eqp_id, fab_name, eqp_model_cd, full_name);
                 버킷당 doc_count 와 align/meas filter 서브집계 2개.
                 지수·구간·분위수는 _shape 가 파생합니다.
* equipment-compare — 같은 필터에 eqp_id terms 를 더해 두 번 walk:
                 (eqp_id, 날짜)와 (eqp_id, full_name).
```

- [ ] **Step 3: 두 함수를 `get_devices` 아래에 추가**

```python
def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> EquipmentsPayload:
    """장비별 집계. composite 한 번으로 표에 필요한 값이 전부 나옵니다.

    소스가 4개인 이유: fab_name 과 eqp_model_cd 는 eqp_id 에 함수 종속이라
    버킷 수를 곱하지 않고(장비 수 × 레시피 수 그대로), 대신 top_hits 서브집계
    없이 표의 fab/model 열을 채울 수 있습니다. 카티전 폭발이 아니므로
    top_hits 로 "최적화" 하지 마십시오 — 버킷당 문서를 하나씩 더 읽는 쪽이
    비쌉니다.

    지수·구간·중앙값·분위수는 파이썬에서 파생합니다 — mock 과 같은 코드
    경로를 타야 두 provider 의 숫자가 어긋나지 않습니다.

    OFFICE-VERIFY: eqp_model_cd.keyword 의 존재는 미확인입니다. 매핑에 없는
    필드를 composite 소스로 쓰면 **예외가 아니라 빈 버킷**이 나와
    /equipments 가 200 에 빈 표를 돌려줍니다("이 기간에 데이터 없음"과
    구분되지 않습니다). 자세한 대처는 _office_meas_hist.EQP_MODEL_CD_KW
    위의 주석에 있습니다.
    """
    clauses = _filter_clauses(fab_names, start_date, end_date)
    buckets = _composite_buckets(
        _INDEX[tool_type],
        [
            ("eqp", _EQP_KW),
            ("fab", _FAB_KW),
            ("model", _EQP_MODEL_KW),
            ("recipe", _FULL_KW),
        ],
        {
            "align_fails": {"filter": _ALIGN_FAIL_FILTER},
            "meas_fails": {"filter": _MEAS_FAIL_FILTER},
        },
        _query(clauses),
    )

    # 격자 타입은 조립기에서 가져옵니다 — fab 과 model 을, align 과 meas 를
    # 서로 바꿔 넣는 실수가 집에서는 테스트로 잡히지 않는 종류라, 정적
    # 압력이라도 걸어 둡니다.
    grid: list[EquipmentGridRow] = [
        (
            _text(b["key"]["eqp"]),
            _text(b["key"]["fab"]),
            _text(b["key"]["model"]),
            _text(b["key"]["recipe"]),
            int(b["doc_count"]),
            int(b.get("align_fails", {}).get("doc_count") or 0),
            int(b.get("meas_fails", {}).get("doc_count") or 0),
        )
        for b in buckets
    ]
    return build_equipments_payload(
        tool_type, fab_names, start_date, end_date, grid
    )


def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...],
) -> EquipmentComparePayload:
    """선택 장비의 (장비, 날짜)·(장비, 레시피) 두 격자.

    composite 를 두 번 도는 이유: 한 번에 (eqp, 날짜, 레시피) 3중 소스로
    걷으면 버킷 수가 장비 × 일수 × 레시피로 곱해집니다. 90일 × 200레시피
    × 5대면 9만 버킷이고, 그중 대부분이 doc_count 0 입니다. 두 번 도는 쪽이
    싸고, 두 격자의 쓰임이 서로 독립적입니다.
    """
    selected = list(dict.fromkeys(eqp_ids))
    if not selected:
        return build_equipment_compare_payload(
            tool_type, fab_names, start_date, end_date, [], [], []
        )

    clauses = _filter_clauses(fab_names, start_date, end_date)
    # eqp_id 는 정확 일치 키입니다 — 대문자로 정규화하지 않습니다.
    clauses = [*clauses, {"terms": {_EQP_KW: selected}}]

    sub_aggs = {
        "align_fails": {"filter": _ALIGN_FAIL_FILTER},
        "meas_fails": {"filter": _MEAS_FAIL_FILTER},
    }

    day_buckets = _composite_buckets(
        _INDEX[tool_type],
        [
            ("eqp", _EQP_KW),
            # date_histogram 은 composite 소스로 쓸 때 date_histogram 소스가
            # 따로 있지만, 여기서는 날짜를 문자열 키로 받아야 조립기의
            # days_in_range 와 바로 맞물립니다. calendar_interval 1d + UTC
            # 포맷이 mock 의 timestamp[:10] 과 같은 키를 냅니다.
            ("day", _TIME_F),
        ],
        sub_aggs,
        _query(clauses),
    )
    trend_grid: list[TrendGridRow] = [
        (
            _text(b["key"]["eqp"]),
            str(b["key"]["day"])[:10],
            int(b["doc_count"]),
            int(b.get("align_fails", {}).get("doc_count") or 0),
            int(b.get("meas_fails", {}).get("doc_count") or 0),
        )
        for b in day_buckets
    ]

    recipe_buckets = _composite_buckets(
        _INDEX[tool_type],
        [("eqp", _EQP_KW), ("recipe", _FULL_KW)],
        sub_aggs,
        _query(clauses),
    )
    recipe_grid: list[RecipeGridRow] = [
        (
            _text(b["key"]["eqp"]),
            _text(b["key"]["recipe"]),
            int(b["doc_count"]),
            int(b.get("align_fails", {}).get("doc_count") or 0),
            int(b.get("meas_fails", {}).get("doc_count") or 0),
        )
        for b in recipe_buckets
    ]

    return build_equipment_compare_payload(
        tool_type, fab_names, start_date, end_date, selected,
        trend_grid, recipe_grid,
    )
```

**`("day", _TIME_F)` 는 OFFICE-VERIFY 입니다.** `timestamp` 는 date 타입이라
`terms` 소스로 쓰면 epoch millis 가 키로 나올 수 있습니다. 그 경우
`str(...)[:10]` 이 `"17546789"` 같은 문자열이 되어 조립기의 날짜와 하나도
맞지 않고, **예외 없이 추이가 전부 0** 으로 나옵니다. 아래 Step 4 의 주석에
대처를 적습니다.

- [ ] **Step 4: 위 위험을 코드 옆에 못 박는다**

`("day", _TIME_F)` 줄 위의 주석을 아래로 교체합니다.

```python
            # OFFICE-VERIFY — timestamp 는 date 타입이라 terms 소스의 키가
            # epoch millis 로 나올 수 있습니다. 그러면 str(key)[:10] 이
            # "1754678912" 같은 문자열이 되어 days_in_range 의 "2026-08-01"
            # 과 하나도 맞지 않고, **예외 없이 추이가 전부 0** 으로 나옵니다
            # (빈 데이터와 구분되지 않습니다). 사무실에서 첫 호출 시 버킷
            # 키를 눈으로 확인하십시오. millis 라면 이 소스를
            # {"date_histogram": {"field": TIME_FIELD,
            #                     "calendar_interval": "1d",
            #                     "format": "yyyy-MM-dd"}}
            # 로 바꿉니다 — composite 는 date_histogram 소스를 지원하며,
            # format 을 주면 키가 곧바로 "2026-08-01" 입니다.
            ("day", _TIME_F),
```

- [ ] **Step 5: office 템플릿이 적어도 import 되는지 확인**

`importorskip` 로 조용히 건너뛰는 함정을 피하기 위해, 모듈을 직접 로드합니다.

Run:

```bash
.venv/bin/python -c "
import back_dev_home.ebeam.hitachi.fail_issue.providers.office_example as o
for name in ('get_equipments', 'get_equipment_compare'):
    assert hasattr(o, name), name
    assert name in o.__all__, name
import inspect
from back_dev_home.ebeam.hitachi.fail_issue.providers import mock as m
for name in ('get_equipments', 'get_equipment_compare'):
    a = inspect.signature(getattr(o, name))
    b = inspect.signature(getattr(m, name))
    assert list(a.parameters) == list(b.parameters), (name, a, b)
print('office_example OK — signatures match mock')
"
```

Expected: `office_example OK — signatures match mock`

- [ ] **Step 6: 전체 테스트**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS (~2180개). worktree 에는 gitignore 대상 `office.py` 가 없으므로
skip 수가 메인 체크아웃과 다를 수 있습니다 — passed 만 보지 말고
passed+skipped 합계를 비교하십시오.

- [ ] **Step 7: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/fail_issue/providers/office_example.py
git commit -m "feat(fail-issue/office): 장비별 composite 집계 템플릿

버킷당 filter 서브집계 2개로 align/meas 실패를 한 번에 셉니다. 비교는
composite 를 두 번 도는데, (eqp × 날짜 × 레시피) 3중 소스는 90일 200레시피
5대에서 9만 버킷이고 대부분이 doc_count 0 입니다.

날짜 소스가 epoch millis 키를 낼 수 있다는 위험을 코드 옆에 적었습니다 —
그 경우 예외 없이 추이가 전부 0 이 되어 빈 데이터와 구분되지 않습니다."
```

---

### Task 7: 백엔드 문서

**Files:**

- Modify: `docs/api-contracts/fail-issue.yaml`
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/MIGRATION.md`

**Interfaces:**

- Consumes: Task 1–6 이 확정한 payload 모양.
- Produces: 없음 (문서).

- [ ] **Step 1: YAML 계약에 타입과 엔드포인트를 추가**

이 파일은 **OpenAPI 가 아닙니다.** 최상위 키는
`resource` / `description` / `base_path` / `constants` / `types` /
`endpoints` / `notes` 이고, 구조가 다음과 같습니다.

- `types:` — 이름 → 필드 맵. 각 필드는 `type`, 선택적으로 `description`,
  `format`, `enum`, `items`, `examples`.
- `endpoints:` — **리스트**입니다. 각 원소가
  `- path: /api/<tool_slug>/fail-issue/<name>` 로 시작하고
  `method` / `description` / `query_params` / `response` 를 갖습니다.
- `response.body` 는 `types:` 의 이름 하나이거나 인라인 필드 맵입니다.
  기존 `devices` 엔드포인트가 인라인 예시입니다.

`types:` 에 `EquipmentRow` · `FleetReference` · `EquipmentTrendPoint` ·
`EquipmentRecipeCell` · `EquipmentRecipeRow` 를 더하고, `endpoints:` 리스트
끝(= `devices` 항목 뒤, `notes:` 앞)에 두 항목을 더합니다.

설명 문자열에 `:` 가 들어가면 반드시 따옴표로 감쌉니다 — 이 저장소에서
`recipe-tat.yaml` 이 그 이유로 깨진 채 브랜치에 실린 적이 있습니다.
`tests/test_api_contract_yaml.py` 가 그걸 잡습니다.

기록할 항목:

- 두 경로와 쿼리 파라미터(`fab_name`, `start_date`, `end_date`,
  그리고 compare 만 `eqp_id`).
- `/equipments` 가 `lot_cd` 를 받지 **않는다**는 사실.
- `eqp_id` 가 5개로 잘리고 `eqp_ids` 로 에코된다는 사실.
- `EquipmentRow` 의 모든 필드와 스케일:
  `*_fail_rate` 는 0..1 분수, `*_index` 는 비율(1.0 = 기대치), `*_expected`
  는 건수.
- `*_index` · `*_index_low` · `*_index_high` 가 셋 다 null 이거나 셋 다
  값이라는 불변식.
- `min_expected_fails` 와 `confidence_z` 의 의미.

- [ ] **Step 2: 계약 파싱 테스트를 돌린다**

Run: `.venv/bin/python -m pytest tests/test_api_contract_yaml.py tests/test_check_contract.py -q`

Expected: PASS

`test_check_contract.py` 를 함께 도는 이유: 그 파일이
`scripts/capture_fixtures.py` 의 `ENDPOINTS` 로스터를 고정하고 있습니다.
**fail_issue 는 지금 그 로스터에 한 항목도 없고**(`__fixtures__` 디렉터리도
없습니다) 로스터 테스트는 "픽스처가 있는데 목록에 없는 피처"만 잡으므로,
이번 변경으로 깨지지 않습니다. 즉 **이 작업에서 로스터에 손대지 마십시오** —
항목을 추가하려면 실행 중인 Flask 로 픽스처를 캡처해야 하고, 그러면 기존
5개 엔드포인트까지 함께 끌어들이는 별개의 작업이 됩니다. 다만 fail_issue
전체가 shape-drift 가드 밖에 있다는 사실은 MIGRATION.md 에 한 줄로
적어 둡니다(Step 3).

- [ ] **Step 3: `MIGRATION.md` 에 "장비별 뷰" 절을 추가**

기존 절 구조를 따르고, 아래를 반드시 포함합니다.

1. **office 어댑터가 해야 할 일** — `office_example.py` 의 두 함수를 그대로
   가져오고, 격자만 만들고 조립기를 부른다는 규약.
2. **OFFICE-VERIFY 목록** (설계 9절과 같은 내용):
   - `FAIL_INDEX_CEIL = 1.25` / `FAIL_INDEX_FLOOR = 0.75`
     (`front-dev-home/app/utils/failEquipmentSignals.ts`) — 조정 절차는
     설계 9.2절.
   - `eqp_model_cd.keyword` 의 존재 — 없으면 빈 표가 나오고 예외는 없습니다.
   - composite 날짜 소스의 키 형식(문자열이냐 epoch millis 냐).
   - fab 혼합 편향이 사무실에서도 나타나는지.
3. **조정 대상이 아닌 것**: `FAIL_INDEX_MIN_EXPECTED = 1.0` 은 정의의 경계,
   `CONFIDENCE_Z = 1.96` 은 관례입니다.
4. **대조 절차**: `/equipments` 의 `fleet.total_executions` 가
   `/summary` 의 `total_executions` 와 같은지 확인합니다. 다르면 composite
   소스 중 하나가 문서를 떨어뜨리고 있다는 뜻이며, 가장 흔한 원인은
   `eqp_model_cd.keyword` 미존재입니다.
5. **가드 공백 고지**: fail_issue 는 `scripts/capture_fixtures.py` 의
   `ENDPOINTS` 로스터에 **한 항목도 없습니다.** 즉
   `scripts/check_contract.py` 의 mock↔office 형태 대조가 이 피처를 전혀
   보지 않으며, 그 결과는 "문제 0건"으로 읽히지 "검사 안 함"으로 읽히지
   않습니다. 새 두 엔드포인트도 마찬가지입니다. 사무실 스왑 시 형태 대조는
   위 4번 절차를 손으로 하십시오. 로스터 채우기는 기존 5개 엔드포인트까지
   함께 끌어들이는 별개 작업입니다.

- [ ] **Step 4: Markdown lint**

Run (저장소 루트): `npm run lint:md`

Expected: `Summary: 0 error(s)`

- [ ] **Step 5: 커밋**

```bash
git add docs/api-contracts/fail-issue.yaml \
        back_dev_home/ebeam/hitachi/fail_issue/MIGRATION.md
git commit -m "docs(fail-issue): 장비별 엔드포인트 계약과 이관 지침

OFFICE-VERIFY 는 배지 상수 2개와 매핑 가정 2개뿐입니다. 대조 절차를
적었습니다: /equipments 의 총 실행수가 /summary 와 다르면 composite 소스
하나가 문서를 떨어뜨리고 있는 것이고, 가장 흔한 원인은 eqp_model_cd.keyword
미존재입니다 — 이건 예외가 아니라 빈 표로 나타납니다."
```

---

### Task 8: 프론트엔드 API 계층

**Files:**

- Modify: `front-dev-home/app/composables/useFailIssueApi.ts`

**Interfaces:**

- Consumes: Task 5 의 두 엔드포인트.
- Produces:
  - `MAX_COMPARE_EQPS = 5`
  - 타입 `FailIssueEquipmentRow`, `FailIssueFleetReference`,
    `FailIssueEquipmentsResponse`, `FailIssueEquipmentTrendPoint`,
    `FailIssueEquipmentTrendSeries`, `FailIssueEquipmentRecipeCell`,
    `FailIssueEquipmentRecipeRow`, `FailIssueEquipmentCompareResponse`
  - `useFailIssueApi().fetchEquipments(params)`,
    `useFailIssueApi().fetchEquipmentCompare(params)`

- [ ] **Step 1: `FailIssueQuery` 에 `eqpIds` 를 더하고 `buildQuery` 를 확장**

```typescript
export interface FailIssueQuery {
  toolType: FailIssueToolType
  fabNames?: string[]
  startDate?: string
  endDate?: string
  limit?: number
  lotCd?: string
  eqpIds?: string[]
}

const buildQuery = (params: FailIssueQuery) => {
  const query: Record<string, string> = {}
  if (params.startDate) query.start_date = params.startDate
  if (params.endDate) query.end_date = params.endDate
  if (params.fabNames?.length) query.fab_name = params.fabNames.join(',')
  if (params.limit !== undefined) query.limit = String(params.limit)
  if (params.lotCd) query.lot_cd = params.lotCd
  if (params.eqpIds?.length) query.eqp_id = params.eqpIds.join(',')
  return query
}
```

- [ ] **Step 2: 상수와 타입을 추가**

`FailIssueDevicesResponse` 아래에 넣습니다.

```typescript
// 백엔드 _analytics_routes.MAX_EQP_IDS 와 같은 값입니다. 서버가 초과분을
// 자르고 eqp_ids 로 에코하므로 이 상수는 UI 가 미리 막기 위한 것이지
// 신뢰 경계가 아닙니다.
export const MAX_COMPARE_EQPS = 5

export interface FailIssueEquipmentRow {
  eqp_id: string
  fab_name: string
  eqp_model_cd: string
  exec_count: number
  align_fail_count: number
  align_fail_rate: number
  // 이 장비의 레시피 구성이면 나왔어야 할 실패 건수. 지수 툴팁이 씁니다.
  align_expected: number
  // actual / expected. 표시 하한 미만이면 null — "실패하지 않았다"가 아니라
  // "모른다"입니다. 정렬에서도 0 으로 취급하면 안 됩니다.
  align_index: number | null
  align_index_low: number | null
  align_index_high: number | null
  meas_fail_count: number
  meas_fail_rate: number
  meas_expected: number
  meas_index: number | null
  meas_index_low: number | null
  meas_index_high: number | null
  recipe_count: number
  top_recipe: string | null
  top_recipe_share: number
}

export interface FailIssueFleetReference {
  tool_count: number
  total_executions: number
  align_fail_count: number
  meas_fail_count: number
  align_fail_rate: number
  meas_fail_rate: number
  median_exec_count: number
  median_recipe_count: number
  min_expected_fails: number
  confidence_z: number
  percentiles: Record<string, Record<string, number>>
}

export interface FailIssueEquipmentsResponse {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string
  end_date: string
  fleet: FailIssueFleetReference
  equipments: FailIssueEquipmentRow[]
}

export interface FailIssueEquipmentTrendPoint {
  date: string
  exec_count: number
  align_fail_count: number
  meas_fail_count: number
}

export interface FailIssueEquipmentTrendSeries {
  eqp_id: string
  points: FailIssueEquipmentTrendPoint[]
}

export interface FailIssueEquipmentRecipeCell {
  eqp_id: string
  exec_count: number
  align_fail_count: number
  meas_fail_count: number
}

export interface FailIssueEquipmentRecipeRow {
  class_name: string
  recipe_name: string
  full_name: string
  total_exec_count: number
  total_align_fail_count: number
  total_meas_fail_count: number
  // 응답의 eqp_ids 와 같은 순서·같은 길이입니다. 백엔드가 0채움을 보장하므로
  // 인덱스로 바로 꽂아도 됩니다.
  cells: FailIssueEquipmentRecipeCell[]
}

export interface FailIssueEquipmentCompareResponse {
  tool_type: FailIssueToolType
  fab_names: string[]
  start_date: string
  end_date: string
  eqp_ids: string[]
  trends: FailIssueEquipmentTrendSeries[]
  recipes: FailIssueEquipmentRecipeRow[]
}
```

- [ ] **Step 3: fetcher 2개를 추가하고 반환 객체에 넣는다**

`fetchDevices` 아래에 넣고, `return { ... }` 에 두 이름을 추가합니다.

```typescript
  const fetchEquipments = async (
    params: FailIssueQuery
  ): Promise<FailIssueEquipmentsResponse> => {
    // /devices 와 같이 scope 전용입니다 — lot_cd 나 eqp_id 를 넘기면 "범위
    // 안에 어떤 장비가 있는가"라는 이 엔드포인트의 목적이 무너집니다.
    const scope: FailIssueQuery = {
      toolType: params.toolType,
      fabNames: params.fabNames,
      startDate: params.startDate,
      endDate: params.endDate
    }
    return await $fetch<FailIssueEquipmentsResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/equipments`),
      { query: buildQuery(scope) }
    )
  }

  const fetchEquipmentCompare = async (
    params: FailIssueQuery
  ): Promise<FailIssueEquipmentCompareResponse> => {
    return await $fetch<FailIssueEquipmentCompareResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/fail-issue/equipment-compare`),
      { query: buildQuery(params) }
    )
  }
```

- [ ] **Step 4: 타입 검사**

Run (`front-dev-home/` 에서): `npm run typecheck && npm run lint`

Expected: 오류 없음

- [ ] **Step 5: 커밋**

```bash
git add front-dev-home/app/composables/useFailIssueApi.ts
git commit -m "feat(fail-issue): 장비별 응답 타입과 fetcher 2개

fetchEquipments 는 /devices 와 같이 scope 전용이라 lotCd·eqpIds 를
의도적으로 떨어뜨립니다 — 범위 안에 어떤 장비가 있는지에 대한 진실이
현재 선택으로 걸러지면 안 됩니다."
```

---

### Task 9: 배지 판정 정책

**Files:**

- Create: `front-dev-home/app/utils/failEquipmentSignals.ts`
- Test: `front-dev-home/app/utils/failEquipmentSignals.test.ts`

**Interfaces:**

- Consumes: `./equipmentSignals.ts` 의 `isPeerGroupComparable` (기존 — 재사용).
- Produces:
  - `FAIL_INDEX_CEIL`, `FAIL_INDEX_FLOOR`, `SHARE_CEIL`
  - `FAIL_SIGNAL_META: Record<FailSignal, { label: string, tone: 'warn' | 'info' }>`
  - `failEquipmentSignals(row: FailEquipmentSignalInput, percentiles: FailPercentiles): FailSignal[]`
  - `isIndexConclusive(row: FailEquipmentSignalInput): boolean`
  - `isPeerGroupComparable` (재수출)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-dev-home/app/utils/failEquipmentSignals.test.ts`:

```typescript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  FAIL_INDEX_CEIL,
  FAIL_INDEX_FLOOR,
  failEquipmentSignals,
  isIndexConclusive
} from './failEquipmentSignals.ts'

const percentiles = {
  recipe_count: { p10: 4, p25: 8, p50: 12, p75: 18, p90: 24 }
}

const row = (over: Partial<Parameters<typeof failEquipmentSignals>[0]> = {}) => ({
  index: null,
  index_low: null,
  index_high: null,
  recipe_count: 12,
  top_recipe_share: 0.2,
  ...over
})

test('a tool whose interval clears 1.0 and exceeds the ceiling is flagged weak', () => {
  assert.deepEqual(
    failEquipmentSignals(
      row({ index: 1.8, index_low: 1.52, index_high: 2.11 }),
      percentiles
    ),
    ['weak']
  )
})

test('an interval that straddles 1.0 yields no verdict however large the index', () => {
  // 지수만 보면 취약이지만 구간이 1.0 을 걸칩니다 — 잡음과 구별되지 않습니다.
  assert.deepEqual(
    failEquipmentSignals(
      row({ index: 2.4, index_low: 0.88, index_high: 6.1 }),
      percentiles
    ),
    []
  )
})

test('a conclusive interval below the ceiling is still not worth flagging', () => {
  // 구간은 1.0 을 넘겼지만 효과 크기가 작습니다. 통계적 유의와 실무적
  // 중요도는 다른 질문이고, 배지는 둘 다 요구합니다.
  assert.deepEqual(
    failEquipmentSignals(
      row({ index: 1.1, index_low: 1.02, index_high: 1.19 }),
      percentiles
    ),
    []
  )
})

test('a genuinely good tool is flagged healthy', () => {
  assert.deepEqual(
    failEquipmentSignals(
      row({ index: 0.6, index_low: 0.45, index_high: 0.79 }),
      percentiles
    ),
    ['healthy']
  )
})

test('a null index yields neither verdict', () => {
  assert.deepEqual(failEquipmentSignals(row(), percentiles), [])
})

test('narrow coverage is judged on the percentile tail with an inclusive bound', () => {
  // p10 은 nearest-rank 라 언제나 실제 표본값 하나입니다. 엄격 부등호를 쓰면
  // 그 경계를 정의하는 장비 자신이 자기 꼬리에서 빠집니다.
  assert.deepEqual(
    failEquipmentSignals(
      row({ recipe_count: 4, top_recipe_share: 0.5 }),
      percentiles
    ),
    ['narrow']
  )
  assert.deepEqual(
    failEquipmentSignals(
      row({ recipe_count: 5, top_recipe_share: 0.9 }),
      percentiles
    ),
    []
  )
})

test('no percentiles means no coverage verdict', () => {
  assert.deepEqual(
    failEquipmentSignals(row({ recipe_count: 1, top_recipe_share: 1 }), {}),
    []
  )
})

test('a tool can be both weak and narrow', () => {
  assert.deepEqual(
    failEquipmentSignals(
      row({
        index: 1.8, index_low: 1.52, index_high: 2.11,
        recipe_count: 4, top_recipe_share: 0.7
      }),
      percentiles
    ),
    ['weak', 'narrow']
  )
})

test('isIndexConclusive is false exactly when the interval straddles 1.0', () => {
  assert.equal(isIndexConclusive(row({ index: 1.8, index_low: 1.52, index_high: 2.11 })), true)
  assert.equal(isIndexConclusive(row({ index: 0.6, index_low: 0.45, index_high: 0.79 })), true)
  assert.equal(isIndexConclusive(row({ index: 1.2, index_low: 0.9, index_high: 1.6 })), false)
  assert.equal(isIndexConclusive(row()), false)
})

test('the ceiling and floor sit either side of 1.0', () => {
  // 이 둘이 뒤집히면 모든 장비가 두 배지를 동시에 받습니다.
  assert.ok(FAIL_INDEX_FLOOR < 1 && FAIL_INDEX_CEIL > 1)
})
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run (`front-dev-home/` 에서): `npm test`

Expected: FAIL — `Cannot find module './failEquipmentSignals.ts'`

- [ ] **Step 3: 최소 구현**

`front-dev-home/app/utils/failEquipmentSignals.ts`:

```typescript
// 실패 장비별 뷰의 배지 판정. 백엔드는 지수와 그 신뢰구간을 계산하고,
// 여기서는 "이 값을 경고로 볼 것인가"라는 표시 정책만 결정합니다.
//
// 판정이 **구간 AND 상수**인 이유 — 두 조건이 서로 다른 질문에 답합니다.
//
//  - 구간 조건(`low > 1` / `high < 1`)은 "잡음과 구별되는가"입니다. 이 지수는
//    드문 사건의 건수비라 잡음이 1/√λ 입니다. 기대 실패가 5건인 장비는 완전히
//    건강해도 지수가 0.55~1.45 사이에서 흔들리므로, 점추정값만 보면 배지가
//    동전 던지기가 됩니다(설계 3.2절의 실측표).
//  - 상수 조건은 "볼 가치가 있을 만큼 큰가"입니다. 바쁜 장비는 구간이 아주
//    좁아져서 1.03 도 통계적으로는 유의해지는데, 3 % 차이로 사람을 부르지는
//    않습니다.
//
// 앞의 것은 통계가 답하고 뒤의 것은 사람이 정합니다. 그래서 상수만
// OFFICE-VERIFY 입니다.

// 또래 집단 판정은 recipe_tat 과 논거가 동일하므로 그 파일에서 재사용합니다.
// 복제하면 한쪽만 고쳐지는 날이 옵니다 — 그 함수 위의 긴 주석이 왜 여러 fab
// 에서 배지를 끄는지 설명합니다.
export { isPeerGroupComparable } from './equipmentSignals.ts'

export interface FailEquipmentSignalInput {
  index: number | null
  index_low: number | null
  index_high: number | null
  recipe_count: number
  top_recipe_share: number
}

// 백엔드 fleet.percentiles: { metric: { p10..p90 } }. 빈 dict 은
// "판단 근거 없음"이고, 그 경우 배지를 달지 않습니다.
export type FailPercentiles = Record<string, Record<string, number>>

export type FailSignal = 'weak' | 'healthy' | 'narrow'

// OFFICE-VERIFY — 사무실 실 분포를 보기 전까지는 자리표시자입니다. 다만
// recipe_tat 의 상수들과 성격이 다릅니다: 이 둘은 잡음 방어선이 아니라
// **업무 판단**입니다("얼마나 나빠야 사람이 움직이는가"). 잡음 방어는
// 구간이 이미 하고 있으므로, 이 값을 잘못 잡아도 배지가 잡음에 켜지지는
// 않습니다 — 너무 적게 켜지거나 너무 많이 켜질 뿐입니다.
// 조정 절차는 설계 문서 9절.
export const FAIL_INDEX_CEIL = 1.25
export const FAIL_INDEX_FLOOR = 0.75

// equipmentSignals.ts 의 같은 이름과 같은 의미이므로 같은 값입니다.
export const SHARE_CEIL = 0.50

export const FAIL_SIGNAL_META: Record<FailSignal, { label: string, tone: 'warn' | 'info' }> = {
  weak: { label: '취약', tone: 'warn' },
  narrow: { label: '편중', tone: 'warn' },
  healthy: { label: '양호', tone: 'info' }
}

const at = (
  percentiles: FailPercentiles,
  metric: string,
  key: string
): number | null => {
  const value = percentiles?.[metric]?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

/** 구간이 1.0 의 한쪽에 완전히 있는가. false 면 표에서 지수를 죽여 그립니다. */
export const isIndexConclusive = (row: FailEquipmentSignalInput): boolean => {
  if (row.index_low === null || row.index_high === null) return false
  return row.index_low > 1 || row.index_high < 1
}

export const failEquipmentSignals = (
  row: FailEquipmentSignalInput,
  percentiles: FailPercentiles
): FailSignal[] => {
  const signals: FailSignal[] = []

  // index === null 은 표본 미달입니다. "실패하지 않았다"가 아니라 "모른다"
  // 이므로 어느 쪽으로도 판정하지 않습니다.
  if (row.index !== null && row.index_low !== null && row.index_high !== null) {
    if (row.index_low > 1 && row.index > FAIL_INDEX_CEIL) {
      signals.push('weak')
    }
    if (row.index_high < 1 && row.index < FAIL_INDEX_FLOOR) {
      signals.push('healthy')
    }
  }

  // 꼬리 비교는 포함 부등호입니다. percentile_summary 는 nearest-rank 라 p10
  // 이 항상 실제 표본 값 하나와 같고, 작은 플릿에서는 그 표본이 곧 최솟값
  // 자신입니다. 엄격 부등호를 쓰면 경계를 정의하는 장비 자신이 자기 꼬리에
  // 들지 못해, 정확히 배지를 달아야 할 가장 극단적인 장비가 구조적으로
  // 제외됩니다. recipe_count 는 정수라 플릿이 커져도 동률이 사라지지
  // 않으므로 이는 상시적인 문제입니다.
  const coverageTail = at(percentiles, 'recipe_count', 'p10')
  if (
    coverageTail !== null
    && row.recipe_count <= coverageTail
    && row.top_recipe_share >= SHARE_CEIL
  ) {
    signals.push('narrow')
  }

  return signals
}
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run (`front-dev-home/` 에서): `npm test && npm run typecheck && npm run lint`

Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add front-dev-home/app/utils/failEquipmentSignals.ts \
        front-dev-home/app/utils/failEquipmentSignals.test.ts
git commit -m "feat(fail-issue): 장비 배지 판정을 더한다

구간 AND 상수입니다. 구간은 '잡음과 구별되는가', 상수는 '볼 가치가 있는가'
라는 서로 다른 질문에 답하며, 지수 2.4 라도 구간이 1.0 을 걸치면 배지가
없습니다. isPeerGroupComparable 은 equipmentSignals.ts 에서 재수출합니다 —
복제하면 한쪽만 고쳐지는 날이 옵니다."
```

---

### Task 10: 플릿 표 컴포넌트

**Files:**

- Create: `front-dev-home/app/components/ebeam/FailIssueFleetTable.vue`

**Interfaces:**

- Consumes: `FailIssueEquipmentRow` (Task 8), `failEquipmentSignals` ·
  `isIndexConclusive` · `FAIL_SIGNAL_META` (Task 9), `formatRate` (기존).
- Produces: 컴포넌트 `<EbeamFailIssueFleetTable>`
  - props: `rows`, `percentiles`, `peerGroupComparable`, `selected`,
    `maxSelected`, `section`
  - emits: `update:selected` (`string[]`)

- [ ] **Step 1: 컴포넌트를 만든다**

```vue
<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="sk-title">
          장비 목록
        </h3>
        <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
          {{ filteredRows.length.toLocaleString() }} / {{ rows.length.toLocaleString() }}
        </span>
        <span class="sk-meta">
          {{ selected.length }} / {{ maxSelected }}대 선택
        </span>
      </div>
      <div class="flex items-center gap-2">
        <UInput
          v-model="search"
          size="xs"
          placeholder="eqp_id / model 검색…"
          icon="i-lucide-search"
          class="w-[14rem]"
        />
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          label="선택 해제"
          :disabled="selected.length === 0"
          @click="emit('update:selected', [])"
        />
      </div>
    </div>

    <p
      v-if="!peerGroupComparable"
      class="mb-3 flex items-start gap-1.5 sk-meta"
    >
      <UIcon
        name="i-lucide-info"
        class="mt-px h-3.5 w-3.5 shrink-0"
      />
      <span>
        조회 결과가 두 개 이상의 fab에 걸쳐 있습니다. fab마다 실패율 기저가
        달라 신호 배지는 표시하지 않고, fail index 열도 fab을 섞은 기준선으로
        계산됩니다 — 이 열로 정렬하면 장비가 아니라 fab이 줄세워집니다.
        장비끼리 비교하려면 fab을 하나만 선택하십시오.
      </span>
    </p>

    <UTable
      v-model:sorting="sorting"
      :columns="columns"
      :data="sortedRows"
      :sorting-options="sortingOptions"
      sticky="header"
      :ui="tableUi"
    >
      <template
        v-for="id in sortableColumnIds"
        :key="id"
        #[`${id}-header`]="{ column }"
      >
        <UTooltip :text="headerTooltip(id)">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ column.columnDef.header }}
          </UButton>
        </UTooltip>
      </template>

      <template #pick-cell="{ row }">
        <UCheckbox
          :model-value="selected.includes(row.original.eqp_id)"
          :disabled="!selected.includes(row.original.eqp_id) && selected.length >= maxSelected"
          @update:model-value="toggle(row.original.eqp_id)"
        />
      </template>

      <template #fail_count-cell="{ row }">
        {{ failCount(row.original).toLocaleString() }}
      </template>

      <template #fail_rate-cell="{ row }">
        {{ formatRate(failRate(row.original)) }}
      </template>

      <template #fail_index-cell="{ row }">
        <span
          v-if="indexOf(row.original) === null"
          class="text-(--sk-ink-muted)"
        >—</span>
        <UTooltip
          v-else
          :text="indexTooltip(row.original)"
        >
          <!-- 구간이 1.0 을 걸치면 값을 죽여 그립니다. 배지가 없는 이유를
               표 안에서 바로 읽을 수 있어야 합니다. -->
          <span :class="conclusive(row.original) ? '' : 'text-(--sk-ink-muted)'">
            {{ indexOf(row.original)!.toFixed(2) }}
          </span>
        </UTooltip>
      </template>

      <template #signals-cell="{ row }">
        <span
          v-if="!peerGroupComparable"
          class="text-(--sk-ink-muted)"
        >—</span>
        <div
          v-else
          class="flex flex-wrap gap-1"
        >
          <span
            v-for="signal in signalsFor(row.original)"
            :key="signal"
            class="inline-flex h-5 items-center rounded px-1.5 text-[10px] font-medium ring-1"
            :class="FAIL_SIGNAL_META[signal].tone === 'warn'
              ? 'bg-(--sk-warn-soft) text-(--sk-warn) ring-(--sk-warn-border)'
              : 'bg-(--sk-muted-surface) text-(--sk-ink-muted) ring-(--sk-border-soft)'"
          >
            {{ FAIL_SIGNAL_META[signal].label }}
          </span>
        </div>
      </template>
    </UTable>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import {
  formatRate,
  type FailIssueEquipmentRow
} from '~/composables/useFailIssueApi'
import {
  FAIL_SIGNAL_META,
  failEquipmentSignals,
  isIndexConclusive,
  type FailPercentiles
} from '~/utils/failEquipmentSignals'

const props = defineProps<{
  rows: FailIssueEquipmentRow[]
  percentiles: FailPercentiles
  // 또래 집단이 한 fab으로 이루어져 있는가. false면 배지를 하나도 달지
  // 않습니다 — 섞인 fab에서 배지는 장비가 아니라 fab을 가리킵니다
  // (근거는 utils/equipmentSignals.ts의 isPeerGroupComparable 위 주석).
  peerGroupComparable: boolean
  selected: string[]
  maxSelected: number
  // 어느 실패 축을 그릴지. 응답은 두 축을 다 담고 있고 열만 갈아 끼웁니다.
  section: 'align' | 'meas'
}>()

const emit = defineEmits<{ 'update:selected': [string[]] }>()

const search = ref('')

// section 별 필드 접근자. 문자열 인덱싱을 한 곳에 가둬서 열 정의·정렬·
// 툴팁이 서로 다른 축을 읽는 사고를 막습니다.
const failCount = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_count : row.meas_fail_count
const failRate = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_rate : row.meas_fail_rate
const expectedOf = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_expected : row.meas_expected
const indexOf = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_index : row.meas_index
const indexLow = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_index_low : row.meas_index_low
const indexHigh = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_index_high : row.meas_index_high

const signalInput = (row: FailIssueEquipmentRow) => ({
  index: indexOf(row),
  index_low: indexLow(row),
  index_high: indexHigh(row),
  recipe_count: row.recipe_count,
  top_recipe_share: row.top_recipe_share
})

const conclusive = (row: FailIssueEquipmentRow) => isIndexConclusive(signalInput(row))

const signalsFor = (row: FailIssueEquipmentRow) =>
  props.peerGroupComparable
    ? failEquipmentSignals(signalInput(row), props.percentiles)
    : []

// 배지가 켜진(또는 안 켜진) 근거를 사용자가 스스로 확인할 수 있어야 합니다.
// 숫자 하나만 던지고 근거를 숨기면 사용자는 배지를 믿지 않거나, 더 나쁘게는
// 근거 없이 믿습니다.
const indexTooltip = (row: FailIssueEquipmentRow) => {
  const low = indexLow(row)
  const high = indexHigh(row)
  const base = `실제 ${failCount(row).toLocaleString()}건 / 기대 ${expectedOf(row).toFixed(1)}건`
  if (low === null || high === null) return base
  const ci = `95 % CI ${low.toFixed(2)} ~ ${high.toFixed(2)}`
  return conclusive(row)
    ? `${base} · ${ci}`
    : `${base} · ${ci} — 구간이 1.00을 걸쳐 잡음과 구별되지 않습니다.`
}

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter(row =>
    row.eqp_id.toLowerCase().includes(q)
    || row.eqp_model_cd.toLowerCase().includes(q)
    || row.fab_name.toLowerCase().includes(q))
})

const sortableColumnIds = [
  'exec_count', 'fail_count', 'fail_rate', 'fail_index', 'recipe_count'
] as const
type SortableColumnId = typeof sortableColumnIds[number]

// fail index 는 간접표준화 지표라 열 이름만으로는 읽히지 않습니다. 설명이
// 없으면 1.31을 "31 % 실패"로 읽습니다 — 실제로는 "기대치보다 31 % 더 실패"
// 입니다.
const FAIL_INDEX_HEADER_TOOLTIP
  = '실제 실패 건수 ÷ 이 장비의 레시피 구성이면 나왔어야 할 건수. '
    + '1.00보다 크면 같은 일감에서 평균보다 더 실패했다는 뜻입니다. '
    + '값이 흐린 장비는 신뢰구간이 1.00을 걸쳐 판단을 보류한 것입니다.'

// 여러 fab을 함께 조회하면 기준선이 fab을 섞어 계산됩니다. 배지와 달리 값을
// 지우지는 않습니다 — 같은 fab 안에서는 여전히 유효하기 때문입니다. 대신
// 경고를 정렬하려고 누르는 바로 그 헤더에 답니다. 표 위 문단만으로는
// 정렬하는 순간 손이 닿는 곳에 경고가 없습니다.
const FAIL_INDEX_MIXED_FAB_TOOLTIP
  = '여러 fab을 함께 조회 중입니다. 기준선이 fab을 섞어 계산되어, 이 열로 '
    + '정렬하면 장비가 아니라 fab이 줄세워집니다.'

const headerTooltip = (id: SortableColumnId) => {
  if (id !== 'fail_index') return undefined
  return props.peerGroupComparable
    ? FAIL_INDEX_HEADER_TOOLTIP
    : FAIL_INDEX_MIXED_FAB_TOOLTIP
}

const sorting = ref<SortingState>([{ id: 'fail_count', desc: true }])

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

// `manualSorting: true` 가 없으면 아래 정렬은 **죽은 코드**입니다. UTable 은
// 언제나 `getSortedRowModel()` 을 설치하므로, 우리가 정렬해 넘긴 배열을
// TanStack 이 자기 `sortingFns.basic` 으로 다시 정렬합니다. 그리고
// `compareBasic(null, x)` 는 -1 이라 null 이 가장 작은 값이 되고
// (`sortUndefined` 는 `undefined` 에만 걸려 `null` 에는 적용되지 않습니다),
// fail index 오름차순에서 표본 미달 장비가 전부 맨 위로 올라옵니다 —
// "판단할 수 없음"이 "가장 건강한 장비"로 읽히는, 표시 하한이 막으려던 바로
// 그 오독입니다. 내림차순은 우연히 같은 답이 나와 눈에 띄지 않습니다.
const sortingOptions = {
  enableMultiSort: false,
  enableSortingRemoval: false,
  manualSorting: true
}

const sortValue = (row: FailIssueEquipmentRow, id: SortableColumnId): number | null => {
  if (id === 'exec_count') return row.exec_count
  if (id === 'recipe_count') return row.recipe_count
  if (id === 'fail_count') return failCount(row)
  if (id === 'fail_rate') return failRate(row)
  return indexOf(row)
}

const sortedRows = computed(() => {
  const current = sorting.value[0]
  if (!current) return filteredRows.value
  const id = current.id as SortableColumnId
  const dir = current.desc ? -1 : 1
  // index가 null인 행은 정렬 방향과 무관하게 항상 맨 뒤로 보냅니다 —
  // '모른다'를 0으로 취급하면 표본 미달 장비가 최상위/최하위로 몰립니다.
  return [...filteredRows.value].sort((a, b) => {
    const av = sortValue(a, id)
    const bv = sortValue(b, id)
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1
    return (av - bv) * dir
  })
})

const toggle = (eqpId: string) => {
  if (props.selected.includes(eqpId)) {
    emit('update:selected', props.selected.filter(id => id !== eqpId))
    return
  }
  if (props.selected.length >= props.maxSelected) return
  emit('update:selected', [...props.selected, eqpId])
}

const failLabel = computed(() => props.section === 'align' ? 'align fail' : 'meas fail')

const columns = computed<TableColumn<FailIssueEquipmentRow>[]>(() => [
  { id: 'pick', header: '', size: 44 },
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 120 },
  { accessorKey: 'fab_name', header: 'fab', size: 72 },
  { accessorKey: 'eqp_model_cd', header: 'model', size: 100 },
  {
    accessorKey: 'exec_count',
    header: '실행수',
    size: 88,
    cell: ({ row }) => row.original.exec_count.toLocaleString()
  },
  { id: 'fail_count', header: failLabel.value, size: 96 },
  { id: 'fail_rate', header: 'fail율', size: 88 },
  { id: 'fail_index', header: 'fail index', size: 104 },
  { accessorKey: 'recipe_count', header: '레시피수', size: 88 },
  { id: 'signals', header: '신호', size: 140 }
])

// 행 hover는 zinc 스케일을 직접 쓰는 두 곳 중 하나로 허용됩니다(DESIGN.md).
// 헤더에는 배경이 필요 없습니다: sticky 헤더가 이미 테마 surface 위에 앉아
// 있어서, 여기에 tint를 주면 더 차가운 두 번째 카드가 하나 더 생길 뿐입니다.
const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 sk-label'
}
</script>
```

- [ ] **Step 2: 타입·린트 검사**

Run (`front-dev-home/` 에서): `npm run typecheck && npm run lint`

Expected: 오류 없음

- [ ] **Step 3: 커밋**

```bash
git add front-dev-home/app/components/ebeam/FailIssueFleetTable.vue
git commit -m "feat(fail-issue): 장비 플릿 표

section 별 필드 접근자를 함수 6개로 가둬서 열 정의·정렬·툴팁이 서로 다른
축을 읽는 사고를 막습니다. manualSorting: true 가 없으면 정렬 비교자가
죽은 코드가 되고, TanStack 의 compareBasic 이 null 을 최솟값으로 취급해
'판단할 수 없음' 장비가 '가장 건강한 장비' 자리에 올라옵니다."
```

---

### Task 11: 비교 패널 컴포넌트

**Files:**

- Create: `front-dev-home/app/components/ebeam/FailIssueEquipmentCompare.vue`

**Interfaces:**

- Consumes: `useFailIssueApi().fetchEquipmentCompare` (Task 8),
  `usePagedRows` (기존), `useEchart` · `useEchartsTheme` (기존).
- Produces: 컴포넌트 `<EbeamFailIssueEquipmentCompare>`
  - props: `toolType`, `fabs`, `dateRange`, `eqpIds`, `rows`, `section`

- [ ] **Step 1: 컴포넌트를 만든다**

```vue
<template>
  <div class="space-y-3">
    <!-- 선택 요약: 플릿 표에서 이미 받은 행으로 계산하므로 추가 요청 없음 -->
    <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-[var(--sk-r-card)] px-3.5 py-2.5">
      <span
        v-for="row in rows"
        :key="row.eqp_id"
        class="inline-flex h-7 items-center gap-2 rounded-md px-2.5 text-[11px] ring-1 ring-(--sk-border-soft)"
      >
        <span
          class="h-2 w-2 rounded-full"
          :style="{ backgroundColor: colorByEqpId.get(row.eqp_id) }"
        />
        <span class="font-mono font-semibold text-(--sk-ink)">{{ row.eqp_id }}</span>
        <span class="text-(--sk-ink-muted)">
          {{ row.exec_count.toLocaleString() }} runs ·
          {{ chipFailCount(row).toLocaleString() }} fails ·
          {{ formatRate(chipFailRate(row)) }}
        </span>
      </span>
    </div>

    <!-- 선택이 바뀌면 이전 선택의 차트/열을 계속 보여주는 대신 로딩으로
         바꿉니다. mock 에서는 즉시라 눈에 띄지 않지만, office 는 composite
         집계라 초 단위입니다 — 그 사이 화면에 남는 숫자는 지금 체크된
         장비의 것이 아닙니다. 위의 선택 요약 칩은 플릿 표 행(props)에서
         나오므로 요청과 무관하게 즉시 맞고, 그래서 로딩 밖에 둡니다. -->
    <AppLoadingState
      v-if="status === 'pending'"
      title="장비 비교 데이터를 불러오는 중입니다."
    />

    <template v-else>
      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-trending-up"
                class="h-4 w-4 text-(--sk-ink-muted)"
              />
              <h3 class="sk-title">
                장비별 일별 {{ aspectLabel }}
              </h3>
            </div>
            <div
              role="radiogroup"
              aria-label="추이 지표"
              class="inline-flex items-center gap-0.5 rounded-md bg-zinc-100/80 p-0.5 dark:bg-zinc-800/70"
            >
              <button
                v-for="metric in TREND_METRICS"
                :key="metric.value"
                type="button"
                role="radio"
                :aria-checked="trendMetric === metric.value"
                class="inline-flex h-7 items-center gap-1.5 rounded px-2.5 text-xs font-semibold transition-colors"
                :class="trendMetric === metric.value
                  ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-50'
                  : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
                @click="trendMetric = metric.value"
              >
                {{ metric.label }}
              </button>
            </div>
          </div>
        </template>
        <div
          ref="trendEl"
          class="h-[360px] w-full"
        />
      </UCard>

      <div class="dashboard-surface rounded-[var(--sk-r-card)] px-3.5 py-3">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <h3 class="sk-title">
            레시피별 fail 비교
          </h3>
          <span class="sk-meta">
            선택 장비들이 돈 레시피의 합집합입니다. 돌지 않은 장비는 —로 표시됩니다.
          </span>
        </div>

        <UTable
          :columns="columns"
          :data="pagedRecipes"
          sticky="header"
          :ui="tableUi"
        />

        <div class="mt-2 flex items-center justify-between text-xs text-(--sk-ink-muted)">
          <span class="tabular-nums">
            {{ pageStart }}–{{ pageEnd }} of {{ sortedRecipes.length.toLocaleString() }}
          </span>
          <div class="flex gap-1">
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-chevron-left"
              :disabled="currentPage <= 1"
              @click="currentPage -= 1"
            />
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              trailing-icon="i-lucide-chevron-right"
              :disabled="currentPage >= pageCount"
              @click="currentPage += 1"
            />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TableColumn } from '@nuxt/ui'
import {
  formatRate,
  useFailIssueApi,
  type FailIssueEquipmentRecipeRow,
  type FailIssueEquipmentRow,
  type FailIssueToolType
} from '~/composables/useFailIssueApi'

const props = defineProps<{
  toolType: FailIssueToolType
  fabs: string[]
  dateRange: { start: string, end: string }
  eqpIds: string[]
  rows: FailIssueEquipmentRow[]
  section: 'align' | 'meas'
}>()

const { fetchEquipmentCompare } = useFailIssueApi()
const { palette } = useEchartsTheme()

const aspectLabel = computed(() => props.section === 'align' ? 'Align fail' : 'Meas fail')

const TREND_METRICS = [
  { value: 'count', label: '개수' },
  { value: 'rate', label: '비율' }
] as const
type TrendMetric = typeof TREND_METRICS[number]['value']

const trendMetric = ref<TrendMetric>('count')

const chipFailCount = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_count : row.meas_fail_count
const chipFailRate = (row: FailIssueEquipmentRow) =>
  props.section === 'align' ? row.align_fail_rate : row.meas_fail_rate

// 칩 점 색과 트렌드 라인 색이 같은 eqp_id에 대해 어긋나지 않도록 하나의
// 인덱스에서만 파생시킵니다. eqpIds(요청 순서)가 정준입니다 — API가 이
// 순서 그대로 trends.eqp_id를 echo하고, rows(플릿 표 순서로 필터된
// selectedRows)는 클릭 순서와 다를 수 있어 그 자체로는 색 소스가 될 수
// 없습니다.
const colorByEqpId = computed(() => new Map(
  props.eqpIds.map((id, index) => [id, palette.value[index % palette.value.length]])
))

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: props.dateRange.start || undefined,
  endDate: props.dateRange.end || undefined,
  eqpIds: props.eqpIds
}))

// 선택 순서가 캐시 키를 흔들지 않도록 정렬해서 넣습니다 — 같은 3대를
// 다른 순서로 고르면 같은 데이터입니다. section 은 키에 넣지 않습니다:
// 응답이 두 축을 다 담고 있어 탭을 오가도 같은 데이터입니다.
const cacheKey = computed(
  () => `fail-issue-compare:${props.toolType}:${props.fabs.join(',') || 'ALL'}`
    + `:${props.dateRange.start || 'auto'}:${props.dateRange.end || 'auto'}`
    + `:${[...props.eqpIds].sort().join(',')}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  () => fetchEquipmentCompare(queryParams.value),
  { watch: [cacheKey] }
)

const trends = computed(() => data.value?.trends ?? [])
const recipes = computed(() => data.value?.recipes ?? [])

const cellFails = (cell: { align_fail_count: number, meas_fail_count: number }) =>
  props.section === 'align' ? cell.align_fail_count : cell.meas_fail_count

const rowTotalFails = (row: FailIssueEquipmentRecipeRow) =>
  props.section === 'align' ? row.total_align_fail_count : row.total_meas_fail_count

// 백엔드는 활성 탭을 모르므로 두 지표의 합으로 정렬해 보냅니다. 여기서
// 활성 축 기준으로 다시 정렬합니다 — 백엔드 순서가 결정적이라 이 정렬도
// 안정적입니다.
const sortedRecipes = computed(
  () => [...recipes.value].sort((a, b) => rowTotalFails(b) - rowTotalFails(a))
)

// 트렌드 오버레이

const trendEl = ref<HTMLDivElement | null>(null)

const seriesValues = (points: { exec_count: number, align_fail_count: number, meas_fail_count: number }[]) =>
  points.map((point) => {
    const fails = props.section === 'align' ? point.align_fail_count : point.meas_fail_count
    if (trendMetric.value === 'count') return fails
    // 비율은 프론트에서 계산합니다 — 백엔드가 이미 분자와 분모를 다
    // 내려주므로 세 번째 필드를 추가할 이유가 없습니다.
    return point.exec_count > 0 ? Number((fails / point.exec_count * 100).toFixed(2)) : 0
  })

const trendOption = computed<EChartsOption>(() => {
  const dates = trends.value[0]?.points.map(point => point.date) ?? []
  const isRate = trendMetric.value === 'rate'
  return {
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      textStyle: { fontSize: 10 },
      data: trends.value.map(series => series.eqp_id)
    },
    grid: { left: 8, right: 24, top: 32, bottom: 28, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        fontSize: 10,
        interval: Math.max(0, Math.floor(dates.length / 8) - 1)
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 10,
        formatter: isRate ? '{value}%' : '{value}'
      }
    },
    // areaStyle을 쓰지 않습니다: 다중 시리즈에 채움을 주면 hover 시 blur가
    // 채움을 지워서 화면이 깨진 것처럼 보입니다.
    series: trends.value.map(series => ({
      type: 'line' as const,
      name: series.eqp_id,
      smooth: true,
      showSymbol: false,
      itemStyle: { color: colorByEqpId.value.get(series.eqp_id) },
      lineStyle: { color: colorByEqpId.value.get(series.eqp_id) },
      data: seriesValues(series.points)
    }))
  }
})

useEchart(trendEl, trendOption, { exportName: 'equipment-fail-trend' })

// 레시피 매트릭스

const PAGE_SIZE = 25
const currentPage = ref(1)
watch([cacheKey, () => props.section], () => {
  currentPage.value = 1
})

const {
  pageCount, pageStart, pageEnd, pagedRows: pagedRecipes
} = usePagedRows(sortedRecipes, PAGE_SIZE, currentPage)

// 열은 응답의 eqp_ids 순서를 그대로 따릅니다. cells가 같은 순서로 0채움되어
// 오므로 인덱스로 바로 꽂습니다 — 백엔드가 길이를 보장합니다.
const columns = computed<TableColumn<FailIssueEquipmentRecipeRow>[]>(() => [
  { accessorKey: 'full_name', header: 'full name', size: 240 },
  {
    id: 'total_fails',
    header: '합계',
    size: 90,
    cell: ({ row }) => rowTotalFails(row.original).toLocaleString()
  },
  ...(data.value?.eqp_ids ?? []).map((eqpId, index) => ({
    id: `eqp-${eqpId}`,
    header: eqpId,
    size: 160,
    cell: ({ row }: { row: { original: FailIssueEquipmentRecipeRow } }) => {
      const cell = row.original.cells[index]
      if (!cell || cell.exec_count === 0) return '—'
      const fails = cellFails(cell)
      return `${fails.toLocaleString()}/${cell.exec_count.toLocaleString()}`
        + ` (${formatRate(fails / cell.exec_count)})`
    }
  }))
])

// 헤더에 배경을 주지 않는 이유는 FailIssueFleetTable.vue의 같은 블록에 있습니다.
const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 sk-label'
}
</script>
```

- [ ] **Step 2: 타입·린트 검사**

Run (`front-dev-home/` 에서): `npm run typecheck && npm run lint`

Expected: 오류 없음

- [ ] **Step 3: 커밋**

```bash
git add front-dev-home/app/components/ebeam/FailIssueEquipmentCompare.vue
git commit -m "feat(fail-issue): 장비 비교 패널

캐시 키에 section 을 넣지 않습니다 — 응답이 두 축을 다 담고 있어 탭을
오가도 같은 데이터입니다. 매트릭스 칸은 fails/runs 와 비율을 함께 보여
주는데, 비율만으로는 3/10 과 300/1000 이 구분되지 않습니다."
```

---

### Task 12: 장비별 뷰 컨테이너

**Files:**

- Create: `front-dev-home/app/components/ebeam/FailIssueEquipmentView.vue`

**Interfaces:**

- Consumes: `fetchEquipments` (Task 8), `isPeerGroupComparable` (Task 9),
  `<EbeamFailIssueFleetTable>` (Task 10), `<EbeamFailIssueEquipmentCompare>`
  (Task 11), `MAX_COMPARE_EQPS` (Task 8).
- Produces: 컴포넌트 `<EbeamFailIssueEquipmentView>`
  - props: `fabs`, `toolType`, `dateRange`, `section`

- [ ] **Step 1: 컴포넌트를 만든다**

```vue
<template>
  <div class="space-y-3">
    <AppLoadingState
      v-if="status === 'pending' && !equipmentRows.length"
      title="장비별 데이터를 불러오는 중입니다."
    />
    <div
      v-else-if="!equipmentRows.length"
      class="dashboard-surface rounded-[var(--sk-r-card)] px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-inbox"
        class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
      />
      <p class="mt-2 sk-body">
        이 기간에 측정한 장비가 없습니다.
      </p>
      <p class="mt-1 sk-meta">
        기간을 넓히거나 다른 fab을 선택해보세요.
      </p>
    </div>

    <template v-else>
      <EbeamFailIssueFleetTable
        :rows="equipmentRows"
        :percentiles="percentiles"
        :peer-group-comparable="peerGroupComparable"
        :selected="selected"
        :max-selected="MAX_COMPARE_EQPS"
        :section="section"
        @update:selected="selected = $event"
      />

      <EbeamFailIssueEquipmentCompare
        v-if="selected.length"
        :tool-type="toolType"
        :fabs="fabs"
        :date-range="dateRange"
        :eqp-ids="selected"
        :rows="selectedRows"
        :section="section"
      />
      <div
        v-else
        class="dashboard-surface rounded-[var(--sk-r-card)] px-6 py-10 text-center"
      >
        <UIcon
          name="i-lucide-mouse-pointer-click"
          class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
        />
        <p class="mt-2 sk-body">
          장비를 선택해주세요
        </p>
        <p class="mt-1 sk-meta">
          위 표에서 최대 {{ MAX_COMPARE_EQPS }}대까지 체크하면 추이와 레시피 구성을 비교합니다.
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  MAX_COMPARE_EQPS,
  useFailIssueApi,
  type FailIssueToolType
} from '~/composables/useFailIssueApi'
import { isPeerGroupComparable } from '~/utils/failEquipmentSignals'

const props = defineProps<{
  fabs: string[]
  toolType: FailIssueToolType
  dateRange: { start: string, end: string }
  section: 'align' | 'meas'
}>()

const { fetchEquipments } = useFailIssueApi()

const selected = ref<string[]>([])

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: props.dateRange.start || undefined,
  endDate: props.dateRange.end || undefined
}))

// section 은 키에 없습니다 — 응답이 align·meas 두 축을 다 담고 있으므로
// 탭을 오가도 재요청이 필요 없습니다(설계 2절의 "응답 분할" 결정).
const cacheKey = computed(
  () => `fail-issue-equipments:${queryParams.value.toolType}`
    + `:${queryParams.value.fabNames?.join(',') ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  () => fetchEquipments(queryParams.value),
  { watch: [cacheKey] }
)

// 조회 범위가 바뀌면 선택을 비웁니다. 범위 밖 장비를 선택한 채로 두면
// 빈 비교 패널이 남습니다 (디바이스별의 resetKey 패턴과 같은 이유).
watch(cacheKey, () => {
  selected.value = []
})

const equipmentRows = computed(() => data.value?.equipments ?? [])
const percentiles = computed(() => data.value?.fleet.percentiles ?? {})

// 배지는 또래 집단이 한 fab일 때만 장비를 가리킵니다. 응답이 에코하는
// `fab_names`가 아니라 **실제로 돌아온 행**의 fab을 세는 이유는, fab 없이
// 조회하면 에코가 빈 목록인 채로 데이터는 전 fab을 덮기 때문입니다. 선택한
// fab 중 한 곳에 측정이 하나도 없어 결과적으로 한 fab만 남는 경우도 행을
// 세는 쪽이 맞습니다.
const peerGroupComparable = computed(() => isPeerGroupComparable(equipmentRows.value))

const selectedRows = computed(
  () => equipmentRows.value.filter(row => selected.value.includes(row.eqp_id))
)
</script>
```

- [ ] **Step 2: 타입·린트 검사**

Run (`front-dev-home/` 에서): `npm run typecheck && npm run lint`

Expected: 오류 없음

- [ ] **Step 3: 커밋**

```bash
git add front-dev-home/app/components/ebeam/FailIssueEquipmentView.vue
git commit -m "feat(fail-issue): 장비별 뷰 컨테이너

캐시 키에서 section 을 뺐습니다 — 한 응답이 두 축을 다 담고 있어 Align ⇄
Meas 전환에 재요청이 없습니다. peerGroupComparable 은 응답이 에코하는
fab_names 가 아니라 실제로 돌아온 행의 fab 을 셉니다: fab 없이 조회하면
에코가 빈 목록인 채로 데이터는 전 fab 을 덮습니다."
```

---

### Task 13: `FailIssueView.vue` 배선

**Files:**

- Modify: `front-dev-home/app/components/ebeam/FailIssueView.vue`

**Interfaces:**

- Consumes: `<EbeamFailIssueEquipmentView>` (Task 12).
- Produces: 없음 (최종 소비자).

- [ ] **Step 1: `VIEW_MODES` 에 세 번째 모드를 추가**

```typescript
const VIEW_MODES = [
  { value: 'summary', label: '전체 요약', icon: 'i-lucide-layers' },
  { value: 'by-device', label: '디바이스별', icon: 'i-lucide-cpu' },
  { value: 'by-equipment', label: '장비별', icon: 'i-lucide-microscope' }
] as const
```

- [ ] **Step 2: 손으로 만든 세그먼트 컨트롤을 `SkNavPill` 로 바꾼다**

`DESIGN.md:371` 이 이 패턴(white/zinc 세그먼트)을 지목해 `<SkNavPill>`(ink
fill)로 바꿔야 한다고 적고 있고, `RecipeTatView.vue` 는 이미 전환했습니다.
`#toggle` 슬롯 안의 `<div role="radiogroup">…</div>` 블록 전체를 아래로
교체합니다.

```vue
          <!-- 뷰 전환은 NAVIGATE 동작이라 SkNavPill(ink fill)입니다. 직접 만든
               white/zinc 세그먼트 컨트롤은 DESIGN.md가 이름을 대어 금지한
               패턴이었습니다 — 트레이 배경이 zinc를 종이 위로 끌고 들어옵니다. -->
          <div class="inline-flex items-center gap-1">
            <SkNavPill
              v-for="mode in VIEW_MODES"
              :key="mode.value"
              :label="mode.label"
              :icon="mode.icon"
              :active="viewMode === mode.value"
              @click="viewMode = mode.value"
            />
          </div>
```

차트 카드 안의 `CHART_TYPES` 토글은 **그대로 둡니다** — 그것은 뷰 전환이
아니라 같은 카드 안의 표현 전환이고, 이번 범위 밖입니다.

- [ ] **Step 3: `metaSubtitle` 에 장비별 문구를 더한다**

```typescript
const metaSubtitle = computed(() => {
  const aspect = props.section === 'align' ? 'Align Fail' : 'Measurement Fail'
  if (viewMode.value === 'by-device') return `${aspect}을 디바이스별로 분석합니다.`
  if (viewMode.value === 'by-equipment') {
    return `${aspect}을 장비(eqp_id)별로 비교합니다. 레시피 구성으로 정규화한 지수입니다.`
  }
  return `${aspect}을 Fab 기준으로 분석합니다.`
})
```

- [ ] **Step 4: 템플릿에 장비별 분기를 넣는다**

디바이스 피커(`<EbeamAnalyticsDevicePicker v-if="viewMode === 'by-device'" …/>`)
바로 **아래**, 디바이스 안내문 블록 **바로 위**에 넣습니다. 그리고 그
안내문의 `v-if` 를 `v-else-if` 로 바꿉니다.

```vue
    <!-- 장비별: 별도 컴포넌트 트리. 기존 본문은 건드리지 않습니다. -->
    <EbeamFailIssueEquipmentView
      v-if="viewMode === 'by-equipment'"
      :fabs="fabs"
      :tool-type="toolType"
      :date-range="dateRange"
      :section="section"
    />

    <!-- 디바이스별 mode without a selection: prompt -->
    <div
      v-else-if="viewMode === 'by-device' && !selectedLot"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
```

`v-if` → `v-else-if` 로 바꾸는 것이 핵심입니다. 그대로 두면 두 블록이 각각
독립된 `v-if` 라 장비별 모드에서 아래 `<template v-else>` 가 함께 켜져
전체 요약 차트가 같이 그려집니다.

`queryParams.lotCd` 는 그대로 둡니다 — `viewMode === 'by-device'` 일 때만
채워지므로 장비별에서는 자동으로 비어 있습니다.

- [ ] **Step 5: 타입·린트·단위 테스트**

Run (`front-dev-home/` 에서): `npm run typecheck && npm run lint && npm test`

Expected: 전부 통과

- [ ] **Step 6: 커밋**

```bash
git add front-dev-home/app/components/ebeam/FailIssueView.vue
git commit -m "feat(fail-issue): Align/Meas 탭에 장비별 모드를 연다

디바이스 안내문의 v-if 를 v-else-if 로 바꾸는 것이 핵심입니다 — 그대로
두면 두 블록이 독립된 v-if 라 장비별 모드에서 아래 v-else 가 함께 켜져
전체 요약 차트가 같이 그려집니다.

모드 토글을 SkNavPill 로 전환했습니다(DESIGN.md:371 이 이 패턴을 지목).
카드 안의 차트 타입 토글은 뷰 전환이 아니므로 그대로 둡니다."
```

---

### Task 14: 브라우저 확인

**Files:** 없음 (확인만)

**Interfaces:**

- Consumes: Task 1–13 전부.
- Produces: 없음.

자동화된 E2E 스위트가 없습니다. Playwright MCP 를 직접 몹니다 — 절차는
`verify` 스킬에 있습니다.

- [ ] **Step 1: 두 서버를 띄운다**

```bash
.venv/bin/python index.py                     # :5050
cd front-dev-home && npm run dev              # :3000
```

- [ ] **Step 2: Align 탭에서 장비별을 연다**

`http://localhost:3000/ebeam/cd-sem/m14a/recipe-status?tab=align` 로 이동한
뒤 `장비별` pill 을 누릅니다.

확인:

- 플릿 표에 장비 5대가 나오고 `align fail` · `fail율` · `fail index` 열이
  보입니다.
- `fail index` 열의 값 중 흐린 것이 있고, 그 위에 마우스를 올리면
  `실제 N건 / 기대 M건 · 95 % CI a ~ b — 구간이 1.00을 걸쳐…` 툴팁이 뜹니다.
- `신호` 열이 있습니다 (mock 에서는 대부분 비어 있는 것이 정상입니다 —
  Task 4 의 docstring 이 이유를 적고 있습니다).

- [ ] **Step 3: 정렬의 null-last 를 눈으로 확인한다**

`fail index` 헤더를 눌러 **오름차순**으로 만듭니다. `—` 인 행이 맨 **아래**
에 있어야 합니다. 맨 위에 올라오면 `manualSorting: true` 가 빠진 것입니다.

- [ ] **Step 4: 장비 2대를 선택한다**

체크박스 2개를 켭니다. 확인:

- 선택 요약 칩 2개의 점 색이 아래 추이 차트의 선 색과 각각 일치합니다.
- `[개수 | 비율]` 토글이 동작하고, `비율` 에서 y축이 `%` 로 바뀝니다.
- 매트릭스 열이 선택한 두 장비이고, 한쪽만 돈 레시피의 다른 칸이 `—` 입니다.
- 6번째 장비를 체크하려 하면 체크박스가 비활성입니다.

- [ ] **Step 5: 탭을 Meas 로 바꾼다**

상단 `Meas Fail` 탭을 누른 뒤 다시 `장비별` 을 봅니다. 확인:

- 열 머리가 `meas fail` 로 바뀌고 값이 달라집니다.
- **네트워크 탭에 `/equipments` 요청이 새로 생기지 않습니다** — 한 응답이 두
  축을 담고 있다는 설계 결정이 실제로 지켜지는지 보는 지점입니다.

- [ ] **Step 6: 여러 fab 을 골라 배지가 꺼지는지 본다**

사이드바에서 fab 을 2개 이상 선택합니다. 확인:

- 표 위에 "조회 결과가 두 개 이상의 fab에 걸쳐 있습니다…" 안내가 뜹니다.
- `신호` 열이 전부 `—` 입니다.
- `fail index` 헤더 툴팁이 혼합 fab 경고로 바뀝니다.

- [ ] **Step 7: 콘솔을 확인한다**

브라우저 콘솔에 오류가 없어야 합니다. `<!---->` 만 렌더되고 아무것도 안
보이면 Flask 가 죽은 것입니다 — 포트부터 확인하십시오.

- [ ] **Step 8: 스크린샷을 남긴다**

`.playwright-mcp/screenshots/` 아래에 상대 경로로 저장합니다
(예: `.playwright-mcp/screenshots/fail-issue-by-equipment-align.png`).

- [ ] **Step 9: 전체 스위트를 마지막으로 돌린다**

```bash
.venv/bin/python -m pytest -q
cd front-dev-home && npm test && npm run typecheck && npm run lint
cd .. && npm run lint:md
```

Expected: 전부 통과

- [ ] **Step 10: main 으로 병합하고 worktree 를 정리한다**

```bash
git -C . merge --ff-only work/fail-eqp && git push
git worktree remove ../skewnono-fail-eqp && git branch -d work/fail-eqp
git worktree list        # 메인 트리 하나만 남아야 합니다
```

`--ff-only` 가 거부되면 그 사이 main 이 움직인 것입니다. **자동 병합이
깨끗해도 안심하지 마십시오** — 이 저장소에서 깨끗한 자동 병합이 office 전용
코드를 망가뜨린 적이 있고, 집에서 도는 테스트는 그걸 잡지 못합니다.
`git log --oneline main..HEAD` 로 무엇이 들어왔는지 먼저 읽으십시오.

---

## Self-Review

**Spec coverage** — 설계 문서의 각 절이 어느 Task 에 들어갔는지:

| 설계 절 | Task |
| --- | --- |
| 3.1 지수 정의 | 2 |
| 3.2 신뢰구간 · 표시 하한 | 1, 2 |
| 3.3 그 밖의 열 | 2 |
| 3.4 배지 판정 | 9, 10 |
| 4.1 `/equipments` | 2, 4, 5 |
| 4.2 `/equipment-compare` | 3, 4, 5 |
| 5.1 `_shape.py` | 1, 2, 3 |
| 5.2 `contracts.py` | 1, 2, 3 |
| 5.3 mock | 4 |
| 5.4 office_example | 6 |
| 5.5 data · routes | 5 |
| 6.1 composable | 8 |
| 6.2 컴포넌트 3개 | 10, 11, 12 |
| 6.3 `FailIssueView` + SkNavPill | 13 |
| 7 테스트 | 1, 2, 3, 5, 9 |
| 8 문서 | 7 |
| 9 사무실 확인 절차 | 7 (MIGRATION.md 로 이관) |

**Type consistency** — Task 간 이름이 일치하는지 확인했습니다:

- `standardised` (Task 1 생산) → Task 2 소비. 반환은 3-튜플.
- `EquipmentGridRow` 7-튜플 (Task 2) → Task 4 mock, Task 6 office 가 같은
  순서로 생산.
- `TrendGridRow` · `RecipeGridRow` 5-튜플 (Task 3) → Task 4, 6.
- `failEquipmentSignals(row, percentiles)` (Task 9) → Task 10 이
  `signalInput(row)` 로 어댑팅해 호출. `FailEquipmentSignalInput` 의 필드명
  (`index`, `index_low`, `index_high`)은 API 필드명(`align_index` 등)과
  **일부러 다릅니다** — 판정 함수는 어느 축인지 몰라야 합니다.
- `MAX_COMPARE_EQPS` (Task 8) → Task 12. 백엔드 `MAX_EQP_IDS = 5` 와 같은 값.
- 컴포넌트 자동 import 이름: `components/ebeam/FailIssueFleetTable.vue` →
  `<EbeamFailIssueFleetTable>`. 경로 접두사가 이름에 들어갑니다 — 이름을
  틀리면 **오류 없이 빈 것이 렌더**되고 정적 검사가 잡지 못합니다.
