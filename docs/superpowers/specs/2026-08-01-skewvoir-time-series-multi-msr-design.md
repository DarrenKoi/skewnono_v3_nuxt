# Skewvoir Time-Series 다중 MSR 분석 화면 설계

Date: 2026-08-01

## 목적

검색 화면(`skewvoir/index`)에서 여러 MSR을 선택해 분석으로 진입했을 때 열리는
`Time-Series` 보기를 실제 분석이 가능한 화면으로 확장합니다.

현재 이 보기는 다음 두 가지 질문만 답합니다.

- 활성 파라미터 한 개의 측정별 평균이 어떻게 변했는가
- focus 측정 한 개의 sequence 추이는 어떤 모양인가

이번 변경은 다음 세 가지 질문에 각각 하나의 보기를 부여하고, 상단 버튼으로
전환합니다.

| 질문 | 보기 |
| --- | --- |
| 시간에 따른 drift — 세트 전체가 한 방향으로 흐르고 있는가 | 추이 |
| 측정별 분포 — 특정 wafer만 산포가 커졌는가 | 분포 |
| 장비 간 skew — 장비들이 서로 다르게 측정하고 있는가 | 장비 skew |

backend API, 데이터 모델, `msr_file` 계약은 변경하지 않습니다. 필요한 데이터는
이미 `setRows`와 `setFiles`에 적재되어 있으므로 이번 작업은 파생 로직과 화면
구성, 그리고 아래에 명시한 활성 파라미터 규칙 변경만 다룹니다.

## 현재 상태

| 항목 | 현재 |
| --- | --- |
| 진입 경로 | `SelectionWorkbench.vue`의 `Time-Series` 버튼 → `openAnalysisSet(focus, msrs, 'time-series')` |
| URL 상태 | `msrs`, `scope=set`, `view=time-series`, `mp` |
| 세트 상한 | `TREND_LIMIT = 30` |
| 데이터 적재 | `POST /api/msr-files` 일괄 조회 결과가 `setFiles: Map<msr, MsrFileResponse>`에 보관됨 |
| 화면 구성 | `Multi-Measurement Trend` + `Sequence Trend` 2개 패널 (155줄) |
| x축 | `type: 'category'` — 측정 라벨 등간격 |
| 파라미터 전환 | 이 보기에는 없음. `ParamNav`는 `views/Dashboard.vue`에만 있음 |
| 활성 파라미터 기본값 | `SearchLanding.vue`가 진입 시 `mp: 'WAFER'`를 기록하고, `parseSelection`도 `mp` 부재 시 `WAFER`로 보정합니다 |

같은 워크스페이스의 `views/Correlation.vue`는 318줄 4패널,
`views/PositionStack.vue`는 132줄 3패널이므로 현재 Time-Series 보기가 가장
얇은 상태입니다.

`trendPoints`는 이미 내부적으로 `ts`(timestamp)를 계산해 정렬한 뒤 차트에
넘기기 직전에 버리고 있습니다. 따라서 실제 시간축 도입 비용은 크지 않습니다.

## 확정된 설계 결정

| 항목 | 결정 |
| --- | --- |
| 화면 구조 | 하나의 차트 슬롯을 세 보기가 공유하고 상단 버튼으로 전환합니다 |
| 기본 보기 | 추이 |
| x축 | 추이 보기의 기본은 실제 시간축이며, `시간 / 순서` 전환으로 등간격 전환이 가능합니다 |
| 값 기준 | 추이 보기에서 원시값과 잔차를 전환할 수 있습니다 |
| 기준값 명칭 | `세트 기준`으로 고정합니다. `consensus`는 사용하지 않습니다 |
| 관리 한계선 | 그리지 않습니다 |
| 파라미터 선택 | 세트 인지형 선택기를 두고, 이를 위해 `scope=set`에서 활성 파라미터 판정 기준을 완화합니다 |
| 세트 무결성 | 누락된 MSR과 recipe 혼재를 화면에 표시하되 선택을 막지는 않습니다 |
| Sequence Trend | 보기 전환과 무관하게 최하단에 상시 유지합니다 |
| FDC 상관 | 이번 범위에서 제외합니다 |

세 보기를 동시에 적층하지 않고 버튼 전환으로 두는 것은 확정된 선택입니다.
수용하는 절충은 수준(평균)과 산포(분포)를 한 화면에서 동시에 볼 수 없다는
점이며, 얻는 것은 각 보기가 자신에게 맞는 축을 온전히 쓸 수 있다는 점입니다.
특히 분포 보기가 자체 category 축을 가지므로 ECharts 기본 boxplot을 그대로
사용할 수 있습니다.

## 활성 파라미터 규칙 변경

이번 변경에서 유일하게 공용 로직을 건드리는 부분이므로 별도로 명시합니다.

현재 `useSkewvoirAnalysis.ts`의 `activeParam`은 URL `mp`를 **focus 파일**이
보유한 경우에만 인정하고, 이어지는 watcher가 focus 파일에 없는 `mp`를 focus
기준 대체값으로 URL에 되써넣습니다. 이 규칙 아래에서는 세트 인지형 선택기가
성립하지 않습니다. 세트 30개 중 22개가 보유한 파라미터라도 focus 측정이
보유하지 않으면 선택 직후 되돌려지기 때문입니다.

따라서 `scope === 'set'`인 동안 판정 기준을 세트 전체로 완화합니다.

| scope | 활성 파라미터 인정 기준 | 되써넣기 |
| --- | --- | --- |
| `single` | 현재와 동일하게 focus 파일의 파라미터 | 현재와 동일 |
| `set` | 세트 내 **어느 한 측정이라도** 보유한 파라미터 | 세트 기준으로 판정 |

세트 파일이 아직 적재되지 않은 동안에는 완화를 적용하지 않고 현재 동작을
유지합니다. `shouldLoadSet`이 `dashboard` 보기를 제외하므로 `scope=set`이면서
`view=dashboard`인 상태에서는 `setFiles`가 비어 있고, 이때 세트 기준으로
판정하면 모든 파라미터가 미보유로 취급되어 URL이 훼손됩니다. 판정 기준은
`setFiles`가 비어 있으면 focus 기준으로 되돌아갑니다.

이 변경은 `Dashboard`, `Gallery`, `PositionStack`, `Correlation`도 함께 읽는
값이므로, 완화가 `scope === 'set'`으로만 한정된다는 점과 위의 미적재 예외를
회귀 테스트로 고정합니다.

## 화면 구성

읽기 순서는
`세트 무결성 알림 → 파라미터 선택기 → 보기 전환 버튼 → 활성 차트 → Sequence Trend`
입니다.

### 세트 무결성 알림

두 가지 사실을 화면 상단에 표시하며, 어느 쪽도 선택을 막지 않습니다.

| 상황 | 표시 |
| --- | --- |
| URL `msrs`에 있으나 측정 이력에서 해소되지 않은 MSR | `n개 측정이 이 장비군 검색 결과에 없어 제외되었습니다` |
| 세트가 2개 이상의 recipe에 걸침 | `recipe n종 혼재 · 장비 차이로 해석하기 어렵습니다` 배지 |

첫 번째는 기존 동작을 드러내는 것입니다. 검색은 두 SEM 계열을 함께 조회하지만
(`SearchLanding.vue`의 주석대로 카테고리 드롭다운만이 색인을 좁힙니다) 분석은
`ws.toolType`으로 이력을 적재하므로, `resolveSetRows`가 이력에 없는 MSR을
조용히 버립니다. CD-SEM 화면에서 HV-SEM 행을 함께 선택하면 그만큼이 아무런
안내 없이 사라집니다.

두 번째는 장비 skew 보기의 해석 한계를 알리는 것입니다. recipe가 섞인 세트에서
장비별 offset은 장비 효과와 recipe 효과가 뒤섞인 값이므로, 장비 차이로 단정할
수 없습니다.

### 파라미터 선택기

활성 파라미터를 이 화면에서 직접 전환합니다.

기존 `ParamNav`를 재사용하지 않습니다. `ParamNav`가 사용하는 `availableParams`는
focus 파일 한 개에서 파생되므로, 서로 다른 recipe가 섞인 세트에서는 세트
대부분이 보유하지 않은 파라미터를 제시할 수 있습니다.

이 선택기는 세트 전체를 기준으로 목록을 구성하고 각 항목에 커버리지를 함께
표시합니다.

| 표시 | 의미 |
| --- | --- |
| `WAFER · 28/30` | 세트 30개 측정 중 28개가 이 파라미터를 보유합니다 |

커버리지 분모는 **파일이 적재된 측정 수**이며, 파일 자체를 받지 못한 MSR은
세트 무결성 알림이 따로 셉니다. `POST /api/msr-files`는 존재하지 않는 MSR을
조용히 건너뛰므로, 이를 구분하지 않으면 조회 실패가 파라미터 미보유로
오인됩니다.

정렬은 세트 전체에 대해 결정론적이어야 합니다. `sortByRowMpOrder`는 한 측정의
파라미터 순서를 정의하는 함수이고 recipe마다 MP 순서가 다를 수 있으므로,
세트에서는 다음 순서로 정합니다.

1. 커버리지가 높은 순
2. 동률이면 세트 내 최소 `(mp_number, sequence)` 순
3. 그래도 동률이면 파라미터 이름 순

이름 없는 settling MP는 `UNNAMED_PARAM_LABEL`(`-`)로 표시하되 기본 선택
대상에서는 제외합니다. 선택 결과는 기존 `mp` URL 키에 `ws.setParam()`으로
기록하므로 새로운 URL 계약이 생기지 않습니다.

### 보기 전환 버튼

| 보기 | 내용 | 전용 컨트롤 |
| --- | --- | --- |
| 추이 | 측정별 평균의 시간 추이 | 시간 / 순서, 원시값 / 잔차, 이상 판정 설정 |
| 분포 | 측정별 상자 그림 | 없음 |
| 장비 skew | 장비별 offset 구간 도표와 수치 표 | 없음 |

비활성 보기는 `v-if`로 DOM과 ECharts 인스턴스를 해제합니다. 이는
`2026-07-29-skewvoir-fdc-graph-view-toggle-design.md`가 확립한 선례를 따르는
것이며, 숨겨진 차트 인스턴스 유지와 숨김 상태의 크기 계산 문제를 피하기
위함입니다. 그 결과 보기를 떠났다가 돌아오면 사용자가 조정한 dataZoom 범위가
초기화됩니다. 이를 이번 변경의 수용된 절충으로 명시합니다.

보기 전환 버튼은 loading, 빈 세트 상태에서는 표시하지 않습니다.

### 보기 1 — 추이

| 요소 | 내용 |
| --- | --- |
| x축 | 실제 시간축(기본) 또는 측정 순서 등간격 |
| y축 | 활성 파라미터의 측정별 평균, 원시값 또는 세트 기준 대비 잔차 |
| 밴드 | 측정별 min/max 범위 |
| 계열 분리 | `eqp_id` 별 색 분리 |
| 점 색상 | 기존 `combineVerdicts` 판정(정상 / 주의 / 이상 / 판정 불가) |
| 상호작용 | 점 클릭 시 해당 측정으로 focus를 이동합니다 |

**관리 한계선은 그리지 않습니다.** 이상 판정은 이미 `anomalyCfg`의 활성 방법에
따라 점 색상으로 표현되고 있으며, 여기에 전역 밴드를 겹치면 두 가지 이유로
어긋납니다. 첫째, `anomalyCfg`의 기본 방법은 `range`(%)이므로 σ 기반 한계선은
기본 상태에서 아무것도 구동하지 않는 설정이 됩니다. 둘째, `peer.ts`의 판정은
각 점을 나머지 점들의 leave-one-out 중심과 비교하므로 전역 평균 ± kσ 직선으로는
재현할 수 없습니다. 밴드 안쪽의 붉은 점이 발생하여 두 표시를 모두 신뢰할 수
없게 되므로, 이 화면은 점 색상 하나만을 이상 판정 표현으로 사용합니다.

잔차 모드에서는 평균뿐 아니라 밴드의 `min`과 `max`도 함께 세트 기준만큼
이동시킵니다. 평균만 Δ로 바꾸면 Δ 값의 선이 원시값 밴드 위에 놓입니다.

`eqp_id` 색 분리는 `SK_SITE`(10색)와 `SK_SITE_OVERFLOW`(회색)를 사용합니다.
장비가 10종을 넘으면 11번째부터 모두 같은 회색이 되어 구분이 사라지므로,
측정 수가 많은 상위 9개 장비에 고유색을 배정하고 나머지는 `기타`로 묶어 범례에
그렇게 표기합니다. 구분되지 않는 색을 여러 장비에 배정하지 않습니다.

점 클릭으로 focus를 옮기려면 클릭된 `msr`을 식별할 수 있어야 합니다.
`useEchart`의 `onClick`은 category **이름**만 전달하고, 이 화면의 라벨은
`eqp_id · timestamp`이므로 `msr`이 아닙니다. 따라서 `TimeSeriesChart.vue`에
`select` emit(`msr: string`)을 추가하고, 차트가 `dataIndex`로 자신의 `points`
배열을 되짚어 `msr`을 실어 보냅니다. `useEchart`의 공용 계약은 바꾸지 않습니다.

### 보기 2 — 분포

측정 하나당 상자 하나를 그립니다. 재료는 이미 `setFiles`에 있는 site row이며
추가 조회가 없습니다.

`components/ebeam/skewvoir/DistributionChart.vue`를 재사용합니다. 이 컴포넌트는
`groups`(`{ label, values }[]`)와 `mode='Box'`를 받아 그룹당 상자 하나를 그리고,
모든 원시 점을 결정적 jitter로 겹쳐 그리며, 각 category 라벨에 N을 함께
표기합니다.

| 요소 | 내용 |
| --- | --- |
| 그룹 | 측정 하나당 그룹 하나. 라벨은 `eqp_id · timestamp` |
| 값 | `isMeasuredRow(row) && row.parameter === activeParam`인 site의 `cd_value` |
| 상자 | `DistributionChart`의 기존 five-number 요약 |
| 원시 점 | 기존 동작대로 전부 겹쳐 표시됩니다 |

다만 이 컴포넌트를 **무수정으로** 쓸 수는 없습니다. 현재 box 축은
`axisLabel: { interval: 0 }`이며 회전, `hideOverlap`, `dataZoom`이 없습니다.
기존 호출부는 그룹 수가 적지만 이 화면은 최대 30개 그룹에 측정당 수십 개의
원시 점을 올립니다. 따라서 `DistributionChart`에 **선택적 prop**을 추가해 축
라벨 회전과 `dataZoom`을 켤 수 있게 하고, 기본값은 현재 동작으로 두어 기존
호출부(`dashboard/Distribution.vue`, `views/Correlation.vue`)의 렌더링을 바꾸지
않습니다.

site 수가 적은 측정에 대한 별도 축약 규칙은 두지 않습니다. 모든 원시 점이 상자
위에 겹쳐 그려지므로 값이 3개인 상자는 점 3개와 함께 표시되어 근거가 얇다는
사실이 드러납니다. 값이 4개 미만인 측정의 수는 패널 meta에 표시합니다.

### 보기 3 — 장비 skew

| 요소 | 내용 |
| --- | --- |
| 행 | `eqp_id` 하나당 한 행 |
| 값 | 측정 수(n), 평균의 평균, 세트 기준 대비 offset, 해당 장비 평균들의 σ |
| 표시 | offset 점과 ±σ 구간을 가로 구간 도표로 표시하고 수치 표를 병기합니다 |
| 정렬 | offset 절대값 내림차순 — 가장 치우친 장비가 최상단에 옵니다 |
| 기준선 | 0 = 세트 기준 |

세트 기준은 세트 내 측정별 평균의 **중앙값**입니다. 이 값을 `consensus`로
표기하지 않습니다. 해당 용어는 이 프로젝트에서 통용되는 말이 아니며,
`skew-check` 화면의 fleet/consensus/residual은 모집단 수준에서 계산되는 값인
반면 이 화면의 기준은 사용자가 직접 고른 최대 30개 측정의 중앙값입니다. UI
문구는 `세트 기준`으로 고정합니다.

측정이 1개뿐인 장비의 σ는 `—`로 표시합니다. `sampleStd`는 `n < 2`에서 `0`을
반환하므로 그대로 쓰면 변동이 없다는 뜻으로 읽히지만, 실제로는 추정할 수 없는
상태입니다.

이 보기는 등급이나 판정을 내리지 않습니다. `n`, 평균, offset, σ만 제시하며
정상 / 이상 같은 상태값을 만들지 않습니다.

### 상시 패널 — Sequence Trend

기존 패널을 그대로 유지하되 최하단에 배치하며, 보기 전환의 영향을 받지
않습니다. 이 패널은 측정 **내부**의 측정 순서를 다루므로 위 세 보기의 측정
**간** 비교와 다른 축이며, 따라서 전환 대상에 포함하지 않고 위계만 낮춥니다.

## URL 계약

기존 `fdcaxis` 선례를 따라 화면 지역 상태도 URL에 실어 링크 재현성을
유지합니다.

| 키 | 값 | 기본 | 의미 |
| --- | --- | --- | --- |
| `tsview` | `trend` \| `dist` \| `skew` | `trend` | 활성 보기 |
| `tsx` | `time` \| `order` | `time` | 추이 보기의 x축 축척 |
| `tsb` | `raw` \| `resid` | `raw` | 추이 보기의 값 기준 |

파싱은 `utils/skewvoirAnalysis/routeQuery.ts`에 추가하고, 기록은 기존
`patchQuery`를 사용합니다. 파라미터 선택은 기존 `mp` 키를 사용하므로 신규 키가
없습니다.

`tsx`와 `tsb`는 추이 보기에만 적용되지만, 다른 보기로 전환했다가 돌아왔을 때
설정이 보존되도록 URL에 계속 유지합니다.

`msrs` 목록은 파생 단계에서 중복을 제거합니다. 현재 `parseMsrList`는 빈 값만
제거하고 중복은 남기므로, 같은 MSR이 두 번 들어오면 평균과 개수 집계가 그만큼
치우치고 30개 상한도 잠식합니다.

## 파생 로직

모든 **신규** 계산은 `utils/skewvoirAnalysis/timeSeries.ts`에 순수 함수로
배치합니다(기존 `DistributionChart`가 자체 계산하는 five-number 요약은 그대로
둡니다). 분위수와 Tukey 경계는 기존 `utils/stats.ts`의 `quantileSorted` /
`iqrFences`를 사용하며 다시 구현하지 않습니다.

```text
buildTrendSeries(setRows, setFiles, param, opts) -> TrendPoint[]
  ts 보존(유한한 timestamp만), eqpId 추가, baseline 적용
  raw   : value = mean,               band = [min, max]
  resid : value = mean - setBaseline, band = [min - setBaseline, max - setBaseline]
  판정은 기존 peerVerdicts + combineVerdicts 규칙을 그대로 사용

setBaseline(points) -> number
  측정별 평균의 중앙값. quantileSorted는 정렬을 하지 않으므로
  호출 전에 오름차순 정렬한다

buildSetDistributionGroups(setRows, setFiles, param) -> DistributionGroup[]
  측정당 그룹 하나. label = `eqp_id · timestamp`,
  values = 측정된 site의 cd_value 목록

buildToolSkew(points, baseline) -> ToolSkewRow[]
  eqp_id 별 n, 평균, offset, sigma(n<2이면 null). offset 절대값 내림차순

paramCoverage(setRows, setFiles) -> ParamCoverage[]
  세트 인지형 파라미터 목록과 보유 측정 수.
  분모는 파일이 적재된 측정 수

setIntegrity(msrList, setRows, setFiles) -> SetIntegrity
  { requested, resolved, loaded, unresolvedMsrs, recipeCount }
  무결성 알림과 커버리지 분모가 함께 읽는다
```

이 저장소에는 컴포넌트 마운트 테스트 하네스가 없으므로 `.vue` 파일 안의 로직은
검증할 수 없습니다. `utils/skewvoirAnalysis/`의 기존 유틸이 (`types.ts`를 제외한
모든 모듈이) `.test.ts`를 동반하는 이유가 이것이며, 이번 파생 로직도 같은 규칙을
따릅니다.

## 컴포넌트 구성

| 파일 | 상태 | 역할 |
| --- | --- | --- |
| `views/TimeSeries.vue` | 재작성 | 보기 전환, 헤더 컨트롤, 차트 슬롯, 무결성 알림, 빈 상태 |
| `TimeSeriesChart.vue` | 확장 | 시간/순서 축, 장비별 계열, 원시/잔차, `select` emit |
| `DistributionChart.vue` | 확장 | 축 라벨 회전과 `dataZoom`을 켜는 선택적 prop 추가(기본값은 현재 동작) |
| `timeseries/ToolSkewPanel.vue` | 신규 | 장비별 offset 구간 도표와 수치 표 |
| `timeseries/ParamCoverageSelect.vue` | 신규 | 세트 인지형 파라미터 선택기 |
| `SequenceTrend.vue` | 변경 없음 | 최하단 상시 유지 |
| `utils/skewvoirAnalysis/timeSeries.ts` | 신규 | 파생 로직 |
| `utils/skewvoirAnalysis/timeSeries.test.ts` | 신규 | 파생 로직 단위 테스트 |
| `utils/skewvoirAnalysis/routeQuery.ts` | 확장 | `tsview` / `tsx` / `tsb` 파서, `msrs` 중복 제거 |
| `composables/useSkewvoirRoute.ts` | 확장 | 신규 키 노출과 setter |
| `composables/useSkewvoirAnalysis.ts` | 확장 | 세트 기준 활성 파라미터 규칙, 신규 파생 결과 노출 |

차트 옵션은 커서 상태에 의존하지 않도록 구성합니다. `useEchart`는 `notMerge`로
다시 그리므로, 커서에 반응하는 옵션은 전체 재구성을 유발합니다.

## 예외 상황

| 상황 | 처리 |
| --- | --- |
| `scope !== 'set'` 또는 측정 2개 미만 | 기존 빈 상태를 유지하며 보기 전환 버튼을 표시하지 않습니다 |
| 이력에서 해소되지 않은 MSR | 무결성 알림에 개수를 표시합니다 |
| 파일 조회에 실패한 MSR | 커버리지 분모에서 제외하고 무결성 알림에 별도로 셉니다 |
| 적재된 파일에 해당 파라미터가 없음 | 해당 측정만 제외하고 패널 meta에 `n/총`을 표시합니다 |
| 이름 없는 settling MP | 기존 `isNamedParam` 규칙대로 추이 점의 판정을 생략합니다 |
| 세트가 단일 장비 | 장비 skew 보기는 `단일 장비 · 비교 대상 없음`을 표시하며 offset 0 행을 만들지 않습니다 |
| 측정이 1개인 장비 | σ를 `—`로 표시합니다 |
| timestamp가 몰려 있음 | 시간축에서는 겹침을 그대로 표시하고, `순서` 전환을 회피 수단으로 제공합니다 |
| timestamp를 파싱할 수 없음 | 시간축에서 제외하고 무결성 알림에 개수를 표시합니다. `순서` 축에서는 표시합니다 |
| `cd_value`가 null | `isMeasuredRow`로 제외합니다(`mp_number < 0`은 측정이 없는 지점입니다) |
| 측정된 site가 없는 측정 | 분포 그룹에서 제외하고 제외 수를 패널 meta에 표시합니다 |
| 잔차 모드 | y축 이름을 `Δ vs 세트 기준 (unit)`으로 바꾸며, 밴드도 함께 이동합니다 |
| `msrs`에 중복 | 파싱 단계에서 제거합니다 |
| 알 수 없는 `tsview` 값 | `trend`로 보정합니다(기존 `parseView` 방식과 동일) |

## 검증 한계

집에서 확인할 수 없는 항목을 명시합니다. 이 화면의 판단 근거가 되는 값들이므로
사무실 확인 대상으로 남깁니다.

| 항목 | 내용 |
| --- | --- |
| 장비 효과 | mock의 CD 값은 `_health(msr)`로만 결정되고 `eqp_id`가 개입하지 않습니다. 따라서 집에서는 장비 skew 보기의 **배선**만 확인할 수 있고 판독 자체는 확인할 수 없습니다 |
| 단위 일관성 | `MsrParamSummary.unit`은 제약 없는 문자열이며, 세트 내 측정들이 같은 파라미터에 같은 단위를 쓰는지는 사무실에서만 확인됩니다 |
| timestamp 형식 | 사무실 어댑터는 offset 없는 KST 문자열을 그대로 전달하므로 브라우저 파싱이 로케일에 좌우될 수 있습니다. 시간축 도입으로 이 문제의 영향이 정렬에서 **위치**로 커집니다 |

## 알려진 선행 이슈

이번 변경으로 생기는 문제는 아니지만 이 화면에서 드러나므로 기록합니다.

`useSkewvoirAnalysis.ts`의 세트 적재 watcher는 요청 세대 가드가 없어, 늦게
도착한 이전 요청이 최신 결과를 덮어쓸 수 있습니다. 실패 시에도 이전 map을
유지하며 오류 상태를 노출하지 않으므로, `setPending`이 false인 채로 오래된
데이터가 보일 수 있습니다. 이번 범위에서는 고치지 않고 별도 항목으로 둡니다.

## 테스트

| 대상 | 방법 |
| --- | --- |
| 파생 로직 | `npm test`(`node --test`)로 `timeSeries.test.ts` 실행 |
| URL 파서 | 기존 `routeQuery.test.ts`에 신규 키와 중복 제거 케이스를 추가합니다 |
| 활성 파라미터 규칙 | `scope=set` 완화와 `setFiles` 미적재 예외를 회귀 테스트로 고정합니다 |
| 타입 | `npm run typecheck` |
| 린트 | `npm run lint`, 문서 변경 시 `npm run lint:md` |
| backend | 변경이 없으나 `.venv/bin/python -m pytest -q`로 무영향을 확인합니다 |
| 화면 | `verify` 스킬로 Flask :5050 + Nuxt :3000 기동 후 검색 → 다중 선택 → Time-Series 경로를 직접 확인합니다 |

단위 테스트가 다뤄야 할 항목은 다음과 같습니다.

- 세트 기준 중앙값이 정렬되지 않은 입력에서도 정확할 것(짝수 개수 포함)
- 잔차 모드에서 평균과 밴드가 같은 양만큼 이동할 것
- 단일 장비 세트에서 skew 행이 생성되지 않는 것
- 측정이 1개인 장비의 σ가 `0`이 아니라 `null`인 것
- 빈 세트와 측정 1개 세트
- 파라미터 커버리지의 분모가 적재된 파일 수일 것
- 파싱 불가 timestamp가 시간축에서 제외되고 개수로 보고될 것
- 중복 `msrs`가 제거될 것
- 세트 정렬이 커버리지 → MP 순서 → 이름 순으로 결정론적일 것
- `tsview` / `tsx` / `tsb`의 기본값과 잘못된 값 보정

## 범위 제외

- FDC 파라미터와의 시간축 상관 분석
- 좌측 레일로의 파라미터 선택기 승격(Position Stack / Correlation / Gallery의
  동일한 제약은 이번 범위에서 다루지 않습니다)
- `TREND_LIMIT` 30 상한 변경
- backend 엔드포인트 및 provider 어댑터 변경
- 보기 간 dataZoom 상태 보존
- 검색 단계에서의 계열 혼재 차단(이번 변경은 결과를 알릴 뿐 선택을 막지 않습니다)
- 세트 적재 watcher의 요청 세대 가드
