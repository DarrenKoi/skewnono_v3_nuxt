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
정리했습니다. 이 문서는 그 목표 상태와 현재 `frontend` 구현을 화면별로
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
| 측정 개요 | `frontend/app/components/ebeam/skewvoir/views/Dashboard.vue` | StatBar, ParamNav, WaferMap 패널 포함 |
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

아래 순서는 2026-08-16 코드 대조(§6) 이후의 것입니다. 판단 기준은 "데이터가
응답에 있는가"가 아니라 **"그 데이터를 다루는 파생 계층까지 있는가"**입니다.
`utils/skewvoirAnalysis/` 에 이미 검증된 파생이 있는 항목은 UI 배선만 남으므로
훨씬 쌉니다.

| 순위 | 항목 | 화면 | 전제 | 상태 |
| --- | --- | --- | --- | --- |
| 1 | set 범위 run×채널 FDC 상태 비교 | FDC | 수신 중인 `FdcParamSummary`, 파생 없음 | 착수 |
| 2 | Across-MSR Outcome mode(Task 10) | 상관 / 분포 | `features.ts` 파생이 이미 완성·미사용 | 착수 |
| 3 | CDU 지표 카드와 실패 원인 분해 | 측정 개요 | `rows` 에서 median/MAD 계산 | 착수 |
| 4 | set 범위 reference median / signed delta / coverage map | 위치 비교 | 파생 추출 + heat 대칭 스케일 선행 | 보류 |
| 5 | Evidence pack 내보내기(Excel 한정) | 신규 | `utils/xlsx.ts` | 보류 |
| 6 | same-site over time image strip | 이미지 갤러리 | 호환 그룹 site key + 이미지 warm 비용 | 보류 |
| 7 | BM/PM event band, 다중 lane | Time-Series, SPC | backend event 계약 | 계약 대기 |
| 8 | I-MR/EWMA, Cp/Cpk, tool matching | SPC | baseline·spec·reference artifact 계약 | 계약 대기 |

1~6까지는 현재 데이터 계약으로 구현할 수 있고, 7~8은 연구 문서의 P2~P3와
같은 조건에서 진행합니다.

## 6. 코드 대조로 확인한 사실 (2026-08-16)

§3~§5의 "신규 계약 불필요" 판정을 구현 코드에 대조했습니다. 대체로 유지되었고
세 가지가 달라졌습니다.

확인한 전제는 다음과 같습니다.

| 확인 사항 | 결과 |
| --- | --- |
| set 전체가 full payload로 로드되는가 | 예. `POST /api/msr-files` 가 MSR마다 전체 `MsrFileResponse` 를 반환하고(`total=len(rows)`, 페이지네이션 없음) `useSkewvoirAnalysis` 의 `setFiles: Map<msr, MsrFileResponse>` 에 담깁니다 |
| `MsrParamSummary` 에 median/MAD가 있는가 | 아니요. `count, mean, std, min, max, unit` 뿐입니다 |
| 실패 원인 필드는 어디 있는가 | `MeasHistRow` 의 `msr_check`, `align_fail`, `fail_images`, `fail_ratio` — 이미 로드되어 있습니다 |
| per-MSR feature 테이블이 있는가 | 있고, 아무도 쓰지 않습니다 (`utils/skewvoirAnalysis/features.ts`) |

### 6.1 정정 — Across-MSR은 계산이 아니라 UI 배선입니다

§3.5는 "set 파일 파라미터 요약 + `FdcParamSummary` 로 시작"이라 했지만, 그 파생은
이미 끝나 있습니다. `features.ts` 가 로드된 MSR마다 `level / spread / coverage /
failure / spatial / fixed_fdc.* / dynamic_fdc.*` 을 `DerivedValue`(값 + n +
missing + transform + 출처 + version)로 만들고, `dynamic_fdc` 의 sequence grain은
MSR grain으로 안전하게 축약되어 있습니다. `useSkewvoirAnalysis` 가 `featureRows` /
`featureRegistry` 로 노출하지만 **렌더링하는 컴포넌트가 하나도 없습니다.**

다만 `FdcParamSummary` 의 `drift_sigma` / `status` 는 registry에 없으므로, 축으로
쓰려면 feature family로 정식 추가해야 합니다. 컴포넌트에서 `fdc_params` 를 직접
읽으면 provenance가 끊깁니다.

### 6.2 정정 — CDU 카드는 재배치가 아니라 신규 계산입니다

§3.1의 "`MsrParamSummary` 재배치만으로 대부분 충족"은 성립하지 않습니다. median과
MAD가 그 응답에 없습니다. 대신 `rows` 가 잘리지 않고 전부 오므로 `cd_value` 에서
클라이언트 계산이 가능합니다 — API 변경은 여전히 불필요하지만 `utils/stats.ts`
확장이 필요합니다. 반대로 shape(center-edge delta)는 `features.ts` 의 `spatial`
feature와 `spatial.ts` 에 이미 있어 공짜입니다.

실패 분해는 §3.1이 출처를 짚지 않았는데, **백엔드에 요청할 것이 없습니다.**
MSR 단위 사유는 `MeasHistRow` 에, 사이트 단위 결측은 `cd_value === null` 과
`measurement_score` 에 이미 있습니다. `fail_ratio` 는 이미 퍼센트이고
(4.57 = 4.57%), `align_fail === 'NA'` 는 실패가 아니라 미상입니다.

### 6.3 정정 — Evidence pack의 PDF는 근거가 없습니다

§4는 "기존 내보내기 유틸(`xlsx.ts`, `csvDownload.ts`)로 충분"이라 했지만 이는
Excel에만 해당합니다. `utils/xlsx.ts` 는 exceljs 동적 import 기반이고 이미지
삽입 경로까지 주석으로 안내하지만, **PDF 라이브러리는 저장소에 없습니다.**
범위를 Excel로 좁히거나 인쇄 스타일시트로 대체해야 합니다.

## 7. 보류 항목의 착수 조건

우선순위 1~3은 착수했습니다. 나머지는 아래 조건이 정리되면 그대로 집을 수 있습니다.

### 7.1 위치 비교 세 map (우선순위 4)

데이터는 충분합니다. 사이트별 누적 루프가 `PositionStack.vue` 안에 지역 computed로
이미 있습니다. 착수 전에 세 가지가 필요합니다.

- **`WaferHeatChart` 의 대칭 스케일 옵션.** 현재 visualMap은 데이터의 min/max로
  범위를 잡으므로, signed delta를 그대로 넘기면 0이 색의 중앙이 아니게 되어
  **부호 방향을 거짓말합니다.**
- **파생 추출.** 누적 로직을 `utils/skewvoirAnalysis/` 로 옮기고 `*.test.ts` 짝을
  붙입니다. 판정 근거가 되는 map을 테스트 없는 컴포넌트 안에 두는 것은 이 폴더의
  관행에서 벗어납니다.
- **정책 결정(미결):** reference median의 모집단에 focus MSR을 포함할지 제외할지.
  포함하면 focus가 자기 기준선을 오염시킵니다 — Time-Series baseline에서 이미 한 번
  고친 함정과 같은 종류입니다.

### 7.2 Evidence pack (우선순위 5)

범위를 **Excel 한정**으로 확정하고 시작합니다(§6.3). 이미지 삽입이 필요하므로
`downloadWorkbook()` 한 줄 경로가 아니라 `createWorkbook()` + 자체 루프 +
`writeWorkbook()` 을 씁니다. 행 조립 로직은 `xlsx.ts` 가 아니라 순수 빌더 모듈에
두어야 `node --test` 로 검증됩니다.

### 7.3 same-site over time image strip (우선순위 6)

계산은 쉽습니다 — canonical site key는 `compatibility.ts` 에, 각 MSR의 `eqp_ip` 와
`class_name` 은 `setFiles` 에 있습니다. **비싼 것은 이미지 경로입니다.**
`useMsrImageWarmer` 는 (MSR, 활성 파라미터) 단위로 warm하고 사무실에서는 FTP를 타며
425/429/503 백오프 체인을 갖습니다. set 전체를 warm하면 tool 부하 stampede입니다.
따라서 strip은 개수를 제한하고(예: 6~8개) 사용자가 명시적으로 요청할 때만 지연
로드해야 합니다.

### 7.4 계약 대기 (우선순위 7~8)

판정 그대로 유지합니다. BM/PM event band와 다중 lane은 backend event 계약이,
I-MR/EWMA·Cp/Cpk·tool matching은 승인·동결된 baseline과 spec 계약이 먼저입니다.

## 8. 유지 항목

다음은 격차가 아니라 연구 문서의 권장을 따르고 있으므로 그대로 유지합니다.

- 사용자 선택 집합에서 관리 한계를 다시 계산하지 않는 것(Time-Series).
- `spm_dict`, mock `health`, vendor score를 판정 경로에서 제외하는 것.
- capability와 tool matching을 게이트로 닫아둔 것.
- correlation의 `연관이며 원인 증명이 아님` 고정 표시와 exact pair 원칙.
- 사용되지 않는 `FdcAnalysis.vue` 계열 레거시 컴포넌트는 향후 정리 대상입니다.

## 9. 측정 품질·실행 신호를 표시 전용 축으로 추가 (2026-10-09)

API 응답에 이미 들어 있었지만 화면이 버리던 신호를 CD 옆에서 볼 수 있게 했습니다.
CD가 움직였을 때 측정 자체가 나빠진 것인지 웨이퍼가 바뀐 것인지를 엔지니어가 직접
보도록 돕는 것이 목적이며, 화면이 대신 판정하지 않습니다.

### 9.1 표시 전용 규칙

- 이 축들은 판정 경로에 들어가지 않습니다. `utils/anomaly/*`, `verdict.ts`,
  `overview.ts`, `timeSeries.ts`, `baselineCompare.ts` 는 이 필드를 읽지 않으며,
  임계값과 주의·이상 색도 없습니다. `features.test.ts` 의
  `quality axes are display-only` 테스트가 이를 고정합니다.
- 위치 레이어의 score는 `analyzeSpatial` 결과에 들어가지 않고
  `spatialScorePoints` 가 따로 만듭니다. 따라서 근거 칩과 readiness는 score를 볼
  수 없습니다.
- 집의 mock은 score와 CD를 같은 `health` 값에서 만듭니다. 그래서 상관 화면에서
  이 축을 고르면 `데모 데이터` 안내가 함께 나옵니다.

### 9.2 추가한 축 (set scope · 상관 · 검토 영수증 `MSR별 지표`)

축 선택 목록에서 `측정 품질·실행 신호 (표시 전용)` 묶음 아래에 나옵니다.

| 축 | 정의 | 값이 없는 경우 | 표시 단위 |
| --- | --- | --- | --- |
| `measurement_score 중앙값` | 활성 파라미터의 row 중 score가 있는 row의 중앙값입니다. 측정 실패 row도 포함합니다. | score가 있는 row가 없으면 값을 내지 않습니다. | 없음 |
| `addressing1_score 중앙값` | 위와 같습니다. | 위와 같습니다. | 없음 |
| `addressing2_score 중앙값` | 위와 같습니다. | 위와 같습니다. | 없음 |
| `alignment offset N 크기` | alignment 지점 N의 offset 두 성분으로 구한 크기입니다. 지점마다 축이 하나입니다. | 두 성분 중 하나라도 숫자가 아니면 값을 내지 않습니다. | 없음 |
| `측정점당 소요 시간` | meas_hist `meastime` 을 MSR의 서로 다른 sequence 수로 나눈 값입니다. | `meastime` 이 0이거나 없을 때, sequence가 없을 때 값을 내지 않습니다. | s |

### 9.3 위치 레이어 (single scope)

Spatial Layer Map에 `Score` 레이어를 추가했습니다. 각 site를 `measurement_score`
원본 값으로 칠하며, 색은 `SK_SCALE` 의 차가운 절반인 순차 램프 `SK_SEQ` 입니다.
범위는 데이터의 최솟값과 최댓값이고, 측정 실패 site는 score가 있으면 색을 칠한 위에
✕ 표시를 그대로 둡니다.

### 9.4 만들지 않은 것

Time-Series lane은 만들지 않았습니다. 추이 차트는 판정이 붙은 `TrendPoint` 한
계열만 받으며, 판정 집계를 거치지 않는 보조 계열이나 lane을 받는 구조가 없습니다.

### 9.5 OFFICE-VERIFY

- score의 척도와 방향입니다. 스키마 문서에는 예시 값만 있어서 화면은 원본 필드
  이름만 쓰고 단위와 좋고 나쁨을 표시하지 않습니다.
- alignment offset의 단위와, 배열의 둘째·셋째 요소가 x·y인지 여부입니다.
- failed row에 score가 실제로 남는지 여부입니다. mock은 failed row의
  `measurement_score` 를 비워 둡니다.

## 10. 잔여 결함 정리 (2026-10-09)

### 10.1 한 화면의 σ 는 한 가지 정의입니다

확인한 사실은 다음과 같습니다.

- msr_file 응답의 파라미터 요약 `std` 는 표본 표준편차(n−1)이고 소수 셋째
  자리로 반올림한 값입니다. `cd_value` 가 숫자인 모든 row(모든 sequence)를
  쓰며 `mp_number` 는 보지 않습니다. mock 과 사내 어댑터가 같은
  `mock._summaries` 를 씁니다.
- 화면의 판정과 측정 개요 블록은 `cduMetrics` 를 씁니다. 표본 표준편차(n−1)를
  반올림 없이 계산하고, `isMeasuredRow`(`mp_number >= 0` 이고 `cd_value` 가
  숫자)를 통과한 row 만 씁니다.
- 따라서 두 값은 정의는 같지만 반올림과 row 조건이 다릅니다. Distribution
  패널은 반올림된 `std` 에 3 을 곱해 3σ 를 적었으므로 측정 개요의 3σ 와 끝
  자리가 어긋날 수 있었습니다.

바꾼 내용은 다음과 같습니다.

| 위치 | 이전 | 지금 |
| --- | --- | --- |
| Distribution 패널 머리말 μ · 3σ | 서버 요약 `mean`, `std × 3` | `cduMetrics` (`distributionHeadline`) |
| 파라미터 요약 표 Std 열 | 서버 요약 `std` | `cduMetrics` 의 `spread.std`, site 가 2개 미만이면 `—` |
| 파라미터 요약 표 Count · Mean · Min · Max | 서버 요약 | 그대로 서버 요약 |
| Time-Series 추이 툴팁 std | 서버 요약 `std` | 값은 그대로이며 이름을 `std (서버 요약)` 으로 적습니다 |

Time-Series 추이의 점은 mean · min · max · std 를 모두 서버 요약에서 읽고, 산포
판정도 그 `std` 로 냅니다. 판정 입력을 바꾸지 않으려고 값은 두고 이름만
구분했습니다.

### 10.2 세트 위치 맵의 site 는 (chip, 측정점)입니다

위치 비교의 세트 화면에 있는 `Composite Mean` 과 `Site Variability (σ)` 맵은 chip
인덱스만으로 row 를 모아 평균과 표준편차를 냈고, 세트의 측정이 같은 배치인지
확인하지 않았습니다. `기준 대비 Δ` 맵에서 고친 두 문제가 그대로 남아 있었습니다.
계산을 `baselineCompare.ts` 의 `compositeSiteMap` 으로 옮기고 규칙을 다음과 같이
정했습니다.

- site 는 (chip, `mp_number`)입니다. wafer 한 장은 site 하나에 값 하나를 냅니다.
  같은 site 를 두 번 측정했으면 그 평균을 씁니다.
- site 의 평균은 wafer 값들의 평균이고, site 의 σ 는 wafer 값들의 표본
  표준편차입니다. 같은 측정점의 wafer 간 산포를 뜻합니다.
- chip 에 그리는 값은 그 chip 의 site 통계를 측정점마다 같은 비중으로 평균한
  값입니다. row 를 한꺼번에 모으면 측정점마다 wafer 수가 다를 때 chip 평균이
  움직이고, 한 chip 안의 측정점 간 차이가 wafer 간 산포로 섞여 들어갑니다.
- wafer 한 장만 측정한 site 에는 σ 가 없습니다. chip σ 에서 빼며, 그런 site 뿐인
  chip 은 σ 맵에 그리지 않습니다. 0 으로 적지 않습니다.
- `analysis.siteDeltaReady` 가 거짓이면 두 맵 모두 그리지 않고, Δ 패널과 같은
  문구로 같은 위치임을 확인할 수 없다고 적습니다. 측정이 한 건뿐인 세트도 여기에
  해당합니다.
- 합치는 대상은 `manifest.included` 가운데 파일을 불러온 측정입니다. 이전에는
  제외된 측정의 row 도 함께 들어갔습니다.

예를 들어 chip (0,0) 의 측정점 1 을 세 wafer 가 10, 14, 12 로, 측정점 2 를 두
wafer 가 20, 24 로 측정했다면 측정점 1 은 평균 12 · σ 2, 측정점 2 는 평균 22 ·
σ 2.828 이고 chip 값은 평균 17 · σ 2.414 입니다. row 를 모으는 이전 방식은 평균
16 · σ 5.83 을 냈습니다.
