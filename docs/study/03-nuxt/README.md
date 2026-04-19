# 03. Nuxt 4 핵심 개념

Nuxt는 Vue 위에 얹은 메타 프레임워크입니다. 백엔드 관점에서 Nuxt가 해주는 일은 대략 이렇습니다.

- 파일 구조 → URL 라우팅 (Flask Blueprint의 데코레이터 대신 파일 경로가 규칙)
- SSR/SSG/CSR 렌더링 선택 지원
- 자동 코드 분할 + 번들링 (Vite 사용)
- auto-import로 `import` 줄이기
- 서버 API 라우트 빌트인 (`server/` 폴더)
- 타입 자동 생성 (`.nuxt/tsconfig.*.json`)

이 프로젝트의 `package.json`에는 `"nuxt": "^4.4.2"`로 명시되어 있어 Nuxt 4 계열입니다. Nuxt 3와 개념은 대부분 동일하고, 기본 디렉토리만 `app/` 아래로 옮긴 변화가 큽니다.

## 1. 디렉토리 규칙 (Nuxt 4 기준)

```text
app/
├── app.vue              최상위 진입점 (<NuxtLayout><NuxtPage/></NuxtLayout>)
├── app.config.ts        런타임 앱 설정 (테마, 기능 플래그 등)
├── assets/              번들에 포함될 자원 (CSS, 이미지)
├── components/          자동 등록되는 Vue 컴포넌트
├── composables/         자동 import되는 컴포저블 함수 (use*)
├── layouts/             페이지 레이아웃 (default, hub ...)
├── mock-data/           (프로젝트 자체 폴더, Nuxt 규칙 X)
├── pages/               파일 기반 라우팅
├── stores/              (프로젝트 자체 폴더 — Pinia 대신 useState 기반)
└── plugins/             전역 플러그인 (이 프로젝트엔 없음)

public/                  정적 파일 그대로 서빙 (/favicon.ico 등)
server/                  서버 라우트 (/api/*)
.nuxt/                   자동 생성 (건드리지 말 것)
.output/                 빌드 결과
nuxt.config.ts           Nuxt 설정
```

## 2. 파일 기반 라우팅 (`pages/`)

경로 규칙 요약:

| 파일 경로 | 매칭 URL |
| --- | --- |
| `pages/index.vue` | `/` |
| `pages/settings.vue` | `/settings` |
| `pages/ebeam/cd-sem/index.vue` | `/ebeam/cd-sem` |
| `pages/ebeam/cd-sem/[fab]/index.vue` | `/ebeam/cd-sem/:fab` |
| `pages/ebeam/cd-sem/[fab]/monitor.vue` | `/ebeam/cd-sem/:fab/monitor` |
| `pages/[...all].vue` | catch-all |

### 2.1 동적 세그먼트 `[param]`

프로젝트에 `pages/ebeam/cd-sem/[fab]/monitor.vue`가 있습니다. URL `/ebeam/cd-sem/m14/monitor`에 매칭되고, 페이지 안에서 다음처럼 읽습니다.

```ts
const route = useRoute()
console.log(route.params.fab)  // 'm14'
```

### 2.2 `definePageMeta`

페이지별 메타데이터(layout, middleware 등)를 선언합니다.

```ts
// pages/index.vue
definePageMeta({
  layout: 'hub'   // app/layouts/hub.vue 사용
})
```

`layout`을 선언하지 않으면 `default.vue`가 기본으로 적용됩니다.

## 3. 컴포넌트 자동 등록

`components/` 아래의 `.vue` 파일은 import 없이 바로 템플릿에서 쓸 수 있습니다.

```text
components/AppLogo.vue             → <AppLogo />
components/nav/AppHeader.vue       → <NavAppHeader />
components/ebeam/ToolInventoryView.vue → <EbeamToolInventoryView />
```

폴더 경로가 프리픽스로 붙는 것에 주의. `nuxt.config.ts`의 `components: { pathPrefix: false }`로 끌 수도 있습니다.

## 4. Composables 자동 등록

`composables/` 아래의 `use*` 함수는 모든 `.vue`/`.ts` 파일에서 import 없이 사용 가능합니다.

프로젝트 예시:

```text
composables/useNavigation.ts       → 아무 곳에서 useNavigation()
composables/useEbeamToolApi.ts     → 아무 곳에서 useEbeamToolApi()
composables/useToolData.ts         → 아무 곳에서 useToolData()
```

추가로 Vue/Nuxt가 제공하는 것들도 자동 import됩니다.

- `ref`, `computed`, `watch`, `onMounted` (Vue)
- `useState`, `useRoute`, `useRouter`, `useRuntimeConfig` (Nuxt)
- `useAsyncData`, `useFetch`, `$fetch` (Nuxt)
- `useHead`, `useSeoMeta` (Nuxt)
- `navigateTo`, `defineNuxtPlugin`, `definePageMeta` (Nuxt)

IDE에서 자동 완성이 안 뜨면 한 번 `npm run dev`를 돌려서 `.nuxt/`의 타입을 생성하세요.

## 5. 데이터 가져오기: `useAsyncData` / `useFetch` / `$fetch`

셋의 차이를 확실히 해두세요.

### 5.1 `$fetch<T>(url)` — 저수준

ofetch 기반. fetch API를 감싼 단순 HTTP 호출입니다. 컴포넌트 내부가 아니라도 어디서든 쓸 수 있습니다.

```ts
// composables/useEbeamToolApi.ts
const fetchToolInventory = async (): Promise<EbeamToolInventoryResponse> => {
  return await $fetch<EbeamToolInventoryResponse>(inventoryUrl)
}
```

### 5.2 `useAsyncData(key, fn)` — 비동기 결과 + SSR 캐시

`key`로 결과를 서버/클라이언트 간에 공유합니다. SSR 시 서버에서 실행한 결과가 클라이언트로 직렬화되어 재실행을 피합니다.

```ts
// pages/index.vue
const { fetchToolInventory } = useEbeamToolApi()

const { data: inventory } = await useAsyncData(
  'ebeam-base-tool-inventory',   // key (유일해야 함)
  () => fetchToolInventory()
)
// inventory는 Ref<EbeamToolInventoryResponse | null>
inventory.value?.['cd-sem']  // 첫 렌더 후 값이 들어옴
```

반환 객체:
- `data`: 결과
- `pending`: 로딩 여부
- `error`: 에러
- `refresh()`: 재요청
- `status`: 'idle' | 'pending' | 'success' | 'error'

### 5.3 `useFetch(url)` — 둘의 합성

`useAsyncData + $fetch`. URL만 주면 알아서 fetch + 캐시.

```ts
const { data, pending, error } = await useFetch<ApiShape>('/api/tools')
```

이 프로젝트는 추상화(`useEbeamToolApi`)를 한 번 거쳐서 `useAsyncData + $fetch` 조합을 쓰고 있습니다. Phase 2에서 `$fetch`가 real Flask endpoint를 가리키게 할 때 페이지 코드를 건드릴 필요가 없어지는 구조입니다.

### 5.4 `watch`와 함께 동적 재요청

`useAsyncData`는 기본적으로 `key`가 바뀌면 재실행됩니다. `watch` 옵션으로 특정 ref 의존성을 걸 수도 있습니다.

```ts
const { data } = await useAsyncData(
  'rows',
  () => fetchRows(fab.value),
  { watch: [fab] }
)
```

## 6. 상태 공유: `useState`

Nuxt의 SSR 안전 `ref`입니다. 컴포넌트 트리 어디서든 같은 key로 호출하면 같은 상태를 공유합니다.

```ts
// stores/navigation.ts
const state = useState<NavigationState>('navigation', () => ({ ...defaultState }))
```

**왜 평범한 `ref`가 아니라 `useState`인가?** SSR에서 서버와 클라이언트의 상태를 맞춰야 하기 때문입니다. 전역 모듈 레벨 `ref`는 서버 여러 요청 간에 공유되어 버그를 일으킵니다.

이 프로젝트는 Pinia 대신 `useState`로 네비게이션 상태를 관리합니다. Phase 2에서 상태가 복잡해지면 Pinia 도입을 검토해도 됩니다.

## 7. 라우팅 API

```ts
// composables/useNavigation.ts
const router = useRouter()
router.push('/ebeam/cd-sem')
router.replace('/settings')
router.back()

// useRoute — 현재 라우트 정보
const route = useRoute()
route.params.fab     // 동적 세그먼트
route.query.q        // ?q=foo
route.path           // '/ebeam/cd-sem/m14'
route.name           // 자동 생성된 라우트 이름
```

`<NuxtLink to="/ebeam/cd-sem">`는 SPA 네비게이션을 수행합니다(풀 페이지 리로드 없음).

## 8. 레이아웃 (`layouts/`)

```text
layouts/default.vue    — 기본 레이아웃
layouts/hub.vue        — 허브(루트) 페이지 전용
```

사용법:

```ts
// pages/index.vue
definePageMeta({ layout: 'hub' })
```

레이아웃 파일에는 `<slot />`이 있어서 페이지 내용이 그 자리에 들어갑니다. `app.vue`의 `<NuxtLayout>` → `<NuxtPage />`가 이 구조의 바깥 쌀집입니다.

## 9. Runtime Config

서버/클라이언트에서 접근 가능한 설정 주입. 환경 변수로 오버라이드 가능합니다.

```ts
// nuxt.config.ts
runtimeConfig: {
  public: {
    apiBase   // 모든 곳에서 접근 가능
  }
  // public 밖에 두면 서버 전용
}

// 사용
const config = useRuntimeConfig()
const base = config.public.apiBase   // '/mock-api' 또는 '/api'
```

환경 변수:

```bash
NUXT_PUBLIC_API_BASE=/api npm run dev
# runtimeConfig.public.apiBase가 '/api'로 덮여씀
```

이 프로젝트가 Phase 1 → Phase 2 스위치를 config 변경만으로 달성하는 핵심 장치입니다.

## 10. SEO / head 메타 (`useHead`, `useSeoMeta`)

```ts
// app.vue
useHead({
  meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
  link: [{ rel: 'icon', href: '/favicon.ico' }],
  htmlAttrs: { lang: 'en' }
})

useSeoMeta({
  title,
  description,
  ogTitle: title,
  ogDescription: description
})
```

SSR 시 HTML에 그대로 박혀서 SEO에 유리합니다.

## 11. 서버 라우트 (`server/api/*.ts`)

이 프로젝트에는 `server/` 폴더만 있고 내용이 비어있지만, 필요 시 아래처럼 Flask 없이도 Nuxt가 서버를 띄울 수 있습니다.

```ts
// server/api/hello.ts
export default defineEventHandler(() => {
  return { message: 'hello' }
})
// → GET /api/hello
```

Phase 2/3에서는 Flask를 쓰기 때문에 거의 안 쓸 것이지만, 알아두면 간단한 mock endpoint 테스트에 유용합니다.

## 12. 개발 명령어

```bash
npm run dev           # 개발 서버 (http://localhost:3100)
npm run dev:remote    # 0.0.0.0 바인딩 (원격 접속)
npm run build         # 프로덕션 빌드 (.output/)
npm run preview       # 빌드 결과 로컬 실행
npm run lint          # ESLint
npm run typecheck     # vue-tsc 타입 체크
npm run postinstall   # nuxt prepare (타입 재생성, 자동 실행)
```

## 13. 프로젝트에서의 Nuxt 사용 정리

| 파일 | 쓰인 Nuxt 기능 |
| --- | --- |
| `app.vue` | `useHead`, `useSeoMeta`, `<NuxtLayout><NuxtPage/>` |
| `pages/index.vue` | `definePageMeta({layout})`, `useAsyncData`, `useState` |
| `pages/ebeam/cd-sem/[fab]/monitor.vue` | 동적 세그먼트 |
| `composables/useNavigation.ts` | `useRouter` |
| `composables/useEbeamToolApi.ts` | `useRuntimeConfig`, `$fetch<T>` |
| `stores/navigation.ts` | `useState`, `readonly`, `computed` |
| `layouts/default.vue`, `layouts/hub.vue` | `<slot />`, 레이아웃 구조 |

## 더 읽을거리

- Nuxt 4 공식 문서: https://nuxt.com/docs
- Nuxt 데이터 fetching 가이드: https://nuxt.com/docs/4.x/getting-started/data-fetching
- `useAsyncData` vs `useFetch` 설명: https://nuxt.com/docs/4.x/getting-started/data-fetching#useasyncdata
- 공식 예제 모음: https://nuxt.com/docs/examples
