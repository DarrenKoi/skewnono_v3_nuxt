# 스큐보아 웨이퍼 분석 방법 연구

- 작성일: 2026-07-15
- 대상: Skewvoir 검색 및 분석 워크스페이스
- 범위: MSR 측정 데이터와 장비·하드웨어 데이터를 이용한 분석 방법 연구
- 상태: 연구 제안입니다. UI 구현 계획이나 공식 판정 규칙은 아닙니다.

## 1. 결론

Skewvoir 분석 워크스페이스는 선택한 MSR 수에 따라 같은 차트를 비우거나 채우는
구조가 아니라, **서로 다른 엔지니어링 질문에 답하는 두 가지 분석 모드**가 되어야
합니다.

- **단일 MSR**은 “이 측정은 유효하며, 웨이퍼 안에서 어디가 다르고, 측정 중
  장비 신호는 어떻게 움직였는가?”에 답해야 합니다.
- **다중 MSR**은 “비교 가능한 측정들 사이에서 무엇이 이동·확산·변화했고,
  어느 장비·lot·시점·하드웨어 신호와 함께 나타났는가?”에 답해야 합니다.
- 다중 분석은 차트보다 먼저 **비교 가능성 검사**를 수행해야 합니다. 최소한
  recipe, parameter, unit, 측정 방법·조건, 좌표계와 site layout이 호환되지 않으면
  한 통계량으로 합치지 않고 분리하거나 `비교 불가`로 표시해야 합니다.
- 사용자가 고른 MSR 집합은 원인 증명이나 공식 공정 판정 집단이 아니라
  **탐색 집합**입니다. 관리 한계와 기준선은 임의 선택 집합에서 다시 계산하지 않고,
  별도로 승인·동결된 역사 기준선에서 가져와야 합니다.
- CD와 FDC가 같이 움직이는 것은 원인 후보를 좁히는 증거일 뿐입니다. 상관은
  인과를 증명하지 않으며, recipe·장비·시간에 의한 공통 변화와 데이터 결합 오류를
  먼저 배제해야 합니다. NIST도 산점도는 연관을 보여줄 뿐 인과를 증명하지 못한다고
  명시합니다([NIST, Scatter Plot](https://www.itl.nist.gov/div898/handbook/eda/section3/eda33q.htm)).

가장 가치가 높은 1차 개편은 다음 순서입니다.

1. 선택 모드와 비교 가능성 서명을 분석 계약으로 만듭니다.
2. 단일 MSR에는 커버리지, 공간 잔차, sequence와 동적 FDC, 정렬·실패 증거를
   제공합니다.
3. 다중 MSR에는 reference/delta map, 시간 추이, 장비·lot 층화, CD↔하드웨어
   결합 분석을 제공합니다.
4. 충분한 역사 데이터와 검토 라벨이 쌓인 뒤 variance component, PCA/MSPC,
   wafer signature, virtual metrology를 연구 기능으로 추가합니다.

## 2. 현재 저장소에서 확인되는 분석 자산

### 2.1 데이터 단위와 필드

| 데이터 | 한 행 또는 문서의 단위 | 현재 주요 필드 | 즉시 가능한 분석 |
| --- | --- | --- | --- |
| `meas_hist` | 장비가 lot에 recipe를 실행한 1회 측정 | `fab_name`, `eqp_id`, `eqp_model_cd`, `lot_id`, `class_name`, `recipe_name`, `timestamp`, `start_time`, `end_time`, `meastime`, `msr`, `msr_check`, `align_fail`, image 실패 수·비율 | 검색 집단 구성, 시간축, 장비·lot 층화, 실행·실패 품질 |
| `msr_file.rows` | MSR 안의 sequence × parameter 측정값 | `sequence`, chip/stage 좌표, `mp_number`, `parameter`, nullable `cd_value`, image, mag/vac/pixel, addressing·measurement score, 방법·object·kind | 웨이퍼 맵, 공간·반경·sequence 분석, paired-site 파라미터 관계, 이미지 연결 |
| `MsrFileResponse` | MSR 1건의 정규화된 상세 | parameter 요약, `fixed_fdc`, sequence별 `dynamic_fdc`, 실행 정보, alignment image·offset·score | 단일 MSR 요약, 측정 내 FDC 추이, 정렬 증거, 다중 MSR feature table |
| Hardware API `docs` | 장비 서비스의 시계열 raw document | BSM, resolution center, FDC와 timestamp | 측정 전·중·후 장비 상태 feature, 장기 drift, maintenance 전후 비교 |
| Hardware API `settings` | 특정 기준일의 장비별 설정 snapshot | MDC, SCE의 선택 장비와 동일 fab 장비 설정 | 장비 간 설정 편차, MSR 시점의 as-of 설정 결합 |
| BM/PM table | 장비 정비 작업 | 작업 시작·종료, category, engineer note | 정비 전후 구간 표시, regime 분할, 해석 문맥 |

저장소 근거는 [meas_hist 설명](../../datatables/meas_hist.txt),
[msr_file 설명](../../datatables/msr_file.txt),
[MSR pickle 구조](../../datatables/msr_file_pickle.txt),
[프런트 MSR 계약](../../../front-dev-home/app/composables/useMsrFileApi.ts),
[Hardware API 계약](../../api-contracts/hardware.yaml)에 있습니다.

### 2.2 현재 화면 계약과 빈틈

현재 검색은 단건을 열면 Dashboard로, 다건을 열면 Time-Series로 진입합니다.
이 방향은 타당합니다. 그러나 비교 파일은 현재 Time-Series와 Position Stack에서만
지연 로드하며, Correlation과 Gallery는 focus MSR만 사용합니다. 따라서 왼쪽의 같은
다섯 메뉴가 단건·다건에서 실제로 같은 분석 범위를 의미하지 않습니다.

또한 다음 한계가 있습니다.

- 단일 MSR로 Position Stack을 열면 wafer-to-wafer σ가 0이므로 분석 가치가 거의
  없습니다. 단건에서는 같은 메뉴를 `공간 진단`으로 바꾸는 편이 적절합니다.
- `FdcAnalysis.vue`와 FDC 차트 자산은 존재하지만 현재 Workspace에 연결되어 있지
  않습니다.
- Phase 1 mock은 숨겨진 `health` 값으로 CD와 FDC drift를 함께 생성합니다.
  따라서 mock에서 보이는 CD↔FDC 상관은 방법 검증 근거가 될 수 없습니다.
- `MsrFileResponse.health`는 mock 내부 생성값이며 office 데이터 계약이 아닙니다.
- `spm_dict`는 현재 seeded parabola 자리표시자이므로 실제 신호 계약 전에는 분석에
  사용하면 안 됩니다.
- vendor의 addressing·measurement score는 표시·모니터링할 수 있지만, 의미와
  보정이 확인되지 않은 상태에서 장비·recipe 간 절대 비교나 판정에 사용하면 안
  됩니다.

## 3. 선택 모드별 워크스페이스 역할

### 3.1 같은 메뉴, 다른 질문

| 페이지 | 단일 MSR 선택 | 다중 MSR 선택 |
| --- | --- | --- |
| Dashboard | **측정 개요**: 커버리지, 실패, parameter별 중심·산포, 실행 조건, alignment, 당시 장비 문맥 | **비교 집합 개요**: 호환성 검사, 구성 분포, 누락 행렬, parameter별 변화 범위, 장비·lot·기간별 요약 |
| 위치 비교 | **공간 진단**: raw map, 실패 위치, 반경·방향 profile, 공간 surface와 residual, sequence 경로 | **공간 비교**: reference median map, MSR별 delta map, site별 wafer-to-wafer variability, map similarity |
| Time-Series | **측정 내 순서 분석**: sequence별 CD와 dynamic FDC, alignment·실패 발생 순서 | **측정 간 시간 분석**: MSR별 level·spread·실패율·FDC feature, 장비별 층화, 관리도·EWMA, BM/PM overlay |
| 상관 / 분포 | **측정 내부 관계**: 같은 site의 parameter↔parameter, sequence별 CD↔dynamic FDC, 분포·잔차 | **측정 간 관계**: MSR 요약 CD↔fixed FDC·hardware feature, 장비·lot별 관계, variance decomposition, 제한된 multivariate 분석 |
| 이미지 갤러리 | 실패·site residual·score·위치 기준으로 한 MSR의 이미지 triage | 같은 site 또는 같은 signature를 MSR 간 나란히 비교하고 변화 순서로 정렬 |

다중 선택이지만 호환 가능한 MSR이 하나뿐이면 `다중`이라는 선택 수를 그대로 믿지
말고, 유효 비교 집단별로 분석을 나눠야 합니다. 반대로 단일 선택이라도 시스템이
자동으로 만든 승인된 historical peer가 있다면 `자동 기준선과 비교`를 별도 레이어로
제공할 수 있습니다. 이때 사용자 선택 집합과 자동 기준선을 시각적으로 구분해야 합니다.

### 3.2 비교 가능성 서명

각 MSR에 다음과 같은 `compatibility_signature`가 필요합니다.

```text
fab
+ tool family / model
+ recipe identity and revision
+ class / process / product-layer identity
+ parameter and unit
+ measurement method / object / kind
+ mag / vac / pixel condition
+ coordinate system and wafer size
+ site-layout hash
```

초기 정책은 다음과 같이 보수적으로 운영하는 것이 좋습니다.

- `recipe + revision + parameter + unit + layout`이 다르면 자동 합성을 금지합니다.
- tool ID는 분석 목적에 따라 다룹니다. 공정 추이는 같은 tool 내 stream으로 보고,
  tool matching은 tool을 의도적인 비교 요인으로 둡니다.
- layout이 일부만 겹치면 교집합 site 수와 coverage를 표시하고, reference/delta map은
  공통 site에서만 계산합니다.
- 단위 변환은 명시적 변환표와 원본 단위를 보존한 경우에만 허용합니다.
- 동일 이름의 parameter라도 측정 방법·배율·가속전압·pixel 조건이 다르면 별도
  stratum으로 취급합니다.

## 4. 단일 MSR에서 구축할 분석

### 4.1 측정 유효성·커버리지

가장 먼저 계산할 것은 이상 점수가 아니라 **무엇이 실제로 측정되었는가**입니다.

- 시도 site 수, 유효 `cd_value` 수, 실패 수와 비율을 parameter별로 계산합니다.
- `msr_check`, `align_fail`, image 실패율, nullable `cd_value`, parse/schema 오류를
  분리해 보여줍니다.
- 누락을 0으로 바꾸지 않으며, 분모가 없거나 불명확하면 `평가 불가`로 둡니다.
- 실패 위치를 wafer map에 남겨 공간 군집인지 확인합니다.
- 실행 정보와 alignment offset·score·이미지를 함께 제공해 측정 결과를 신뢰할 수
  있는지 사람이 먼저 판단하게 합니다.

이 단계는 통계 모델보다 deterministic rule이 적합합니다. `실패`, `누락`, `판정
불가`를 하나의 health score에 평균내면 원인이 사라집니다.

### 4.2 공간 구조 분석

단일 MSR의 위치 페이지는 다음 레이어를 순차적으로 제공해야 합니다.

1. **Raw site map**: 측정값과 실패를 그대로 표시합니다.
2. **중심 보정 map**: parameter의 median 또는 승인 target을 뺀 signed residual을
   표시합니다. 서로 다른 nominal level의 map 비교에도 필요한 기초 feature입니다.
3. **반경 profile**: wafer 중심에서의 radius를 계산해 center-to-edge 추이를
   표시합니다. 단순 선형뿐 아니라 구간 median과 신뢰 가능한 site 수를 같이
   보여줍니다.
4. **방향·sector profile**: 좌표 원점과 notch 방향이 검증된 경우에만 각도별 편차를
   표시합니다.
5. **공간 surface와 residual**: distinct coordinate와 coverage가 충분하면 2차
   surface 또는 thin-plate spline을 적합하고, fitted surface와 국소 residual을
   분리합니다.

반도체 장비 fault가 wafer surface의 수준뿐 아니라 공간 pattern 변화로 나타날 수
있으며, Gardner 등은 fault-free target surface와 관측 surface를 thin-plate spline과
공간 signature metric으로 비교하는 방법을 실험했습니다
([Gardner et al., 1997](https://doi.org/10.1109/3476.650961)). 다만 Skewvoir에서는
표본 위치가 20~80개로 희소할 수 있으므로 spline은 탐색 레이어로 시작하고,
smoothing parameter와 성능을 historical holdout으로 검증해야 합니다.

통계적 주의사항은 다음과 같습니다.

- wafer site는 독립 반복 측정이 아닙니다. 공간적으로 가까운 점의 상관을 무시하면
  표준오차를 과도하게 작게 계산할 수 있습니다.
- edge와 center의 정상적인 공정 차이를 전역 median 하나로 판단하면 구조적 영역이
  전부 outlier로 보일 수 있습니다.
- 좌표 원점·축·notch·wafer size가 불명확하면 회전·반경·방향 분석을 중단해야
  합니다.
- surface가 site를 지나치게 따라가면 실제 이상을 흡수합니다. 적합도와 residual
  map을 함께 보여주고, interpolation을 관측값처럼 표현하지 않아야 합니다.

### 4.3 측정 내 sequence·FDC 분석

`sequence`와 `dynamic_fdc[sequence]`를 이용하면 현재 데이터만으로 다음 분석이
가능합니다.

- parameter 측정값, 실패 여부, Brightness, Contrast, Stigma, Defocus,
  Alignment/ImageShift 계열을 같은 sequence 축에 표시합니다.
- dynamic FDC마다 시작값, 끝값, range, robust slope, 최대 변화, missing fraction을
  계산합니다.
- CD 변화와 FDC 변화를 같은 sequence에 맞춘 산점도와 linked brushing으로
  확인합니다.
- 급격한 변화 직전·직후의 SEM image와 alignment evidence를 연결합니다.

그러나 `sequence`는 순서일 뿐 실제 시간 간격이 아닙니다. sequence별 timestamp가
없다면 기울기의 단위는 `per sequence`이며, 초당 drift나 정확한 lag 분석으로
표현하면 안 됩니다. 또한 scan path가 공간 위치와 강하게 연결되면 sequence trend와
공간 trend가 혼재하므로, sequence와 좌표를 함께 표시해야 합니다.

### 4.4 측정 내부 correlation·분포

단일 MSR에서 가장 정직한 상관은 **같은 site 또는 같은 sequence로 정확히 짝지은
값**입니다.

- parameter X/Y는 `chip_number + sequence` 또는 더 강한 site key로 join합니다.
- scatter, Pearson `r`, Spearman rank correlation, 표본 수, missing pair 수를 같이
  표시합니다.
- 선형성, outlier, 이분산을 산점도에서 확인하고, 필요하면 LOWESS 같은 탐색 곡선을
  추가합니다.
- 서로 다른 parameter의 단위와 측정 방법을 항상 축에 표시합니다.
- 여러 parameter pair를 동시에 훑으면 false discovery가 증가하므로 탐색 결과와
  사전 지정 검정을 구분합니다.

Pearson 하나만 표시하면 비선형 관계와 outlier 영향을 놓칠 수 있습니다. NIST는
산점도가 선형·비선형 관계, 분산 변화와 outlier를 함께 확인하는 도구라고 설명하며
([NIST, Scatter Plot](https://www.itl.nist.gov/div898/handbook/eda/section3/eda33q.htm)),
rank correlation은 비정규이거나 단조 비선형 관계에서 사용할 수 있다고 안내합니다
([NIST, Rank Correlation](https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/rankcorr.pdf)).

## 5. 다중 MSR에서 구축할 분석

### 5.1 비교 집합 개요와 데이터 준비도

다중 Dashboard는 평균값 카드보다 먼저 다음 질문에 답해야 합니다.

- 선택한 MSR이 몇 개이며 몇 개가 실제 분석 가능합니까?
- 몇 개의 compatibility group으로 나뉩니까?
- recipe, 장비, lot, 기간, parameter, layout 구성이 어떻게 됩니까?
- MSR별·feature별 누락률과 실패율은 얼마입니까?
- 비교는 사용자 선택 집합 기준입니까, 승인된 historical baseline 기준입니까?

권장 표현은 `N개 선택 → M개 로드 → K개 호환 → G개 그룹`의 funnel과
MSR × feature availability matrix입니다. 혼합 집단을 숨겨서 하나의 평균으로
표현하지 않아야 합니다.

### 5.2 공간 비교

같은 layout의 MSR 집합에는 다음 네 가지 map이 가장 가치가 높습니다.

1. **Reference median map**: 각 site에서 compatible MSR들의 median을 계산합니다.
2. **Candidate delta map**: 각 MSR 값에서 reference site median을 뺍니다. candidate를
   판정할 때는 reference 계산에서 그 candidate를 제외합니다.
3. **Site variability map**: 각 site의 wafer-to-wafer sample std 또는 MAD를
   표시합니다. 단일 MSR에서는 이 map을 만들지 않습니다.
4. **Coverage map**: site별 유효 MSR 수를 표시해 불균형 누락을 드러냅니다.

추가 탐색 기능은 다음과 같습니다.

- 동일 site의 MSR별 small multiples와 linked brushing입니다.
- 각 MSR의 center-corrected map을 vector로 만들고 matched-site Pearson/Spearman,
  RMSE, cosine similarity를 비교합니다.
- radial·sector profile을 겹쳐 level shift와 shape change를 분리합니다.
- 충분한 wafer와 검토 라벨이 축적되면 residual map을 clustering하여 반복되는
  spatial signature를 찾습니다.

ORNL·SEMATECH의 초기 연구는 wafer map의 체계적 spatial signature를 자동으로
분할·분류해 사람이 처리해야 할 데이터를 줄이는 방향을 제시했습니다
([Tobin et al., 1997](https://doi.org/10.1117/12.275936)). Skewvoir에서는 처음부터
자동 root-cause label을 붙이기보다, engineer-reviewed signature library와
`similar historical maps` 검색부터 시작하는 편이 안전합니다.

### 5.3 측정 간 시간 분석

먼저 각 MSR을 다음과 같은 **한 행짜리 feature table**로 정규화합니다.

```text
timestamp, fab, tool, model, recipe_revision, lot, wafer, msr,
parameter_mean, median, std, MAD, min, max, coverage, fail_ratio,
spatial_level, radial_slope, edge_center_delta, surface_residual,
fixed_fdc_*, dynamic_fdc_*_mean/std/slope/range/missing,
hardware_pre/during/post_features, maintenance_regime
```

이후 분석은 질문별로 분리합니다.

- **Run chart**: mean, median, spread, coverage, 실패율을 시간순으로 표시합니다.
- **장비 층화**: 같은 그래프에서 tool별 선을 분리하고 lot·maintenance 구간을
  표시합니다.
- **Individuals/Moving Range**: MSR당 요약값 한 개이고 승인된 in-control baseline이
  있을 때 사용합니다.
- **EWMA**: 작은 지속 drift를 찾을 때 사용합니다. NIST는 EWMA가 과거 값의 가중치를
  점차 낮추며 작은·점진적 이동에 민감하고, 대표적인 역사 데이터베이스가 필요하다고
  설명합니다([NIST, EWMA Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc314.htm)).
- **CUSUM**: 엔지니어가 검출해야 할 최소 shift 크기를 정의할 수 있을 때 후보로
  둡니다([NIST, CUSUM Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm)).
- **Maintenance 전후 비교**: BM/PM 경계를 표시하고 충분한 전후 MSR을 같은 호환
  집단에서 비교합니다. 정비 효과와 시간 drift가 confounding될 수 있음을 표시합니다.

관리도는 spec limit 차트가 아닙니다. NIST의 관리도는 in-control process의 center와
control limit을 통해 시간에 따른 상태를 모니터링하는 도구입니다
([NIST, Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)).
따라서 USL/LSL, engineering limit, statistical control limit을 화면에서 다른 선과
이름으로 구분해야 합니다.

또한 다음을 지켜야 합니다.

- 사용자가 고른 5~30개 점으로 control limit을 매번 다시 만들지 않습니다.
- recipe·장비 설정·software·maintenance 변화에서 baseline version을 나눕니다.
- baseline에 review candidate를 자동 흡수하지 않습니다.
- MSR 간 간격이 불규칙하면 sequence index와 실제 elapsed time을 구분합니다.
- autocorrelation을 확인합니다. NIST는 비랜덤성과 autocorrelation이 일반적인
  통계 검정과 표준오차의 타당성을 훼손할 수 있다고 경고합니다
  ([NIST, Autocorrelation Plot](https://www.itl.nist.gov/div898/handbook/eda/section3/autocopl.htm)).

### 5.4 CD·FDC·하드웨어 결합 분석

현재 자산은 세 가지 grain으로 나뉩니다.

| Grain | CD outcome | 장비 데이터 | 올바른 결합 |
| --- | --- | --- | --- |
| site/sequence | `msr_file.rows.cd_value` | `dynamic_fdc[sequence]` | 동일 MSR·동일 sequence로 exact join |
| MSR/run | parameter summary, 실패율, spatial feature | `fixed_fdc`, dynamic FDC 요약 | 동일 MSR의 feature row |
| 장비 시간 | MSR의 `start_time`~`end_time` | hardware `docs.timestamp`, BM/PM interval, as-of settings | 같은 `eqp_id`에서 pre/during/post window와 이전 as-of snapshot |

권장 feature는 다음과 같습니다.

- FDC·BSM·resolution time series의 latest-before-start, pre-window mean/std/slope,
  during-window min/max/range, post-window recovery입니다.
- MDC·SCE는 MSR 시작 시점 이전의 가장 최근 snapshot만 사용합니다.
- BM/PM은 `days_since_maintenance`, maintenance category, regime ID로 변환하되
  engineer note 원문을 증거로 연결합니다.
- Brightness/Contrast, Stigma, Defocus, stage drift, source, e-chuck, alignment
  계열을 의미별 family로 유지합니다. 서로 다른 단위를 한 점수로 평균하지 않습니다.

분석 화면은 다음을 제공합니다.

- CD feature와 hardware feature의 scatter + tool/lot 색상 + 시간 방향입니다.
- tool별 correlation과 전체 pooled correlation을 나란히 표시합니다.
- lag 후보는 사전 정의된 window만 평가하고, 가장 큰 상관 하나를 사후 선택해
  원인처럼 표현하지 않습니다.
- 관계가 maintenance 경계 전후에 바뀌는지 facet합니다.
- raw record로 역추적할 수 있는 timestamp, source, unit, aggregation window를
  tooltip과 export에 남깁니다.

MSR 결과 하나를 같은 run의 수천 개 sensor timestamp에 복제해 correlation을
계산하면 표본 수를 인위적으로 부풀리는 pseudoreplication이 됩니다. Hardware trace는
recipe step·channel별 feature로 먼저 축약하고, **MSR/run 한 건을 분석 단위 한 건**으로
유지해야 합니다. Raw trace끼리 비교할 때는 같은 phase와 시간 grid에 정렬한 별도
trajectory 분석을 사용합니다.

### 5.5 장비·lot·wafer·site 변동 분해

다중 MSR이 여러 장비·lot·wafer와 반복 site를 포함하면 단순 box plot보다
variance component가 더 유용합니다. 예시는 다음과 같습니다.

```text
y = overall level
  + tool effect
  + lot effect
  + MSR/wafer effect
  + site-within-wafer effect
  + residual
```

NIST는 semiconductor batch 안의 wafer, wafer 안의 site처럼 중첩된 자료에서
wafer와 site를 random effect로 다루면 각 변동원의 기여도를 추정할 수 있다고
설명합니다([NIST, Nested Variation](https://www.itl.nist.gov/div898/handbook/pri/section5/pri55.htm)).
REML 기반 mixed model을 사용하고 variance proportion과 interval을 보여주는 방식을
권장합니다. NIST도 variance component의 REML 추정과 넓을 수 있는 신뢰구간을 함께
설명합니다([NIST, Variance Components](https://www.itl.nist.gov/div898/handbook/prc/section4/prc44.htm)).

다만 임의의 다중 선택만으로 이 분석을 항상 실행할 수는 없습니다.

- tool당 한 MSR이면 tool effect와 MSR effect를 분리할 수 없습니다.
- lot와 tool이 완전히 겹치면 어느 효과인지 식별할 수 없습니다.
- site layout이 다르면 site effect가 design 차이와 혼재합니다.
- 반복이 없는 factor와 매우 작은 level 수의 결과는 descriptive로만 표시합니다.

따라서 이 분석은 `설계 충분 / 제한적 / 식별 불가` readiness를 먼저 계산해야 합니다.

## 6. 고급 분석 후보

### 6.1 PCA/MSPC 기반 장비 상태 분석

hardware와 FDC feature가 많고 서로 상관될 때 PCA score, loading, Hotelling
`T²`, residual `Q/SPE`를 이용해 multivariate 상태를 요약할 수 있습니다. 반도체
etch 장비 센서에서 PCA와 multiway PCA를 비교한 원 연구는 engineering variables,
광학 emission, RF sensor를 이용해 fault detection을 수행했습니다
([Wise et al., 1999](https://doi.org/10.1002/(SICI)1099-128X(199905/08)13:3/4%3C379::AID-CEM556%3E3.0.CO;2-N)).

Skewvoir 적용 조건은 다음과 같습니다.

- 변수 단위·sampling·window를 고정하고 missingness를 관리합니다.
- in-control training period를 버전으로 동결합니다.
- `p < n - 1`을 최소 조건으로 하고 `n`이 `p`보다 충분히 큰지 검증합니다. NIST의
  Hotelling 설명도 독립적인 다변량 정규 관측과 `p < n - 1`을 전제로 합니다
  ([NIST, Hotelling Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc341.htm)).
- aggregate score만 보여주지 않고 기여 loading, 원 변수의 signed deviation,
  baseline과 모델 버전을 함께 보여줍니다.
- recipe·tool mode를 섞은 multimodal 집단에 PCA 하나를 강제하지 않습니다.

초기 제품 판정에는 사용하지 않고 `연구 분석`으로 두는 것이 적절합니다.

### 6.2 Wafer spatial signature 검색·군집

충분한 compatible map이 쌓이면 다음 순서가 안전합니다.

1. site align과 coverage gate를 통과합니다.
2. 각 map에서 nominal level과 승인된 radial trend를 제거합니다.
3. residual map을 vector 또는 spatial descriptor로 만듭니다.
4. nearest historical maps를 먼저 제공합니다.
5. engineer가 반복 signature를 검토·이름 붙인 뒤 clustering·classification을
   오프라인 검증합니다.

Spatial signature가 장비 fault와 연결될 수 있다는 원 연구가 있지만, known-fault
surface 또는 역사 fault label이 필요합니다
([Gardner et al., 1997](https://doi.org/10.1109/3476.650961)). 따라서 `ring`,
`edge`, `scratch` 같은 모양을 바로 root cause로 번역하지 않고 `유사 pattern`으로
표현해야 합니다.

### 6.3 Virtual metrology와 동적 sampling

MSR 결과를 label, 측정 이전의 hardware/FDC feature를 predictor로 두면 장기적으로
virtual metrology를 연구할 수 있습니다. 최근 NIST 원 연구는 CMP 데이터에서 online
Gaussian process와 예측 불확실성을 이용해 drift·shift를 추적하고 동적 sampling을
구성했습니다([Han et al., 2025](https://doi.org/10.1109/TSM.2025.3531920)).

그러나 이는 현재 분석 페이지의 단순 확장이 아닙니다. 다음 별도 체계가 필요합니다.

- MSR 발생 이전 데이터만 사용하는 leakage-safe feature pipeline입니다.
- 시간 순서 train/validation/test와 maintenance·recipe change holdout입니다.
- 예측값뿐 아니라 uncertainty, calibration, out-of-distribution 상태입니다.
- 실제 측정을 계속 확보하는 sampling·retraining·rollback 정책입니다.
- measurement uncertainty와 tool-to-tool matching 검증입니다. IRDS Metrology는
  repeatability, wafer reload variation, long-term drift를 포함한 reproducibility와
  tool-to-tool matching을 명시적으로 다룹니다
  ([2024 IRDS Metrology](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=959302)).

Virtual metrology는 `예측 참고`로 시작해야 하며 실제 MSR을 대체하는 공식값으로
바로 승격하면 안 됩니다.

## 7. 통계적으로 지켜야 할 원칙

### 7.1 가장 위험한 오류

| 위험 | Skewvoir에서 생기는 예 | 방지 방법 |
| --- | --- | --- |
| Pseudoreplication | 한 wafer의 50 site를 독립 wafer 50개처럼 사용 | wafer/MSR을 experimental unit으로 유지하고 site 중첩·공간 상관을 모델링합니다. |
| Trace replication | MSR 결과 하나를 수천 sensor timestamp에 복제해 큰 `N`의 상관을 생성 | step별 run feature를 만든 뒤 MSR당 한 행으로 결합합니다. |
| Selection bias | 사용자가 문제처럼 보이는 MSR만 골라 전체 공정처럼 해석 | `사용자 선택 탐색 집합`을 명시하고 공식 baseline과 분리합니다. |
| Simpson's paradox·confounding | tool을 섞은 CD↔FDC 상관이 tool별 관계와 반대 | recipe·tool·lot·기간별 scatter와 estimate를 함께 표시합니다. |
| Temporal leakage | MSR 이후 hardware 값을 predictor로 사용 | event-time join과 latest-before/as-of 규칙을 서버에서 고정합니다. |
| Baseline contamination | flag된 MSR이 다음 기준선을 완화 | 승인 baseline을 동결·버전 관리하고 명시적으로 갱신합니다. |
| Multiple comparisons | 수백 FDC × parameter × lag 중 최대 상관만 표시 | 사전 지정 family·window, multiplicity 표시, holdout 재검증을 사용합니다. |
| Control/spec 혼동 | 3σ 밖이면 제품 spec fail로 표시 | control limit, engineering limit, USL/LSL을 별도 의미로 표시합니다. |
| Missing-as-zero | `cd_value: null`을 0 nm로 통계에 포함 | nullable을 보존하고 coverage·평가 불가를 별도 상태로 둡니다. |
| Mock validation | 공통 hidden `health`가 만든 CD↔FDC 상관을 성능으로 보고 | office historical data와 time split에서만 방법을 검증합니다. |
| 측정계 혼입 | tool 차이를 공정 차이로 바로 해석 | repeatability, reload, 장기 drift와 tool-to-tool matching을 별도 측정 연구로 확인합니다. |
| Opaque aggregate | CD, 실패, FDC, score를 health 한 개로 평균 | outcome, tool condition, execution/data quality를 별도 evidence family로 유지합니다. |

### 7.2 표본 수와 준비도

하나의 보편적인 최소 `N`은 없습니다. 검출할 shift, 허용 false alarm, feature 수,
분포와 dependence에 따라 달라집니다. 제품은 최소한 다음 gate를 제공해야 합니다.

| 분석 | 최소 준비 조건 | 조건 미충족 시 |
| --- | --- | --- |
| 단일 raw·coverage map | 유효 좌표와 nullable 상태 | 좌표 없는 표와 `공간 분석 불가` 사유를 표시합니다. |
| Surface/residual | 충분한 distinct 좌표, wafer coverage, 좌표계 검증 | raw map만 표시합니다. |
| Paired correlation | 정확한 pair key, 두 변수의 변동, 유효 pair 수 | `상관 평가 불가`와 pair/missing 수를 표시합니다. |
| Multi delta map | 동일 parameter·unit·layout의 2개 이상 MSR | 단일 공간 진단으로 전환합니다. |
| Control chart/EWMA | 승인된 in-control historical stream, regime 정보, dependence 점검 | run chart만 표시하고 관리 한계를 그리지 않습니다. |
| Variance component | 여러 factor level과 replication, 식별 가능한 design | descriptive group plot만 표시합니다. |
| PCA/Hotelling | 고정 feature schema, 충분한 `n >> p`, stable covariance | univariate evidence만 표시합니다. |
| Signature classifier | 충분한 compatible maps와 engineer-reviewed labels | similarity search·clustering 연구까지만 제공합니다. |
| Virtual metrology | leakage-safe history, uncertainty, time-split validation | 예측 기능을 제공하지 않습니다. |

## 8. 추가로 필요한 데이터 계약

### 8.1 모든 MSR과 hardware record에 필요한 공통 필드

- event timestamp, timezone, source timestamp와 ingest timestamp가 필요합니다.
- `fab`, `eqp_id`, model, module/chamber, software version이 필요합니다.
- recipe ID, revision/hash, class, process, product/layer, lot, wafer ID가 필요합니다.
- parameter ID, display name, numeric value, unit, dtype, valid/quality flag가
  필요합니다.
- measurement method, object/kind, mag, vac, pixel, beam condition이 필요합니다.
- wafer size, coordinate origin·axis·notch, chip/stage coordinate, layout ID/hash가
  필요합니다.
- source record ID와 raw-document link가 필요합니다.

Trace를 MSR에 정확히 연결하려면 recipe step의 시작·종료, process job, substrate,
module/chamber도 보존해야 합니다. SEMI E157은 module process tracking에서 trace와
summary data를 process job, recipe, substrate, module, recipe step에 연결하는 표준
계약을 제공합니다
([SEMI E157](https://store-us.semi.org/products/e15700-semi-e157-specification-for-module-process-tracking)).

SEMI EDA는 장비가 event, exception, trace data를 named collection plan으로 제공하는
모델을 정의하며([SEMI E134](https://store-us.semi.org/products/e13400-semi-e134-specification-for-data-collection-management)),
E125 기반 장비 self-description과 E164 common metadata는 장비 데이터 source의
이름·구조·단위·관계를 일관되게 표현하는 참고 기준이 됩니다
([SEMI E125](https://store-us.semi.org/products/e12500-semi-e125-specification-for-equipment-self-description-eqsd),
[SEMI E164](https://store-us.semi.org/products/e16400-semi-e164-specification-for-eda-common-metadata)).
사내 장비가 이 표준을 직접 제공하지 않더라도 backend normalizer의 canonical
metadata를 설계할 때 유용합니다.

### 8.2 현재 계약에 추가해야 할 핵심 항목

| 항목 | 필요한 이유 |
| --- | --- |
| `recipe_revision` 또는 content hash | 같은 이름의 recipe 변경 전후를 분리합니다. |
| `site_layout_id/hash` | 다중 map 비교와 site join의 호환성을 증명합니다. |
| raw row의 `unit` | parameter 이름에 의존한 단위 추정을 제거합니다. |
| sequence별 timestamp | CD↔dynamic FDC 시간·lag·rate 분석을 가능하게 합니다. |
| coordinate metadata | 반경·각도·회전·다른 wafer layout 비교를 안전하게 합니다. |
| typed hardware metric schema | 현재 heterogeneous `docs`의 `values` 배열을 이름·값·단위로 해석합니다. |
| calibration·maintenance regime ID | 기준선 분리와 정비 전후 해석에 사용합니다. |
| quality/validity reason | missing, parse fail, vendor invalid, out-of-range를 구분합니다. |
| historical baseline version | 관리 한계와 판정의 재현성을 보장합니다. |

Hardware raw data의 수집 모델은 높은 속도의 모든 값을 무조건 적재하는 방식보다,
분석 목적별 data collection plan과 metadata registry가 적절합니다. SEMI EDA 역시
관련 source를 목적별 group으로 조직하고 event·exception·trace를 collection plan으로
관리합니다([SEMI EDA overview](https://www.semi.org/en/next-gen-semi-eda-standards)).

## 9. 권장 개발 순서

### P0. 분석 진실성과 모드 계약

- URL과 backend request에 `mode=single|set`의 명시적 의미를 둡니다.
- `compatibility_signature`, group, 제외 사유, data readiness를 backend에서
  계산합니다.
- raw MSR, history, hardware를 event time으로 결합하는 feature 계약을 만듭니다.
- 사용자 선택 탐색 집합과 승인 historical baseline을 분리합니다.
- mock `health`, placeholder `spm_dict`, vendor score를 판정 경로에서 제외합니다.

### P1. 단일 MSR의 공간·실행 증거

- Dashboard에 coverage/failure, execution, alignment, parameter summary를
  완성합니다.
- 위치 페이지를 raw/failure/residual/radial 공간 진단으로 바꿉니다.
- sequence CD와 dynamic FDC를 연결합니다.
- paired-site correlation과 이미지 triage를 연결합니다.

### P2. 다중 MSR의 비교·시간·장비 증거

- 비교 집합 funnel과 availability matrix를 만듭니다.
- reference median, delta, variability, coverage map을 만듭니다.
- per-MSR feature table과 tool/lot-stratified run chart를 만듭니다.
- 승인 baseline이 있을 때만 Individuals/EWMA를 엽니다.
- FDC, BSM, resolution, MDC/SCE, BM/PM을 event-time join합니다.

### P3. 원인 후보 축소

- variance component와 tool matching 분석을 추가합니다.
- spatial signature similarity search와 engineer label workflow를 추가합니다.
- constrained PCA/MSPC를 연구 탭으로 검증합니다.

### P4. 예측 연구

- virtual metrology, uncertainty-aware dynamic sampling, predictive maintenance를
  별도 offline acceptance 절차로 연구합니다.

## 10. 엔지니어에게 보여줄 설명 계약

어떤 분석 결과도 다음 정보를 잃지 않아야 합니다.

- 분석 질문과 grain이 `site`, `sequence`, `MSR`, `tool-time` 중 무엇인지 표시합니다.
- 사용된 MSR, 제외된 MSR과 이유, compatibility group을 표시합니다.
- raw value, unit, aggregation window, transform, reference를 표시합니다.
- sample count, pair count, coverage와 missing count를 표시합니다.
- 탐색 결과인지 승인된 공식 기준선 결과인지 표시합니다.
- threshold·baseline·feature schema·model version을 표시합니다.
- correlation에는 `연관이며 원인 증명이 아님`을 표시합니다.
- 평가할 수 없으면 정상으로 바꾸지 않고 `평가 불가`와 이유를 표시합니다.
- chart point에서 raw MSR row, hardware record, image, maintenance event로
  drill-through할 수 있어야 합니다.

이 계약을 지키면 Skewvoir는 많은 차트를 모은 화면이 아니라, 측정 산출물에서
공간 evidence를 찾고, compatible history에서 변화를 확인하고, 장비 evidence로
원인 후보를 좁히는 워크스페이스가 됩니다.

## 11. 1차 출처

### 공식 표준·기관 문서

- [NIST/SEMATECH Engineering Statistics Handbook: Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3.htm)
- [NIST: EWMA Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc314.htm)
- [NIST: Autocorrelation Plot](https://www.itl.nist.gov/div898/handbook/eda/section3/autocopl.htm)
- [NIST: Nested Variation](https://www.itl.nist.gov/div898/handbook/pri/section5/pri55.htm)
- [2024 IRDS Metrology](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=959302)
- [SEMI E125: Equipment Self Description](https://store-us.semi.org/products/e12500-semi-e125-specification-for-equipment-self-description-eqsd)
- [SEMI E134: Data Collection Management](https://store-us.semi.org/products/e13400-semi-e134-specification-for-data-collection-management)
- [SEMI E164: EDA Common Metadata](https://store-us.semi.org/products/e16400-semi-e164-specification-for-eda-common-metadata)
- [SEMI E157: Module Process Tracking](https://store-us.semi.org/products/e15700-semi-e157-specification-for-module-process-tracking)

### 동료심사 원 연구

- Gardner, M. M. et al. (1997), [Equipment Fault Detection Using Spatial Signatures](https://doi.org/10.1109/3476.650961).
- Tobin, K. W. et al. (1997), [Automatic Classification of Spatial Signatures on Semiconductor Wafer Maps](https://doi.org/10.1117/12.275936).
- Wise, B. M. et al. (1999), [PCA and Multiway Methods for Fault Detection in a Semiconductor Etch Process](https://doi.org/10.1002/(SICI)1099-128X(199905/08)13:3/4%3C379::AID-CEM556%3E3.0.CO;2-N).
- Sachs, E., Hu, A. and Ingolfsson, A. (1995), [Run by Run Process Control: Combining SPC and Feedback Control](https://doi.org/10.1109/66.350755).
- Kang, P. et al. (2009), [A Virtual Metrology System for Semiconductor Manufacturing](https://doi.org/10.1016/j.eswa.2009.05.053).
- Han, X. et al. (2025), [A Comparative Study of Semiconductor Virtual Metrology Methods and Novel Algorithmic Framework for Dynamic Sampling](https://doi.org/10.1109/TSM.2025.3531920).
