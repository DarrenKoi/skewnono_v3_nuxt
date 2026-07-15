# minio_handler 레시피

`usage.md`가 method 단위 reference라면, 이 문서는 "이런 일을 하고 싶을 때
어떻게 조립하느냐"에 대한 짧은 코드 조각 모음입니다. 모든 예제는
`minio_config.py`에 `BUCKET="user"`, `PREFIX="2067928/"`가 설정돼 있다고
가정합니다. 즉 `mo.put("foo.txt", ...)`의 실제 key는
`user/2067928/foo.txt`입니다.

```python
from minio_handler import MinioObject

mo = MinioObject()   # 모든 예제에서 공통으로 가정
```

## 존재 확인 후 동작

### 있을 때만 삭제

```python
def delete_if_exists(mo: MinioObject, key: str) -> bool:
    if not mo.exists(key):
        return False
    mo.delete(key)
    return True
```

`exists`는 NotFound 류만 잡아 `False`를 돌려주고, 권한/네트워크 오류는
그대로 raise 합니다. 따라서 위 함수는 "조용히 무시"가 아니라 "없으면
스킵, 진짜 문제는 raise"입니다.

### 없을 때만 업로드 (덮어쓰기 방지)

S3에는 원자적 "put if not exists"가 없습니다. race가 중요하지 않은
환경이라면 다음 패턴이면 충분합니다.

```python
def put_if_absent(mo: MinioObject, key: str, data: bytes) -> bool:
    if mo.exists(key):
        return False
    mo.put(key, data)
    return True
```

엄격한 race-free가 필요하면 `If-None-Match` header를 직접 보내야 하는데,
SDK 수준이라 wrapper 범위 밖입니다. 보통은 key에 timestamp/uuid를 넣어
충돌 자체를 피하는 편이 더 단순합니다.

### 있으면 가져오고 없으면 None

```python
def get_or_none(mo: MinioObject, key: str) -> bytes | None:
    if not mo.exists(key):
        return None
    return mo.get(key)
```

`exists` + `get`은 두 번의 HTTP 호출입니다. 매우 빈번한 path라면
`get`만 호출하고 `S3Error`를 잡는 편이 한 번의 round-trip으로 끝납니다.

```python
from minio.error import S3Error

def get_or_none_fast(mo: MinioObject, key: str) -> bytes | None:
    try:
        return mo.get(key)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
            return None
        raise
```

## List 패턴

### 한 디렉터리만 (한 단계 아래)

```python
for obj in mo.list("project_a/", recursive=False):
    print(obj.object_name)
```

`recursive=False`면 S3의 "common prefix" 동작이 들어옵니다. 즉 하위
디렉터리는 하나의 prefix entry로 묶여서 나오고, 그 안의 파일은 펼쳐지지
않습니다.

### 모든 객체 (재귀)

```python
for obj in mo.list("project_a/"):   # recursive=True가 기본
    print(obj.object_name, obj.size)
```

### 키 이름으로 필터

`list`는 server-side 필터를 지원하지 않으므로, prefix를 가능한 좁게 잡고
나머지는 client-side에서 거릅니다.

```python
parquets = [
    obj for obj in mo.list("project_a/results/")
    if obj.object_name.endswith(".parquet")
]
```

날짜 같이 자연스럽게 정렬되는 키라면 prefix를 더 좁히세요. `list`는
사전순으로 돌려주므로 prefix를 정밀화할수록 부담이 줄어듭니다.

```python
today_logs = list(mo.list("logs/2026-05-06/"))
```

### 총 개수 / 총 용량

```python
total_count = 0
total_bytes = 0
for obj in mo.list("project_a/"):
    total_count += 1
    total_bytes += obj.size
print(f"{total_count} objects, {total_bytes / 1_048_576:.1f} MiB")
```

대량 prefix에서는 `list` 자체가 paginate되며 lazy하게 흘러나오므로 메모리
부담은 작습니다. 한꺼번에 전부 메모리에 담는 `list(mo.list(...))`만 피하면
됩니다.

### 가장 최근 객체 한 개

키에 timestamp가 들어 있다면 정렬만으로 끝납니다.

```python
def latest_under(mo: MinioObject, prefix: str) -> str | None:
    keys = (obj.object_name for obj in mo.list(prefix))
    return max(keys, default=None)
```

키에 timestamp가 없다면 `last_modified`로 비교해야 합니다.

```python
def latest_by_mtime(mo: MinioObject, prefix: str):
    return max(mo.list(prefix), key=lambda o: o.last_modified, default=None)
```

후자는 모든 객체를 다 훑어야 하므로 prefix를 좁게 두는 편이 좋습니다.

## Bulk 삭제 패턴

### 키 목록을 직접 알 때

```python
errors = mo.delete_many(["a.txt", "b.txt", "c.txt"])
for err in errors:
    print("failed:", err)
```

`delete_many`는 한 번의 요청으로 여러 객체를 지웁니다. 반환값은 실패한
항목들만 들어 있는 list입니다 (성공은 조용히 끝남).

### 특정 prefix 전체 삭제

```python
mo.delete_prefix("scratch/2026-05-06/")
```

`delete_prefix`는 내부적으로 `list` + `delete_many`를 함께 돌려 줍니다.
default prefix와 합성되므로 위 호출은 실제로
`user/2067928/scratch/2026-05-06/` 아래만 지웁니다.

```python
# 빈 string으로는 호출 거부 (default_prefix만으로도 안 됨 → 안전장치 없음.
# 다음은 위험!)
# mo.delete_prefix("")    # 의도가 분명할 때만 쓰세요
```

### 키 이름 조건으로 일괄 삭제 (`delete_matching`)

key 문자열에 조건이 있을 때 — timestamp가 path 중간에 박혀 있거나, 형식이
제각각이거나, 확장자로 거르고 싶을 때 — `delete_matching`이 `list` + 필터 +
`delete_many`를 한 번에 묶어 줍니다. predicate가 `True`를 돌려준 key만 지우고,
`delete_prefix`와 똑같이 실패 entry list를 반환합니다.

```python
# 파일명 안에 날짜가 박혀 있는 하루치 삭제. prefix로 sem/ 아래만 훑음
errors = mo.delete_matching(lambda k: "2026-06-11" in k, prefix="sem")
```

predicate는 *full key* (`default_prefix`까지 붙은 `object_name`)를 그대로
받습니다 — bucket에 저장된 문자열과 동일합니다. 따라서 `lambda k: ...`
안에서 `k`는 `2067928/sem/...` 형태입니다.

```python
# 확장자로 거르기 — .tmp 산출물 전체
mo.delete_matching(lambda k: k.endswith(".tmp"), prefix="scratch")

# 정규식으로 날짜 범위 거르기
import re
pat = re.compile(r"/2026-06-(0[1-9]|1[0-5])/")   # 6/1 ~ 6/15
mo.delete_matching(lambda k: bool(pat.search(k)), prefix="logs")
```

`prefix`는 **성능 레버**입니다. predicate는 Python 단에서 도는 fine filter일
뿐이고, `prefix`는 그 앞단에서 MinIO에게 server-side로 범위를 좁혀 달라고
넘기는 값입니다. `prefix` 없이 부르면 bucket 전체를 훑어 가며 필터하므로,
가능한 한 좁은 `prefix`를 항상 같이 주세요.

> **언제 `delete_prefix` 대신 이걸 쓰나.** 날짜가 key의 *맨 앞* path 조각이면
> (`sem/2026/06/11/...`) `delete_prefix("sem/2026/06/11")`가 더 낫습니다 —
> MinIO가 server-side로 범위를 좁혀 주니까요. `delete_matching`은 매칭 대상이
> 맨 앞 prefix가 *아닐* 때(파일명 중간, 형식 혼재, 확장자)를 위한 도구입니다.

> **시간 기준(`last_modified`) 삭제에는 못 씁니다.** predicate는 key 문자열만
>받지 `obj.last_modified`는 못 봅니다. "N일 지난 객체" 같은 조건은 아래
> "조건부 일괄 삭제" / "정기 cleanup"의 수동 패턴을 쓰세요.

### 조건부 일괄 삭제 (예: 7일 지난 .tmp 파일)

> key 문자열만으로 거를 수 있다면 위의 `delete_matching`이 더 짧습니다.
> 아래 패턴은 `last_modified` 같은 *객체 metadata*가 필요할 때의 형태입니다.


```python
from datetime import datetime, timedelta, timezone

cutoff = datetime.now(timezone.utc) - timedelta(days=7)
old_tmp = [
    obj.object_name
    for obj in mo.list("scratch/")
    if obj.object_name.endswith(".tmp") and obj.last_modified < cutoff
]
if old_tmp:
    mo.delete_many(old_tmp)
```

`delete_many`에 빈 list를 넘기면 그냥 빈 list를 돌려주므로 `if`로 한 번
더 감쌀 필요는 형식적이지만, 0건일 때 print 같은 후속 동작을 분기하기엔
편합니다.

`object_name`은 default_prefix가 이미 붙은 *full key*입니다.
`delete_many`는 다시 `_resolve_key`를 거치므로, 풀어 보면
`2067928/2067928/...` 가 될 수도 있겠다고 의심이 들 텐데 — 실제로는
`object_name`이 절대 키이고 wrapper의 `delete_many`는 그대로 쓰고 싶을
때 `bucket=`만 넘기는 식이 가장 안전합니다. 즉:

```python
# 안전한 형태: prefix 합성을 우회하기 위해 use_prefix(None)로 잠시 비움
mo.use_prefix(None)
try:
    mo.delete_many(old_tmp)
finally:
    mo.use_prefix("2067928/")
```

또는 prefix가 붙기 전 *짧은* 키를 직접 만들어서 넘깁니다.

```python
short_keys = [
    obj.object_name.removeprefix("2067928/")
    for obj in mo.list("scratch/")
    if obj.object_name.endswith(".tmp")
]
mo.delete_many(short_keys)
```

## Copy / Move

S3에는 native rename이 없습니다. "옮기기"는 항상 *copy → delete*입니다.
서버 사이드 copy는 SDK의 raw API를 직접 써야 합니다.

```python
from minio.commonconfig import CopySource

def move(mo: MinioObject, src: str, dst: str) -> None:
    bucket = mo._resolve_bucket()
    src_full = mo._resolve_key(src)
    dst_full = mo._resolve_key(dst)

    mo.client.copy_object(
        bucket,
        dst_full,
        CopySource(bucket, src_full),
    )
    mo.client.remove_object(bucket, src_full)
```

`copy_object`는 byte 전송 없이 MinIO 안에서 복사하므로 큰 파일에서도
빠릅니다. 5 GiB 초과 파일은 server-side multipart copy가 필요하니 그
경우엔 `compose_object`를 봐야 합니다.

작은 파일이면 `get` + `put`이 가장 단순한 우회로입니다.

```python
mo.put(dst, mo.get(src))
mo.delete(src)
```

이 방식은 wrapper만으로 끝나는 대신 byte를 전부 한 번 다운/업로드하므로
사이즈가 크면 비쌉니다.

## Metadata 검사

### content-type / etag / size로 분기

```python
stat = mo.stat("report.json")
if stat.content_type != "application/json":
    raise ValueError("not a JSON object")
if stat.size > 10 * 1024 * 1024:
    raise ValueError("too large")
data = mo.get("report.json")
```

`stat`은 객체 본문을 받지 않으므로 매우 가볍습니다. 큰 파일을 받기 전에
`stat`로 size를 보고 거르는 게 좋은 습관입니다.

### 사용자 metadata 읽기

```python
mo.put("report.json", b"{}", metadata={"x-experiment-id": "exp-204"})
stat = mo.stat("report.json")
print(stat.metadata)
# 응답에서는 헤더 형태로 나옵니다:
#   x-amz-meta-x-experiment-id: exp-204
```

업로드할 때는 `x-amz-meta-` 접두어 없이 키만 주면 됩니다. 서버가 prefix를
자동으로 붙입니다. 다시 읽을 때는 prefix가 붙은 형태로 옵니다.

## 상위 도메인 객체 처리

### JSON / Pickle / DataFrame을 키 하나에 안전하게

```python
mo.put_json("config/run-204.json", {"lr": 1e-3, "epochs": 10})
cfg = mo.get_json("config/run-204.json")

mo.put_pickle("models/run-204.pkl", trained_model)
model = mo.get_pickle("models/run-204.pkl")   # 신뢰된 데이터에만 사용

import pandas as pd
df = pd.DataFrame({"x": [1, 2, 3]})
mo.put_dataframe("frames/run-204.parquet", df)
df_back = mo.get_dataframe("frames/run-204.parquet")
```

`put_pickle`/`get_pickle`은 임의 코드 실행 위험이 있으므로 외부에서 받은
데이터에는 절대 쓰지 마세요.

### "있으면 캐시, 없으면 계산해서 저장"

```python
def cached(key: str, build):
    """build()는 비싸므로 한 번만 계산해서 MinIO에 캐싱."""

    if mo.exists(key):
        return mo.get_pickle(key)
    value = build()
    mo.put_pickle(key, value)
    return value
```

여러 worker가 동시에 같은 key를 빌드할 수 있다면, 이긴 worker의 값으로
조용히 덮어쓰기됩니다. 정합성이 중요하면 key에 worker id를 넣고 마지막에
하나로 promote 하는 패턴을 쓰세요.

## Presigned URL 짧은 레시피

### 단일 다운로드 링크 (브라우저로 열어 받기)

```python
from datetime import timedelta

url = mo.presigned_get_url("reports/q1.pdf", expires=timedelta(minutes=15))
```

### "다른 이름으로 저장" 강제

```python
url = mo.presigned_get_url(
    "reports/q1.pdf",
    expires=timedelta(hours=1),
    response_headers={
        "response-content-disposition": 'attachment; filename="2026-Q1.pdf"',
    },
)
```

### 브라우저 직접 업로드용 PUT URL

```python
upload_url = mo.presigned_put_url("uploads/raw.bin", expires=timedelta(minutes=10))
# 프런트엔드에서 fetch(upload_url, { method: "PUT", body: file })
```

자세한 운영 패턴(만료 정책, 7일 초과 우회, Flask 통합)은
`usage.md`의 "Presigned URL" 섹션을 보세요.

## 정기 cleanup (lifecycle 대용)

> 사내 환경에서는 bucket lifecycle 정책을 직접 등록할 권한이 없습니다.
> wrapper에서도 lifecycle 메서드는 제거했습니다. retention은 Airflow DAG
> 또는 cron으로 직접 돌리는 cleanup job으로 처리합니다.

### N일 지난 date 폴더 삭제 (`delete_older_than`)

`YYYY/MM/DD` 폴더로 적재하는 데이터는 손으로 짠 purge 루프가 필요 없습니다.
`MinioObject`에 1급 메서드 `delete_older_than(days, base, *, dry_run=False)`이
있습니다. `base` 아래의 date 폴더를 cheap한 non-recursive walk로 찾고 (날짜로
파싱되지 않는 폴더는 건너뜀), `today_KST - days` 컷오프보다 **앞선** 날짜의
폴더만 골라 하루치씩 `remove_objects`로 일괄 삭제합니다. 최근 `days`일은
(오늘 포함) 보존됩니다.

```python
mo.delete_older_than(7,   "scratch")    # scratch/YYYY/MM/DD 중 7일 지난 폴더
mo.delete_older_than(30,  "logs")       # logs/ 아래 30일 지난 폴더
mo.delete_older_than(365, "archive")    # archive/ 아래 1년 지난 폴더
```

컷오프 기준은 객체의 `last_modified`가 아니라 **폴더 경로의 날짜**입니다.
date 폴더 구조가 아닌 평평한 prefix를 last_modified로 거르고 싶다면 위의
`delete_matching`을 쓰세요.

### Airflow DAG에서

이미 있는 `airflow_mgmt`의 `minio_purge` DAG가 이 패턴입니다. 새 base가
필요하면 거기 task 하나를 추가하는 식으로 운영하세요.

```python
# dags/example_purge.py (참고용 스케치)
from datetime import datetime
from airflow.sdk import dag, task

@dag(
    schedule="0 3 * * *",   # 매일 03:00 KST
    start_date=datetime(2026, 5, 1),
    catchup=False,
)
def scratch_purge():
    @task
    def purge():
        from minio_handler import MinioObject
        mo = MinioObject()
        result = mo.delete_older_than(7, "scratch")
        return [f.path for f in result.folders]

    purge()

scratch_purge()
```

### 빈 디렉터리 (prefix) 정리

S3에는 디렉터리가 없으므로 "빈 디렉터리 삭제"라는 동작 자체가 필요하지
않습니다. 안에 객체가 0개면 prefix는 listing 결과에 나타나지 않습니다.
어쩌다 placeholder 파일 (`.keep` 등)을 남겨 두는 컨벤션이라면, 그 placeholder만
직접 `mo.delete(...)`로 지우면 됩니다.

### 통계만 보고 싶을 때

실제로 지우기 전에 영향 범위를 미리 보려면 `delete_older_than`을
`dry_run=True`로 부르세요. 삭제는 하지 않고 선택될 폴더 목록만 돌려줍니다.
폴더 전체를 그냥 훑어보고 싶으면 `list_date_folders`를 쓰면 됩니다.

```python
result = mo.delete_older_than(30, "logs", dry_run=True)
for folder in result.folders:
    print("would delete", folder.path)

# 또는 전체 date 폴더 목록만:
for folder in mo.list_date_folders("logs"):
    print(folder.date, folder.path)
```

## 관련 문서

- `usage.md` — 전체 method reference, 환경 설정, 자주 하는 실수
- `concepts.md` — bucket / key / metadata / consistency 등 S3 개념
- `data_management.md` — key naming, partitioning, retention 패턴
- `serialization.md` — DataFrame ↔ Parquet, PIL.Image ↔ PNG/JPEG 등
- `web_integration.md` — Flask 통합 (proxy / presigned URL / multipart)
