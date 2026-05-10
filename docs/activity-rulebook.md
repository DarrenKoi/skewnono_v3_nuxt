# Activity 게이미피케이션 룰북

## 1. 목적

이 문서는 `/activity` 페이지의 점수, 등급, 랭킹 규칙을 설명합니다. 현재 홈/오프라인 단계에서는 Flask 메모리 저장소가 활동을 계산하고, 사무실 단계에서는 OpenSearch 로그와 일별 집계 인덱스로 같은 응답 형태를 만들어야 합니다.

프론트엔드는 이미 `/api/activity/me`와 `/api/activity/leaderboard`만 바라봅니다. 따라서 실제 데이터 소스를 바꾸더라도 이 두 응답 형태는 유지해야 합니다.

## 2. 현재 구현 기준

현재 기준은 `back_dev_home/activity/data.py`의 구현이 source of truth입니다.

| 항목 | 현재 규칙 |
| --- | --- |
| 점수 단위 | 성공한 API 요청 1건 = 1점 |
| 집계 대상 | `path`가 `/api/`로 시작하는 요청 |
| 제외 대상 | `/api/activity/*` 요청, 비 API 경로, 로그인 사용자가 없는 요청 |
| 실패 요청 | HTTP status가 400 이상이면 점수를 주지 않음 |
| 사용자 식별 | `g.user_id` 우선, 없으면 `LASTUSER` cookie, 없으면 `local-dev` |
| feature 계산 | `/api/afm/...`은 `afm`, `/api/health/...`는 `health`처럼 path의 두 번째 segment |
| 최근 활동 | 사용자별 최대 50건 보관 |
| 연속 활동일 | 오늘 활동이 있으면 오늘부터, 없으면 어제부터 연속된 날짜 수 |
| 랭킹 | 전체 점수 내림차순, 동점이면 `user_id` 오름차순 |

현재 모델은 의도적으로 단순합니다. 사용자가 페이지를 탐색하고 기능을 호출할수록 점수가 오릅니다. 데이터 품질, 업무 난이도, 업무 성과는 아직 점수에 반영하지 않습니다.

## 3. 등급 규칙

등급은 누적 점수 기준입니다. 점수는 현재 구현에서 API 성공 요청 수와 같습니다.

| 등급 key | 화면 label | icon | 최소 점수 | 다음 등급 |
| --- | --- | --- | --- | --- |
| `bronze` | `Bronze` | `medal` | 0 | 50 |
| `silver` | `Silver` | `medal` | 50 | 200 |
| `gold` | `Gold` | `trophy` | 200 | 500 |
| `platinum` | `Platinum` | `gem` | 500 | 1500 |
| `diamond` | `Diamond` | `crown` | 1500 | 없음 |

진행률은 현재 등급 안에서 다음 등급까지 얼마나 왔는지 계산합니다.

```text
score_into_tier = score - current.min_score
score_to_next = current.next_score - score
pct = round(score_into_tier * 100 / (current.next_score - current.min_score))
```

`diamond`는 최상위 등급이므로 `score_to_next`가 `null`이고 진행률은 100%입니다.

## 4. 활동으로 인정되는 이벤트

현재는 HTTP 요청 로그를 활동 이벤트로 봅니다. 활동 이벤트는 최소한 다음 필드를 가져야 합니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `timestamp` | date | 요청 완료 시각입니다. UTC 기준 ISO timestamp를 권장합니다. |
| `user_id` | keyword | 사용자 식별자입니다. 사무실에서는 사번, AD 계정, SSO id 중 하나로 고정해야 합니다. |
| `event` | keyword | 요청 로그이면 `request`입니다. |
| `method` | keyword | `GET`, `POST` 같은 HTTP method입니다. |
| `path` | keyword | `/api/...` 요청 경로입니다. query string은 점수 계산에는 필요하지 않습니다. |
| `status` | integer | HTTP status code입니다. 400 이상은 점수 제외입니다. |
| `latency_ms` | integer | 요청 처리 시간입니다. 점수에는 쓰지 않지만 장애 분석에 필요합니다. |
| `feature` | keyword | `afm`, `ebeam`, `health` 같은 기능명입니다. 저장 시점에 넣는 것을 권장합니다. |
| `activity_weight` | integer | 기본값 1입니다. 향후 중요한 행동에 가중치를 줄 때 사용합니다. |

`feature`와 `activity_weight`는 현재 OpenSearch logging handler의 기본 필드는 아니지만, 사무실 전환 시 추가하는 것이 좋습니다. 매 조회 때 path를 script로 파싱하는 방식은 가능하지만 랭킹 페이지의 반복 조회에는 불리합니다.

## 5. 운영용 점수 정책

처음 운영에 붙일 때는 현재 구현과 같은 1요청 1점 정책을 유지하는 것이 안전합니다. 사용자에게 보여주는 등급 체계가 이미 이 전제를 따르고 있고, 데이터 소스 전환과 점수 정책 변경을 동시에 하면 검증이 어려워집니다.

권장 순서는 다음과 같습니다.

1. **V1: 요청 기반 점수**  
   `/api/*` 성공 요청 1건을 1점으로 계산합니다. 현재 UI와 동일합니다.
2. **V2: 활동 타입별 가중치**  
   단순 조회는 1점, 비교/분석 실행은 2점, 저장/공유/다운로드 같은 명시적 결과 생성은 3점처럼 확장합니다.
3. **V3: 품질 제한 추가**  
   짧은 시간 반복 새로고침, 실패 요청, 자동 polling은 점수에서 제외합니다.

V2 이상으로 갈 때도 등급 cutoff는 바로 바꾸지 말고, 2주 이상 실제 점수 분포를 본 뒤 조정해야 합니다.

## 6. OpenSearch 연결 데이터

OpenSearch에는 두 계층을 두는 것을 권장합니다.

| 계층 | 예시 인덱스 | 역할 |
| --- | --- | --- |
| 원본 로그 | `skewnono_logging-*` 또는 `skewnono_activity_raw-*` | 요청 단위 이벤트 저장, 디버깅, 재집계 |
| 일별 집계 | `skewnono_activity_user_daily` | 사용자별 점수, feature별 count, active day, 랭킹 빠른 조회 |

원본 로그만으로도 동작은 가능합니다. 하지만 activity 페이지가 자주 열리고 사용자 수가 늘면 매번 전체 기간의 raw log를 terms aggregation으로 훑는 방식은 부담이 됩니다. 랭킹은 일별 사용자 집계를 읽는 쪽이 안정적입니다.

### 6.1 원본 로그 필터

점수 계산에 들어가는 기본 조건은 다음과 같습니다.

```text
event == "request"
user_id exists
path starts with "/api/"
path does not start with "/api/activity/"
status < 400
```

OpenSearch query에서는 `event`, `user_id`, `status`, `feature`, `@timestamp`가 필터 가능한 필드여야 합니다. `path`는 exact match와 prefix filter가 가능해야 합니다.

### 6.2 일별 집계 문서

일별 집계 문서는 사용자와 날짜 기준으로 하나씩 만드는 것이 좋습니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `activity_date` | date | 집계 날짜입니다. |
| `user_id` | keyword | 사용자 식별자입니다. |
| `score` | integer | 해당 날짜의 점수 합입니다. |
| `request_count` | integer | 점수 대상 요청 수입니다. V1에서는 `score`와 같습니다. |
| `feature_counts` | object | `{"afm": 12, "ebeam": 7}` 같은 feature별 count입니다. |
| `first_seen` | date | 해당 날짜 첫 활동 시각입니다. |
| `last_seen` | date | 해당 날짜 마지막 활동 시각입니다. |
| `updated_at` | date | 집계 문서 갱신 시각입니다. |

이 집계는 배치 작업, cron, Airflow, 또는 OpenSearch transform 중 운영 환경에 맞는 방식으로 만들 수 있습니다.

## 7. API 응답을 만드는 방법

프론트엔드 응답 형태는 `front-dev-home/app/composables/useActivityApi.ts`의 타입과 맞아야 합니다.

### 7.1 `/api/activity/me`

이 endpoint는 현재 사용자의 summary를 반환합니다.

필요한 값은 다음 데이터에서 계산합니다.

| 응답 필드 | 계산 방법 |
| --- | --- |
| `stats.score` | 사용자의 전체 기간 `score` 합 |
| `stats.rank` | 전체 사용자 score 내림차순 순위 |
| `stats.total_users` | 랭킹 집계 대상 사용자 수 |
| `stats.streak_days` | 최근 날짜부터 끊기지 않은 active day 수 |
| `stats.days_active` | 활동한 날짜 수 |
| `stats.favorite_feature` | feature별 count가 가장 큰 feature |
| `stats.by_feature` | 전체 기간 feature별 count |
| `stats.first_seen` | 전체 기간 첫 활동 시각 |
| `stats.last_seen` | 전체 기간 마지막 활동 시각 |
| `tier` | score 기준 등급과 다음 등급 진행률 |
| `recent` | raw log에서 최근 활동 50건 |

`recent`만 raw log를 직접 조회하고, 나머지는 일별 집계에서 계산하는 구조가 좋습니다.

### 7.2 `/api/activity/leaderboard`

이 endpoint는 상위 사용자 목록과, 현재 사용자가 top 안에 없을 때 현재 사용자 row를 반환합니다.

권장 계산 방식은 다음과 같습니다.

1. `skewnono_activity_user_daily`에서 사용자별 전체 score를 sum합니다.
2. score 내림차순, `user_id` 오름차순으로 정렬합니다.
3. `top` query parameter는 1에서 50 사이로 제한합니다.
4. 각 row에 `rank`, `user_id`, `score`, `tier`, `streak_days`, `is_me`를 채웁니다.

## 8. OpenSearch 속도 판단

OpenSearch는 이 용도에 충분히 빠르게 만들 수 있습니다. 조건은 매 페이지 요청마다 큰 raw log 전체를 직접 랭킹하지 않는 것입니다.

권장 기준은 다음과 같습니다.

| 조회 | 권장 소스 | 이유 |
| --- | --- | --- |
| 내 점수, 등급, feature breakdown | 일별 집계 | 사용자 1명의 여러 날짜만 읽으면 됩니다. |
| 리더보드 Top N | 일별 집계 | 사용자별 sum aggregation만 필요합니다. |
| 최근 활동 20-50건 | 원본 로그 | timestamp desc 정렬로 작은 범위만 읽습니다. |
| 장애/감사 분석 | 원본 로그 | 정확한 request 단위 기록이 필요합니다. |

운영에서 확인할 성능 목표는 다음과 같습니다.

| 항목 | 목표 |
| --- | --- |
| `/api/activity/me` | p95 300ms 이하 |
| `/api/activity/leaderboard` | p95 500ms 이하 |
| raw log bulk indexing | 요청 path를 block하지 않음 |
| 집계 갱신 지연 | 실시간성이 필요 없으면 1-5분 이내, 일일 snapshot이면 하루 1회 |

현재 `back_dev_home/_logging/opensearch_handler.py`는 큐에 넣고 background thread가 bulk로 밀어 넣는 구조입니다. 이 방향은 맞습니다. 요청 처리 thread가 OpenSearch 장애 때문에 느려지면 activity 기능이 전체 앱 성능을 망칠 수 있으므로, 로그 적재 실패는 사용자 요청 실패로 전파하지 않는 원칙을 유지해야 합니다.

## 9. 구현 체크리스트

사무실 데이터 연결 시 다음 순서로 진행합니다.

1. `skewnono.activity` 로그가 `user_id`, `method`, `path`, `status`, `latency_ms`를 OpenSearch에 쓰는지 확인합니다.
2. 가능하면 `feature`, `activity_weight`를 로그 extra field에 추가합니다.
3. raw log mapping에서 `user_id`, `event`, `method`, `path`, `feature`는 `keyword`로 둡니다.
4. status와 latency는 numeric type으로 둡니다.
5. 일별 집계 인덱스 `skewnono_activity_user_daily`를 만듭니다.
6. `back_dev_home/activity/data.py`와 같은 함수 이름, 같은 TypedDict shape를 유지한 office용 `data.py`를 작성합니다.
7. `/api/activity/me`, `/api/activity/leaderboard?top=10`을 현재 프론트엔드 타입과 비교합니다.
8. 점수 분포를 2주 정도 본 뒤 V2 가중치 정책 적용 여부를 결정합니다.

## 10. 주의할 점

- activity 페이지 자체 조회는 점수에서 제외해야 합니다. 그렇지 않으면 랭킹을 확인하는 행동만으로 점수가 오릅니다.
- 자동 polling, health check, background refresh는 사용자 활동이 아니므로 별도 제외 규칙을 두는 것이 좋습니다.
- 사용자 식별자가 바뀌면 과거 점수가 분리됩니다. 사무실에서는 `user_id` 기준을 먼저 고정해야 합니다.
- 등급 기준은 화면의 동기부여 장치입니다. 업무 성과 평가처럼 보이지 않도록 문구와 사용 범위를 제한해야 합니다.
- OpenSearch query가 느리면 등급 cutoff를 바꾸는 것이 아니라 raw log 조회를 줄이고 일별 집계를 강화해야 합니다.
