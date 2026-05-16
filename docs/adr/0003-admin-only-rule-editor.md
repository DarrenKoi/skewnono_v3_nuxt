# Measurement Rule 편집은 관리자 전용입니다

[[계측-룰]] (Measurement Rule) 은 모든 [[lot-health-signal]] 계산의 입력입니다. 한 lot 의 신호등 색이 *cross-team coordination 매체* 로 쓰이므로 — 담당자가 임원에게 빨간 lot 을 보고할 때, 임원이 다른 팀에 비교 directive 를 내릴 때 — 룰은 **single source of truth** 여야 합니다. 따라서 룰 편집은 별도 `/admin/measurement-rules` 페이지에서 **관리자(admin) 한 사람만** 수행하고, 다른 사용자는 read-only 입니다.

## 고려된 대안

- **Per-user editable rule** — 사용자가 자기 보기용으로 룰을 자유롭게 수정. 개인 분석에는 편하나, 신호등 색의 *공유 의미* 가 사라짐. "내 화면에서는 R3K-12 가 red 인데 네 화면에서는 green" 이라는 상황이 발생하면 evidence forwarding ([[0002]]) 자체가 무의미.
- **Per-team editable rule** — 팀 단위로 룰을 둠. fab 운영 조직이 lot 단위 ([[lot]]) 라 팀 경계가 fab 안에서도 여러 갈래로 갈리고, 같은 fab 안의 다른 팀이 *서로 다른 룰* 로 같은 lot 을 본다는 모순이 생김.
- **Anyone can edit, audit log 로 통제** — 자유롭게 편집하되 변경 이력을 추적. 변경 자체는 막지 않으므로 *현재 시점* 의 single source of truth 가 흔들리고, audit 으로는 "지금 색이 왜 이런가" 라는 *실시간 질문* 에 답하지 못함.

## 결과로 따라오는 제약

- 사용자가 룰에 동의하지 않을 때 *제안 채널* 이 따로 필요 — 첫 버전은 구두/Slack 으로 처리, 추후 페이지 안에서 "이 룰 수정 요청" 같은 surface 검토.
- 룰 변경 시 모든 사용자의 신호등이 *동시에* 바뀜 — 의도된 동작이지만, 변경 직후의 인지 부조화 (어제 green 이던 lot 이 갑자기 red) 가 발생. admin 이 룰을 바꾸는 행위가 사실상 *전사 broadcast* 이므로 변경 시점·이유를 공유하는 운영 prac 필요.
- 룰 편집 권한이 한 사람 (현재 daeyoung) 에게 묶임 — bus-factor 1. 단기적으로 수용하되, 권한 위임 / 백업 admin 정책은 운영 단계에서 별도 결정.

## 되돌리기 어려운 이유

권한을 *닫는 방향* (read-write → read-only) 은 사용자의 기존 워크플로를 뺏는 일이라 정치적 비용이 큽니다. 처음부터 read-only 로 시작하면 "편집 권한이 없다" 가 default 라 마찰이 없지만, 한 번 read-write 로 열고 나면 "내가 쓰던 기능을 왜 가져가나" 가 반드시 발생. 따라서 *보수적 default* (관리자 전용) 로 시작합니다.
