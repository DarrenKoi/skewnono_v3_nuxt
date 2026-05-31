# 장비간 스큐 관리 — 구현 진행 전 다음 단계

본 문서는 설계 스펙
(`docs/superpowers/specs/2026-05-31-tool-skew-mgmt-design.md`)을 구현 플랜으로
옮기기 전에, 먼저 짚어야 할 항목과 진행 순서를 정리한 것입니다. 검토 후
`writing-plans` 단계로 넘어갑니다.

## 1. 확정된 결정 (2026-05-31 brainstorming 완료)

스펙 §7.3 "열린 결정"을 모두 확정했습니다. 구현 플랜은 아래를 전제로 작성합니다.

| 항목 | 확정 | 비고 |
| --- | --- | --- |
| 군집 연결 규칙 | 완전연결(clique) = **N배화** | 단일연결(transitive) 기각 — 체이닝으로 비-TTTM 장비를 한 그룹에 묶는 오류 방지. 장비쌍 스큐 ≤ tolerance = 상호 **TTTM**(Tool to Tool Matching). |
| tolerance 기본값 | 고정 nm — 기본 0.05nm, 범위 0.01~0.20nm(step 0.005) | 엔지니어 knob. 가드레일 기본값 ≥ SE(잡음 절단 방지). office 재튜닝. |
| cd_band bin 경계 | 공정 영역대 고정 경계 | 데이터 기반 배제(셀 ID 안정성). 예시 <25/25–50/50–100/100–200/≥200nm, 정확값 office 확정. |
| 참고(양산) 표시 | 요약 칩 + 펼침 드릴다운 | 주석 `TTTM 미반영`. tier명 "방증"→"**참고**". |
| 1차 답 선택 | **최대 N배화** | 동률 시 (a) 약한 장비쌍 스큐 작은 쪽 → (b) 신뢰도 높은 쪽. |

## 2. 데이터·계약 의존성 확인

| 의존 | 확인 사항 | 현재 가정 |
| --- | --- | --- |
| meas_hist → msr/idp | Recipe의 점유 셀 도출 가능 여부 | msr=계측값, idp=빔조건으로 추적 가능(확인됨) |
| hardware 피처 | BSM·MDC 데이터를 입력으로 재사용 | 기존 데이터를 계약으로 연결, 중복 생성 금지 |
| 팹 스코프 | `[fab]` 라우트·`fac_id`로 팹 내부 한정 | 개발(R3)·양산(M계열) 교차 금지 |
| MDC epoch | BM/PM 변경 시점 이력 적재 | epoch 경계·baseline 리셋의 원천 데이터 |

## 3. 구현 순서 (tracer-bullet 수직 슬라이스)

각 슬라이스는 계약→mock→UI를 관통하여 화면에서 확인 가능한 단위입니다.

1. **계약 + 픽스처 골격** — `back_dev_home/ebeam/<...>/skew/` 에 `contracts.py` ·
   `__fixtures__/` 로 3-tier 응답 형태(`direct_skew_matrix` ·
   `predicted_skew_matrix`+`confidence` · `production_corroboration` ·
   `current_tolerance` · `epoch_markers` · `mdc_history`)를 확정합니다.
2. **mock data.py + routes.py** — 셀 단위 mock 출력을 내려주는 데이터 접근 계층과
   블루프린트를 추가합니다(팹 스코프).
3. **대시보드 ① finder** — `/ebeam/cd-sem/[fab]/skew-check` 에 최대 N배화(1차 답) +
   장비쌍 행렬(TTTM 근거 드릴다운) + tolerance knob(클라이언트 N배화) + 양산 참고
   칩(`TTTM 미반영`)을 구현합니다.
4. **대시보드 ② 함대 현황** — 오늘 장비쌍 행렬 + consensus 편차.
5. **대시보드 ③ 트렌드·epoch** — 장비별 skew 시계열 + BM/PM 마커.
6. **대시보드 ④ MDC 이력** — 빔 조건 × 축별 변경 타임라인.

## 4. 검증 범위 (Phase-1)

- Phase-1이 증명하는 것은 **계약과 UX**뿐입니다. "추천이 옳다"는 검증은 office
  실데이터로 `data.py` 스왑 후 별도 수행합니다.
- 합성 mock으로는 방법론의 정확성을 증명할 수 없으므로, 슬라이스의 완료 기준은
  "계약·화면 흐름이 동작하는가"로 둡니다.

## 5. 범위 밖 (후속 spec)

- 특수각 전용 Wafer 수집·검증.
- 스큐 = f(CD) 회귀 모델(예측 tier 승급).
- 패턴/uniformity 성분 분리.
- 응용 ②: PM MDC·CD_MONITORING 목표값 사전 산출.
- 알람 발송 채널.

## 6. 다음 액션

§1 결정을 모두 확정했으므로, 다음 세션에서 `writing-plans` 스킬로 구현 플랜을
작성합니다(스펙 §6 계약 · §5 대시보드 4섹션 기준).
