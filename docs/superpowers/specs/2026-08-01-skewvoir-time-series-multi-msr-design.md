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
구성만 다룹니다.

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
| 파라미터 선택 | 이 화면 전용의 세트 인지형 선택기를 상단에 배치합니다 |
| Sequence Trend | 보기 전환과 무관하게 최하단에 상시 유지합니다 |
| FDC 상관 | 이번 범위에서 제외합니다 |

세 보기를 동시에 적층하지 않고 버튼 전환으로 두는 것은 확정된 선택입니다.
수용하는 절충은 수준(평균)과 산포(분포)를 한 화면에서 동시에 볼 수 없다는
점이며, 얻는 것은 각 보기가 자신에게 맞는 축을 온전히 쓸 수 있다는 점입니다.
특히 분포 보기가 자체 category 축을 가지므로 ECharts 기본 boxplot을 그대로
사용할 수 있습니다.

## 화면 구성

읽기 순서는 `파라미터 선택기 → 보기 전환 버튼 → 활성 차트 → Sequence Trend`입니다.

### 파라미터 선택기

화면 최상단에 배치하며, 활성 파라미터를 이 화면에서 직접 전환합니다.

기존 `ParamNav`를 그대로 재사용하지 않습니다. `ParamNav`가 사용하는
`availableParams`는 focus 파일 한 개에서 파생되므로, 서로 다른 recipe가 섞인
세트에서는 세트 대부분이 보유하지 않은 파라미터를 제시할 수 있습니다. 이
경우 추이에서 해당 측정들이 조용히 제외됩니다.

따라서 이 선택기는 세트 전체를 기준으로 목록을 구성하고 각 항목에 커버리지를
함께 표시합니다.

| 표시 | 의미 |
| --- | --- |
| `WAFER · 28/30` | 세트 30개 측정 중 28개가 이 파라미터를 보유합니다 |

정렬은 기존 `sortByRowMpOrder`를 따르며, 이름 없는 settling MP는
`UNNAMED_PARAM_LABEL`(`-`)로 표시하되 기본 선택 대상에서는 제외합니다. 선택
결과는 기존 `mp` URL 키에 `ws.setParam()`으로 기록하므로 새로운 URL 계약이
생기지 않습니다.

기본값은 하드코딩된 `WAFER`가 아닙니다. 현재 규칙(`activeParam`)대로 URL `mp`를
우선 존중하고, 없으면 첫 번째 이름 있는 파라미터로 결정합니다.

### 보기 전환 버튼

파라미터 선택기 바로 아래에 탭 형태로 배치합니다.

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
| 계열 분리 | `eqp_id` 별로 색을 분리하며, 색상은 `SK_SITE` 범주형 팔레트와 `SK_SITE_OVERFLOW`를 사용합니다 |
| 관리 한계선 | 세트 평균 ± `anomalyCfg.stddev.watchK` / `abnormalK` |
| 점 색상 | 기존 `combineVerdicts` 판정(정상 / 주의 / 이상 / 판정 불가) |
| 상호작용 | 점 클릭 시 `setFocusedMsr`로 focus를 이동합니다 |

관리 한계선의 배수는 기존 `anomalyCfg`를 그대로 사용합니다. 밴드가 ±3σ인데
점 색상은 ±2σ 기준으로 칠해지면 밴드 안쪽의 붉은 점이 발생하여 두 표시를
모두 신뢰할 수 없게 되므로, 이 화면은 하나의 이상 판정 어휘만 사용합니다.

### 보기 2 — 분포

측정 하나당 상자 하나를 그립니다. 재료는 이미 `setFiles`에 있는 site row이며
추가 조회가 없습니다.

**신규 차트 컴포넌트를 만들지 않습니다.** 기존
`components/ebeam/skewvoir/DistributionChart.vue`가 `groups`
(`{ label, values }[]`)와 `mode='Box'`를 받아 그룹당 상자 하나를 그리고, 모든
원시 점을 결정적 jitter로 겹쳐 그리며, 각 category 라벨에 N을 함께 표기합니다.
이 화면에 필요한 것은 세트를 그룹 목록으로 바꾸는 파생 함수 하나뿐입니다.

| 요소 | 내용 |
| --- | --- |
| 그룹 | 측정 하나당 그룹 하나. 라벨은 `eqp_id · timestamp` |
| 값 | `isMeasuredRow(row) && row.parameter === activeParam`인 site의 `cd_value` |
| 상자 | `DistributionChart`의 기존 five-number 요약 |
| 원시 점 | 기존 동작대로 전부 겹쳐 표시됩니다 |

site 수가 적은 측정에 대한 별도 축약 규칙을 두지 않습니다. `DistributionChart`가
이미 모든 원시 점을 상자 위에 겹쳐 그리므로, 값이 3개인 상자는 점 3개와 함께
표시되어 근거가 얇다는 사실이 화면에 드러납니다. 표식을 따로 낮추는 것보다
이 편이 정직하며 공용 컴포넌트를 수정하지 않아도 됩니다. 다만 값이 4개 미만인
측정의 수는 패널 meta에 함께 표시합니다.

### 보기 3 — 장비 skew

| 요소 | 내용 |
| --- | --- |
| 행 | `eqp_id` 하나당 한 행 |
| 값 | 측정 수(n), 평균의 평균, 세트 기준 대비 offset, 해당 장비 평균들의 σ |
| 표시 | offset 점과 ±σ 구간을 가로 구간 도표로 표시하고 수치 표를 병기합니다 |
| 정렬 | offset 절대값 내림차순 — 가장 치우친 장비가 최상단에 옵니다 |
| 기준선 | 0 = 세트 기준 |

세트 기준은 세트 내 측정별 평균의 **중앙값**입니다.

이 값을 `consensus`로 표기하지 않습니다. 해당 용어는 이 프로젝트에서 통용되는
말이 아니며, `skew-check` 화면의 fleet/consensus/residual은 모집단 수준에서
계산되는 값인 반면 이 화면의 기준은 사용자가 직접 고른 최대 30개 측정의
중앙값입니다. UI 문구는 `세트 기준`으로 고정합니다.

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

## 파생 로직

모든 계산은 `utils/skewvoirAnalysis/timeSeries.ts`에 순수 함수로 배치합니다.
분위수와 Tukey 경계는 기존 `utils/stats.ts`의 `quantileSorted` / `iqrFences`를
사용하며 다시 구현하지 않습니다.

```text
buildTrendSeries(setRows, setFiles, param, opts) -> TrendPoint[]
  ts 보존, eqpId 추가, baseline 적용
  raw   : value = summary.mean
  resid : value = summary.mean - setBaseline
  판정은 기존 peerVerdicts + combineVerdicts 규칙을 그대로 사용

setBaseline(points) -> number
  측정별 평균의 중앙값

buildSetDistributionGroups(setRows, setFiles, param) -> DistributionGroup[]
  측정당 그룹 하나. label = `eqp_id · timestamp`,
  values = 측정된 site의 cd_value 목록

buildToolSkew(points, baseline) -> ToolSkewRow[]
  eqp_id 별 n, 평균, offset, σ. offset 절대값 내림차순 정렬

controlLimits(points, anomalyCfg) -> { center, watchLo, watchHi, abnormalLo, abnormalHi }

paramCoverage(setRows, setFiles) -> ParamCoverage[]
  세트 인지형 파라미터 목록과 보유 측정 수
```

이 저장소에는 컴포넌트 마운트 테스트 하네스가 없으므로 `.vue` 파일 안의 로직은
검증할 수 없습니다. `utils/skewvoirAnalysis/`의 기존 15개 유틸이 모두 `.test.ts`를
동반하는 이유가 이것이며, 이번 파생 로직도 같은 규칙을 따릅니다.

## 컴포넌트 구성

| 파일 | 상태 | 역할 |
| --- | --- | --- |
| `views/TimeSeries.vue` | 재작성 | 보기 전환, 헤더 컨트롤, 차트 슬롯, 빈 상태 처리 |
| `TimeSeriesChart.vue` | 확장 | 시간/순서 축, 장비별 계열, 원시/잔차, 관리 한계선, 클릭 focus 이동 |
| `DistributionChart.vue` | 변경 없음 | 분포 보기에서 `groups` + `mode='Box'`로 재사용 |
| `timeseries/ToolSkewPanel.vue` | 신규 | 장비별 offset 구간 도표와 수치 표 |
| `timeseries/ParamCoverageSelect.vue` | 신규 | 세트 인지형 파라미터 선택기 |
| `SequenceTrend.vue` | 변경 없음 | 최하단 상시 유지 |
| `utils/skewvoirAnalysis/timeSeries.ts` | 신규 | 파생 로직 |
| `utils/skewvoirAnalysis/timeSeries.test.ts` | 신규 | 파생 로직 단위 테스트 |
| `utils/skewvoirAnalysis/routeQuery.ts` | 확장 | `tsview` / `tsx` / `tsb` 파서 |
| `composables/useSkewvoirRoute.ts` | 확장 | 신규 키 노출과 setter |
| `composables/useSkewvoirAnalysis.ts` | 확장 | 신규 파생 결과 노출 |

차트 옵션은 커서 상태에 의존하지 않도록 구성합니다. `useEchart`는 `notMerge`로
다시 그리므로, 커서에 반응하는 옵션은 전체 재구성을 유발합니다.

## 예외 상황

| 상황 | 처리 |
| --- | --- |
| `scope !== 'set'` 또는 측정 2개 미만 | 기존 빈 상태를 유지하며 보기 전환 버튼을 표시하지 않습니다 |
| 일부 측정에 해당 파라미터가 없음 | 해당 측정은 제외하고, 패널 meta에 `n/총`을 표시합니다 |
| 이름 없는 settling MP | 기존 `isNamedParam` 규칙대로 판정을 생략하며, 장비 skew 판정도 생략합니다 |
| 세트가 단일 장비 | 장비 skew 보기는 `단일 장비 · 비교 대상 없음`을 표시하며 offset 0 행을 만들지 않습니다 |
| timestamp가 몰려 있음 | 시간축에서는 겹침을 그대로 표시하고, `순서` 전환을 회피 수단으로 제공합니다 |
| `cd_value`가 null | `isMeasuredRow`로 제외합니다(`mp_number < 0`은 측정이 없는 지점입니다) |
| 잔차 모드 | y축 이름을 `Δ vs 세트 기준 (unit)`으로 바꾸며, 장비 skew 보기는 이미 offset이므로 변화가 없습니다 |
| 측정된 site가 없는 측정 | 분포 그룹에서 제외하고 제외 수를 패널 meta에 표시합니다 |
| 알 수 없는 `tsview` 값 | `trend`로 보정합니다(기존 `parseView` 방식과 동일) |

## 테스트

| 대상 | 방법 |
| --- | --- |
| 파생 로직 | `npm test`(`node --test`)로 `timeSeries.test.ts` 실행 |
| URL 파서 | 기존 `routeQuery.test.ts`에 신규 키 파싱과 보정 케이스를 추가합니다 |
| 타입 | `npm run typecheck` |
| 린트 | `npm run lint`, 문서 변경 시 `npm run lint:md` |
| backend | 변경이 없으나 `.venv/bin/python -m pytest -q`로 무영향을 확인합니다 |
| 화면 | `verify` 스킬로 Flask :5050 + Nuxt :3000 기동 후 검색 → 다중 선택 → Time-Series 경로를 직접 확인합니다 |

단위 테스트가 다뤄야 할 항목은 다음과 같습니다.

- 잔차 계산과 세트 기준 중앙값(짝수 개수 세트 포함)
- 단일 장비 세트에서 skew 행이 생성되지 않는 것
- 빈 세트와 측정 1개 세트
- 파라미터를 일부만 보유한 세트의 커버리지 집계
- 측정된 site가 없는 측정이 분포 그룹에서 제외되는 것
- `tsview` / `tsx` / `tsb`의 기본값과 잘못된 값 보정

## 범위 제외

- FDC 파라미터와의 시간축 상관 분석
- 좌측 레일로의 파라미터 선택기 승격(Position Stack / Correlation / Gallery의
  동일한 제약은 이번 범위에서 다루지 않습니다)
- `TREND_LIMIT` 30 상한 변경
- backend 엔드포인트 및 provider 어댑터 변경
- 보기 간 dataZoom 상태 보존
