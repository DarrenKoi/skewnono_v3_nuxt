# OSSearch DataFrame 조회 가이드

이 문서는 `OSSearch`가 제공하는 DataFrame 변환 메서드, 특히 10k 한계를
넘어서 row를 가져오는 `*_dataframe_all` 계열의 사용법을 정리합니다.
모든 예제는 `pandas`가 설치되어 있다고 가정합니다.

## 메서드 선택 기준

| 상황 | 사용할 메서드 | 비고 |
| --- | --- | --- |
| row 수 ≤ 10,000, 단순 query | `search_dataframe(body)` | 한 번의 `search` 호출 |
| 최근 N일 데이터를 빠르게 보고 싶음 | `range_dataframe(time_field=..., days=...)` | 기본값 `timestamp` / 7일, single-shot (`size` cap) |
| 최근 N일이지만 10k를 넘을 수 있음 | `range_dataframe_all(time_field=..., days=..., max_rows=N)` | scroll 기반 |
| match query 결과 전체가 필요 | `match_dataframe_all(field, query)` | scroll 기반 |
| 특정 field가 keyword와 매칭되는 **최신** row만 | `latest_match_dataframe(field, keyword)` | match + 시간 desc, 기본 `size=1` |
| 임의 query 결과 전체가 필요 | `search_dataframe_all(body)` | scroll 기반, body 직접 작성 |
| row가 수백만 쏟아질 수 있음 | `*_dataframe_all(..., max_rows=N)` | N개에서 잘림 |

## 10,000 한계가 어디서 오는가

OpenSearch 단일 `search` request는 index setting
`index.max_result_window`(기본 10,000)에서 막힙니다. 이 값을 키우는 대신
scroll API를 쓰는 것이 cluster에 안전합니다. `*_dataframe_all` 메서드들은
모두 scroll API를 wrapping합니다.

## 기본 사용

```python
from ops_store import OSSearch

search = OSSearch(client, index="my_index")

# 1) 단건 search → DataFrame (≤ 10k)
df = search.search_dataframe(
    {"query": {"term": {"status": "ok"}}, "size": 5000}
)

# 2) 최근 7일, timestamp 컬럼 (default)
df = search.range_dataframe()

# 3) 최근 30일, 다른 시간 컬럼, caller query AND
df = search.range_dataframe(
    time_field="event_tm",
    days=30,
    query={"term": {"status": "ok"}},
)
```

## scroll로 전부 가져오기

```python
body = {
    "query": {"range": {"timestamp": {"gte": "now-30d", "lte": "now"}}},
    "sort": [{"timestamp": {"order": "desc"}}],
}

df = search.search_dataframe_all(
    body,
    batch_size=2000,   # 한 scroll page에서 받는 hit 수
    scroll="2m",       # scroll context 유지 시간
)
```

- `batch_size`: 1,000~5,000 정도가 일반적입니다. 너무 작으면 round trip이
  늘고, 너무 크면 coordinator node 메모리를 더 씁니다.
- `scroll`: page 간 처리 시간이 길어지는 경우 `"5m"` 등으로 늘립니다.
- 함수가 return하기 직전 scroll context는 `clear_scroll`로 정리됩니다.
  중간에 exception이 나도 `try/finally`로 정리됩니다.

## `max_rows`로 상한선 두기

기본값은 `None`(전부 가져옴)이라 query가 의도보다 큰 결과를 매칭하면
수백만 row가 client로 흘러옵니다. opt-in 상한을 걸어두면 안전합니다.

```python
df = search.search_dataframe_all(
    body,
    batch_size=5000,
    max_rows=50000,   # 5만 개 이후로는 잘림
)
```

- `max_rows=N`이면 결과는 정확히 N개 이하입니다. `batch_size`가 N보다
  크게 설정돼 있어도 마지막에 client-side로 truncate합니다.
- 잘렸는지 알고 싶으면 `len(df) == max_rows`를 확인하거나, 미리
  `search.count(query)`로 매칭 수를 점검합니다.
- 잘림 상황에서 경고/로그를 띄우지 않습니다. caller가 판단합니다.

## query 매칭 row 수를 미리 확인

```python
total = search.count({"range": {"timestamp": {"gte": "now-30d"}}})["count"]
if total > 200000:
    raise RuntimeError(f"too many rows: {total}")

df = search.search_dataframe_all(body, max_rows=200000)
```

`count`는 hit를 받지 않고 매칭 수만 받아오는 가벼운 호출입니다.
큰 pull 직전 한 번 찍어보는 패턴이 가장 신뢰할 만합니다.

## `match_dataframe_all` 단축형

`{"query": {"match": {field: value}}}` body를 직접 만들고 싶지 않을 때:

```python
df = search.match_dataframe_all(
    "title",
    "flask",
    batch_size=1000,
    max_rows=20000,
    include_meta=True,   # _id, _index, _score 컬럼 포함
)
```

## `latest_match_dataframe` (keyword 매칭 + 최신순)

특정 field가 keyword와 매칭되는 document 중 **가장 최근 것**만 DataFrame으로
받고 싶을 때 씁니다. `match` query로 거른 뒤 `time_field` 기준 내림차순으로
정렬해 상위 `size`개(기본 1 = 최신 한 건)를 돌려줍니다.

```python
search = OSSearch(client, index="people")

# 1) fullname이 "Jane Doe"와 매칭되는 최신 한 건
df = search.latest_match_dataframe("fullname", "Jane Doe")

# 2) 최신 5건, 다른 시간 field, 메타 컬럼 포함
df = search.latest_match_dataframe(
    "fullname",
    "Jane Doe",
    size=5,
    time_field="event_tm",   # 기본값 "timestamp"
    include_meta=True,        # _id, _index, _score 컬럼 포함
)
```

- `latest()` 위에 얹은 single-shot 헬퍼라, 검색 전에 mapping을 확인해
  `time_field`가 `date` / `date_nanos`인지 검증합니다. index가 없으면 빈
  DataFrame을 돌려줍니다.
- `match` query라 `text` field와 `keyword` field 모두에서 동작합니다.
  엄격한 정확 일치(term)가 필요하면 `term`을 직접 build해 `latest(query=...)`를
  쓰세요.
- 결과 전체(>10k)가 아니라 "최신 몇 건"만 필요할 때 쓰는 메서드입니다.
  전부 필요하면 `match_dataframe_all`을 보세요.

## DataFrame 메타 컬럼

`include_meta=True`를 주면 row마다 `_id`, `_index`, `_score`가 컬럼으로
포함됩니다. 후속 작업에서 OpenSearch document를 다시 업데이트하거나
참조해야 할 때 켭니다.

## `range_dataframe_all` (range + scroll + max_rows)

10k를 넘길 가능성이 있는 시간 범위 조회는 이 메서드를 씁니다. 인자는
`range_dataframe`과 거의 같지만 `size` 대신 scroll knobs(`batch_size`,
`scroll`)와 `max_rows`가 있습니다.

```python
df = search.range_dataframe_all(
    time_field="timestamp",
    days=30,
    query={"term": {"status": "ok"}},  # range와 AND
    batch_size=2000,
    max_rows=100000,
)
```

- `size` 인자가 없는 이유: scroll이 페이지 단위로 받기 때문에 한 번에
  몇 개를 받을지 결정하는 값은 `batch_size`, 전체 상한은 `max_rows`로
  분리되어 있습니다.
- `range_search` / `range_dataframe`은 single-shot이라 `size`가 곧 cap입니다.
  `max_rows`를 따로 받지 않습니다.

## scroll 메서드 사용 시 주의

- scroll은 search-after와 달리 cluster에 context를 남기므로, 같은 task에서
  여러 query를 병렬로 scroll하면 메모리 압박이 생길 수 있습니다.
- DAG task에서 호출할 때는 `pandas`가 worker virtualenv에 있는지 먼저
  확인합니다(`OSSearch._require_pandas`는 없으면 `ImportError`를 던집니다).
