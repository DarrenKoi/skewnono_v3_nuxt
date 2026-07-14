# Phase 2 사무실 데이터 연결 실행 계획

## 1. 목표

`back_dev_home/` 하나를 댁과 사무실에서 함께 사용하면서 Flask route와 프론트엔드
계약을 바꾸지 않고 mock adapter를 실 데이터 adapter로 점진 전환합니다.

완료 상태는 다음과 같습니다.

- 프론트엔드는 계속 `/api/*`만 호출합니다.
- `routes.py`와 `contracts.py`는 환경을 모릅니다.
- `data.py`는 provider를 선택하는 작은 seam으로 유지됩니다.
- `providers/office.py`만 `ops_store`, `minio_handler`, Redis 등 사무실 source를
  압니다.
- 사무실 source 오류가 mock 데이터로 위장되지 않습니다.
- 피처별로 office 전환과 mock rollback이 환경 변수 한 줄로 가능합니다.

공통 구현 규칙과 GLM 프롬프트는
[`docs/back-end/office-data-adapters.md`](../../back-end/office-data-adapters.md)를
기준으로 합니다.

## 2. 고정 결정

| 항목 | 결정 |
| --- | --- |
| Flask app tree | `back_dev_home/` 하나만 사용합니다. `back_dev_office/`를 만들지 않습니다. |
| 공개 seam | `data.py`의 함수 이름, 파라미터, 반환 계약입니다. |
| mock 구현 | `providers/mock.py`에 둡니다. |
| office 구현 | `providers/office.py`에 둡니다. |
| OpenSearch | 저장소의 `ops_store.OSSearch`, `OSDoc`, `OSIndex`를 사용합니다. |
| MinIO | 저장소의 `minio_handler.MinioObject`를 사용합니다. |
| Redis | `redis` client를 사용하되 설정/timeout 규약을 foundation 단계에서 고정합니다. |
| provider 선택 | `SKEWNONO_DATA_PROVIDER`와 `SKEWNONO_<FEATURE>_PROVIDER`를 사용합니다. |
| 최초 rollout | 전역은 `mock`, 검증 중인 피처만 `office`로 설정합니다. |
| 오류 fallback | 자동 mock fallback을 금지합니다. |
| secret | 환경 변수 또는 사내 secret manager로 주입하며 Git에 커밋하지 않습니다. |
| 실 sample | 사외 반출과 Git 커밋을 금지하고 익명화 구조만 남깁니다. |

## 3. 명세 계층

피처 구현 전에 다음 자료가 모두 있어야 합니다.

| 자료 | 위치 | 역할 |
| --- | --- | --- |
| HTTP 계약 | `docs/api-contracts/<feature>.yaml` | route, 파라미터, wire shape, enum |
| Python 계약 | `back_dev_home/<feature>/contracts.py` | provider 반환 키와 타입 |
| mock 기준 | `back_dev_home/<feature>/providers/mock.py` | 정상 동작과 edge case 기준선 |
| 대표 응답 | `back_dev_home/<feature>/__fixtures__/*.json` | 구조 비교 예시 |
| 원본 schema | `docs/datatables/<source>.txt` | 원본 필드와 의미 |
| 연결 노트 | `docs/back-end/office-sources/<feature>.md` | mapping, query, dedup, 오류, 성능 결정 |

연결 노트는 다음 형식을 사용합니다.

```markdown
# <feature> office source

## Source
- 종류: OpenSearch / MinIO / Redis / SQL / 내부 interface
- alias, bucket, Redis key: 환경 변수 이름만 기록
- 소유 팀과 read/write 권한: <확인 필요>

## Field mapping
| Contract field | Source field | Conversion | Null/unknown rule |
| --- | --- | --- | --- |

## Query semantics
- filter:
- join:
- latest-row rule:
- dedup key and tie-breaker:
- sort:
- pagination and safety limit:

## Runtime
- timeout/retry:
- expected/max rows or object size:
- cache/freshness:
- partial failure:

## Security
- 반환 금지 필드:
- 로그 마스킹:
- 익명화 규칙:

## Acceptance
- unit fixture cases:
- integration command:
- go/no-go threshold:
```

host, 사용자명, 비밀번호, token, 인증서 본문, 실제 장비 IP와 실제 row는 연결 노트에
기록하지 않습니다.

## 4. 실행 순서

### Phase 0 — 공통 foundation 고정

#### Task 0.1 — 승인 모듈과 dependency 정리

대상 파일:

- `ops_store/`
- `minio_handler/`
- `back_dev_home/requirements.txt`
- `.gitignore`
- `back_dev_home/health/data.py`

작업:

1. `minio_store` → `minio_handler` rename을 하나의 독립 commit으로 완료합니다.
2. `back_dev_home/health/data.py`의 import를 `minio_handler`로 통일합니다.
3. `opensearch-py`, `pandas`, `redis`, `minio` SDK를 backend requirements에 둡니다.
4. `minio_handler/minio_config.py`를 Git에서 제외합니다.
5. office image에서 `ops_store`, `minio_handler`를 import할 수 있는지 확인합니다.
6. `OPENSEARCH_*`, `MINIO_*`, `REDIS_*` 변수 목록을 deployment manifest에
   기록합니다.

완료 조건:

- 삭제된 `minio_store` import가 없습니다.
- fresh clone에서 secret 파일 없이 import가 가능합니다.
- fake client test는 사내 endpoint 없이 실행됩니다.
- 실제 health smoke test는 mock 문구가 아니라 각 source의 실제 상태를 반환합니다.

#### Task 0.2 — provider 선택 통일

대상 파일:

- `back_dev_home/_runtime/data_provider.py`
- `back_dev_home/ebeam/hitachi/hardware/data.py`
- `back_dev_home/ebeam/hitachi/skew/data.py`
- provider-backed 피처의 `providers/__init__.py`
- `tests/test_office_provider_dispatch.py`

작업:

1. 모든 dispatcher가 `get_data_provider(feature)`를 사용합니다.
2. `is_cloud()`를 mock/office 선택에 사용하지 않습니다.
3. mock/office provider는 선택된 함수 안에서 lazy import합니다.
4. 전역 설정, 피처 override, 잘못된 값의 동작을 테스트합니다.

완료 조건:

- Phase 2 localhost에서 `SKEWNONO_<FEATURE>_PROVIDER=office`가 동작합니다.
- home startup은 office-only package가 없어도 mock provider로 기동합니다.
- feature override가 전역 설정보다 우선합니다.

#### Task 0.3 — office 오류 계약

새 공통 오류 module과 Flask handler를 설계합니다. 이름은 구현 전에 현재
`back_dev_home/_auth/errors.py` 규약과 충돌하지 않는지 확인합니다.

권장 응답 의미는 다음과 같습니다.

| 상황 | HTTP | 외부 code | 원칙 |
| --- | --- | --- | --- |
| 필수 환경 변수 누락 | 500 | `office_configuration_error` | 배포 오류이며 내부 값은 숨깁니다. |
| source timeout/연결 실패 | 503 | `office_source_unavailable` | mock fallback을 하지 않습니다. |
| source 권한 거부 | 503 | `office_source_unavailable` | 사용자에게 credential 정보를 노출하지 않습니다. |
| source row 계약 위반 | 500 | `office_contract_violation` | 문제 필드와 실제 값은 server log에서 마스킹합니다. |
| 정상 empty result | 200 | 해당 없음 | 해당 피처 계약이 empty를 허용할 때만 사용합니다. |

완료 조건:

- 모든 오류는 JSON입니다.
- trace, host, query body, credential은 응답에 포함되지 않습니다.
- timeout을 강제로 발생시킨 test가 503을 검증합니다.

### Phase 1 — `sem_list` reference 연결

`sem_list`를 첫 실 데이터 피처로 연결합니다. storage와 여러 화면이 장비 metadata를
재사용하므로 후속 작업의 기준이 됩니다.

#### Task 1.1 — 사무실 source inventory

생성/갱신 파일:

- `docs/datatables/sem_list.txt`
- `docs/back-end/office-sources/sem-list.md`

사무실에서 확인할 내용:

1. OpenSearch alias/index와 mapping입니다.
2. 계약 10개 필드의 원본 field입니다.
3. vendor/status 원본 값 전체와 enum mapping입니다.
4. timestamp timezone과 UTC 변환 규칙입니다.
5. 같은 `eqp_id`의 latest-row/tie-breaker 규칙입니다.
6. 폐기/비가동/임시 장비 포함 규칙입니다.
7. 예상/최대 장비 수와 갱신 주기입니다.
8. `eqp_ip` 반환 권한입니다.

미확인 항목은 `확인 필요`로 남깁니다. GLM이 추측하지 않습니다.

#### Task 1.2 — `ops_store` office adapter

대상 파일:

- `back_dev_home/sem_list/providers/office.py`
- `tests/test_sem_list_office.py`

구현 규칙:

1. index 값은 `SKEWNONO_SEM_LIST_INDEX`에서 읽습니다.
2. `ops_store.OSSearch`를 process별로 재사용합니다.
3. module import 시 client를 만들거나 network call을 하지 않습니다.
4. 필요한 `_source` 필드만 조회합니다.
5. 전체 결과는 `search_dataframe_all()`로 읽습니다.
6. `count()` 또는 `safety_limit + 1` 방식으로 truncation을 탐지합니다.
7. source document 정규화는 한 private 함수에 모읍니다.
8. dedup과 sort는 연결 노트에 확정된 규칙만 구현합니다.

테스트 cases:

- 정상 10개 필드
- vendor/status mapping 전체
- timezone-aware/naive timestamp
- 필수 field null/누락
- 잘못된 integer와 알 수 없는 enum
- 중복 `eqp_id`와 tie-breaker
- 여러 scroll page
- safety limit 초과
- timeout/permission 오류

#### Task 1.3 — 실제 smoke와 frontend 확인

최초 설정:

```bash
export SKEWNONO_DATA_PROVIDER=mock
export SKEWNONO_SEM_LIST_PROVIDER=office
export SKEWNONO_SEM_LIST_INDEX=<office-alias>
python index.py
```

검증:

1. `GET /api/sem-list`가 bare array를 반환합니다.
2. 모든 행이 정확히 10개 계약 key를 가집니다.
3. `eqp_id` 중복, 잘못된 enum, timestamp parse 실패가 없습니다.
4. source count와 반환 count 차이가 연결 노트의 제외 규칙으로 설명됩니다.
5. Nuxt landing, fab sidebar, tool tab, inventory가 정상 렌더링됩니다.
6. source 차단 시 mock row가 아니라 JSON 503을 반환합니다.

Rollback:

```bash
export SKEWNONO_SEM_LIST_PROVIDER=mock
```

코드 rollback 없이 설정 변경만으로 복구되어야 합니다.

### Phase 2 — health와 storage 연결

#### Task 2.1 — health

- OpenSearch: `ops_store.OSSearch`
- MinIO: `minio_handler.MinioObject`
- Redis: `redis.Redis`

현재 health의 broad exception → mock fallback은 production readiness를 숨길 수 있습니다.
office provider에서는 `up/down` 상태와 안전한 detail을 반환하되 mock latency나 mock
timestamp를 실제 상태처럼 반환하지 않습니다.

#### Task 2.2 — storage

구현 파일:

- `back_dev_home/ebeam/hitachi/storage/providers/office.py`
- `tests/test_storage_office.py`

source:

- storage monitoring index: `ops_store.OSSearch`
- PPID unavailable hash: Redis
- equipment enrichment: office `get_sem_list()`

검증 포인트:

- `tool_slug`, `fac_ids` filtering
- storage 수집 실패의 blank/null 규칙
- Redis latest date 선택과 30일 streak
- orphan IP 보존
- sem-list join의 IP 중복 처리
- partial source failure 정책

### Phase 3 — read-only 화면 피처

다음 우선순위는 source 준비도와 사용자 영향으로 조정합니다.

| 우선순위 | 피처 | 예상 source | 현재 준비 상태 |
| --- | --- | --- | --- |
| P0 | `sem_list` | OpenSearch via `ops_store` | provider seam과 계약 있음 |
| P0 | `health` | OpenSearch + MinIO + Redis | 기존 혼합 구현, office 의미 정리 필요 |
| P1 | `storage` | OpenSearch + Redis + sem-list join | provider seam과 계약 있음 |
| P1 | `hardware` | 서비스별 OpenSearch/MinIO, 확인 필요 | provider seam과 계약 있음 |
| P1 | `meas_hist` | OpenSearch | provider 분리와 YAML 보강 필요 |
| P1 | `msr_file` | metadata index + MinIO, 확인 필요 | provider 분리와 YAML 필요 |
| P1 | `recipe_search` | Redis/OpenSearch/MinIO, 확인 필요 | provider 분리와 YAML 필요 |
| P2 | `device_statistics` | OpenSearch aggregation | provider 분리 필요 |
| P2 | `recipe_tat` | OpenSearch aggregation | provider 분리, 시간 anchor 확정 필요 |
| P2 | `fail_issue` | OpenSearch aggregation | provider 분리 필요 |
| P2 | `activity` | Redis + OpenSearch | provider 분리 필요 |
| P2 | `admin_logs` | OpenSearch | 기존 조회를 provider seam으로 이동 필요 |
| P2 | `skew` | 파생 통계 source, 확인 필요 | provider seam과 계약 있음 |
| P2 | `pm_planning` | hardware 파생 source, 확인 필요 | provider 분리 필요 |
| P2 | `lateral_recipe` | Redis + OpenSearch | provider 분리와 YAML 필요 |
| P3 | `afm` | file/MinIO/source 확인 필요 | provider 분리 필요 |
| P3 | `announcements` | 운영 source 확인 필요 | provider 분리 필요 |
| P3 | `access_control` | shared persistence 확인 필요 | write 정책과 audit 필요 |
| P3 | `api_tokens` | shared persistence 확인 필요 | secret/hash/write 정책 필요 |

각 피처는 다음 한 묶음으로 완료합니다.

1. source inventory와 연결 노트
2. `contracts.py`
3. `providers/mock.py`
4. `providers/office.py`
5. dispatcher `data.py`
6. mock/office interface tests
7. actual-source smoke
8. frontend smoke
9. drift report

### Phase 4 — write/admin 피처

쓰기 피처는 read-only 피처가 안정된 뒤 진행합니다.

추가 명세:

- authentication/authorization
- idempotency key
- optimistic concurrency/version
- audit event
- validation과 partial write
- retry 시 중복 방지
- rollback/restore
- secret/hash/PII 보존 정책

`access_control`, `api_tokens`, announcement 관리, rule 저장 등은 이 기준 없이 office
write를 활성화하지 않습니다.

## 5. 사무실 GLM 작업 절차

각 피처에서 GLM에 다음 입력을 함께 제공합니다.

1. 본 실행 계획
2. `docs/back-end/office-data-adapters.md`
3. API YAML
4. `data.py`, `contracts.py`, mock/office provider
5. 대표 fixture
6. 원본 schema와 연결 노트
7. `ops_store` 또는 `minio_handler`의 실제 interface 문서
8. 익명화 raw sample

모델 출력은 다음 순서로 받습니다.

1. 확인한 사실
2. `확인 필요` 목록
3. 변경 허용 범위
4. patch
5. query/pagination/normalization/error 설명
6. test와 결과

모델이 `routes.py`, `contracts.py`, 프론트엔드 또는 공통 저장 모듈을 수정하려 하면
먼저 계약 변경 사유를 별도 제안으로 분리하게 합니다.

## 6. 검증 matrix

| 단계 | 검증 | 기준 |
| --- | --- | --- |
| 댁 기준선 | mock feature tests | 기존 결과 유지 |
| Python 전체 | `python -m unittest discover tests` | 실패 0 |
| 구조 | `python scripts/check_contract.py` | 대상 endpoint 통과 |
| 의미 | office adapter unit tests | enum/null/time/dedup/truncation 통과 |
| 실제 source | office-only smoke | count와 latency 기준 충족 |
| frontend | Nuxt manual smoke | 주요 화면 오류 없음 |
| 문서 | `npm run lint:md` 또는 changed-file lint | 변경 문서 오류 0 |
| diff | `git diff --check` | whitespace 오류 0 |

`check_contract.py`는 첫 행 구조만 비교하므로 단독 release gate로 사용하지 않습니다.

## 7. 배포와 rollback

### Incremental rollout

```bash
SKEWNONO_DATA_PROVIDER=mock
SKEWNONO_SEM_LIST_PROVIDER=office
SKEWNONO_STORAGE_PROVIDER=mock
```

피처별 acceptance가 끝날 때마다 해당 override만 `office`로 바꿉니다. 모든
provider-backed 피처가 준비되기 전에는 전역 값을 `office`로 바꾸지 않습니다.

### Full office rollout

```bash
SKEWNONO_DATA_PROVIDER=office
```

이 상태는 모든 provider-backed 피처의 office test와 actual-source smoke가 통과한 뒤에만
사용합니다.

### Rollback

장애 피처만 `SKEWNONO_<FEATURE>_PROVIDER=mock`으로 되돌립니다. mock 응답임을 운영자가
알 수 있도록 deployment configuration과 화면/로그 표시 정책을 별도로 정합니다. 자동
fallback은 사용하지 않습니다.

## 8. Commit 계획

작업은 다음 크기로 나눕니다.

1. `docs: define office data connection plan`
2. `backend: finalize office storage clients`
3. `backend: standardize provider selection`
4. `backend: add office data error contract`
5. `sem-list: document office source mapping`
6. `sem-list: connect office OpenSearch adapter`
7. `sem-list: add office adapter tests`
8. 피처별 source/adapter/test commit 반복

각 commit은 unrelated tmux/worktree 변경을 포함하지 않고 명시적 경로만 stage합니다.

## 9. 최종 완료 기준

- 19개 route module의 source와 provider 상태가 inventory에 기록되어 있습니다.
- 연결 대상 피처는 YAML, Python contract, fixture, source note를 가집니다.
- OpenSearch는 `ops_store`, object storage는 `minio_handler`를 사용합니다.
- 모든 office adapter는 fake-client unit test와 actual-source smoke를 통과합니다.
- provider 전환은 config-only이며 rollback도 config-only입니다.
- source 장애가 mock 데이터로 위장되지 않습니다.
- secret과 실 sample이 Git 또는 client 오류 응답에 없습니다.
- Phase 2 frontend는 feature code 변경 없이 Flask office data를 렌더링합니다.
