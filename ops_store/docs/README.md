# ops_store 문서

이 폴더는 `ops_store`를 **Airflow `with DAG(...) as dag:` 형식에서 사용하는
방법**만 다룹니다. 예전처럼 Flask app, standalone script, mapping reference,
ISM reference, logging strategy를 파일별로 나누지 않습니다.

## 문서 구성

- `with_dag_usage.md`: DAG 파일 구조, `ops_store` import, OpenSearch 연결,
  index bootstrap, bulk ingest, search, rollover/ISM, logging/testing 규칙

## 기준

- DAG 예제는 모두 `from airflow.sdk import DAG`와
  `with DAG(...) as dag:` context manager 형식을 사용합니다.
- Python 실행 task는 `PythonOperator`로 명시합니다.
- `@dag`, `@task` TaskFlow 예제는 이 문서 범위에 넣지 않습니다.
- `ops_store`는 OpenSearch client를 얇게 감싼 helper입니다. OpenSearch의
  mapping, query, alias, rollover body를 숨기지 않습니다.
- Airflow worker에서 읽히는 `OPENSEARCH_*` OS environment variable을 기본
  연결 방식으로 봅니다. Airflow UI Variable은 `ops_store`가 자동으로 읽지
  않습니다.

## 언제 이 문서를 보면 되는가

- Airflow DAG에서 OpenSearch index를 만들거나 확인해야 할 때
- DAG task에서 record를 OpenSearch에 bulk indexing 해야 할 때
- DAG task에서 최신 document, sample, aggregation 결과를 조회해야 할 때
- rollover alias 또는 간단한 ISM policy를 DAG 운영 흐름에 연결해야 할 때
