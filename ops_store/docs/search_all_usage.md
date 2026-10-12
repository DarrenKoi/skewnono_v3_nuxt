# OSSearch DataFrame 조회 가이드

이 문서는 `OSSearch`가 제공하는 DataFrame 변환 메서드, 특히 10k 한계를
넘어서 row를 가져오는 `*_dataframe_all` 계열의 사용법을 정리합니다.
모든 예제는 `pandas`가 설치되어 있다고 가정합니다.

## 메서드 선택 기준

| 상황 | 사용할 메서드 | 비고 |
| --- | --- | --- |
| row 수 ≤ 10,000, 단순 query | `search_dataframe(body)` | 한 번의 `search` 호출 |
| 최근 N일 데이터를 빠르게 보고 싶음 | `range_dataframe(time_field=..., days=...)` | 기본값 `timestamp` / 7일, single-shot (`size` cap) |
| 최근 N일이지만 10k를 넘을 수 있음 | `range_dataframe_all(time_field=..., days=..., max_rows=N)` | search_after 기반 |
| match query 결과 전체가 필요 | `match_dataframe_all(field, query)` | search_after 기반 |
| 특정 field가 keyword와 매칭되는 **최신** row만 | `latest_match_dataframe(field, keyword)` | match + 시간 desc, 기본 `size=1` |
| 임의 query 결과 전체가 필요 | `search_dataframe_all(body)` | search_after 기반, body 직접 작성 |
| row가 수백만 쏟아질 수 있음 | `*_dataframe_all(..., max_rows=N)` | N개에서 잘림 |

## 10,000 한계가 어디서 오는가

OpenSearch 단일 `search` request는 index setting
`index.max_result_window`(기본 10,000)에서 막힙니다. 이 값을 키우는 대신
`search_after`로 페이지를 나눠 받는 것이 cluster에 안전합니다.
`*_dataframe_all` 메서드들은 모두 `search_after` 페이지네이션을 wrapping합니다.
(이전에는 scroll API를 썼지만, OpenSearch 3.7 클러스터에서 결과가 클 때
문서가 조용히 누락되어 교체했습니다.)

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

## search_after로 전부 가져오기

```python
body = {
    "query": {"range": {"timestamp": {"gte": "now-30d"}}},
    "sort": [{"timestamp": {"order": "desc"}}],
}

df = search.search_dataframe_all(
    body,
    batch_size=2000,   # 한 page에서 받는 hit 수
)
```

- `batch_size`: 1,000~5,000 정도가 일반적입니다. 너무 작으면 round trip이
  늘고, 너무 크면 coordinator node 메모리를 더 씁니다.
- `scroll`: 더 이상 쓰이지 않습니다. 기존 호출부가 깨지지 않도록 인자만
  남아 있습니다.
- body의 `sort`는 그대로 유지되고, 그 뒤에 `_id` 오름차순이 tiebreaker로
  붙습니다. `sort`가 없으면 `_id` 오름차순만 적용됩니다.
- `track_total_hits`는 `False`로 보냅니다. 전체 개수를 세는 비용이 필요
  없기 때문입니다.
- cluster에 context를 남기지 않으므로 정리할 것이 없습니다. 대신 snapshot이
  아니므로, 조회 도중 색인된 문서는 정렬 위치에 따라 포함될 수도 빠질 수도
  있습니다.

## range 조회에는 상한(`lte`)이 없습니다

`range_search` / `range_dataframe` / `range_dataframe_all`은 `gte`만 보내고
`lte: "now"`는 붙이지 않습니다. KST 실제 시각을 offset 없이 색인한 index는
OpenSearch가 그 값을 UTC로 해석하므로, 최신 문서가 `now`보다 최대 9시간
"미래"에 놓입니다. `lte: "now"`가 있으면 그 9시간분이 조용히 빠집니다.

같은 이유로 `gte`의 `now-Nd`도 9시간 어긋나 있습니다. 이쪽은 요청보다
9시간 더 오래된 문서까지 포함되는 방향이라 누락은 생기지 않습니다. body를
직접 작성할 때도 이런 index에는 `lte: "now"`를 넣지 않습니다.

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

## `range_dataframe_all` (range + search_after + max_rows)

10k를 넘길 가능성이 있는 시간 범위 조회는 이 메서드를 씁니다. 인자는
`range_dataframe`과 거의 같지만 `size` 대신 `batch_size`와 `max_rows`가
있습니다.

```python
df = search.range_dataframe_all(
    time_field="timestamp",
    days=30,
    query={"term": {"status": "ok"}},  # range와 AND
    batch_size=2000,
    max_rows=100000,
)
```

- `size` 인자가 없는 이유: 페이지 단위로 받기 때문에 한 번에
  몇 개를 받을지 결정하는 값은 `batch_size`, 전체 상한은 `max_rows`로
  분리되어 있습니다.
- `range_search` / `range_dataframe`은 single-shot이라 `size`가 곧 cap입니다.
  `max_rows`를 따로 받지 않습니다.

## `*_dataframe_all` 메서드 사용 시 주의

- 실제 page 크기는 `batch_size`와 `max_rows` 중 작은 값입니다.
- DAG task에서 호출할 때는 `pandas`가 worker virtualenv에 있는지 먼저
  확인합니다(`OSSearch._require_pandas`는 없으면 `ImportError`를 던집니다).
