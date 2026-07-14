# 접근 제어(X-ID 차단 + 예외 관리) 설계

- 작성일: 2026-07-14
- 상태: 승인됨 (구현 진행)

## 1. 목적

사번(멤버 ID)이 `X`로 시작하는 사용자는 기본적으로 서비스 데이터를 볼 수 없도록 차단합니다.
단, 관리자가 예외로 허용한 X-사용자는 정상적으로 이용할 수 있습니다.
예외 목록은 관리자 전용 페이지(`/admin/access`)에서 관리하며, 관리자는
홈 환경에서는 `local-dev`, 운영(클라우드) 환경에서는 사번 `2067928`입니다.

## 2. 배경 (현재 구조)

- 신원 확인은 `back_dev_home/_auth/`가 담당합니다. 홈에서는 `LASTUSER` 쿠키,
  운영에서는 `hcputil.auto.sso` SSO 검증으로 `g.user_id`를 설정합니다.
- 인가(누가 무엇을 볼 수 있는가)는 현재 `activity/data.py`의
  `is_admin()`(관리자 활동 패널 전용)만 존재하며, 일반 데이터 접근 제한은 없습니다.
- `/api/admin/logs`는 현재 서버 측 관리자 검사가 없는 상태입니다(이번 작업에서 보완).

## 3. 접근 정책

| 사용자 | 결과 |
| --- | --- |
| ID가 `X`/`x`로 시작 + 예외 목록에 없음 | 차단 (모든 `/api/*`에 403) |
| ID가 `X`/`x`로 시작 + 예외 목록에 있음 | 정상 이용 |
| 그 외 모든 사번 | 정상 이용 |
| 관리자 | 항상 정상 이용 (차단 규칙 우회) |

- ID 비교는 대소문자를 구분하지 않습니다. 예외 목록에는 대문자로 정규화하여 저장합니다.
- 차단은 `_auth/middleware.py`의 `before_request`에서 전역 적용합니다.
  쿠키/SSO 경로와 `Bearer skn_...` API 토큰 경로(토큰 소유자 기준) 모두 동일하게 검사합니다.
- SPA HTML 서빙(비-API 경로)은 차단하지 않습니다. 차단된 사용자에게도 프런트엔드가
  로드되어야 "접근 권한 없음" 안내 화면을 보여줄 수 있기 때문입니다(fail-closed는
  데이터 계층인 `/api/*`에서 보장).

### 오류 응답 형식

```json
{ "error": { "code": "access_denied", "message": "..." } }
```

HTTP 상태 코드는 `403`입니다. 프런트엔드는 `code === "access_denied"`로 차단 여부를 판별합니다.

## 4. 백엔드 구성

### 4.1 `_auth/admin.py` (신규, 공용 관리자 판정)

- `_admin_allowlist()` — `SKEWNONO_ADMIN_USERS` 환경 변수(쉼표 구분)가 있으면 사용,
  없으면 기본값: 클라우드 `{"2067928"}`, 홈 `{"local-dev"}`.
- `is_admin(user_id)` — 기존 `activity/data.py`의 동명 함수를 이 모듈로 이동합니다.
  `activity/data.py`는 여기서 import 하도록 변경합니다(동작 동일, 클라우드 기본값만 교체).
- `require_admin` — 라우트 데코레이터. 비관리자는
  `403 {"error": {"code": "forbidden"}}`.
- 기존 취약점 보완: `/api/admin/logs`에도 `require_admin`을 적용합니다.

### 4.2 `access_control/` (신규 피처 폴더)

표준 피처 패턴(`data.py` = 스왑 계층, `routes.py` = 블루프린트)을 따릅니다.

`data.py`:

- 예외 목록은 `back_dev_home/access_control/state/access_exceptions.json`에 저장합니다.
  - 경로는 `SKEWNONO_ACCESS_EXCEPTIONS_FILE` 환경 변수로 재정의 가능(운영에서 패키지
    디렉터리가 읽기 전용일 경우 대비).
  - `.gitignore`에 추가합니다.
  - `threading.Lock`으로 보호하고, 변경 시 즉시 파일에 기록(write-through)합니다.
  - 파일 mtime이 바뀌면 다시 읽습니다 — 멀티 워커 WSGI 환경에서도 한 워커의
    grant가 다른 워커에 전파됩니다.
  - 파일이 없으면 빈 목록으로 동작합니다. 파일이 손상/읽기 불가면 해당 요청만
    빈 목록으로 판정(fail-safe)하되 캐시하지 않고, 그 상태에서의 변경(추가/제거)은
    503으로 거부합니다 — 부분 로드된 뷰로 파일을 덮어써 기존 grant를 유실하는
    사고를 방지합니다. 쓰기 실패도 503으로 관리자에게 그대로 노출됩니다.
- 공개 함수: `is_blocked(user_id)`, `list_exceptions()`, `add_exception(user_id)`,
  `remove_exception(user_id)`, `record_denied(user_id)`, `list_denied()`.
- `is_blocked`는 순수하게 "X 접두 + 예외 아님" 규칙만 판정합니다.
  관리자 우회는 집행 지점(미들웨어)에서 처리합니다.
- 차단 시도 기록은 메모리 링 버퍼(최근 50건, 사용자별 중복 제거, 마지막 시각 갱신)로만
  유지합니다. 편의 기능이므로 재시작 시 소실되어도 무방합니다.
- `add_exception` 검증: 공백 제거 후 비어 있지 않아야 하고, `X`로 시작해야 합니다
  (X-사번이 아닌 ID는 차단 대상이 아니므로 400으로 거부).

`routes.py` (모두 `@require_admin`):

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/admin/access` | 규칙 + 예외 목록 + 최근 차단 시도 통합 조회 |
| POST | `/api/admin/access/exceptions` | 예외 추가 (`{"user_id": "X1234"}`) |
| DELETE | `/api/admin/access/exceptions/<user_id>` | 예외 제거 |

조회를 하나의 GET으로 통합한 이유: 관리 페이지가 한 번에 필요한 데이터이고,
사용자당 20req/5s 레이트 리밋을 아끼기 위함입니다.

### 4.3 `_auth/middleware.py` 수정

신원 확정 직후(토큰 경로·SSO/쿠키 경로 공통) 차단 검사를 수행합니다.

```text
user_id 확정
  → 관리자면 통과
  → is_blocked(user_id)이면 record_denied(user_id) 후
      /api/* 요청: 403 access_denied
      그 외(SPA HTML 등): 통과
```

## 5. 프런트엔드 구성

### 5.1 차단 안내 화면

- 앱 시작 시 플러그인에서 `/api/activity/me`를 1회 호출해 신원을 확인합니다.
- `403 access_denied` 응답이면 전역 상태(`useState('access-denied')`)를 설정하고,
  `app.vue`가 앱 셸 대신 전체 화면 안내 컴포넌트
  (`components/access/AccessDeniedScreen.vue`)를 렌더링합니다.
  보호된 UI가 잠깐 노출되는 현상(flash)이 없어야 합니다.
- 안내 문구: 접근 권한이 없다는 설명 + 관리자에게 문의(사번 2067928) 안내.

### 5.2 관리 페이지 `/admin/access`

- `pages/admin/access.vue` — 기존 `/admin/logs`와 나란한 독립 페이지.
- 구성: 차단 규칙 안내 카드, 예외 목록 테이블(제거 버튼), 사번 직접 추가 폼,
  최근 차단 시도 목록(행별 "허용" 원클릭 버튼).
- `composables/useAccessControlApi.ts` — 통합 조회 + 추가/제거 함수.
- 프런트 가드: `/activity/me`의 `is_admin`이 아니면 접근 불가 안내를 표시합니다
  (서버가 어차피 403으로 거부하므로 UI 편의 목적).

## 6. 테스트

백엔드는 표준 라이브러리 `unittest` + Flask 테스트 클라이언트를 사용합니다
(`tests/test_access_control.py`, 실행: `.venv/bin/python -m unittest discover tests`).

- X-접두 사번 차단(403 + `access_denied` 코드) / 일반 사번 통과
- 예외 추가 → 접근 허용, 제거 → 다시 차단 (JSON 파일 왕복 포함)
- 관리자 우회(차단 규칙 미적용)
- 비관리자의 `/api/admin/access`, `/api/admin/logs` 호출 시 403
- 차단 시도 기록(중복 제거, 최근 시각 갱신)
- 대소문자 무시 비교(`x1234` 차단, 예외 `X1234` 등록 시 `x1234` 허용)

프런트엔드는 브라우저에서 `LASTUSER` 쿠키를 바꿔가며 실사용 검증합니다
(차단 화면, 예외 등록 후 정상 접근, 관리 페이지 CRUD).

## 7. 이후 확장 (이번 범위 아님)

- 예외 목록의 사무실(운영) 저장소 전환: `access_control/data.py`만
  OpenSearch/Redis 구현으로 교체하면 됩니다(라우트·미들웨어 불변).
- 관리자 다수 운영: `SKEWNONO_ADMIN_USERS` 환경 변수로 코드 수정 없이 확장 가능합니다.
