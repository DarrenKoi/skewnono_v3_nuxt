# ops_store with DAG 사용 가이드

이 문서는 `ops_store`를 Airflow DAG 안에서 사용하는 실전 형식만 정리합니다.
모든 예제는 `with DAG(...) as dag:` 형식입니다.

## 기본 원칙

- DAG 파일은 schedule, dependency, operator wiring만 담당합니다.
- 실제 업무 로직은 plain Python 함수 또는 `scripts/` helper로 분리합니다.
- `ops_store` import는 Airflow worker의 `sys.path`가 repository root를 볼 수
  있게 만든 뒤 수행합니다.
- 연결 정보는 `OPENSEARCH_*` OS environment variable에서 읽습니다.
- 실패를 숨기지 않습니다. OpenSearch write/search가 실패하면 task가 red가
  되도록 exception을 그대로 올립니다.

## `ops_store`가 제공하는 것

| class/function | DAG에서의 용도 |
| --- | --- |
| `OSIndex` | index 생성, mapping/settings 적용, alias/rollover 확인, ISM policy 생성 |
| `OSDoc` | 단건 `index`, `upsert`, `delete`, `bulk_index`, 중복 `_id` 건너뛰는 `bulk_create`, raw bulk action 실행 |
| `OSSearch` | raw search, `match`, `term`, `filter_terms`, `latest`, `sample`, aggregation |
| `OSConfig` | 환경 변수 대신 명시적 연결 설정이 필요할 때 사용 |
| `create_client` | 여러 service가 같은 OpenSearch client를 공유해야 할 때 사용 |
| `normalize_document` | `datetime`, `Decimal`, `NaN` 등을 JSON-safe 값으로 변환 |

## DAG 파일 기본 골격

`airflow_mgmt`의 기존 DAG들은 `airflow_mgmt/project_root.txt`를 찾아
`airflow_mgmt/`를 `sys.path`에 넣는 패턴을 씁니다. 하지만 `ops_store/`는
repository top-level package이므로, `ops_store/__init__.py`가 있는 directory를
찾아 `sys.path`에 넣어야 합니다.

```python
import logging
import sys
from datetime import datetime
from pathlib import Path

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

log = logging.getLogger(__name__)


def _find_repo_root() -> Path:
    try:
        start = Path(__file__).resolve().parent
    except NameError:
        start = Path.cwd().resolve()

    for path in (start, *start.parents):
        if (path / "ops_store" / "__init__.py").is_file():
            return path
    raise RuntimeError(f"ops_store package not found above {start}")


ROOT_DIR = _find_repo_root()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ops_store import OSDoc, OSIndex, OSSearch  # noqa: E402
```

이 bootstrap은 DAG file 위치가 `airflow_mgmt/dags/...`여도 위로 올라가며
`C:\Code\flask_modules` 같은 repository root를 찾습니다.

## 연결 설정

`OSDoc(index="...")`, `OSIndex(index="...")`, `OSSearch(index="...")`처럼
service를 만들면 내부에서 `load_config()`가 호출되고 다음 환경 변수를 읽습니다.

| env var | 의미 |
| --- | --- |
| `OPENSEARCH_HOST` | OpenSearch host |
| `OPENSEARCH_PORT` | OpenSearch port |
| `OPENSEARCH_USER` / `OPENSEARCH_PASSWORD` | basic auth 계정 |
| `OPENSEARCH_USE_SSL` | `true`면 https |
| `OPENSEARCH_VERIFY_CERTS` | TLS certificate 검증 여부 |
| `OPENSEARCH_SSL_SHOW_WARN` | TLS warning 표시 여부 |
| `OPENSEARCH_CA_CERTS` | CA bundle path |
| `OPENSEARCH_BULK_CHUNK` | bulk helper chunk size |
| `OPENSEARCH_TIMEOUT` | request timeout |
| `OPENSEARCH_MAX_RETRIES` | retry 횟수 |
| `OPENSEARCH_RETRY_ON_TIMEOUT` | timeout retry 여부 |
| `OPENSEARCH_HTTP_COMPRESS` | HTTP compression 여부 |

Airflow UI Variable은 `ops_store`가 자동으로 읽지 않습니다. Airflow Variable을
쓰고 싶다면 DAG task 안에서 직접 읽고 `OSConfig`나 service keyword argument로
넘깁니다.

```python
from airflow.sdk import Variable
from ops_store import OSConfig, OSDoc


def write_with_variable_host() -> None:
    config = OSConfig(
        host=Variable.get("opensearch_host"),
        user=Variable.get("opensearch_user"),
        password=Variable.get("opensearch_password"),
    )
    OSDoc(config=config, index="recipe-events").index({"status": "ok"})
```

## 전체 예제: index 확인 후 bulk ingest

이 예제는 하나의 DAG에서 index alias를 준비하고 record를 bulk indexing한 뒤
최신 document를 확인합니다.

```python
import logging
import sys
from datetime import datetime
from pathlib import Path

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

log = logging.getLogger(__name__)


def _find_repo_root() -> Path:
    try:
        start = Path(__file__).resolve().parent
    except NameError:
        start = Path.cwd().resolve()
    for path in (start, *start.parents):
        if (path / "ops_store" / "__init__.py").is_file():
            return path
    raise RuntimeError(f"ops_store package not found above {start}")


ROOT_DIR = _find_repo_root()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ops_store import OSDoc, OSIndex, OSSearch  # noqa: E402


INDEX_PREFIX = "recipe-events"
WRITE_ALIAS = "recipe-events-write"

MAPPINGS = {
    "dynamic": "strict",
    "properties": {
        "event_id": {"type": "keyword"},
        "tool_id": {"type": "keyword"},
        "status": {"type": "keyword"},
        "message": {"type": "text"},
        "event_tm": {"type": "date"},
    },
}


def ensure_index() -> dict:
    index = OSIndex()
    if index.alias_exists(WRITE_ALIAS):
        return index.describe(WRITE_ALIAS)

    return index.create(
        index=f"{INDEX_PREFIX}-000001",
        mappings=MAPPINGS,
        aliases={WRITE_ALIAS: {"is_write_index": True}},
        shards=1,
        replicas=0,
    )


def collect_records() -> list[dict]:
    return [
        {
            "event_id": "recipe-001",
            "tool_id": "CDSEM-01",
            "status": "ok",
            "message": "recipe log parsed",
            "event_tm": datetime.utcnow(),
        }
    ]


def ingest_records() -> dict:
    records = collect_records()
    success, errors = OSDoc(index=WRITE_ALIAS).bulk_index(
        records,
        id_field="event_id",
        normalize=True,
        raise_on_error=False,
    )

    if errors:
        raise RuntimeError(f"OpenSearch bulk errors: {errors[:3]}")

    result = {"success": success, "error_count": len(errors)}
    log.info("bulk ingest result: %s", result)
    return result


def check_latest() -> dict | None:
    result = OSSearch(index=WRITE_ALIAS).latest("event_tm", size=1)
    log.info("latest result: %s", result)
    return result


with DAG(
    dag_id="recipe_events_to_opensearch",
    description="Ingest recipe event records into OpenSearch",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["opensearch", "recipe-events"],
) as dag:
    ensure_index_task = PythonOperator(
        task_id="ensure_index",
        python_callable=ensure_index,
    )

    ingest_records_task = PythonOperator(
        task_id="ingest_records",
        python_callable=ingest_records,
    )

    check_latest_task = PythonOperator(
        task_id="check_latest",
        python_callable=check_latest,
    )

    ensure_index_task >> ingest_records_task >> check_latest_task
```

## Mapping은 짧게 유지하고 명시적으로 둔다

DAG 문서에서는 긴 mapping reference를 따로 두지 않습니다. 실무 기준은 다음만
기억하면 충분합니다.

- production index는 `dynamic: "strict"`를 기본으로 둡니다.
- ID, status, category, exact match field는 `keyword`를 씁니다.
- 자연어 검색 대상은 `text`를 씁니다.
- 시간 정렬, `latest()` 대상 field는 `date` 또는 `date_nanos`여야 합니다.
- object array를 element 단위로 정확히 검색해야 하면 `nested`를 씁니다.
- mapping은 대부분 immutable입니다. type을 바꿔야 하면 새 index를 만들고
  reindex하거나 rollover로 새 write index부터 새 mapping을 적용합니다.

## Skip-if-exists ingest (`bulk_create`)

`bulk_index()`는 같은 `_id`가 있으면 overwrite하지만, `bulk_create()`는
OpenSearch bulk `create` op type을 써서 **이미 존재하는 `_id`는 건너뜁니다**
(HTTP 409). 같은 batch를 다시 돌려도 기존 document를 덮어쓰지 않으므로
append-only log나 idempotent ingest에 그대로 씁니다.

`_id`는 각 dict의 `id_field`(기본 `"_id"`) 에서 꺼내 document `_id`로 올리고,
`_source`에는 저장하지 않습니다. 반환값 `BulkCreateResult`는 새로 쓴 건수
`created`, 이미 있어서 건너뛴 `skipped`, 그리고 409가 아닌 실제 실패만 담는
`errors`를 분리해서 돌려줍니다.

```python
from ops_store import OSDoc


def ingest_skip_existing(records: list[dict]) -> dict:
    result = OSDoc(index="recipe-events-write").bulk_create(
        records,
        id_field="event_id",   # 이 key를 _id로 올림. 생략하면 각 dict의 "_id" 사용
        normalize=True,        # datetime/Decimal/NaN/numpy 값을 JSON-safe로 변환
    )
    if result.errors:
        raise RuntimeError(f"bulk_create errors: {result.errors[:3]}")
    return {"created": result.created, "skipped": result.skipped}
```

### `_id`를 dict list에 직접 넣기

`_id`를 본인이 계산해서 각 dict에 넣어두고 기본 `id_field="_id"`로 넘기는
패턴입니다. composite key는 여러 field를 이어 붙여 만듭니다.

```python
# 단일 field를 _id로
records = [{"_id": r["event_id"], **r} for r in raw_records]

# composite _id (예: tool_id + event_id + timestamp)
records = [
    {"_id": f"{r['tool_id']}:{r['event_id']}:{r['timestamp']}", **r}
    for r in raw_records
]

OSDoc(index="recipe-events-write").bulk_create(records)
```

`_id`는 metadata이므로 `bulk_create`가 `_source`에서 자동으로 빼냅니다.
즉 위 `{"_id": ..., **r}`에서 `_id` key만 빠지고 나머지 field는 그대로
저장됩니다. 별도 field로도 남기고 싶으면 다른 이름으로 한 번 더 넣으세요
(예: `{"_id": cid, "composite_id": cid, **r}`).

### `id_field`로 다른 key를 id로 지정하기

dict를 새로 만들지 않고, 이미 들고 있는 field를 그대로 `_id`로 쓰고 싶을 때는
`id_field`에 그 key 이름을 넘깁니다. 해당 key는 꺼내서 document `_id`로 올라가고
`_source`에는 저장되지 않습니다.

```python
records = [
    {"event_id": "recipe-001", "tool_id": "CDSEM-01", "status": "done"},
    {"event_id": "recipe-002", "tool_id": "CDSEM-02", "status": "failed"},
]

result = OSDoc(index="recipe-events-write").bulk_create(
    records,
    id_field="event_id",   # event_id를 _id로 올림 → _source에는 tool_id, status만 남음
)
# 위 records의 _id는 각각 "recipe-001", "recipe-002"가 되고,
# 다시 같은 batch를 돌리면 result.skipped == 2 (전부 이미 존재)
```

`id_field`로 지정한 key가 `_source`에서 빠지는 게 싫다면(= id로도 쓰고 field로도
남기고 싶다면), `id_field`를 쓰지 말고 위의 "직접 넣기"처럼 `_id`를 따로 넣으세요:
`{"_id": r["event_id"], **r}`.

## Search task 예제

```python
from ops_store import OSSearch


def count_failed_events() -> dict:
    return OSSearch(index="recipe-events-write").count(
        {"term": {"status": "failed"}}
    )


def latest_for_tool() -> dict | None:
    return OSSearch(index="recipe-events-write").latest(
        "event_tm",
        size=1,
        query={"term": {"tool_id": "CDSEM-01"}},
    )


def status_values() -> list:
    return OSSearch(index="recipe-events-write").unique_values("status")
```

`latest()`는 검색 전에 mapping을 확인합니다. 지정한 field가 없거나 `date` /
`date_nanos`가 아니면 `ValueError`가 발생하고 task가 실패합니다.

## Rollover task 예제

rollover는 write alias 기준으로 실행합니다. 새 index 이름을 직접 주지 않으면
OpenSearch가 현재 write index의 숫자 suffix를 증가시킵니다.

```python
from ops_store import OSIndex


def rollover_if_needed() -> dict:
    return OSIndex(index="recipe-events-write").rollover(
        conditions={
            "max_age": "30d",
            "max_size": "20gb",
            "max_docs": 5_000_000,
        }
    )
```

rollover를 쓰려면 최초 index 이름이 `recipe-events-000001`처럼 숫자 suffix를
가져야 하고, alias에 `is_write_index: True`가 있어야 합니다. 상태 확인은
`OSIndex().describe("recipe-events-write")`로 합니다.

## ISM policy를 DAG로 관리할 때

`create_ism_policy()`는 hot state에서 rollover를 실행하고, retention이 있으면
delete state로 넘기는 최소 lifecycle body를 만듭니다. 복잡한 hot/warm/cold
구성은 OpenSearch body를 직접 관리하는 편이 낫습니다.

```python
from ops_store import OSIndex


def ensure_policy() -> dict:
    return OSIndex().create_ism_policy(
        policy_id="recipe-events-retention",
        index_pattern="recipe-events-*",
        rollover_conditions={"min_size": "20gb", "min_index_age": "30d"},
        retention_age="180d",
        description="recipe event retention policy",
    )
```

`ism_template`은 pattern에 맞는 새 index에만 자동 적용됩니다. 이미 존재하는
index에는 필요할 때 `attach_ism_policy(policy_id, index)`를 별도 task로 호출합니다.

## Logging 기준

`ops_store`는 자체적으로 OpenSearch 호출을 logging하지 않습니다. DAG에서는 다음
기준을 사용합니다.

- task 시작/종료, 처리 건수, bulk error 요약은 Airflow task log에 남깁니다.
- OpenSearch cluster 상태와 query 성능은 OpenSearch/Kibana에서 봅니다.
- 업무 request path 안에서 logging 자체를 OpenSearch write에 강하게 묶지 않습니다.
- 실패 detail은 너무 길 수 있으므로 Airflow log에는 앞부분만 남기고 task는
  exception으로 실패시킵니다.

## 테스트 기준

`ops_store` 단위 테스트는 live OpenSearch cluster를 요구하지 않습니다. client를
mocking해서 request body와 return value를 검증합니다.

```bash
python3 -m unittest tests.test_ops_store_services.OSDocTests -v
python3 -m unittest tests.test_ops_store_services.OSIndexTests -v
python3 -m unittest tests.test_ops_store_services.OSSearchTests -v
```

Airflow DAG 파일을 추가했다면 DAG integrity test도 실행합니다.

```bash
python3 -m pytest airflow_mgmt/tests -v
```

문서만 바꿨다면 최소 확인은 다음으로 충분합니다.

```bash
git diff --check -- ops_store/docs
```
