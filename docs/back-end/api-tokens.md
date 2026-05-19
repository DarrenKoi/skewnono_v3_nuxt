# API와 토큰의 관계

SKEWNONO의 모든 데이터는 `/api/*` 엔드포인트를 통해 노출됩니다. 이 문서는 그 엔드포인트가 **누가 호출했는지**를 어떻게 식별하고, **API 토큰**이 그 식별 흐름에 어떻게 끼어드는지 설명합니다.

## 1. 한눈에 보기

```text
   ┌──────────────────────┐
   │ 브라우저 (사람)       │──── 쿠키 ─────┐
   └──────────────────────┘              │
                                          ▼
   ┌──────────────────────┐    ┌────────────────────────┐
   │ 스크립트/내부 서비스  │── Authorization: Bearer ──▶│ Flask before_request   │
   └──────────────────────┘                            │ (_auth/middleware.py)  │
                                                      └─────────┬──────────────┘
                                                                ▼
                                                ┌───────────────────────────┐
                                                │ g.user_id 설정             │
                                                │ g.api_token_id (토큰일 때)│
                                                └───────────────┬───────────┘
                                                                ▼
                                                ┌───────────────────────────┐
                                                │ 라우트 핸들러 실행          │
                                                │ (피처별 routes.py)         │
                                                └───────────────┬───────────┘
                                                                ▼
                                                ┌───────────────────────────┐
                                                │ after_request 로깅          │
                                                │ (_logging/activity.py)      │
                                                │ → OpenSearch `skewnono_logging`│
                                                └───────────────────────────┘
```

핵심은 **하나의 식별자 `g.user_id`로 모든 다운스트림 코드가 작동한다**는 점입니다. 토큰 인증은 그 식별자를 어떻게 채우느냐의 다른 경로일 뿐, 다운스트림 라우트는 호출이 사람에게서 왔는지 스크립트에서 왔는지 신경 쓰지 않습니다.

## 2. 두 가지 인증 경로

`_auth/middleware.py`의 `_attach_identity` 훅이 매 요청마다 다음 순서로 신원을 결정합니다.

| 순서 | 조건 | 결과 |
| --- | --- | --- |
| 1 | 경로가 `/login`, `/static/*` | 공개 경로 — 인증 생략 |
| 2 | `/api/*` 요청 + `Authorization: Bearer skn_...` 헤더 | 토큰 조회 → 일치하면 `g.user_id = 소유자`, `g.api_token_id = 토큰 ID` |
| 3 | 그 외 (SSO 쿠키 등) | `IdentityProvider.identify()` → `g.user_id` 설정 |
| 4 | 위 모두 실패 + `/api/*` | 401 응답 |
| 5 | 위 모두 실패 + 그 외 경로 | SSO 로그인으로 리다이렉트 |

순서가 중요합니다. 토큰 경로(2)가 SSO 경로(3)보다 **먼저** 시도되므로, 같은 사용자가 브라우저에서 로그인되어 있어도 `Authorization` 헤더가 붙은 호출은 토큰 경로로 식별됩니다.

토큰이 형식상 존재하지만 폐기되었거나 위조된 경우(2번 경로에서 매치 실패) 미들웨어는 **즉시 401을 반환하고 SSO로 떨어지지 않습니다**. 머신 호출자가 302 리다이렉트 루프에 빠지지 않도록 하기 위함입니다.

## 3. 토큰의 수명 주기

토큰 자체는 `back_dev_home/api_tokens/` 피처가 관리합니다. 다른 피처와 동일한 슬라이스 패턴(`routes.py` + `data.py`)을 따릅니다.

| 단계 | 엔드포인트 | 누가 호출 가능 |
| --- | --- | --- |
| 발급 | `POST /api/account/api-tokens` | 사람 세션만 (SSO 쿠키) |
| 목록 조회 | `GET /api/account/api-tokens` | 사람 세션 + 토큰 세션 모두 |
| 폐기 | `DELETE /api/account/api-tokens/<id>` | 사람 세션만 |

발급과 폐기를 **토큰 인증 세션에서 금지**한 이유는 명확합니다. 유출된 토큰 하나가 같은 사용자의 다른 토큰을 폐기하거나 새 토큰을 발급해 영구화하는 것을 막아야 합니다. 사람이 직접 로그인한 세션만 토큰 관리 권한을 가집니다.

### 3.1 발급 시 한 번만 보이는 평문

`POST /api/account/api-tokens` 응답에는 다음이 포함됩니다.

```json
{
  "token": {
    "id": "abc123def456",
    "label": "야간 백업 스크립트",
    "created_at": "2026-05-18T07:49:01+00:00",
    "last_used_at": null
  },
  "plaintext": "skn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

`plaintext`는 **이 응답이 유일한 표시 기회**입니다. 서버는 SHA-256 해시만 저장하므로 분실하면 복구할 수 없고 폐기 후 재발급해야 합니다. GitHub PAT, Stripe API 키와 동일한 패턴입니다.

### 3.2 토큰 형식

| 항목 | 값 |
| --- | --- |
| 접두사 | `skn_` |
| 본문 | `secrets.token_urlsafe(32)` (32바이트 무작위, base64url 인코딩) |
| 전체 길이 | 47자 |
| 저장 형태 | SHA-256 해시(64자 hex) + 메타데이터 |

접두사 `skn_`은 로그/소스 코드에서 누출된 토큰을 grep으로 빠르게 찾을 수 있도록 의도된 표식입니다.

## 4. 로깅과 분석

`_logging/activity.py`의 `after_request` 훅이 모든 요청에 대해 구조화된 로그 한 줄을 발행합니다. 사무실(Phase 3)에서는 `_logging/opensearch_handler.py`가 그 로그를 OpenSearch `skewnono_logging` 인덱스로 비동기 배치 전송합니다.

토큰 인증 요청은 로그 문서에 **추가 필드 `api_token_id`** 를 갖습니다. 이 필드가 분석의 핵심 축입니다.

| 필드 | 사람 세션 | 토큰 세션 |
| --- | --- | --- |
| `user_id` | SSO 식별자 | 토큰 소유자 ID |
| `api_token_id` | `null` | 토큰 ID |
| `feature` | `route_to_feature(path)` (공통, `_logging/feature_map.py`) | 동일 |
| `latency_ms` | 측정값 (공통) | 동일 |
| `activity_weight` | 1 (조건 충족 시) | **항상 0** |

`activity_weight`가 0이라는 것은 토큰 호출이 사용자 활동 점수에 **반영되지 않는다**는 뜻입니다. 즉, 야간 배치 스크립트가 점수판을 점령하는 사태는 발생하지 않습니다. 그러나 OpenSearch 로그에는 그대로 남으므로, 사용자는 "내 스크립트가 어떤 엔드포인트를 얼마나 자주 호출했는가"를 `api_token_id` 또는 `user_id` 기준으로 자유롭게 질의할 수 있습니다.

### 4.1 분석 질의 예시

```text
# 특정 토큰이 최근 24시간 동안 호출한 엔드포인트와 호출 수
SELECT feature, COUNT(*)
FROM skewnono_logging
WHERE api_token_id = 'abc123def456'
  AND @timestamp > now() - 24h
GROUP BY feature

# 특정 사용자의 모든 토큰 호출(여러 토큰을 한 사용자가 발급한 경우)
SELECT api_token_id, COUNT(*)
FROM skewnono_logging
WHERE user_id = 'kim.minju'
  AND api_token_id IS NOT NULL
GROUP BY api_token_id
```

## 5. 토큰이 부여하는 권한 범위

토큰은 **소유자의 권한을 그대로 빌려옵니다**. 새로운 권한 모델이나 스코프 체계는 없습니다.

```text
사용자 kim.minju가 SSO로 호출 가능한 엔드포인트 == kim.minju가 발급한 토큰으로 호출 가능한 엔드포인트
```

이로 인한 함의:

- 모든 `/api/*` 읽기 엔드포인트(`/api/sem-list`, `/api/afm/...`, `/api/ebeam/...` 등)가 토큰으로 호출 가능합니다.
- 향후 추가되는 엔드포인트는 별도 조치 없이 자동으로 토큰 호출 가능 영역에 들어옵니다. 이를 원하지 않는 엔드포인트(내부 전용)는 **명시적으로** 토큰 거부를 표시해야 합니다.
- 토큰 자체는 권한을 **확대하지 않습니다**. 사용자가 가진 권한 이상의 동작은 토큰으로도 불가능합니다.

## 6. 댁(Home) ↔ 사무실(Office) 스왑 시 유지해야 할 계약

`api_tokens` 피처도 다른 피처와 동일한 스왑 원칙을 따릅니다. `routes.py`는 손대지 않고 `data.py`만 OpenSearch/DB 백엔드로 교체합니다.

`api_tokens/data.py`가 제공해야 하는 인터페이스:

| 함수 | 입력 | 출력 | 비고 |
| --- | --- | --- | --- |
| `create_token(owner_user_id, label)` | 소유자 ID, 라벨 | `(공개뷰, 평문)` | 평문은 함수 호출자만 본다 |
| `list_tokens(owner_user_id)` | 소유자 ID | `[공개뷰, ...]` | 소유자별 인덱스 권장 |
| `revoke_token(owner_user_id, token_id)` | 소유자 ID, 토큰 ID | `bool` | 다른 소유자의 토큰은 폐기 불가 |
| `find_by_plaintext(plaintext)` | 평문 토큰 | `Optional[Row]` | 해시 룩업, 핫패스 |
| `touch_last_used(token_id)` | 토큰 ID | `None` | 60초 디바운스 권장 |

### 6.1 사무실 구현 시 주의 사항

- **해시 기반 조회가 핫패스**입니다. `find_by_plaintext`는 매 요청마다 호출되므로 `sha256(plaintext)` → `token_id` 매핑은 캐시되거나 인덱스로 잡혀야 합니다.
- **`touch_last_used`는 디바운스됩니다.** 모의 구현은 60초 안에 들어온 동일 토큰의 갱신을 무시합니다. 사무실 구현도 같은 정책을 따라야 OpenSearch/DB에 초당 수십 건의 쓰기가 발생하지 않습니다.
- **저장 시 평문은 절대 보관하지 않습니다.** 컬럼/필드는 `hash`(sha256 hex)만 가집니다.
- **소유자 ID 인덱스 필수.** `list_tokens`는 사용자의 설정 페이지에서 매번 호출되므로 전체 스캔이면 안 됩니다.

## 7. 보안 고려 사항

| 위협 | 완화책 |
| --- | --- |
| 토큰 유출 → 데이터 노출 | 사용자가 설정 페이지에서 즉시 폐기 가능. 모든 호출이 OpenSearch에 기록되므로 사후 추적 가능 |
| 토큰 유출 → 다른 토큰 폐기/발급 | 토큰 세션은 `/api/account/api-tokens` POST/DELETE 불가 (403) |
| 평문 토큰 DB 노출 | SHA-256 해시만 저장 — DB 덤프로 토큰을 복원 불가능 |
| 무차별 대입 | 256비트 무작위 시드 — 실질적으로 불가능 |
| 로그/소스에 토큰 누출 | `skn_` 접두사로 grep 가능. 정기 감사 권장 |
| 머신 호출자에 대한 SSO 리다이렉트 루프 | 토큰 부적합 시 미들웨어가 401만 반환, 302 리다이렉트 차단 |

## 8. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `back_dev_home/api_tokens/data.py` | 토큰 저장소(모의: 인메모리) |
| `back_dev_home/api_tokens/routes.py` | `/api/account/api-tokens` CRUD |
| `back_dev_home/_auth/middleware.py` | 토큰 ↔ SSO 인증 분기 |
| `back_dev_home/_logging/activity.py` | `api_token_id` 로그 필드 + 활동 점수 제외 |
| `back_dev_home/_logging/opensearch_handler.py` | `api_token_id` OpenSearch 승격 필드 |
| `front-dev-home/app/composables/useApiTokens.ts` | 설정 페이지용 CRUD 컴포저블 |
| `front-dev-home/app/components/settings/ApiTokens.vue` | 토큰 관리 UI |
| `front-dev-home/app/pages/settings.vue` | `<SettingsApiTokens />` 마운트 지점 |
