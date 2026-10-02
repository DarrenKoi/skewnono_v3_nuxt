# 03. Nuxt 4 핵심 개념


CSR(Client-Side Rendering)은 브라우저 렌더링, SSR(Server-Side Rendering)은 서버 렌더링, SSG(Static Site Generation)는 빌드 시 정적 파일 생성, SPA(Single Page Application)는 브라우저 라우터로 이동하는 앱입니다. TTL(Time To Live)은 캐시의 시간 기반 유효 수명이며 현재 helper에 자동으로 존재하지 않습니다.

## 1. 기초: Vue에 프로젝트 규칙을 더합니다

Vue는 상태와 화면을 연결합니다. Nuxt는 그 위에서 페이지 파일을 URL로 연결하고, 컴포넌트와 함수를 자동 등록하며, 개발 서버와 빌드 도구를 묶습니다. Flask의 라우트 데코레이터처럼 URL 규칙이 필요하지만, Nuxt에서는 `pages/`의 파일 경로가 그 규칙입니다.

**확인 기준은 2026-10-03입니다.** [package.json](../../../frontend/package.json)의 `nuxt: ^4.4.2`는 설치 허용 범위입니다. [package-lock.json](../../../frontend/package-lock.json)은 **4.5.0**을 고정하며, 원본 작업 공간의 `frontend/node_modules/nuxt/package.json`도 4.5.0입니다. `^4.4.2`를 현재 설치 버전이라고 읽으면 안 됩니다. 온라인 4.x 문서는 이후 버전 기능도 포함하므로 [4.5.0 소스](https://github.com/nuxt/nuxt/blob/v4.5.0/packages/nuxt/src/app/composables/asyncData.ts)와 대조합니다.

학습 목표는 다음 세 질문에 답하는 것입니다.

1. 화면을 여는 파일은 어디에 있습니까?
2. API 응답과 화면의 임시 상태는 각각 누가 보관합니까?
3. 개발 서버에서 되는 기능이 정적 배포에서도 동작합니까?

## 2. 용어: 렌더링과 실행 위치

| 용어 | 뜻 | 이 프로젝트 |
| --- | --- | --- |
| CSR | 브라우저 JavaScript가 화면을 만듭니다. | `ssr: false`인 SPA입니다. |
| SSR | 요청마다 서버가 화면 HTML을 렌더링합니다. | 현재 사용하지 않습니다. |
| SSG / generate | 빌드 시 정적 배포 파일을 만듭니다. | `npm run build`가 `nuxt generate`입니다. |
| SPA | 페이지 이동을 브라우저 라우터가 처리합니다. | 회사 배포에서 Flask가 정적 결과를 제공합니다. |
| Nitro | Nuxt의 서버 엔진입니다. | 개발 프록시에 사용하며 배포 API 서버는 Flask입니다. |
| payload | Nuxt가 비동기 결과와 상태를 담는 데이터입니다. | 클라이언트에서도 데이터 공유에 사용됩니다. |
| composable | Vue/Nuxt 기능을 묶는 함수입니다. | `useSemList()` 같은 함수입니다. |

SSG라는 명령을 사용한다고 API 데이터까지 서버 HTML로 미리 렌더링하는 것은 아닙니다. 이 저장소는 CSR 앱의 정적 파일을 생성합니다. 최초 HTML만 읽는 검색 로봇에 완성된 데이터 화면이 전달된다고 가정하면 안 됩니다.

## 3. 실제 구현: 파일 → 화면 → API

### 3.1 디렉토리와 라우트

```text
frontend/
  app/app.vue          UApp → NuxtLayout → NuxtPage
  app/pages/           URL을 만드는 페이지 파일
  app/layouts/         공통 화면 틀, slot에 페이지를 넣습니다.
  app/components/      재사용 화면 조각
  app/composables/      API / 반응형 로직
  app/stores/          프로젝트 규칙: useState 기반 공유 상태
  app/utils/           순수 계산과 경계 처리
  app/plugins/         클라이언트 초기화 / 페이지 활동 기록
  app/assets/          빌드하는 CSS 등의 자원
  public/              그대로 배포하는 폰트 / 아이콘
  .nuxt/               생성된 타입과 내부 파일
  .output/public/      generate의 정적 배포 결과
  nuxt.config.ts       개발 / 빌드 설정
```

`stores/`, `utils/`의 의미를 Nuxt의 마법과 프로젝트 규칙으로 구분합니다. `stores/`라는 이름이 Pinia 사용을 뜻하지 않습니다. 예전 프런트 `mock-data/`와 `useEbeamToolApi.ts`는 현재 존재하지 않습니다. Mock도 Flask의 provider에서 응답합니다. `plugins/`에는 [persist-fab.client.ts](../../../frontend/app/plugins/persist-fab.client.ts)와 [pageView.client.ts](../../../frontend/app/plugins/pageView.client.ts)가 존재합니다.

| 실제 페이지 파일 | URL |
| --- | --- |
| [index.vue](../../../frontend/app/pages/index.vue) | `/` |
| [settings.vue](../../../frontend/app/pages/settings.vue) | `/settings` |
| [CD-SEM 허브](../../../frontend/app/pages/ebeam/cd-sem/index.vue) | `/ebeam/cd-sem` |
| [FAB 장비 목록](../../../frontend/app/pages/ebeam/cd-sem/[fab]/index.vue) | `/ebeam/cd-sem/:fab` |
| [FAB 하드웨어](../../../frontend/app/pages/ebeam/cd-sem/[fab]/hardware.vue) | `/ebeam/cd-sem/:fab/hardware` |

`[fab]`는 경로 인자를 뜻합니다. `/ebeam/cd-sem/R3/hardware`에서 `useRoute().params.fab`는 `R3`입니다. 파일이 있다는 사실과 인자가 유효하다는 사실은 별개입니다. URL 입력은 정규화와 유효성 처리가 필요합니다. 예전 `monitor.vue`를 실제 파일 예시로 사용하지 않습니다.

`definePageMeta({ layout: 'hub' })`는 허브 레이아웃을 지정합니다. 기본 레이아웃은 `default.vue`입니다. [app.vue](../../../frontend/app/app.vue)는 접근 제한 여부도 판단하므로, 실제로 모든 요청이 무조건 레이아웃으로 들어가는 것은 아닙니다.

### 3.2 자동 등록과 Nuxt 컨텍스트

`components/nav/AppHeader.vue`는 `<NavAppHeader />`, `components/ebeam/ToolInventoryView.vue`는 `<EbeamToolInventoryView />`로 자동 등록됩니다. Vue의 `ref`, `computed`, `watch`, Nuxt의 `useState`, `useRoute`, `useAsyncData` 등은 Nuxt가 처리하는 코드에서 자동 import할 수 있습니다.

그러나 `useRuntimeConfig()`와 `useState()`는 앱 컨텍스트가 필요한 함수입니다. 아무 모듈의 최상위나 Node 테스트에서 마음대로 호출하는 함수가 아닙니다. 자동 import 변환도 일반 `node --test`에는 없습니다. 그래서 순수 함수 테스트는 명시적인 상대 import를 사용합니다. Composable 하위 폴더까지 모두 자동 검색된다고 가정하지 말고 [자동 import 규칙](https://nuxt.com/docs/4.x/guide/concepts/auto-imports)을 확인합니다.

```ts
// 페이지 / 컴포넌트 setup에서 사용하는 학습 예시입니다.
const route = useRoute()
const router = useRouter()
const fab = computed(() => String(route.params.fab ?? ''))
const goToSettings = () => router.push('/settings')
```

`router.push`는 이력을 추가하고, `replace`는 현재 이력을 바꾸며, `back`은 뒤로 갑니다. `<NuxtLink>`는 내부 이동에 사용합니다. `route.query`는 사용자 입력이며 문자열, 배열, null 등의 가능성을 고려해야 합니다.

### 3.3 `$fetch`, `useAsyncData`, `useFetch`

| API | 책임 | 주의점 |
| --- | --- | --- |
| `$fetch<T>(url)` | HTTP 요청과 응답 파싱 | 타입 매개변수는 JSON 검증기가 아닙니다. |
| `useAsyncData(key, handler)` | 결과 / 오류 / 로딩 상태의 공유와 실행 관리 | 키와 옵션, 캐시 정책이 필요합니다. |
| `useFetch(url)` | `$fetch`를 `useAsyncData`와 연결 | TTL을 자동 제공하지 않습니다. |

현재 [useSemListApi.ts](../../../frontend/app/composables/useSemListApi.ts)는 `$fetch<SemListResponse>`로 `/api/sem-list`를 요청합니다. 같은 파일의 `useSemList()`는 키 `'sem-list'`를 사용합니다. 페이지, 사이드바, 목록이 같은 원본 데이터를 공유한 뒤 `computed`로 필요한 목록을 계산합니다.

```ts
// 현재 저장소에서 바로 읽을 수 있는 사용 패턴입니다.
const { data: rows, status, error } = await useSemList()
const total = computed(() => rows.value.length)
```

`data`, `error`, `status`, `pending`은 ref입니다. `refresh`, `execute`, `clear`는 함수입니다. `status`는 `idle`, `pending`, `success`, `error`를 구분합니다. `useSemList()`는 `default: () => []`를 지정하므로 초기 목록은 빈 배열입니다. 빈 배열만 보고 “조회 완료인데 결과 없음”이라고 단정하지 말고 상태도 확인합니다. 일반 `useAsyncData`는 기본값을 지정하지 않으면 `undefined` 가능성이 있습니다.

같은 키는 같은 자원 / 같은 상태를 뜻합니다. 서로 다른 FAB의 서로 다른 서버 결과를 같은 `'rows'` 키에 넣으면 충돌합니다. 반대로 SEM 전체 목록을 한 번 받아 클라이언트에서 FAB로 필터링한다면 FAB별 키를 만드는 것이 불필요할 수 있습니다. 동적 서버 조회에서는 응답을 결정하는 인자를 키에 포함하거나 `watch`를 명시합니다.

### 3.4 `deep: false`와 캐시의 실제 한계

Nuxt 4의 기본 `deep`은 **false**입니다. 설치된 4.5.0도 옵션에 따라 `shallowRef`를 사용합니다. 응답을 읽기 전용 원본으로 다루고 `.value` 전체 교체로 갱신하는 패턴에 적합합니다. `data.value[0].available = 'Off'`처럼 중첩 필드만 바꾸면 그 변경을 Vue가 추적하지 않을 수 있습니다. 수정 가능한 폼 데이터가 필요하면 원본과 별도 로컬 상태로 분리하는 이유입니다.

공유 키에서 handler, `deep`, `default`, `transform`, `pick`, `getCachedData`를 일관되게 유지합니다. API composable 한곳으로 모으는 것은 이 계약을 유지하기 위한 선택입니다. [공식 useAsyncData 설명](https://nuxt.com/docs/4.x/api/composables/use-async-data)은 기본값과 공유 옵션을 설명하지만, 뒤 버전의 추가 옵션을 그대로 복사하지 않습니다.

이 저장소의 캐시는 [asyncDataCache.ts](../../../frontend/app/utils/asyncDataCache.ts)에 있습니다.

```text
useSemList()
  → useAsyncData('sem-list', fetchOnce, getCachedData: payloadCache)
      → 기존 payload/static 값이 있으면 재사용
      → 없으면 createInFlightSlot의 Promise를 사용
          → $fetch('/api/sem-list')
              → Flask mock 또는 office provider
```

- `payloadCache`는 `payload.data[key] ?? static.data[key]`를 반환합니다. 시간 검사를 하지 않습니다.
- `payloadCacheOnInitial`은 첫 실행에만 캐시를 주고, 수동 refresh 등에는 `undefined`를 반환합니다.
- `createInFlightSlot`은 진행 중 요청뿐 아니라 **성공한 Promise도 `reset()` 전까지 유지**합니다. 실패하면 비워 재시도할 수 있게 합니다. 이름만 보고 완료 직후 사라진다고 읽으면 안 됩니다.
- Nuxt 4.5.0의 캐시 조회는 refresh 때도 적용될 수 있습니다. `payloadCache`를 붙인 곳에서 `refresh()`가 반드시 새 HTTP 요청을 보장한다고 말할 수 없습니다. 슬롯을 유지하는 곳은 슬롯 reset 정책도 봅니다.
- 이것들은 TTL, `staleTime`, 창 포커스 재조회, 브라우저 새로고침 후 영속 캐시가 아닙니다. Nuxt의 기본 캐시 수명도 앱 사용 여부와 옵션의 영향을 받으므로 “영원히 재사용”이라고 가르치지 않습니다.

### 3.5 공유 상태와 영속 상태

[stores/navigation.ts](../../../frontend/app/stores/navigation.ts)는 `useState<NavigationState>('navigation', ...)`로 상태를 공유하고, setter에서 FAB 정규화와 중복 제거를 수행합니다. 단순 `ref`는 컴포넌트마다 새로 만들어질 수 있지만 같은 키의 `useState`는 Nuxt 앱에서 공유합니다. SSR 안전성은 Nuxt의 일반 장점이며, 이 SPA에서 당장 쓰는 이유는 앱 안의 공유입니다.

`useState`는 새로고침 후 저장을 보장하지 않습니다. 그런 상태는 [usePersistedState.ts](../../../frontend/app/composables/usePersistedState.ts)를 사용합니다. `unknown` JSON을 `normalize`로 확인하고, 앱 수명의 detached effect scope에서 `flush: 'sync'` watcher를 한 번 붙입니다. 현재 watcher는 기본적으로 얕으므로 배열 `push` 등 중첩 변경보다 새 배열 대입 방식에 주의합니다. 저장이 차단되면 읽기/쓰기 예외를 처리하지만 저장 성공을 보장하지는 않습니다. Pinia를 별도로 도입하지 않습니다.

### 3.6 개발 프록시와 배포 설정

[nuxt.config.ts](../../../frontend/nuxt.config.ts)의 기본값은 API base `/api`, 개발 대상 `http://localhost:5050`입니다. 개발 시 Nitro가 `/api`를 Flask로 프록시합니다. 세 단계 모두 프런트가 Flask를 호출하며, 집에서는 Flask mock provider가 답합니다.

```text
개발: 브라우저 :3000 /api/* → Nitro devProxy → Flask :5050 /api/*
배포: 브라우저 → Flask의 정적 SPA + Flask /api/*
```

`NUXT_API_TARGET`은 개발 프록시 대상이고 `NUXT_PUBLIC_API_BASE`는 브라우저 코드에 공개되는 API base입니다. `public` 설정에 비밀키를 넣으면 안 됩니다. **정적 배포에는 실행 중인 Nitro가 없으므로 배포 후 환경 변수만 바꿔 이미 생성된 JavaScript를 다시 설정할 수 없습니다.** base를 바꾸려면 빌드 입력과 재생성을 고려합니다. provider 전환은 백엔드의 별도 설정입니다.

`server/api/*.ts`는 Nuxt 일반 기능이지만 현재 `frontend/server/`는 없습니다. 정적 generate 결과에 새로운 서버 API가 실행되는 것도 아닙니다. 이 앱의 서버 기능은 Flask feature 폴더에 만듭니다.

`useHead` / `useSeoMeta`는 제목과 메타데이터를 관리합니다. 이 SPA에서는 브라우저에서 갱신되는 부분과 빌드 때 들어간 초기 메타데이터를 구분합니다. SSR에서의 SEO 이점을 현재 구성의 이점으로 옮겨 쓰지 않습니다.

## 4. 선택 이유와 한계

Nuxt는 파일 규칙과 자동 생성 타입을 제공해 반복 작업을 줄입니다. API composable과 `useState`만으로 현재 공유 요구를 처리하므로 새로운 query/store 라이브러리를 추가하지 않습니다. TTL이나 포커스 재조회가 실제 요구가 되면 그때 정책을 설계합니다. 파일 규칙은 숨은 계약이므로 파일 이동, 키 변경, 실행 위치 변경을 단순 정리로 취급하면 안 됩니다.

## 5. 흔한 실수

1. package 선언 하한을 실제 설치 버전으로 적습니다. lock과 설치된 package를 확인합니다.
2. `useAsyncData`를 영속 저장이나 TTL 캐시로 이해합니다. 현재 helper의 반환값과 reset 정책을 봅니다.
3. API 결과의 중첩 필드를 바꾸고 화면 갱신을 기대합니다. Nuxt 4 기본 shallow data임을 확인합니다.
4. 정적 배포에서 Nitro 서버 API와 runtime 환경 변수 변경을 기대합니다. 실제 실행 서버는 Flask입니다.
5. `.nuxt/` 생성 파일을 직접 고칩니다. `nuxt.config.ts`의 입력 설정을 고칩니다.
6. Nuxt 컨텍스트 함수를 일반 Node 테스트에서 호출합니다. 순수 로직을 명시적으로 import해서 검사합니다.

## 6. 안전 실습과 완료 기준

서비스를 띄우거나 의존성을 설치하지 않고도 다음을 확인할 수 있습니다. 저장소 루트에서 실행합니다.

```bash
cat frontend/package.json
cat frontend/tsconfig.json
rg --files frontend/app/pages frontend/app/plugins
rg -n 'ssr:|devProxy|runtimeConfig|apiBase' frontend/nuxt.config.ts
rg -n 'getCachedData|reset|inFlight' frontend/app/utils/asyncDataCache.ts
```

읽기 실습의 답은 `ssr: false`, 정적 generate, `/api` base, Flask 개발 프록시, 초기 전용 캐시와 일반 캐시의 차이입니다. `createInFlightSlot`의 성공 경로에서 `inFlight = null`이 실행되지 않는 것도 찾아야 합니다.

설치가 완료된 개인 학습 환경에서는 `frontend/`에서 다음 검사만 실행합니다. `postinstall`은 타입 생성에 필요한 경우에만 사용하며 `.nuxt/`를 생성합니다.

```bash
npm run typecheck
npm test
```

이 검사는 타입과 순수 함수를 확인합니다. 페이지 렌더링, 라우터 이동, 실제 서버 응답, office DB 정합성까지 검증하지 않습니다. 앱 수동 확인은 별도의 브라우저 단계입니다.

## 7. 공식 근거와 다음 문서

- [Nuxt 4 디렉토리 구조](https://nuxt.com/docs/4.x/directory-structure/app)
- [Nuxt 4 데이터 fetching](https://nuxt.com/docs/4.x/getting-started/data-fetching)
- [Runtime config와 정적 배포 한계](https://nuxt.com/docs/4.x/guide/going-further/runtime-config)
- [Nuxt 4.5.0 asyncData 구현](https://github.com/nuxt/nuxt/blob/v4.5.0/packages/nuxt/src/app/composables/asyncData.ts)
- [다음: Nuxt UI](../04-nuxt-ui/README.md)
