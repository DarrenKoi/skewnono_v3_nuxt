# 스큐보아 분석 도구 격차 분석

- 작성일: 2026-08-16
- 대상: Skewvoir `analysis` 워크스페이스의 여섯 분석 화면 (측정 개요, 위치 비교, FDC,
  Time-Series, 상관 / 분포, 이미지 갤러리)
- 기준: [웨이퍼 분석 방법 연구](wafer-analysis-method-research.md)와
  [분석 상세 페이지 CD 벤치마크 연구](analysis-drilldown-benchmark-research.md)가
  정의한 정착 관행 대비 현재 구현의 격차
- 상태: 격차 분석 문서입니다. 구현 계획이나 공식 판정 규칙은 아닙니다.

## 1. 목적과 결론

두 연구 문서는 정착 관행·조건부 분석·연구 기능의 성숙도 구분과 우선순위(P0~P3)까지
정리했습니다. 이 문서는 그 목표 상태와 현재 `front-dev-home` 구현을 화면별로
대조하여 무엇이 채워졌고 무엇이 비어 있는지를 한눈에 보이게 합니다.

핵심 결론은 다음과 같습니다.

- 여섯 화면의 단일 MSR 범위는 연구 문서의 P1 방향을 대체로 충족했습니다. 특히
  위치 비교의 공간 진단, FDC의 sequence 뷰, 갤러리의 review queue는 목표 역할에
  근접합니다.
- 가장 큰 빈틈은 **set 범위**에 있습니다. 위치 비교의 reference/delta/coverage map,
  상관의 across-MSR mode, 갤러리의 same-site 비교가 연구 문서가 요구하는 다중 MSR
  evidence에 못 미칩니다. 두 곳은 코드에 `Task 10 replaces later`, `Task 12
  replaces` 주석이 남아 있어 의도된 미완성입니다.
- 측정 개요는 통계 요약이 mean + 3σ에 머무릅니다. 정착 관행은 CDU를 median, MAD,
  range, valid `N`과 함께 제공하고 실패를 원인별로 분해합니다.
- FDC는 이미 수신하는 `FdcParamSummary`(nominal, drift_sigma, status)만으로 set
  범위의 run×채널 상태 비교가 가능하므로 새 계약 없이 확장할 수 있습니다.
- SPC, capability(Cp/Cpk), tool matching은 연구 문서의 권장대로 baseline·spec
  계약이 확보되기 전까지 열지 않는 것이 올바르며, 그대로 유지합니다.

## 2. 비교 방법과 근거

각 화면을 두 연구 문서의 해당 절(방법 연구 §3~§5, 벤치마크 연구 §5~§8)과
대조했습니다. 구현 확인은 다음 파일 기준입니다.

| 화면 | 구현 파일 | 비고 |
| --- | --- | --- |
| 측정 개요 | `front-dev-home/app/components/ebeam/skewvoir/views/Dashboard.vue` | StatBar, ParamNav, WaferMap 패널 포함 |
| 위치 비교 | `views/PositionStack.vue` | set 범위는 Composite Mean + Site Variability(σ) 두 heat chart |
| FDC | `views/Fdc.vue` | set 범위는 안내 카드만 표시 |
| Time-Series | `views/TimeSeries.vue` | 추이/분포/장비 skew 3렌즈 |
| 상관 / 분포 | `views/Correlation.vue` | set 범위에 `Task 10 replaces later` 주석 |
| 이미지 갤러리 | `views/Gallery.vue` | set 범위에 `Task 12 replaces` 주석 |

정합성·준비성 계약(`compatibility.ts`, ReadinessModal)은 이미 P0 요구를 충족하므로
이 문서의 격차 항목에서 제외합니다.

## 3. 화면별 격차

### 3.1 측정 개요 — 통계 요약과 실패 분해가 얕습니다

현재 구현은 성공률(measured/failed), 이상 사이트 수, 활성 파라미터의 mean + 3σ,
align 방법과 이미지를 StatBar에 표시합니다. 분포 차트와 포인트 테이블이 함께
있습니다.

격차는 다음과 같습니다.

- **CDU 지표 카드 부재**: 벤치마크 연구 §5.2C는 wafer level(mean, median, target
  offset), spread(σ, 3σ, MAD, range, valid `N`), shape(center-edge delta)의 세
  줄을 요구합니다. 현재 `MsrParamSummary`의 mean/std/min/max를 재배치하는 것만으로
  대부분 충족되며 새 계약이 필요 없습니다.
- **실패 원인 분해 부재**: 방법 연구 §4.1은 `msr_check`, `align_fail`, image 실패,
  nullable `cd_value`를 분리해 보여주기를 요구합니다. 현재 성공률 하나로
  통합되어 있어 실패의 공간 군집 여부도 확인할 수 없습니다.
- 다중 MSR 선택 시의 비교 집합 funnel(`N개 선택 → M개 로드 → K개 호환 → G개
  그룹`)은 ReadinessModal이 부분 충족합니다. 파라미터별 변화 범위 요약이 아직
  없습니다.

### 3.2 위치 비교 — 단일은 충족, set의 절반이 비어 있습니다

단일 범위(SpatialWorkbench)는 level/shape/coverage 증거 칩, 공간 레이어 맵,
반경·섹터 프로파일, site 상세 테이블까지 갖추어 벤치마크 연구 §5의 공간 진단
역할에 근접합니다.

set 범위는 Composite Mean과 Site Variability(σ) heat chart만 있습니다. 벤치마크
연구 §5.2B와 방법 연구 §5.2가 요구하는 나머지 세 map이 없습니다.

| 요구 map | 목적 | 구현 상태 |
| --- | --- | --- |
| Composite Mean map | 공통 칩 위치 평균 | 있음 |
| Site Variability map | site별 wafer 간 σ | 있음 |
| Reference median map | site별 호환 MSR 중앙값 기준면 | 없음 |
| Signed delta map | focus − reference의 방향·위치 | 없음 |
| Coverage map | site별 유효 MSR 수, 불균형 누락 | 없음 |

이 세 map은 로드된 set 파일만으로 계산 가능하므로 신규 API 계약 없이 우선
구현할 수 있는 격차입니다.

### 3.3 FDC — 단일 충족, set이 비어 있습니다

단일 범위는 파라미터 매트릭스, 개별 그래프, sequence 이벤트 레인, 무결성 배지를
갖추고 `per sequence` 단위를 정직하게 표시합니다.

격차는 다음과 같습니다.

- **set 범위 전무**: 현재 안내 카드만 표시합니다. 그러나 `MsrFileResponse`가 이미
  채널별 `FdcParamSummary`(category, nominal, drift_sigma, status)를 전달하므로,
  set의 run×채널 상태 heat chart와 채널별 추이 비교는 수신 중인 데이터만으로
  가능합니다. 방법 연구 §5.3의 per-MSR feature 관점에서도 이것이 첫 조각입니다.
- 방법 연구 §4.3의 dynamic FDC별 요약 수치(시작값, 끝값, range, slope, missing
  fraction)는 그래프로는 보이지만 표 형태의 요약이 없습니다.

### 3.4 Time-Series — 탐색 충족, SPC·event는 계약 대기입니다

축 모드(시간/순서/장비), baseline(측정값/잔차), 이상 판정 방식과 편집 가능한
임계값, 장비 skew, 무결성 배지까지 갖추어 탐색 도구로는 완성도가 높습니다.

격차는 다음과 같습니다.

- **다중 lane 부재**: 벤치마크 연구 §6.2는 CD level, CD uniformity, measurement
  quality, tool context의 네 lane이 시간 cursor를 공유하기를 요구합니다. 현재는
  활성 파라미터 한 줄과 장비 skew 렌즈뿐입니다.
- **BM/PM event band 부재**: 방법 연구 §2.1이 근거로 든 BM/PM 테이블이 아직
  결합되지 않았습니다. 이것은 프런트 변경 전에 backend event 계약이 먼저입니다.
- I-MR, EWMA, CUSUM과 control limit은 승인·동결된 기준선 계약이 없으므로 열지
  않는 것이 올바릅니다(벤치마크 연구 §6.3). 다만 현재 사용자 편집 임계값이
  통계적 관리 한계와 같은 방식으로 표시되지 않는지 시각적 구분을 확인할 필요가
  있습니다.

### 3.5 상관 / 분포 — 단일 충족, set이 자리표시자입니다

단일 범위는 exact pair 산점도, 한계 분포(Hist/ECDF/Box/Violin), 반경·섹터
그룹화, site 증거 서랍까지 갖추었습니다.

격차는 다음과 같습니다.

- **set 범위 자리표시자**: `Task 10 replaces later` 주석이 남아 있고 단순 X/Y
  산점도만 있습니다. 벤치마크 연구 §7.1의 네 mode 중 MSR/run 단위의 Across-MSR
  Outcome(파라미터 요약 ↔ FDC·hardware feature, tool별 층화 상관을 pooled 상관과
  나란히)이 가장 중요한 빈틈입니다. 로드된 set 파일의 파라미터 요약과
  `FdcParamSummary`로 시작할 수 있고, hardware event-time join은 방법 연구 §5.4의
  계약을 기다립니다.
- Cp/Cpk capability는 spec·안정 stream 계약이 확인될 때까지 게이트를 유지합니다.
- LOWESS 같은 탐색 곡선은 부가 기능으로 우선순위가 낮습니다.

### 3.6 이미지 갤러리 — triage 충족, 비교 워크플로가 없습니다

단일 범위는 증거 기반 review queue, 우선정렬 토글, 전체 뷰어까지 의도된 역할에
맞습니다.

격차는 다음과 같습니다.

- **same-site over time 부재**: 벤치마크 연구 §8.3의 첫 번째 비교 mode입니다.
  호환 그룹의 같은 canonical site를 MSR별 image strip으로 나란히 보는 기능이
  set 범위(현재 파일명 grid, `Task 12 replaces`)에도 단일 범위에도 없습니다.
- measurement overlay, line profile, LER/LWR은 `spm_dict` 자리표시자와 edge
  trace 계약 상태 그대로 게이트를 유지합니다(벤치마크 연구 §8.4, §8.5).
- Before/After event 비교는 BM/PM event 결합 후 가능하므로 Time-Series 격차와
  같은 계약을 기다립니다.

## 4. 새 카테고리 제안

기존 여섯 화면에 넣기 어렵고 정착 관행으로 가치가 높은 두 가지와 연구 문서가
이미 지정한 연구 기능을 제안합니다.

| 카테고리 | 내용 | 성숙도 | 전제 |
| --- | --- | --- | --- |
| SPC / 모니터링 | 승인 기준선 stream의 run chart, 고정 관리 한계, BM/PM event band, CD level·WCDU·품질 lane | 조건부 분석 | baseline 버전·spec 등록 계약, event 결합 |
| Evidence pack 내보내기 | 한 MSR 판정 근거(요약 통계, wafer map, 이상 site, 해당 SEM image, 제외 사유)의 Excel/PDF 묶음 | 정착 관행 | 기존 내보내기 유틸(`xlsx.ts`, `csvDownload.ts`)로 충분 |
| 원인 후보 축소 연구 | variance component, spatial signature 유사 검색 | 연구 기능 | 방법 연구 §6의 검토 라벨·설계 요건 |

Evidence pack은 새 데이터 계약 없이 가능하면서 업계 표준 소프트웨어가 기본으로
제공하는 기능이므로 저비용·고가치입니다.

## 5. 권장 우선순위

신규 API 계약 없이 가능한 것부터 정렬했습니다. 계약이 필요한 항목은 벤치마크
연구 §10의 준비도 표가 그대로 적용됩니다.

| 순위 | 항목 | 화면 | 전제 |
| --- | --- | --- | --- |
| 1 | set 범위 reference median / signed delta / coverage map | 위치 비교 | 로드된 set 파일로 충분 |
| 2 | Across-MSR Outcome mode(Task 10) | 상관 / 분포 | set 파일 파라미터 요약 + FdcParamSummary로 시작 |
| 3 | CDU 지표 카드와 실패 원인 분해 | 측정 개요 | MsrParamSummary 재배치 |
| 4 | same-site over time image strip | 이미지 갤러리 | 호환 그룹 site key |
| 5 | set 범위 run×채널 FDC 상태 비교 | FDC | 수신 중인 FdcParamSummary |
| 6 | Evidence pack 내보내기 | 신규 | 기존 내보내기 유틸 |
| 7 | BM/PM event band, 다중 lane | Time-Series, SPC | backend event 계약 |
| 8 | I-MR/EWMA, Cp/Cpk, tool matching | SPC | baseline·spec·reference artifact 계약 |

1~6까지는 현재 데이터 계약으로 구현할 수 있고, 7~8은 연구 문서의 P2~P3와
같은 조건에서 진행합니다.

## 6. 유지 항목

다음은 격차가 아니라 연구 문서의 권장을 따르고 있으므로 그대로 유지합니다.

- 사용자 선택 집합에서 관리 한계를 다시 계산하지 않는 것(Time-Series).
- `spm_dict`, mock `health`, vendor score를 판정 경로에서 제외하는 것.
- capability와 tool matching을 게이트로 닫아둔 것.
- correlation의 `연관이며 원인 증명이 아님` 고정 표시와 exact pair 원칙.
- 사용되지 않는 `FdcAnalysis.vue` 계열 레거시 컴포넌트는 향후 정리 대상입니다.
