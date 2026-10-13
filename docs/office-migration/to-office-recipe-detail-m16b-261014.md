# recipe-search 4xx/5xx 와 fab_name=M16B 원인 확인 — Home → Office (2026-10-14)

- 작성일: 2026-10-13입니다.
- 수신자: 사무실에서 SKEWNONO를 실행·확인하는 Office agent입니다.
- 목적: 활동 로그에 recipe-search 쪽 4xx/5xx 가 있고, 그 행들에 `M16B` 가 들어
  있습니다. 집에서 코드를 추적한 결과 **M16B 를 기본값으로 고르는 코드는 없습니다**.
  M16B 는 세 가지 중 하나로 들어옵니다. (가) 다중 fab 목록 조회 `R3,M16B` 가 실패했는데
  로그가 콤마를 쪼개 저장해 M16B 로 보이는 경우, (나) 데이터(meas_hist)가 M16B 라고
  태그한 행에서 상세를 연 경우, (다) 링크에 소유 fab 이 없어 사이드바 첫 fab 으로
  떨어진 경우입니다. 어느 쪽인지에 따라 고칠 자리가 다르므로, 코드를 고치기 전에
  로그 원문과 응답 본문으로 가려 달라는 요청입니다.
- 범위: OpenSearch 로그 인덱스를 **읽기만** 합니다. Redis 도 읽기만 합니다.
- 답이 손으로 옮겨지므로 스크립트가 **짧은 줄만** 찍도록 했습니다. 그 줄들과 글자
  몇 개가 회신의 전부입니다.

## 1. 로그 조회 스크립트

저장소 루트에서 `python` 을 열고 붙여 넣습니다. 최근 7일, recipe_search 기능의
status 400 이상 요청 행을 시간순으로 찍습니다. 같은 request_id 의 예외 행이 있으면
그 메시지 앞부분을 함께 찍습니다.

```python
from urllib.parse import unquote
from backend.ebeam._office_search import client
from backend._logging.target import resolve_logging_target

alias = resolve_logging_target().alias
print("alias", alias)
os_ = client()
body = {
    "size": 200, "sort": [{"@timestamp": "asc"}],
    "_source": ["@timestamp", "request_id", "user_id", "status", "path",
                "query_string", "fab_name_list", "error_name"],
    "query": {"bool": {"filter": [
        {"term": {"event": "request"}},
        {"term": {"feature": "recipe_search"}},
        {"range": {"status": {"gte": 400}}},
        {"range": {"@timestamp": {"gte": "now-7d"}}},
    ]}},
}
hits = [h["_source"] for h in os_.search(index=alias, body=body)["hits"]["hits"]]
print("n", len(hits))
for h in hits:
    rid = h.get("request_id")
    exc = ""
    if rid:
        e = os_.search(index=alias, body={"size": 1, "_source": ["exception.message", "message"],
            "query": {"bool": {"filter": [{"term": {"request_id": rid}},
                                          {"term": {"event": "request_exception"}}]}}})
        for d in e["hits"]["hits"]:
            s = d["_source"]
            exc = (s.get("exception", {}).get("message") or s.get("message") or "")[:160]
    print(f"{h['@timestamp'][:19]} {h.get('status')} {h.get('user_id')} "
          f"{h.get('path','').split('/recipe-search/')[-1]} "
          f"q={unquote(h.get('query_string') or '')[:120]} fabs={h.get('fab_name_list')}")
    if exc:
        print("   exc:", exc)
```

찍히는 모양은 이렇습니다(값은 예입니다).

```text
alias skewnono_logging
n 4
2026-10-12T02:14:07 502 2067928 recipes q=fab_name=R3,M16B fabs=['R3', 'M16B']
   exc: Redis key 'v3_cdsem_unique_rcp_list' not found — check REDIS_HOST ...
2026-10-12T02:15:31 502 2067928 recipe-detail q=recipe_name=ADI/ADI_CD_001&fab_name=M16B fabs=['M16B']
   exc: No document in meas_hist_cdsem has full_name='ADI/ADI_CD_001' for fab 'M16B'. ... Redis recipe registry was tried first and declined: v3_cdsem_rcp_loc_m16b has no usable ...
2026-10-12T02:16:02 400 2067928 recipe-detail q=recipe_name=ADI/ADI_CD_001&fab_name=R3,M16B fabs=['R3', 'M16B']
2026-10-12T02:20:44 404 2067928 measurement-locations q=recipe_name=ADI/ADI_CD_001&fab_name=M16B fabs=['M16B']
```

- 셋째 칸 뒤의 단어가 **어느 엔드포인트**인지입니다. `recipes` 는 목록, `recipe-detail`
  은 열어보기, `measurement-locations` 는 IDP 버전 인덱스 조회입니다.
- `q=` 가 원래 요청의 쿼리입니다. 로그의 `fabs=` 는 콤마를 쪼개 저장한 값이라
  **`q=` 쪽을 믿어 주십시오.**
- `exc:` 줄이 502 의 실제 원인 문장입니다. 앞 160자만 찍습니다.

## 2. 상세 요청이 있으면 Redis 와 meas_hist 대조

1절 결과에 `recipe-detail` 이고 `q=` 의 fab_name 이 **정확히 `M16B` 하나**인 행이 있으면,
그 행의 recipe_name 과 fab 을 아래 `RECIPE`, `FAB` 에 넣고 붙여 넣습니다. 그 레시피가
어디에 등록돼 있고 어디서 측정됐는지 한 줄씩 찍습니다.

```python
from backend.ebeam._office_search import client, query
from backend.ebeam.recipe_search.providers import office as rs

RECIPE, FAB, TOOL = "ADI/ADI_CD_001", "M16B", "cd-sem"   # 1절 행의 값으로 바꿉니다
r = rs._redis_client()
fam = "cdsem" if TOOL == "cd-sem" else "hvsem"
for fab in ("r3", "r4", "m16a", "m16b", "m16c"):
    loc = r.hget(f"v3_{fam}_rcp_loc_{fab}", RECIPE)
    tools = r.hget(f"v3_{fam}_tools_in_rcp_{fab}", RECIPE)
    print(f"registry {fab} loc={'Y' if loc else '-'} tools={'Y' if tools else '-'}")
os_ = client()
res = os_.search(index=f"meas_hist_{fam}", body={"size": 0,
    "query": query([{"term": {"full_name.keyword": RECIPE}}]),
    "aggs": {"fabs": {"terms": {"field": "fab_name.keyword", "size": 10},
             "aggs": {"eqps": {"terms": {"field": "eqp_id.keyword", "size": 3}}}}}})
for b in res["aggregations"]["fabs"]["buckets"]:
    eqps = ",".join(e["key"] for e in b["eqps"]["buckets"])
    print(f"meas_hist fab={b['key']} n={b['doc_count']} eqps={eqps}")
```

찍히는 모양은 이렇습니다(값은 예입니다).

```text
registry r3 loc=Y tools=Y
registry r4 loc=- tools=-
registry m16a loc=- tools=-
registry m16b loc=- tools=-
registry m16c loc=- tools=-
meas_hist fab=R3 n=412 eqps=CG6300_02,CG6300_05
meas_hist fab=M16B n=3 eqps=CG6300_02
```

- `registry` 줄 — fab 별 등록부 hash 에 그 레시피가 있는지입니다.
- `meas_hist` 줄 — 그 레시피가 측정된 fab 과 장비입니다. **같은 장비가 두 fab 에
  나타나면** meas_hist 의 fab_name 은 장비가 아니라 lot 의 fab 이라는 뜻입니다. 이것이
  이번 질문의 핵심 판정입니다.

## 3. 재현 (가능하면)

1절에서 `recipe-detail` 행의 user_id 가 본인이거나 재현이 가능하면, 브라우저
개발자 도구 Network 에서 **Preserve log** 를 켜고 같은 레시피를 다시 열어 주십시오.
필요한 것은 네 가지입니다.

1. 상세를 열기 **직전 페이지의 주소창 URL** (`/ebeam/cd-sem/<fab 부분>/...` 까지).
2. 어느 화면의 어느 버튼으로 열었는지 (검색표 행 / recipe-tat 또는 recipe-status 행
   메뉴 / skewvoir 왼쪽 레일 / 하드웨어 창 / 주소 직접 입력).
3. `recipe-detail` 요청의 전체 URL.
4. 그 응답 JSON 의 `error` 값 전체.

## 4. 질문 (한 글자로 답해 주십시오)

`A` = 집의 가정이 맞음, `B` = 아님, `?` = 모름 또는 해당 없음.

1. 1절의 오류 행은 **대부분 `recipes` 목록 조회**이고 `q=` 에 `R3,M16B` 처럼 콤마가
   있다. (A 면 M16B 선택 문제가 아니라 목록 upstream 문제입니다.)
2. `recipe-detail` 행 중 `q=` 의 fab_name 이 **정확히 `M16B` 하나**인 것이 있다.
3. 2번이 A 이면, 그 행의 `exc:` 문장은 `No document in meas_hist` 로 시작한다.
   (`Found N document(s) ... none carries` 로 시작하면 B, `Could not download` /
   `Tried N tool(s)` 이면 C 로 적어 주십시오.)
4. 2절에서 그 레시피는 **R3 등록부에는 있고 M16B 등록부에는 없다**.
5. 2절 meas_hist 에서 **같은 eqp_id 가 두 fab 에** 나타난다. (A 면 meas_hist 의
   fab_name 은 lot 의 fab 입니다.)
6. 3절 재현에서 열기 직전 URL 의 fab 부분에 **fab 이 둘 이상** (예: `r3,m16b`) 있었다.
7. 3절 재현에서 `recipe-detail` 요청 URL 에 `fab_name=` 이 **있었다**.
8. 1절에 `recipe-detail` 이고 status **400** 이며 `q=` 에 콤마가 있는 행이 있다.
9. `measurement-locations` 404 행이 있다.
10. 사무실 `office.py` 는 이번 주에 다시 cp 한 것이다. (부팅 로그에 `STALE office.py`
    가 없으면 A.)

## 5. 답안지

```text
1.
2.
3.
4.
5.
6.
7.
8.
9.
10.
1절 출력 (전체 붙여넣기):
2절 출력 (전체 붙여넣기):
3절 1~4 (있으면):
```
