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

**쿠키 읽기를 provider 에서 미들웨어로 올립니다.** 체인이 한 곳에 모여야 읽고
검증할 수 있기 때문입니다. provider 에는 **"쿠키가 없을 때 그것이 무엇을
의미하는가"** 라는 단계별 판단만 남습니다 — `provider.py` 의 docstring 이 이미
그것을 유일한 보안 경계로 규정하고 있습니다.

| 순서 | 출처 | `identity_source` | 관리자 가능 |
| --- | --- | --- | --- |
| 1 | `Bearer skn_...` 토큰 | `token` | 가능 |
| 2 | `LASTUSER` / `LAST_USER` 쿠키 | `cookie` | 가능 |
| 3 | 선언 세션 (`/identify`) | `declared` | **불가** |
| 4 | 단계별 fallback — 집: `local-dev` | `local` | 가능 |
| 4 | 단계별 fallback — 클라우드: `anonymous` | `anonymous` | 불가 |

4번은 한 자리이며, 어느 값이 나오는지는 어느 provider 가 설치되었는지로만
갈립니다. `local` 은 `LocalIdentityProvider` 만 만들 수 있고 이 provider 는
`is_cloud()` 가 거짓일 때만 설치되므로, 클라우드에서 `local` 이 나타나는 경로는
존재하지 않습니다.

### 왜 `local` 이 별도의 출처여야 하는가

집 provider 는 쿠키가 없을 때 `local-dev` 를 돌려주며, 이 값은 **관리자
ID**입니다(`_auth/admin.py` 의 `_HOME_DEFAULT_ADMINS`). 그런데 provider 가
문자열 하나만 돌려주면 미들웨어는 그 값이 쿠키에서 왔는지 fallback 에서 왔는지
구분할 수 없습니다 — `_cookie_identity()` 가 provider 내부 함수이기 때문입니다.

구분하지 못한 채로 §7 의 신뢰 목록을 적용하면 둘 중 하나가 됩니다.

- `cookie` 로 이름 붙인다 → 집은 동작하지만 **`identity_source` 가 거짓말을
  합니다.** 이 필드의 존재 이유가 출처 구분이므로 자기모순입니다.
- 신뢰하지 않는다 → **집의 모든 개발자가 관리자 화면을 잃습니다.**

그래서 쿠키 읽기를 미들웨어로 올리고, fallback 에만 단계별 이름을 붙입니다.
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

Flask 의 **서명된 session 쿠키**를 사용합니다. `app.secret_key` 는 대입되어
있으나 **실제 키는 아직 없습니다** — 이 작업에서 함께 고칩니다(§5.1).

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

### 5.1 `SKEWNONO_SECRET_KEY` 를 필수로 승격합니다

현재 코드는 기본값을 갖습니다.

```python
# back_dev_home/__init__.py:126
app.secret_key = os.environ.get("SKEWNONO_SECRET_KEY", "dev-only-not-for-prod")
```

그리고 이 환경변수는 `.env` 에 **존재하지 않습니다**(2026-07-29 확인). 즉 지금
배포하면 클라우드가 **저장소에 공개된 상수**로 session 에 서명하며, 아무 경고도
나지 않습니다. `verified` 플래그의 근거가 바로 이 서명이므로, 그 상태의 서명은
서명이 아닙니다.

따라서 `is_cloud()` 가 참인데 `SKEWNONO_SECRET_KEY` 가 없으면 **기동을
거부합니다.** 집과 사무실 localhost 는 기본값을 그대로 유지합니다 — 그쪽에서는
편의가 목적이고 위조할 대상도 없기 때문입니다.

조용한 위조 가능 상태를 기동 오류로 바꾸는 교환이며, 실패는 배포 시점에 한 번
드러납니다. 번들의 `preflight.py` 가 이미 같은 항목을 검사하므로 진단 경로도
이미 존재합니다.

> **덧붙임**: 기본 키로 서명이 무력화되어도 **관리자 승격은 일어나지
> 않습니다.** §7 이 신뢰하는 출처는 `token`·`cookie`·`local` 이고, 위조된
> session 은 정의상 `declared` 이기 때문입니다. 위조로 얻을 수 있는 것은 잘못된
> 귀속뿐이며, 이는 §5 가 의도한 구조가 실제로 버티고 있다는 뜻입니다. 그렇다고
> 기본값을 남겨둘 이유는 되지 않습니다.

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
| `absent` | — | 수락, `verified: false`, INFO 로그 |
| `unavailable` | — | 수락, `verified: false`, WARN 로그 |

거부는 **오직 한 칸**입니다 — 디렉터리가 그 사람을 알고 있는데 이름이 다를 때.
나머지 실패는 모두 "검증할 수 없음"으로 취급해 통과시킵니다.

디렉터리의 이름을 저장하는 이유는 `dept_nm`, `organ_cd`, `upper_organ_nm` 까지
함께 확보되기 때문입니다. 입력된 이름은 확인용이며 저장 대상이 아닙니다.

### `absent` 를 거부하지 않는 이유

이전 판은 `absent` 를 `422` 로 거부했습니다. 이는 `members` 에 없는 사람을
**완전히 차단**하는 규칙인데, 코드가 이미 그 인원의 존재를 단정하고 있습니다.

```python
# _auth/directory.py:161-165
# A real, ordinary outcome: contractors and service accounts hold a
# LASTUSER cookie without a directory row.
```

디렉터리 미등록이 "정상적이고 흔한 결과"라면, 그것을 근거로 한 차단은 미등록
비율이 낮다는 것이 확인되기 전까지는 정당화되지 않습니다. 확인은 사무실에서만
가능하고(§13), 그 사이에 이 규칙은 협력사·서비스 계정을 막습니다.

따라서 **기본값을 안전한 쪽으로 둡니다** — 통과시키되 `verified: false` 로
표시합니다. 귀속이 목적이고 인증이 목적이 아니므로(§2), 미검증 신원도 익명보다
낫습니다. 사무실에서 미등록 비율이 무시할 수준으로 확인되면 그때 조이는 것이
순서이며, 그 반대는 되돌릴 수 없습니다.

INFO 와 WARN 을 나눈 이유는 `absent` 는 예상된 결과이고 `unavailable` 은
인프라 이상이기 때문입니다. 같은 처리를 하되 같은 사건은 아닙니다.

### 대가: 사번 존재 여부가 드러납니다

이전 판이 두 실패에 같은 메시지를 쓴 이유는 응답으로 특정 사번의 디렉터리 등재
여부를 알 수 없게 하려는 것이었습니다. `absent` 를 통과시키면 그 구분이
관찰됩니다 — 아무 이름이나 넣었을 때 `422` 면 등재된 사번, `200` 이면 미등재
사번입니다.

이를 수용하는 이유는 세 가지입니다. 이 계층은 인증이 아니며(§2), 내부망 전용
사설 클라우드이고, 드러나는 사실은 사번의 **존재**가 아니라 사내 디렉터리
**등재 여부**입니다. 다만 조용히 잃는 성질이 아니므로 §13 에 위험으로
기록합니다.

### 집(mock) 모드의 위치

집에서는 Redis 가 없어 `_home_member()` 가 `홍길동(<사번>)` 이라는 **채워진**
row 를 만들어냅니다. 결과만 보면 `found` 와 구분되지 않으므로, `probe_member()`
는 조회 **이전에** `get_mode()` 로 분기해 `unavailable` 을 돌려주어야 합니다.
비교 규칙 표에는 집을 위한 행이 없지만, 구현에는 분기가 필요합니다.

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
# `local` 은 집 provider 의 `local-dev` fallback 이며, 이 provider 는
# is_cloud() 가 거짓일 때만 설치됩니다 — 클라우드에서는 나올 수 없는 값입니다.
_TRUSTED_SOURCES = frozenset({"cookie", "token", "local"})

def is_admin_request() -> bool:
    if getattr(g, "identity_source", None) not in _TRUSTED_SOURCES:
        return False
    return is_admin(getattr(g, "user_id", None))
```

신뢰 목록은 **화이트리스트**입니다. 새 출처를 추가하면 기본적으로 관리자가 될
수 없으며, 되게 하려면 이 집합에 명시적으로 넣어야 합니다. `declared` 와
`anonymous` 가 빠진 것이 이 설계의 유일한 서버측 보안 경계입니다(§4).

`local` 을 포함하는 이유는 집 provider 의 fallback 이 관리자 ID 이기
때문입니다(§3). 이것이 빠지면 집에서 관리자 화면이 통째로 사라지며, 증상은
"권한 없음"이라 원인이 신원 출처 이름에 있다는 것을 알아내기 어렵습니다.

`require_admin` 과 `_deny_if_blocked`(`_auth/middleware.py:36`)가 모두 이 함수를
사용합니다. 후자까지 바꾸는 이유는, 선언 신원으로 X 로 시작하는 사번을 입력해
접근 제어 차단을 우회하는 경로를 막기 위함입니다.

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
| `_auth/provider.py` | 쿠키 읽기를 넘기고 **fallback 판단만** 남김 (`local` / `anonymous`) |
| `_auth/middleware.py` | 쿠키 읽기 + 4단계 체인 소유, `g.identity_source` 설정 |
| `_auth/admin.py` | `is_admin_request()` 추가, `local` 을 신뢰 목록에 포함 |
| `_auth/routes.py` | `GET /api/me` 확장, `POST`/`DELETE /api/identify` |
| `_logging/activity.py` | 로그 문서에 `identity_source` 추가 |
| `__init__.py` | 조건부 `ProxyFix`, 30일 세션 수명, **클라우드 secret key 강제**(§5.1) |

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
5. 백엔드: `probe_member(empno)` → 이름 비교(§6.2) → session 기록 → 갱신된 me 반환
6. SPA 가 신원 상태를 갱신 → `navigateTo(next)`

> 5번은 반드시 `probe_member()` 여야 합니다. `lookup_member()` 는 §6.1 이
> 설명하듯 "row 없음"과 "Redis 도달 불가"를 같은 값으로 뭉개므로 검증에 쓸 수
> 없으며, 그것으로 구현하면 검증이 조용히 무의미해집니다.

## 11. 오류 처리

| 상황 | 응답 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 사번 형식 누락 | `422` | 입력 필드 오류 |
| 이름 불일치 (`found`) | `422` | "사번 또는 이름이 확인되지 않습니다" |
| 디렉터리 미등재 (`absent`) | `200` | 정상 진입 (배지: 미검증) |
| 디렉터리 도달 불가 (`unavailable`) | `200` | 정상 진입 (배지: 미검증) |
| session 서명 불일치 | 익명으로 취급 | `/identify` 재유도 |

## 12. 테스트 전략

### 백엔드 (pytest)

- 신원 우선순위 4단계 전부, 각 단계의 `identity_source`
- **선언 신원은 관리자가 될 수 없음** — `is_cloud()` 양쪽 기본 allowlist 모두에서
- 선언 신원이 X 접두 사번으로 접근 제어를 우회하지 못함
- **집 fallback(`local`)이 관리자 자격을 유지함** — 이 작업이 새로 만드는 회귀
  경로이므로(§3) 테스트로 못을 박습니다
- 쿠키로 온 신원이 `cookie` 로, fallback 이 `local` 로 이름 붙음 (서로 구분됨)
- 검증 4개 행 전부 (순수 함수 + 라우트 양쪽)
- **`absent` 가 거부가 아니라 `verified: false` 통과임** (§6.2)
- session 왕복, 30일 수명, `DELETE` 해제
- `declared_from` 기록, 활동 로그의 `identity_source`
- `ProxyFix` 가 플래그 없이는 적용되지 않음
- **`is_cloud()` 에서 `SKEWNONO_SECRET_KEY` 가 없으면 기동이 실패함**, 그리고
  집에서는 없어도 기동함 (§5.1)

### 프런트엔드

`npm test` 는 `node --test` 로 **순수 함수만** 다룹니다(마운팅 하네스 없음).
따라서 입력 검증 헬퍼만 단위 테스트하고, 화면과 미들웨어는 `verify` 스킬에 따라
Playwright MCP 로 수동 확인합니다. 이 한계는 숨기지 않고 기록합니다.

## 13. 위험과 미해결 항목

| 항목 | 영향 | 대응 |
| --- | --- | --- |
| 게이트가 클라이언트 전용 | `curl` 로 우회 가능 | 의도된 수용. 관리자 차단만 서버 강제 |
| 집에서 검증 경로 미실행 | mock 사각지대 | 비교 로직을 순수 함수로 분리해 직접 테스트 |
| `SKEWNONO_SECRET_KEY` 기본값 | 서명 무력화 | **해소** — 클라우드 기동 시 필수로 승격(§5.1) |
| DHCP 로 IP 변동 | `declared_from` 신뢰도 | 참고 신호로만 사용, 판정 근거로 쓰지 않음 |
| 사번 등재 여부가 응답으로 관찰됨 | 디렉터리 열거 | 수용(§6.2). 인증 계층이 아니고 내부망 전용 |
| `members` 미등록 인원 | 미검증 신원 비율 상승 | OFFICE-VERIFY: 실제 미등록 비율 확인 |

`members` 항목은 이번 개정으로 **성격이 바뀌었습니다.** 이전 판에서는 미등록
인원이 앱에 아예 들어오지 못하는 가용성 위험이었으나, `absent` 를 통과시키기로
하면서(§6.2) 이제는 "미검증 신원이 얼마나 되는가"라는 **데이터 품질** 문제로
내려왔습니다. 사무실에서 비율을 확인하는 일은 여전히 필요하지만, 더 이상 배포를
막는 선행 조건은 아닙니다.

남은 가장 큰 미확인 항목은 열거 위험이며, 이는 확인이 아니라 **선택**입니다 —
등재 여부를 감추려면 이름 불일치도 통과시켜야 하고, 그러면 §6 의 검증 자체가
사라집니다. 귀속이 목적인 계층에서는 검증을 남기는 쪽이 맞다고 판단했습니다.
