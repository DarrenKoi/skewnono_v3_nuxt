# 스큐보아 측정 결과 검색 (Skewvoir Search) — Design

- Date: 2026-07-14
- Status: Approved
- Scope: `front-dev-home/app/components/ebeam/skewvoir/SearchLanding.vue` 및 `back_dev_home/meas_hist/`

## 1. 배경

스큐보아 랜딩(`측정 결과 검색`)은 현재 껍데기입니다.

- 검색창은 입력만 받고 아무 동작도 하지 않습니다.
- `FILTERS` 행의 다섯 개 항목은 `<button>` + chevron 아이콘일 뿐 팝오버가 붙어 있지 않습니다. 그래서 눌러도 드롭다운이 열리지 않습니다.
- `Result Timeline` / `Quick Stats by Recipe` 패널은 의미 없는 자리표시자입니다.
- `Latest Measurements`는 mock 최신 행 12건을 그대로 보여줍니다.
- `MP : WAFER`, `3σ > 0.5`, `outliers` 칩은 실제 데이터와 연결되지 않은 장식입니다.

이 설계는 이 화면을 실제로 동작하는 검색 화면으로 만듭니다.

## 2. 목표와 비목표

### 목표

- 검색창 하나로 장비(tool), 레시피, lot id, 날짜, msr 을 검색합니다.
- `FILTERS`를 실제 다중 선택 드롭다운으로 동작시킵니다.
- 검색 결과 영역을 만들고, 자리표시자 패널 두 개를 제거합니다.
- `Latest Measurements`를 localStorage 기반 "최근 본 측정"으로 대체합니다.
- OpenSearch 전제(60일 보존, `size: 10000`)를 백엔드 계약에 반영합니다.

### 비목표

- MP, outlier, 3σ 관련 필터/칩은 이 화면에서 제거합니다. (분석 화면의 관심사입니다.)
- 분석 워크스페이스(`analysis.vue`) 내부는 변경하지 않습니다. 단, 최근 본 측정 기록을 위한 호출 한 줄은 추가합니다.

## 3. 검색 실행 모델

**백엔드 검색 + 클라이언트 즉시 좁히기(hybrid)** 방식입니다.

- 검색어는 프런트엔드가 구조화된 필드로 파싱합니다 (§4.0).
- 검색과 필터의 **실행**은 백엔드가 합니다. Phase 1은 `data.py`의 in-memory 필터, Phase 2/3은 동일 함수의 OpenSearch 구현입니다. 라우트와 프런트엔드는 바뀌지 않습니다.
- 브라우저에 로드된 결과 행에 한해, 네트워크를 타지 않는 즉시 좁히기(narrow) 입력을 제공합니다.

## 4. 검색어 문법

### 4.0 파서의 위치 — 프런트엔드

검색어 파싱은 **프런트엔드**(`app/utils/measHistQuery.ts`)에서 수행합니다. 백엔드는 원문 전체를 다시 파싱하지 않고 **구조화된 필드 + 미분류 토큰 `q`** 를 받습니다. `q` 는 쿼리 문자열 문법이 아니라 프런트엔드가 분리한 반복 문자열 파라미터입니다.

이유는 네 가지입니다.

1. **백엔드 입력 계약이 하나로 단일화됩니다.** 원문 문법을 백엔드가 다시 이해할 필요가 없습니다. 구조화 필드는 정확 필터로, `q` 는 허용 필드 전체의 부분 일치로 변환합니다.
2. **facet 응답을 파싱 근거로 쓸 수 있습니다.** facets 는 실재하는 `eqp_id` 와 `full_name` 목록을 이미 담고 있습니다. 알려진 장비 id 와 **정확히 일치하는** 토큰은 추측할 필요 없이 장비 id 입니다. `MCD`/`ECXDX` 같은 접두사 정규식을 데이터와 따로 관리하지 않아도 됩니다.
3. **칩이 즉시 렌더링됩니다.** 해석 결과를 보려고 왕복할 필요가 없습니다.
4. **저장소의 테스트 관례와 맞습니다.** 프런트엔드 파서는 `app/**/*.test.ts` 와 `node --test` 로, home Flask 계약은 표준 라이브러리 `unittest` 로 검증합니다. OpenSearch 실연결 검증은 별도 office-local 테스트로 격리합니다.

대가는 필드 형태 지식이 클라이언트에 있다는 점입니다. 손수 만든 API 호출도 반복 `q` 파라미터를 사용할 수 있지만, `q` 값 내부에 별도의 검색 문법은 없습니다.

### 4.1 토큰화

`[\s,;]+` 로 분리합니다. 공백, 콤마, 세미콜론을 모두 구분자로 취급하며 입력 중 생기는 후행 구분자는 무시합니다.

`MCD018, MCD019; ADI_CD_BIAS_001` → 토큰 3개.

### 4.2 필드 자동 판별

토큰마다 다음 순서로 판별합니다. facets 의 장비 목록(`knownEq`)을 함께 넘겨받습니다.

1. `field:value` 접두사(`lot:`, `recipe:`, `eq:`, `msr:`, `date:`, `q:`)가 있으면 그 필드로 강제합니다.
2. 날짜 형태(`2026-05-10`, `20260510`) → `date`
3. 8자리 숫자로 시작하는 `_` 구분 4개 이상 → `msr` (예: `20260510_ADI_CD_BIAS_001_RKPB240012_MCD018`)
4. `knownEq` 에 있는 값 (대소문자 무시) → `eq`
5. lot id 형태(`^[A-Z0-9]{3,4}\d{6,8}$`, 예: `RKPB240012`) → `lot`
6. **그 외 전부 → `q` (검색 허용 필드 전체의 부분 일치)**

**레시피 목록은 판별 근거로 쓰지 않습니다.** 실제 색인의 레시피는 수백 개여서 전부 내려받을 수 없기 때문입니다 (§6.3). 따라서 `ECXDX` 같은 장비 접두사와 `CD_BIAS` 같은 레시피 일부는 모두 `q` 로 보냅니다. 백엔드는 `eqp_id`, `lot_id`, `recipe_name`, `full_name`, `msr` 등 고정 허용 목록 전체에서 대소문자를 무시한 부분 일치를 수행합니다.

이 규칙의 중요한 성질은 **어떤 토큰도 조용히 버려지거나 임의로 레시피로 오분류되지 않는다** 는 점입니다. 존재하지 않는 문자열을 입력하면 결과가 0건으로 정직하게 나옵니다. 토큰을 질의에서 빼버려 결과가 사용자가 입력한 것보다 **넓어지는** 일은 없습니다. 계측 도구에서는 이쪽이 훨씬 위험한 실패 방향입니다.

`unknown` 은 이제 `field:` 접두사가 붙었는데 값이 형식에 맞지 않는 경우(예: `date:notadate`)에만 남습니다. 이 경우에만 빨간 칩으로 표시합니다.

### 4.3 결합 규칙

- **같은 필드끼리는 OR**, **필드 간에는 AND** 입니다.
- `MCD018, MCD019, ADI_CD_BIAS_001` → `(eq = MCD018 OR eq = MCD019) AND search_all ~ ADI_CD_BIAS_001`
- 이 규칙이 아니면 같은 필드 토큰 두 개는 항상 0건이 됩니다. OpenSearch `bool { must: [terms, terms] }` 와 그대로 대응합니다.
- 날짜 토큰 1개는 해당 일자, 2개는 범위입니다.

### 4.4 msr 과 lot 의 관계

msr 은 `날짜_레시피_lot_장비` 조합이므로 lot id 를 부분 문자열로 포함합니다. 따라서 완전한 `RKPB240012` 는 lot 필드로 판별해 term 질의를 보냅니다. 완전한 msr 형태도 `msr` 정확 일치로 질의합니다. 그 외 msr 일부 문자열은 `q` 로 들어가며, 일반 keyword 필드가 아니라 §5.2.2의 전용 `wildcard` 필드에서 찾습니다.

### 4.5 파싱 결과

파서 반환값입니다.

```ts
interface ParsedQuery {
  eq: string[]
  lot: string[]
  recipe: string[]
  msr: string[]
  date: string[]     // YYYY-MM-DD 정규화
  q: string[]        // 고정 허용 필드 전체 부분 일치
  unknown: string[]
}
```

UI 는 이를 검색창 아래 칩으로 표시합니다. 미인식 토큰(`unknown`)은 빨강으로 구분합니다. 자동 판별이 어떻게 해석했는지 사용자가 볼 수 있어야 오타와 무결과를 구분할 수 있습니다. 이 값이 그대로 요청 파라미터가 되므로 화면에 보이는 해석과 실제 질의는 어긋날 수 없습니다.

## 5. 백엔드

### 5.1 `GET /api/meas-hist/search`

모든 파라미터는 프런트엔드가 분류한 값입니다. `q` 도 원문 전체가 아니라 미분류 토큰의 반복 파라미터입니다 (§4.0). 검색창이 만든 필드와 필터 드롭다운이 만든 필드는 같은 파라미터로 합쳐져 들어옵니다.

| 파라미터 | 출처 | 설명 |
| --- | --- | --- |
| `tool_type` | 라우트 | `cd-sem` \| `hv-sem` |
| `fab` | 필터 | `fab_name` 다중 선택 (반복 파라미터) |
| `model` | 필터 | `eqp_model_cd` 다중 선택 |
| `eq` | 필터 + 검색어 | `eqp_id` 정확 일치, 다중 |
| `recipe` | 필터 + 검색어 | `full_name` / `recipe_name` 부분 일치, 다중 |
| `lot` | 검색어 | `lot_id` 정확 일치, 다중 |
| `msr` | 검색어 | `msr` 정확 일치, 다중 |
| `q` | 검색어 fallback | 고정 허용 필드 전체에서 대소문자 무시 부분 일치, 다중 |
| `from`, `to` | 필터 + 검색어 | 조회 기간 |
| `offset`, `limit` | 페이징 | 기본 `limit=50` |

같은 파라미터의 값 여러 개는 OR, 파라미터 간에는 AND 입니다 (§4.3).

응답:

```json
{
  "total": 1284,
  "capped": false,
  "offset": 0,
  "limit": 50,
  "range": { "from": "2026-03-11", "to": "2026-05-10", "anchor": "2026-05-10" },
  "out_of_retention": false,
  "rows": []
}
```

### 5.2 조회 범위와 크기 제한

실제 색인은 전체 측정 이력을 담고 있습니다. 따라서 모든 질의에 다음을 강제합니다.

- **날짜 범위는 항상 존재합니다.** 사용자가 기간을 지정하지 않아도 백엔드가 `now-60d → now` 를 주입합니다.
- **사용자 지정 범위는 보존 창과 교집합입니다.** 대체가 아닙니다. 오래된 북마크나 조작된 URL 이 보존 기간 밖을 스캔할 수 없습니다. 범위가 완전히 창 밖이면 0건과 함께 `보존 기간(60일) 밖입니다` 를 반환합니다.
- **`size: 10000`** — OpenSearch `index.max_result_window` 기본값입니다. 조회 상한이지 브라우저로 보내는 양이 아닙니다.
- `total` 이 10000 을 넘으면 `capped: true` 를 실어 보내고, UI 는 `상위 10,000건만 조회 · 검색어를 좁혀주세요` 를 표시합니다. 상한을 숨기면 "이 레시피가 몇 번 돌았나"에 조용히 틀린 답을 주게 됩니다.

기간을 좁히면 스캔 문서가 줄고 상한에 걸릴 확률도 낮아집니다. 프런트엔드의 기본 60일은 편의이고, 백엔드의 clamp 가 보증입니다.

### 5.2.1 보존 창의 기준 시각 (anchor)

Phase 1 mock 의 시계는 `meas_hist/data.py` 의 `NOW = datetime(2026, 5, 10)` 에 고정되어 있고, 600행은 그 시점 기준 과거 60일에 분포합니다. 벽시계 오늘을 기준으로 60일 창을 잡으면 mock 행이 **한 건도** 들어오지 않습니다.

따라서 보존 창은 **백엔드가 선언하는 기준 시각(anchor)** 을 기준으로 잡습니다.

- `data.py` 가 `RETENTION_ANCHOR` 를 노출합니다. Phase 1 은 `NOW`, Phase 2/3 은 실제 `datetime.now(timezone.utc)` 입니다.
- 창은 `anchor - 60d → anchor` 입니다. §5.2 의 clamp 는 모두 이 창을 씁니다.
- 검색/facets 응답의 `range` 에 `anchor` 를 함께 실어 보냅니다.
- 프런트엔드는 이 `anchor` 를 `DateRangePopover` 의 `anchorDate` prop 과 기본 기간 계산에 그대로 사용합니다. 벽시계 `today()` 를 쓰지 않습니다.
- "최근 본 측정" 의 만료 판정(§6.5)도 같은 anchor 를 씁니다.

Phase 2 로 넘어갈 때 바뀌는 것은 `RETENTION_ANCHOR` 한 줄뿐입니다.

### 5.2.2 OpenSearch 부분 일치 전략

일반 `keyword` 필드 여러 개에 `*토큰*` 을 직접 실행하는 방식은 기본 전략으로 사용하지 않습니다. 선행 wildcard 는 많은 term 을 순회해 느리고, 클러스터의 `search.allow_expensive_queries=false` 설정에서 차단될 수 있습니다.

대신 색인 시 검색 허용 필드를 합친 `search_all` 값을 추가하고 이를 OpenSearch `wildcard` 타입으로 매핑합니다. 정확 필터는 기존 keyword 필드에 유지하고, `q` fallback 만 `search_all` 에 `*토큰*` 질의를 실행합니다.

- 검색 허용 필드와 OpenSearch DSL: `back_dev_home/meas_hist/opensearch_query.py`
- home mock: 동일 허용 필드를 메모리에서 `casefold()` 부분 일치합니다.
- office ingest: `build_search_all_value(row)` 값을 `search_all` 로 색인합니다.
- 기존 60일 문서: 매핑만 추가해서는 값이 생기지 않으므로 재색인 또는 backfill 후 기능을 활성화합니다.
- 실클러스터 확인: `tests/test_meas_hist_search_local.py` 를 office 환경 변수로 실행합니다.

근거는 OpenSearch 공식 문서의 [Wildcard query](https://docs.opensearch.org/latest/query-dsl/term/wildcard/)와 [Wildcard field type](https://docs.opensearch.org/latest/mappings/supported-field-types/wildcard/)입니다.

### 5.3 `GET /api/meas-hist/facets`

`tool_type` 에 대해 존재하는 `fab`, `model`, `eq` 값과 건수를 반환합니다. Phase 2 는 OpenSearch terms aggregation 입니다. 드롭다운은 실재하는 값만 보여줍니다.

`recipe` 집계는 **반환하지 않습니다**. 레시피는 드롭다운이 없고 검색창으로만 찾기 때문입니다 (§6.3). 쓰지 않을 수백 개짜리 목록을 서버가 집계하지 않게 합니다.

`anchor` 와 `retention_days` 도 함께 반환합니다 (§5.2.1). 프런트엔드의 모든 날짜 계산이 이 값을 기준으로 합니다.

### 5.4 파일 구성

- `back_dev_home/meas_hist/data.py` — `search_meas_hist(...)`, `get_meas_hist_facets(...)` 추가. 2개 고정 검색 fixture + 랜덤 행으로 구성된 600행 시드 데이터 위에서 in-memory 필터링합니다.
- `back_dev_home/meas_hist/opensearch_query.py` — office `search_all` 매핑·ingest 값·fallback DSL 계약입니다.
- `back_dev_home/meas_hist/routes.py` — 파라미터 마샬링만 합니다. `request.args.getlist(...)` 로 반복 파라미터를 읽습니다.

블루프린트는 `back_dev_home/__init__.py` 가 `rglob("routes.py")` 로 자동 등록하므로 등록 코드를 추가할 필요가 없습니다.

교체면(swap surface)은 `data.py` 안에 머뭅니다. Phase 2 는 이 두 함수만 OpenSearch 질의로 다시 쓰면 되고 라우트와 프런트엔드는 그대로입니다. `opensearch-py` 는 이미 `requirements.txt` 에 있습니다.

## 6. 프런트엔드

### 6.1 컴포저블

**`app/utils/measHistQuery.ts`** (신규, 순수 함수)

- `parseMeasHistQuery(text: string, known?: { eq: string[] }): ParsedQuery` — §4 의 문법 전체. 순수 함수이므로 `node --test` 로 직접 테스트합니다.
- `removeToken(text: string, token: string): string` — 칩의 × 가 검색어에서 해당 토큰만 제거할 때 씁니다.

**`useMeasHistSearch.ts`** (신규)

- 상태: `queryText`, `filters`(`fab[]`, `model[]`, `eq[]`, `recipe[]`, `from`, `to`), `offset`, 결과(`rows`, `total`, `capped`, `outOfRetention`).
- `parsed` — `queryText` + facets 로부터 계산되는 computed 입니다. 타이핑 즉시 칩이 갱신됩니다.
- 요청 파라미터는 `parsed` 와 `filters` 를 필드별로 합집합해 만듭니다 (검색어의 `eq` 와 드롭다운의 `eq` 는 같은 `eq` 파라미터로 합쳐집니다).
- `search()` — 결과를 교체합니다. `loadMore()` — `offset += 50` 으로 이어붙입니다.
- **검색은 명시적입니다.** Enter 또는 Search 버튼에서만 실행합니다. 타이핑마다 60일 색인에 질의하면 lot id 하나 입력에 질의 여섯 번이 나갑니다. 반면 **필터 드롭다운 변경은 즉시 재검색**합니다. 의도적인 단일 동작이기 때문입니다.
- `narrowText` + `narrowedRows` — 로드된 행에 대한 클라이언트 즉시 필터입니다. 네트워크를 타지 않습니다.

**`useMeasHistFacets.ts`** (신규) — `useAsyncData('meas-hist-facets:<tool>')`. tool type 별로 캐시하며 모든 드롭다운이 공유합니다.

**`useSkewvoirRecentlyViewed.ts`** (신규) — localStorage 목록. `useSkewvoirSavedViews` 의 구조를 그대로 따릅니다 (모듈 수준 `readAll`/`writeAll`, `useState` 로 반응성 공유, `import.meta.client` 가드).

- `record(row)` — 앞에 추가, `msr` 기준 중복 제거, **최대 15건**, 저장.
- `items` — tool type 별 computed. 각 항목은 `expired: capturedAt < today − 60d` 를 함께 가집니다.
- 랜딩의 `open()` 과 분석 워크스페이스 양쪽에서 호출합니다. 공유 링크로 연 측정도 기록에 남아야 합니다.

### 6.2 컴포넌트 분리

현재 `SearchLanding.vue` 는 334줄이고, 실제 필터를 붙이면 500줄을 넘습니다. 분리합니다.

| 컴포넌트 | 책임 |
| --- | --- |
| `SearchLanding.vue` | 오케스트레이션만. 헤더, 저장된 뷰, 컴포저블 연결 (~120줄) |
| `search/SearchBar.vue` | 입력, Search 버튼, **파싱 토큰 칩** (`EQ: MCD018` ×, 미인식 토큰은 빨강). 칩의 × 는 해당 토큰을 검색어에서 제거합니다. |
| `search/FilterBar.vue` | 다섯 개 facet 을 실제 `UPopover` 다중 선택으로. 선택 개수 표시, 활성 시 `초기화` |
| `search/ResultTable.vue` | 검색 결과 표. 빈 상태, 좁히기 입력, `총 N건` + 상한 경고, 다중 선택 → `선택 분석`, `더 보기` |
| `search/RecentlyViewed.vue` | localStorage 표. 만료 행은 흐리게 + `보존 기간 만료` |

### 6.3 필터 항목

| facet | 소스 필드 | 형태 |
| --- | --- | --- |
| FAB | `fab_name` | 다중 선택 |
| 장비 종류 | `eqp_model_cd` | 벤더별 그룹, 다중 선택 |
| EQ | `eqp_id` | 다중 선택. 팝오버 안에 타입-투-필터 입력을 둡니다. |
| 기간 | `timestamp` | 기존 `EbeamDateRangePopover` 재사용. `anchorDate` 에 백엔드 anchor(§5.2.1)를 넘깁니다. 프리셋은 7일 / 30일 / 60일 입니다. |

facet 은 네 개뿐입니다.

**`RECIPE` 드롭다운은 두지 않습니다.** 실제 색인의 레시피는 수백 개여서 목록을 전부 내려받는 것이 불가능합니다. 레시피는 **검색창으로만** 찾습니다 (부분 문자열, §4.2). 같은 이유로 facets 응답에서도 `recipe` 집계를 빼서, 쓰지도 않을 목록을 서버가 만들지 않게 합니다.

**`Area` 필터도 삭제합니다.** `sem_list` 에도 `meas_hist` 에도 대응 필드가 없습니다. 아무것도 거르지 못하는 필터는 없는 것만 못합니다.

날짜 토큰과 기간 드롭다운은 **같은 파라미터**이며, **마지막에 쓴 쪽이 이깁니다(last write wins)**.

- `date:2026-05-10` 을 입력하면 범위가 그날 하루가 되고 기간 칩도 그렇게 바뀝니다.
- 반대로 기간 드롭다운에서 범위를 고르면 검색어의 날짜 토큰이 **제거**됩니다.

한쪽이 언제나 이기게 두면 다른 쪽은 눌러도 아무 일이 없는 죽은 컨트롤이 됩니다. 그러면 "화면은 적용됐다고 하는데 질의는 무시하는" 상태가 되므로, 두 입력구는 항상 하나의 진실을 가리켜야 합니다.

필터는 검색어와 AND 로 결합합니다.

### 6.4 결과 영역

- **기본 상태(질의 없음): 빈 상태.** 무엇을 검색할 수 있는지와 60일 보존 안내만 보여줍니다.
- 결과는 **50건씩**, `더 보기` 로 다음 50건을 이어붙입니다. 페이지 번호는 두지 않습니다. 7페이지로 걸어가기보다 검색어를 좁히는 편이 언제나 낫습니다.
- 표 컬럼: `LOT · RECIPE(full_name) · EQ · FAB · CAPTURED`
- 기존 다중 선택 → `선택 분석 (Time-Series)` 와 저장된 뷰 팝오버는 유지합니다.

### 6.5 최근 본 측정

- 분석 워크스페이스로 측정을 열면 `{msr, lot, recipe, eq, fab, capturedAt, viewedAt}` 를 기록합니다.
- 60일 보존 창을 벗어난 항목은 **흐리게 표시하고 클릭을 막으며 `보존 기간 만료`** 를 붙입니다. 조용히 사라지게 하지 않습니다. 보존 규칙이 있다는 사실 자체가 두 달 만에 lot 을 다시 찾는 사람에게 필요한 정보입니다.
- 만료 판정은 `capturedAt < anchor - 60d` 입니다. anchor 는 백엔드가 준 값입니다 (§5.2.1). 벽시계를 쓰지 않습니다.
- mock 에는 삭제 경로가 없으므로 날짜 계산으로 충분합니다. Phase 2 는 저장된 msr 을 백엔드로 검증하는 방식으로 UI 변경 없이 올릴 수 있습니다.

### 6.6 제거 대상

- `Result Timeline`, `Quick Stats by Recipe` 패널
- `MP : WAFER`, `3σ > 0.5`, `outliers` 칩
- `useSkewvoirWorkspace` 의 `pinnedFilters` (mock 시드값이며 실제로 쓰이는 곳이 없습니다)

## 7. 오류 처리

| 상황 | 처리 |
| --- | --- |
| 검색 실패 | 인라인 `검색에 실패했습니다` + `재시도`. 기존 결과는 유지합니다. |
| 0건 | *일치 없음* 과 *보존 기간 밖* 을 구분해 표시합니다. |
| 상한 초과 | `상위 10,000건만 조회 · 검색어를 좁혀주세요` |
| facet 로드 실패 | 드롭다운을 비활성 상태로 렌더링합니다. 비어 있고 이유를 알 수 없는 상태로 두지 않습니다. |

## 8. 테스트

프런트엔드 순수 파서는 `app/**/*.test.ts` 와 `npm test` (`node --test`) 로 검증합니다. Flask와 OpenSearch 계약은 외부 패키지 추가 없이 `tests/`의 `unittest` 모듈로 나눕니다.

**`app/utils/measHistQuery.test.ts`** (신규):

- 토큰화 — 공백·콤마·세미콜론 혼합, 연속 구분자, 후행 구분자.
- 필드 판별 — 날짜 두 형태, msr 형태, `knownEq` 정확 일치, lot 형태, 그 외 전부 `q` 폴백, `field:` 접두사 오류로만 남는 미인식.
- `field:` 접두사 강제 — 형태 규칙을 이깁니다.
- 같은 필드 여러 토큰이 배열로 누적되는지.
- facets 미로딩 상태의 축약 규칙.
- `removeToken` — 해당 토큰만 제거하고 나머지 구분자를 망가뜨리지 않는지.

**`tests/test_meas_hist_search_home.py`** 는 고정 mock fixture, `q`의 장비/lot/recipe/model/msr 부분 일치, 구조화 필터와의 AND, Flask 반복 파라미터 계약, OpenSearch DSL 생성을 검증합니다.

**`tests/test_meas_hist_search_local.py`** 는 home에서 skip되고, office 환경 변수가 있을 때 실제 index의 `search_all` wildcard 매핑과 실데이터 hit를 확인합니다.
