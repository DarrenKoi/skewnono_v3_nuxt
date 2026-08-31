# 사무실 데이터 어댑터 연결 가이드

이 문서는 `back_dev_home/`를 Phase 2 사무실 데이터와 연결할 때 지켜야 하는
공통 인터페이스와 사무실 LLM 작업 절차를 정의합니다. 환경 간 전달 절차는
[`docs/swap-strategy.md`](../swap-strategy.md), HTTP 응답 형태는
[`docs/api-contracts/`](../api-contracts/README.md)가 기준입니다.

## 1. 변경 경계

피처의 안정적인 seam은 `data.py`가 노출하는 함수입니다. 사무실 연결은 원칙적으로
`providers/office.py` 안에서 끝나야 합니다.

```text
back_dev_home/<feature>/
|-- routes.py              # 변경 금지: HTTP 입력과 응답
|-- data.py                # 변경 금지: provider 선택과 공개 함수
|-- contracts.py           # 변경 금지: Python 응답 계약
|-- providers/
|   |-- mock.py            # 댁 adapter와 기준 동작
|   `-- office.py          # 사무실 adapter와 원본 데이터 정규화
`-- __fixtures__/          # 대표 HTTP 응답 예시
```

| 파일 | 책임 | 사무실 연결 시 원칙 |
| --- | --- | --- |
| `routes.py` | 쿼리 파라미터 파싱, 상태 코드, JSON 직렬화 | 수정하지 않습니다. |
| `data.py` | mock/office adapter 선택, 공개 인터페이스 | 수정하지 않습니다. |
| `contracts.py` | 반환 키와 Python 타입 | 합의된 계약 변경이 아니면 수정하지 않습니다. |
| `providers/mock.py` | 결정론적 댁 기준선 | 실 데이터 코드를 넣지 않습니다. |
| `providers/office.py` | 사무실 조회, 정규화, source-specific 오류 | 주요 구현 대상입니다. |
| API 계약 YAML | HTTP 경로, 파라미터, wire shape, enum | 응답의 최종 기준입니다. |
| 픽스처 JSON | 대표 응답 예시 | 값이 아니라 구조 비교에 사용합니다. |
| 데이터테이블 문서 | 사무실 원본 필드와 의미 | 실제 매핑이 바뀔 때 갱신합니다. |

다음 변경은 금지합니다.

- `routes.py`에서 OpenSearch, Redis, SQL 또는 사내 클라이언트를 직접 호출하지 않습니다.
- 프론트엔드에 home/office 분기를 추가하지 않습니다.
- 사무실 조회 실패 시 mock 데이터를 자동 반환하지 않습니다. 의도적인 mock 사용은
  provider 환경 변수로 선택합니다.
- 실제 원본에 없는 필드, enum, 기본값을 LLM이 추측해서 만들지 않습니다.
- 비밀번호, 토큰, 인증서 본문, 사내 호스트를 코드나 문서에 커밋하지 않습니다.

## 2. 실행 환경 선택

데이터 위치와 Flask 배포 위치는 별도 결정입니다. Phase 2의 최초 전환은 전역 mock을
유지하고 검증 중인 피처만 office로 여는 방식으로 시작합니다.

```bash
export SKEWNONO_DATA_PROVIDER=mock
export SKEWNONO_SEM_LIST_PROVIDER=office
```

모든 provider-backed 피처가 검증된 뒤 전역 기본값을 office로 바꿀 수 있습니다. 이때
아직 연결하지 않은 피처만 명시적으로 mock으로 유지합니다.

```bash
export SKEWNONO_DATA_PROVIDER=office
export SKEWNONO_STORAGE_PROVIDER=mock
```

공통 선택기는 `back_dev_home/_runtime/data_provider.py`이며, 피처별 환경 변수가 전역
설정보다 우선합니다. 환경 변수를 지정하지 않으면 `_runtime/site.py`의 site 감지가
기본값을 정하고, 이때 Phase 3 클라우드 배포 경로(`is_cloud()`)는 office로 판정됩니다.
전체 규칙은 [`docs/back-end/provider-selection.md`](provider-selection.md)를 참고합니다.
Phase 3의 SSO, SPA 서빙, 로깅 활성화는 데이터 연결과 별도로 검증합니다.

## 3. 승인된 사무실 데이터 모듈

사무실 adapter는 저장소에 포함된 다음 모듈을 우선 사용합니다. 각 피처가
`opensearch-py`나 `minio` SDK를 직접 초기화하지 않습니다.

| 데이터 종류 | 사용할 모듈 | 주요 인터페이스 |
| --- | --- | --- |
| OpenSearch 조회/집계 | `ops_store` | `OSSearch` |
| OpenSearch 문서 쓰기 | `ops_store` | `OSDoc` |
| OpenSearch index 관리 | `ops_store` | `OSIndex` |
| MinIO 객체 읽기/쓰기 | `minio_handler` | `MinioObject` |
| Redis | `redis` | 피처별 adapter에서 사용하되 공통 설정 규칙을 별도로 확정 |

### 3.1 `ops_store`

`OSSearch(index=...)`는 다음 `OPENSEARCH_*` 환경 변수를 읽어 client를 생성합니다.

- 연결: `OPENSEARCH_HOST`, `OPENSEARCH_PORT`, `OPENSEARCH_USER`,
  `OPENSEARCH_PASSWORD`
- TLS: `OPENSEARCH_USE_SSL`, `OPENSEARCH_VERIFY_CERTS`,
  `OPENSEARCH_SSL_SHOW_WARN`, `OPENSEARCH_CA_CERTS`
- 동작: `OPENSEARCH_TIMEOUT`, `OPENSEARCH_MAX_RETRIES`,
  `OPENSEARCH_RETRY_ON_TIMEOUT`, `OPENSEARCH_HTTP_COMPRESS`

office 배포에서는 `ops_store`의 개발 기본값에 의존하지 않습니다. host, 인증, TLS 검증,
timeout을 배포 환경에서 명시하며 secret 값은 환경 변수 또는 secret manager로
주입합니다.

```python
from ops_store import OSSearch

search = OSSearch(index=index_name)
frame = search.search_dataframe_all(
    body,
    batch_size=1000,
    scroll="2m",
    max_rows=safety_limit + 1,
)
```

- 10,000행을 넘을 수 있으면 `search_dataframe_all()` 또는
  `range_dataframe_all()`을 사용합니다. 이 메서드는 scroll context를 `finally`에서
  정리합니다.
- `max_rows`에 도달한 결과를 정상 전체 결과로 반환하지 않습니다. `count()` 또는
  `safety_limit + 1` 조회로 truncation을 탐지하고 명시적 오류로 처리합니다.
- 읽기 adapter에서 `OSIndex`로 mapping/index를 만들거나 변경하지 않습니다. index
  관리는 배포/migration 작업으로 분리합니다.
- feature query와 source mapping은 `providers/office.py`에 두며 `ops_store`에
  feature-specific 메서드를 추가하지 않습니다.

#### OpenSearch logging family 준비

`activity`와 `admin_logs` office adapter는 같은 cluster에서
`SKEWNONO_LOG_ENV`가 선택한 alias를 읽습니다.

| 실행 위치 | `SKEWNONO_LOG_ENV` | Alias |
| --- | --- | --- |
| 사무실 PC localhost | `local` | `skewnono_logging_local` |
| 회사 production cloud | `production` | `skewnono_logging` |

회사 네트워크와 `OPENSEARCH_*` 자격 증명이 준비된 환경에서만 다음 명령을
실행합니다.

```bash
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all \
  --dry-run
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all
```

첫 번째 명령은 cluster에 접속하거나 변경하지 않고 policy, template, mapping,
초기 index 요청을 출력하는 read-only 검토 단계입니다. 두 번째 명령은 멱등하지만
공유 cluster의 ISM policy, index template, mapping, backing index와 alias를
생성하거나 갱신합니다. dry-run 결과를 검토하지 않고 두 번째 명령을 실행하지
않습니다.

반영 후 다음 write alias 연결을 확인합니다.

```text
skewnono_logging_local-000001 → skewnono_logging_local
skewnono_logging-000001       → skewnono_logging
```

기존 alias가 numbered rollover write index가 아니거나 첫 index가 충돌하면 script는
자동 삭제나 재색인 없이 실패합니다. Flask writer와 reader는 index를 자동 생성하지
않습니다. cluster smoke test 전에는
[`docs/office-migration/STATUS.md`](../office-migration/STATUS.md)의 상태를
`구현완료`로 유지하며, 실제 office 데이터와 화면까지 확인한 뒤에만 `office`로
변경합니다.

### 3.2 `minio_handler`

MinIO 접속 설정은 `minio_handler/minio_config.py` 한 곳에서만 관리합니다. endpoint,
access key, secret key, secure, region, cert_check와 기본 bucket·prefix가 모두 이
파일에 들어갑니다. 이 파일은 `.gitignore`에 등록되어 있어 Git에 올라가지 않으며,
home과 office가 각자의 사본을 유지합니다.

`MINIO_*` 환경 변수는 사용하지 않습니다. `minio_handler/base.py`에서 환경 변수가
`minio_config.py`보다 **높은** 우선순위를 가지므로, `.env`에 `MINIO_*` 한 줄만
남아 있어도 실제로 관리하는 파일의 값을 조용히 덮어씁니다. 특히 값이 빈
`MINIO_SECRET_KEY=`는 "설정하지 않음"이 아니라 `""`으로 읽혀 `None`으로 해석되므로,
정상적인 secret key를 아무 오류 없이 무효화합니다. 그래서 `back_dev_home/.env.example`의
MinIO 절에는 자격 증명을 두지 않습니다.

bucket과 prefix는 피처 연결 명세에 기록하고 `MinioObject` 생성 시 명시합니다.

```python
from minio_handler import MinioObject

objects = MinioObject(bucket=bucket_name, prefix=feature_prefix)
body = objects.get(object_key)
```

- `get()`은 응답 connection을 닫고 bytes를 반환하므로 크기가 제한된 객체에
  사용합니다.
- 큰 객체는 메모리에 전부 적재하지 않도록 download, presigned URL 또는 streaming
  정책을 피처별로 정합니다.
- MinIO는 prefix listing 외의 field query가 없습니다. 검색 가능한 metadata는
  `ops_store`에 두고 MinIO에는 object body를 둡니다.
- bucket, prefix, retention, 최대 object 크기, content type, 누락 object 처리를
  연결 명세에 기록합니다.

### 3.3 client 재사용과 테스트

두 모듈 모두 기존 client를 생성자에 주입할 수 있습니다. public feature 인터페이스는
변경하지 않고, office adapter 내부에서만 생성과 조회를 분리합니다.

- process별 client/service instance를 재사용하되 module import 시 연결하지 않습니다.
- unit test는 fake OpenSearch/MinIO client를 주입합니다.
- feature test에서 실제 사내 endpoint를 호출하지 않습니다.
- `ops_store`와 `minio_handler` 자체를 feature 작업 중 수정하지 않습니다. 여러 피처에
  공통으로 필요한 일반 기능이 확인된 경우 별도 변경으로 검토합니다.

## 4. 피처별 연결 명세에 반드시 기록할 내용

사무실에서 코드를 만들기 전에 아래 항목을 피처별 작업 노트에 채웁니다. 모르는 값은
`확인 필요`로 남기며 LLM이 채우게 하지 않습니다.

| 구분 | 필수 내용 |
| --- | --- |
| 공개 인터페이스 | 함수 이름, 파라미터, 반환 타입, sync/async 여부 |
| HTTP 계약 | YAML 경로, 성공 상태, 최상위 배열/객체 형태, 오류 상태 |
| 원본 위치 | OpenSearch alias/index, Redis key, SQL table 또는 사내 인터페이스 |
| 연결 설정 | 필요한 환경 변수 이름, TLS/CA, 인증 방식, 권한 범위 |
| 필드 매핑 | 원본 필드 → 계약 필드, 형 변환, 단위 변환 |
| 조회 규칙 | filter, join, 최신 행 선택, dedup key, 정렬, pagination |
| 결측 규칙 | `null`, 빈 문자열, 기본값, 행 제외 조건 |
| enum 규칙 | 원본 값 → 계약 enum과 알 수 없는 값 처리 |
| 시간 규칙 | 원본 timezone, UTC 변환, 출력 format, 조회 window anchor |
| 일관성 규칙 | 여러 원본을 읽을 때 snapshot 시점과 join 실패 처리 |
| 오류 규칙 | timeout, retry, 부분 실패, 빈 결과, 데이터 오류 처리 |
| 성능 목표 | 예상 행 수, 최대 행 수, 응답 목표, 캐시/갱신 주기 |
| 보안 | 반환 금지 필드, 개인정보/사내 IP 노출 승인, 로그 마스킹 |
| 검증 | 정상/결측/중복/미등록 enum fixture와 acceptance command |

원본 mapping 또는 실제 sample은 사내에만 보관할 수 있습니다. 이 경우 외부 저장소에는
필드명과 의미만 익명화해 기록하고, 민감한 값은 사무실 전용 작업 노트로 분리합니다.

## 5. `sem_list` 기준 명세

`sem_list`는 현재 adapter 구조의 기준 피처이며 다른 데이터의 장비 join에도 사용됩니다.
따라서 첫 번째 실 데이터 연결 대상으로 권장합니다.

### 5.1 고정된 인터페이스

- 공개 함수: `get_sem_list() -> list[SemListRow]`
- HTTP: `GET /api/sem-list`
- 응답: `{data, total}` envelope가 없는 bare JSON array입니다.
- 쿼리 파라미터: 없습니다.
- provider 선택: `SKEWNONO_SEM_LIST_PROVIDER`, 없으면
  `SKEWNONO_DATA_PROVIDER`, 없으면 `mock`입니다.
- OpenSearch index/alias 설정: `SKEWNONO_SEM_LIST_INDEX`입니다.
- 프론트 분류: `eqp_model_cd` prefix로 tool type을 분류합니다.

계약 필드는 다음과 같습니다. `사무실 원본` 열은 실제 mapping 확인 후 사무실 작업
노트에 채웁니다.

| 계약 필드 | 계약 타입/값 | 사무실 원본 | 필수 정규화 |
| --- | --- | --- | --- |
| `fac_id` | `str` | 확인 필요 | 공백 제거, 대표 facility 코드 유지 |
| `eqp_id` | `str` | 확인 필요 | 공백 제거, 장비별 유일성 검증 |
| `eqp_model_cd` | `str` | 확인 필요 | 원본 model code 유지, 대소문자 규칙 확정 |
| `eqp_grp_id` | `str` | 확인 필요 | 누락 가능 여부와 기본값 결정 |
| `vendor_nm` | `HITACHI` 또는 `AMAT` | 확인 필요 | 원본 vendor 값을 두 enum으로 명시적 mapping |
| `eqp_ip` | `str` | 확인 필요 | IPv4 검증, 노출 권한 확인 |
| `fab_name` | `str` | 확인 필요 | M 계열 suffix와 R3/R4 규칙 검증 |
| `updt_dt` | UTC ISO 8601 `str` | 확인 필요 | timezone-aware UTC로 변환하고 `Z`로 출력 |
| `available` | `On` 또는 `Off` | 확인 필요 | 원본 상태값을 두 enum으로 명시적 mapping |
| `version` | `int` | 확인 필요 | 숫자 변환 실패 처리 결정 |

### 5.2 구현 전에 결정해야 하는 사항

다음 답이 없으면 `office.py` 구현을 완료한 것으로 보지 않습니다.

1. 실제 source와 읽기 전용 alias/index/table 이름은 무엇입니까?
2. 같은 `eqp_id`가 여러 행이면 최신 행을 고르는 timestamp와 tie-breaker는
   무엇입니까?
3. 비가동, 폐기 또는 임시 장비도 반환합니까? `available`과 행 포함 여부는 별개입니까?
4. vendor/status의 모든 실 원본 값과 계약 enum mapping은 무엇입니까?
5. timestamp에 timezone이 없으면 어느 timezone으로 해석합니까?
6. 알 수 없는 model prefix를 반환합니까, 제외합니까, 데이터 오류로 처리합니까?
7. 예상/최대 장비 수는 얼마입니까? OpenSearch 기본 `size`로 잘리지 않도록 어떤
   pagination을 사용합니까?
8. 정렬 순서를 보장합니까? 보장한다면 어떤 필드 순서입니까?
9. inventory 갱신 주기와 허용 stale 시간은 얼마입니까? 프론트는 현재 SPA 세션 동안
   `sem-list` 결과를 재사용합니다.
10. `eqp_ip`를 모든 로그인 사용자에게 반환해도 되는지 보안 승인이 있습니까?

### 5.3 권장 구현 내부 구조

공개 인터페이스는 그대로 두고 `office.py` 내부에만 작은 내부 seam을 둡니다.

```python
from functools import lru_cache

from ops_store import OSSearch


@lru_cache(maxsize=1)
def _get_search() -> OSSearch:
    return OSSearch(index=_required_index_name())


def get_sem_list() -> list[SemListRow]:
    documents = _fetch_all_documents(_get_search())
    rows = [_normalize_document(document) for document in documents]
    return _deduplicate_and_sort(rows)
```

- `_required_index_name()`은 `SKEWNONO_SEM_LIST_INDEX`가 없으면 명확한 설정 오류를
  발생시킵니다.
- `_get_search()`는 process 안에서 `OSSearch`를 재사용하고, import 시 네트워크에
  접속하지 않습니다.
- `_fetch_all_documents()`는 `search_dataframe_all()`로 필요한 `_source` 필드만
  조회하며 batch, scroll, safety limit을 명시합니다.
- `_normalize_document()`는 source-specific 필드명을 `SemListRow`로 변환하는 유일한
  위치입니다.
- `_deduplicate_and_sort()`는 연결 명세에 확정된 규칙만 구현합니다.
- 테스트는 fake client/raw document를 사용해 공개 결과를 검증합니다. 사내 시스템을
  unit test에서 직접 호출하지 않습니다.

## 6. 사무실 LLM용 프롬프트

아래 블록에 사무실 mapping과 sample을 추가한 뒤 GLM 계열 모델에 전달합니다.

```text
당신은 SKEWNONO Flask의 Phase 2 데이터 adapter를 구현합니다.

[목표]
- back_dev_home/sem_list/providers/office.py를 실제 사무실 source에 연결합니다.
- public interface get_sem_list() -> list[SemListRow]를 유지합니다.
- GET /api/sem-list의 bare-array wire contract를 정확히 유지합니다.

[먼저 읽을 파일]
1. back_dev_home/sem_list/routes.py
2. back_dev_home/sem_list/data.py
3. back_dev_home/sem_list/contracts.py
4. back_dev_home/sem_list/providers/mock.py
5. back_dev_home/sem_list/providers/office.py
6. docs/api-contracts/sem-list.yaml
7. back_dev_home/sem_list/__fixtures__/sem-list.json
8. tests/test_sem_list_home.py
9. docs/back-end/office-data-adapters.md
10. ops_store/__init__.py
11. ops_store/base.py
12. ops_store/search.py
13. ops_store/docs/search_all_usage.md

[사무실 source 정보]
- source 종류와 이름: <필수 입력>
- OpenSearch alias/index 값(SKEWNONO_SEM_LIST_INDEX): <필수 입력>
- mapping: <필수 입력>
- 익명화 raw document: <정상/결측/중복/미등록 enum 예시>
- 인증과 TLS 방식: <필수 입력, secret 값은 입력하지 않음>
- 예상/최대 행 수: <필수 입력>
- freshness와 timeout 목표: <필수 입력>

[허용 변경]
- back_dev_home/sem_list/providers/office.py
- office adapter용 새 test file
- 실제로 추가된 외부 패키지의 requirements 문서

[변경 금지]
- routes.py, data.py, contracts.py, providers/mock.py
- docs/api-contracts/sem-list.yaml과 frontend
- public 함수의 이름, 파라미터, 반환 타입
- ops_store와 minio_handler

[구현 규칙]
1. OpenSearch 접근에는 ops_store.OSSearch를 사용합니다.
2. source-specific 필드와 query는 office.py 내부에 둡니다.
3. OSSearch는 재사용하되 module import 시 생성하거나 네트워크 연결하지 않습니다.
4. 필요한 필드만 조회하고 search_dataframe_all의 batch, scroll, safety limit,
   truncation 탐지를 명시합니다.
5. 모든 행을 SemListRow의 정확한 10개 키로 정규화합니다.
6. vendor_nm/available mapping, timezone, null, unknown 값은 제공된 명세만 따릅니다.
7. office 조회 실패를 mock 데이터로 숨기지 않습니다.
8. secret, 사내 host, 실제 장비/IP sample을 코드/fixture/log에 남기지 않습니다.
9. unit test는 fake client/raw documents를 사용하고 정상, 결측, 중복, 잘못된 enum,
   pagination을 검증합니다.
10. 불명확한 source 사실은 추측하지 말고 '확인 필요' 목록으로 출력합니다.

[완료 조건]
- SKEWNONO_SEM_LIST_PROVIDER=office일 때 office adapter가 선택됩니다.
- 모든 행의 키/타입/enum/timestamp/유일성이 계약과 일치합니다.
- 결과가 source 최대 행 수에서도 잘리지 않습니다.
- 기존 home test와 새 office adapter test가 모두 통과합니다.
- python scripts/verify/check_contract.py가 실행 중인 office Flask에 대해 통과합니다.

[응답 형식]
1. 확인한 source 가정과 확인 필요 사항
2. 변경 파일 목록
3. 구현 patch
4. query, pagination, normalization, error 정책 설명
5. 실행한 test와 결과
```

## 7. 검증 게이트

`scripts/verify/check_contract.py`는 대표 픽스처와 실제 응답의 첫 행 구조 및 Python 기본 타입을
비교합니다. enum, timestamp 의미, 모든 행의 키, 중복, 정렬, 행 수 truncation까지
증명하지는 않습니다. 따라서 다음 검증을 함께 수행합니다.

1. 정상/결측/중복/미등록 enum raw document를 대상으로 adapter test를 실행합니다.
2. 모든 반환 행에 정확히 계약 키만 있는지 확인합니다.
3. `vendor_nm`, `available`, timestamp, integer 변환을 모든 행에 검사합니다.
4. `eqp_id` 중복과 최대 예상 행 수에서의 누락을 검사합니다.
5. Flask를 office provider로 실행하고 실제 HTTP 응답을 확인합니다.
6. Nuxt를 `NUXT_API_TARGET`으로 Flask에 연결해 landing/navigation/inventory를 확인합니다.
7. 의도적으로 source timeout을 발생시켜 오류가 mock 데이터로 위장되지 않는지
   확인합니다.

권장 명령은 다음과 같습니다.

```bash
SKEWNONO_SEM_LIST_PROVIDER=office python index.py
SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/python -m pytest back_dev_home/sem_list -q
PORT=5000 .venv/bin/python -m scripts.verify.check_contract
```

두 번째 줄이 해당 기능의 office 게이트입니다. `unittest` 로는 `back_dev_home/**/tests/`
아래의 contract 테스트가 수집되지 않으므로 `pytest` 를 사용합니다. 기능 이름만 바꾸면
다른 기능에도 그대로 적용됩니다.

`check_contract` 는 살아 있는 Flask 에 붙어 픽스처와 구조를 비교합니다. `PORT` 로 대상을
지정하며 기본값은 댁 기준 5050 이므로, 사무실 Flask(5000)에 붙일 때는 위와 같이 명시해야
합니다.

## 8. 현재 전환 현황과 순서

2026-07-15 기준 route module은 19개이지만 `providers/office.py` seam이 준비된 피처는
다음 네 개입니다.

| 상태 | 피처 |
| --- | --- |
| provider 선택 준비 | `sem_list`, `ebeam/storage`, `ebeam/hardware`, `ebeam/tttm` |
| 기존 `data.py` 구현 분리 필요 | `access_control`, `activity`, `admin_logs`, `afm`, `announcements`, `api_tokens`, `device_statistics`, `fail_issue`, `pm_planning`, `recipe_search`, `recipe_tat`, `lateral_recipe`, `health`, `meas_hist`, `msr_file` |

모든 폴더에 빈 `office.py`부터 만들지 않습니다. 각 피처는 다음 순서로 전환합니다.

1. HTTP YAML, Python contract, fixture, 원본 schema를 먼저 완성합니다.
2. 기존 mock 구현을 `providers/mock.py`로 이동합니다.
3. `data.py`를 provider 선택만 하는 얕은 dispatcher로 바꿉니다.
4. 동일 공개 인터페이스의 `providers/office.py`를 추가합니다.
5. mock과 office adapter를 같은 interface test로 검증합니다.

연결 순서는 `sem_list` → 공통 연결/health → `storage` → 화면별 read-only 피처 →
쓰기/관리 피처를 권장합니다. `sem_list`를 먼저 연결해야 IP와 장비 metadata를 join하는
후속 피처가 하나의 장비 기준을 사용할 수 있습니다.

## 9. 아직 별도 결정이 필요한 공통 항목

- OpenSearch와 MinIO는 저장소의 `ops_store`, `minio_handler`를 사용합니다. 두 모듈이
  의존하는 `opensearch-py`, `pandas`, `redis`, `minio` SDK는
  `back_dev_home/requirements.txt`에 포함하고 사무실 image도 동일한 dependency
  범위를 사용해야 합니다.
- 인증은 사내 인프라가 내려주는 `LASTUSER` 쿠키만 사용하므로 cloud image가
  제공하는 SSO 라이브러리에 대한 의존성은 없습니다.
- 현재 일반 예외는 JSON 오류 계약으로 정규화되지 않습니다. source timeout/권한 오류를
  어떤 code와 HTTP 상태로 반환할지 정한 뒤 공통 handler를 추가해야 합니다.
- Phase 2 localhost에서 Local identity를 쓸지 SSO를 쓸지 확정해야 합니다. 데이터
  provider 선택은 이미 이 결정과 분리되어 있습니다.
- OpenSearch/Redis client factory를 공유할지는 첫 두 개의 실제 adapter가 같은 연결
  설정을 사용한다는 사실을 확인한 뒤 결정합니다.
- production worker 수, client connection pool, retry 폭, readiness probe와 graceful
  shutdown을 배포 명세에 기록해야 합니다.
