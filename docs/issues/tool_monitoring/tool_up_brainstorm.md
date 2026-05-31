# BM/PM 장비 Up 게이트 & PM 집중 관리 — 브레인스토밍 결정 기록

- 작성일: 2026-05-31
- 단계: **설계·계획 완료**. 본 문서는 초기 **결정 기록**이며, §4의 모든 과제가
  해소되어 정식 spec과 구현 plan으로 승격되었습니다.
  - 정식 spec: `docs/superpowers/specs/2026-05-31-bmpm-up-gate-pm-planning-design.md`
  - 구현 plan: `docs/superpowers/plans/2026-05-31-bmpm-up-gate-pm-planning.md`
- 원천 이슈: `docs/issues/tool_monitoring/tool_up_rules.txt`
- 상위 도메인: `docs/issues/hardware_mgmt/skew_btw_tools.txt`
- 공유 코어: `docs/superpowers/specs/2026-05-31-tool-skew-mgmt-design.md`
  (스큐 코어 엔진 — consensus·skew·epoch). 본 기능은 그 스펙이 미뤄둔
  **"응용 ②: PM MDC·CD_MONITORING 목표값 사전 산출"**의 구체화입니다.

## 1. 풀려는 문제

엔지니어는 BM/PM마다 Data를 직접 확인하고 장비 Up/Down을 결정합니다. HW 엔지니어가
점검을 마치면 App(MI) 엔지니어에게 Data 확인을 요청하는데, App 엔지니어가 부재하면
확인 주체가 없어 **장비 Up이 지연**되는 것이 통증입니다.

동시에, 지금까지는 PM 시 **그 장비 자기 기준**으로만 전후 값이 spec range에 들면
Up 했기 때문에, 장비는 안정적으로 운영되지만 **시간이 지나도 fleet 간 스큐가
개선되지 않는** 단점이 있습니다.

## 2. 핵심 긴장 — 두 조건의 충돌

| 조건 | 내용 | 방향 |
| --- | --- | --- |
| 1. 연속성 | BM/PM 전후 계측 데이터가 spec range 안에서 유지 | "변하지 마라"(자기 baseline) |
| 2. 수렴 | fleet 중앙값에서 먼 장비를 median 쪽으로 유도 | "변해라"(fleet median) |

의도적 MDC 조정은 전후 delta를 만들므로, **"언제 안정성보다 수렴을 우선하는가"**가
이 설계의 심장입니다. 해법은 **바깥쪽 N개 장비만 중앙으로 당기는 순위 기반
접근**입니다(전 장비가 median을 쫓으면 표적이 흔들려 진동하지만, 바깥 N개만
당기면 분포가 매 PM 사이클마다 좁아지기만 하여 수렴합니다).

## 3. 확정 결정

| 항목 | 결정 |
| --- | --- |
| 스코프 | 신규 별도 spec, 스큐 코어(consensus·skew·epoch)를 **계약으로 공유** |
| 구조 (A) | 별도 라우트 1개 + 코어 공유. finder(`/skew-check`)와 분리 |
| 출력 (가) | 장비별·즉시 **Up 게이트** — 통과 시 HW 엔지니어 단독 Up |
| 출력 (나) | fleet **집중 관리 대상 선정** — 빔 조건별 중앙값 거리 순위 |
| 튜닝 철학 | 후순위 N개만 중앙으로 — 분포 수렴, 진동 회피 |

### 3.1 출력 (가) — Up 게이트

- **하드 게이트(통과 시 HW 단독 Up):** (a) CD_MONITORING 계측값이 spec range 안 +
  (d) BSM(빔 형상 radar)이 spec range 안. 둘 다 자기 참조적이라 App 엔지니어
  없이도 판정 가능합니다 → 통증 해결.
- **advisory 신호:** (b) fleet 대비 스큐를 게이트 옆에 함께 표시합니다. **Up을
  막지 않으며**, 멀면 다음 PM 집중 대상 후보로 적재만 합니다(양산은 계속 돌려야
  하므로 지금 Up은 보류하지 않음).
- **제외:** (c) MDC 변화는 게이트 항목이 아니라 수렴 추천의 이력 입력·epoch
  마커로 사용. (e) 특수각은 deferred(기존 스큐 스펙과 동일).

### 3.2 출력 (나) — 집중 관리 대상 선정

- **순위 최소 단위 = 빔 조건(500V·800V).** 빔별로 중앙값에서 먼 장비 N개를
  다음 PM 집중 대상으로 지명합니다. 축(X/Y)은 드릴다운.
- HW가 빔 칼리브레이션을 빔·축별로 수행하므로 "이 장비의 800V·Y가 멀다"가
  실행 단위입니다.
- 지명은 **HW 협의 후 확정**(시스템은 후보를 제시, 사람이 결정).

### 3.3 수렴 추천의 해상도 — (1) 채택

- 셀(빔×축)별로 `현재값 · fleet median(목표) · 부호 있는 gap`과 MDC·BSM 과거
  epoch 이력을 나란히 제시하고, 방향은 정성 화살표("median보다 +0.4nm 높음 →
  낮추는 쪽") 수준으로 둡니다.
- **MDC는 절대 목표값이 아닙니다.** 하드웨어 리세팅을 하면 default가 완전히 새로
  잡히므로 MDC 이력은 주로 *그 장비 자신의 이력 관리*용입니다. HW 세팅이 이미
  최적이고 **최종 출력값만 옮기면 될 때** MDC를 조정하며, 이때 타겟값을 제시할
  수는 있으나 그것이 최종 목표는 될 수 없습니다.
- "권고 MDC 수치 산출"은 회귀모델·office 실데이터가 필요하므로 deferred.

## 4. 다음 세션 과제 — ✅ 모두 해소 (2026-05-31)

아래 항목은 후속 브레인스토밍에서 모두 확정되어 정식 spec에 반영되었습니다.

1. **대시보드 레이아웃** → **레이아웃 A(스택)** 채택. 라우트
   `/ebeam/cd-sem/[fab]/pm-planning`, 헤더 `EbeamMetaBar`. 게이트는 슬림 상단
   스트립, 집중 관리가 full-width 본문.
2. **열린 결정 확정:**
   - 순위 지표 = **max-axis** `max(|skew_X|, |skew_Y|)` (빔별, 축은 드릴다운).
   - 선정 규칙 = **advisory 임계 게이트 → bottom-N** (자기-제한).
   - N·임계값 = **knob + 기본값**(N=3, 빔별 임계 500V 0.30 / 800V 0.40 nm),
     클라이언트 재계산.
   - spec range 원천 = 기존 per-tool spec(**hardware 피처가 소유**). 게이트는
     **사후값 ∈ spec**만 보고 전후 delta는 context(비차단).
3. 정식 spec 승격 + `writing-plans` 완료 (위 헤더의 두 문서 링크 참조).

### 4.1 구현 착수 전 유의사항 (다음 작업자용)

- **스큐 코어는 아직 docs-only.** 백엔드에 consensus·skew·epoch 엔진과
  `/skew-check` 페이지가 구현되어 있지 않습니다. 따라서 Phase-1 `pm_planning`
  mock은 계약에 맞는 skew 데이터를 **자체 합성**합니다(코어 구현 시 `data.py`만 스왑).
- **hardware 피처에 spec range 필드가 실제로는 아직 없습니다.** plan의 Task A1이
  `hardware/providers/spec_range_mock.py`를 새로 추가해 소유권은 hardware에 두고
  `pm_planning`이 import하는 구조로 처리합니다.

## 5. 범위 밖 (후속)

- 권고 MDC 수치 자동 산출(회귀모델·office 데이터 필요).
- 특수각 전용 검증.
- 알람 발송 채널.
