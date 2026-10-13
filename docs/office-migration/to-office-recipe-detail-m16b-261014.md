# recipe-search 4xx/5xx 와 fab_name=M16B 원인 확인 — Home → Office (2026-10-14)

- 작성일: 2026-10-13입니다.
- 수신자: 사무실에서 SKEWNONO를 실행·확인하는 Office agent입니다.
- 목적: 활동 로그에 recipe-search 쪽 4xx/5xx 가 있고, 그 행들에 `M16B` 가 들어
  있습니다. 집에서 코드를 추적한 결과 **M16B 를 기본값으로 고르는 코드는 없습니다**.
  우선 다음 세 가능성을 확인합니다. (가) 다중 fab 목록 조회 `R3,M16B` 가 실패했는데
  로그가 콤마를 쪼개 저장해 M16B 로 보이는 경우, (나) 데이터(meas_hist)가 M16B 라고
  태그한 행에서 상세를 연 경우, (다) 링크에 소유 fab 이 없어 사이드바 첫 fab 으로
  떨어진 경우입니다. Redis 카탈로그와 위치 등록부의 갱신 차이 같은 다른 가능성도
  있으므로, 어느 항목에도 맞지 않으면 원인을 확정하지 않습니다. 어느 쪽인지에 따라
  고칠 자리가 다르므로, 코드를 고치기 전에 로그 원문과 응답 본문으로 가려 달라는
  요청입니다.
- 범위: OpenSearch 로그 인덱스와 Redis 를 **읽기만** 합니다.
- 답이 손으로 옮겨지므로 스크립트가 **짧은 줄만** 찍도록 했습니다. 그 줄들과 글자
  몇 개가 회신의 전부입니다.

## 0. 먼저 보존할 것

데이터 수정, adapter 교체, 프로세스 재시작을 하기 **전에** 아래를 적어 둡니다. 로그에는
응답 본문이 저장되지 않아, 지나간 502 의 본문은 나중에 복원할 수 없습니다.

- 오류가 난 배포가 localhost 인지 cloud 인지. 로그 alias 는 localhost 가
  `skewnono_logging_local`, cloud 가 `skewnono_logging` 입니다.
- recipe_search 의 `office.py` 와 `office_example.py` 가 같은 내용인지 (`diff` 가 비어
  있는지), 그리고 마지막으로 cp 한 뒤 프로세스를 재시작했는지.
- 부팅 로그의 provider 판정 줄과 `STALE office.py` 줄이 있으면 그대로.

## 1. 로그 조회 스크립트

**오류가 난 배포와 같은 환경**에서 저장소 루트의 `python` 에 붙여 넣습니다. 최근 7일,
recipe_search 기능의 status 400 이상 요청 행을 시간순으로 찍습니다. 처리된 502 의
원인 문장은 요청 행이 아니라 별도 application 예외 행에 남고 request_id 로 연결되지
않으므로, 같은 시각 전후 3초의 예외 행을 **후보**로 함께 찍습니다.

```python
from urllib.parse import unquote
from backend._runtime.office_redis import load_env_file
load_env_file("SKEWNONO_LOG_ENV")
from backend.ebeam._office_search import client
from backend._logging.target import resolve_logging_target

alias = resolve_logging_target().alias
print("alias", alias, "<- 조사 대상 배포와 다르면 중단")
os_ = client()
body = {
    "size": 200, "track_total_hits": True, "sort": [{"@timestamp": "asc"}],
    "_source": ["@timestamp", "host", "user_id", "status", "path", "query_string", "fab_name_list"],
    "query": {"bool": {"filter": [
        {"term": {"event": "request"}},
        {"term": {"feature": "recipe_search"}},
        {"range": {"status": {"gte": 400}}},
        {"range": {"@timestamp": {"gte": "now-7d"}}},
    ]}},
}
res = os_.search(index=alias, body=body)
hits = [h["_source"] for h in res["hits"]["hits"]]
total = res["hits"]["total"]["value"]
print("shown", len(hits), "total", total, "INCOMPLETE: 기간을 좁혀 다시" if total > len(hits) else "")
if res.get("timed_out") or res.get("_shards", {}).get("failed"):
    raise RuntimeError("부분 결과 — 답하지 마십시오")
for i, h in enumerate(hits, 1):
    ts = h["@timestamp"]
    print(f"[{i}] {ts} host={h.get('host')} user={h.get('user_id')} status={h.get('status')}")
    print(f"    path={h.get('path')} fabs={h.get('fab_name_list')}")
    q = unquote(h.get("query_string") or "")
    for j in range(0, len(q), 100):
        print(f"    q{j // 100 + 1}={q[j:j + 100]}")
    near = os_.search(index=alias, body={"size": 2, "sort": [{"@timestamp": "asc"}],
        "_source": ["@timestamp", "exception.message", "message"],
        "query": {"bool": {"must_not": [{"term": {"event": "request"}}],
                           "filter": [{"exists": {"field": "exception.message"}},
                                      {"range": {"@timestamp": {"gte": f"{ts}||-3s", "lte": f"{ts}||+3s"}}}]}}})
    for d in near["hits"]["hits"]:
        print("    exc?", d["_source"]["@timestamp"], (d["_source"].get("exception", {}).get("message") or "")[:200])
```

찍히는 모양은 이렇습니다(값은 예입니다).

```text
alias skewnono_logging <- 조사 대상 배포와 다르면 중단
shown 3 total 3
[1] 2026-10-12T02:14:07.431+00:00 host=skw-01 user=2067928 status=502
    path=/api/cdsem/recipe-search/recipes fabs=['R3', 'M16B']
    q1=fab_name=R3,M16B
    exc? 2026-10-12T02:14:07.430+00:00 Redis key 'v3_cdsem_unique_rcp_list' not found — check REDIS_HOST ...
[2] 2026-10-12T02:15:31.002+00:00 host=skw-01 user=2067928 status=502
    path=/api/cdsem/recipe-search/recipe-detail fabs=['M16B']
    q1=recipe_name=ADI/ADI_CD_001&fab_name=M16B
    exc? 2026-10-12T02:15:30.998+00:00 No document in meas_hist_cdsem has full_name='ADI/ADI_CD_001' for fab 'M16B'. ... Redis recipe registry was tried first and declined: ...
[3] 2026-10-12T02:16:02.117+00:00 host=skw-01 user=2067928 status=400
    path=/api/cdsem/recipe-search/recipe-detail fabs=['R3', 'M16B']
    q1=recipe_name=ADI/ADI_CD_001&fab_name=R3,M16B
```

- `path` 의 끝 단어가 **어느 엔드포인트**인지입니다. `recipes` 는 목록, `recipe-detail`
  은 열어보기, `measurement-locations` 는 IDP 버전 인덱스 조회입니다. `cdsem` / `hvsem`
  부분이 계열입니다.
- `q1=` 이 원래 요청의 쿼리입니다(100자 단위로 나눠 찍습니다). 로그의 `fabs=` 는 쿼리의
  콤마를 쪼갠 값과 handler 가 보탠 fab 의 합집합이라 **`q=` 쪽을 믿어 주십시오.**
- `exc?` 줄은 시각이 가까운 예외 행의 **후보**입니다. request_id 연결이 없으므로 그
  요청의 원인으로 확정하지는 않습니다. 원인 분류는 3절 재현의 응답 본문을 우선합니다.
- `shown` 이 `total` 보다 작으면 기간을 좁혀 빠진 구간도 봅니다. 완료 전에는
  "없다" 나 "대부분" 을 판정하지 않습니다.
- 시각은 **UTC** 입니다. meas_hist 의 KST 벽시계와 같은 규칙으로 읽지 않습니다.

## 2. 상세 요청이 있으면 Redis 와 meas_hist 대조

1절 결과에 `recipe-detail` 이고 `q=` 의 fab_name 이 **콤마 없이 하나**인 행이 있으면,
그 행의 값으로 `RECIPE`(쿼리의 recipe_name), `FAB`(쿼리의 fab_name), `TOOL`(path 가
`cdsem` 이면 `cd-sem`, `hvsem` 이면 `hv-sem`)을 바꿔 붙여 넣습니다. 등록부 hash 가 있는
fab 을 Redis 에서 훑어 그 레시피의 보유 여부를, meas_hist 에서 측정 fab 과 장비를
한 줄씩 찍습니다.

```python
from backend.ebeam._office_search import client, query
from backend.ebeam.recipe_search.providers import office as rs

RECIPE, FAB, TOOL = "ADI/ADI_CD_001", "M16B", "cd-sem"   # 1절 행의 값으로 바꿉니다
r = rs._redis_client()
fam = {"cd-sem": "cdsem", "hv-sem": "hvsem"}[TOOL]
fabs = {FAB.strip().lower()}
for kind in ("rcp_loc", "tools_in_rcp"):
    prefix = f"v3_{fam}_{kind}_"
    for key in r.scan_iter(match=prefix + "*", count=100):
        key = key.decode() if isinstance(key, bytes) else key
        fabs.add(key[len(prefix):])
def short(v):
    v = v.decode() if isinstance(v, bytes) else v
    return "-" if not v else (v[:60] + ("…" if len(v) > 60 else ""))
for fab in sorted(fabs):
    loc = r.hget(f"v3_{fam}_rcp_loc_{fab}", RECIPE)
    tools = r.hget(f"v3_{fam}_tools_in_rcp_{fab}", RECIPE)
    print(f"registry {fab} loc={short(loc)} tools={short(tools)}")
os_ = client()
res = os_.search(index=f"meas_hist_{fam}", body={"size": 0,
    "query": query([{"term": {"full_name.keyword": RECIPE}}]),
    "aggs": {"fabs": {"terms": {"field": "fab_name.keyword", "size": 10},
             "aggs": {"eqps": {"terms": {"field": "eqp_id.keyword", "size": 3}}}}}})
agg = res["aggregations"]["fabs"]
print("meas_hist fab 누락", agg.get("sum_other_doc_count", 0), "timed_out", res.get("timed_out"))
for b in agg["buckets"]:
    eqps = ",".join(e["key"] for e in b["eqps"]["buckets"])
    print(f"meas_hist fab={b['key']} n={b['doc_count']} eqps={eqps}")
latest = os_.search(index=f"meas_hist_{fam}", body={"size": 5, "sort": [{"timestamp": "desc"}],
    "_source": ["timestamp", "eqp_id", "eqp_ip", "class_name", "idw_name", "idp_name"],
    "query": query([{"term": {"full_name.keyword": RECIPE}}, {"term": {"fab_name.keyword": FAB}}])})
for d in latest["hits"]["hits"]:
    s = d["_source"]
    has = "".join("Y" if s.get(k) else "-" for k in ("eqp_ip", "class_name", "idw_name", "idp_name"))
    print(f"latest {s.get('timestamp')} {s.get('eqp_id')} fields(ip,class,idw,idp)={has}")
```

찍히는 모양은 이렇습니다(값은 예입니다).

```text
registry m16b loc=- tools=-
registry r3 loc=['ADI/ADI_CD_001.idw', 'ADI/ADI_CD_001.idp'] tools=['CG6300_02', 'CG6300_05']
registry r4 loc=- tools=-
meas_hist fab 누락 0 timed_out False
meas_hist fab=R3 n=412 eqps=CG6300_02,CG6300_05
meas_hist fab=M16B n=3 eqps=CG6300_02
latest 2026-10-11T09:12:44 CG6300_02 fields(ip,class,idw,idp)=YY--
```

- `registry` 줄 — Redis 에 등록부 hash 가 있는 fab 마다 그 레시피의 값 앞 60자입니다.
  `-` 는 값이 없다는 뜻입니다. 값이 있다는 것은 **hash 에 항목이 있다**는 뜻일 뿐,
  경로가 올바르거나 장비가 접근 가능하다는 뜻은 아닙니다.
- `meas_hist` 줄 — 그 레시피가 측정된 fab 과 장비 상위 3개입니다. 상위 3개 표본이라
  안 찍혔다고 없는 것은 아닙니다. **같은 장비가 두 fab 에 나타나면** fab 과 장비의 관계를
  더 확인해야 합니다. 이 출력만으로 lot 기준인지 장비 위치 기준인지 확정하지 않습니다.
- `latest` 줄 — 열어보기가 실제로 읽는 최신 5건입니다. 네 글자가 모두 `Y` 인 건이
  하나도 없으면 "문서는 있는데 경로 필드가 비어" 실패하는 경우입니다.

## 3. 재현 (가능하면)

1절에서 `recipe-detail` 행의 user_id 가 본인이거나 재현이 가능하면, 브라우저
개발자 도구 Network 에서 **Preserve log** 를 켜고 같은 레시피를 다시 열어 주십시오.
최초 실패와 재현은 따로 적습니다.

1. 진입부터 실패까지 **주소창 전체 URL 을 순서대로** (query 포함). 상세 탭 이동과
   사이드바 fab 변경이 있었으면 전후를 각각 한 줄로.
2. 거친 경로 (4절 11번의 글자로).
3. 클릭한 원천 행의 full_name, fab_name, eqp_id, source 를 값별 한 줄로. 작업 세트에서
   열었다면 그 항목에 owner fab 이 있었는지도.
4. `recipe-detail` 요청의 전체 URL.
5. 그 응답 JSON 의 `error.code` 와 `error.message` 전체.

## 4. 질문 (한 글자로 답해 주십시오)

`A` = 집의 가정이 맞음, `B` = 아님, `?` = 모름 또는 해당 없음. 다른 글자가 있는 질문은
그 글자 중에서 고릅니다.

1. 1절 오류 전체 중 `recipes` 목록 요청이 절반을 넘고, 그 요청의 원래 `q=` 에
   `R3,M16B` 처럼 콤마가 있다. (A 라도 별도의 M16B 상세 오류는 배제하지 않습니다.)
2. `recipe-detail` 행 중 `q=` 의 fab_name 이 **콤마 없이 하나**이고 그 값이 M16B 인 것이
   있다.
3. 그 상세 응답(또는 3절 재현)의 `error.message` 는 무엇으로 시작하는가. A = `No
   document in meas_hist`, B = `Found N document(s)`, C = `Could not download` 또는
   `Tried N tool(s)`, D = 그 밖의 문구, `?` = 응답을 확보하지 못함.
4. 2절에서 그 레시피는 **r3 는 loc 와 tools 가 모두 값이 있고, m16b 는 둘 다 `-`** 이다.
   A = 그렇다, B = 다른 조합(한 줄로 적어 주십시오), `?` = 조회 미완.
5. 2절 meas_hist 표본에서 **같은 eqp_id 가 두 fab 에** 나타난다. A = 나타난다,
   B = 안 나타난다, `?` = 표본만으로 확인 불가.
6. 3절 재현에서 열기 직전 주소창 URL 의 fab 부분에 **fab 이 둘 이상** (예: `r3,m16b`)
   있었다.
7. 실패한 상세를 **처음 여는 주소창 URL** 에 비어 있지 않은 `fab_name=` 이 있었다.
   (API 요청 URL 이 아니라 주소창 URL 로 답합니다. 상세 페이지는 그 값이 없으면 URL 첫
   fab 을 채워서 API 를 부르므로, API URL 로는 구분이 안 됩니다.)
8. 1절에 `recipe-detail` 이고 status **400** 이며 `q=` 에 콤마가 있는 행이 있다.
9. `measurement-locations` 404 행이 있다.
10. 오류가 난 배포의 recipe_search `office.py` 가 `office_example.py` 와 **동일**하고
    (diff 비어 있음), 마지막 cp 뒤 재시작까지 했다. A = 둘 다 확인, B = 내용 불일치 또는
    미재시작, `?` = 미확인. (부팅 로그에 STALE 경고가 없다는 것만으로 A 를 고르지
    않습니다.)
11. 실패까지 거친 경로. A = 검색표 행, B = recipe-tat 또는 recipe-status 행 메뉴,
    C = skewvoir 왼쪽 레일, D = 하드웨어 창 → 측정 이력 → 열어보기 탭, E = 작업 세트
    또는 레시피 전환기, F = owner 없는 상세에서 사이드바 fab 변경, G = 다른 상세 화면의
    열어보기 탭, H = 주소 직접 입력, `?` = 확인 못함. 여러 단계면 글자를 순서대로.
12. meas_hist 의 fab_name 이 무엇을 기준으로 적재되는지 **원천 적재 로직**으로 확인했다.
    A = lot 소속 fab, B = 측정 당시 장비 위치, C = 현재 장비 위치, D = 그 밖(한 줄),
    `?` = 미확인.

## 5. 답안지

```text
0절 (배포 구분 / diff 결과 / 재시작 여부 / 부팅 로그 줄):
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
11.
12.
1절 출력 (전체 붙여넣기):
2절 출력 (전체 붙여넣기):
3절 1~5 (있으면):
```
