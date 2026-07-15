# 스큐보아 Phase B — 측정 개요 (Measurement Overview) Design

- Date: 2026-07-15
- Status: **결정 완료 — 안 A + 상단 파라미터 내비게이터 + 연결 선택 + 세트 적응 뷰. 구현 대기.**
- Scope: `front-dev-home/app/components/ebeam/skewvoir/` (Dashboard → Measurement Overview)
- 선행 작업: Phase 0 + Phase A (`docs/superpowers/plans/2026-07-14-skewvoir-phase-a-analytical-truth.md`, 커밋 `4cf582a..9bd4ad6`)
- 방법론 참고: `docs/issues/skewvoir/wafer-analysis-method-research.md` (단일/다중 분석 모드, 통계 원칙, 데이터 계약 연구) — §8.1·§9.5·§10.3·§11·§12에 반영

## 1. 배경

Phase A에서 스큐보아의 **숫자**를 정직하게 만들었습니다.

- `cd_value`가 nullable이 되었습니다. `mp_number < 0`인 점은 측정이 없으므로 값도 없습니다.
- 모든 소비자가 `isMeasuredRow` 게이트를 통과합니다. 평균·σ·3Σ·이상 판정이 더 이상 가짜 값에 오염되지 않습니다.
- 통계가 `utils/stats.ts` 한 곳으로 모였습니다.

그러나 **부작용**이 하나 남았습니다. 게이트가 실패한 점을 조용히 버리기 때문에, 화면은 `43 sites`라고만 말합니다. 장비가 실제로 시도한 것은 45점이고 2점이 실패했다는 사실이 사라졌습니다. 통계는 정직해졌지만 **실패는 보이지 않게 되었습니다.**

Phase B는 이 관점을 뒤집습니다. 실패는 노이즈가 아니라 **증거**입니다.

## 2. 이 설계가 답하는 질문

> MSR은 측정의 산출물입니다. 산출물을 보고 좋은지 나쁜지 판단합니다.

판단하는 주체는 **사람**입니다. 앱의 역할은 판정을 내리는 것이 아니라, **판단 가능한 형태로 산출물을 제시하는 것**입니다.

## 3. 확정 사항

### 3.1 측정 실패의 정의 — `cd_value`가 null인 경우만

실패는 **점 데이터가 아예 없는 경우**(`mp_number < 0` → `cd_value: null`)로 한정합니다. 이는 `isMeasuredRow`의 부정과 정확히 같습니다. 규칙이 하나이고, 이미 구현·검증되어 있습니다.

다음은 실패로 **보지 않습니다**.

| 후보 | 판정 | 이유 |
| --- | --- | --- |
| 점 데이터 없음 (`cd_value: null`) | **실패** | 장비가 측정을 못 했습니다. |
| 측정됐으나 score 없음 | 실패 아님 | score는 장비사 로직입니다. |
| score가 낮음 | 실패 아님 | 임계값이 자의적입니다. |
| SEM 이미지 없음 | 실패 아님 | CD 값이 있으면 측정은 된 것입니다. |

### 3.2 `*_score`는 모니터링 대상이지 판정 근거가 아닙니다

`measurement_score` / `addressing1_score` / `addressing2_score`는 **장비사(vendor)의 자체 로직**으로 산출됩니다. 따라서 **측정 간 비교가 불가능합니다.** 화면에 표시하되(모니터링), 어떤 판정·정렬·임계값의 근거로도 사용하지 않습니다.

### 3.3 비교 가능성은 오직 동일 RECIPE 안에서만 성립합니다

같은 recipe는 **같은 제품을 같은 위치에서** 측정하므로 비교할 수 있습니다. 그래서 peer 그룹은 동일 recipe로 자동 구성합니다.

- **자동**: 열자마자 의미 있는 기준선이 있어야 합니다.
- **재정의 가능**: 기존 `비교 세트` 선택기(`TimeSeries.vue`)를 유지해 엔지니어가 세트를 편집할 수 있게 합니다.

### 3.4 `HEALTH · LAST 31H` 블록은 삭제합니다

`useSkewvoirWorkspace.ts:59`의 `useState(..., () => ({ scans: 24, outliers: 15 }))`는 **하드코딩된 가짜 값**이며 지금 사용자에게 그대로 노출되고 있습니다. LeftRail의 역할은 내비게이션과 현재 선택 표시입니다. 측정의 실제 사실(커버리지·이상 사이트)은 본문 뷰에서 보여줍니다.

## 4. 범위 분할

Phase B 백로그는 하나의 spec으로 묶기에 너무 큽니다. 서로 다른 질문에 답하기 때문입니다. 각각 독립된 spec → plan → 구현 사이클을 갖습니다.

| | 하위 과제 | 답하는 질문 | 사용하는 자산 |
| --- | --- | --- | --- |
| **B1** | 측정 개요 | 이 측정은 쓸 만한가? | 실패 가시화, `siteVerdicts`, `exe_detail_info`, `alignment` |
| **B2** | Peer 비교 | 이 웨이퍼가 recipe 동료 대비 이상한가? | 동일 recipe 자동 기준선, delta map |
| **B3** | 장비 증거 — FDC (측정 동반) | 장비가 원인인가? | 고아 `Fdc*` 4개 컴포넌트, `dynamic_fdc`(sequence) / `fixed_fdc`, CD↔FDC 상관 (exact join, 인라인) |
| **B3.2** | 장비 증거 — 하드웨어 (timestamp) | 장비가 원인인가? | `useHardwareApi`(eqp_id + start~end), BSM/Reso/MDC/SCE/BM·PM, 앵커 팝업 (event-time join) |
| **B4** | 갤러리 정리 | 어떤 이미지부터 볼 것인가? | 정렬·필터·비교, `siteVerdicts` |

**B1을 먼저 진행합니다.** 실패한 측정은 애초에 비교할 가치가 없으므로, 분류 깔때기의 입구입니다.

## 5. B1 — 측정 개요 상세

### 5.1 반드시 담기는 것

1. **커버리지(실패)를 1급 정보로.** 모든 개수 표기가 정직해집니다. `43 sites` → `43 / 45 측정 · 2 실패`.
2. **실패 점의 위치.** 실패 행도 `chip_number` / `sequence`를 그대로 갖고 있으므로 웨이퍼 맵에 `✕`로 찍을 수 있습니다. **실패가 한 구역에 뭉쳐 있다면 그 자체가 소견입니다.**
3. **사이트 이상 판정.** Phase A에서 만들었지만 아직 아무 뷰도 쓰지 않는 `utils/anomaly/site.ts::siteVerdicts`를 여기서 처음 소비합니다. leave-one-out 기준이며, 앱 전체에서 "이상"의 정의는 하나뿐입니다.
4. **측정 조건 + 정렬 증거.** Phase 0이 열어준 `exe_detail_info`(wafer/process/mag/vacc/pixel)와 `alignment`(3점, OM/SEM, offset, score)를 표시합니다. 현재 `Acquisition.vue`는 `meas_hist` 행을 쓰고 있어 이 데이터를 아직 보지 않습니다.
5. **동일 recipe 대비 편차 — B2로 이관합니다.** 자동 peer 세트 delta는 B2(Peer 비교)의 핵심 자산을 필요로 하고, §8의 미결 질문이 모두 peer 세트 정책입니다. B1은 peer 카드 없이 4-카드 판정 스트립으로 출하하고, B2에서 5번째 카드를 추가합니다.

### 5.2 담지 않는 것

- `spm_dict` — **신호가 없는 자리표시자입니다.** 사무실 백엔드가 실제 파형을 주기 전에는 어떤 패널도 만들지 않습니다.
- `MsrFileResponse.health` — mock 생성기의 내부 편향 스칼라이며 사무실 백엔드에는 존재하지 않습니다.
- score 기반 임계값·정렬·판정 (§3.2).

## 6. 레이아웃 — **안 A 확정**

세 안 모두 §5의 정보를 담았습니다. 차이는 **무엇을 먼저 읽게 하는가**였습니다. 아래 세 안 중 **안 A (Answer-first)**를 채택했습니다(§6.4).

### 안 A — Answer-first (`docs/design/2026-07-15-skewvoir-phase-b/option-a-answer-first.png`)

![Option A](../../design/2026-07-15-skewvoir-phase-b/option-a-answer-first.png)

상단에 판정 스트립(커버리지 · 이상 사이트 · 평균 · peer 대비 · 정렬)이 사실을 먼저 선언하고, 아래 패널들이 그 근거가 됩니다. 현재 Dashboard 구조와 가장 가깝습니다.

### 안 B — Triage funnel (`docs/design/2026-07-15-skewvoir-phase-b/option-b-triage-funnel.png`)

![Option B](../../design/2026-07-15-skewvoir-phase-b/option-b-triage-funnel.png)

판단 순서 그대로 3개 밴드를 쌓습니다. ① 측정이 되었는가 → ② 웨이퍼는 정상인가 → ③ 다른 측정과 비교하면. 화면이 곧 사고 절차입니다. 다만 세로로 길어 스크롤이 필요합니다.

### 안 C — Wafer as the hero (`docs/design/2026-07-15-skewvoir-phase-b/option-c-wafer-hero.png`)

![Option C](../../design/2026-07-15-skewvoir-phase-b/option-c-wafer-hero.png)

웨이퍼 맵 하나를 중앙에 크게 두고 레이어(CD 값 / 실패 / 이상 / Radius / Score / 이미지)를 토글합니다. 점을 클릭하면 우측에 해당 SEM 이미지와 판정이 나옵니다. 좌우는 얇은 여백 정보입니다.

### 트레이드오프

| | 강점 | 약점 |
| --- | --- | --- |
| A | 한눈에 결론. 기존 구조와 연속적입니다. | 스트립이 "판정"처럼 읽혀 사람의 판단을 앞지를 수 있습니다. |
| B | 판단 순서를 화면이 강제합니다. 신규 사용자에게 친절합니다. | 세로로 깁니다. 숙련자에게는 느립니다. |
| C | 웨이퍼가 주인공. 점↔이미지 탐색이 즉각적입니다. | 분포·추세가 주변부로 밀립니다. |

> **결정: 안 A (Answer-first).** 판정 스트립이 사실을 먼저 선언하고 아래 패널이 근거가 됩니다. 기존 Dashboard 구조와 연속적이며 `activeParam` / `setParam` 배선을 그대로 재사용합니다.

### 6.4 다중 파라미터 — 파라미터 내비게이터

하나의 MSR은 파라미터가 **하나가 아닙니다.** class가 3~4개 파라미터로 매핑됩니다(예: `GATE` → `GATE_CD` · `GATE_HEIGHT` · `GATE_PROFILE`, `CD` → `CD_TOP` · `CD_BOTTOM` · `CD_MIDDLE` · `SIDEWALL_ANGLE`). 각 파라미터는 **단위와 범위가 다르므로**(nm · deg · 무차원) 하나의 웨이퍼 맵·분포에 함께 얹을 수 없습니다.

따라서 측정 개요는 **파라미터별 요약을 1급 정보로** 담되, 상세 증거 패널(웨이퍼 맵 · 이상/실패 · 분포)은 **한 번에 한 파라미터만** 렌더링합니다.

- **파라미터 내비게이터** — 우측 상단의 표. 각 행이 한 파라미터의 요약입니다: 파라미터명 · 커버리지(측정/전체) · 평균 · 3Σ · 이상 개수. 이것이 "각 파라미터의 데이터 요약"을 담는 자리입니다.
- **행 선택 = active 파라미터.** 선택하면 웨이퍼 맵 · 이상/실패 표 · 분포 · 판정 스트립의 커버리지·이상·평균 카드가 그 파라미터로 다시 그려집니다. 기존 `DataSummary.vue`의 클릭-전환 동작을 승격한 것입니다.
- **정렬 카드만 측정 단위**(파라미터 무관)입니다. 나머지 카드는 active 파라미터를 따릅니다.

## 7. 검증

- 실패 사이트가 통계에 **절대** 포함되지 않아야 합니다 (Phase A의 게이트 유지, 회귀 금지).
- 실패 개수는 백엔드 payload와 일치해야 합니다 (`45 raw − 43 measured = 2`).
- `siteVerdicts`의 `status`(판정 수행 여부)와 `severity`(이상 정도)는 계속 분리된 축입니다.
- 레이아웃 변경이므로 Phase A의 "레이아웃 불변" 제약은 여기서 해제됩니다. 단, 숫자의 의미는 바뀌지 않습니다.

## 8. 열린 질문 — **B2로 이관**

아래는 모두 peer 세트 정책 질문이므로, peer 비교(`vs PEERS` 카드)와 함께 **B2**에서 다룹니다. B1은 이 질문들에 막히지 않습니다.

1. 자동 peer 세트의 크기·기간 기본값은 얼마입니까? (예: 동일 recipe 최근 30일 / 최대 30 MSR)
2. peer 세트는 **모든 장비**를 한 풀로 봅니까, 아니면 동일 장비 / 타 장비를 나눕니까? §3.3에서는 한 풀로 두었으나, 장비 skew는 별도 `Skew Check` 기능의 영역일 수 있습니다.

### 8.1 B2 설계 제약 (research 반영)

peer 비교를 B2에서 만들 때 다음을 지킵니다(근거: `docs/issues/skewvoir/wafer-analysis-method-research.md` §1·§3.1·§5.3·§7.1).

- **탐색 집합 ≠ 동결 baseline.** 사용자가 고른 MSR 집합은 탐색 집합입니다. 관리 한계·기준선은 임의 선택에서 재계산하지 않고, 승인·버전 동결된 historical baseline에서 가져옵니다. flag된 MSR이 다음 기준선을 오염시키지 않게 합니다.
- **비교 가능성 게이트.** peer로 묶기 전에 `compatibility_signature`(recipe + revision, parameter + unit, 측정 방법·조건, 좌표계, site-layout)를 검사합니다. 불일치는 합치지 않고 분리하거나 `비교 불가`로 표시합니다.
- **명시적 모드 계약(고려).** §10.3은 세트 크기로 암묵 적응합니다. research §9 P0는 URL·백엔드에 `mode=single|set`을 명시하는 편을 권합니다. B1에는 영향이 없으며, B2 백엔드 호환성 검사 설계 시 재검토합니다.

## 9. 구현 설계 (B1 확정)

레이아웃은 현재 `views/Dashboard.vue`의 12-컬럼 그리드를 안 A로 재배치합니다. 위에서 아래로: **판정 스트립**(전체 너비, active 파라미터를 따름) → **파라미터 내비게이터**(전체 너비, 각 파라미터 요약 + active 선택) → **검사 존**(`focusedSequence`로 연결된 패널들: 웨이퍼 맵 · 반경 플롯 · 측정점 표 · SEM 이미지 · 분포 · 이상/실패 사이트 · 측정 조건 & 정렬). 인터랙션·배치의 상세는 §10입니다.

### 9.1 신규

- **`overview/VerdictStrip.vue`** — B1은 4개 카드입니다. `측정 성공률`(active 파라미터, `43 / 45 · 2 실패`), `이상 사이트`(active 파라미터, 부제 "leave-one-out vs N sites" — 같은 웨이퍼의 형제 사이트 기준이지 peer MSR이 아닙니다), `{파라미터} 평균`(평균 · 3Σ · 범위), `정렬`(측정 단위, `alignment` locked 개수). 5번째 `vs PEERS` 카드는 B2로 이관합니다(§8).
- **이상 사이트 개수의 정의** — `siteVerdicts`에서 `severity`가 정상이 아닌 사이트 수, 즉 `abnormal` + `watch`(`이상` + `주의`)입니다. 측정 실패(`cd_value: null`)는 별개의 축이며 이 수에 **포함되지 않습니다.** 이 정의가 판정 스트립 카드와 §9.2 내비게이터의 **이상 개수** 컬럼에 동일하게 적용됩니다.
- **`overview/SiteVerdicts.vue`** — 이상/실패 사이트 표: SEQ · CHIP · CD · Δ(형제 사이트 대비) · 판정 배지(`이상` / `주의` / `측정 실패`). 행 = active 파라미터의 `siteVerdicts` 중 플래그된 사이트 + `cd_value: null` 실패 행. 실패 행은 하단에 흐리게, `측정 실패`로 표시합니다.

### 9.2 개편

- **`DataSummary.vue` → 파라미터 내비게이터** — 기존 파라미터별 표에 두 컬럼 추가: **커버리지**(측정/전체)와 **이상 개수**(파라미터별 `siteVerdicts`). 파라미터 전체를 나열하고 클릭으로 `activeParam`을 전환하는 동작은 이미 있습니다. "각 파라미터 요약"은 여기에 담깁니다.
- **`WaferMap.vue`** — 실패를 더 이상 버리지 않습니다. 측정된 점은 색으로 유지하고, `cd_value: null`은 **`✕`**, 이상 사이트(`siteVerdicts`)는 **`◎`** 링으로 추가합니다. 범례에 두 글리프를 추가합니다.
- **`Acquisition.vue` → 측정 조건 & 정렬** — `focusFile.exe_detail_info`(wafer / process) + 행의 대표 `meas_condition_*`(mag / vacc / pixel) + `focusFile.alignment`(ALIGN 1~3 method / offset / score)를 읽습니다. score는 §3.2에 따라 "모니터링만 · 비교 불가"로 표기합니다. (현재는 `meas_hist` 행만 읽습니다.)

### 9.3 삭제

- **HEALTH 블록** — `useSkewvoirWorkspace.ts:59`의 `health` state와 `LeftRail.vue`의 `HEALTH · LAST 31H` 섹션(§3.4, 하드코딩 가짜 값).

### 9.4 내비게이션

- `SKEWVOIR_VIEW_MODES`에서 `dashboard` 뷰의 라벨을 `측정 개요 / Measurement Overview`로 변경합니다. `kind: 'dashboard'` 슬러그는 유지하여 기존 `view=dashboard` 링크·저장된 뷰·테스트가 계속 동작하게 합니다(표시 라벨만 변경).

### 9.5 정직성 (회귀 금지)

- `siteVerdicts`(leave-one-out, `isMeasuredRow` 게이트)가 이 화면 전체에서 "이상"의 **유일한** 정의입니다 — 스트립 카드 · 표 · 웨이퍼 `◎` · 내비게이터 이상 컬럼이 같은 함수를 읽습니다.
- 요약의 평균·3Σ는 실패를 제외해야 합니다. 백엔드 `MsrParamSummary`가 이미 게이트되어 있지 않으면 `utils/stats.ts`로 측정 행에서 프런트에서 재계산합니다(§7).
- **반경 구조 한계 (알려진 제약).** 사이트 leave-one-out은 형제 사이트 전체를 기준으로 하므로, 정상적인 center/edge 반경 구조가 있으면 가장자리 사이트가 통째로 이상으로 플래그될 수 있습니다(research §4.2). B1에서는 이를 **문서화된 한계**로 두고, 중심 보정 residual 기반 판정은 §10.3 공간 진단에서 다룹니다. B1의 `이상` 배지·부제는 "형제 사이트 대비"라는 문구로 이 기준을 명시합니다.

## 10. 인터랙션 & 워크스페이스 구조 (2026-07-15 확장)

측정 개요를 "브리핑 후 검사(brief-then-inspect)" 도구로 만들기 위한 결정 3가지입니다.

### 10.1 연결 선택 (`focusedSequence`)

패널은 두 grain으로 나뉩니다: 측정점 표 · 반경 플롯 · SEM 이미지는 **sequence 단위**(측정 행 1개 = 점 1개 = SEM 1장), 웨이퍼 맵은 **chip 단위**(같은 chip의 여러 sequence를 평균). 따라서 연결 식별자는 **`sequence`**입니다.

- `useSkewvoirAnalysis`에 `focusedSequence: Ref<number | null>`을 추가합니다(뷰 전환에도 유지 — `activeParam`과 동일 패턴).
- 측정점 행 · 반경 점 · 웨이퍼 마커 클릭 → `focusedSequence` 설정.
- **SEM 이미지**는 그 sequence의 이미지를 보여줍니다. 현재는 첫 장만 표시하고 특정 점으로 이동할 방법이 없으므로 가장 큰 개선입니다.
- 웨이퍼 맵 · 반경 플롯은 포커스 마커를 강조하고, 측정점 표는 해당 행으로 스크롤·강조합니다.
- **chip 다중 sequence 처리**: 여러 sequence가 있는 chip을 클릭하면 대표 sequence를 포커스하고 측정점 표를 그 chip으로 필터링합니다.
- 이상/실패 사이트 표(§9.1)의 행도 클릭 시 그 sequence를 포커스합니다.

이 공유 상태는 B1의 측정 개요 패널이 1차 소비자이며, 다른 뷰는 이후 무료로 채택할 수 있습니다.

### 10.2 파라미터 내비게이터 상단 배치

파라미터 내비게이터(§9.2, 옛 `DataSummary`)를 우측이 아니라 **판정 스트립 바로 아래 전체 너비 밴드**에 둡니다. 결과를 먼저 브리핑하고 아래에서 상세를 검사하는 흐름이며, "각 파라미터 요약"이 화면 상단에 노출됩니다.

### 10.3 선택 모드 적응 — 위치 비교 · Time-Series

단일 MSR과 다중 MSR은 다른 분석 과제입니다. **통합 내비게이션을 유지하되 두 뷰가 세트 크기(1 vs N)를 감지해 적응합니다.** 별도 모드 상태 없이, 이미 세트 데이터를 지연 로드하는 컴포저블 구조와 일치합니다.

| 뷰 | 단일 MSR (세트 = 1) | 다중 MSR (세트 = N) |
| --- | --- | --- |
| 위치 비교 | **공간 진단** — raw map + 실패 위치 + 중심 보정(median 차감) residual map + 반경 profile + (좌표계 검증 시) 방향·surface/residual. 표준 웨이퍼 공간 분해이며 §9.5의 반경 구조 한계를 해소합니다. | 현행 — 합성 평균 맵 + wafer-to-wafer σ. |
| Time-Series | **시퀀스 추이** — 측정 순서에 따른 값 드리프트. `SequenceTrend` 패널을 1차로 승격. 축은 `per sequence`(시간 아님)로 표기하고 좌표를 함께 표시해 scan-path/공간 혼재를 드러냅니다. | 현행 — mean ± min/max 시간 추이. |
| 상관 / 분포 | **측정 내부 관계** — 같은 site(`chip_number + sequence`)의 parameter↔parameter. scatter + Pearson + Spearman + 표본·missing pair 수. cross-parameter 분석은 여기에 둡니다. | 현행 — 측정 간 관계. |

- **위치 비교** 단일 모드(공간 진단)는 신규 작업입니다. 근거: research §4.2.
- **Time-Series** 단일 모드는 기존 `SequenceTrend` 승격 + 다중 추이 패널을 세트가 생기면 표시하는 재배치입니다. 근거: research §4.3.
- **상관 / 분포** 단일 모드(parameter↔parameter)는 cross-parameter 분석의 새 자리입니다. 근거: research §4.4. (이전 초안의 "위치 × 파라미터"를 여기로 이관.)

### 10.4 범위 순서

1. **B1 — 측정 개요** (§9 + §10.1 연결 선택 + §10.2 상단 내비게이터). 먼저 출하합니다.
2. **위치 비교 · Time-Series 적응** (§10.3). B1이 만든 `focusedSequence`를 재사용하는 후속 증분입니다.

이렇게 나누면 B1이 뷰 적응 작업에 막히지 않고, 연결 선택 상태는 한 번 만들어 두 곳에서 씁니다.

## 11. 분석 진실성·설명 계약 (research 반영)

`docs/issues/skewvoir/wafer-analysis-method-research.md` §7·§10을 B1 패널에 적용합니다. 측정 개요는 "차트 모음"이 아니라 **판단 가능한 증거**를 제시해야 하므로, 모든 패널이 다음을 지킵니다.

1. **증거 family 분리.** 커버리지(`cd_value` 실패), 정렬(`align_fail`), 이미지 실패율, vendor score는 **각각 별도 축**입니다. 하나의 health 점수로 평균내지 않습니다(§3.4·§4.1·§7.1). 판정 스트립은 이들을 별도 카드·신호로 유지합니다.
2. **`평가 불가`를 정상으로 바꾸지 않습니다.** 분모가 없거나 전제(좌표·최소 site 수 등)가 없으면 패널은 그 사유를 표시합니다(예: "좌표 없음 → 공간 분석 불가", "site 부족 → 이상 평가 불가"). 이는 `siteVerdicts`의 `status` 축을 UI에 그대로 노출하는 것입니다.
3. **관리 한계 ≠ spec 한계.** 3Σ는 통계량이며 제품 spec 합불(USL/LSL)이 아닙니다. 화면에서 통계 한계와 engineering/spec 한계를 다른 의미·이름으로 구분합니다(§5.3·§7.1).
4. **grain·개수·drill-through.** 각 패널은 자기 grain(`site` / `sequence` / `MSR`)을 표기하고 표본·커버리지·missing 개수를 보여줍니다. raw 값과 단위를 보존하며, 연결 선택(§10.1)이 point → SEM raw로의 drill-through 역할을 합니다.
5. **탐색 vs 공식.** B1은 단일 측정의 사실만 다루므로 전부 "이 측정의 값"입니다. peer/baseline 비교(B2)를 붙일 때 탐색 결과와 승인 기준선을 시각적으로 구분합니다(§8.1).

이 계약은 신규 코드가 아니라 **패널이 지켜야 할 표시 규칙**입니다. 구현 계획의 각 패널 작업에 수용 기준으로 포함합니다.

## 12. 장비 증거 — FDC & 하드웨어 (B3 · B3.2)

"장비가 원인인가?"에 답하는 증거입니다. **두 소스가 서로 다른 grain으로 존재하며 서로 다른 join이 필요합니다.** 이 구분이 UI 표면을 나눕니다.

| 소스 | grain | join | 표면 |
| --- | --- | --- | --- |
| FDC (측정 동반) — `dynamic_fdc[sequence]` · `fixed_fdc` · `fdc_params` | site/sequence · MSR | **정확 join** (sequence / MSR, 검색 없음) | 분석 **인라인**, CD와 같은 sequence 축 |
| 하드웨어 텔레메트리 — BSM · Reso · MDC · SCE · BM/PM | tool-time | **event-time join** (`eqp_id` + `start_time`~`end_time` 창) | **앵커 팝업**(slideover/modal) |

배선은 이미 존재합니다. `useHardwareApi.fetchService({ toolType, service, eqpId, fabName, start, end })`가 `start` / `end`를 받고, `meas_hist` 행이 `eqp_id` · `start_time` · `end_time`을 갖습니다.

### 12.1 B3 — FDC (측정 동반, 인라인)

- 고아 상태인 `Fdc*` 컴포넌트(`FdcAnalysis` · `FdcScatter` · `FdcSequenceTrend` · `FdcTimeSeriesChart`)를 워크스페이스에 연결합니다.
- CD와 `dynamic_fdc`를 **같은 sequence 축**에 표시하고 §10.1의 `focusedSequence`로 연결합니다. 급변 직전·직후의 SEM·alignment 증거를 이어 봅니다.
- sequence는 순서일 뿐 시간이 아닙니다. 기울기 단위는 `per sequence`이며 좌표를 함께 표시합니다(research §4.3).

### 12.2 B3.2 — 하드웨어 (timestamp, 팝업)

- MSR의 `eqp_id`와 `start_time`~`end_time` 창으로 하드웨어 서비스를 검색해 측정 **전·중·후** 장비 상태를 보여줍니다.
- **별도 앵커 팝업**으로 띄웁니다. 이유는 편의가 아니라 **grain 분리**입니다. tool-time 텔레메트리를 per-site 데이터처럼 오독하지 않도록 분석 본문과 표면을 나눕니다(research §10).
- MDC · SCE는 시계열이 아니라 MSR 시작 **이전 가장 최근 as-of snapshot**만 사용합니다. BSM · Reso · FDC-service · BM/PM은 창 내 시계열입니다.

### 12.3 지켜야 할 것 (research §5.4 · §7)

- **mock는 방법 검증 근거가 아닙니다.** Phase 1 mock은 숨은 `health` 하나로 CD와 FDC를 함께 만들므로, mock의 CD↔FDC 상관은 인공물입니다. 방법 검증은 office 역사 데이터·시간 분할에서만 합니다.
- **MSR/run 1건 = 분석 단위 1건.** 한 MSR 결과를 수천 sensor timestamp에 복제해 `N`을 부풀리지 않습니다(pseudoreplication). 하드웨어 trace는 feature로 먼저 축약합니다.
- **상관 ≠ 인과.** recipe · 장비 · 시간 공통 변화를 먼저 배제하고, `연관이며 원인 증명이 아님`을 표기합니다.
