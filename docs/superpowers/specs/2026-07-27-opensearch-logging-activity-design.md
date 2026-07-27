# OpenSearch 제품 활동·운영 로그 설계

- **작성일:** 2026-07-27
- **상태:** 승인된 설계, 구현 계획 작성 전 문서 검토 대기
- **적용 범위:** `ops_index_mgmt`, `ops_store`, `back_dev_home/_logging`,
  `back_dev_home/activity`, `back_dev_home/admin_logs`

## 1. 배경

현재 백엔드는 요청 로그를 구조화하여 출력하고
`OpenSearchBulkHandler`로 OpenSearch에 보낼 수 있습니다. 그러나 현재
구현에는 다음과 같은 차이가 남아 있습니다.

- `ops_index_mgmt/skewnono_logging.py`는 production alias 하나와 30일
  보존 정책만 가정합니다.
- OpenSearch 로그 handler 설치 여부를 `is_cloud()`로 판단하므로 사무실
  localhost에서는 같은 경로를 사용할 수 없습니다.
- `/activity` office adapter는 아직 OpenSearch 집계를 구현하지 않았습니다.
- `/admin/logs`의 OpenSearch 조회가 mock adapter 안에 섞여 있으며,
  자격 증명이 없으면 데모 데이터를 반환합니다.
- 활동 집계용 메모리 기록과 OpenSearch 로그 기록이 동시에 실행되므로,
  office 구현을 단순히 추가하면 같은 요청을 두 번 저장할 위험이 있습니다.
- `query_string`을 그대로 저장하고, `fab_name`의 단일 값·복수 값 의미가
  로그 문서에 고정되어 있지 않습니다.

이 설계는 회사 내부에서만 동작하는 SKEWNONO의 제품 활동 로그와 운영
로그를 같은 사내 OpenSearch cluster에 저장하고, 동일한 문서를
`/activity`와 `/admin/logs`가 서로 다른 목적으로 읽도록 정리합니다.

보존 기간 검토 배경은
[사용자 활동 로그 보존 기간 조사](../../research/2026-07-27-user-activity-log-retention.md)에
정리되어 있습니다. 최종 결정은 production 365일, office localhost
30일입니다.

## 2. 목표

- 제품 활동과 운영 로그를 하나의 canonical document 형식으로 만듭니다.
- office localhost와 production이 같은 cluster와 `ops_store`를 사용하되
  서로의 데이터를 섞지 않습니다.
- `/activity`는 canonical request document를 집계합니다.
- `/admin/logs`는 같은 문서와 예외·애플리케이션 로그를 검색합니다.
- 사용자 요청은 OpenSearch 장애나 지연의 영향을 받지 않습니다.
- 인덱스·template·ISM policy 생성은
  `ops_index_mgmt/skewnono_logging.py`에서만 수행합니다.
- 회사에서 한 번 실행하여 local과 production index family를 준비할 수
  있게 합니다.

## 3. 비목표

- 개인정보처리시스템 접속기록, 보안 감사, 권한 변경 감사 등 법적·규제상
  별도 보존 의무가 있는 audit trail을 구현하지 않습니다.
- 외부 SaaS나 회사 외부 저장소로 로그를 보내지 않습니다.
- 장기 archive, snapshot repository, cold tier를 추가하지 않습니다.
- 요청·응답 body, 인증 header, cookie를 저장하지 않습니다.
- OpenSearch 장애 동안의 완전한 무손실 전달을 보장하는 disk spool을
  추가하지 않습니다.
- 최초 구현에서 명시적인 frontend product-event 수집 endpoint를
  추가하지 않습니다. 활동은 backend request를 분류하여 계산합니다.

향후 공식 audit event가 필요하면 이 로그 family에 섞지 않고 접근 권한과
보존 기간이 다른 별도 family로 설계합니다.

## 4. 결정 요약

| 항목 | 결정 |
| --- | --- |
| cluster | office localhost와 production이 같은 사내 OpenSearch cluster를 사용합니다. |
| 논리 구조 | 환경마다 하나의 logging alias를 사용하며, activity와 operation을 별도 alias로 나누지 않습니다. |
| local alias | `skewnono_logging_local` |
| production alias | `skewnono_logging` |
| local 보존 | rollover 완료 후 최소 30일입니다. |
| production 보존 | rollover 완료 후 최소 365일입니다. |
| 쓰기 | `ops_store.OSDoc.bulk()`만 사용합니다. |
| 읽기 | `ops_store.OSSearch.search_raw()`만 사용합니다. |
| index 관리 | `ops_index_mgmt/skewnono_logging.py`를 회사에서 수동 실행합니다. |
| 시간 | 문서는 UTC로 저장하고 calendar 집계는 `Asia/Seoul`을 사용합니다. |
| 장애 정책 | 요청은 계속 처리하며, 제한된 retry 후 구조화 로그가 유실될 수 있습니다. |

## 5. 전체 구조

```text
Flask request
  └─ request logging middleware
       ├─ 안전한 필드 정규화
       ├─ 활동 분류(entry/feature/background/operation)
       └─ OpenSearchBulkHandler
            └─ ops_store.OSDoc.bulk()
                 ├─ local      → skewnono_logging_local
                 └─ production → skewnono_logging

/api/activity/*
  └─ activity office adapter
       └─ ops_store.OSSearch → 선택된 환경 alias 집계

/api/admin/logs
  └─ admin_logs office adapter
       └─ ops_store.OSSearch → 선택된 환경 alias 검색
```

logging target을 결정하는 작은 interface를 `back_dev_home/_logging`에
둡니다. 호출자는 환경변수나 alias naming 규칙을 직접 알지 않고
`local` 또는 `production`에 대응하는 target만 받습니다. 이 seam 뒤에서
alias, deployment 이름, 활성화 여부를 함께 검증하므로 writer와 두 reader가
서로 다른 alias를 선택하는 drift를 막습니다.

## 6. Index family와 일회성 생성

### 6.1 이름과 정책

| 환경 | Alias | Backing pattern | ISM policy | Template |
| --- | --- | --- | --- | --- |
| local | `skewnono_logging_local` | `skewnono_logging_local-*` | `skewnono_logging_local_retention_policy` | `skewnono_logging_local_template` |
| production | `skewnono_logging` | `skewnono_logging-*` | `skewnono_logging_retention_policy` | `skewnono_logging_template` |

각 family의 첫 backing index는 `<alias>-000001`이며 alias를
`is_write_index: true`로 연결합니다. 두 family는 같은 mapping, shard,
replica, refresh, rollover 설정을 사용하고 보존 기간만 다릅니다.

- primary shard: 2개
- replica: 1개
- refresh interval: 30초
- rollover: 20GB 또는 7일
- local 삭제 전이: `min_rollover_age: 30d`
- production 삭제 전이: `min_rollover_age: 365d`

`min_rollover_age`는 마지막 문서까지 최소 보존 기간을 보장하기 위한
결정입니다. 7일 rollover 때문에 실제 보존은 local 약 30~37일,
production 약 365~372일이 됩니다. 회사 cluster에서 실행하기 전에
설치된 ISM plugin이 `min_rollover_age`를 지원하는지 dry-run과 소규모
검증으로 확인합니다.

### 6.2 실행 interface

생성 코드는 기존 파일인
`ops_index_mgmt/skewnono_logging.py`에만 둡니다. Flask startup, provider,
logging handler는 index, policy, template을 생성하거나 변경하지 않습니다.

명령은 target을 명시하도록 만듭니다.

```bash
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment local \
  --dry-run

.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all
```

`--environment`는 `local`, `production`, `all` 중 하나이며 생략할 수
없습니다. 같은 cluster에서 두 family를 한 번에 준비할 때는 `all`을
사용합니다. 명령은 repo root에서 회사 network와 자격 증명이 준비된
상태로 실행합니다.

script는 다음 순서로 idempotent하게 동작합니다.

1. 환경별 ISM policy를 생성하거나 갱신합니다.
2. 환경별 composable index template을 생성하거나 갱신합니다.
3. alias가 없으면 첫 numbered backing index와 write alias를 만듭니다.
4. alias가 있으면 numbered write index와 rollover 설정을 검증합니다.
5. 기존 backing index에 additive mapping update를 적용합니다.
6. 적용 결과에서 policy, template, alias, write index를 출력합니다.

같은 이름의 standalone index나 잘못 연결된 alias가 있으면 자동 삭제하거나
덮어쓰지 않고 명확히 실패합니다. 자격 증명과 host를 Python 상수에 넣지
않고 `ops_store.create_client()`가 읽는 `OPENSEARCH_*` 환경변수만
사용합니다.

## 7. Runtime 환경 선택

새 환경변수 `SKEWNONO_LOG_ENV`를 사용합니다.

| 실행 위치 | 값 | 선택 alias |
| --- | --- | --- |
| office PC localhost | `local` | `skewnono_logging_local` |
| company production cloud | `production` | `skewnono_logging` |

OpenSearch logging이 활성화되어 있는데 값이 없거나 다른 값이면 시작
과정에서 설정 오류를 명확히 알립니다. path 기반 `is_cloud()` 추론은
사용하지 않습니다. 이렇게 해야 office PC와 production에서 같은 코드를
사용하고 설정만 바꿀 수 있습니다.

관련 설정은 다음과 같습니다.

| 환경변수 | 역할 |
| --- | --- |
| `SKEWNONO_LOG_ENV` | logging alias와 `deployment` 값을 선택합니다. |
| `OPENSEARCH_*` | `ops_store` connection, TLS, timeout, retry 설정입니다. |
| `OPENSEARCH_LOGGING_DISABLED` | 명시적인 write kill switch입니다. |
| `SKEWNONO_ACTIVITY_PROVIDER` | `office`이면 OpenSearch 집계 adapter를 선택합니다. |
| `SKEWNONO_ADMIN_LOGS_PROVIDER` | `office`이면 OpenSearch 검색 adapter를 선택합니다. |

provider 선택과 logging target 선택은 별도 개념입니다. mock test는
`SKEWNONO_*_PROVIDER=mock`으로 외부 연결 없이 동작하고, office localhost와
production은 두 provider를 `office`로 선택하면서 서로 다른
`SKEWNONO_LOG_ENV`를 사용합니다.

## 8. Canonical log document

### 8.1 공통 필드

| 필드 | Mapping | 의미 |
| --- | --- | --- |
| `event_id` | `keyword` | retry에도 중복되지 않는 문서 식별자입니다. |
| `@timestamp` | `date` | UTC ISO-8601 발생 시각입니다. |
| `event` | `keyword` | `request`, `request_exception`, application event 등입니다. |
| `level` | `keyword` | Python logging level입니다. |
| `logger` | `keyword` | logger 이름입니다. |
| `message` | `text` | 사람이 읽는 bounded message입니다. |
| `service` | `keyword` | 고정값 `skewnono`입니다. |
| `deployment` | `keyword` | `local` 또는 `production`입니다. |
| `host` | `keyword` | 실행 host 이름입니다. |
| `request_id` | `keyword` | 요청 correlation ID입니다. |
| `user_id` | `keyword` | 인증된 사용자 ID이며 없으면 필드를 생략합니다. |
| `api_token_id` | `keyword` | token 요청 식별자이며 없으면 필드를 생략합니다. |
| `method` | `keyword` | HTTP method입니다. |
| `path` | `keyword` | query를 제외한 Flask request path입니다. |
| `query_string` | `keyword` | redaction과 길이 제한을 적용한 query입니다. |
| `status` | `integer` | HTTP status입니다. |
| `latency_ms` | `integer` | request 처리 시간입니다. |
| `remote_addr` | `keyword` | 내부 client 또는 proxy 주소입니다. |
| `feature` | `keyword` | 안정적인 page-level feature slug입니다. |
| `activity_kind` | `keyword` | `entry`, `feature`, `background`, `operation` 중 하나입니다. |
| `activity_weight` | `integer` | 활동 집계 대상이면 1, 아니면 0입니다. |
| `fab_name_list` | `keyword` | 요청 context의 정규화된 FAB 이름 목록입니다. |
| `error_code` | `keyword` | HTTP 또는 애플리케이션 오류 코드입니다. |
| `error_name` | `keyword` | bounded 오류 이름입니다. |
| `exception.*` | `keyword`/`text` | type, message, bounded stack입니다. |

OpenSearch에는 별도 array mapping이 없습니다. `fab_name_list`는
`keyword` mapping에 JSON list를 저장합니다.

```json
{
  "fab_name_list": ["M14", "M16"]
}
```

단일 FAB도 `["M14"]`로 저장하고 context가 없으면 빈 list를 사용합니다.
`fab_name`은 기존 DB field와 request parameter의 단일 값 의미를 그대로
유지합니다. 로그에서만 복수형 의미를 명확히 하기 위해
`fab_name_list`를 사용합니다.

root mapping은 `dynamic: false`로 설정하고 query에 사용하는 모든 필드를
명시적으로 mapping합니다. 예상하지 못한 필드가 index field를 계속
만드는 것을 막고, 새 query field는 index-management mapping을 통해
의도적으로 추가합니다.

`event=request` 또는 `event=request_exception`이 아닌 일반 application
log는 `method`, `path`, `status`, `activity_kind`, `activity_weight`,
`fab_name_list` 같은 request 전용 필드를 생략할 수 있습니다.

### 8.2 FAB 정규화

middleware는 임의의 request body나 response를 읽어 FAB를 추론하지
않습니다. 다음 두 입력만 허용합니다.

1. `fab_name` query parameter를 쉼표로 나누고 trim, uppercase, 중복 제거한
   값입니다.
2. JSON body나 route parameter를 이미 검증한 route가 전용 helper를 통해
   request context에 명시적으로 승격한 FAB 값입니다.

예를 들어 `fab_name=M14,m16,M14`는 `["M14", "M16"]`이 됩니다. 여러 FAB가
있는 문서는 각 FAB aggregation bucket에 한 번씩 포함되므로 FAB bucket의
합은 전체 request 수보다 클 수 있습니다.

`/api/sem-list` 응답에 여러 FAB가 있다는 이유로 그 목록 전체를 request의
`fab_name_list`에 복사하지 않습니다. 그 요청 자체에 선택된 FAB context가
없다면 빈 list가 맞습니다.

### 8.3 데이터 최소화

- request·response body를 저장하지 않습니다.
- `Authorization`, cookie와 모든 request header를 저장하지 않습니다.
- query key는 대소문자를 무시하고 검사하며 `password`, `passwd`,
  `token`, `access_token`, `api_key`, `secret`, `authorization`, `cookie`
  계열 값을 `[REDACTED]`로 바꿉니다.
- 정규화된 query string은 최대 2,048자로 제한합니다.
- `message`와 `exception.message`는 각각 4,096자, `error_name`은
  1,024자, `exception.stack`은 32,768자로 제한하여 비정상적으로 큰
  문서를 막습니다.
- logging 변환 실패 시 원본 body나 header를 fallback으로 출력하지
  않습니다.

## 9. 활동 분류

하나의 `activity_weight`만으로는 필수 진입 요청과 실제 기능 사용을
구분할 수 없습니다. 따라서 `activity_kind`와 `activity_weight`를 함께
사용합니다.

| Kind | 의미 | `activity_weight` |
| --- | --- | --- |
| `entry` | 사용자가 제품에 진입할 때 필수로 발생하는 요청입니다. | 인증된 사람의 2xx/3xx이면 1입니다. |
| `feature` | 사용자가 의도적으로 제품 기능을 사용한 요청입니다. | 인증된 사람의 2xx/3xx이면 1입니다. |
| `background` | polling, prefetch, 자동 refresh입니다. | 0입니다. |
| `operation` | health, admin, activity 자체 조회, token 자동화, 비 API traffic입니다. | 0입니다. |

공통 activity policy module이 `user_id`, `api_token_id`, path, status,
feature를 입력으로 받아 두 필드를 결정합니다. middleware, mock recorder,
office reader가 같은 정책 의미를 공유하고 각자 조건을 복사하지 않습니다.

분류 우선순위는 다음과 같이 고정합니다. 먼저 앞 단계에서 결정되면 뒤
단계로 넘어가지 않습니다.

1. 인증되지 않은 요청, API token 요청, 4xx/5xx, `/api/activity`,
   `/api/admin`, `/api/health`, static asset, non-API 요청은
   `operation/0`입니다.
2. 명시적으로 등록된 polling, prefetch, 자동 refresh 요청은
   `background/0`입니다.
3. 명시적으로 등록된 필수 진입 요청은 `entry/1`입니다.
4. 그 밖의 인증된 사람의 성공한 product API 요청은 `feature/1`입니다.

모든 제외 요청도 canonical log document로 남으며 `/admin/logs`에서
조회할 수 있습니다.

### 9.1 장비 리스트 처리

장비 상태 landing page에서 항상 읽는 `/api/sem-list`는 `entry`로
분류합니다. 모든 사용자가 거쳐 가는 요청이므로 제품 진입 증거로는
사용하지만 기능 인기 순위를 높이지 않습니다.

| 지표 | 장비 리스트 포함 여부 |
| --- | --- |
| DAU/WAU/MAU | 포함합니다. |
| 사용자 `first_seen`/`last_seen` | 포함합니다. |
| Top features | 제외합니다. |
| Feature usage count | 제외합니다. |
| FAB active users | FAB context가 있으면 포함합니다. |
| `/admin/logs` | 항상 포함합니다. |

예상 문서는 다음과 같습니다.

```json
{
  "event": "request",
  "feature": "sem_list",
  "activity_kind": "entry",
  "activity_weight": 1,
  "fab_name_list": []
}
```

선택된 FAB나 장비 model로 진입한 뒤 발생하는 page-specific API 요청은
해당 route policy에 따라 `feature`로 분류하고 전달된 FAB context를
`fab_name_list`에 기록합니다.

## 10. 한 번만 쓰는 원칙

request 하나는 `event=request` document 하나만 생성합니다.
`request_exception`은 운영 조사를 위한 별도 event가 될 수 있지만
activity 집계는 `event=request`만 읽으므로 중복 활동으로 계산하지
않습니다.

office mode에서 `activity.record_request()`는 OpenSearch에 다시 쓰지
않습니다. canonical writer는 logging middleware와
`OpenSearchBulkHandler`뿐입니다. mock provider의 in-memory
`record_request()`는 외부 OpenSearch 없이 contract와 UI를 검증하기 위해
유지합니다.

각 문서에 생성한 `event_id`를 OpenSearch `_id`로 사용합니다. 같은 batch를
retry해도 동일 ID가 overwrite되므로 retry가 중복 활동 문서를 만들지
않습니다.

## 11. `/activity` OpenSearch reader

tracked `providers/office_example.py`에 `ops_store.OSSearch` 기반 집계를
구현하고 회사에서 `providers/office.py`로 복사하는 기존 provider
workflow를 따릅니다. mock adapter는 메모리 데이터만 다루고
`is_cloud()` 분기나 OpenSearch fallback을 갖지 않습니다.

모든 calendar interval은 timestamp를 UTC로 저장한 상태에서
`time_zone: Asia/Seoul`을 명시합니다.

### 11.1 공통 활동 filter

사용자 활동 지표의 공통 filter는 다음과 같습니다.

```text
event = request
activity_weight = 1
activity_kind IN (entry, feature)
```

Top feature와 FAB page ranking에는 다음 filter를 추가합니다.

```text
activity_kind = feature
```

### 11.2 Endpoint 의미

| Endpoint | OpenSearch 의미 |
| --- | --- |
| `/activity/me` | 해당 사용자의 이번 달 request/day, 최근 30일 daily, 보존 구간 top features, first/last event를 계산합니다. |
| `/activity/summary` | KST 기준 DAU, trailing 7-day WAU, trailing 30-day MAU와 7/30일 top features를 계산합니다. |
| `/activity/users` | 최근 30일 사용자별 request, active day, last seen, favorite feature를 계산합니다. |
| `/activity/users/<id>` | 선택 사용자의 `/activity/me`와 같은 집계를 반환합니다. |
| `/activity/fabs` | 7/30일 FAB별 distinct active user와 feature page count를 계산합니다. |

`first_seen`은 시스템 lifetime이 아니라 현재 alias에서 보존 중인 문서 중
가장 이른 활동 시각입니다. production에서는 최대 365일 관측값이고
local에서는 최대 30일 관측값입니다. 기존 response field 이름은
유지하되 이 의미를 문서와 UI 도움말에 명시합니다.

`/activity/fabs`의 기존 `total` field는 해당 기간의 distinct active user
수로 정의합니다. `pages`는 `activity_kind=feature`인 요청 수만 집계합니다.
`entry`인 장비 리스트가 FAB active-user 확인에는 기여할 수 있지만 page
ranking을 지배하지 않습니다.

`fab_name_list=[]`인 문서는 FAB 집계의 `미지정` bucket으로 처리합니다.
한 사용자가 여러 FAB context에서 활동하면 각 FAB의 distinct-user
bucket에 포함될 수 있으므로 FAB별 `total`의 합은 전체 active user보다
클 수 있습니다.

## 12. `/admin/logs` OpenSearch reader

OpenSearch query 구현을 mock adapter에서
`admin_logs/providers/office_example.py`로 이동합니다. 회사에서는 기존
workflow대로 `providers/office.py`를 준비합니다.

- 현재 pagination, time range, level, event, method, user, feature, path,
  status, free-text filter contract를 유지합니다.
- 선택된 환경 alias를 logging target interface에서 받습니다.
- request, exception, 일반 application log를 모두 검색할 수 있습니다.
- `activity_kind`, `fab_name_list`, `deployment`, `event_id`는 raw document에
  포함하고 후속 UI filter 확장이 가능하도록 mapping합니다.
- OpenSearch 설정 누락, alias 누락, connection failure는 데모나 빈 결과로
  바꾸지 않고 안정적인 HTTP 503 오류로 반환합니다.
- mock provider는 자동화 test와 명시적 mock mode에서만 deterministic
  demo data를 반환합니다.

frontend는 503을 빈 로그로 보이지 않고 일시적 조회 불가 상태로
표시합니다. `/activity`도 같은 원칙을 따릅니다.

## 13. 비동기 전달과 장애 처리

사용자 request latency와 availability가 log delivery보다 우선합니다.

- request thread는 bounded queue에 `put_nowait()`만 수행합니다.
- 기본 queue 크기는 10,000개, batch 크기는 100개, flush interval은
  5초를 유지합니다.
- worker가 `ops_store.OSDoc.bulk()`를 호출합니다.
- transient transport 또는 retry 가능한 item failure는 전체 3회 시도하며
  retry 간격은 0.5초, 1초입니다.
- `event_id`를 `_id`로 사용하므로 retry는 idempotent합니다.
- retry할 수 없는 item failure는 즉시 실패로 계산합니다.
- 최종 실패한 batch는 request에 예외를 전파하지 않고 drop합니다.
- graceful shutdown은 짧은 제한 시간 안에서 남은 queue를 flush합니다.
- handler 내부 오류는 같은 logger로 다시 기록하지 않고 `stderr`에
  bounded 메시지를 남겨 recursion을 막습니다.

handler는 최소한 다음 진단값을 유지합니다.

- enqueued document 수
- indexed document 수
- queue-full drop 수
- bulk failure와 retry 수
- 마지막 성공 시각과 마지막 실패 시각
- 현재 queue depth

queue drop이나 최종 bulk 실패가 발생하면 매 건이 아니라 제한된 주기로
누적값을 `stderr`에 알립니다. 초기 범위에서는 durable disk spool을
추가하지 않으므로 OpenSearch 장기 장애 시 일부 구조화 로그가 유실될 수
있습니다.

startup은 configured alias에 접근할 수 없는 경우 명확한 경고를 남기되
Flask application을 중단하거나 index를 자동 생성하지 않습니다.
`/activity`와 `/admin/logs` reader는 조회 시 503을 반환합니다.

## 14. Module 책임

| Module | 책임 |
| --- | --- |
| `ops_index_mgmt/skewnono_logging.py` | 두 환경의 policy, template, mapping, alias, 첫 backing index를 수동 생성·검증합니다. |
| `ops_store` | `OSIndex`, `OSDoc`, `OSSearch`, environment client interface를 제공합니다. |
| `back_dev_home/_logging` target module | `SKEWNONO_LOG_ENV`를 검증하고 writer와 reader에 같은 target을 제공합니다. |
| `back_dev_home/_logging` policy module | feature, activity kind, weight, FAB context, redaction을 정규화합니다. |
| `OpenSearchBulkHandler` | canonical document 생성, queue, retry, bulk, 진단값을 소유합니다. |
| activity mock adapter | deterministic in-memory 활동 데이터를 제공합니다. |
| activity office adapter | selected alias를 집계하여 기존 activity contract를 반환합니다. |
| admin_logs mock adapter | deterministic demo log만 제공합니다. |
| admin_logs office adapter | selected alias를 검색하여 기존 admin log contract를 반환합니다. |

각 caller는 `ops_store`의 세부 connection이나 environment별 alias를
복사하지 않습니다. index lifecycle 복잡성은 `ops_index_mgmt`, runtime
target 결정은 logging target module, request 의미는 policy module에
모아 변경 locality를 유지합니다.

## 15. 오류 처리

| 상황 | Writer | Reader |
| --- | --- | --- |
| `SKEWNONO_LOG_ENV` 오류 | 설정 오류를 명확히 알립니다. | 같은 설정 오류를 알립니다. |
| OpenSearch 자격 증명 누락 | handler를 설치하지 않고 경고합니다. | 503을 반환합니다. |
| alias 미생성 | 요청은 계속 처리하고 경고·drop count를 남깁니다. | 503을 반환합니다. |
| 일시적 connection failure | worker에서 제한된 retry 후 drop합니다. | 503을 반환합니다. |
| queue full | 새 document를 drop하고 count를 올립니다. | 영향이 없습니다. |
| mapping reject | 해당 item을 실패 처리하고 field 정보를 bounded stderr로 남깁니다. | 기존 문서는 계속 조회합니다. |
| malformed query | 영향이 없습니다. | 기존 contract대로 400을 반환합니다. |

office/local 또는 production에서 실패를 mock 데이터로 감추지 않습니다.

## 16. 검증

### 16.1 Index-management 단위 검증

- local과 production 이름, pattern, policy ID가 충돌하지 않습니다.
- 두 환경 mapping이 동일합니다.
- local은 30일, production은 365일 `min_rollover_age`를 사용합니다.
- `--environment` 누락과 잘못된 값은 cluster 접속 전에 실패합니다.
- `--dry-run`은 cluster를 변경하지 않고 두 환경의 요청 body를 출력합니다.
- 기존 정상 alias에는 destructive 변경을 하지 않습니다.
- standalone index나 잘못된 alias는 명확히 거부합니다.

### 16.2 Logging 단위 검증

- scalar 또는 comma-separated `fab_name`이 `fab_name_list`로
  정규화됩니다.
- 단일 FAB도 list이며 casing과 중복이 정리됩니다.
- 민감 query 값이 redaction되고 길이가 제한됩니다.
- body, header, cookie는 document에 들어가지 않습니다.
- 장비 리스트는 `entry/1`, top-feature 대상은 `feature/1`이 됩니다.
- token, failure, health, admin, activity, background 요청은 weight 0입니다.
- retry 시 같은 `event_id`와 `_id`를 사용하여 문서가 중복되지 않습니다.
- queue-full, partial bulk failure, retry exhaustion, shutdown flush가 request
  thread에 예외를 전파하지 않습니다.

### 16.3 Provider contract 검증

- mock provider contract test는 OpenSearch 없이 통과합니다.
- fake `OSSearch` response로 activity 모든 endpoint shape를 검증합니다.
- KST day boundary, 7/30일 window, production 보존-window first seen을
  검증합니다.
- `entry`는 DAU에 포함되고 top features에는 포함되지 않습니다.
- multi-FAB 문서는 각 FAB bucket에 한 번 포함됩니다.
- FAB `total`은 distinct user이며 `pages`는 feature request만 셉니다.
- activity와 admin office adapter는 같은 resolved alias를 사용합니다.
- OpenSearch failure는 mock fallback 없이 503으로 정규화됩니다.

### 16.4 Frontend 검증

- `/activity`가 OpenSearch 집계 결과를 기존 contract로 렌더링합니다.
- 장비 리스트가 top feature에 나타나지 않습니다.
- FAB selector가 7/30일 결과를 올바르게 전환합니다.
- `/activity`와 `/admin/logs`의 503이 빈 데이터가 아닌 일시적 오류로
  보입니다.

### 16.5 회사 cluster 수동 검증

1. `--environment all --dry-run` 결과를 검토합니다.
2. `--environment all`을 한 번 실행합니다.
3. 두 policy, template, alias, numbered write index를 확인합니다.
4. office localhost에서 `SKEWNONO_LOG_ENV=local`로 요청을 발생시킵니다.
5. `skewnono_logging_local`에만 문서가 들어가는지 확인합니다.
6. `/activity`와 `/admin/logs`가 같은 local 문서를 읽는지 확인합니다.
7. production에서 `SKEWNONO_LOG_ENV=production`으로 smoke request를
   발생시키고 production alias만 변경되는지 확인합니다.
8. ISM explain 결과에서 rollover alias와 정책 적용 상태를 확인합니다.

실제 cluster에 대한 생성과 smoke check는 회사 network에서만 수행하며
CI나 외부 환경에서는 실행하지 않습니다.

## 17. Rollout

1. index-management builder와 단위 test를 구현합니다.
2. logging target, policy, canonical document, handler를 구현합니다.
3. activity와 admin_logs의 tracked `office_example.py`를 구현하고 mock에서
   OpenSearch·`is_cloud()` 분기를 제거합니다.
4. frontend unavailable state와 field 설명을 맞춥니다.
5. 회사에서 `ops_index_mgmt/skewnono_logging.py --environment all`을
   실행합니다.
6. office localhost에서 local alias로 end-to-end 검증합니다.
7. production에 같은 code와 production target 설정을 배포합니다.

provider workflow상 gitignored `office.py`가 필요한 환경은 배포 전에
tracked `office_example.py`를 복사합니다. index 생성은 그 복사와 별개이며
오직 `ops_index_mgmt` script로 수행합니다.

## 18. 완료 조건

- 같은 사내 cluster에 local과 production logging family가 독립적으로
  존재합니다.
- production 문서는 최소 365일, local 문서는 최소 30일 보존됩니다.
- 한 request가 activity writer와 logging writer에 의해 중복 저장되지
  않습니다.
- `/activity`와 `/admin/logs`가 `ops_store`를 통해 같은 환경 alias를
  읽습니다.
- 장비 리스트는 active-user 지표에는 포함되고 top-feature에는 포함되지
  않습니다.
- `fab_name_list`가 기존 scalar `fab_name`과 혼동 없이 복수 FAB context를
  표현합니다.
- office localhost와 production은 frontend·Flask code 변경 없이
  configuration만 바꾸어 동작합니다.
- OpenSearch 장애가 사용자 request를 실패시키지 않으며, reader는
  fabricated data 대신 명확한 503을 반환합니다.
