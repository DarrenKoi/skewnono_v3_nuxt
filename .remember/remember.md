# Handoff — 장비간 스큐(skew-check) 용어·통계 정리 세션

- 날짜: 2026-05-31
- 작업 영역: `main`
- 산출물: `docs/issues/hardware_mgmt/skew_check_terminology_and_stats.md` (신규, 린트 통과)
- 상위 설계: `docs/superpowers/specs/2026-05-31-tool-skew-mgmt-design.md`
- 다음 액션: 위 문서 §8의 **미해결 수치 6개**를 확정 → `skew_check_next_steps.md`
  §1·§3과 묶어 `writing-plans`로 진행.

## 이번 세션에서 한 일

설계 스펙이 통계 수법을 "이름만 있고 정의가 없는" 상태였음(consensus·잔차·skew를
어떤 입도로 계산하는지 불명확). 이를 **용어 정의 + 계산 입도의 과학적 근거**로
고정하고 새 문서에 기록함. 모든 결정에 "왜"를 함께 남김(office 구현자가 잘못된
단순화로 회귀하지 않도록).

## 확정된 결정 (근거와 함께 문서에 기록됨)

- **fleet(함대)** = 그날 그 cell을 **실제 측정한 장비만**(등록 전체 아님). 팹 스코프.
- **consensus(기준값)** = 같은 cell·site·**그날**, 장비 site평균들의 로버스트 중앙값.
  절대 진실값 아닌 fleet 자체 합의. **반드시 하루 단위**(윈도우로 내면 공통 드리프트가
  잔차에 남음).
- **잔차(residual)** = `tool − consensus` (부호 고정, 양수=높게 읽음).
- **skew** = 윈도우 내 일별 잔차의 계통 평균. 장비쌍 skew = `|skew_i − skew_j|`.
- **계산 입도 = site별** (전체평균 아님). 근거: 분산 3층 분해
  `CD = TrueCD(site) + LocalVar + ToolSkew + noise`. site-index 매칭으로 site 간
  패턴(±0.1nm) 상쇄 → ToolSkew만 분리. 전체평균은 ① 공간 어긋남 은폐(평균 같아도
  site마다 다른 두 장비 구분 못 함) ② 불균형 패턴 누수 ③ 신뢰구간 악화.
- **측정 현실**: Wafer당 9 site × site당 2점(무작위 접근). site-index는 매칭되나
  측정점은 매칭 안 됨 → "site 매칭 + site내 평균"(상쇄 아닌 감쇠).
- **풀링은 일별 잔차에서**(원시점 아님). 하루=기준값/잔차, 윈도우=잔차→skew 집계.
- **윈도우** = 현재 epoch 내(cell 차원이 자동 보장) · 통상 ~1주 · **최대 2주 lookback**.
  부족하면 신뢰도 강등(억지 확장 금지).
- **측정 cadence**: 24h에 1~2h 간격 1대씩 → 동시 합의 불가, "하루"가 fleet 전원 담는
  최소 버킷. 스케줄 **회전형**(확인) + 하루내 공통변동 < 스큐(확인) → 시각 교란이
  윈도우에서 평균 소멸(고정 슬롯이면 alias 위험, detrend 필요 — office 검증).
- **epoch 리셋 트리거 = MDC 값 변경, 그것만**(다운·수리 자체 아님). 장비별 타임라인.
- **장비 다운 두 갈래**: 단순 다운(MDC 불변)=같은 epoch, 2주 내 이어 풀링 /
  PM·BM(MDC 변경)=새 epoch, 과거 단절.
- **BM/PM 이벤트 = 하드경계(MDC변경) vs 소프트마커(MDC불변)** 2층. 소프트마커는
  epoch 유지하되 후보 불연속점으로 표시. 기본=마커 이후 우선+부족시 플래그 풀링.
  진단 신호(MDC 못 잡은 H/W 드리프트)·안정성 플래그 설명·대시보드 마커로 활용.
  BM/PM 이벤트는 `mdc_history`와 별개 계약 입력.

## 미해결 (다음 세션 = §8)

- consensus 로버스트 추정량 구체형(중앙값/trimmed/Huber) + 유효 최소 표본 수.
- 신뢰도 tier(High/Med/Low) 경계 수치.
- cd_band bin 경계.
- 안정성 플래그 분산 임계값.
- 유효 최소 fleet 수(다중 동시 다운 시 그날 스킵).
- 유효 최소 잔차 수(신뢰도 강등 임계).
- BM/PM 소프트 마커 처리 규칙(마커 이후 우선 vs step 검정) — office 정교화.

## 참고

- 이 문서는 계약·UX만 증명하는 Phase-1 범위. 실제 통계 구현·"추천이 옳다" 검증은
  office에서 `data.py` 스왑 후 별도 수행.
- 미해결 수치 대부분은 `skew_check_next_steps.md` §1·§3의 "열린 결정"과 동일 빈칸.
