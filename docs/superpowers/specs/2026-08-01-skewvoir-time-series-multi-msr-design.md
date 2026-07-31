# Skewvoir Time-Series 다중 MSR 분석 화면 설계

Date: 2026-08-01

## 목적

검색 화면(`skewvoir/index`)에서 여러 MSR을 선택해 분석으로 진입했을 때 열리는
`Time-Series` 보기를 실제 분석이 가능한 화면으로 확장합니다.

현재 이 보기는 다음 두 가지 질문만 답합니다.

- 활성 파라미터 한 개의 측정별 평균이 어떻게 변했는가
- focus 측정 한 개의 sequence 추이는 어떤 모양인가

이번 변경은 다음 세 가지 질문에 각각 고정된 자리를 부여합니다.

| 질문 | 담당 패널 |
| --- | --- |
| 장비 간 skew — 장비들이 서로 다르게 측정하고 있는가 | 장비 skew |
| 시간에 따른 drift — 세트 전체가 한 방향으로 흐르고 있는가 | 추이 |
| 측정별 분포 — 특정 wafer만 산포가 커졌는가 | 분포 |

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
| 화면 구조 | 하나의 x축을 공유하는 3개 패널(추이 / 분포 / 장비 skew)을 세로로 적층하고, x축을 공유하지 않는 기존 Sequence Trend를 최하단에 유지합니다 |
| x축 | 기본은 실제 시간축이며, 헤더의 `시간 / 순서` 전환으로 등간격 전환이 가능합니다 |
| skew 기준 | 원시값과 잔차(residual)를 헤더 전환으로 모두 제공합니다 |
| 장비 skew | 독립 패널로 배치합니다 |
| 파라미터 선택 | 이 화면 전용의 세트 인지형 선택기를 상단에 배치합니다 |
| FDC 상관 | 이번 범위에서 제외합니다 |

## 화면 구성

읽기 순서는 `파라미터 선택기 → 추이 → 분포 → 장비 skew → Sequence Trend`입니다.

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

### 패널 1 — 추이

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

### 패널 2 — 분포

측정 하나당 상자 하나를 그립니다. 재료는 이미 `setFiles`에 있는 site row이며
추가 조회가 없습니다.

| 요소 | 내용 |
| --- | --- |
| 대상 row | `isMeasuredRow(row) && row.parameter === activeParam` |
| 상자 | q1 / median / q3 |
| 수염 | Tukey 1.5 × IQR |
| 이상점 | 수염 밖 site를 개별 점으로 표시 |
| x 위치 | 패널 1과 동일한 x 좌표를 사용합니다 |

x 좌표는 패널 1과 **같은 파생 결과**에서 가져옵니다. 두 패널이 각각 정렬을
수행하면 상자와 평균점이 어긋날 수 있고, 이는 적층 배치의 목적 자체를
무너뜨립니다.

ECharts `boxplot` 계열은 category 축을 전제하므로 시간축 위에 배치할 수
없습니다. 따라서 `custom` 계열과 `renderItem`으로 상자를 직접 그립니다.
`renderItem`은 좌표계에 의존하지 않으므로 시간축과 순서축 모두에서 동작합니다.
구현이 과도해질 경우 `candlestick` 계열(시간축 지원, q1/q3/수염 매핑 가능,
median은 별도 표식 필요)을 대안으로 둡니다.

### 패널 3 — 장비 skew

| 요소 | 내용 |
| --- | --- |
| 행 | `eqp_id` 하나당 한 행 |
| 값 | 측정 수(n), 평균의 평균, 세트 기준 대비 offset, 해당 장비 평균들의 σ |
| 표시 | offset 점과 ±σ 구간을 가로 구간 도표로 표시하고 수치 표를 병기합니다 |
| 정렬 | offset 절대값 내림차순 — 가장 치우친 장비가 최상단에 옵니다 |
| 기준선 | 0 = 세트 기준 |

세트 기준은 세트 내 측정별 평균의 **중앙값**입니다.

이 값을 `consensus`로 표기하지 않습니다. `skew-check` 화면의
fleet/consensus/residual은 모집단 수준에서 계산되는 값인 반면, 이 화면의 기준은
사용자가 직접 고른 최대 30개 측정의 중앙값입니다. 같은 단어를 쓰면 이 화면이
갖지 않은 통계적 엄밀성을 암시하게 되므로, UI 문구는 `세트 기준`으로 고정합니다.

### 패널 4 — Sequence Trend

기존 패널을 그대로 유지하되 최하단으로 이동합니다. 이 패널은 측정 **내부**의
측정 순서를 다루므로 위 세 패널의 측정 **간** 비교와 다른 축이며, 따라서
제거하지 않고 위계만 낮춥니다.

## URL 계약

기존 `fdcaxis` 선례를 따라 화면 지역 상태도 URL에 실어 링크 재현성을
유지합니다.

| 키 | 값 | 기본 | 의미 |
| --- | --- | --- | --- |
| `tsx` | `time` \| `order` | `time` | x축 축척 |
| `tsb` | `raw` \| `resid` | `raw` | 값 기준 |

파싱은 `utils/skewvoirAnalysis/routeQuery.ts`에 `parseTsAxis` / `parseTsBaseline`로
추가하고, 기록은 기존 `patchQuery`를 사용합니다. 파라미터 선택은 기존 `mp`
키를 사용하므로 신규 키가 없습니다.

## 파생 로직

모든 계산은 `utils/skewvoirAnalysis/timeSeries.ts`에 순수 함수로 배치합니다.

```text
buildTrendSeries(setRows, setFiles, param, opts) -> TrendPoint[]
  ts 보존, eqpId 추가, baseline 적용
  raw   : value = summary.mean
  resid : value = summary.mean - setBaseline
  판정은 기존 peerVerdicts + combineVerdicts 규칙을 그대로 사용

setBaseline(points) -> number
  측정별 평균의 중앙값

buildDistributions(setRows, setFiles, param) -> BoxPoint[]
  측정별 q1 / median / q3 + Tukey 1.5 IQR 수염 + 이상점

buildToolSkew(points, baseline) -> ToolSkewRow[]
  eqp_id 별 n, 평균, offset, σ. |offset| 내림차순 정렬

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
| `views/TimeSeries.vue` | 재작성 | 패널 조립, 헤더 컨트롤, 빈 상태 처리 |
| `TimeSeriesChart.vue` | 확장 | 시간/순서 축, 장비별 계열, 원시/잔차, 관리 한계선, 클릭 focus 이동 |
| `timeseries/DistributionStrip.vue` | 신규 | 측정별 상자 그림 |
| `timeseries/ToolSkewPanel.vue` | 신규 | 장비별 offset 구간 도표와 수치 표 |
| `timeseries/ParamCoverageSelect.vue` | 신규 | 세트 인지형 파라미터 선택기 |
| `SequenceTrend.vue` | 변경 없음 | 최하단 유지 |
| `utils/skewvoirAnalysis/timeSeries.ts` | 신규 | 파생 로직 |
| `utils/skewvoirAnalysis/timeSeries.test.ts` | 신규 | 파생 로직 단위 테스트 |
| `utils/skewvoirAnalysis/routeQuery.ts` | 확장 | `tsx` / `tsb` 파서 |
| `composables/useSkewvoirRoute.ts` | 확장 | `tsAxis` / `tsBaseline` 노출 |
| `composables/useSkewvoirAnalysis.ts` | 확장 | 신규 파생 결과 노출 |

차트 옵션은 커서 상태에 의존하지 않도록 구성합니다. `useEchart`는 `notMerge`로
다시 그리므로, 커서에 반응하는 옵션은 전체 재구성을 유발합니다.

## 예외 상황

| 상황 | 처리 |
| --- | --- |
| `scope !== 'set'` 또는 측정 2개 미만 | 기존 빈 상태를 유지합니다 |
| 일부 측정에 해당 파라미터가 없음 | 해당 측정은 제외하고, 패널 meta에 `n/총`을 표시합니다 |
| 이름 없는 settling MP | 기존 `isNamedParam` 규칙대로 판정을 생략하며, 장비 skew 판정도 생략합니다 |
| 세트가 단일 장비 | 장비 skew 패널은 `단일 장비 · 비교 대상 없음`을 표시하며 offset 0 행을 만들지 않습니다 |
| timestamp가 몰려 있음 | 시간축에서는 겹침을 그대로 표시하고, `순서` 전환을 회피 수단으로 제공합니다 |
| `cd_value`가 null | `isMeasuredRow`로 제외합니다(`mp_number < 0`은 측정이 없는 지점입니다) |
| 잔차 모드 | y축 이름을 `Δ vs 세트 기준 (unit)`으로 바꾸며, 장비 skew 패널은 이미 offset이므로 변화가 없습니다 |
| site가 4개 미만인 측정 | 상자 대신 원시 점을 표시합니다 |

site가 4개 미만일 때 상자를 그리지 않는 이유는, 3개 값으로 만든 사분위 상자가
실제로는 근거가 거의 없는데도 요약된 형태로 보이기 때문입니다. 데이터를
왜곡하는 것보다 표식을 낮추는 편이 정직합니다.

## 테스트

| 대상 | 방법 |
| --- | --- |
| 파생 로직 | `npm test`(`node --test`)로 `timeSeries.test.ts` 실행 |
| 타입 | `npm run typecheck` |
| 린트 | `npm run lint`, 문서 변경 시 `npm run lint:md` |
| backend | 변경이 없으나 `.venv/bin/python -m pytest -q`로 무영향을 확인합니다 |
| 화면 | `verify` 스킬로 Flask :5050 + Nuxt :3000 기동 후 검색 → 다중 선택 → Time-Series 경로를 직접 확인합니다 |

단위 테스트가 다뤄야 할 항목은 다음과 같습니다.

- 손으로 계산한 고정 입력에 대한 사분위수와 Tukey 경계
- 잔차 계산과 세트 기준 중앙값
- 단일 장비 세트에서 skew 행이 생성되지 않는 것
- 빈 세트와 측정 1개 세트
- site 4개 미만인 측정의 상자 축약
- 파라미터 커버리지 집계

## 범위 제외

- FDC 파라미터와의 시간축 상관 분석
- 좌측 레일로의 파라미터 선택기 승격(Position Stack / Correlation / Gallery의
  동일한 제약은 이번 범위에서 다루지 않습니다)
- `TREND_LIMIT` 30 상한 변경
- backend 엔드포인트 및 provider 어댑터 변경
