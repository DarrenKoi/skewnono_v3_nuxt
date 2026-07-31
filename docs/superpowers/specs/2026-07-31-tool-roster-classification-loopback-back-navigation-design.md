# Tool Roster 분류·루프백 제외·복귀 동선 설계

- 날짜: 2026-07-31
- 상태: 문서 검토 대기
- 영역: `front-dev-home` 공용 장비 분류와 `/tool-roster`

## 배경

공용 `classifyToolType()`은 현재 `eqp_model_cd`가 대문자 `VERITYSEM`으로
시작할 때만 VeritySEM으로 분류합니다. 실제 전사 명부에는
`VERITY_SEM` 형식도 존재하므로 해당 장비가 Tool Roster의 `미분류` 묶음에
들어갑니다. 이 분류 함수는 Tool Roster뿐 아니라 랜딩, Fab 사이드바와 여러
장비별 화면에서 함께 사용하므로 같은 장비가 화면마다 일관되게 해석되어야
합니다.

또한 전사 명부에 `eqp_ip`가 `127.0.0.1`인 장비가 일부 존재합니다. 루프백
주소는 IT 방화벽 해제 요청에 사용할 수 없으므로 Tool Roster의 표시, 집계와
내보내기 대상에서 제외해야 합니다.

Tool Roster는 랜딩의 System Status에서 진입하지만 현재 페이지 안에는 랜딩으로
돌아가는 명시적인 동선이 없습니다.

## 목표

- `VeritySEM`과 `Verity_SEM` 접두사를 대소문자와 무관하게 VeritySEM으로
  분류합니다.
- 공용 분류 함수를 사용하는 모든 화면에 같은 규칙을 적용합니다.
- `eqp_ip` 앞뒤 공백을 제거한 값이 정확히 `127.0.0.1`인 행을 Tool Roster의
  모든 사용자 동작에서 제외합니다.
- Tool Roster 헤더에서 랜딩(`/`)으로 돌아갈 수 있게 합니다.
- 알 수 없는 다른 모델은 계속 `미분류`에 남겨 신규 장비 유형이 조용히
  사라지지 않게 합니다.

## 선택한 설계

### 공용 VeritySEM 분류

`front-dev-home/app/utils/toolType.ts`의 `classifyToolType()`에서 VeritySEM
판정용 문자열을 대문자로 정규화합니다. 정규화된 모델명이 다음 접두사 중
하나로 시작하면 `verity-sem`을 반환합니다.

- `VERITYSEM`
- `VERITY_SEM`

이는 접두사 규칙이므로 `VeritySEM_4`, `verity_sem_5`와 그 뒤에 다른 모델
식별자가 이어지는 값도 인식합니다. CD-SEM, HV-SEM과 Provision의 기존 규칙은
이번 변경에서 확장하지 않습니다.

분류 함수를 페이지별로 복제하지 않습니다. 기존 모든 소비자가 공용 함수를
계속 사용하므로 랜딩의 장비 수, Fab 사이드바와 Tool Roster가 같은 결과를
얻습니다.

### Tool Roster의 루프백 제외

`front-dev-home/app/utils/pendingToolMatrix.ts`에 Tool Roster 행을 정제하는 순수
함수를 둡니다. 이 함수는 `row.eqp_ip.trim() !== '127.0.0.1'`인 행만
반환합니다.

`tool-roster.vue`의 최상위 `rows` 계산에서 API 응답을 이 함수에 한 번
통과시킵니다. 이후의 모든 기능은 이미 정제된 `rows`에서 파생되므로 별도
조건을 반복하지 않아도 다음 항목에서 같은 장비가 제외됩니다.

- 헤더의 조회 장비 수
- Tool Type 필터 수량과 `미분류` 수량
- Fab × 모델 매트릭스와 셀 드릴다운
- IP 목록 복사
- CSV 다운로드
- 모든 장비가 연결되었다는 빈 상태 판정

`127.0.0.1`만 제외합니다. 전체 `127.0.0.0/8`, 빈 IP 또는 다른 특수 주소를
추가로 제외하는 것은 이번 요구사항에 포함하지 않습니다.

백엔드 `GET /api/sem-list/pending` 계약과 provider는 변경하지 않습니다. 실제
사무실의 `office.py`는 환경별 추적 제외 파일이므로, 프론트엔드 경계에서
정제해야 mock과 현재 office adapter 모두 같은 화면 동작을 보장할 수 있습니다.

### 랜딩 복귀 버튼

`tool-roster.vue` 카드 헤더의 제목 왼쪽에 Nuxt UI 버튼을 추가합니다.

- 목적지: `/`
- 아이콘: `i-lucide-arrow-left`
- 레이블: `뒤로가기`
- 스타일: 기존 상세 화면의 중립 계열 버튼 패턴

링크는 브라우저 이력에 의존하는 `router.back()`이 아니라 고정된 `/`를
사용합니다. 직접 URL로 Tool Roster에 진입한 경우에도 항상 요청한 랜딩
페이지로 이동해야 하기 때문입니다.

## 데이터 흐름

```text
GET /api/sem-list/pending
  → 127.0.0.1 행 제외
  → 공용 classifyToolType(eqp_model_cd)
  → 필터 수량 / 매트릭스 / 드릴다운 / IP 복사 / CSV
```

## 테스트

구현은 테스트 주도로 진행합니다.

1. 기존 순수 함수 테스트에 `VeritySEM`, `Verity_SEM`의 대소문자 변형이 모두
   `verity-sem`으로 분류되는 실패 테스트를 추가합니다.
2. `127.0.0.1`과 공백이 붙은 `127.0.0.1` 행은 제외되고 일반 IP 행은
   유지되는 실패 테스트를 추가합니다.
3. 최소 구현 후 해당 테스트와 전체 프론트엔드 테스트를 실행합니다.
4. `npm run typecheck`와 변경 파일 대상 ESLint를 실행합니다.
5. 실행 중인 앱에서 버튼의 `/` 이동, 미분류 수량 정정과 루프백 장비의
   표시·복사·CSV 제외를 확인합니다.

## 변경하지 않는 범위

- 백엔드 pending endpoint와 `PendingToolRow` 계약은 변경하지 않습니다.
- `127.0.0.1`이 아닌 특수 IP에 대한 새 정책은 만들지 않습니다.
- VeritySEM 이외 장비군의 대소문자 규칙은 변경하지 않습니다.
- 미분류 fallback과 Tool Type 필터 UI는 유지합니다.
