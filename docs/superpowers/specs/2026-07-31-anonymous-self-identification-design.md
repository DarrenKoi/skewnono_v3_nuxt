# 익명 사용자 자기 신원 입력 (Self-Identification) 설계

## 1. 배경

Phase 3 클라우드에서 사용자 식별은 사내 인프라가 내려주는 `LASTUSER` 쿠키
하나에 의존합니다. 쿠키가 없는 요청은 현재 `anonymous` 라는 공유 ID 로 기록되며
(`_auth/provider.py`), 앱은 정상 동작합니다.

문제는 그 트래픽이 **누구의 것인지 알 수 없다는 점**이 아니라, 알 수 없다는
사실이 조용하다는 점입니다. 쿠키를 전달하지 않는 호스트 설정이든 실제 익명
접근이든, 활동 로그에는 `anonymous` 한 줄로 합쳐져 구분되지 않습니다.

이 문서는 익명 사용자에게 **사번(empno)과 이름(emp_nm)을 직접 입력받는 화면**을
두어, 약하더라도 귀속 가능한 신원을 확보하는 설계를 기술합니다.

## 2. 목표와 비목표

### 목표

- 익명 사용자를 `/identify` 화면으로 유도해 사번·이름을 입력받습니다.
- 입력된 신원을 `members` 디렉터리로 검증합니다.
- 입력된 신원임을 **데이터에 태깅**하여 인프라가 준 신원과 구분합니다.
- 선언이 이루어진 IP 를 함께 기록합니다.

### 비목표

- **인증(authentication)을 대체하지 않습니다.** 이 계층은 의도적으로 약하며,
  사용자도 이를 인지하고 채택했습니다. 위조 방지가 아니라 귀속(attribution)이
  목적입니다.
- 사용자 계정·비밀번호·세션 관리 체계를 만들지 않습니다.
- `LASTUSER` 쿠키가 있는 경로의 동작은 바꾸지 않습니다.

## 3. 신원 우선순위

`or ANONYMOUS` fallback 을 `CloudIdentityProvider` 에서 **미들웨어로 이동**합니다.
네 단계 체인이 한 곳에 모여야 읽고 검증할 수 있기 때문입니다.

| 순서 | 출처 | `identity_source` | 관리자 가능 |
| --- | --- | --- | --- |
| 1 | `Bearer skn_...` 토큰 | `token` | 가능 |
| 2 | `LASTUSER` / `LAST_USER` 쿠키 | `cookie` | 가능 |
| 3 | 선언 세션 (`/identify`) | `declared` | **불가** |
| 4 | 없음 | `anonymous` | 불가 |

`CloudIdentityProvider.identify()` 는 다시 "쿠키 또는 None" 으로 되돌립니다.
미들웨어가 `g.user_id` 와 `g.identity_source` 를 함께 설정합니다.

## 4. 게이트 위치 — 클라이언트 전용

게이트는 **Nuxt 전역 미들웨어**입니다. Flask 는 익명 요청을 지금처럼 그대로
처리합니다. `curl` 로 API 를 직접 호출하면 게이트를 우회할 수 있습니다.

이렇게 정한 이유는 두 가지입니다.

1. 서버에서 막으려면 `/api/me` 와 `/api/identify` 를 게이트에서 예외
   처리해야 합니다. **예외가 있는 인증 게이트는 이 저장소가 이미 한 번 겪은
   버그 유형**입니다(리다이렉트 루프, `docs/deployment.md` 참조).
2. 서버 응답(리다이렉트)으로 페이지를 유도하는 방식은 인증 게이트가 앱의 첫
   `before_request` 라는 사실 때문에 `index.html` 과 번들까지 막습니다. 이것이
   Phase 3 배포를 빈 화면으로 만든 원인이었습니다.

기존 `app/middleware/afm-hidden.global.ts` 와 같은 형태의 클라이언트 라우팅이
이 저장소의 확립된 패턴이며, CSR SPA(`ssr: false`)에서 올바른 도구입니다.

> **명시적 경계**: 이 게이트는 UX 유도이지 보안 경계가 아닙니다. 보안 경계로
> 남는 것은 **선언 신원은 결코 관리자가 될 수 없다**는 규칙 하나뿐이며, 이는
> 서버에서 강제합니다.

## 5. 저장 방식

Flask 의 **서명된 session 쿠키**를 사용합니다. `app.secret_key` 는 이미
존재합니다(`SKEWNONO_SECRET_KEY`).

```python
session["declared"] = {
    "empno": "2067928",
    "emp_nm": "고대영",
    "verified": True,
    "declared_from": "10.251.122.42",
}
```

| 항목 | 값 |
| --- | --- |
| 유효기간 | 30일 (`PERMANENT_SESSION_LIFETIME`, `session.permanent = True`) |
| 서명 | `SKEWNONO_SECRET_KEY` |
| 해제 | `DELETE /api/identify` ("본인이 아닙니다" 링크) |

서명이 필요한 이유는 `verified` 플래그입니다. 평문 쿠키라면 사용자가 이를
`true` 로 바꿔 검증되지 않은 신원을 검증된 것으로 위장할 수 있습니다.

단, **`declared` 라는 사실 자체는 플래그가 아니라 구조로 보장됩니다** — 신원이
`LASTUSER` 쿠키가 아니라 session 의 `declared` 키에서 왔다는 것은 저장 위치가
다르다는 사실이지 클라이언트가 주장하는 값이 아닙니다.

## 6. 검증 규칙

### 6.1 먼저: `lookup_member()` 로는 검증할 수 없습니다

`lookup_member()` 는 **row 없음**과 **Redis 도달 불가**를 모두 같은 결과(사번만
담은 bare record)로 되돌립니다. 이는 의도된 설계입니다 — 이름은 장식이므로
어떤 실패든 사용자를 막지 않아야 하기 때문입니다.

그러나 검증은 이 둘을 **반드시 구분해야 합니다.** row 가 없으면 거부하고,
Redis 가 죽었으면 수락해야 하는데, 현재 API 로는 어느 쪽인지 알 수 없습니다.

따라서 `_auth/directory.py` 에 결과를 구분해 돌려주는 진입점을 추가합니다.

```python
class Probe(NamedTuple):
    member: Member | None   # found 일 때만 채워집니다
    status: Literal["found", "absent", "unavailable"]

def probe_member(user_id: str) -> Probe: ...
```

| status | 의미 |
| --- | --- |
| `found` | 디렉터리에 row 가 있고 해석되었습니다 |
| `absent` | 디렉터리는 정상이나 해당 사번의 row 가 없습니다 |
| `unavailable` | Redis 미설정·도달 불가·값 해석 실패, 또는 mock 모드 |

`lookup_member()` 는 이 함수를 감싸는 관대한 wrapper 로 재작성합니다. 실패를
삼키는 정책이 한 곳에만 남고, 검증만 원본 결과를 봅니다. 기존 호출자
(`GET /api/me`)의 동작은 바뀌지 않습니다.

### 6.2 비교 규칙

`POST /api/identify` 는 `probe_member(empno)` 로 조회한 뒤 `emp_nm` 을
비교합니다. 비교는 **양끝 공백 제거 후 정확히 일치**해야 합니다. 한글 이름에는
대소문자가 없으므로 대소문자 정규화는 하지 않으며, 공백만 관대하게 봅니다.

| `probe_member` 결과 | 이름 | 처리 |
| --- | --- | --- |
| `found` | 일치 | 수락, `verified: true`, **디렉터리의 이름**을 저장 |
| `found` | 불일치 | `422`, 일반 메시지 |
| `absent` | — | `422`, 동일한 일반 메시지 |
| `unavailable` | — | 수락, `verified: false`, WARN 로그 |

집/mock 모드는 `unavailable` 에 포함되므로 별도 분기가 없습니다. "검증할 수
없으면 통과시킨다"는 규칙 하나로 집과 사무실 장애가 같은 경로를 따릅니다.

디렉터리의 이름을 저장하는 이유는 `dept_nm`, `organ_cd`, `upper_organ_nm` 까지
함께 확보되기 때문입니다. 입력된 이름은 확인용이며 저장 대상이 아닙니다.

row 없음과 이름 불일치에 **같은 메시지**를 쓰는 이유는 응답으로 특정 사번의
존재 여부를 확인할 수 없게 하기 위함입니다.

### 집(mock) 모드가 검증을 건너뛰는 이유와 그 대가

집에서는 Redis 가 없어 `_home_member()` 가 `홍길동(<사번>)` 을 만들어냅니다.
엄격히 비교하면 개발자가 그 문자열을 그대로 입력해야 하므로 검증을
건너뜁니다.

그 대가로 **집에서는 검증 경로가 한 번도 실행되지 않습니다.** `CLAUDE.md` 가
경고하는 mock 사각지대와 같은 형태입니다. 따라서 비교 로직은 라우트 안에 두지
않고 **순수 함수로 분리**하여, 디렉터리 없이도 일치·불일치 양쪽을 직접
단위 테스트합니다.

## 7. 관리자 차단

`is_admin(user_id)` 는 ID 만 받는 순수 함수로 유지합니다. 요청 맥락을 함께 보는
`is_admin_request()` 를 `_auth/admin.py` 에 추가합니다.

```python
_TRUSTED_SOURCES = frozenset({"cookie", "token"})

def is_admin_request() -> bool:
    if getattr(g, "identity_source", None) not in _TRUSTED_SOURCES:
        return False
    return is_admin(getattr(g, "user_id", None))
```

`require_admin` 과 `_deny_if_blocked` 가 모두 이 함수를 사용합니다. 후자까지
바꾸는 이유는, 선언 신원으로 X 로 시작하는 사번을 입력해 접근 제어 차단을
우회하는 경로를 막기 위함입니다.

## 8. IP 기록과 프록시

요청별 IP 는 이미 `_logging/activity.py` 가 `remote_addr` 로 모든 활동 문서에
기록하고 있습니다. 추가 작업은 **선언 시점의 IP 를 선언 신원과 함께 저장**하는
것뿐입니다(`declared_from`). 이를 통해 사번 하나가 여러 IP 에서 선언되거나 한
IP 에서 여러 사번이 선언되는 패턴이 보입니다.

### ProxyFix (이번 작업에 포함)

현재 저장소에 `ProxyFix` 가 없습니다. `wsgi.ini` 는 `http-socket` 직접 노출이므로
`request.remote_addr` 이 실제 클라이언트 IP 입니다. 그러나 같은 파일 20–24행이
Phase 3 에서 nginx 뒤로 옮기는 구성을 안내하고 있으며, **그렇게 바꾸는 순간 모든
요청의 IP 가 `127.0.0.1` 로 기록되고 아무 오류도 나지 않습니다.**

`SKEWNONO_TRUST_PROXY` 환경변수가 참일 때만 `ProxyFix` 를 적용합니다. 조건부여야
하는 이유는, 직접 노출된 상태에서 `X-Forwarded-For` 를 신뢰하면 누구나 헤더를
넣어 자신의 IP 를 위조할 수 있기 때문입니다.

## 9. 구성 요소

### 백엔드

| 파일 | 역할 |
| --- | --- |
| `_auth/self_id.py` (신규) | 선언 신원 읽기/쓰기/해제, session 캡슐화 |
| `_auth/verify.py` (신규) | 이름 비교 순수 함수 (디렉터리 불필요) |
| `_auth/directory.py` | `probe_member()` 추가, `lookup_member()` 를 wrapper 로 |
| `_auth/provider.py` | `or ANONYMOUS` 제거, 쿠키 전용으로 환원 |
| `_auth/middleware.py` | 4단계 체인 소유, `g.identity_source` 설정 |
| `_auth/admin.py` | `is_admin_request()` 추가 |
| `_auth/routes.py` | `GET /api/me` 확장, `POST`/`DELETE /api/identify` |
| `_logging/activity.py` | 로그 문서에 `identity_source` 추가 |
| `__init__.py` | 조건부 `ProxyFix`, 30일 세션 수명 |

### 프런트엔드

| 파일 | 역할 |
| --- | --- |
| `app/middleware/identify.global.ts` (신규) | 익명이면 `/identify` 로 유도 |
| `app/pages/identify.vue` (신규) | 사번·이름 입력 화면 |
| `app/composables/useIdentity.ts` (신규) | `useState` 기반 신원 상태 |

## 10. 데이터 흐름

1. 브라우저 → `GET /` → Flask 가 `index.html` 을 그대로 응답(익명 통과)
2. SPA 부팅 → `useIdentity()` → `GET /api/me`
   → `{ user_id: "anonymous", identity_source: "anonymous" }`
3. 전역 미들웨어가 익명을 감지 → `navigateTo('/identify?next=/sem-list')`
4. 사용자가 사번·이름 입력 → `POST /api/identify`
5. 백엔드: `lookup_member(empno)` → 이름 비교 → session 기록 → 갱신된 me 반환
6. SPA 가 신원 상태를 갱신 → `navigateTo(next)`

## 11. 오류 처리

| 상황 | 응답 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 사번 형식 누락 | `422` | 입력 필드 오류 |
| 검증 실패(없음/불일치) | `422` | "사번 또는 이름이 확인되지 않습니다" |
| 디렉터리 도달 불가 | `200` | 정상 진입 (배지: 미검증) |
| session 서명 불일치 | 익명으로 취급 | `/identify` 재유도 |

## 12. 테스트 전략

### 백엔드 (pytest)

- 신원 우선순위 4단계 전부, 각 단계의 `identity_source`
- **선언 신원은 관리자가 될 수 없음** — `is_cloud()` 양쪽 기본 allowlist 모두에서
- 선언 신원이 X 접두 사번으로 접근 제어를 우회하지 못함
- 검증 5개 행 전부 (순수 함수 + 라우트 양쪽)
- session 왕복, 30일 수명, `DELETE` 해제
- `declared_from` 기록, 활동 로그의 `identity_source`
- `ProxyFix` 가 플래그 없이는 적용되지 않음

### 프런트엔드

`npm test` 는 `node --test` 로 **순수 함수만** 다룹니다(마운팅 하네스 없음).
따라서 입력 검증 헬퍼만 단위 테스트하고, 화면과 미들웨어는 `verify` 스킬에 따라
Playwright MCP 로 수동 확인합니다. 이 한계는 숨기지 않고 기록합니다.

## 13. 위험과 미해결 항목

| 항목 | 영향 | 대응 |
| --- | --- | --- |
| 게이트가 클라이언트 전용 | `curl` 로 우회 가능 | 의도된 수용. 관리자 차단만 서버 강제 |
| 집에서 검증 경로 미실행 | mock 사각지대 | 비교 로직을 순수 함수로 분리해 직접 테스트 |
| `SKEWNONO_SECRET_KEY` 기본값 | 서명 무력화 | 클라우드 배포 시 필수 설정 (`docs/deployment.md`) |
| DHCP 로 IP 변동 | `declared_from` 신뢰도 | 참고 신호로만 사용, 판정 근거로 쓰지 않음 |
| `members` 미등록 인원 | 협력사·서비스 계정 진입 불가 | OFFICE-VERIFY: 실제 미등록 비율 확인 필요 |

마지막 항목이 가장 큰 미확인 위험입니다. `members` 에 없는 인원이 많다면
"row 없음 → 거부" 규칙이 정당한 사용자를 막습니다. 사무실에서 미등록 비율을
확인한 뒤 필요하면 해당 규칙만 완화합니다.
