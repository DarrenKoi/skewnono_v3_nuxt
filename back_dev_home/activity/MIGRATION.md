# activity office 전환

## 현재 구현

`activity` office adapter는 canonical request log를 사내 OpenSearch에서
집계합니다. Redis counter와 별도 `usage_events` index를 사용하지 않습니다.
office 조회 실패 시 mock으로 폴백하지 않으며 route가
`503 activity_query_failed`를 반환합니다.

환경별 source alias는 `SKEWNONO_LOG_ENV`로 선택합니다.

- `local`: `skewnono_logging_local`
- `production`: `skewnono_logging`

두 alias는 같은 사내 cluster에 있고
`back_dev_home/_logging/target.py`가 writer와 reader에 같은 target을
제공합니다. 연결 설정은 `OPENSEARCH_*` 환경변수에서 읽습니다.

## 데이터 의미

활동 집계 대상은 다음 조건을 모두 만족하는 request document입니다.

- `event=request`
- `activity_weight=1`
- `activity_kind`가 `entry` 또는 `feature`입니다.
- 식별된 사람의 `user_id`가 있습니다.

`entry`는 `/api/sem-list` 진입 요청입니다. active user, request 수,
first/last seen에는 포함하지만 top feature와 FAB page 순위에는 포함하지
않습니다. `feature`만 feature 순위와 page count에 포함합니다.

문서 timestamp는 UTC로 저장합니다. 다음 calendar window는
`Asia/Seoul` 기준으로 계산합니다.

- DAU: 오늘 00:00부터 현재까지입니다.
- WAU와 7일 순위: 오늘을 포함한 최근 7 calendar days입니다.
- MAU, 30일 순위, 사용자 목록, FAB 30일 집계: 오늘을 포함한 최근
  30 calendar days입니다.
- 개인 `this_month`: 이번 달 1일 00:00부터 현재까지입니다.
- 개인 daily series: 오늘을 포함한 30개 날짜이며 빈 날짜는 0입니다.

`first_seen`은 alias가 실제로 보존하는 기간 안에서 가장 이른
활동입니다. production은 약 365~372일, local은 약 30~37일 범위이므로
계정의 영구적인 최초 사용일을 의미하지 않습니다.

## Endpoint 계약

### `GET /api/activity/me`

현재 로그인 사용자의 이번 달 request 수, active days, feature 순위,
30일 daily series, retained-window first/last seen을 반환합니다. 알려지지
않은 사용자는 404가 아니라 동일한 shape의 zero response를 반환합니다.
`is_admin`은 `_auth.admin.is_admin()`에서 계산합니다.

### `GET /api/activity/summary`

KST 기준 DAU, 최근 7일 WAU, 최근 30일 MAU와 7일·30일 feature 순위를
반환합니다. active user 수는 `user_id` cardinality로 계산합니다.

### `GET /api/activity/fabs`

최근 7일·30일 FAB별 활동을 반환합니다. `total`은 request 수가 아니라
distinct active user 수입니다. 하나의 request에 여러 FAB가 있으면 각
FAB bucket에 한 번씩 기여합니다. FAB가 없거나 빈 값이면 `"미지정"`으로
정규화합니다. `pages`에는 `feature` document만 포함합니다.

### `GET /api/activity/users`

최근 30일 user composite aggregation을 page 단위로 모두 읽습니다.
`requests_30d`, `days_active_30d`, `last_seen`, feature-only
`favorite_feature`를 반환하고 `(-requests_30d, user_id)`로 정렬합니다.

### `GET /api/activity/users/<user_id>`

개인 history shape를 반환합니다. 조회 결과가 없으면 `404 not_found`,
OpenSearch 조회 실패면 `503 activity_query_failed`를 반환합니다.

## Write path

`back_dev_home/_logging/activity.py`가 request마다 classification과 FAB
정규화를 수행하고 `OpenSearchBulkHandler`가 canonical document 한 건을
저장합니다.

office adapter의 `record_request()`는 의도적인 no-op입니다. provider
adapter에서 다시 쓰면 같은 요청이 두 번 저장되므로 writer를 추가하지
않습니다. mock adapter만 process-local 상태를 갱신합니다.

## Office 연결

회사 network에서 다음 tracked adapter를 복사합니다.

```bash
cp back_dev_home/activity/providers/office_example.py \
  back_dev_home/activity/providers/office.py
```

`.env`에 OpenSearch 연결 설정과 target을 지정합니다.

```dotenv
SKEWNONO_ACTIVITY_PROVIDER=office
SKEWNONO_LOG_ENV=local
OPENSEARCH_HOST=...
OPENSEARCH_PORT=443
OPENSEARCH_USER=...
OPENSEARCH_PASSWORD=...
```

production 배포에서는 같은 cluster 설정을 유지하고
`SKEWNONO_LOG_ENV=production`만 사용합니다.

## 검증

먼저 `ops_index_mgmt/skewnono_logging.py`로 alias를 준비한 뒤 office
provider gate를 실행합니다.

```bash
SKEWNONO_ACTIVITY_PROVIDER=office \
SKEWNONO_LOG_ENV=local \
  .venv/bin/python -m pytest back_dev_home/activity -q
```

그다음 Flask를 실행하여 `/api/activity/me`, `/summary`, `/fabs`,
`/users`를 확인합니다. OpenSearch 연결을 잠시 차단했을 때 raw cluster
오류가 response에 노출되지 않고 `503 activity_query_failed`가 반환되는지도
확인합니다.
