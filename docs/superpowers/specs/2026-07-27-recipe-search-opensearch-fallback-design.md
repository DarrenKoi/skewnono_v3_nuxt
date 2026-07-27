# Recipe 검색 Redis → OpenSearch Failover — Design

- **Date:** 2026-07-27
- **Feature:** `front-dev-home/app/components/ebeam/RecipeSearchView.vue`
- **Status:** Approved design, pending implementation plan

## Goal

Recipe 검색의 빠른 진입점은 Redis Recipe catalog로 유지하되, Redis가
응답하지 않거나 유효한 결과를 제공하지 못하면 기존 OpenSearch 측정 이력
검색을 실제 대체 검색 경로로 사용합니다.

OpenSearch에서 발견한 Recipe는 안내 문구로만 보여주지 않고 일반 검색
결과처럼 선택할 수 있어야 합니다. 다만 현재 office `열어보기`와 `비교하기`는
실제 IDP 데이터가 아니라 synthetic mock 데이터에 의존하므로, OpenSearch
fallback Recipe에는 `횡전개`와 `측정 이력`만 제공합니다.

## Product Intent

Redis와 OpenSearch는 같은 역할의 중복 저장소가 아닙니다.

- Redis는 Recipe 이름 catalog를 하루 주기로 갱신합니다. 페이지가 catalog를
  한 번 받은 뒤에는 브라우저 메모리에서 즉시 필터링하므로 타이핑 중 검색이
  빠릅니다.
- OpenSearch `meas_hist_*`는 측정 이력의 실제 소스입니다. Redis보다 최근에
  생성된 Recipe를 발견할 수 있으며, Redis 장애 때도 Recipe 검색 진입점을
  유지합니다.
- `횡전개`와 `측정 이력`은 검색 결과의 출처와 관계없이 이미 OpenSearch를
  읽습니다. 따라서 OpenSearch가 찾아낸 `full_name`은 두 화면의 유효한
  Recipe 식별자입니다.
- OpenSearch는 Redis 결과에 항상 합치는 추가 소스가 아닙니다. Redis가 현재
  검색어에 결과를 제공하면 OpenSearch를 호출하지 않습니다.

## Current State

`RecipeSearchView.vue`는 Redis catalog를
`/<tool>/recipe-search/recipes`에서 내려받아 `rankRecipeMatches()`로
클라이언트 검색합니다.

현재도 Redis 검색 결과가 0이면 600ms debounce 후
`/meas-hist/search`를 호출합니다. 응답 row의 `full_name`을
`matchingHistoryNames()`로 deduplicate하고 동일한 AND-token 의미를 다시
적용합니다. 그러나 결과는 toast와 다음 문구에만 사용합니다.

> redis에는 없지만 측정 기록은 발견됩니다. (redis update 주기 1일)

또한 현재 fallback 조건은 Redis catalog 요청이 성공한 경우만 허용합니다.
Redis 요청 자체가 실패하면 기존 error 화면에서 중단되며 OpenSearch를
시도하지 않습니다.

## Scope

포함 범위는 다음과 같습니다.

- Redis 요청 실패, 빈 catalog, 현재 검색어의 Redis 0건을 OpenSearch
  fallback 조건으로 처리합니다.
- OpenSearch `full_name`을 일반 Recipe result row로 승격합니다.
- Redis/OpenSearch row를 모두 선택할 수 있게 합니다.
- 선택 항목에 검색 출처를 저장하고 지원 action을 계산합니다.
- OpenSearch row와 OpenSearch를 포함한 작업 세트에는 `횡전개`와
  `측정 이력`만 제공합니다.
- detail route와 Recipe switcher에서 출처를 보존하여 우회 경로로
  `열어보기`가 노출되지 않게 합니다.
- 기존 localStorage의 `string[]` 작업 세트를 새 선택 구조로
  migration합니다.
- 기존 debounce, stale-response 방지, 검색 ranking, 결과 내 filter,
  pagination을 유지합니다.

제외 범위는 다음과 같습니다.

- office `recipe-detail`의 실제 IDP 데이터 연결
- OpenSearch Recipe의 `열어보기` 또는 `비교하기`
- Redis와 OpenSearch 결과의 상시 merge
- 새 Flask endpoint 또는 backend response contract
- `/meas-hist/search`를 distinct Recipe aggregation으로 교체하는 작업

## Failover Decision

검색어는 현재와 같이 의미 있는 3자 이상 입력해야 합니다. 검색어가 조건을
충족하기 전에는 Redis 상태와 관계없이 OpenSearch를 호출하지 않습니다.

| Redis catalog 상태 | 현재 Redis match | 동작 |
| --- | --- | --- |
| 정상, row 있음 | 1건 이상 | Redis 결과만 즉시 표시하며 OpenSearch를 호출하지 않습니다. |
| 정상, row 있음 | 0건 | debounce 후 OpenSearch를 검색합니다. |
| 정상, catalog가 비어 있음 | 0건 | debounce 후 OpenSearch를 검색합니다. |
| 요청 실패 | 판정 불가 | Redis 오류로 페이지를 막지 않고 debounce 후 OpenSearch를 검색합니다. |

Redis 요청 실패 또는 빈 catalog는 해당 페이지 세션에서 fallback mode로
표시합니다. 사용자가 Retry로 Redis catalog를 다시 받아 성공하면 이후
검색은 다시 Redis 우선 흐름을 사용합니다.

OpenSearch 요청 상태는 다음처럼 처리합니다.

| OpenSearch 상태 | 화면 |
| --- | --- |
| 대기 중 | `OpenSearch에서 Recipe를 검색하는 중입니다.` loading 상태를 표시합니다. |
| 1건 이상 | 일반 결과 표를 OpenSearch source badge와 함께 표시합니다. |
| 0건 | 두 소스에서 결과를 찾지 못한 empty state를 표시합니다. |
| 실패 | Redis가 사용 가능하면 non-blocking fallback 오류를 표시하고 Redis 0건을 유지합니다. Redis도 실패했다면 두 검색 소스를 사용할 수 없다는 오류를 표시합니다. |

stale OpenSearch response는 현재 `historyProbeSeq` 방식으로 폐기합니다.
검색어, tool type, fab 또는 Redis match 상태가 바뀌면 이전 timer와 결과를
즉시 무효화합니다.

## OpenSearch Query Contract

기존 `useMeasHistApi().searchMeasHist()`를 그대로 사용합니다.

```ts
searchMeasHist({
  toolType,
  fab: fab ? [fab] : undefined,
  recipe: tokenizeRecipeQuery(query),
  limit: 200
})
```

`/meas-hist/search`는 Recipe token을 OpenSearch의
`recipe_name.keyword`와 `full_name.keyword` substring 조건으로 찾고,
최근 측정 row부터 반환합니다. 서버 조건은 token 사이를 OR 처리하므로
frontend의 `matchingHistoryNames()`가 모든 token을 포함하는지 다시 확인하여
Redis 검색과 같은 AND 의미를 복원합니다.

이 계약은 최근 matching measurement row 최대 200건에서 distinct
`full_name`을 도출합니다. 전체 OpenSearch Recipe catalog를 보장하는
aggregation은 이번 범위가 아닙니다. 결과 ceiling을 확대하거나 distinct
Recipe endpoint가 필요하면 별도 backend 변경으로 다룹니다.

## Result Model

화면 result와 persisted selection은 source를 명시합니다.

```ts
type RecipeSearchSource = 'redis' | 'opensearch'

interface RecipeSearchResult {
  recipe_name: string
  source: RecipeSearchSource
}

interface RecipeSelectionEntry {
  name: string
  source: RecipeSearchSource
}
```

현재 Redis result는 `source: 'redis'`, fallback result는
`source: 'opensearch'`입니다. 이름 비교와 deduplication은 기존 동작을
보존하여 exact string을 identity로 사용합니다.

## Selection Persistence and Migration

현재 `useRecipeSelectionSet()`은 localStorage에 `string[]`를 저장합니다.
새 normalizer는 다음 두 형식을 모두 받습니다.

- legacy string은 `{ name: string, source: 'redis' }`로 migration합니다.
- 새 object는 유효한 `name`과 `source`만 유지합니다.

기존 사용자가 저장한 항목은 이 기능 이전에 Redis result에서만 선택할 수
있었으므로 Redis로 migration하는 것이 맞습니다.

같은 이름을 중복 저장하지 않습니다. 기존 OpenSearch selection이 이후
Redis catalog에 포함되면 source를 `redis`로 승격하여 `열어보기`와
`비교하기`를 다시 사용할 수 있게 합니다. Redis 일시 장애나 catalog
변동으로 이미 확인된 Redis selection을 OpenSearch로 강등하지는 않습니다.

composable은 source-aware entry와 기존 consumer가 사용할 name 목록을 함께
제공합니다. 이름 표시, 삭제, Recipe switcher는 name 목록을 사용하고,
action gating과 route 작성은 entry의 source를 사용합니다.

## Capability Rules

| Result/selection source | 선택 | 열어보기 | 횡전개 | 측정 이력 | 비교하기 |
| --- | --- | --- | --- | --- | --- |
| Redis | 가능 | 가능 | 가능 | 가능 | 가능 |
| OpenSearch | 가능 | 불가 | 가능 | 가능 | 불가 |

작업 세트 action은 선택 항목 전체의 capability 교집합으로 계산합니다.

- Redis-only set은 기존 네 action을 유지합니다.
- OpenSearch-only 또는 mixed set은 `횡전개`, `측정 이력`만 제공합니다.
- 숨겨진 action handler에도 동일한 guard를 둡니다. UI 숨김만으로 synthetic
  detail 요청을 막았다고 간주하지 않습니다.

작업 세트의 `횡전개`와 `측정 이력`은 현재처럼 첫 selection을 열고 `set=1`로
Recipe switcher를 활성화합니다. 두 화면은 모든 source의 selection을
전환할 수 있습니다.

## Route and Detail Navigation

OpenSearch result가 detail service로 이동할 때 query에
`source=opensearch`를 추가합니다. Redis는 기존 URL을 유지합니다.

```text
.../lateral?recipe_name=<full_name>&source=opensearch
.../meas-hist?recipe_name=<full_name>&source=opensearch
```

`recipeDetailRoute()`와 `buildRecipeDetailNavItems()`가 source를 전달하고
지원 screen만 생성합니다.

- OpenSearch Recipe의 detail nav에는 `횡전개`와 `측정 이력`만 표시합니다.
- Redis Recipe에는 기존 `열어보기`, `횡전개`, `측정 이력`을 표시합니다.
- Recipe switcher가 항목을 바꾸면 선택 entry의 source로 query를 함께
  교체합니다.
- `열어보기` 화면의 Recipe switcher에는 Redis selection만 표시하여 mixed
  set에서 OpenSearch Recipe로 전환하는 우회 경로를 차단합니다.
- compare view는 Redis-only set이 아니면 request를 보내지 않는 defensive
  guard를 둡니다.

`source` query는 frontend capability context이며 보안 경계는 아닙니다.
실제 IDP source가 연결될 때 OpenSearch Recipe의 `open` capability를
활성화하고 해당 query를 그대로 재사용할 수 있습니다.

## UI

Redis와 OpenSearch는 동일한 results table을 사용합니다. 별도 fallback
table을 만들지 않아 결과 내 filter, page size, pagination, row action
layout이 두 경로에서 달라지지 않게 합니다.

- OpenSearch 결과 section에는 `OpenSearch fallback` badge를 표시합니다.
- 각 OpenSearch row에는 Recipe 이름과 `OpenSearch` source indicator를
  표시합니다.
- checkbox는 두 source 모두 동일하게 제공합니다.
- OpenSearch row action cell에는 `횡전개`, `측정 이력`만 표시합니다.
- Redis row는 기존 세 action을 유지합니다.
- `Matched` stat과 result count는 현재 화면에 표시하는 active source의
  결과 수를 사용합니다.
- Redis 장애 중에는 기존 `Recipe 목록을 불러오지 못했습니다.` blocking
  화면 대신 `Redis를 사용할 수 없어 OpenSearch fallback을 사용합니다.`
  상태를 검색 입력 근처에 표시합니다.

기존 amber hint와 toast는 실제 result table로 대체합니다. 결과가 이미
작업 가능한 row로 보이므로 같은 사실을 toast로 반복하지 않습니다.

## Component Boundaries

주요 변경 seam은 다음과 같습니다.

- `RecipeSearchView.vue`
  - Redis/OpenSearch failover state와 active results를 조합합니다.
  - source별 row action과 selection을 연결합니다.
- `recipeSearchMatch.ts`
  - OpenSearch name을 source-aware result로 만드는 pure helper와 active
    result 결정을 둡니다.
- `useRecipeSelectionSet.ts`
  - selection normalizer, source migration/promotion, capability 계산을
    소유합니다.
- `SearchSelectTray.vue`
  - parent가 계산한 available action만 표시합니다.
- `recipeView.ts`, `RecipeDetailNav.vue`, `RecipeSwitcher.vue`
  - source-preserving route와 screen gating을 담당합니다.
- `RecipeCompareView.vue`
  - Redis-only set인지 request 전에 방어적으로 확인합니다.

Vue component에 provider 호출이나 OpenSearch query shape를 새로 복제하지
않습니다. API 호출은 기존 composable을 사용하고, source/capability
결정은 pure helper 또는 selection composable에 둡니다.

## Testing

frontend는 Vue mounting harness가 없으므로 pure TypeScript seam을 Node test
runner로 검증합니다.

- Redis match가 있으면 OpenSearch result를 active result로 선택하지
  않습니다.
- Redis 실패, 빈 catalog, query 0건에서 OpenSearch result를 선택합니다.
- OpenSearch response의 중복 제거와 AND-token 의미를 보존합니다.
- legacy `string[]` selection을 Redis entry로 migration합니다.
- malformed selection object를 제거합니다.
- 동일 Recipe를 source와 관계없이 한 번만 저장합니다.
- OpenSearch selection을 Redis로 승격하며 반대 방향으로 강등하지
  않습니다.
- Redis-only, OpenSearch-only, mixed set의 capability 교집합을 검증합니다.
- source별 row action을 검증합니다.
- OpenSearch route가 source를 보존하고 `open` nav를 생성하지 않음을
  검증합니다.
- Redis route와 기존 detail navigation contract가 바뀌지 않음을
  검증합니다.
- compare request guard가 OpenSearch를 포함한 set을 거부함을 검증합니다.
- stale OpenSearch response가 현재 query 결과를 덮지 않는 기존 sequence
  guard를 유지합니다.

## Verification

구현 후 `front-dev-home/`에서 다음 명령을 실행합니다.

```text
npm run lint
npm run typecheck
npm test
npm run build
```

repo root에서 다음 명령을 실행합니다.

```text
git diff --check
```

실행 중인 앱에서는 다음 시나리오를 확인합니다.

1. Redis match가 있는 검색은 OpenSearch를 호출하지 않고 기존 결과/action을
   유지합니다.
2. Redis 0건은 OpenSearch 결과 표와 `횡전개`, `측정 이력`을 표시합니다.
3. Redis 요청 실패도 검색 입력을 막지 않고 OpenSearch fallback을
   사용합니다.
4. OpenSearch row를 여러 개 선택하고 두 지원 화면에서 Recipe switcher로
   전환할 수 있습니다.
5. mixed set은 `열어보기`, `비교하기`를 노출하거나 호출하지 않습니다.
6. Redis와 OpenSearch가 모두 실패하면 두 소스를 사용할 수 없다는 상태를
   표시합니다.

## Future: OpenSearch Recipe 열어보기

office `recipe-detail`이 실제 IDP source에 연결되면 OpenSearch result의
`open` capability를 활성화합니다. 그때까지는 synthetic mock table을 실제
Recipe 정보처럼 노출하지 않습니다. 이번 source-aware selection과 route
구조는 이후 capability 한 항목을 변경하는 방식으로 확장할 수 있어야
합니다.
