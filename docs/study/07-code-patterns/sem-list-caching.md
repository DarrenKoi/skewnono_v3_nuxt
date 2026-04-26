# sem-list 캐싱과 죽은 코드 정리 (2026-04-26 세션)

이 문서는 `/simplify` 리뷰로 시작된 한 세션에서 정리한 **`front-dev-home`의 데이터 패칭 구조 결정**을 기록합니다. 단순한 변경 이력이 아니라, 각 결정 뒤에 숨은 *왜*에 초점을 맞춥니다.

**관련 커밋:**

| 커밋 | 제목 |
| --- | --- |
| `ead8384` | Remove dead navigation code |
| `44b50db` | Make tool-inventory table display match its filter/export pipeline |
| `fc19681` | Consolidate /sem-list fetches behind one useSemList composable |

## 1. 죽은 코드와 "write-only state" 패턴

### 1.1 발견한 것

`/simplify` 리뷰 결과 다음 코드가 **사용되지 않는데도 작동하고 있었습니다.**

- `composables/useFavorites.ts` — 어디서도 `import`되지 않음
- `composables/useRecent.ts` — 어디서도 `import`되지 않음
- `stores/navigation.ts`의 `recent` 상태 + `addRecent` 액션
- `pages/ebeam/{cd-sem,hv-sem,verity-sem,provision}/[fab]/index.vue` 4개 파일의 `addRecent(next)` 호출

흥미로운 점은 `recent`가 단순히 안 쓰인 게 아니라 **쓰이긴 하지만 읽히지 않았다**는 것입니다. 4개의 fab 페이지가 이동할 때마다 충실히 `addRecent`를 호출했지만, 그 결과를 화면에 보여줄 코드는 한 줄도 없었습니다. `pages/index.vue`의 "Recent" 카드는 단순히 `"No recent activity"`라는 하드코딩된 문자열만 표시하고 있었습니다.

### 1.2 왜 이런 코드가 살아남았는가

타입 검사기는 **양 끝이 모두 정상이면** 통과시킵니다.

- 쓰는 쪽: `addRecent(next)` — 진짜 함수 호출, 시그니처 일치, 통과
- 받는 쪽: `state.value.recent = [...]` — 진짜 배열 mutation, 통과

타입스크립트가 잡지 못하는 것은 "이 데이터를 누군가 *읽긴 하는가?*" 입니다. 컴파일러는 함수가 호출되었는지, 변수가 쓰여졌는지는 알지만, 그 결과가 *소비*되는지는 모릅니다.

이런 패턴을 **write-only state** 또는 **dangling pipeline**이라고 부릅니다. 보통 다음과 같은 경위로 생깁니다.

1. 처음에 기능 A를 절반 구현하다 "Recent 표시는 나중에" 하고 미룬다.
2. 그 사이에 "쓰는 쪽"만 머지된다.
3. 시간이 지나면 누가 왜 만들었는지 잊힌다.
4. 컴파일도 되고 테스트도 통과하니 그 상태로 굳는다.

### 1.3 발견 방법

`grep`으로 *읽기*와 *쓰기*를 분리해서 보면 드러납니다.

```bash
# recent를 쓰는 곳
grep -rn "addRecent\|state\.recent\s*=" front-dev-home/app

# recent를 읽는 곳
grep -rn "store\.recent\|\.recent\b" front-dev-home/app | grep -v "addRecent\|state\.value\.recent"
```

쓰는 곳은 5곳(상태 정의 + 4개 페이지), 읽는 곳은 0곳이었습니다. 배경 노이즈가 0이라면 그 파이프라인은 죽은 것입니다.

### 1.4 교훈

- **타입 검사 통과 ≠ 코드가 의미 있다.** 양 끝이 일치해도 중간에 소비자가 없으면 죽은 파이프라인입니다.
- 새 기능을 추가할 때 **소비자(UI 표시)부터** 만드는 것이 안전합니다. 표시할 곳이 없는 데이터는 일단 모으지 않습니다.
- 정기적으로 `useXxx`, `addXxx` 같은 함수의 호출자를 *읽기 측*만 따로 카운트해 보면 좋습니다.

## 2. UTable 필터 파이프라인 일치 (single source of truth)

### 2.1 문제

`components/ebeam/ToolInventoryView.vue`에서 `<UTable>`이 두 개의 필터 파이프라인을 동시에 돌리고 있었습니다.

```vue
<!-- before -->
<UTable
  v-model:global-filter="globalFilter"
  v-model:column-filters="columnFilters"
  v-model:sorting="sorting"
  :data="rows"
  ...
/>
```

여기서 `:data="rows"`는 **원본 데이터**입니다. TanStack Table 내부가 `globalFilter`/`columnFilters`/`sorting`을 기준으로 자기만의 필터를 다시 돌렸습니다.

동시에 같은 컴포넌트 안에서:

```ts
const filteredRows = computed(() => rows.value.filter(matchesActiveFilters))
const exportRows = computed(() => /* filteredRows를 sorting에 맞게 정렬 */)
```

이 JavaScript 파이프라인이 **헤더 카운터(`X of Y tools`)**와 **CSV 다운로드** 결과를 만들고 있었습니다.

즉, 사용자가 화면에서 보는 표는 *TanStack의 결과*, 카운터와 CSV는 *JS의 결과*였습니다. 대부분의 입력에서는 두 결과가 일치했지만, 두 필터 구현체가 미묘하게 다를 수 있는 지점(예: 숫자 컬럼 `version`에 대한 globalFilter 동작)에서는 어긋날 수 있었습니다.

### 2.2 수정

```vue
<!-- after -->
<UTable
  v-model:sorting="sorting"
  :data="exportRows"
  ...
/>
```

- 이미 필터링·정렬된 `exportRows`를 데이터로 넘깁니다.
- `v-model:global-filter`/`v-model:column-filters` 바인딩은 제거합니다 — 이중 필터를 막기 위함입니다.
- `v-model:sorting`만 유지합니다. 이건 컬럼 헤더의 정렬 화살표 아이콘이 방향을 표시하기 위해 필요한 *시각 상태*입니다.

이제 화면 표시, 헤더 카운터, CSV 다운로드 모두 **하나의 진실 공급원**(`exportRows`)에서 나옵니다.

### 2.3 교훈

UI 라이브러리가 제공하는 "내부 필터링" 기능과 직접 작성한 `computed` 필터를 **같은 데이터에 대해 동시에 돌리지 마세요.** 둘 중 하나만 골라야 합니다.

- 라이브러리 내부에 맡길 거면: 카운터·내보내기 같은 부수 정보도 라이브러리 API(`getRowModel()` 등)에서 읽어야 합니다.
- 직접 만들 거면: 라이브러리에는 이미 처리된 데이터를 넘기고 라이브러리의 필터 기능은 끕니다.

## 3. TanStack Query vs Nuxt useAsyncData

### 3.1 결정

이 프로젝트는 **TanStack Query(Vue Query)를 사용하지 않습니다.** Nuxt 내장 `useAsyncData`로 충분합니다.

`CLAUDE.md`에 한때 "Data fetching: TanStack Query (Vue Query)"라고 적혀 있었지만, 실제 코드에는 `@tanstack/vue-query`가 설치된 적도, 사용된 적도 없었습니다. 문서가 *희망사항*이었던 셈이고, 이번 세션에서 문서를 실제 코드와 일치시켰습니다.

### 3.2 비교 표

| 필요한 기능 | `useAsyncData` | TanStack Query |
| --- | --- | --- |
| 키 단위 캐시 + 동시 호출 dedupe | ✅ | ✅ |
| 수동 무효화 (`refresh`/`clearNuxtData`) | ✅ | ✅ |
| TTL / stale window (`staleTime`) | ❌ | ✅ |
| 윈도우 포커스/온라인 시 재패치 | ❌ | ✅ |
| 폴링 인터벌 | ❌ (수동 setInterval) | ✅ |
| 키 prefix 단위 무효화 | ❌ | ✅ |
| Mutation + 낙관적 업데이트 | ❌ (수동) | ✅ |
| 자동 재시도/백오프 | ❌ | ✅ |
| 전용 DevTools | ❌ | ✅ |

오른쪽 열의 기능 중 **현재 프로젝트가 실제로 필요로 하는 것이 하나도 없습니다.**

- mock 데이터는 변하지 않으므로 "stale" 개념이 의미 없습니다.
- 폴링이 필요한 화면은 아직 없습니다.
- mutation은 클라이언트 측 필터/정렬 정도이고 서버 변경이 없습니다.

### 3.3 언제 도입을 검토해야 하는가

다음 중 하나라도 진짜 요구사항이 되면 그때 검토합니다.

- 장비 상태(On/Off)를 실시간 가까이 보여줘야 한다 → 폴링이나 SSE 필요.
- 사용자가 즐겨찾기를 서버에 저장하고 즉시 반영되는 UI가 필요하다 → mutation + 낙관적 업데이트.
- 캐시된 데이터의 신선도가 중요해진다 → `staleTime`.

그 전에는 도입 비용(번들 사이즈 + 학습 곡선 + 또 하나의 패턴)만 떠안는 셈입니다.

## 4. `/sem-list` 패칭 통합 — `useSemList()` 컴포저블

### 4.1 통합 전 상태

`/api/sem-list` 엔드포인트는 **항상 보이는 네비게이션 chrome**의 데이터 소스입니다.

- `NavToolTypeTabs` (CD-SEM/HV-SEM/… 탭의 카운트 뱃지)
- `NavFabSidebar` (왼쪽 fab 목록 R3/R4/M16…)
- `pages/index.vue` (허브 페이지 카운트)
- `EbeamToolInventoryView` (메인 인벤토리 표)

문제는 4곳이 **각각 다른 `useAsyncData` 키**를 쓰고 있었다는 점입니다.

| 파일 | 캐시 키 |
| --- | --- |
| `pages/index.vue` | `'sem-list-base'` |
| `components/nav/ToolTypeTabs.vue` | `'sem-list-tool-types'` |
| `components/nav/FabSidebar.vue` | `'sem-list:fab-names'` |
| `components/ebeam/ToolInventoryView.vue` | `` `sem-list:${toolType}:${fab}` `` |

키가 다르면 Nuxt는 *다른 자원*으로 간주합니다. 결과적으로 `/ebeam/cd-sem/r3` 한 페이지를 띄울 때 **`/api/sem-list`로 3건의 동일 요청**이 나갔습니다.

### 4.2 통합 후 상태

단 하나의 컴포저블로 일원화했습니다.

```ts
// app/composables/useSemListApi.ts
const SEM_LIST_CACHE_KEY = 'sem-list'

export const useSemList = () => {
  const { fetchSemList } = useSemListApi()
  const fetchOnce = () => {
    if (!inFlightSemList) {
      inFlightSemList = fetchSemList().catch((err) => {
        inFlightSemList = null
        throw err
      })
    }
    return inFlightSemList
  }
  return useAsyncData(SEM_LIST_CACHE_KEY, fetchOnce, {
    default: () => [] as SemListRow[],
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}
```

소비자 측은 모두 같은 한 줄로 바뀌었습니다.

```ts
// pages/index.vue, ToolTypeTabs.vue, FabSidebar.vue, ToolInventoryView.vue
const { data: semRows } = await useSemList()
```

각 컴포넌트는 자기 뷰에 맞게 `computed`로 파생값만 만듭니다.

```ts
// FabSidebar
const fabNames = computed(() => extractFabNames(semRows.value ?? []))

// ToolInventoryView
const rows = computed<SemListRow[]>(() =>
  filterRows(allRows.value ?? [], props.toolType, props.fab)
)
```

### 4.3 검증 결과 (Playwright 측정)

| 동작 | 통합 전 | 통합 후 |
| --- | --- | --- |
| `/ebeam/cd-sem/r3` 첫 로드 | 3 요청 | **1 요청** |
| `r3` → `r4` 사이드바 클릭 | 1 추가 요청 | **0 추가 요청** |
| `cd-sem` → `hv-sem` 탭 전환 | 1 추가 요청 | **0 추가 요청** |

페이지 간 이동에서 추가 요청이 0건이라는 점이 핵심입니다 — 같은 SPA 세션 동안 데이터가 살아있다는 의미입니다.

## 5. Nuxt `useAsyncData` 중복 제거의 함정

같은 캐시 키를 썼는데도 처음엔 여전히 3건의 요청이 나갔습니다. 그 이유를 이해하는 것은 Nuxt를 깊이 다룰 때 매우 유용합니다.

### 5.1 두 가지 dedupe 메커니즘

Nuxt의 `useAsyncData`는 두 가지 중복 방지 장치를 가집니다.

1. **In-flight promise** (`nuxtApp._asyncDataPromises[key]`)
    - 같은 키로 진행 중인 요청이 있으면 그 Promise를 재사용.
    - 요청이 끝나면(`finally`) 이 항목은 **삭제**됩니다.
2. **Cached payload** (`nuxtApp.payload.data[key]`)
    - 요청 결과가 저장되는 곳. 다음 호출이 이걸 보고 패치를 건너뛸 수 있습니다.
    - 단, 가져갈지 말지를 결정하는 게 `getCachedData` 옵션입니다.

### 5.2 기본 `getCachedData`의 함정

Nuxt 4의 기본 `getCachedData`는 대략 이렇게 동작합니다.

```ts
getCachedData: (key, nuxtApp, ctx) => {
  if (ctx.cause === 'initial' || nuxtApp.isHydrating) {
    return nuxtApp.payload.data[key]
  }
  // 그 외에는 undefined → 새로 패치
}
```

`ssr: false` SPA 모드에서는 **`isHydrating`이 매우 짧은 순간만 true**입니다. 그 윈도우가 닫히고 나서 마운트되는 형제 컴포넌트는 페이로드에 데이터가 있어도 못 보고, *새로* 패치해 버립니다.

### 5.3 Suspense 경계와 동시성

`<NuxtPage>`와 그 위의 layout 컴포넌트들은 각각 별도의 Suspense 경계를 가집니다. 컴포넌트들이 *동시에* 마운트되는 것 같지만, 실제로는 각자의 `<script setup>` `await`이 마이크로태스크 큐 경계를 건너면서 **순차적으로** 실행되는 경우가 많습니다.

그러면 다음 시나리오가 발생합니다.

1. 컴포넌트 A: `useAsyncData('sem-list', fn)` → in-flight promise 등록 → fetch 시작.
2. fetch 완료 → A의 promise resolved → `_asyncDataPromises['sem-list']` 삭제.
3. 컴포넌트 B: `useAsyncData('sem-list', fn)` → in-flight 없음, `getCachedData`도 hydration 끝나서 `undefined` 반환 → **새 fetch**.
4. 같은 방식으로 컴포넌트 C도 새 fetch.

총 3건의 요청. 정확히 이번에 관측된 패턴이었습니다.

### 5.4 두 단계 해법

#### 5.4.1 1단계 — 명시적 `getCachedData`

```ts
useAsyncData(key, fn, {
  getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
})
```

이걸 추가하면 hydration 윈도우가 끝난 후에도 페이로드의 캐시를 사용합니다. 이론상은 이걸로 충분해 보이지만, **실측에서는 여전히 3건**이 나갔습니다. 이유는 다음과 같습니다.

세 컴포넌트가 *동시에* setup을 시작하는 케이스에서는 `getCachedData`가 호출될 때마다 페이로드가 **아직 비어있을 수** 있습니다(첫 fetch가 끝나기 전). 그러면 모두 새 패치를 시작하고, 1단계 보호막이 무력화됩니다.

#### 5.4.2 2단계 — 모듈 스코프 in-flight promise

```ts
let inFlightSemList: Promise<SemListResponse> | null = null

const fetchOnce = () => {
  if (!inFlightSemList) {
    inFlightSemList = fetchSemList().catch((err) => {
      inFlightSemList = null  // 에러 시 다음 시도 가능하게
      throw err
    })
  }
  return inFlightSemList
}
```

모듈 스코프 변수는 모든 호출자가 공유하므로, 동시 호출이라도 **둘째 호출자부터는 첫 호출의 promise를 그대로 받습니다.** Nuxt 내부 `_asyncDataPromises`와 동일한 아이디어지만, Nuxt가 promise를 너무 빨리 지우는 문제를 우회합니다.

`inFlightSemList`는 `getCachedData`가 페이로드를 반환할 수 있게 되면 자연스럽게 잊혀집니다(다음 호출은 `useAsyncData`가 아예 fetcher를 부르지 않음). 다만 명시적으로 nullify하지는 않았는데, 그래도 메모리상으로는 promise 객체 하나라 무시할 수준입니다.

### 5.5 정리: 언제 어떤 보호막이 작동하는가

| 시나리오 | `getCachedData` | 모듈 스코프 promise |
| --- | --- | --- |
| 첫 패치 후 다른 페이지로 이동 | ✅ 동작 | (불필요) |
| 형제 컴포넌트가 동시에 마운트 | ❌ 한계 | ✅ 동작 |
| F5 새로고침 | (앱 재시작이라 둘 다 리셋) | (재시작) |

따라서 두 장치를 **함께** 적용하는 것이 안전합니다. 코드 비용도 작습니다.

## 6. 페이지 간 데이터 유지 — Pinia가 필요한가?

### 6.1 결론

**`/api/sem-list` 데이터의 페이지 간 유지에 Pinia는 필요 없습니다.** 현재 `useSemList()` 구현이 이미 SPA 세션 내내 캐시를 유지합니다.

### 6.2 무엇이 어디까지 살아있는가

| 시나리오 | 캐시되는가 | 이유 |
| --- | --- | --- |
| `/` → `/ebeam/cd-sem/r3` → `/r4` → `/hv-sem/r3` | ✅ | 같은 키, 같은 모듈 스코프 promise |
| 사이드바에서 fab 버튼 토글 | ✅ | route param만 변하고, host 컴포넌트는 unmount되지 않음 |
| F5 새로고침 | ❌ 다시 패치 | 앱 재시작 → `payload`/모듈 변수 리셋 |
| 탭 닫고 다시 열기 | ❌ 다시 패치 | 위와 동일 |

mock 데이터에서는 새로고침 시 다시 받아오는 동작이 전혀 문제없고, 오히려 Phase 2/3에서는 *최신 상태 반영*을 위해 **새로고침 시 재패치가 바람직합니다.**

### 6.3 그러면 Pinia는 언제 도입하는가

Pinia가 가치를 갖는 영역은 *서버에서 가져오는 캐시*가 아니라 **클라이언트 측 상태**입니다.

1. 여러 페이지가 읽고 쓰는 UI 상태 — `category`, `toolType`, `fab`, `favorites` 같은 항목. 현재 `stores/navigation.ts`가 `useState` 기반 임시 store로 처리 중입니다.
2. 낙관적 mutation — 즐겨찾기 추가가 화면에 즉시 반영되어야 할 때.
3. DevTools 연동 — 시간 여행 디버깅, 상태 변화 관찰.
4. `pinia-plugin-persistedstate` 같은 플러그인으로 새로고침 후에도 상태 유지 — `favorites`나 fab 선택을 손쉽게 영속화 가능.

당장의 트리거가 될 만한 기능은 *Favorites UI 본격 구현* 정도입니다. 그날이 오면 다음 순서로 마이그레이션하면 됩니다.

1. `@pinia/nuxt` 모듈 추가.
2. `stores/navigation.ts`를 Pinia store로 재작성. API는 가능한 한 동일하게 유지.
3. `pinia-plugin-persistedstate`로 `favorites`, `fab` 영속화.
4. 수동 영속화 플러그인 `plugins/persist-fab.client.ts` 제거.
5. `useNavigation()`을 import하던 7개 파일은 그대로 둬도 동작하도록 wrapper 유지(또는 직접 store import로 변환).

이 마이그레이션은 **API/패칭 코드와 완전히 분리되어 있습니다.** 즉, sem-list 캐싱과는 별개의 작업이며 서로 충돌하지 않습니다.

## 7. 이 세션의 큰 교훈

세부 구현이 다 잊혀져도 다음 한 줄씩만 기억하면 됩니다.

- **타입이 통과해도 죽은 파이프라인일 수 있습니다.** 쓰는 측만 보지 말고 *읽는 측*의 호출자 수를 셉니다.
- **UI 라이브러리의 내부 필터와 직접 만든 필터를 같은 데이터에 동시에 돌리지 않습니다.** 한 곳을 진실 공급원으로 정합니다.
- **문서와 코드는 일치시킵니다.** 희망사항으로 적힌 라이브러리 이름은 미래의 본인과 새로 들어올 동료를 헛걸음하게 만듭니다.
- **`useAsyncData`는 fetch 래퍼가 아니라 캐시 레이어입니다.** 같은 키를 쓰면 서로 다른 컴포넌트 간에도 데이터를 공유합니다.
- **`ssr: false` SPA에서 Nuxt의 기본 dedupe는 부족할 수 있습니다.** `getCachedData` + 모듈 스코프 promise 두 단계 보호가 안전합니다.
- **Pinia는 API 캐시 도구가 아니라 클라이언트 UI 상태 도구입니다.** sem-list 같은 서버 데이터에는 `useAsyncData`가 더 적합합니다.
