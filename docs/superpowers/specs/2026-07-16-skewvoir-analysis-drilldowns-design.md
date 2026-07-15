# 스큐보아 상세 분석 워크스페이스 — Design

- Date: 2026-07-16
- Status: **설계 제안 — 사용자 검토 및 구현 대기**
- Scope: `front-dev-home/app/components/ebeam/skewvoir/`의 `위치 비교`, `Time-Series`, `상관 / 분포`, `이미지 갤러리`와 `측정 개요`의 상세 분석 진입 UX
- 선행 설계: [측정 개요 Design](2026-07-15-skewvoir-phase-b-measurement-overview-design.md), [검색 Design](2026-07-14-skewvoir-search-design.md)
- 방법론 근거: [웨이퍼 분석 방법 연구](../../issues/skewvoir/wafer-analysis-method-research.md), [상세 분석 벤치마크 연구](../../issues/skewvoir/analysis-drilldown-benchmark-research.md)

## 1. 결론

스큐보아의 `측정 개요`는 **한 MSR의 산출물을 빠르게 읽고 다음 조사 방향을
결정하는 페이지**입니다. 나머지 네 페이지는 개요 차트를 크게 다시 그리는 곳이
아니라, 엔지니어가 다음 질문을 하나씩 깊게 조사하는 워크벤치가 되어야 합니다.

| 페이지 | 엔지니어의 질문 | 핵심 산출물 |
| --- | --- | --- |
| 위치 비교 | 차이가 **어디에** 있고 level 변화인가 pattern 변화인가? | raw/reference/delta/variability map, radial·sector profile, site 근거 |
| Time-Series | 변화가 **언제** 시작됐고 어떤 tool·lot·정비 구간에 묶이는가? | run chart, sequence trace, control evidence, event overlay |
| 상관 / 분포 | 무엇이 **함께 움직이고**, 분포와 변동원은 어떻게 다른가? | paired scatter, stratified distribution, feature relationship, variance source |
| 이미지 갤러리 | 실제 pattern 변화인가 **측정 artifact**인가? | priority review queue, same-site filmstrip, overlay·profile evidence |

페이지 이름은 유지하되 내용은 고정하지 않습니다. 선택이 한 개이면 **한 실행의
진단**, 여러 개이면 **호환 가능한 측정 집단의 비교**로 같은 메뉴의 질문과 화면이
적응합니다. 단순히 다중 차트를 숨기거나 단일 데이터를 여러 번 복제하지 않습니다.

## 2. 제품 이야기와 사용자 흐름

### 2.1 기본 흐름

```text
검색에서 MSR 선택
  ↓
측정 개요
  ├─ 측정이 온전한가?        coverage · failure · alignment
  ├─ 어떤 parameter가 다른가? level · spread · outlier
  └─ 어디를 더 조사할까?     4개 상세 페이지로 evidence hand-off
       ├─ 위치 비교           spatial pattern
       ├─ Time-Series         sequence / historical drift
       ├─ 상관 / 분포         relationship / variation
       └─ 이미지 갤러리       visual evidence
```

`측정 개요`가 결론을 대신 내리지는 않습니다. 확인된 사실과 데이터 준비도를 요약하고,
상세 페이지는 그 사실을 원시 site·MSR·이미지·장비 record까지 추적할 수 있게 합니다.

### 2.2 두 가지 분석 범위

| 범위 | 진입 조건 | 제품 의미 | 허용되는 표현 |
| --- | --- | --- | --- |
| 단일 MSR | focus 한 개, 비교 세트 없음 | 한 번의 측정 실행 진단 | site, sequence, 공간·이미지 근거 |
| 다중 MSR | 사용자가 2개 이상 선택 | 호환 가능한 실행 집단 탐색 | MSR별 비교, 시간 추이, 층화, reference 대비 |

다중 선택은 곧 비교 가능함을 뜻하지 않습니다. 화면은 먼저
`N개 선택 → M개 로드 → K개 호환 → G개 그룹`을 보여주고, 현재 focus와 같은
compatibility group만 기본 분석합니다. 제외된 MSR과 이유는 숨기지 않습니다.

### 2.3 측정 개요의 역할

측정 개요에는 다음만 남깁니다.

- parameter별 coverage, 실패, 중심, 산포와 현재 선택한 site의 근거입니다.
- 실행 조건, alignment, wafer map, radius, 분포, SEM의 **대표 증거**입니다.
- 상세 조사가 가치 있는 경우에만 `더 보기` hand-off를 제시합니다.

예시는 다음과 같습니다.

| 개요에서 확인한 사실 | hand-off 문구 | 이동 대상과 전달 상태 |
| --- | --- | --- |
| edge와 center의 차이가 큼 | `공간 pattern 자세히 보기` | 위치 비교 + parameter + focus MSR |
| 후반 sequence에서 값 이동 | `측정 순서와 FDC 같이 보기` | Time-Series + parameter + sequence |
| 두 parameter가 같은 site에서 함께 변화 | `짝지은 값 확인하기` | 상관 / 분포 + X/Y parameter |
| 이상·실패 site에 이미지 존재 | `검토할 이미지 N장` | 갤러리 + 이상·실패 필터 |

개요에서 상세 페이지의 미니 차트를 네 개 더 만들지 않습니다. **사실 → 다음 질문**만
연결하여 정보 밀도와 판단 순서를 지킵니다.

## 3. 업계 분석을 제품 기능으로 번역하는 원칙

반도체 계측·공정 모니터링에서 널리 쓰이는 분석을 그대로 메뉴로 복사하지 않고,
Skewvoir 데이터의 grain과 준비도에 맞춰 다음처럼 배치합니다.

| 분석 관행 | Skewvoir 적용 | 제품 단계 |
| --- | --- | --- |
| wafer/site map과 center-edge·radial profile | 위치 비교의 기본 레이어 | 즉시 가치 |
| reference 대비 delta와 site variability | 호환 다중 MSR 위치 비교 | 즉시 가치 |
| run chart, I-MR, EWMA, CUSUM | 다중 MSR Time-Series | baseline 준비도에 따라 단계 공개 |
| tool·lot·maintenance stratification | Time-Series와 상관 / 분포의 공통 filter | 즉시 가치 |
| paired scatter와 분포 비교 | 같은 site 또는 MSR feature grain으로만 계산 | 즉시 가치 |
| variance component | 반복과 factor 식별성이 충분한 집단 | 고급 분석 |
| spatial signature similarity | engineer-reviewed history가 축적된 뒤 | 연구 기능 |
| PCA/MSPC·virtual metrology | 동결 baseline, feature schema, 시간 분할 검증 이후 | 별도 연구 기능 |

통계 이름보다 먼저 `어떤 질문에 답하는가`, `분석 단위는 무엇인가`, `평가 가능한가`를
보여줍니다.

벤치마크의 직접 근거는 다음과 같습니다.

| 1차 근거 | 설계에 반영한 결정 |
| --- | --- |
| [SEMI E142](https://www.semi.org/en/standards-watch-2026-apr/major-revision-underway-for-semi-e142) | map을 합치거나 빼기 전에 layout·좌표계 registration을 검사합니다. |
| [SEMI E133](https://store-us.semi.org/products/e13300-semi-e133-specification-for-automated-process-control-systems-interface) | CD outcome, tool condition, measurement quality를 한 점수 대신 분리된 evidence lane으로 유지합니다. |
| [NIST/SEMATECH control-chart guidance](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc3.htm) | run chart는 항상 가능하지만 control chart는 안정된 역사 baseline이 있을 때만 엽니다. |
| [NIST process capability](https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm) | 실제 spec과 안정성 확인 전에는 Cp/Cpk를 제공하지 않습니다. |
| [Hitachi CD-SEM measurement principle](https://www.hitachi-hightech.com/global/en/knowledge/semiconductor/room/manufacturing/cd-sem.html) | Gallery를 image, measurement position, edge/line-profile 근거가 연결된 검토 화면으로 설계합니다. |
| [NIST CD-SEM repeatability/bias simulation](https://www.nist.gov/publications/simulation-study-repeatability-and-bias-cd-sem) | image appearance와 pattern 변화 외에 noise·beam·edge algorithm artifact를 별도 검토합니다. |

상세 source-to-feature 근거와 정착/조건부/연구 기능 구분은
[상세 분석 벤치마크 연구](../../issues/skewvoir/analysis-drilldown-benchmark-research.md)에
기록합니다.

## 4. 전역 UI/UX 계약

### 4.1 모든 상세 페이지의 공통 Context Bar

상세 페이지 최상단에는 하나의 공통 context bar가 있습니다.

```text
[단일 MSR | 비교 세트 12] [Focus MSR] [Parameter]
[호환 10 / 제외 2] [사용자 선택 · 탐색]                 [비교 세트 편집]
```

| 항목 | 동작 |
| --- | --- |
| 분석 범위 | 단일/다중을 명시합니다. 다중에서 한 개만 호환되면 단일 진단으로 전환하되 이유를 알립니다. |
| Focus MSR | 다중 집단에서도 delta, image, detail table의 중심 MSR을 하나 유지합니다. |
| Parameter | 모든 페이지가 같은 active parameter를 공유합니다. 페이지 이동 시 유지합니다. |
| 호환성 | 포함·제외 수, group 수, 주요 제외 사유를 표시합니다. 클릭하면 readiness drawer가 열립니다. |
| 근거 성격 | `사용자 선택 · 탐색`과 `승인 baseline vN`을 명확히 구분합니다. |

현재 `Time-Series.vue`에만 있는 비교 세트 선택기는 이 공통 bar로 승격합니다. 한
페이지에서 편집한 세트가 다른 상세 페이지에서도 그대로 유지되어야 합니다.

### 4.2 페이지마다 같은 읽기 순서

1. **Answer strip**: 중요한 사실 3~5개를 문장과 숫자로 요약합니다.
2. **Primary workbench**: 질문에 가장 직접적인 차트·맵을 크게 보여줍니다.
3. **Breakdown**: tool, lot, radius, sector, site 등으로 원인을 좁힙니다.
4. **Evidence table/drawer**: 계산에 들어간 row, 제외 사유, 이미지와 raw metadata를
   확인합니다.

Answer strip은 `정상/불량` 단일 health score가 아닙니다. 예를 들어 위치 비교는
`level shift`, `shape difference`, `unstable sites`, `coverage`를 분리합니다.

### 4.3 연결 선택

다음 선택은 페이지를 넘어 유지합니다.

- focus MSR
- active parameter
- focused site (`layout + chip + mp`, sequence는 보조 식별자)
- 선택한 tool·lot filter
- reference 종류

맵의 site를 누르면 profile, table, SEM preview가 같은 site로 이동합니다. Time-Series의
MSR을 누르면 focus MSR이 바뀌고, Gallery는 그 MSR의 같은 site를 먼저 보여줍니다.

### 4.4 상태와 언어

| 상태 | 표현 |
| --- | --- |
| 계산 가능 | 값 + 단위 + N + reference를 표시합니다. |
| 제한적 | 결과를 표시하되 `교집합 18/45 sites`처럼 제한을 인접 표기합니다. |
| 평가 불가 | 빈 차트 대신 이유와 필요한 데이터를 표시합니다. |
| 데이터 로드 실패 | 이전 결과를 최신 결과처럼 유지하지 않고 stale 상태와 재시도를 표시합니다. |
| 탐색 결과 | `원인 후보`, `연관`을 사용하며 `원인`, `불량`으로 단정하지 않습니다. |

## 5. 위치 비교 — Spatial Pattern Workbench

### 5.1 답할 질문

> 값의 차이가 wafer 전체 level 이동인가, center-edge·방향성·국소 hotspot 같은
> 공간 pattern 변화인가?

### 5.2 단일 MSR 화면

단일 MSR에서는 기존의 wafer-to-wafer `σ=0` 합성 맵을 만들지 않습니다. 한 실행의
공간 구조를 진단합니다.

```text
┌ Answer: center↔edge Δ | 방향 차이 | 국소 residual | coverage ┐
├ Layer [Raw | 중심 보정 | 공간 residual | 실패]  [색 범위]     ┤
│                         큰 wafer map                           │
├ Radial profile ─────────┬ Sector profile ──────────────────────┤
├ Site evidence table ────┴ selected site SEM preview ───────────┤
└ 좌표계 · layout · transform · N · missing ─────────────────────┘
```

레이어의 의미는 다음과 같습니다.

| 레이어 | 계산 | 엔지니어 가치 |
| --- | --- | --- |
| Raw | 원 측정값 | 실제 level과 위치를 그대로 확인합니다. |
| 중심 보정 | site 값 - parameter median 또는 승인 target | nominal 차이를 제거하고 shape를 봅니다. |
| 공간 residual | 검증된 radial/surface trend를 뺀 잔차 | 전역 pattern과 국소 이상을 분리합니다. |
| 실패 | nullable 측정과 image/alignment 실패 위치 | 데이터 부재의 공간 군집을 확인합니다. |

- radial profile은 radius bin별 median, spread, 유효 site 수를 같이 보여줍니다.
- sector profile은 notch와 좌표 방향이 검증된 경우에만 엽니다.
- sequence scan path를 켜면 공간 pattern이 측정 순서 drift와 혼재하는지 확인합니다.
- site 클릭은 값, residual, radius, chip/MP, sequence, 이미지 존재 여부를 한 drawer에
  모읍니다.

### 5.3 다중 MSR 화면

기본 비교는 `focus MSR vs reference median`입니다. reference는 호환 MSR의 site별
median이며 focus를 reference 계산에서 제외합니다.

```text
┌ Answer: level Δ | shape RMSE | unstable sites | common coverage ┐
├ [Focus] [Reference] [Delta] [Variability] [Coverage] 레이어      ┤
│  reference map          focus delta map          variability map │
├ selected site의 MSR별 값 ───── radial/sector profile overlay ────┤
└ MSR small multiples / similarity 순위 / 제외 사유 ───────────────┘
```

| 결과 | 의미 | 주의 |
| --- | --- | --- |
| Reference median map | compatible cohort의 대표 spatial level | focus 제외 여부를 표시합니다. |
| Focus delta map | focus - site reference | 공통 site에서만 계산합니다. |
| Variability map | site별 wafer-to-wafer sample σ 또는 MAD | site별 유효 MSR 수를 함께 표시합니다. |
| Coverage map | site별 유효 MSR 수 | 낮은 coverage를 안정 영역처럼 보이지 않게 합니다. |
| Shape similarity | center-corrected RMSE, correlation | 원인 label이 아니라 pattern 유사도입니다. |

`Composite Mean` 하나만 보여주는 현재 구조는 reference와 candidate가 섞여 차이가
사라집니다. 새 기본값은 **reference와 delta를 나란히** 두는 것입니다. 평균 map은
보조 레이어로 남길 수 있지만 첫 화면이 아닙니다.

### 5.4 주요 interaction

- `Reference`: leave-focus-out median, 특정 MSR, 승인 baseline 중 하나를 고릅니다.
- `Compare`: focus를 고정한 채 다른 MSR을 화살표 또는 table로 순회합니다.
- `Brush`: map에서 영역을 그리면 profile과 site table이 그 영역으로 필터됩니다.
- `Pin scale`: 여러 map이 같은 색 범위를 사용하게 하여 색상 과장을 막습니다.
- `동일 위치 이미지`: focused site를 Gallery의 same-site 비교로 보냅니다.

### 5.5 평가 불가 조건

- coordinate origin, axis, notch, wafer size가 불명확하면 sector·회전 비교를 닫습니다.
- layout이 다르면 union map을 만들지 않고 공통 site 수와 별도 group을 보여줍니다.
- 단일 MSR에서는 variability map을 만들지 않습니다.
- surface fit의 distinct coordinate·coverage가 부족하면 raw와 center-corrected까지만
  제공합니다.

## 6. Time-Series — Drift & Event Workbench

### 6.1 답할 질문

> 변화가 언제 시작됐고, 지속적인 drift인가 일시적인 excursion인가, 어떤 tool·lot·
> recipe revision·maintenance 구간과 함께 나타나는가?

### 6.2 단일 MSR 화면 — 실제 시간 대신 측정 순서

sequence별 timestamp가 없으므로 제목과 X축을 `Time-Series`가 아니라
`측정 순서 (Sequence)`로 명시합니다.

```text
┌ Answer: 시작↔끝 Δ | robust slope/sequence | change candidate | 실패 구간 ┐
├ CD value ──────────────────────────── shared sequence cursor ─────────────┤
├ Dynamic FDC [family/metric] ───────── aligned stacked panes ─────────────┤
├ scan-path mini wafer ──────────────── failure/image event ribbon ────────┤
└ selected sequence: site · CD · FDC · image · alignment evidence ─────────┘
```

- CD와 FDC를 단위가 다른 하나의 Y축에 겹치지 않고 **정렬된 stacked pane**으로
  표시합니다.
- 시작값, 끝값, range, robust slope, missing fraction을 metric별로 제공합니다.
- cursor를 움직이면 wafer scan path와 SEM image가 같은 sequence로 이동합니다.
- scan path와 CD trend가 유사하면 `공간 위치와 순서 효과가 혼재할 수 있음`을
  표시합니다.
- 기울기 단위는 `per sequence`입니다. 초당 변화나 lag time으로 표현하지 않습니다.

### 6.3 다중 MSR 화면 — 공정·장비 run chart

```text
┌ Answer: latest Δ | drift onset | affected tool/lot | baseline status ┐
├ Metric [mean|median|3σ|coverage|fail|edge-center|FDC…] [group/color] ┤
│                         main run chart                               │
│ [engineering/spec limits] [control limits] [event overlays]         │
├ spread/coverage companion pane ───── tool·lot small multiples ──────┤
└ MSR table: timestamp · value · tool · lot · regime · evidence ──────┘
```

Metric family는 다음과 같습니다.

| Family | 기본 metric | 용도 |
| --- | --- | --- |
| Level | mean, median, target delta | 중심 이동을 봅니다. |
| Uniformity | sample σ, WCDU(3σ), MAD, IQR | wafer 내 산포 변화를 한 숫자에 고정하지 않고 봅니다. |
| Completeness | coverage, fail ratio, image fail | 측정 품질 변화를 봅니다. |
| Spatial | edge-center Δ, radial slope, residual RMS | shape drift를 수치화합니다. |
| Tool evidence | fixed FDC, dynamic FDC summary, hardware feature | 원인 후보를 좁힙니다. |

기본 chart는 같은 time cursor를 공유하는 네 lane으로 구성합니다.

1. `CD level`: mean, median, target delta입니다.
2. `CD uniformity`: σ, WCDU(3σ), MAD, edge-center delta입니다.
3. `Measurement quality`: coverage, fail ratio, alignment/image failure입니다.
4. `Tool context`: fixed/dynamic FDC summary와 maintenance·recipe event입니다.

한 화면에서 네 lane을 모두 읽을 수 있게 하되, metric picker로 각 lane의 대표 metric을
바꿉니다. 서로 다른 evidence family를 한 anomaly score나 한 Y축에 합치지 않습니다.

### 6.4 Run chart와 control chart를 분리

- 모든 호환 세트는 descriptive run chart를 볼 수 있습니다.
- I-MR, EWMA, CUSUM은 승인된 in-control baseline과 regime version이 있을 때만
  활성화합니다.
- 사용자가 선택한 현재 집합으로 control limit을 매번 다시 계산하지 않습니다.
- `USL/LSL`, engineering target, statistical control limit은 선 종류와 legend를
  분리합니다.
- 현재 leave-one-out `%/σ` 판정은 `선택 집합 탐색 편차`로 이름을 바꾸며 공식
  control 상태처럼 보이지 않게 합니다.

EWMA는 작은 지속 이동, CUSUM은 사전 정의한 최소 shift 검출에 유용하지만 둘 다
baseline과 false-alarm 설계가 필요합니다. 준비되지 않으면 비활성 control과 필요한
조건을 설명하고 run chart만 제공합니다.

### 6.5 Event context

차트 아래 event lane에 다음을 겹칩니다.

- tool, lot, recipe revision과 software/calibration regime 경계입니다.
- BM/PM 시작·종료와 category입니다.
- alignment failure, coverage 급락, image failure입니다.
- hardware pre/during/post feature가 있는 경우 raw record 링크입니다.

event는 상관 문맥이며 원인 확정이 아닙니다. 점 클릭 시 해당 MSR로 focus가 바뀌고
`위치 비교`, `상관 / 분포`, `갤러리`로 동일 상태를 넘깁니다.

## 7. 상관 / 분포 — Factor Explorer

### 7.1 답할 질문

> 어떤 측정·장비 factor가 결과와 함께 움직이며, 그 관계가 tool·lot·공간 구역을
> 나누어도 유지되는가? 분포의 이동·확산·꼬리 중 무엇이 달라졌는가?

### 7.2 Query Builder

```text
[Grain: Site/Sequence | MSR] [X feature] [Y feature]
[Color: tool/lot/radius/sector] [Facet] [Range] [Spec/target]
```

- 단일 MSR의 기본 grain은 `Site/Sequence`입니다.
- 다중 MSR의 기본 grain은 `MSR`입니다.
- grain을 바꾸면 허용 feature 목록도 바뀝니다. 한 MSR의 45 site를 MSR 45개처럼
  취급하지 않습니다.
- feature label에는 이름, 단위, aggregation, source를 표시합니다.

### 7.3 단일 MSR 화면

| 분석 | join | 제공 정보 |
| --- | --- | --- |
| parameter X ↔ Y | 같은 canonical site key | scatter, Pearson r, Spearman ρ, pair N, missing N |
| CD ↔ dynamic FDC | 같은 MSR + sequence | scatter, sequence 방향, selected point evidence |
| 분포 | active parameter의 measured site | histogram/ECDF, median/IQR, mean/3σ, coverage |
| 공간 group 비교 | radius bin 또는 검증된 sector | box/violin + raw points + group N |

산점도와 분포를 별개 카드로 두지 않고 같은 query의 두 관점으로 연결합니다.

```text
┌ Relationship summary: r | ρ | pair N | missing | grain ┐
├ scatter + marginal distribution ─── correlation matrix ┤
├ selected groups ECDF/box + raw points ────────────────┤
└ paired rows · site metadata · SEM preview ─────────────┘
```

### 7.4 다중 MSR 화면

MSR마다 한 행인 feature table을 사용합니다. 후보 feature는 parameter level/spread,
coverage/failure, spatial feature, `fixed_fdc`, dynamic FDC summary, event-time으로 결합한
hardware feature입니다.

- 전체 pooled scatter와 tool별 estimate를 나란히 보여 Simpson's paradox를 확인합니다.
- color는 tool, lot, maintenance regime, recipe revision 중 하나를 선택합니다.
- 분포는 `focus group vs reference`, tool별, lot별 ECDF/box/violin을 제공합니다.
- authoritative USL/LSL이 있을 때만 out-of-spec count와 capability 후보를 표시합니다.
- 반복과 factor 식별성이 충분하면 `변동 기여` 고급 패널에서 tool/lot/wafer/site
  variance component를 보여줍니다.

### 7.5 상관 결과의 설명 계약

모든 relationship에는 다음을 붙입니다.

```text
Grain: MSR · N=24 (missing 3) · Pearson r=… · Spearman ρ=…
Color: tool · Window: during measurement · Exploratory association
연관은 원인을 증명하지 않습니다.
```

- 상수에 가까운 변수, pair 부족, join 실패는 `평가 불가`입니다.
- 여러 feature를 훑는 correlation matrix는 discovery 도구입니다. 선택한 최대 상관을
  검증 완료 결과처럼 승격하지 않습니다.
- mock의 공통 `health`가 만든 CD↔FDC 상관은 제품 방법 검증 근거로 사용하지 않습니다.
- 회귀선은 raw point를 숨기지 않으며 비선형·이분산·outlier를 먼저 볼 수 있게 합니다.

## 8. 이미지 갤러리 — Visual Evidence Workbench

### 8.1 답할 질문

> 어떤 이미지를 먼저 봐야 하며, 같은 위치·같은 pattern이 다른 MSR에서도 반복되는가?

### 8.2 단일 MSR — review queue

현재의 단순 filename grid를 evidence queue로 바꿉니다. 목표는 이미지를 크게 보는
것이 아니라 CD 숫자가 **어느 경계와 signal에서 계산되었는지**, 촬영 조건 차이가
해석을 바꾸는지 확인하는 것입니다.

```text
┌ 검토 요약: 실패 | site 이상 | 큰 residual | score monitor | 전체 ┐
├ Filter [이상·실패 우선] [radius/sector] [sequence]  Sort […]     ┤
│ image cards: thumbnail · chip/MP · CD · residual · reason        │
├ full viewer ─────────────── metadata/evidence drawer ─────────────┤
└ 이전/다음 · wafer에서 위치 보기 · 같은 위치 비교 ───────────────┘
```

기본 우선순위는 다음과 같습니다.

1. 측정 실패 또는 image failure입니다.
2. site verdict가 abnormal/watch인 이미지입니다.
3. center/radial trend를 제거한 residual 절대값이 큰 이미지입니다.
4. vendor measurement/addressing score가 낮은 이미지입니다. 단, `모니터링`으로만
   표시하고 판정 이유에는 넣지 않습니다.
5. 나머지는 wafer scan sequence 순서입니다.

카드에는 `chip/MP`, sequence, parameter/value/unit, residual, radius, verdict reason을
보여줍니다. thumbnail 클릭은 full viewer와 wafer map focus를 동시에 이동합니다.

### 8.3 다중 MSR — same-site filmstrip

다중 모드의 기본 단위는 이미지 파일이 아니라 **canonical site**입니다.

- 왼쪽에서 site를 고르면 오른쪽에 MSR 시간순 filmstrip을 표시합니다.
- reference, focus, before/after maintenance 이미지를 pin하여 나란히 비교합니다.
- 각 이미지 아래 CD, delta, tool, lot, timestamp, mag/vac/pixel을 표시합니다.
- image missing을 빈칸으로 유지하여 변화가 없는 것처럼 압축하지 않습니다.
- 위치·배율·pixel 조건이 다르면 `시각 비교 제한`을 표시합니다.

`similar pattern` 검색은 engineer-reviewed signature library가 쌓인 이후의 연구
기능입니다. 초기 버전은 같은 site, 같은 residual ranking, 같은 metadata 조건의
deterministic 검색을 우선합니다.

### 8.4 Full viewer

| 영역 | 내용 |
| --- | --- |
| Image | 원본 확대, pan/zoom, scale bar입니다. brightness/contrast는 화면 표시만 변경합니다. |
| Measurement | CD 값, parameter, method/object/kind, chip/MP, sequence입니다. |
| Measurement evidence | 제공되는 경우 ROI, 검출 edge, CD gauge, measurement direction, gray-level line profile입니다. |
| Acquisition | mag, vac, pixel size, landing voltage, scan/dwell, detector, repeat index, alignment와 image source입니다. |
| Comparison | reference delta, site history, 같은 위치의 앞/뒤 이미지입니다. |
| Navigation | wafer 위치, Time-Series MSR, 상관 point로 이동합니다. |

측정 edge/ROI/line profile은 backend가 좌표, physical scale, threshold와 algorithm
version을 제공할 때만 추가합니다. 제공하지 않으면 기능을 숨기고 `원본 image만
제공됨`으로 표시합니다. 등록 정보 없이 pixel difference image를 만들어 morphology
변화처럼 제시하지 않습니다.

Gallery review tag는 pattern과 artifact evidence를 분리합니다. `charging/contrast`,
`focus/astigmatism`, `image drift`, `contamination/repeat exposure`, `edge algorithm`,
`pixel calibration`은 자동 root-cause가 아니라 엔지니어가 확인할 **artifact 의심**
항목입니다.

### 8.5 성능과 접근성

- thumbnail은 lazy load와 virtualized grid를 사용합니다.
- 원본은 viewer를 열 때만 요청하고 실패한 URL은 개별 재시도합니다.
- 이미지 외에 alt text, chip/MP, 값, verdict reason을 제공하여 색과 이미지에만
  의존하지 않습니다.
- keyboard로 card 이동, viewer 이전/다음, 닫기를 지원합니다.

## 9. 페이지 간 정보 설계

### 9.1 상세 페이지는 서로 다른 grain을 소유

| 페이지 | 기본 grain | 보조 grain |
| --- | --- | --- |
| 측정 개요 | focus MSR + parameter | site |
| 위치 비교 | site × MSR | spatial region |
| Time-Series | 단일: sequence, 다중: MSR/run | tool-time event |
| 상관 / 분포 | 명시적으로 선택한 site/sequence 또는 MSR | group/factor |
| 이미지 갤러리 | image evidence + canonical site | MSR/run |

chart 제목과 export에는 grain을 항상 기록합니다.

### 9.2 URL에 보존할 상태

기존 `view`, `msr`, `msrs`, `mp`를 유지하고 다음 shareable state를 추가합니다.

| Query | 예 | 의미 |
| --- | --- | --- |
| `scope` | `single`, `set` | 선택 수와 별개로 사용자가 의도한 분석 범위입니다. |
| `site` | canonical site key | linked site selection입니다. |
| `ref` | `loo-median`, `msr:…`, `baseline:v3` | 비교 reference입니다. |
| `metric` | `mean`, `fail_ratio`, `edge_center` | Time-Series의 active metric입니다. |
| `x`, `y`, `grain` | feature IDs, `msr` | 상관 query입니다. |

popover 열림, chart zoom, panel 접힘 같은 일시 상태는 URL에 넣지 않습니다.

## 10. 데이터와 계산 계약

### 10.1 Compatibility manifest

다중 페이지를 그리기 전에 다음 manifest가 필요합니다.

```ts
interface AnalysisManifest {
  scope: 'single' | 'set'
  selected: number
  loaded: number
  groups: CompatibilityGroup[]
  focusGroupId: string | null
  excluded: { msr: string, reasonCodes: string[] }[]
  baseline: { id: string, version: string, approved: boolean } | null
  readiness: Record<AnalysisCapability, Readiness>
}
```

compatibility signature는 최소한 recipe identity/revision, parameter/unit,
method/object/kind, mag/vac/pixel, coordinate system, wafer size, site-layout hash를
포함합니다. 현재 계약에 없는 항목은 `unknown`으로 두며 같은 값으로 가정하지 않습니다.

### 10.2 Canonical site key

현재 `chip_number`와 `sequence`만으로 다른 MSR의 같은 site를 확정하면 안 됩니다.
backend가 다음 key를 만들거나 그 근거 필드를 제공해야 합니다.

```text
site_layout_id + chip/die index + mp_number + parameter + coordinate identity
```

같은 site key가 없으면 다중 delta와 same-site gallery를 `제한적`으로 표시하고,
stage coordinate tolerance join을 자동 확정하지 않습니다.

### 10.3 MSR feature row

Time-Series와 다중 상관은 한 MSR당 한 행을 공유합니다.

```text
identity/time/regime
+ level/spread/coverage/failure
+ spatial features
+ fixed FDC and dynamic FDC summaries
+ hardware pre/during/post features
+ provenance/missingness
```

한 MSR 결과를 수천 sensor timestamp에 복제하지 않습니다. hardware raw trace는
event-time window에서 feature로 축약한 뒤 MSR row에 결합합니다.

### 10.4 Reference와 transform provenance

모든 derived value는 다음 메타데이터를 가집니다.

- raw source와 unit입니다.
- transform 이름과 parameter입니다.
- reference MSR 목록 또는 baseline version입니다.
- included/excluded count와 missing count입니다.
- computation version입니다.

export는 화면의 숫자만 내보내지 않고 이 provenance를 함께 포함합니다.

## 11. 통계·판정 무결성

1. null을 0으로 바꾸지 않습니다.
2. 단일 MSR의 site는 독립 wafer 반복이 아닙니다.
3. 다중 비교는 coordinate registration과 compatibility gate를 먼저 통과합니다.
4. reference는 candidate/focus를 제외한 leave-one-out 계산을 기본으로 합니다.
5. 사용자 선택 집합과 승인 baseline을 분리합니다.
6. control limit, engineering limit, USL/LSL을 분리합니다.
7. correlation에는 grain, pair N, missing, strata, window를 표시합니다.
8. tool·lot이 섞인 pooled 결과 옆에 stratified 결과를 제공합니다.
9. vendor score는 모니터링이며 공식 판정 근거가 아닙니다.
10. mock의 CD↔FDC 관계로 방법 성능을 검증하지 않습니다.
11. 평가 불가는 정상으로 치환하지 않습니다.
12. 모든 결과에서 raw site, MSR, image, event로 drill-through할 수 있어야 합니다.

## 12. 반응형 레이아웃

- Desktop `xl`: primary workbench를 viewport 안에 유지하고 panel 내부가 스크롤합니다.
- Tablet: Answer strip → primary chart → breakdown 순으로 1열 또는 2열 재배치합니다.
- Mobile: 전체 분석 기능을 억지로 축소하지 않습니다. summary와 evidence table을 우선하고,
  map comparison과 full viewer는 full-screen sheet로 엽니다.
- chart는 색 외에 symbol, line style, label을 함께 사용합니다.
- red/green만으로 정상·이상을 구분하지 않습니다.

## 13. 단계별 범위

| 단계 | 출하 범위 | 필요한 기반 |
| --- | --- | --- |
| C0 | 공통 context bar, scope, compatibility/readiness, linked state | 현재 route + set fetch 확장 |
| C1 | 위치 비교 raw/reference/delta/variability/coverage | canonical site와 layout gate |
| C2 | 단일 sequence+FDC, 다중 descriptive run chart+event | MSR feature row, event-time metadata |
| C3 | paired correlation, stratified distribution, feature explorer | grain-safe joins, feature registry |
| C4 | review queue, same-site filmstrip, full viewer | image evidence metadata, canonical site |
| C5 | 승인 baseline control chart, variance component | baseline registry, 충분한 역사 반복 |
| Research | signature similarity, PCA/MSPC, virtual metrology | engineer label, offline/time-split 검증 |

## 14. 비범위

- 앱이 자동으로 공정 원인 또는 제품 pass/fail을 확정하는 기능은 아닙니다.
- 현재 mock의 `health`, placeholder `spm_dict`를 판정에 사용하지 않습니다.
- 승인 source가 없는 spec limit, target, control limit을 생성하지 않습니다.
- 등록 정보 없는 image pixel diff와 자동 defect label을 제공하지 않습니다.
- 첫 구현에서 PCA, clustering, virtual metrology를 포함하지 않습니다.
- `측정 개요`를 상세 분석 차트 모음으로 다시 확장하지 않습니다.

## 15. 성공 기준

엔지니어는 다음 작업을 설명 없이 수행할 수 있어야 합니다.

1. 측정 개요에서 이상한 parameter/site를 발견하고 같은 상태로 상세 페이지에
   진입합니다.
2. 위치 비교에서 level shift와 spatial shape change를 구분합니다.
3. Time-Series에서 실제 시간과 단일 실행 sequence를 혼동하지 않습니다.
4. 변화가 특정 tool·lot·maintenance regime에 국한되는지 확인합니다.
5. 상관 결과의 grain, N, missing, strata와 provenance를 확인합니다.
6. Gallery에서 이상·실패 이미지를 먼저 검토하고 같은 site의 역사 이미지를
   나란히 봅니다.
7. 어떤 결과가 탐색 집합이고 어떤 결과가 승인 baseline인지 구분합니다.
8. 모든 요약 숫자에서 raw MSR/site/image/event evidence로 돌아갑니다.

이 흐름이 완성되면 Skewvoir는 `많은 차트가 있는 dashboard`가 아니라,
**측정 개요에서 신호를 발견하고 공간 → 시간 → 관계 → 이미지 근거로 조사 범위를
좁히는 엔지니어링 분석 워크스페이스**가 됩니다.
