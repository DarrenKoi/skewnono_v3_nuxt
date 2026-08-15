# 스큐보아 분석 상세 페이지 CD 벤치마크 연구

- 작성일: 2026-07-16
- 대상: Skewvoir `analysis` 워크스페이스의 위치 비교, Time-Series,
  상관 / 분포, 이미지 갤러리
- 범위: 반도체 웨이퍼 CD 측정에서 널리 쓰이는 분석 관점과 상세 페이지 설계 근거
- 상태: 연구 노트입니다. 공식 판정 규칙이나 구현 명세는 아닙니다.
- 구현 대비 격차와 착수 순서는
  [분석 도구 격차 분석](analysis-coverage-gap-analysis.md)에 있습니다. §12의 적용
  우선순위는 그 문서 §5의 검증된 순서로 대체되었습니다.

## 1. 연구 목적과 결론

이 문서는 기존 [웨이퍼 분석 방법 연구](wafer-analysis-method-research.md)의
단일 MSR·다중 MSR 구분, 비교 가능성 서명, 데이터 결합 원칙을 반복하지 않습니다.
대신 측정 개요에서 이상 징후를 발견한 엔지니어가 네 개 상세 페이지에서 어떤 질문에
답하고 어떤 행동을 결정할 수 있어야 하는지를 반도체 CD 측정 관행에 맞춰 구체화합니다.

권장 워크플로는 다음과 같습니다.

```text
측정 개요
  ├─ 어디가 다른가? ───────────────→ 위치 비교
  ├─ 언제부터 달라졌는가? ─────────→ Time-Series
  ├─ 무엇과 함께 변했고 얼마나 퍼졌는가? → 상관 / 분포
  └─ 실제 pattern인가, 측정 artifact인가? → 이미지 갤러리
```

핵심 결론은 다음과 같습니다.

- **위치 비교**는 평균 wafer map이 아니라 `level`, `shape`, `coverage`를 분리하는
  공간 진단 화면이어야 합니다. 같은 좌표계와 layout을 증명한 뒤 raw, reference,
  signed delta, site variability, coverage를 순서대로 보여주는 것이 우선입니다.
- **Time-Series**는 한 MSR 내부의 sequence 순서와 여러 MSR의 실제 시간 흐름을
  섞지 않아야 합니다. 기본 화면은 run chart이며, 승인된 안정 기준선이 있을 때만
  관리도·EWMA·CUSUM을 엽니다.
- **상관 / 분포**는 site-level 관계, MSR/run-level 관계, tool·lot별 분포를 서로 다른
  분석 단위로 다뤄야 합니다. 공정 능력 지수는 안정 공정과 실제 specification이
  확인된 경우에만 제공합니다.
- **이미지 갤러리**는 단순 thumbnail grid가 아니라 CD 값의 line profile, 검출 edge,
  scale, recipe와 acquisition 조건을 함께 확인하는 measurement-evidence 화면이어야
  합니다. charging, focus, contamination, edge algorithm에 의한 오차를 pattern
  변화와 구분해야 합니다.
- 1차 제품은 업계에서 이미 정착한 CDU, run chart/SPC, exact-pair correlation,
  image review를 우선해야 합니다. tool matching은 reference-artifact 반복 측정 계약이
  준비된 뒤 조건부로 제공하며, 일반 production wafer의 tool별 평균 차이만으로 metrology
  bias를 추정하지 않습니다. Zernike fingerprint, spatial signature 자동 분류, PCA/MSPC,
  virtual metrology는 연구 기능으로 분리해야 합니다.

## 2. 방법 성숙도 구분

이 문서에서는 기능을 다음 세 단계로 구분합니다.

| 구분 | 의미 | 제품 표시 원칙 |
| --- | --- | --- |
| 정착 관행 | 표준, 공인 통계 지침, 생산용 CD-SEM 공급사 기능과 여러 원 연구에서 반복되는 분석입니다. | 기본 상세 페이지에 제공할 수 있으나 데이터 준비도와 단위를 항상 표시합니다. |
| 조건부 분석 | 방법 자체는 정착되어 있으나 실험 설계, 동결 기준선, reference sample 또는 추가 metadata가 필요합니다. | 준비 조건을 통과한 경우에만 열고 미충족 사유를 설명합니다. |
| 연구 기능 | 최근 연구 또는 site별 원인 label·대규모 history·모델 검증이 필요한 분석입니다. | 공식 판정과 분리해 `연구 분석` 또는 `탐색`으로 표시합니다. |

공급사 자료는 실제 생산용 장비가 제공하는 기능 범위를 확인하는 근거로만 사용합니다.
특정 제품의 성능 수치는 독립 검증 결과로 해석하지 않습니다.

## 3. 현재 화면에서 확인되는 출발점과 빈틈

현재 코드는 Time-Series와 위치 비교에서만 비교 MSR 파일을 지연 로드하고,
상관 / 분포와 Gallery는 focus MSR의 row만 사용합니다
([분석 composable](../../../front-dev-home/app/composables/useSkewvoirAnalysis.ts)).
따라서 네 메뉴가 같은 비교 집합을 공유하는 것처럼 보이지만 실제 분석 범위는 다릅니다.

| 페이지 | 현재 구현 | 엔지니어링 빈틈 |
| --- | --- | --- |
| [위치 비교](../../../front-dev-home/app/components/ebeam/skewvoir/views/PositionStack.vue) | 공통 `chip_number`별 composite mean과 wafer-to-wafer sample σ를 표시합니다. | layout·좌표 호환성, site별 유효 MSR 수, reference/delta, focus MSR 강조, 단일 MSR 공간 진단이 없습니다. |
| [Time-Series](../../../front-dev-home/app/components/ebeam/skewvoir/views/TimeSeries.vue) | MSR별 mean과 min/max band, 사용자 선택 `%`·σ 진단, focus MSR sequence를 표시합니다. | 실제 기준선, tool·lot·recipe 층화, coverage·실패·WCDU lane, BM/PM event, 관리 한계와 spec 구분이 없습니다. |
| [상관 / 분포](../../../front-dev-home/app/components/ebeam/skewvoir/views/Correlation.vue) | focus MSR 안에서 parameter pair scatter와 한 parameter의 histogram·box·violin을 표시합니다. | exact pair 품질, 다중 MSR의 run-level CD↔FDC 관계, strata 비교, capability readiness가 없습니다. |
| [이미지 갤러리](../../../front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue) | focus MSR의 parameter별 image, chip, CD를 grid로 표시합니다. | residual·실패·score 기준 triage, 동일 site 전후 비교, scale·edge·line profile·acquisition metadata와 artifact 증거가 없습니다. |

현재 기능을 폐기할 필요는 없습니다. 각 페이지가 사용하는 분석 단위와 비교 집합을
명시하고, 현재 차트를 아래에 정의한 evidence stack의 일부로 재배치하는 것이 적절합니다.

## 4. 공통 UI·분석 계약

### 4.1 모든 결과가 답해야 하는 질문

모든 chart와 table은 다음 다섯 정보를 함께 제공해야 합니다.

1. 분석 단위가 `site`, `sequence`, `MSR/run`, `tool-time` 중 무엇입니까?
2. 무엇과 비교했으며 reference가 사용자 선택 집합인지 승인 기준선인지 명시합니까?
3. 몇 건을 사용했고 몇 건을 어떤 이유로 제외했습니까?
4. raw value, unit, transform, aggregation window가 무엇입니까?
5. chart point에서 원 MSR row, SEM image, FDC record와 event로 이동할 수 있습니까?

### 4.2 공통 화면 구조

네 상세 페이지의 상단에는 같은 `Analysis Context Bar`를 유지하는 것이 좋습니다.

```text
[Focus MSR] [비교 집합 12/15] [호환 그룹 A] [Parameter] [단위]
[사용자 탐색 집합 | 승인 기준선 v3] [제외 3건 보기] [Export evidence]
```

- focus MSR은 모든 chart에서 같은 강조색을 사용합니다.
- 사용자 선택 집합과 승인 기준선은 색뿐 아니라 label과 line style도 다르게 합니다.
- `12/15`는 선택 15건 중 실제 분석에 사용한 12건이라는 뜻이며 제외 사유를 엽니다.
- page를 이동해도 parameter, focus MSR, comparison set, 선택 site·time point를
  유지합니다.
- 데이터 준비 조건을 만족하지 못하면 빈 chart 대신 `평가 불가`와 누락 계약을
  표시합니다.

## 5. 위치 비교: 어디가 다른가

### 5.1 페이지가 지원할 엔지니어 판단

- 변화가 wafer 전체의 level shift입니까, center-to-edge 또는 국소 shape 변화입니까?
- focus MSR의 차이가 반복되는 site signature입니까, coverage 차이로 생긴 착시입니까?
- 특정 edge, sector, scan path 또는 측정 실패 위치에 집중됩니까?
- 같은 site의 역사 MSR에서도 같은 방향의 변화가 반복됩니까?

### 5.2 정착 관행으로 우선 제공할 evidence stack

#### A. 좌표·coverage gate

SEMI E142는 substrate map의 layout과 XY map data를 보고·저장·전송하는 데이터
항목을 정의하며, 서로 다른 wafer XY 좌표계를 표준 좌표로 변환하는 필요성도
명시합니다([SEMI E142 개정 설명](https://www.semi.org/en/standards-watch-2026-apr/major-revision-underway-for-semi-e142)).
따라서 map을 평균하거나 빼기 전에 다음을 먼저 보여줘야 합니다.

- wafer size, origin, axis, notch, site-layout ID/hash 일치 여부입니다.
- 공통 site 수, focus MSR coverage, site별 유효 MSR 수입니다.
- 회전·반사·좌표 변환이 있었다면 원 좌표와 변환 version입니다.
- 공통 site가 적거나 변환을 증명할 수 없으면 composite와 delta를 만들지 않습니다.

#### B. 다섯 개의 기본 map

| Map | 계산 | 엔지니어가 얻는 정보 | 주의사항 |
| --- | --- | --- | --- |
| Raw focus map | focus MSR의 측정값과 missing·fail을 그대로 표시합니다. | 실제 관측값과 측정 공백을 확인합니다. | missing을 0이나 interpolation 값으로 채우지 않습니다. |
| Reference map | compatible historical MSR의 site별 median입니다. | 정상적인 site fingerprint를 확인합니다. | focus MSR은 자신의 reference 계산에서 제외합니다. |
| Signed delta map | `focus - reference`입니다. | 넓어짐·좁아짐의 방향과 위치를 확인합니다. | 서로 다른 nominal CD·unit·method를 빼지 않습니다. |
| Site variability map | site별 MSR 간 sample σ와 robust MAD입니다. | 본래 불안정한 site와 새로운 변화를 구분합니다. | site별 유효 MSR 수를 함께 표시합니다. |
| Coverage map | site별 valid MSR 수와 비율입니다. | 평균·σ가 불균형 표본에서 만들어졌는지 확인합니다. | coverage가 다른 site의 σ를 같은 신뢰도로 비교하지 않습니다. |

생산용 CD-SEM 공급사는 `across-wafer`와 `local CD uniformity`를 실제 분석 항목으로
제공합니다([Hitachi High-Tech CD-SEM 분석 항목](https://www.hitachi-hightech.com/us/en/products/advanced-analytical/microscopy/cdsem.html)).
WCDU는 실무·논문에서 wafer 내 측정값의 `3σ`로 보고되는 경우가 있지만
([MRAM patterning 연구의 WCDU 정의](https://doi.org/10.1016/j.mne.2021.100082)),
Skewvoir는 `3σ` 하나만 보여주지 않아야 합니다. mean·median, σ·MAD, max-min,
valid `N`, edge exclusion을 나란히 보여줘야 비정규 분포와 몇 개의 극단값을 구분할
수 있습니다.

#### C. level과 shape 분리

권장 우측 panel은 다음 세 줄입니다.

1. **Wafer level**: mean, median, target offset입니다.
2. **WCDU/spread**: σ, `3σ`, MAD, range, valid `N`입니다.
3. **Shape profile**: center-edge delta, radius-bin median, sector median입니다.

Wafer 중심에서 edge로 CD가 달라지는 WCDU는 실제 resist process 연구에서도 별도
문제로 다뤄집니다([Lim et al., 2019](https://doi.org/10.2494/photopolymer.32.441)).
따라서 radial profile은 단순 장식이 아니라 center-to-edge signature를 찾는 정착된
분해 관점입니다. 다만 notch와 좌표축이 검증되지 않으면 sector·방향 분석은
비활성화합니다.

#### D. 비교 동작

- `Focus vs Reference`, `Focus vs One MSR`, `Small multiples` 세 모드를 제공합니다.
- delta color scale은 0을 중심으로 대칭 고정하며 page 안에서 자동 재조정하지 않습니다.
- site를 클릭하면 같은 site의 MSR별 sparkline, 분포와 SEM image strip을 엽니다.
- radial bin과 sector를 선택하면 다른 페이지의 분포·Gallery에도 같은 선택을 전달합니다.
- interpolation surface는 별도 toggle로 두고 관측 site marker를 항상 남깁니다.

### 5.3 조건부·연구 기능

- **조건부: Focus-Exposure/Bossung**은 의도적으로 설계된 focus-exposure matrix와
  동일 pattern CD가 있을 때 process-window 분석으로 유용합니다. Bossung plot은
  focus와 dose에 따른 linewidth를 표시해 optical lithography에서 공정 창을 평가하는
  데 자주 사용됩니다([FEM 원 연구](https://doi.org/10.1016/j.mee.2011.02.108)).
  일반 생산 history에서 우연히 존재하는 focus·dose 값을 DOE처럼 처리하면 안 됩니다.
- **연구: Zernike fingerprint**는 wafer CDU shape를 저차 공간 성분으로 압축해
  module matching에 사용할 가능성이 있습니다. 2025년 DRAM photolithography 연구가
  이 접근을 제안했지만([Ohri et al., 2025](https://doi.org/10.1117/12.3051932)),
  현재는 연구 기능으로 두고 raw/delta map을 대체하지 않아야 합니다.
- **연구: spatial signature 분류**는 engineer-reviewed label과 재현 가능한 history가
  있을 때만 수행합니다. 모양만 보고 `ring = 특정 장비 고장`처럼 원인을 자동 부여하지
  않습니다.

## 6. Time-Series: 언제부터 무엇이 바뀌었는가

### 6.1 두 시간축을 분리합니다

| Mode | X축 | 한 점의 단위 | 답하는 질문 |
| --- | --- | --- | --- |
| Run History | 실제 `timestamp` 또는 elapsed time | MSR/run 한 건의 요약 feature | lot·wafer·장비 운용 중 언제 level·spread·quality가 변했습니까? |
| Within-Run Sequence | `sequence`와 가능하면 sequence timestamp | 같은 MSR 안의 site/parameter 측정 | 한 번의 측정 도중 drift·fail·FDC 변화가 어느 순서에서 나타났습니까? |

`sequence`에 실제 timestamp가 없으면 `per minute` 또는 lag로 표현하지 않습니다.
scan path와 wafer 위치가 결합되어 있으면 sequence trend 아래에 좌표 path mini-map을
같이 표시합니다.

### 6.2 Run History의 권장 lane

하나의 mean ± min/max chart에 모든 의미를 넣지 않고, 같은 시간 cursor를 공유하는
네 개 lane으로 구성하는 것이 좋습니다.

1. **CD level**: MSR별 mean·median과 focus point입니다.
2. **CD uniformity**: σ·MAD·`3σ`·edge-center delta입니다.
3. **Measurement quality**: coverage, fail ratio, align fail, image fail입니다.
4. **Tool context**: fixed FDC, dynamic FDC 요약, maintenance·recipe revision event입니다.

tool, lot, recipe revision, chamber/module을 색 또는 facet으로 선택할 수 있어야 합니다.
점이 많을 때는 line 하나로 연결하기보다 tool별 stream을 분리하고, 실제 시간 공백과
MSR 순번을 서로 다른 축 옵션으로 제공합니다.

SEMI E133은 semiconductor fab의 process control system 범위로 R2R, fault detection,
fault classification, fault prediction과 SPC를 명시합니다
([SEMI E133](https://store-us.semi.org/products/e13300-semi-e133-specification-for-automated-process-control-systems-interface)).
Skewvoir는 이 기능들을 한 anomaly score로 합치기보다 CD outcome, tool condition,
measurement quality의 세 evidence lane으로 유지해야 합니다.

### 6.3 관리도 선택 규칙

| 데이터 구조 | 기본 표현 | 조건을 만족할 때 | 제공하지 말아야 할 경우 |
| --- | --- | --- | --- |
| 시간점마다 MSR 요약값 1개 | Run chart | frozen in-control history가 있으면 Individuals-MR입니다. | 사용자 선택 5~30건으로 limit을 매번 다시 계산하지 않습니다. |
| 한 wafer 안에 rational subgroup site가 여러 개 | mean과 S lane | layout·site 수·sampling이 일관되면 X-bar/S입니다. | site가 서로 다른 pattern·parameter이면 한 subgroup으로 합치지 않습니다. |
| 작은 지속 shift가 중요함 | Raw point와 rolling context | baseline과 λ·ARL 정책이 승인되면 EWMA입니다. | recipe·tool regime을 섞은 baseline에 적용하지 않습니다. |
| 검출할 최소 shift가 사전 정의됨 | Run chart | shift와 false-alarm 정책이 승인되면 CUSUM입니다. | 가장 잘 flag하는 설정을 사후 선택하지 않습니다. |

NIST semiconductor case study도 wafer를 subgroup으로 두고 mean과 standard-deviation
control chart를 함께 사용합니다
([NIST Subgroup Analysis](https://www.itl.nist.gov/div898/handbook/pmc/section6/pmc613.htm)).
한 시간점에 한 값만 있으면 Individuals chart가 맞으며
([NIST Individuals Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc322.htm)),
EWMA는 작은·점진적 drift에, CUSUM은 작은 mean shift에 민감합니다
([NIST EWMA](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm),
[NIST CUSUM](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm)).

통계 관리 한계, engineering watch limit, USL/LSL을 같은 선처럼 표현하지 않습니다.
control limit은 안정 공정의 변동으로부터, specification은 제품·공정 owner의 요구에서
옵니다.

### 6.4 event와 tool matching

- BM/PM, recipe revision, software version, calibration은 point가 아니라 vertical event
  band로 표시합니다.
- event 전후 차이는 같은 compatible stream의 충분한 전후 MSR로 계산합니다.
- event 직후 변화는 `관련 시점`이지 `정비가 원인`이라는 결론이 아닙니다.
- tool-to-tool matching은 일반 production wafer의 tool별 평균 차이와 reference
  artifact 결과를 구분합니다. CD-SEM 정확도 평가는 short-term·long-term
  repeatability와 tool-to-tool matching을 별도 성분으로 다룹니다
  ([Otaka et al., 2006](https://doi.org/10.1380/jsssj.27.636)).
- reference/check sample stream이 없으면 `tool 차이 후보`만 표시하고 metrology bias와
  process 차이를 분리했다고 주장하지 않습니다.

## 7. 상관 / 분포: 무엇과 함께 변했고 얼마나 퍼졌는가

### 7.1 네 가지 분석 mode

| Mode | 행의 단위 | 대표 질문 | 권장 chart |
| --- | --- | --- | --- |
| Within-MSR Pair | 같은 site 또는 sequence의 exact pair | 한 MSR에서 parameter X와 Y가 같은 위치에서 같이 변합니까? | scatter, marginal distribution, residual |
| Across-MSR Outcome | MSR/run 한 건 | CD level·WCDU가 같은 run의 FDC·hardware feature와 같이 변합니까? | stratified scatter, robust fit, time arrow |
| Group Distribution | MSR/run 또는 명시된 site stratum | tool·lot·recipe·기간별 중심과 산포가 다릅니까? | box/violin + raw point, ECDF |
| Capability | 승인 stream의 MSR/run | 안정 공정이 실제 specification 안에 들어갑니까? | histogram/ECDF + spec, capability card |

UI는 mode를 상단 segmented control로 나누고, 서로 다른 분석 단위의 `N`을 한 화면에서
합치지 않아야 합니다.

### 7.2 Within-MSR Pair

- 값 pairing은 `chip_number + sequence + parameter`보다 강한 MeasurementKey
  (PhysicalSiteKey + parameter)로 exact join합니다. 서로 다른 parameter(X↔Y, CD↔FDC)를
  같은 위치에서 join할 때는 parameter를 뺀 PhysicalSiteKey를 씁니다.
- Pearson `r`, Spearman `ρ`, valid pair `N`, missing X/Y 수를 같이 표시합니다.
- scatter에서 outlier, 비선형성, 이분산을 보고 통계량을 해석합니다.
- radial bin·sector·scan-order 색상을 toggle해 공간 또는 sequence confounding을
  확인합니다.
- 같은 site에 반복 row가 있으면 임의 평균하지 않고 repeat index를 보존합니다.

NIST는 scatter plot이 관계의 형태, 방향, outlier를 보여주지만 인과를 증명하지
않는다고 설명합니다
([NIST Scatter Plot](https://www.itl.nist.gov/div898/handbook/eda/section3/eda33q.htm)).
따라서 correlation badge에는 `연관이며 원인 증명이 아님`을 고정 문구로 표시합니다.

### 7.3 Across-MSR CD↔FDC·hardware

- outcome과 predictor 모두 MSR당 한 행으로 축약합니다.
- dynamic trace는 recipe step과 pre/during/post window별 mean, std, slope, range,
  missing fraction으로 feature화합니다.
- pooled correlation과 tool·recipe별 correlation을 나란히 표시해 Simpson's paradox를
  확인합니다.
- point 색은 tool, outline은 lot, 화살표 또는 작은 label은 시간 순서로 표현합니다.
- 여러 feature·lag를 탐색했다면 검사한 전체 수와 multiplicity 상태를 표시합니다.
- MSR 결과 하나를 수천 개 raw FDC timestamp에 복제해 큰 `N`을 만들지 않습니다.
- home mock에서 CD와 FDC는 모두 per-MSR 공통 `health` scalar로 편향되므로, 이
  데이터에서 관찰되는 CD↔FDC 상관은 생성기 artifact이며 방법 검증 근거가 아닙니다.
  단일 sequence(§6)와 다중 run 화면 모두에 `데모 데이터` 표식을 답니다.

### 7.4 분포와 공정 능력

기본 분포 화면에는 raw jitter point, median, IQR, mean, σ, MAD, valid `N`, missing을
같이 제공합니다. Violin은 작은 `N`에서 밀도 형태가 과장될 수 있으므로 `N`이 작으면
box + raw point로 자동 전환합니다.

`Cp`, `Cpk`와 같은 capability는 다음 조건을 모두 만족할 때만 엽니다.

- 실제 USL/LSL과 unit, 적용 product/layer·recipe revision이 등록되어 있습니다.
- process가 같은 regime에서 안정적이라는 근거가 있습니다.
- 분석 단위가 독립적인 run/wafer 수준이며 한 wafer의 site를 독립 wafer처럼 세지
  않습니다.
- 분포 가정 또는 non-normal capability 방법이 명시되어 있습니다.

NIST는 process capability를 **in-control process**와 specification의 비교로 정의하며
([NIST Process Capability](https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm)),
capability보다 안정성 확인이 먼저라고 설명합니다
([NIST Process Stability](https://www.itl.nist.gov/div898/handbook/ppc/section4/ppc45.htm)).
따라서 임의 선택 집합의 histogram에 spec line을 얹었다는 이유만으로 Cpk를
계산하지 않습니다.

### 7.5 조건부·연구 기능

- **조건부: variance component**는 tool, lot, wafer, site의 반복 구조와 factor
  식별성이 있을 때 변동 기여도를 보여줍니다. 설계가 부족하면 group box plot만
  제공합니다.
- **조건부: tool matching**은 같은 reference pattern을 여러 CD-SEM에서 반복 측정한
  자료가 있을 때 bias, repeatability, long-term reproducibility를 분리합니다.
- **조건부: Bossung/process window**는 계획된 focus-dose matrix에서만 제공합니다.
- **연구: PCA/MSPC**는 고정 feature schema와 동결된 in-control training period,
  충분한 `n >> p`가 필요합니다. score만 표시하지 않고 contribution과 원 변수를
  함께 보여줘야 합니다.
- **연구: virtual metrology**는 leakage-safe history, time-split 검증, uncertainty와
  out-of-distribution 검출이 필요합니다. 일반 correlation 화면의 다음 단계로 자동
  승격하지 않습니다.

## 8. 이미지 갤러리: 실제 pattern인가, 측정 artifact인가

### 8.1 페이지 역할

Gallery는 `이미지가 있는 site 목록`이 아니라 **측정 결과를 사람 눈으로 검증하고
비교하는 triage queue**여야 합니다. 첫 화면의 기본 정렬은 다음과 같습니다.

1. measurement fail·missing CD가 있는 image입니다.
2. absolute signed delta가 큰 image입니다.
3. addressing·measurement score가 낮은 image입니다.
4. 급격한 sequence/FDC 변화 전후 image입니다.
5. edge·center·선택 sector처럼 공간 filter에 해당하는 image입니다.
6. 정상 reference image입니다.

vendor score의 정의와 보정이 확인되지 않았다면 `낮은 score`는 review 우선순위일 뿐
불량 판정이 아닙니다.

### 8.2 image card와 lightbox에 필요한 정보

| 레이어 | 표시 내용 | 목적 |
| --- | --- | --- |
| Thumbnail | site, sequence, CD, signed delta, fail·quality badge | 많은 image에서 review 순서를 정합니다. |
| Measurement overlay | 측정 ROI, 검출 edge, CD gauge, measurement direction | 숫자가 image의 어느 경계에서 나온 것인지 확인합니다. |
| Signal evidence | 가능하면 gray-level line profile과 edge threshold | contrast·edge algorithm 영향과 실제 폭을 구분합니다. |
| Acquisition metadata | mag, vac, pixel size, landing voltage, scan speed/dwell, detector, repeat index | 서로 다른 촬영 조건의 image를 같은 조건처럼 비교하지 않습니다. |
| Traceability | MSR, recipe revision, parameter, method/object/kind, tool, timestamp, raw image link | chart에서 원 측정까지 역추적합니다. |

Hitachi의 CD-SEM 설명도 SEM gray-level에서 line profile을 얻고 pixel 수로 치수를
계산하며, trapezoid pattern의 top과 bottom 폭이 다를 때 recipe가 측정 위치를
지정한다고 설명합니다
([Hitachi High-Tech, CD-SEM 원리](https://www.hitachi-hightech.com/global/en/knowledge/semiconductor/room/manufacturing/cd-sem.html)).
따라서 image만 확대해서 보여주는 것보다 measurement overlay와 line profile을
함께 보여주는 것이 CD 값 검토에 더 직접적입니다.

### 8.3 비교 mode

- **Same site over time**: 같은 canonical site와 parameter의 MSR별 image strip입니다.
- **Focus vs Reference**: focus image와 reference image를 같은 scale·crop으로
  나란히 표시합니다.
- **Before/After event**: BM/PM·recipe revision 전후의 compatible image pair입니다.
- **Same value, different image**: CD는 비슷하지만 score·profile이 다른 image를
  비교해 measurement ambiguity를 찾습니다.
- **Different value, similar image**: edge algorithm·calibration 차이 가능성을
  검토합니다.

모든 pair view는 동일 pixel scale을 기본으로 하며, resampling·contrast normalization을
사용하면 원본과 별도 표시합니다. 확대율 숫자가 같더라도 calibration·pixel size와
tool이 다르면 물리 scale이 같다고 가정하지 않습니다.

### 8.4 반드시 분리할 artifact evidence

NIST CD-SEM simulation 연구는 noise amplitude, edge detection algorithm, beam size가
repeatability에 영향을 주며, sample shape에 따라 bias가 달라져 일반적인 same-sample
precision test가 일부 오차를 놓칠 수 있음을 보였습니다
([Villarrubia et al., 2005](https://www.nist.gov/publications/simulation-study-repeatability-and-bias-cd-sem)).
또한 SEM과 HRTEM CD 비교 연구에서는 측정 중 hydrocarbon deposition 차이가
test-chip별 SEM offset에 기여했습니다
([Cresswell et al., 2008](https://www.nist.gov/publications/comparison-sem-and-hrtem-cd-measurements-extracted-test-structures-having-feature)).

따라서 Gallery는 다음 항목을 pattern defect와 별도로 표시해야 합니다.

- charging 또는 비정상 contrast입니다.
- focus·astigmatism·blur입니다.
- image drift와 scan distortion입니다.
- contamination 또는 반복 조사에 따른 변화입니다.
- edge threshold·measurement algorithm 차이입니다.
- magnification/pixel calibration과 tool-to-tool matching 상태입니다.

`artifact 의심`은 자동 root-cause가 아니라 review tag입니다. 원 image, acquisition
조건, 같은 site의 재측정과 reference artifact를 확인한 뒤 엔지니어가 결론을 남겨야
합니다.

### 8.5 LER·LWR 확장 조건

CD-SEM에서 LER/LWR은 실제 제공되는 분석이지만
([Hitachi High-Tech CD-SEM 분석 항목](https://www.hitachi-hightech.com/us/en/products/advanced-analytical/microscopy/cdsem.html)),
현재의 scalar `cd_value`와 thumbnail만으로 재계산해서는 안 됩니다. NIST 원 연구도
공급사별 LER definition과 sampling capability가 표준화되지 않았으며 metric과
sampling 조건을 구분해야 한다고 지적합니다
([NIST, CD-SEM LER 측정 조건](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=822538)).

따라서 LER/LWR card는 edge coordinate/profile, sampling interval·length, detrending,
metric definition, algorithm version이 계약에 추가된 후 조건부로 제공합니다.

## 9. 상세 페이지 간 연결 동작

상세 페이지는 독립 dashboard 네 개보다 같은 evidence를 다른 축으로 보는 linked
workspace가 되어야 합니다.

| 시작 동작 | 위치 비교 | Time-Series | 상관 / 분포 | 이미지 갤러리 |
| --- | --- | --- | --- | --- |
| 개요의 WCDU 상승 클릭 | focus delta와 variability map을 엽니다. | 같은 시점의 WCDU lane을 강조합니다. | focus와 peer의 spread distribution을 엽니다. | absolute delta 상위 image를 정렬합니다. |
| map의 site 클릭 | site detail을 유지합니다. | 같은 site의 MSR별 CD trend를 엽니다. | site 또는 같은 radial bin 분포를 엽니다. | 같은 site over time을 엽니다. |
| Time-Series point 클릭 | 해당 MSR을 focus로 바꿉니다. | event·lane cursor를 고정합니다. | 해당 run을 scatter에서 강조합니다. | 해당 MSR image를 표시합니다. |
| correlation outlier 클릭 | 해당 MSR·site를 map에서 강조합니다. | run 또는 sequence를 강조합니다. | pair와 residual을 유지합니다. | 정확한 source image를 엽니다. |
| Gallery image 클릭 | site 위치를 강조합니다. | acquisition sequence를 강조합니다. | 해당 row를 raw point로 강조합니다. | overlay·profile lightbox를 엽니다. |

URL 또는 workspace state에는 최소한 `focus msr`, comparison set, parameter,
physical site key, time point, stratum, reference version을 담아 분석 결과를 재현할 수
있어야 합니다.

## 10. 데이터 준비도와 추가 계약

| 기능 | 필요한 계약 | 현재 확인 상태 | 미충족 시 동작 |
| --- | --- | --- | --- |
| Registered map comparison | wafer size, origin·axis·notch, layout hash, canonical site key | chip/stage 좌표와 wafer geometry 일부는 있으나 layout hash와 변환 version은 없습니다. | raw map만 제공하고 합성·delta를 금지합니다. |
| WCDU·radial·sector | valid CD, unit, edge exclusion, 중심·notch | CD와 geometry 일부는 있습니다. edge exclusion·notch 신뢰 계약은 추가 확인이 필요합니다. | 계산 가능 metric만 표시하고 방향 분석을 닫습니다. |
| Run History | 실제 MSR timestamp, tool, lot, recipe revision, parameter summary | timestamp·tool·lot·recipe name과 summary는 있습니다. recipe revision은 없습니다. | revision이 다른 집단을 자동 합성하지 않습니다. |
| Within-Run Sequence | sequence, sequence timestamp, 좌표, dynamic FDC | sequence·좌표·dynamic FDC는 있으나 sequence timestamp가 없습니다. | X축과 slope를 `per sequence`로만 표시합니다. |
| Frozen-baseline SPC | baseline ID/version, regime, 승인·제외 이력 | 현재 사용자 선택 집합만 있습니다. | run chart만 표시합니다. |
| CD↔hardware | event-time join key, typed value·unit, aggregation window | fixed/dynamic FDC가 있으나 모든 hardware source의 typed join은 필요합니다. | 같은 MSR exact join만 허용합니다. |
| Capability | USL/LSL, unit, 적용 범위, stable stream | 공식 specification·stability 계약은 확인되지 않습니다. | histogram·ECDF까지만 제공합니다. |
| Image evidence | raw image, scale, ROI·edge·line profile, beam/scan 조건, algorithm version | image 이름과 mag/vac/pixel·일부 score는 있으나 overlay/profile 계약은 없습니다. | 원 image와 현재 metadata만 표시합니다. |
| Tool matching | reference artifact ID, repeat/reload, tool, calibration regime | production MSR과 tool ID는 있으나 reference study 계약은 없습니다. | tool별 차이를 process와 metrology로 분해하지 않습니다. |
| LER/LWR | edge trace, sample interval·length, detrending과 metric definition | 현재 scalar CD 중심입니다. | 기능을 숨기고 필요한 계약을 안내합니다. |

현재 계약의 자세한 근거는 [MSR 파일 설명](../../datatables/msr_file_pickle.txt),
[pickle 구조](../../datatables/msr_file_pickle.txt),
[프런트 MSR API](../../../front-dev-home/app/composables/useMsrFileApi.ts)에 있습니다.

**Phase-1(offline mock) 처분.** 위 표에서 `현재 확인 상태`가 계약 미충족인 항목
(registered map comparison, frozen-baseline SPC, capability, tool matching, image
overlay/profile, LER/LWR)은 Phase-1 mock 데이터로 live-verify 할 수 없습니다. 이
항목들은 UI를 미리 완성하지 않고 readiness placeholder와 필요한 계약만 표시하며,
실제 구현·검증은 office 계약이 연결되는 Phase 2/3으로 미룹니다. Phase-1에서 검증
가능한 범위는 단일 MSR 공간 진단, 단일 sequence+FDC, exact-pair correlation, review
queue입니다.

## 11. Source-to-feature 근거 매트릭스

| 1차 출처 | 출처가 직접 뒷받침하는 내용 | Skewvoir 기능 | 성숙도 | 적용 시 주의 |
| --- | --- | --- | --- | --- |
| [SEMI E142](https://www.semi.org/en/standards-watch-2026-apr/major-revision-underway-for-semi-e142) | substrate map data와 서로 다른 XY 좌표계 변환·정렬 필요성입니다. | 위치 비교 전 coordinate/layout gate입니다. | 정착 관행 | 표준 명칭을 쓴다고 실제 좌표 변환이 검증되는 것은 아닙니다. |
| [SEMI E133](https://store-us.semi.org/products/e13300-semi-e133-specification-for-automated-process-control-systems-interface) | fab PCS에 R2R, FD/FC/FP, SPC와 equipment data 연계가 포함됩니다. | Time-Series의 CD·FDC·quality evidence lane입니다. | 정착 관행 | 표준은 인터페이스 범위를 지지하며 Skewvoir의 판정 threshold를 정하지 않습니다. |
| [NIST wafer subgroup case](https://www.itl.nist.gov/div898/handbook/pmc/section6/pmc613.htm) | wafer를 subgroup으로 mean과 S chart를 함께 분석합니다. | MSR별 CD level과 within-wafer spread의 동기화 lane입니다. | 정착 관행 | rational subgroup과 sampling consistency가 필요합니다. |
| [NIST Individuals chart](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc322.htm) | 시간점마다 개별 측정 하나인 경우 moving range로 변동을 추정합니다. | MSR 요약값의 I-MR option입니다. | 조건부 분석 | 승인된 안정 history 없이 현재 선택 집합으로 limit을 만들지 않습니다. |
| [NIST EWMA](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm)·[CUSUM](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm) | 작은·점진적 drift와 작은 mean shift 검출 특성입니다. | Time-Series drift detector입니다. | 조건부 분석 | λ, target shift, ARL·false-alarm 정책과 frozen baseline이 필요합니다. |
| [NIST Process Capability](https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm) | capability는 in-control process와 specification의 비교입니다. | 상관 / 분포의 Cp·Cpk readiness gate입니다. | 조건부 분석 | stability, unit, USL/LSL과 분포 가정을 먼저 확인합니다. |
| [Hitachi CD-SEM 분석 서비스](https://www.hitachi-hightech.com/us/en/products/advanced-analytical/microscopy/cdsem.html) | across-wafer/local CDU와 LER/LWR이 실제 CD-SEM 분석 항목입니다. | 위치 비교의 CDU와 향후 Gallery roughness입니다. | 정착 관행 | vendor 성능 주장이 아니라 실제 기능 범위의 근거로만 사용합니다. |
| [Lim et al., 2019](https://doi.org/10.2494/photopolymer.32.441) | wafer center-to-edge CD 변화가 WCDU 문제로 나타납니다. | radial profile과 edge-center delta입니다. | 정착 관행 | 한 원인으로 고정하지 않고 공정·장비 문맥과 함께 봅니다. |
| [Otaka et al., 2006](https://doi.org/10.1380/jsssj.27.636) | CD 정확도에 short/long-term repeatability, tool matching, traceable calibration이 포함됩니다. | 별도 measurement-health trend와 tool matching view입니다. | 정착 관행 | production wafer tool 차이만으로 metrology bias를 추정하지 않습니다. |
| [Villarrubia et al., 2005](https://www.nist.gov/publications/simulation-study-repeatability-and-bias-cd-sem) | noise, edge algorithm, beam size와 sample shape가 repeatability·bias에 영향을 줍니다. | Gallery의 overlay·profile·artifact evidence입니다. | 정착 관행 | image appearance 또는 repeatability 하나를 accuracy로 간주하지 않습니다. |
| [Hitachi CD-SEM 원리](https://www.hitachi-hightech.com/global/en/knowledge/semiconductor/room/manufacturing/cd-sem.html) | gray-level line profile, pixel 기반 CD, recipe가 정한 측정 위치입니다. | Gallery measurement overlay와 line profile입니다. | 정착 관행 | top/bottom·method 차이를 같은 CD처럼 비교하지 않습니다. |
| [Cresswell et al., 2008](https://www.nist.gov/publications/comparison-sem-and-hrtem-cd-measurements-extracted-test-structures-having-feature) | hydrocarbon deposition 차이가 SEM CD offset 변동에 기여했습니다. | acquisition repeat·contamination review tag입니다. | 정착 관행 | image 재측정도 sample을 바꾸지 않는다는 가정을 두지 않습니다. |
| [NIST LER 연구](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=822538) | LER/LWR metric과 sampling이 공급사 간 표준화되지 않았고 조건에 민감합니다. | 향후 LER/LWR contract와 Gallery card입니다. | 조건부 분석 | scalar CD나 thumbnail로 roughness를 역산하지 않습니다. |
| [Bossung/FEM 연구](https://doi.org/10.1016/j.mee.2011.02.108) | focus·dose별 CD로 process window와 iso-focal 조건을 평가합니다. | 계획된 FEM의 focus-dose contour입니다. | 조건부 분석 | 일반 history의 관측값을 DOE처럼 해석하지 않습니다. |
| [Ohri et al., 2025](https://doi.org/10.1117/12.3051932) | Zernike 기반 wafer CDU model과 track module fingerprinting을 제안합니다. | 위치 비교의 shape component와 module matching 연구입니다. | 연구 기능 | HVM 검증·설명 가능성·raw map 대조가 필요합니다. |

## 12. 제품 적용 우선순위

### P0. 분석 진실성

- 네 페이지가 같은 focus·comparison set·compatibility result를 공유하게 합니다.
- site, sequence, MSR/run, tool-time의 분석 단위를 API와 UI에 명시합니다.
- reference, exclusion reason, valid `N`, coverage, unit을 모든 chart 계약에 넣습니다.
- 위치 비교 전 coordinate/layout gate와 Time-Series baseline gate를 구현합니다.

### P1. 정착된 엔지니어링 evidence

- 위치 비교에 raw/reference/delta/variability/coverage map과 radial profile을 제공합니다.
- Time-Series에 level, WCDU, quality, tool-context lane과 event overlay를 제공합니다.
- 상관 / 분포에 exact-pair 품질, MSR/run mode, strata, stability/capability gate를
  제공합니다.
- Gallery에 residual·fail triage, same-site compare, metadata와 measurement overlay를
  제공합니다.
- 네 페이지의 selection과 raw evidence drill-through를 연결합니다.

### P2. 조건부 분석

- 승인 baseline에 I-MR, X-bar/S, EWMA·CUSUM을 추가합니다.
- reference artifact가 있는 tool matching과 variance component를 추가합니다.
- 계획된 focus-dose matrix에만 Bossung/process-window 분석을 추가합니다.
- edge trace 계약이 준비된 뒤 LER/LWR을 추가합니다.

### P3. 연구 기능

- Zernike·spline spatial fingerprint와 historical similarity search를 검증합니다.
- engineer-reviewed label이 쌓인 뒤 signature clustering·classification을 검증합니다.
- PCA/MSPC와 virtual metrology는 offline acceptance, uncertainty, drift monitoring과
  rollback 정책을 가진 별도 연구 기능으로 운영합니다.

이 순서를 따르면 측정 개요는 모든 분석을 축약한 복잡한 dashboard가 아니라,
`어디·언제·무엇과·실제 image`라는 네 가지 후속 질문으로 엔지니어를 안내하는
wayfinder가 됩니다. 상세 페이지는 같은 측정 evidence를 공간, 시간, 관계, 원본
image라는 서로 다른 축으로 검증하는 workspace가 됩니다.
