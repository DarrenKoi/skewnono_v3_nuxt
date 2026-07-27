# admin_logs 사무실 이전

## 경계

`GET /api/admin/logs`는 선택된 provider에 따라 다음처럼 동작합니다.

| Provider | 데이터 소스 | 네트워크 사용 |
| --- | --- | --- |
| `mock` | 고정된 인메모리 데모 로그 | 사용하지 않음 |
| `office` | `SKEWNONO_LOG_ENV`로 선택한 OpenSearch logging alias | 사용함 |

`mock` provider는 `OPENSEARCH_PASSWORD`, 클라우드 감지 결과와 관계없이 항상 데모
데이터만 반환합니다. `office` provider는 자격 증명 유무에 따라 mock으로
되돌아가지 않으며, 설정이나 OpenSearch 조회에 실패하면 라우트가
`503 log_query_failed`를 반환합니다.

## Office adapter 준비

사무실에서 추적된 템플릿을 복사합니다.

```bash
cp back_dev_home/admin_logs/providers/office_example.py \
  back_dev_home/admin_logs/providers/office.py
```

`office.py`는 gitignore 대상입니다. 공통 조회 파서나 응답 계약은 수정하지 않고,
사내 연결에 추가 조정이 필요한 경우에만 이 복사본을 수정합니다.

다음 환경 변수를 설정합니다.

```dotenv
SKEWNONO_ADMIN_LOGS_PROVIDER=office
SKEWNONO_LOG_ENV=local
```

`SKEWNONO_LOG_ENV`는 필수이며 다음 alias를 선택합니다.

| 값 | 조회 alias |
| --- | --- |
| `local` | `skewnono_logging_local` |
| `production` | `skewnono_logging` |

OpenSearch 접속 정보는 `ops_store`가 사용하는 `OPENSEARCH_*` 환경 변수로
제공합니다. provider 내부에는 자격 증명 기반 분기나 `is_cloud()` 기반 분기가
없습니다.

## 저장소 준비

회사 네트워크에서 먼저 dry-run 결과를 검토한 뒤 실제 반영 명령을 실행합니다.

```bash
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all \
  --dry-run
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all
```

두 번째 명령은 정책, 템플릿, 매핑, 초기 인덱스와 alias를 멱등하게 준비하지만
공유 클러스터를 변경합니다. 상세 절차와 확인 항목은
[`docs/back-end/office-data-adapters.md`](../../docs/back-end/office-data-adapters.md)를
따릅니다.

## HTTP 계약

라우트는 `require_admin`으로 보호됩니다. 관리자가 아니면 provider 호출 전에
`403 forbidden`을 반환합니다.

지원하는 query parameter는 다음과 같습니다.

- `from`, `to`: UTC ISO-8601 시간 범위이며, 생략 시 최근 24시간입니다.
- `page`, `page_size`: 기본값은 각각 `1`, `50`이며 최대 page size는 `200`입니다.
- `level`, `event`, `method`, `user_id`, `feature`, `path`
- `status_min`, `status_max`
- `q`: 메시지, 예외, 오류 이름, 경로, 사용자 식별자를 검색합니다.

잘못된 숫자 값은 라우트에서 `400 invalid_log_query`로 변환합니다. 설정 오류나
OpenSearch 조회 오류는 내부 상세 내용을 노출하지 않고
`503 log_query_failed`와 `Could not query OpenSearch logs` 메시지로 변환합니다.

성공 응답은 `contracts.py`의 `LogQueryResponse`를 따릅니다. office 응답의
`filters`에는 실제로 조회한 `deployment`와 `index_alias`가 포함됩니다. 결과가
없는 경우는 오류가 아니라 `items: []`, `total: 0`인 정상 응답입니다.

## 검증

홈의 deterministic mock 계약을 검증합니다.

```bash
.venv/bin/python -m pytest back_dev_home/admin_logs -q
```

사무실에서 복사한 adapter와 실제 OpenSearch 연결을 검증합니다.

```bash
SKEWNONO_ADMIN_LOGS_PROVIDER=office \
SKEWNONO_LOG_ENV=local \
.venv/bin/python -m pytest back_dev_home/admin_logs -q
```

`office.py`가 없으면 provider 선택기가 정확한 복사 명령을 포함한
`RuntimeError`로 실패합니다. office 모드에는 mock fallback이 없습니다.
