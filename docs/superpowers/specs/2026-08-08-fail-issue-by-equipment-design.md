# Align / Meas Fail 장비별 뷰 — 설계

- 작성일: 2026-08-08
- 상태: 설계 확정, 구현 전
- 범위: Recipe 현황 화면의 `Align Fail`·`Meas Fail` 두 탭에 `장비별`(eqp_id
  기준) 뷰를 추가합니다. 2026-08-07 에 `Recipe TAT` 탭에 넣은 장비별 뷰와
  같은 구조를 따르되, 지표는 소요 시간이 아니라 **실패**입니다.

## 1. 배경

Recipe 현황의 세 탭 중 `Recipe TAT` 만 장비별 시점을 갖고 있습니다.
`Align Fail` 과 `Meas Fail` 은 아직 `전체 요약` 과 `디바이스별` 두 가지뿐이며,
두 시점 모두 **레시피가 주어**입니다.

현업이 실패를 볼 때 필요한 나머지 축은 장비입니다. 구체적으로는 세 가지
질문에 답해야 합니다.

1. 어느 장비에서 정렬 실패 · 측정 실패가 유독 많이 나는가
2. 그 실패가 장비 탓인가, 그 장비가 맡은 레시피 탓인가
3. 의심되는 장비 몇 대를 나란히 놓았을 때 실패가 언제 · 어느 레시피에서
   갈리는가

`fail_issue` 의 원천 행(`FailRow`)에는 이미 `eqp_id` 가 실려 있고, office
OpenSearch 문서도 `eqp_id` 를 갖고 있습니다(`docs/datatables/meas_hist.txt`).
지금은 랭킹 행의 `sample_eqp_ids` 예시 목록으로만 쓰이므로, 이 작업은 새
집계 축을 추가하는 일이지 새 데이터를 구하는 일이 아닙니다.

## 2. 결정 요약

| 항목 | 결정 | 근거 |
| --- | --- | --- |
| 화면 구조 | recipe_tat 과 동일합니다. 선택 없이 **전 장비 플릿 표**를 먼저 보여주고, 거기서 최대 5대를 체크하면 비교 패널이 열립니다. | 이미 옆 탭에서 동작 중인 흐름입니다. 같은 페이지의 탭끼리 다른 상호작용을 주면 학습 비용만 늘어납니다. |
| 실패 비교 기준 | 단순 fail 비율이 아니라 **레시피 구성으로 정규화한 지수**(`align_index` · `meas_index`). | 3.1절. 단순 비율은 장비 상태가 아니라 그 장비가 맡은 레시피의 난이도를 잽니다(user-confirmed 2026-08-08). |
| 잡음 판정 | 점추정값을 상수와 비교하지 않고 **신뢰구간**으로 겁니다(Byar 근사). | 3.2절. recipe_tat 의 `TAT_INDEX_MIN_SAMPLE = 12` 를 그대로 베끼면 안 되는 유일한 지점이며, 상수 하나를 손으로 고르는 방식 자체가 이 지표에는 맞지 않습니다(2026-08-08 실측 근거). |
| 응답 분할 | `align` · `meas` 두 지표를 **한 응답**에 담고 프론트가 활성 `section` 열만 그립니다. | 두 탭이 이미 `FailIssueView` 인스턴스 하나를 공유합니다(`section` prop 만 바뀜). 탭을 오갈 때 재요청이 없고, office composite 집계도 한 번만 돕니다(user-confirmed 2026-08-08). |
| 비교 패널 | `일별 fail 추이 오버레이` + `레시피별 fail 매트릭스` 두 카드입니다. | recipe_tat 과 같은 두 카드 구조입니다. 매트릭스가 없으면 "왜 이 장비가 높은가"를 레시피 단위로 추적할 수 없습니다(user-confirmed 2026-08-08). |
| 측정 0건 장비 | **표에 넣지 않습니다.** | recipe_tat 과 같은 결정입니다. 명부 조인이 필요해 office 어댑터에 Redis 의존이 추가되며, 이번 범위 밖입니다. |
| 지표 계산 위치 | 비율·지수·분위수는 백엔드 공용 조립기(`_shape.py`), 배지 판정은 프론트엔드 한 파일. | 3.4절. recipe_tat 이 세운 규약을 그대로 따릅니다. |
| 임계값 상태 | OFFICE-VERIFY 는 `FAIL_INDEX_CEIL`·`FAIL_INDEX_FLOOR` **둘뿐**입니다. | 구간이 잡음 방어를 맡으면서 손으로 고를 상수가 넷에서 둘로 줄었고, 남은 둘은 통계 추정이 아니라 "얼마나 나빠야 사람이 움직이는가"라는 업무 판단입니다. 확인 절차는 9절. |
| API | 새 엔드포인트 2개. 기존 5개(`summary`/`daily-trend`/`align-ranking`/`meas-ranking`/`devices`)는 **손대지 않습니다.** | 4절 참고. |
| 컴포넌트 배치 | `FailIssueView.vue` 의 기존 본문은 **건드리지 않고** 모드 분기만 추가하며, 장비별은 새 컴포넌트 3개입니다. | 이미 726줄입니다. 동작 중인 두 뷰의 회귀 위험을 0으로 둡니다. |

## 3. 지표 정의

### 3.1 `align_index` · `meas_index` — 레시피 구성으로 정규화한 실패

장비를 `align_fail_rate` 로 줄세우면 **반드시 틀립니다.** 레시피마다 고유한
정렬 난이도가 다르기 때문입니다. 정렬이 까다로운 레이어를 많이 맡은 장비는
저절로 "실패가 잦은 장비"가 되고, 쉬운 레이어만 도는 장비는 "건강한 장비"가
됩니다. 장비 상태가 아니라 **일감의 난이도**를 잰 것입니다.

recipe_tat 의 `tat_index` 와 같은 간접표준화로 풉니다. 조회 범위(tool_type +
fab + 기간) 안에서:

```text
base(r)  = 레시피 r의 플릿 평균 실패율
           = Σ_t fail_count(t, r) / Σ_t exec_count(t, r)

expected(t) = Σ_r  exec_count(t, r) × base(r)   # 이 장비의 일감이면 이만큼 실패해야 함
actual(t)   = Σ_r  fail_count(t, r)             # 실제로 이만큼 실패했음

index(t)    = actual(t) / expected(t)
```

`1.31` 은 "같은 레시피 구성이라면 기대치보다 31 % 더 실패했다"는 뜻입니다.
`align` 과 `meas` 는 서로 독립적으로 같은 식을 돕니다.

어떤 레시피를 장비 한 대만 돌았다면 그 레시피의 플릿 평균이 곧 그 장비의
평균이라 해당 항이 정확히 `1.0` 을 기여합니다. 비교 정보가 없는 일감은 지수를
`1.0` 쪽으로 희석시킬 뿐 없는 경보를 만들지 않습니다 — recipe_tat 과 같은,
의도된 성질입니다.

**지수는 fab 하나 안에서만 비교 가능합니다.** `base(r)` 이 조회 범위 전체의
레시피별 평균이므로, 여러 fab 을 함께 조회하면 fab 단위의 실패율 차이가 그
fab 장비 *전부*의 지수가 됩니다. mock 의 `FAB_ALIGN_FAIL_RATE` 는 fab 별로
0.05 ~ 0.15 로 3배 차이가 나므로 이 편향은 mock 에서 즉시 재현됩니다. 그래서
프론트엔드는 조회 범위에 fab 이 2개 이상이면 배지를 아예 달지 않습니다
(3.4절).

### 3.2 잡음 판정 — 상수가 아니라 신뢰구간

recipe_tat 은 `exec_count >= TAT_INDEX_MIN_SAMPLE(12)` 로 표본 하한을 걸고,
배지는 `tat_index` 점추정값을 상수(`TAT_CEIL = 1.10`)와 비교합니다. **여기서
그 방식을 베끼면 안 됩니다.** 상수만 바꾸는 문제가 아니라 규칙의 형태가
이 지표에 맞지 않습니다.

TAT 지수는 **연속량(초)의 평균비**라 잡음이 `CV/√n` 입니다. 레시피 안
meastime 의 변동계수를 0.15 로 잡으면 12건에서 상대 표준편차가 0.043 이고,
`TAT_CEIL = 1.10` 은 `1.0` 에서 **2.3σ** 떨어져 있습니다 — 충분히 강한
기준입니다.

실패 지수는 **드문 사건의 건수비**입니다. 잡음이 `1/√λ` (λ = 기대 실패
건수)이므로 λ = 5 에서 상대 표준편차가 0.447 이고, 같은 폭의 상수를
1.25 로 넓혀도 `1.0` 에서 **0.56σ** 밖에 안 됩니다.

#### 실측: 이 화면의 λ 는 작습니다

2026-08-08 mock 실측(cd-sem, 장비당 align 실패 건수 중앙값):

| 조회 범위 | 14일(기본) | 30일 | 90일 |
| --- | --- | --- | --- |
| 단일 fab (M14A, 5대) | 4 | 11 | 21 |
| 전 fab (84대) | 2 | 5 | 15 |

이 λ 에서 **완전히 건강한 장비**가 잡음만으로 `[0.75, 1.25]` 밖으로 나갈
확률:

| λ | P(index ≥ 1.25) | P(index ≤ 0.75) | 둘 중 하나 |
| --- | --- | --- | --- |
| 5 | 23.8 % | 26.5 % | **50.3 %** |
| 21 | 11.7 % | 11.1 % | **22.9 %** |
| 80 | 1.7 % | 1.2 % | 2.9 % |
| 200 | ~0 % | ~0 % | ~0 % |

기본 조회(14일)에서 동전 던지기가 배지를 정합니다. 분위수 AND 조건도 이걸
구하지 못합니다 — 장비 5대짜리 fab 에서 `≥ p90` 은 **정의상 최댓값 장비
하나**라 언제나 참인 조건이기 때문입니다.

#### 해법: 점추정값이 아니라 구간을 본다

이 지수는 역학의 **간접표준화 비(SMR)** 와 정확히 같은 양입니다. 그쪽에서
쓰는 표준 처방을 그대로 씁니다: 상수와 비교할 대상을 점추정값이 아니라
**신뢰구간**으로 바꿉니다. Byar 근사면 충분하며 새 데이터가 필요 없습니다
(관측 건수와 기대 건수만 있으면 됩니다).

```text
z = 1.96  (95 %)

low(t)  = 0                                                      if obs = 0
        = obs × (1 − 1/(9·obs) − z/(3·√obs))³ ÷ expected         otherwise
high(t) = (obs+1) × (1 − 1/(9·(obs+1)) + z/(3·√(obs+1)))³ ÷ expected
```

배지 규칙(3.4절)은 이 구간이 `1.0` 을 넘겼는지로 판정하고, 상수는 **실무적
중요도**("이 정도는 되어야 볼 가치가 있다") 하한으로만 남습니다.

이 규칙은 스스로 적응합니다. 같은 배지를 받기 위해 필요한 관측 지수:

| 기대 실패 λ | 취약 배지에 필요한 index |
| --- | --- |
| 5 | 2.20 |
| 21 | 1.48 |
| 80 | 1.24 |
| 500 | 1.09 |

조용한 장비는 극단적이어야 하고, 바쁜 장비는 9 % 만 나빠도 잡힙니다. 그리고
실제로 25 % 나쁜 장비가 λ = 5 에서 **판단 보류**로 남는 것은 결함이 아니라
정답입니다 — 그 표본으로는 정말 구분할 수 없습니다.

#### 표시 하한

구간이 잡음 판정을 전부 맡으므로 손으로 고른 표본 하한이 필요 없습니다.
남는 것은 "지수라는 수를 만들 수 있는가"라는 정의상의 하한뿐입니다.

```text
index(t) = actual(t) / expected(t)   if expected(t) >= FAIL_INDEX_MIN_EXPECTED
           None                       otherwise
```

`FAIL_INDEX_MIN_EXPECTED = 1.0` — 기대 실패가 1건 미만이면 비율의 분모가
사실상 없습니다. **이 값은 OFFICE-VERIFY 가 아닙니다.** 튜닝 대상이 아니라
정의의 경계이므로 사무실 분포를 봐도 바뀔 이유가 없습니다.

`index` 가 `None` 인 것은 "실패하지 않았다"가 아니라 **"모른다"** 입니다.
정렬·배지 어느 쪽에서도 `None` 을 0 으로 취급하지 않습니다(3.3절, 3.4절).

### 3.3 그 밖의 열

| 필드 | 정의 | 비고 |
| --- | --- | --- |
| `exec_count` | 범위 안 이 장비의 측정 행 수 | 표시용이자 fail 비율의 분모입니다. |
| `align_fail_count` · `meas_fail_count` | 실패 행 수 | 판정 규칙은 기존 mock 의 `_is_align_fail` · `_is_meas_fail` 을 그대로 씁니다. |
| `align_fail_rate` · `meas_fail_rate` | `fail_count / exec_count`, 0..1 분수 | 기존 랭킹 행과 같은 스케일입니다. |
| `recipe_count` | 이 장비가 돈 서로 다른 `full_name` 수 | `편중` 배지의 입력입니다. |
| `top_recipe` · `top_recipe_share` | 실행이 가장 많은 레시피와 그 **실행 수** 비중 | recipe_tat 은 TAT 비중이지만 여기서는 실행 수 비중입니다. 실패 화면에서 "이 장비는 사실상 한 레시피만 돈다"의 근거는 시간이 아니라 횟수입니다. |

`top_recipe` 동률 처리는 recipe_tat 과 같습니다. 2차 키로 `full_name` 을
명시해 mock(행 스캔 순서)과 office(composite 버킷 순서)가 서로 다른 승자를
고르는 일을 막습니다.

### 3.4 임계값과 배지

백엔드는 **비율·구간·분포**를 계산하고, "이 값을 경고로 볼 것인가"라는 표시
정책만 프론트엔드 한 파일에 둡니다 — `equipmentSignals.ts` 와 같은 구조입니다.

신뢰구간이 백엔드에 있는 이유: 구간은 표시 정책이 아니라 **통계량**입니다.
`_shape.py` 가 "지수 산식은 한 곳에만 있다"를 지키는 것과 같은 이유로, 구간도
mock·office 가 각자 계산하면 안 됩니다. 프론트엔드가 갖는 것은 `1.0` 과
`CEIL` 이라는 **경계값 두 개**뿐입니다.

`FleetReference.percentiles` 가 내려주는 키:
`align_fail_rate`, `align_index`, `meas_fail_rate`, `meas_index`,
`recipe_count`, `exec_count`. 각 값은 `{p10,p25,p50,p75,p90}` 이며, 지수는
`None` 인 장비를 제외하고 계산합니다. **분위수는 이제 배지 판정에 쓰이지
않습니다** — 사무실에서 `FAIL_INDEX_CEIL` 을 정하기 위한 분포 참고용으로만
내려보냅니다(9절).

새 파일 `front-dev-home/app/utils/failEquipmentSignals.ts`:

| 배지 | 조건 | 톤 |
| --- | --- | --- |
| `취약` | `index_low > 1.0` **AND** `index > FAIL_INDEX_CEIL` | warn |
| `양호` | `index_high < 1.0` **AND** `index < FAIL_INDEX_FLOOR` | info |
| `편중` | `recipe_count <= p10` **AND** `top_recipe_share >= SHARE_CEIL` | warn |

두 조건이 각각 다른 질문에 답합니다. 구간 조건은 **"잡음과 구별되는가"**,
상수 조건은 **"볼 가치가 있을 만큼 큰가"** 입니다. 앞의 것은 통계가 답하고,
뒤의 것은 사람이 정합니다.

상수: `FAIL_INDEX_CEIL = 1.25`, `FAIL_INDEX_FLOOR = 0.75` (둘 다
OFFICE-VERIFY — 다만 이제 "잡음 방어선"이 아니라 **업무 판단**입니다. 9절),
`SHARE_CEIL = 0.50` (`equipmentSignals.ts` 와 같은 의미이므로 같은 값).

`index` 가 `None` 이면 `index_low`·`index_high` 도 `None` 이고, `취약`·`양호`
어느 쪽도 아닙니다.

`편중` 의 꼬리 비교는 recipe_tat 과 같이 **포함 부등호**(`<=`)입니다.
`percentile_summary` 는 nearest-rank 라 p10 이 항상 실제 표본 값 하나와
같고, 작은 플릿에서는 그 표본이 곧 최솟값 자신입니다. 엄격 부등호를 쓰면
경계를 정의하는 장비 자신이 자기 꼬리에 들지 못해, 정확히 배지를 달아야 할
가장 극단적인 장비가 구조적으로 제외됩니다. `recipe_count` 는 정수라 플릿이
커져도 동률이 사라지지 않으므로 이는 상시적인 문제입니다.

`isPeerGroupComparable` 은 기존 `equipmentSignals.ts` 에서 **import 해서
재사용**합니다. 여러 fab 을 섞으면 배지가 장비가 아니라 fab 을 가리킨다는
논거가 동일하고, 그 논거가 이미 그 파일에 길게 적혀 있습니다. 복제하면 한쪽만
고쳐지는 날이 옵니다.

## 4. API

### 4.1 `GET /<tool_slug>/fail-issue/equipments`

쿼리: `fab_name`, `start_date`, `end_date`. **`lot_cd` 를 받지 않습니다** —
이 엔드포인트는 "범위 안에 어떤 장비가 있는가"에 대한 진실이라 선택으로
걸러지면 안 됩니다(`/devices` 와 같은 이유).

```jsonc
{
  "tool_type": "cd-sem",
  "fab_names": ["M14"],
  "start_date": "2026-07-25",
  "end_date": "2026-08-08",
  "fleet": {
    "tool_count": 12,
    "total_executions": 41280,
    "align_fail_count": 5120,
    "meas_fail_count": 6890,
    "align_fail_rate": 0.124,
    "meas_fail_rate": 0.167,
    "median_exec_count": 3410.0,
    "median_recipe_count": 18.0,
    "min_expected_fails": 1.0,
    "confidence_z": 1.96,
    "percentiles": { "align_index": { "p10": 0.71, "p90": 1.31 } }
  },
  "equipments": [
    {
      "eqp_id": "CDS-1102",
      "fab_name": "M14",
      "eqp_model_cd": "CG5000",
      "exec_count": 4120,
      "align_fail_count": 512,
      "align_fail_rate": 0.1243,
      "align_expected": 390.8,
      "align_index": 1.3101,
      "align_index_low": 1.1991,
      "align_index_high": 1.4287,
      "meas_fail_count": 690,
      "meas_fail_rate": 0.1675,
      "meas_expected": 662.7,
      "meas_index": 1.0412,
      "meas_index_low": 0.9649,
      "meas_index_high": 1.1219,
      "recipe_count": 18,
      "top_recipe": "ADI/M1_CD",
      "top_recipe_share": 0.3421
    }
  ]
}
```

`*_expected` 는 표시용입니다. 배지가 켜진 이유를 사용자가 스스로 확인할 수
있어야 신뢰가 생깁니다 — 표의 지수 칸 툴팁이 `실제 512건 / 기대 390.8건
(95 % CI 1.20 ~ 1.43)` 을 그대로 보여줍니다. 숫자 하나만 던지고 근거를 숨기면
사용자는 배지를 믿지 않거나, 더 나쁘게는 근거 없이 믿습니다.

`confidence_z` 를 에코하는 이유는 `min_expected_fails` 와 같습니다: 구간의
의미를 프론트엔드가 추측하지 않게 하기 위해서입니다.

정렬은 `exec_count` 내림차순, 동률이면 `eqp_id` 오름차순입니다. recipe_tat 이
`total_meastime` 을 쓰는 자리에 여기서는 실행 수를 씁니다 — 이 화면에는
`total_meastime` 이 없습니다.

### 4.2 `GET /<tool_slug>/fail-issue/equipment-compare`

쿼리: 위와 같고 `eqp_id=a,b,c` 가 추가됩니다. `resolve_analytics_scope` 가
이미 이 인자를 파싱하고 `MAX_EQP_IDS = 5` 로 자릅니다 —
요청 파싱 쪽에 새로 만들 것이 없습니다.

```jsonc
{
  "tool_type": "cd-sem",
  "fab_names": ["M14"],
  "start_date": "2026-07-25",
  "end_date": "2026-08-08",
  "eqp_ids": ["CDS-1102", "CDS-1107"],
  "trends": [
    {
      "eqp_id": "CDS-1102",
      "points": [
        { "date": "2026-07-25", "exec_count": 290,
          "align_fail_count": 36, "meas_fail_count": 48 }
      ]
    }
  ],
  "recipes": [
    {
      "class_name": "ADI",
      "recipe_name": "M1_CD",
      "full_name": "ADI/M1_CD",
      "total_exec_count": 2600,
      "total_align_fail_count": 300,
      "total_meas_fail_count": 412,
      "cells": [
        { "eqp_id": "CDS-1102", "exec_count": 1420,
          "align_fail_count": 180, "meas_fail_count": 232 },
        { "eqp_id": "CDS-1107", "exec_count": 1180,
          "align_fail_count": 120, "meas_fail_count": 180 }
      ]
    }
  ]
}
```

`eqp_ids` 는 상한 적용 후 **실제로 사용된 목록**을 에코합니다. 절단을 조용히
하지 않기 위한 필드입니다.

`trends[].points` 는 요청 기간의 모든 날짜를 채웁니다. 조용한 날을 건너뛰면
x축이 거짓말을 합니다.

`recipes[].cells` 는 선택 장비 수만큼 **요청 순서 그대로**이며, 그 장비가 이
레시피를 돌지 않았으면 0 으로 채웁니다. 열이 밀리면 비교표가 다른 장비의
숫자를 보여줍니다.

`recipes` 정렬은 `total_align_fail_count + total_meas_fail_count` 내림차순,
동률이면 `full_name` 오름차순입니다. 백엔드는 활성 탭을 모르므로 두 지표를
합친 결정적 순서만 보장하고, **프론트엔드가 활성 aspect 기준으로 다시
정렬**합니다. 페이지네이션이 안정적이려면 백엔드 순서가 결정적이어야 하므로
2차 키를 명시합니다.

## 5. 백엔드 구현

### 5.1 새 파일 `fail_issue/providers/_shape.py`

recipe_tat 과 같은 규약입니다: **provider 는 자기 소스에서 격자만 만들고
조립은 여기서 합니다.** 지수·중앙값·분위수를 두 provider 가 각자 계산하면
언젠가 어긋나고, 그때 어느 쪽이 맞는지 판정할 방법이 없습니다. 집에서는
office 를 실행할 수 없으므로 그 판정자가 아예 존재하지 않습니다.

```python
# (eqp_id, fab_name, eqp_model_cd, full_name, exec_count, align_fails, meas_fails)
EquipmentGridRow = tuple[str, str, str, str, int, int, int]

def build_equipments_payload(tool_type, fab_names, start_date, end_date, grid)
    -> EquipmentsPayload

# (eqp_id, date, exec_count, align_fails, meas_fails)
TrendGridRow = tuple[str, str, int, int, int]
# (eqp_id, full_name, exec_count, align_fails, meas_fails)
RecipeGridRow = tuple[str, str, int, int, int]

def build_equipment_compare_payload(
    tool_type, fab_names, start_date, end_date, eqp_ids, trend_rows, recipe_rows
) -> EquipmentComparePayload
```

`days_in_range` 와 `window_seconds` 는 recipe_tat 의 `_shape.py` 에 이미
있습니다. `days_in_range` 만 필요하므로 **거기서 import 합니다** — 날짜 채움
규칙이 두 벌이 되면 두 화면의 x축이 서로 다른 날 개수를 그리게 됩니다.
(`window_seconds` 는 이 화면에 점유율이 없어 쓰지 않습니다.)

`expected` 합산에서 `count` 가 0 인 레시피는 `base` 에 없으므로 건너뜁니다.
mock 은 행마다 1 을 더하므로 도달할 수 없지만 office 의 composite 는
`doc_count` 0 인 버킷을 낼 수 있습니다. 0.0 으로 채우지 않고 건너뛰는 이유는
recipe_tat 과 같습니다: 기여할 실행이 없는 항은 분모에서 빠져야 하고, 0.0 을
더하면 분모만 작아져 지수가 조용히 부풀어 오릅니다.

Byar 구간은 `_shape.py` 안의 순수 함수 하나(`byar_interval(obs, expected)`)로
두고, 조립기가 장비마다 두 번(align·meas) 부릅니다. `obs = 0` 이면 하한은
정확히 0 이며(로그가 정의되지 않는 자리), 이 분기를 빼면 `ZeroDivisionError`
가 납니다.

### 5.2 `contracts.py` 추가분

`FAIL_INDEX_MIN_EXPECTED`, `CONFIDENCE_Z`, `EquipmentRow`, `FleetReference`,
`EquipmentsPayload`, `EquipmentTrendPoint`, `EquipmentTrendSeries`,
`EquipmentRecipeCell`, `EquipmentRecipeRow`, `EquipmentComparePayload`.

`EquipmentTrendPoint` 는 기존 `DailyTrendPoint` 와 필드가 같지만 **별도
타입으로 둡니다.** 기존 타입은 페이지 전역 추이의 계약이고 이 타입은 장비
단위 추이의 계약이라, 한쪽에 필드를 더할 때 다른 쪽이 따라 움직여야 할 이유가
없습니다.

### 5.3 `providers/mock.py` 추가분

`get_equipments` 와 `get_equipment_compare` 를 추가합니다. 기존
`_filter_rows` 를 그대로 쓰고(이미 `lru_cache` 로 memoize 되어 있음), 행을
격자로 접어 `_shape` 에 넘깁니다. 기존 집계 함수는 손대지 않습니다.

docstring 에는 이 mock 이 무엇을 대신하는지 적습니다: 실패는
`FAB_ALIGN_FAIL_RATE` · `FAB_MEAS_FAIL_RATE` 라는 **fab 단위 고정 스칼라**에서
나오므로, mock 에는 "장비 개체차"가 존재하지 않습니다. 즉 같은 fab 안의 장비
지수는 표본 변동만으로 흩어집니다. 배지가 실제로 켜지는지는 사무실에서만
확인할 수 있으며 이는 OFFICE-VERIFY 입니다.

**mock 값을 바꾸지 않습니다.** 장비별 편차를 지어내면 사무실 데이터에 대해
거짓을 가르치게 됩니다(CLAUDE.md 의 "Never make a mock imitate office values
it cannot know").

### 5.4 `providers/office_example.py` 추가분

recipe_tat 의 office_example 과 같은 방식으로 composite 집계 템플릿을
씁니다. `_composite_buckets` 를 `(eqp_id, full_name)` 복합 소스로 돌리고 각
버킷에서 `doc_count` 와 두 개의 `filter` 하위 집계(`align_fail: "Fail"`,
`fail_ratio > MEAS_FAIL_THRESHOLD`)를 읽어 격자를 만든 뒤 `_shape` 에
넘깁니다. `fab_name` · `eqp_model_cd` 는 버킷당 `top_hits` 1건이 아니라
composite 소스에 함께 넣어 얻습니다 — 장비 하나는 fab 하나에 속하므로
카디널리티가 늘지 않습니다.

`office.py` 는 gitignore 대상이므로 이 작업에서 만들지 않습니다. 사무실에서
`python -m scripts.sync_office_adapters fail_issue` 로 갱신합니다.

### 5.5 `data.py` · `routes.py`

`data.py` 에 두 dispatcher 를 추가하고, `routes.py` 에 두 GET 을 추가합니다.
`resolve_analytics_scope` 를 이미 쓰고 있으므로 recipe_tat 의 두 라우트를
그대로 옮겨 오는 수준입니다.

## 6. 프론트엔드 구현

### 6.1 `composables/useFailIssueApi.ts`

`MAX_COMPARE_EQPS = 5` 와 응답 타입들, `fetchEquipments` ·
`fetchEquipmentCompare` 를 추가합니다. `fetchEquipments` 는 `/devices` 와 같이
`lotCd` 를 **의도적으로 떨어뜨립니다**.

`buildQuery` 에 `eqpIds` 분기를 더합니다(`eqp_id=a,b,c`).

### 6.2 새 컴포넌트 3개

| 파일 | 역할 |
| --- | --- |
| `ebeam/FailIssueEquipmentView.vue` | 데이터 로드 + 빈 상태 + 선택 상태 소유. 조회 범위가 바뀌면 선택을 비웁니다. |
| `ebeam/FailIssueFleetTable.vue` | 플릿 표. 검색·정렬·체크박스·배지. |
| `ebeam/FailIssueEquipmentCompare.vue` | 선택 요약 칩 + 추이 오버레이 + 레시피 매트릭스. |

세 파일 모두 `section: 'align' | 'meas'` 를 prop 으로 받아 활성 지표의 열만
그립니다.

플릿 표 열: `pick`, `eqp_id`, `fab`, `model`, `실행수`, `fail 수`, `fail율`,
`fail index`, `레시피수`, `신호`. `fail 수`·`fail율`·`fail index` 는 활성
section 의 값을 읽습니다.

`fail index` 칸은 점추정값을 쓰고, 툴팁에 근거를 전부 펼칩니다:
`실제 512건 / 기대 390.8건 · 95 % CI 1.20 ~ 1.43`. 구간이 `1.0` 을 걸치는
장비는 값을 `--sk-ink-muted` 로 죽여 "이 수는 아직 판단 근거가 아니다"를
시각적으로 말합니다 — 배지가 없는 이유를 표 안에서 바로 읽을 수 있어야
합니다.

정렬은 `manualSorting: true` 로 두고 비교자를 직접 씁니다. recipe_tat 의
`RecipeTatFleetTable.vue` 에 이 한 줄이 없었을 때 무슨 일이 벌어졌는지 그
파일 주석에 적혀 있습니다: UTable 이 언제나 `getSortedRowModel()` 을 설치하고
`compareBasic(null, x)` 가 `-1` 이라, `index` 가 `None` 인 표본 미달 장비가
오름차순에서 전부 맨 위로 올라옵니다. `sortUndefined` 는 `undefined` 에만
걸려 `null` 에는 적용되지 않습니다. **`index === null` 은 정렬 방향과 무관하게
항상 맨 뒤로 보냅니다.**

추이 차트는 `[개수 | 비율]` 토글을 갖습니다. 비율은 `fail_count / exec_count`
로 프론트에서 계산합니다 — 백엔드가 이미 두 값을 다 내려주므로 세 번째 필드를
추가할 이유가 없습니다.

다중 시리즈에 `areaStyle` 을 주지 않습니다. hover 시 blur 가 채움을 지워
화면이 깨진 것처럼 보입니다(`RecipeTatEquipmentCompare.vue` 의 같은 주석).

매트릭스 페이지네이션은 `usePagedRows` 를 씁니다.

### 6.3 `FailIssueView.vue` 수정

`VIEW_MODES` 에 `{ value: 'by-equipment', label: '장비별', icon:
'i-lucide-microscope' }` 를 추가하고, 템플릿에 `viewMode === 'by-equipment'`
분기를 **디바이스 안내문 앞**에 넣습니다. 기존 본문은 건드리지 않습니다.

`queryParams.lotCd` 는 그대로 둡니다 — `viewMode === 'by-device'` 일 때만
채워지므로 장비별에서는 자동으로 비어 있습니다.

`metaSubtitle` 에 장비별 문구를 더합니다.

**함께 고치는 것 2가지** (지금 손대는 코드 안에서만):

1. 모드 토글이 손으로 만든 white/zinc 세그먼트 컨트롤입니다. `DESIGN.md:371`
   이 바로 이 패턴을 지목해 `<SkNavPill>`(ink fill)로 바꿔야 한다고 적고
   있고, `RecipeTatView.vue` 는 이미 전환했습니다. 세 번째 pill 을 더하면서
   함께 전환합니다.
2. 새로 만드는 surface 는 `rounded-[var(--sk-r-card)]` 를 씁니다.
   기존 `FailIssueView.vue` 마크업의 `rounded-2xl` 은 이번 범위에서 손대지
   않습니다 — 관련 없는 회귀 위험을 만들지 않습니다.

## 7. 테스트

| 파일 | 검사 |
| --- | --- |
| `fail_issue/tests/test_shape.py` (신규) | 순수 조립기. 지수 산식이 손으로 계산한 값과 일치하는가. 기대 실패가 하한 미만이면 `None` 인가. `None` 을 분위수에서 제외하는가. 비교 payload 의 `cells` 길이와 순서가 `eqp_ids` 와 같은가. 돌지 않은 장비 칸이 0 인가. |
| `fail_issue/tests/test_byar.py` (신규) | 구간이 문헌값과 일치하는가(관측 11 · 기대 5 → 약 `[1.10, 3.94]`). `obs = 0` 에서 하한이 정확히 0 이고 예외가 없는가. `low <= index <= high` 가 항상 성립하는가. λ 가 커질수록 구간이 좁아지는가(단조성). |
| `fail_issue/tests/test_contract.py` (추가) | 두 엔드포인트의 payload 가 TypedDict 키를 전부 갖는가. 한 장비가 fab 하나에만 나타나는가. `equipments` 합이 `fleet` 합과 맞는가. `eqp_id` 6개를 보내면 5개로 잘리고 `eqp_ids` 가 그 사실을 에코하는가. `trends[].points` 가 요청 기간의 날짜 수와 같은가. |
| `front-dev-home/app/utils/failEquipmentSignals.test.ts` (신규) | 구간이 `1.0` 을 걸치면 배지 없음. 구간은 통과했는데 `CEIL` 미만이면 배지 없음(두 조건이 AND 인지). `index === null` 에서 `취약`·`양호` 어느 쪽도 아님. `편중` 의 포함 부등호 경계. |

`test_byar.py` 를 따로 두는 이유는 이 함수가 이 기능에서 **유일하게 자명하지
않은 수식**이기 때문입니다. 나머지는 합계와 나눗셈이라 눈으로 검증되지만,
Byar 근사는 틀려도 그럴듯한 숫자를 냅니다.

프론트엔드에는 컴포넌트 마운팅 하네스가 없으므로 순수 함수만 테스트합니다.
화면 확인은 `verify` 스킬로 Playwright MCP 를 직접 몹니다.

## 8. 문서

- `docs/api-contracts/fail-issue.yaml` — 두 엔드포인트 추가.
- `back_dev_home/ebeam/hitachi/fail_issue/MIGRATION.md` — office 어댑터가
  해야 할 일과 OFFICE-VERIFY 목록(9절을 그대로 옮깁니다).
- `docs/datatables/meas_hist.txt` — 이 작업은 새 필드를 요구하지 않으므로
  변경 없습니다. 사무실에서 새 사실이 나오면 그때 mock 과 함께 갱신합니다.

## 9. 사무실 확인 절차

집에서 정할 수 없는 것은 **두 개뿐**입니다. 신뢰구간이 잡음 방어를 맡으면서
튜닝이 필요한 상수가 넷에서 둘로 줄었고, 남은 둘도 통계 추정이 아니라 업무
판단입니다.

| 확인 대상 | 지금 값 | 무엇을 보는가 |
| --- | --- | --- |
| `FAIL_INDEX_CEIL` | 1.25 | "얼마나 나빠야 사람이 움직이는가" |
| `FAIL_INDEX_FLOOR` | 0.75 | 같은 질문의 반대편 |

### 9.1 필요한 것

단일 fab · 90일 조회의 `/equipments` 응답 **한 개**면 충분합니다. 장비 수가
많은 fab 을 고르십시오 — 5대짜리 fab 은 분위수가 최댓값·최솟값 자신이라
분포를 읽을 수 없습니다.

```bash
curl -s -b 'LASTUSER=local-dev' \
  'http://localhost:5000/api/cdsem/fail-issue/equipments?fab_name=<FAB>&start_date=<90일전>&end_date=<오늘>' \
  > /tmp/eqp.json
```

### 9.2 볼 것 네 가지

1. **λ 의 실제 범위.** `equipments[].align_expected` 의 분포입니다. 집에서는
   90일 단일 fab 에서 중앙값 21 이었습니다. 사무실이 200 이상이면 구간이
   좁아져 `CEIL` 이 실질적인 유일한 문턱이 되고, 20 근처면 구간이 대부분을
   걸러내 배지가 드물게 뜹니다. **이 값 하나가 나머지 판단을 전부 좌우합니다.**
2. **배지가 몇 대에 뜨는가.** `index_low > 1.0 AND index > 1.25` 를 만족하는
   장비 수를 세어 보십시오. 플릿의 5~15 % 면 적당합니다. 0대면 `CEIL` 을
   낮추고, 절반이 넘으면 올립니다.
3. **뜬 장비가 실제로 문제 장비인가.** 이게 결정적입니다. 배지가 붙은
   장비를 현업이 아는 문제 장비와 대조하십시오. 통계가 맞아도 지표가 틀릴
   수 있습니다 — 그 경우 조정 대상은 상수가 아니라 3.1절의 `base(r)` 정의
   입니다.
4. **fab 혼합 편향이 재현되는가.** fab 없이 조회한 뒤 배지가 특정 fab 에
   몰리는지 봅니다. 몰린다면 3.1절 예상대로이고, 프론트엔드가 이미 다중 fab
   에서 배지를 끄므로 조치는 필요 없습니다. 몰리지 않는다면 `base(r)` 을
   fab 별로 계산할 필요가 없다는 뜻이므로 3.1절 주석을 그때 정정합니다.

### 9.3 확인 후

`failEquipmentSignals.ts` 의 상수 두 개만 고치고, 주석의 `OFFICE-VERIFY` 를
`office 확인 YYYY-MM-DD` 로 바꿉니다. 백엔드는 건드릴 것이 없습니다 — 구간과
분위수는 데이터에서 나오지 상수에서 나오지 않습니다.

`FAIL_INDEX_MIN_EXPECTED = 1.0` 과 `CONFIDENCE_Z = 1.96` 은 **확인 대상이
아닙니다.** 앞은 정의의 경계, 뒤는 관례입니다.

## 10. 범위 밖

- 측정 0건 장비를 표에 넣는 일 (명부 조인 필요).
- `Recipe TAT` 탭의 장비별 뷰 수정. 이 작업은 그 코드를 읽기만 합니다.
  (**예외 1건, 2026-08-09 기록** — 아래 참조.)
- `office.py` 작성 (gitignore 대상, 사무실에서 `cp`).
- 두 화면의 플릿 표를 공용 컴포넌트로 합치는 일. 열·지표·배지가 모두 다르고,
  지금 합치면 `section` 과 지표 종류 두 축을 동시에 받는 컴포넌트가 됩니다.
  세 번째 소비자가 생기면 그때 다시 봅니다.

### 10.1 읽기 전용 펜스의 예외 (2026-08-09 기록)

위 펜스에도 불구하고 이 작업은 `Recipe TAT` 쪽 파일 두 개를 수정했습니다.
`useRecipeTatApi.ts` 에서 `MAX_COMPARE_EQPS` 를 제거하고,
`RecipeTatEquipmentView.vue` 의 import 를 바꾼 뒤, 두 탭이 함께 쓰는
`front-dev-home/app/utils/analyticsLimits.ts` 를 새로 만들었습니다.

**사유:** Nuxt 자동 임포트 이름 충돌입니다. `useFailIssueApi.ts` 가
`MAX_COMPARE_EQPS` 를 내보내는 순간 이미 같은 이름을 내보내던
`useRecipeTatApi.ts` 와 부딪히고, Nuxt 는 이 경우 **빌드 WARN 하나만 남기고
한쪽을 조용히 버립니다** — 정적 검사에 걸리지 않고 런타임에야 드러나는
종류의 고장입니다. 펜스를 지키려면 두 탭이 같은 상수 5 를 서로 다른 이름으로
들고 있어야 했고, 그건 값이 갈라질 자리를 만드는 선택이었습니다.

**성질:** 동작 보존입니다. 상수 값(5)도, 두 뷰의 화면 동작도 그대로입니다.
바뀐 것은 그 값이 사는 위치뿐입니다.

**후속:** 이 상수의 최종 홈은 `recipe_tat/contracts.py` 입니다 —
recipe-tat spec §4.2 가 그렇게 정해 두었고, `analyticsLimits.ts` 는 그
백엔드 상수를 프론트에서 참조하는 자리로 남습니다.
