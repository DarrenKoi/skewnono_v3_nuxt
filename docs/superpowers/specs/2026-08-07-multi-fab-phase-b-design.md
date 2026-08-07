# 사이드바 FAB 다중 선택 — Phase B 설계

recipe-search 계열과 live-alarm에 다중 FAB 지원을 추가하는 설계입니다.
Phase 1 설계 문서(`2026-08-07-multi-fab-selection-design.md`)의 6절에 기록해
둔 요구사항을 구현 가능한 형태로 확정합니다.

## 1. 배경

Phase 1에서 사이드바 다중 선택, 쉼표 URL 세그먼트, filter 형 feature
(storage·hardware·recipe-status)의 합산 조회가 완료되었습니다. key 형
backend를 쓰는 recipe-search 계열과 live-alarm은 `NavFabScopeNotice` 힌트를
띄운 채 primary FAB만 표시하도록 미뤄 두었고, 이번 Phase B가 그 잔여분입니다.

핵심 제약 두 가지가 설계를 결정합니다.

- **같은 recipe 이름이 FAB마다 존재합니다.** mock 기준 cd-sem R3∩M16B가
  50,000개 중 9,984개(약 20%)입니다. 따라서 목록의 각 행이 어느 FAB
  소속인지 태그가 필수이고(user-confirmed 2026-08-07), 상세 화면은 해당
  recipe 소유 FAB의 registry를 조회해야 합니다.
- **office catalog·registry는 FAB별 Redis hash입니다.**
  `v3_{cdsem|hvsem}_unique_rcp_list`(field = 소문자 fab),
  `v3_{family}_{rcp_loc|tools_in_rcp}_{fab}`. 현재의 전-FAB union 경로
  (`HGETALL` 후 이름 dedupe)는 FAB 출처를 파괴하므로 그대로 쓸 수 없습니다.

## 2. 결정 요약

| 결정 | 내용 |
| --- | --- |
| 범위 | recipe-search 계열 + recipe-status 상세 링크 seam + live-alarm을 한 spec·한 plan으로 진행 |
| 목록 행 단위 | (recipe, fab) 쌍당 1행 — 중복 이름은 인접 2행으로, dedupe 없음 (user-confirmed) |
| 상세 화면 | 데이터는 소유 FAB 단일 조회 유지, 라우팅만 소유 FAB을 전달 |
| compare | FAB 교차 비교 허용 — recipe별 fab을 body에 담음 |
| live-alarm 보드 | 병합 단일 피드 + 행별 FAB 배지 (user-confirmed) |
| 제외 | skew-check(영구), pm-planning(office adapter 미구현) |

## 3. 와이어 규약

Phase 1의 지배 규약을 그대로 씁니다.

- 요청: `?fab_name=R3,M16B` — 쉼표 결합, 대문자. 파싱은
  `_analytics_routes.resolve_analytics_scope`와 같은 모양의
  `tuple(part.strip().upper() …)`.
- 응답 meta: `fab_names: list[str]` — 요청 echo. fab 생략(전-FAB) 시 빈
  리스트.
- 프론트 캐시 키: `fabsKey`(= `fabs.join(',')`), 표시: `fabs.join(' + ')`,
  내보내기 파일명: `fabs.join('+').toLowerCase()`.

## 4. recipe-search 카탈로그

### 4.1 계약 — `recipe_search/contracts.py`

- `RecipeSearchRow`: `str` → `TypedDict {recipe_name: str, fab_name: str}`.
- `RecipeSearchResponse`: `fab_name: str | None` → `fab_names: list[str]`,
  `rows: list[RecipeSearchRow]`, `total = len(rows)`.

### 4.2 백엔드 — routes·providers

- `routes.py`의 `_resolve_fab_name()` → `_resolve_fab_names()`
  (`tuple[str, ...]`, 빈 튜플이면 전-FAB). `data.py`의
  `get_recipe_catalog(tool_type, fab_names=None)`로 전파합니다.
- mock: FAB별 생성 결과에 `fab_name`을 붙여 이어붙입니다. dedupe 없음.
- office(`office_example.py`):
  - FAB 지정 시 FAB당 `HGET` 1회씩 N회, 각 결과에 해당 fab 태그.
  - 전-FAB 경로는 기존 `HGETALL`을 유지하되 field 이름(=fab)으로 행을
    태그합니다 — 현재 파괴되던 출처가 복원됩니다. `_unique` dedupe는
    제거합니다(행 단위가 (recipe, fab)이므로 자연히 유일).
- lateral_recipe·meas_hist 백엔드는 **변경 없음** — 상세 화면이 소유 FAB
  단일 조회를 유지하기 때문입니다(6절).

### 4.3 프론트엔드

- `RecipeSearchView` props: `fab: Fab` → `fabs: string[]`. 데이터 fetch는
  `fab_name=fabs.join(',')` 1회 호출, 캐시 키는 `fabsKey`.
- 행에 FAB 배지 표시 — 선택 FAB이 2개 이상일 때만. 배지 색은 `--sk-*`
  토큰만 사용하고 스타일은 DESIGN.md를 따릅니다.
- OpenSearch fallback probe는 이미 리스트 인자(`fab: string[]`)를 받으므로
  `fabs` 전체를 넘깁니다. 다만 probe가 실제로 소비하는 것은 meas-hist의
  `recipe_names` 스냅샷이며, 이 스냅샷은 이름만 담을 뿐 FAB 정보를 담지
  않습니다. 그 결과 fallback 행은 `fab_name: ''`으로 채워지고, 배지는
  표시되지 않으며, 상세 라우트는 소유 FAB이 비어 있어 `primaryFab`으로
  대체됩니다. FAB별로 태그하려면 스냅샷 자체를 (name, fab) 쌍으로 확장해야
  하며, 이는 확정된 작업이 아니라 향후 검토 과제로 남겨 둡니다.
- 목록은 지금도 클라이언트 페이지네이션(메모리 내 배열)이므로 2 FAB 시
  약 10만 행은 구조 변경 없이 수용합니다. 문자열 → 객체 행 전환에 따른
  렌더·필터 경로만 수정합니다.

## 5. 선택·비교

- **선택 정체성은 (recipe_name, fab_name) 쌍**입니다.
  `useRecipeSelectionSet`은 toolType 단위 v2 키로 이동합니다:
  `skewnono:recipe-search.selection.v2.{toolType}`. FAB 체크박스를 바꿔도
  선택이 유지됩니다. 구 단일-FAB 키는 마이그레이션 없이 방치합니다(무해).
- `useRecipeRecentSearches`도 같은 이유로
  `skewnono:recipe-search.recent.v2.{toolType}`로 이동합니다 — 검색어는
  FAB 무관합니다.
- **compare** — `POST .../compare` body를
  `{"recipes": [{"recipe_name": str, "fab_name": str}]}`로 교체합니다
  (기존 `recipe_names` + 단일 `fab_name` 제거, 하위호환 없음 — 사내
  소비자뿐입니다). FAB 교차 비교를 허용합니다: 같은 이름의 R3본·M16B본
  비교가 이 기능의 동기이며, mock은 이미 (이름, fab) 시드로 서로 다른
  데이터를 생성합니다. compare 화면의 recipe 열마다 FAB 칩을 표시합니다.
  office compare는 현재 mock 재수출이므로 office 측 위험이 없습니다.

## 6. 상세 라우팅 — 소유 FAB을 쿼리로 전달

- `utils/recipeView.ts`의 `recipeDetailRoute()`는 **경로 세그먼트에 현재
  다중 선택을 유지**하고(사이드바 선택이 지워지지 않도록), 소유 FAB을
  `&fab_name=<owner>` 쿼리로 추가합니다.
- 상세 페이지(open·lateral·meas-hist)는
  `ownerFab = (route.query.fab_name)?.toUpperCase() ?? primaryFab`을
  구해 기존 스칼라 `fab` prop으로 View에 넘깁니다 — View 내부는 거의
  변경이 없고, 조회가 소유 FAB의 registry
  (`v3_..._rcp_loc_{fab}` 등)로 정확히 향하게 됩니다.
- 상세 화면에서 사이드바 FAB을 토글하면 카탈로그 index로 돌아가는 기존
  `matchFeatureFromPath` 동작을 **의도된 동작으로 확정**합니다 — 상세는
  FAB 소유물이므로 FAB 집합 변경이 상세를 무효화하는 것이 맞습니다.

### 6.1 recipe-status seam — ranking 행의 기여 FAB

- recipe-tat·fail-issue의 ranking 행(`RankingRow`·`AlignRankingRow`·
  `MeasRankingRow`)은 recipe 이름으로 집계되어 FAB이 없습니다. 각 행에
  `fab_names: list[str]`(그 집계에 측정을 기여한 FAB, 사전순)을
  추가합니다. 집계기는 이미 `fab_name`을 가진 측정 행을 순회하므로 set
  수집 비용은 무시할 수준입니다.
- `EbeamRecipeRowActions` props: `fab: string` → `fabNames: string[]`.
  기여 FAB이 1개면 그 FAB으로 즉시 이동, 2개 이상이면 액션 클릭 시 FAB
  선택 드롭다운을 보여 줍니다. `fabs[0]` 무언(無言) 강등이 사라집니다.
- `docs/api-contracts/{recipe-tat,fail-issue}.yaml`에 ranking 행의
  `fab_names` 추가를 반영합니다.

## 7. live-alarm

### 7.1 백엔드

- `routes.py`: `fab_name` 쉼표 리스트 허용, 빈 값은 기존대로 400.
- `contracts.py`:
  - `AlarmEvent`에 `fab_name: str` 추가 — reader가 roster의
    `placement_of(eqp_id)`로 stamping합니다(추가 필드, 파생 값).
  - `LiveAlarmPayload`: `fab_name: str` → `fab_names: list[str]` +
    `not_configured_fabs: list[str]` 추가.
- provider(mock·office_example 공통 계약):
  - 선택 FAB → `fac_id_for`로 **중복 제거된 fac 집합** K개를 구합니다.
    M16A·M16B·M16C는 fac을 공유하므로 K ≤ N입니다.
  - fac마다 기존 `ensure_fresh`를 수행합니다 — 비용은 fac당 20초에 최대
    1회의 office 호출로 불변이고, K배가 상한입니다(R3+M16B는 2배,
    M16A+M16B+M16C는 1배).
  - 보드는 fac별 `ZRANGEBYSCORE` 결과를 합치고, 이벤트마다
    `placement_of`로 fab을 stamping한 뒤 선택 FAB 집합에 속한 것만 남겨
    `occurred_epoch` 내림차순 정렬합니다.
  - `unmatched_count`는 **fac당 1회씩** 합산합니다(형제 FAB 중복 가산
    방지).
  - `feed_status`: 선택 FAB 전부가 미구성일 때만 `not_configured`.
    구성된 fac 중 하나라도 stale이면 `stale`(보수적 — 데이터 불완전
    가능성을 알림). `fetched_at`은 구성된 fac 중 최솟값(가장 오래된
    성공)으로 보고합니다.
  - 일부 FAB만 미구성이면 보드는 정상 표시하고
    `not_configured_fabs`에 담아 프론트가 "M16B: 미구성" 한 줄을
    덧붙입니다.

### 7.2 프론트엔드

- `useLiveAlarmFeed(toolType, fabs: string[])` — 요청 1회에
  `fab_name=R3,M16B`, useState 키는 `live-alarm:{slug}:{fabsKey}`.
  페이지는 이미 `fullPath` 키로 리마운트되므로 폴링 재바인딩은 기존
  메커니즘 그대로입니다.
- 행·meas 그룹 헤더에 FAB 배지 — 선택 FAB 2개 이상일 때만. meas 그룹은
  (eqp, ppid) 단위라 본질적으로 단일 FAB이므로 그룹 첫 이벤트의
  `fab_name`을 씁니다.
- 행의 recipe-search 링크는 현재 다중 세그먼트를 유지합니다 — 카탈로그가
  다중 FAB이 되므로 검색이 올바르게 안착하고 배지가 소속을 구분해 줍니다.

## 8. NavFabScopeNotice 정리

업그레이드되는 12개 페이지(recipe-search 10 + live-alarm 2)에서
`NavFabScopeNotice`를 제거합니다. skew-check·pm-planning에는 유지합니다.

## 9. 테스트·검증

- 백엔드 pytest: route별 쉼표 파싱, mock 태그 행(중복 이름 인접 2행),
  office union 경로의 출처 태그, compare body 신규 형태, ranking 행
  `fab_names`, live-alarm fac 중복 제거·stamping·`unmatched_count`
  합산·부분 미구성, provider-contract 스위트(office 테스트는 import-skip
  별칭 패턴으로 홈에서도 실행).
- 프론트 unit(`node --test`): 선택 v2 (recipe, fab) 정체성,
  `recipeDetailRoute`의 owner 쿼리, feed 키 생성.
- 브라우저 검증(Playwright MCP, `verify` skill): 중복 이름 2행의 상이한
  배지, M16B 행 → M16B 상세 데이터, FAB 교차 compare, live-alarm 병합
  보드 배지, notice 제거 확인.
- 작업은 CLAUDE.md 규칙대로 전용 `git worktree`에서 진행합니다.

## 10. office 전달 메모

`office_example.py`가 바뀌는 feature는 사무실에서 `office.py` 재복사가
필요합니다. **recipe_search, live_alarm, recipe_tat, fail_issue 네
feature 모두** 해당합니다 — ranking/카탈로그 집계 로직이 공유 추적
파일(`_office_meas_hist.py` 등)이 아니라 **각 provider 자신의
`office_example.py`**(`get_recipe_catalog`, `get_board`, `get_ranking`,
`get_align_ranking`/`get_meas_ranking`)에 있으므로, 넷 다 같은 office
배포에서 재복사가 필요합니다. 부팅 로그의 `STALE office.py` 표시와
`python -m scripts.sync_office_adapters`가 최종 판정입니다.

## 11. 하지 않는 것

- meas_hist·lateral_recipe 백엔드 변경 — 상세 화면이 소유 FAB 단일
  조회를 유지하므로 불필요합니다.
- 구 selection·recent localStorage 키 마이그레이션 — 방치해도 무해합니다.
- FAB별 시리즈 분리 차트, 사이드바 즐겨찾기 필터(Phase 1에서 제외 확정).
- skew-check·pm-planning의 다중 FAB.
