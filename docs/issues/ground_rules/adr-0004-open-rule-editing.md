---
status: accepted (supersedes ADR-0003)
---

# 계측 룰·어노테이션 편집은 전 엔지니어에게 개방합니다

> 본 ADR 은 `docs/issues/ground_rules/` 폴더 규약에 따라 이곳에 둡니다. 루트 `docs/adr/0003-admin-only-rule-editor.md` 를 **supersede** 합니다.

계측 룰(파라미터 cap 정책)과 lot 어노테이션(`memory_class` 오버라이드, `yield_check_state`)은
**인증된 엔지니어 누구나** 프런트엔드에서 자유롭게 편집합니다. ADR 0003 의 관리자 전용 게이트를 제거하는
대신, SSO 신원 기반 변경 추적 + 모든 변경의 **버전 이력**(author·timestamp) + **언제든 rollback** 으로
무결성을 확보합니다. 이 grilling 의 목표 자체가 "누구나 쉽게 룰을 바꾸고 모니터링하는 시각적 surface"이므로,
편집을 한 사람에게 묶는 권한 모델은 목표와 충돌합니다.

## 고려된 대안

- **관리자 전용 (ADR 0003)** — 신호등이 cross-team 매체라 single source of truth 여야 한다는 논리.
  기각: admin 1인(daeyoung)이 전사 lot 의 수율 전→후 전이와 Tech·Advanced 메모리 분류를 상시 추적·입력하는
  것은 병목이며 비현실적. admin 이 상시 대응 불가.
- **lot 담당자 한정** — 담당자가 자기 lot 어노테이션만 편집. 사실 입력으로는 자연스러우나, 룰(정책)까지
  열지 못하고 권한 경계 관리 비용이 듦. "누구나 쉽게"라는 목표에 못 미침.

## 결과로 따라오는 제약

- **룰 저장소는 현재 상태만이 아니라 append-only 버전 이력 + rollback 을 지원**해야 한다
  (CONTEXT.md §계측-룰 의 "seed 룰 + read/write API" 보다 확장된 요구).
- 동시 편집·실수로 전사 신호등이 즉시 흔들릴 수 있다 → history + rollback + SSO attribution 이 안전망.
  변경 시점·이유를 공유하는 운영 practice(예: 변경 사유 메모 필드) 권장.
- 신뢰 기반(권한 기반 아님) 모델 — "책임감 있게 행동한다"는 조직 전제 위에 선다. 전제가 깨지면 재검토.
- 루트 `docs/adr/0003` 은 본 ADR 로 superseded 처리 필요(사용자 승인 후 루트 수정).
