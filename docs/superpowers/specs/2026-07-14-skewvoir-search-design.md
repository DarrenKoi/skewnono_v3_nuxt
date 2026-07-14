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

- 검색과 필터는 백엔드가 실행합니다. Phase 1은 `data.py`의 in-memory 필터, Phase 2/3은 동일 함수의 OpenSearch 구현입니다. 라우트와 프런트엔드는 바뀌지 않습니다.
- 브라우저에 로드된 결과 행에 한해, 네트워크를 타지 않는 즉시 좁히기(narrow) 입력을 제공합니다.

## 4. 검색어 문법

### 4.1 토큰화

`[\s,;]+` 로 분리합니다. 공백, 콤마, 세미콜론을 모두 구분자로 취급하며 입력 중 생기는 후행 구분자는 무시합니다.

`MCD018, MCD019; ADI_CD_BIAS_001` → 토큰 3개.

### 4.2 필드 자동 판별

토큰마다 다음 순서로 필드를 판별합니다.

1. `field:value` 접두사(`lot:`, `recipe:`, `eq:`, `msr:`, `date:`)가 있으면 그 필드로 강제합니다.
2. 날짜 형태(`2026-05-10`, `20260510`) → `date`
3. 8자리 숫자로 시작하는 `_` 구분 3개 이상 → `msr` (예: `20260510_ADI_CD_BIAS_001_RKPB240012_MCD018`)
4. lot id 형태(`^[A-Z0-9]{3,4}\d{6}$`, 예: `RKPB240012`) → `lot`
5. 알려진 장비 접두사(`MCD`, `PCD`, `ACD`, `VCD`, `ECXDX`, `ECDX`, `HCDX`)로 시작 → `eq`
6. 그 외 → `recipe` (대소문자 무시 부분 일치, `full_name` 과 `recipe_name` 양쪽에 매칭)

### 4.3 결합 규칙

- **같은 필드끼리는 OR**, **필드 간에는 AND** 입니다.
- `MCD018, MCD019, ADI_CD_BIAS_001` → `(eq = MCD018 OR eq = MCD019) AND recipe ~ ADI_CD_BIAS_001`
- 이 규칙이 아니면 같은 필드 토큰 두 개는 항상 0건이 됩니다. OpenSearch `bool { must: [terms, terms] }` 와 그대로 대응합니다.
- 날짜 토큰 1개는 해당 일자, 2개는 범위입니다.

### 4.4 msr 과 lot 의 관계

msr 은 `날짜_레시피_lot_장비` 조합이므로 lot id 를 부분 문자열로 포함합니다. 따라서 `RKPB240012` 는 lot 필드로 판별해 색인된 term 질의를 보냅니다. msr 부분 문자열 매칭은 wildcard 스캔이 되어 느리므로 사용하지 않습니다. 완전한 msr 형태의 토큰만 `msr` 필드에 정확 일치로 질의합니다.

### 4.5 파싱 결과 되돌려주기

응답에 `parsed` 를 포함합니다.

```json
{ "eq": ["MCD018"], "lot": ["RKPB240012"], "recipe": [], "msr": [], "date": ["2026-05-10"], "unknown": ["xyz"] }
```

UI 는 이를 검색창 아래 칩으로 표시합니다. 자동 판별이 어떻게 해석했는지 사용자가 볼 수 있어야 오타와 무결과를 구분할 수 있습니다. Phase 2 의 OpenSearch 질의도 같은 파서 결과로 만들어지므로 표시와 실제 질의가 어긋나지 않습니다.

## 5. 백엔드

### 5.1 `GET /api/meas-hist/search`

| 파라미터 | 설명 |
| --- | --- |
| `tool_type` | `cd-sem` \| `hv-sem` |
| `q` | 검색창 원문 |
| `fab` | 다중 선택 (반복 파라미터) |
| `model` | `eqp_model_cd` 다중 선택 |
| `eq` | `eqp_id` 다중 선택 |
| `recipe` | `full_name` 다중 선택 |
| `from`, `to` | 조회 기간 |
| `offset`, `limit` | 페이징 (기본 `limit=50`) |

응답:

```json
{
  "total": 1284,
  "capped": false,
  "offset": 0,
  "limit": 50,
  "range": { "from": "2026-05-15", "to": "2026-07-14" },
  "parsed": { "...": "..." },
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

### 5.3 `GET /api/meas-hist/facets`

`tool_type` 에 대해 존재하는 `fab`, `model`, `eq`, `recipe`(full_name) 값과 건수를 반환합니다. Phase 2 는 OpenSearch terms aggregation 입니다. 드롭다운은 실재하는 값만 보여줍니다.

### 5.4 파일 구성

- `back_dev_home/meas_hist/query.py` (신규) — 토큰 파서. 순수 함수.
- `back_dev_home/meas_hist/data.py` — `search_meas_hist(...)`, `get_meas_hist_facets(...)` 추가. 기존 600행 시드 데이터 위에서 in-memory 필터링합니다.
- `back_dev_home/meas_hist/routes.py` — 파라미터 마샬링만 합니다.

교체면(swap surface)은 `data.py` 안에 머뭅니다. Phase 2 는 이 두 함수만 OpenSearch 질의로 다시 쓰면 되고 라우트와 프런트엔드는 그대로입니다.

## 6. 프런트엔드

### 6.1 컴포저블

**`useMeasHistSearch.ts`** (신규)

- 상태: `queryText`, `filters`(`fab[]`, `model[]`, `eq[]`, `recipe[]`, `from`, `to`), `offset`, 결과(`rows`, `total`, `capped`, `parsed`).
- `search()` — 결과를 교체합니다. `loadMore()` — `offset += 50` 으로 이어붙입니다.
- **검색은 명시적입니다.** Enter 또는 Search 버튼에서만 실행합니다. 타이핑마다 60일 색인에 질의하면 lot id 하나 입력에 질의 여섯 번이 나갑니다. 반면 **필터 드롭다운 변경은 즉시 재검색**합니다. 의도적인 단일 동작이기 때문입니다.
- `narrowText` + `narrowedRows` — 로드된 행에 대한 클라이언트 즉시 필터입니다. 네트워크를 타지 않습니다.

**`useMeasHistFacets.ts`** (신규) — `useAsyncData('meas-hist-facets:<tool>')`. tool type 별로 캐시하며 모든 드롭다운이 공유합니다.

**`useSkewvoirRecentlyViewed.ts`** (신규) — localStorage 목록. `useSkewvoirSavedViews` 의 구조를 그대로 따릅니다 (모듈 수준 `readAll`/`writeAll`, `useState` 로 반응성 공유, `import.meta.client` 가드).

- `record(row)` — 앞에 추가, `msr` 기준 중복 제거, **최대 20건**, 저장.
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
| EQ | `eqp_id` | 다중 선택. FAB/모델 선택에 따라 좁혀집니다. |
| RECIPE | `full_name` | 다중 선택. 팝오버 안에 타입-투-필터 입력을 둡니다. 사무실 색인의 수백 개 레시피에서도 쓸 수 있어야 합니다. |
| 기간 | `timestamp` | 프리셋(24시간 / 7일 / 30일 / 60일) + 사용자 지정 범위 |

기존 `Area` 필터는 **삭제**합니다. `sem_list` 에도 `meas_hist` 에도 대응 필드가 없습니다. 아무것도 거르지 못하는 필터는 없는 것만 못합니다.

날짜 토큰과 기간 드롭다운은 **같은 파라미터**입니다. `date:2026-05-10` 을 입력하면 범위가 그날 하루로 설정되고 기간 칩도 그렇게 바뀝니다. 날짜 입력구가 둘로 갈라지지 않습니다.

필터는 검색어와 AND 로 결합합니다.

### 6.4 결과 영역

- **기본 상태(질의 없음): 빈 상태.** 무엇을 검색할 수 있는지와 60일 보존 안내만 보여줍니다.
- 결과는 **50건씩**, `더 보기` 로 다음 50건을 이어붙입니다. 페이지 번호는 두지 않습니다. 7페이지로 걸어가기보다 검색어를 좁히는 편이 언제나 낫습니다.
- 표 컬럼: `LOT · RECIPE(full_name) · EQ · FAB · CAPTURED`
- 기존 다중 선택 → `선택 분석 (Time-Series)` 와 저장된 뷰 팝오버는 유지합니다.

### 6.5 최근 본 측정

- 분석 워크스페이스로 측정을 열면 `{msr, lot, recipe, eq, fab, capturedAt, viewedAt}` 를 기록합니다.
- 60일 보존 창을 벗어난 항목은 **흐리게 표시하고 클릭을 막으며 `보존 기간 만료`** 를 붙입니다. 조용히 사라지게 하지 않습니다. 보존 규칙이 있다는 사실 자체가 두 달 만에 lot 을 다시 찾는 사람에게 필요한 정보입니다.
- 만료 판정은 `capturedAt` 날짜 계산으로 합니다. mock 에는 삭제 경로가 없습니다. Phase 2 는 저장된 msr 을 백엔드로 검증하는 방식으로 UI 변경 없이 올릴 수 있습니다.

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

`back_dev_home` pytest:

- **토큰 파서** — 필드별 형태 판별, `field:` 강제, 같은 필드 OR / 필드 간 AND, 구분자(공백·콤마·세미콜론) 처리, 미인식 토큰.
- **`search_meas_hist`** — 60일 clamp, 사용자 범위와의 교집합, 보존 창 밖 질의, `capped` 플래그, 페이징.
- **`get_meas_hist_facets`** — 값과 건수.

파서는 순수 함수이고 이 기능의 유일한 실질 로직이므로 제대로 테스트할 가치가 있습니다.
