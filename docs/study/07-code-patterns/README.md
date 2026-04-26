# 07. 프로젝트 고유 코드 패턴

이 문서는 `front-dev-home`에서 **실제 적용된 아키텍처 결정**과 그 배경을 정리합니다. Phase 1 → Phase 2 → Phase 3 이식을 쉽게 하기 위한 추상화가 핵심입니다.

## 1. 레이어 구조 한눈에

```text
┌─────────────────────────────────────────┐
│  pages/*.vue                            │ ← 라우트, data 요청
│    ↓ uses                               │
├─────────────────────────────────────────┤
│  components/*.vue                       │ ← UI 렌더링
│    ↓ uses                               │
├─────────────────────────────────────────┤
│  composables/useX.ts                    │ ← 비즈니스 로직, fetch 추상화
│    ↓ uses                               │
├─────────────────────────────────────────┤
│  stores/*.ts                            │ ← 전역 상태 (useState 기반)
│    ↓ reads                              │
├─────────────────────────────────────────┤
│  mock-data/*.ts  (Phase 1)              │ ← 데이터 소스
│  Flask API     (Phase 2/3)              │
└─────────────────────────────────────────┘
```

상위 레이어만 교체해도 하위는 영향이 없도록 설계되어 있습니다. 가장 중요한 경계선은 **composable 레이어**입니다.

## 2. Store 패턴 (`stores/navigation.ts`)

Pinia 대신 Nuxt의 `useState`를 활용한 경량 store.

```ts
import { useState } from 'nuxt/app'
import { computed, readonly } from 'vue'

export type Category = 'ebeam' | 'thickness'
export type ToolType = 'cd-sem' | 'hv-sem' | 'verity-sem' | 'provision'
export type Fab = 'all' | 'R3' | 'M11' | 'M12' | 'M14' | 'M15' | 'M16'

export interface NavigationState {
  category: Category
  toolType: ToolType
  fab: Fab
  favorites: string[]
  recent: string[]
}

const defaultState: NavigationState = {
  category: 'ebeam', toolType: 'cd-sem', fab: 'all', favorites: [], recent: []
}

export function useNavigationStore() {
  const state = useState<NavigationState>('navigation', () => ({ ...defaultState }))

  const setCategory = (category: Category) => { state.value.category = category }
  // ... 나머지 setter들

  return {
    state: readonly(state),              // 읽기 전용으로 노출 (직접 수정 방지)
    category: computed(() => state.value.category),
    toolType: computed(() => state.value.toolType),
    // ... computed getter들
    setCategory, setToolType, setFab, addFavorite, removeFavorite, toggleFavorite, addRecent
  }
}
```

### 왜 이 패턴?

1. **`useState<T>('key', factory)`** — SSR 안전. 서버/클라이언트가 같은 state를 공유하며 hydration 문제가 없음.
2. **`readonly(state)`** — 외부에 전체 state를 노출하되 수정은 막음 (action 함수로만 수정).
3. **`computed()`** — 개별 필드를 selector로 노출. 컴포넌트가 필요한 필드만 구독.
4. **Pinia는 아직 도입 안 함** — 현재 규모에선 오버엔지니어링. 스토어가 여러 개 생기고 서로 의존하면 Pinia로 마이그레이션 고려.

### 사용 패턴

```ts
// composables/useNavigation.ts
const store = useNavigationStore()
const router = useRouter()

const navigateToCategory = (category: Category) => {
  store.setCategory(category)           // action 호출
  if (category === 'thickness') {
    router.push('/thickness')
  } else {
    router.push(`/ebeam/${store.toolType.value}`)  // .value로 computed 언랩
  }
}

return { ...store, navigateToCategory }
```

`useNavigation`은 store + router를 묶은 얇은 파사드입니다. 컴포넌트는 이것만 쓰면 됩니다.

## 3. API 추상화 패턴 (`composables/useEbeamToolApi.ts`)

Phase 1 ↔ Phase 2/3 이식성을 위한 핵심 추상화.

```ts
import type { Fab, ToolType } from '~/stores/navigation'
import type { EbeamToolInventoryResponse, EbeamToolRow } from '~/mock-data/...'

const joinApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${normalizedBase}${normalizedPath}`
}

export const summarizeRowsByFab = (rows: EbeamToolRow[]): FabToolSummary[] => {
  // 순수 함수 — 서버/클라이언트 어디서 호출해도 동일
  const summaryMap = new Map<Exclude<Fab, 'all'>, FabToolSummary>()
  for (const row of rows) { ... }
  return Array.from(summaryMap.values())
}

export const useEbeamToolApi = () => {
  const config = useRuntimeConfig()
  const inventoryUrl = joinApiPath(config.public.apiBase, '/ebeam/tools')

  const fetchToolInventory = async (): Promise<EbeamToolInventoryResponse> => {
    return await $fetch<EbeamToolInventoryResponse>(inventoryUrl)
  }

  const filterRows = (inventory, toolType, fab='all'): EbeamToolRow[] => { ... }
  const fetchToolRows = async (toolType, fab='all'): Promise<EbeamToolRow[]> => {
    const inventory = await fetchToolInventory()
    return filterRows(inventory, toolType, fab)
  }
  const fetchFabSummaries = async (toolType): Promise<FabToolSummary[]> => { ... }

  return { fetchToolInventory, fetchToolRows, fetchFabSummaries, filterRows }
}
```

### 설계 포인트

1. **URL 계산은 `useRuntimeConfig().public.apiBase`에서** — Phase 마다 다르지만 코드는 하나.
2. **`$fetch<T>` 제네릭 사용** — 응답 타입을 명시하면 호출 측에서 자동완성 가능.
3. **순수 함수와 fetch 함수 분리** — `summarizeRowsByFab`, `filterRows`는 데이터만 받으면 되므로 단위 테스트가 쉬움.
4. **Composable은 함수 모음을 반환하는 팩토리**. Python에서 module-level 함수를 노출하는 것과 비슷하지만, `useRuntimeConfig()` 같은 Nuxt 컨텍스트를 포착할 수 있어야 하므로 꼭 함수 안에 둡니다.

### Phase 전환 시 바뀌는 부분

- **Phase 1**: `/mock-api/ebeam/tools`로 가는데, 현재 코드에서는 실제로 `$fetch`가 `mockEbeamToolInventoryResponse`를 직접 내려주는 mock middleware 또는 경로 없음 처리가 필요. (⚠ 추후 확장 필요 — 아래 섹션 참고)
- **Phase 2**: `/api/ebeam/tools` → Nitro devProxy → Flask
- **Phase 3**: 동일 경로, 프로덕션 Flask가 처리

### Phase 1에서 mock을 실제로 연결하는 방법 (현재 미구현)

지금 `useEbeamToolApi`는 `$fetch`를 호출하지만, Phase 1에선 `/mock-api/ebeam/tools` 엔드포인트가 없어서 실제로는 요청이 실패할 수 있습니다. 세 가지 해결책:

1. **Nuxt server 라우트를 만들기**

   ```ts
   // server/api/ebeam/tools.ts
   import { mockEbeamToolInventoryResponse } from '~/mock-data/...'
   export default defineEventHandler(() => mockEbeamToolInventoryResponse)
   ```

   `apiBase='/api'`로 맞추면 `/api/ebeam/tools`가 자동으로 mock을 리턴.

2. **Composable 내부에서 분기**

   ```ts
   const USE_MOCK = config.public.apiBase === '/mock-api'
   const fetchToolInventory = async () => {
     if (USE_MOCK) return mockEbeamToolInventoryResponse
     return await $fetch<...>(inventoryUrl)
   }
   ```

3. **`$fetch` 인터셉터 사용** — 전역 플러그인에서 `/mock-api/*` 요청을 가로채 mock 반환.

현재 코드를 보면 1번 또는 2번을 곧 도입해야 하는 상태로 보입니다. 다음 스터디 세션에서 이 부분을 직접 구현해보는 것을 추천합니다.

## 4. Page ↔ Component 역할 분리

### 4.1 Page는 얇게

```vue
<!-- pages/ebeam/cd-sem/index.vue -->
<script setup lang="ts">
const { setToolType, setFab } = useNavigation()

onMounted(() => {
  setToolType('cd-sem')
  setFab('all')
})
</script>

<template>
  <EbeamToolInventoryView
    tool-type="cd-sem"
    title="CD-SEM Overview"
    subtitle="Mocked backend inventory loaded from ..."
  />
</template>
```

- navigation store 동기화 + 재사용 가능한 View 컴포넌트에 props 전달
- 실제 데이터 fetch, 테이블 렌더링은 View 컴포넌트가 담당
- 같은 View를 `hv-sem`, `verity-sem`, `provision` 페이지에서 props만 바꿔 재사용

### 4.2 View Component가 fetch를 수행

```vue
<!-- components/ebeam/ToolInventoryView.vue -->
<script setup lang="ts">
const props = withDefaults(defineProps<{
  fab?: Fab; subtitle: string; title: string; toolType: ToolType
}>(), { fab: 'all' })

const { fetchToolInventory, filterRows } = useEbeamToolApi()

const asyncKey = `ebeam-tool-inventory:${props.toolType}:${props.fab}`
const { data } = await useAsyncData(asyncKey, async () => {
  const inventory = await fetchToolInventory()
  const rows = filterRows(inventory, props.toolType, props.fab)
  const fabSummaries = props.fab === 'all' ? summarizeRowsByFab(rows) : []
  return { rows, fabSummaries }
})

const rows = computed(() => data.value?.rows ?? [])
const fabSummaries = computed(() => data.value?.fabSummaries ?? [])
const onlineCount = computed(() => rows.value.filter(row => row.available === 'On').length)
const offlineCount = computed(() => rows.value.filter(row => row.available === 'Off').length)
const fabCount = computed(() => new Set(rows.value.map(row => row.fab_name)).size)
</script>
```

### 포인트

- **`asyncKey`를 props로부터 생성** — props 조합마다 다른 캐시 키. 다른 `toolType`/`fab` 조합으로 전환하면 새 fetch.
- **하나의 `useAsyncData`로 결과를 묶고, 개별 값은 `computed`로 파생** — 필요한 필드마다 따로 fetch하지 않음. 네트워크 효율.
- **`data.value?.rows ?? []`** — 로딩 중 null 안전 처리 + 기본값.

## 5. 레이아웃 선택 패턴

두 개의 layout이 있습니다.

- `layouts/hub.vue` — 헤더 + footer만. 홈(`pages/index.vue`)이 사용.
- `layouts/default.vue` — 헤더 + 사이드바 + feature tabs. 나머지 모든 페이지 기본.

홈만 다른 layout을 쓰려면 `definePageMeta({ layout: 'hub' })`를 명시.

**확장 아이디어**: 인증이 필요한 페이지에는 `layout: 'authenticated'`, 에러 페이지에는 `layout: 'error'` 같은 식으로 layout을 늘려갈 수 있습니다.

## 6. 네비게이션 일관성 패턴

여러 컴포넌트가 `useNavigation`을 통해 같은 상태를 공유합니다.

```text
AppHeader.vue     → navigateToCategory
FabSidebar.vue    → navigateToFab
ToolTypeTabs.vue  → navigateToToolType
FeatureTabs.vue   → useRoute()로 현재 경로 파악
```

각 컴포넌트가 독립적으로 `useRouter`를 부르지 않고, store를 거쳐서 라우팅 + 상태 업데이트가 한 번에 일어나도록 했습니다. Page `onMounted`에서 store를 동기화하는 것도 이 방향성과 일치.

## 7. 아이콘 / 색상 / 스페이싱의 톤 통일

- 팔레트는 `zinc` 계열만 (중성 무채색)
- accent color는 거의 없음 (모노톤 대시보드 감성)
- icon collection은 `lucide`로 통일 (`i-lucide-*`)
- 카드는 전부 `rounded-2xl` + `.dashboard-surface`

디자인 시스템이 소규모일수록 일관성 유지가 중요합니다. 새 컴포넌트를 만들 때도 이 토큰들을 지키세요.

## 8. 개선 아이디어 (다음 학습 주제)

읽어본 코드 기반으로 정리한 "다음에 해볼 만한" 개선들.

1. **Mock API endpoint 구현** — 위 3.Phase 1 미구현 이슈 해결.
2. **`useNavigation` 타입 좁히기** — `useRoute().params.fab`의 타입이 `string | string[]`이라서 `as Fab` 없이 쓰려면 runtime guard 함수가 필요.
3. **Favorites 영속화** — 현재 `useState`는 새로고침 시 초기화됩니다. localStorage 연동(`@vueuse/core`의 `useLocalStorage`) 또는 Pinia + `pinia-plugin-persistedstate` 도입 시 유지됩니다. 참고: `recent` 파이프라인은 미사용 코드여서 제거되었습니다(2026-04-26 세션).
4. **Error boundary** — `useAsyncData`의 `error`를 받아 UI로 표시. 현재 코드엔 없음.
5. **Loading skeleton** — `pending` 값을 써서 스켈레톤 UI 표시.
6. **Pinia 도입 검토** — store가 3개 이상으로 늘어나면 검토합니다. Pinia는 DevTools 통합, plugin 생태계 면에서 우수합니다.
7. **단위 테스트 기반 마련** — Vitest + Vue Test Utils로 `summarizeRowsByFab`, `filterRows` 같은 pure function부터 시작합니다.

## 9. 요약

| 패턴 | 어디서 | 핵심 |
| --- | --- | --- |
| `useState` 기반 store | `stores/navigation.ts` | SSR-safe 전역 상태 + readonly 노출 |
| URL 계산 추상화 | `useSemListApi.ts`, `useStorageApi.ts`, `useDeviceStatisticsApi.ts` | `apiBase + path` 조합 |
| 순수 헬퍼 함수 | `extractFabNames`, `filterRows`, `classifyToolType` | 테스트 쉬움, 재사용 |
| View 컴포넌트 + Page 분리 | `ToolInventoryView.vue` + `pages/ebeam/*` | Page는 얇게, View는 재사용 |
| Layout 선택 | `definePageMeta({layout})` | 페이지 단위 shell 전환 |
| 단일 키 `useAsyncData` 통합 | `useSemList()` 컴포저블 | 모든 소비자가 같은 키를 공유해 SPA 세션 내내 캐시 |
| 모듈 스코프 in-flight promise | `useSemListApi.ts`의 `inFlightSemList` | Suspense 경계를 가로지르는 동시 요청 dedupe 보강 |
| `computed`로 파생 값 | 어디서나 | 반응형 + 캐시 |

## 10. 심화 주제 — 별도 문서

이 챕터에서 다 담기 어려운 주제는 별도 파일로 분리되어 있습니다.

- [`sem-list-caching.md`](./sem-list-caching.md) — `useSemList()` 통합, Nuxt `useAsyncData` 중복 제거의 함정, TanStack Query 미도입 결정, 페이지 간 캐시 유지와 Pinia 도입 시점 (2026-04-26 세션 요약).
