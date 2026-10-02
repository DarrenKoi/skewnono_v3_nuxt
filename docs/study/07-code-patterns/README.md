# 07. 프로젝트 고유 코드 패턴

2026-10-03의 실제 코드 기준입니다. 컴포저블은 화면에서 함께 쓰는 동작을 함수로 묶은 것이고, store는 페이지를 넘어서 공유하는 상태의 진입점입니다. 이 저장소는 Pinia나 Vue Query를 사용하지 않고 Nuxt와 Vue 내장 기능으로 현재 요구를 처리합니다.

## 1. 기초: 서버 데이터와 화면 상태를 구분합니다

장비 목록은 서버가 관리하는 데이터입니다. 선택한 팹과 비교할 장비는 사용자가 만든 화면 상태입니다. 둘을 같은 보관소에 넣어야 하는 것은 아닙니다.

```text
페이지 / 컴포넌트
  ├─ API composable → $fetch('/api/...') → Flask → data.py → provider
  ├─ useAsyncData → 요청 결과와 상태 공유
  ├─ useState store → 현재 SPA의 화면 상태 공유
  └─ usePersistedState → useState + localStorage 복원/저장
```

모든 단계에서 Flask를 호출합니다. 프론트의 `mock-data`로 집 데이터를 읽는 옛 구조와 `useEbeamToolApi` 예제는 현재 구조가 아닙니다. provider만 바꾸는 백엔드 경계는 [10장](../10-backend-providers/README.md)에 있습니다.

## 2. 용어

| 용어 | 쉬운 뜻 | 수명/주의점 |
| --- | --- | --- |
| `ref` | 바뀌면 화면도 반응하는 값 | script에서는 `.value` |
| `computed` | 다른 값에서 계산한 결과 | 원본을 다시 보관하는 저장소가 아님 |
| composable | Vue/Nuxt 상태와 동작을 묶는 함수 | `useXxx` 이름을 사용 |
| store | 공유 상태와 변경 함수 묶음 | 이 앱에서는 `useState` 기반 |
| 캐시 | 이미 얻은 결과 재사용 | 최신값이라는 보장은 별도 |
| dedupe | 겹친 요청 처리 방식 | 캐시·영속화와 다름 |
| normalize | 외부 값 구조를 검증/정리 | 서버에 아직 존재하는지까지 보장하지 않음 |

lock과 확인한 설치본은 Nuxt 4.5.0, Vue 3.5.40입니다. Nuxt 직접 선언은 `^4.4.2`, Vue는 간접 의존성입니다. 선언·lock·설치의 구분은 [06장](../06-vite-config/README.md)에 있습니다.

## 3. 실제 구현

### 3.1 navigation store

[stores/navigation.ts](../../../frontend/app/stores/navigation.ts)의 현재 필드는 `toolType`, `fabs`, `favorites`, `selectedToolId`입니다. 예전 `category`, `recent` 필드는 없습니다. `Fab`은 서버의 `fab_name`을 담는 `string`이며 고정된 팹 문자열 union이 아닙니다.

`useState('navigation', factory)`가 상태를 공유하고 `readonly(state)`가 직접 수정을 제한합니다. 필드별 `computed`와 `setToolType`, `setFabs`, `setSelectedTool` 등의 액션을 반환합니다. `setFabs`는 `canonicalFabList`를 이용해 대문자 정규화·중복 제거·순서 유지·sentinel 제거를 한 곳에서 처리합니다. `fab` 접근자는 `fabs[0]` 또는 선택 없음 값 `all`을 반환하는 단일 선택 호환 경로입니다.

[useNavigation.ts](../../../frontend/app/composables/useNavigation.ts)는 store와 router를 묶습니다. 지원하는 기능을 유지하며 장비군을 전환하고, 같은 기능이면 query를 유지하며, fabless 기능과 단일 팹 기능을 별도로 처리합니다. 화면이 URL 조립 규칙을 복제하지 않도록 이 진입점을 사용합니다.

### 3.2 API와 순수 함수

[useSemListApi.ts](../../../frontend/app/composables/useSemListApi.ts)는 `useRuntimeConfig().public.apiBase`와 기존 [joinApiPath](../../../frontend/app/utils/apiPath.ts)를 이용해 URL을 만듭니다. `fetchSemList()`는 `$fetch`이고 `filterRows()`는 장비 모델 분류와 팹 필터입니다. 필터의 서버 팹 값과 선택 팹 값은 대소문자를 정규화해서 비교합니다.

타입 `SemListRow`는 응답을 읽는 개발 계약입니다. `$fetch<SemListResponse>`라는 타입 표기만으로 잘못된 서버 JSON이 런타임에 검증되는 것은 아닙니다. 응답 계약을 바꾸면 백엔드·fixture·사용 화면을 함께 확인해야 합니다.

### 3.3 데이터 요청과 영속 상태

[sem-list 캐싱](sem-list-caching.md)은 `useAsyncData('sem-list')`, `payloadCache`, Promise slot을 함께 설명합니다. `refresh()`를 호출했다고 항상 새 HTTP 요청이 생기지 않는 것이 핵심입니다.

[영속 상태](persisted-state.md)는 `usePersistedState`의 복원, detached scope, 동기 watcher, 배열 교체 규칙을 설명합니다. `navigation.favorites` 자체는 현재 인메모리이며 영속 팩토리가 있다는 사실과 별개입니다. 반면 device cart와 레시피 선택 등은 실제로 영속 팩토리를 사용합니다.

### 3.4 Page, View, Layout의 역할 분리

[CD-SEM 팹 페이지](../../../frontend/app/pages/ebeam/cd-sem/[fab]/index.vue)는 `useFabRoute('cd-sem')`로 선택 팹을 얻고 재사용 View에 `tool-type`, `fabs`, 제목 등을 넘깁니다. `AppAsyncBoundary`는 로딩 경계를 감쌉니다. 페이지가 모든 표 로직을 복사할 필요가 없는 구조입니다.

[ToolInventoryView.vue](../../../frontend/app/components/ebeam/ToolInventoryView.vue)는 `useSemList()`의 전체 목록에서 `computed(() => filterRows(...))`로 장비군과 팹에 해당하는 행을 계산합니다. 검색·모델·상태 조건과 정렬도 파생 결과로 만듭니다. 예전 팹별 API key로 원본 목록을 중복 fetch하는 예제와 다릅니다.

```text
공유 sem-list 응답
 → 장비군 / 선택 팹 filterRows
 → 검색 / 모델 / 상태 조건
 → 정렬 결과
 → 화면 표 / 카운터 / 내보내기에 필요한 파생 결과
```

null 또는 undefined일 때 `?? []`를 쓰는 것은 로딩 중 계산 오류를 막기 위한 것입니다. 오류가 발생했을 때도 항상 빈 배열만 보여 주면 사용자가 0건과 실패를 구분하지 못하므로 오류·로딩 상태 표시는 별도 필요합니다.

[홈 페이지](../../../frontend/app/pages/index.vue)는 `definePageMeta({ layout: 'hub' })`를 지정합니다. [default layout](../../../frontend/app/layouts/default.vue)은 현재 route가 e-beam인지와 `hideFabSidebar` 메타를 함께 보고 팹 사이드바 표시를 결정합니다. '기본 레이아웃이면 항상 사이드바가 있다'고 단정하지 않습니다.

### 3.5 시각 규칙도 공유 계약입니다

[DESIGN.md](../../../DESIGN.md)가 시각 언어의 기준입니다. 현재 규칙은 종이색 표면·따뜻한 잉크·terracotta 필터 강조이며 'zinc만 쓰는 모노톤'이라는 옛 설명은 유효하지 않습니다. 색은 `--sk-*` 토큰을 사용하고 navigation과 filter의 강조 의미를 구분합니다. 컴포넌트에 보이는 옛 클래스가 새 화면의 기준을 자동으로 결정하지는 않습니다.

## 4. 선택 이유와 한계

내장 `useState`로 공유 상태를 만들 수 있고 `useAsyncData`로 서버 응답을 공유할 수 있으므로 같은 기능을 위한 라이브러리를 추가하지 않습니다. Pinia 재검토 사유는 store 개수 자체가 아니라 시간 여행 디버깅이나 기존 컴포저블로 표현하기 어려운 상태 조정 같은 실제 요구입니다. TTL·focus refetch 같은 서버 캐시 요구가 생기면 별도로 평가합니다.

한계도 있습니다. localStorage에는 서버 존재 여부를 판단하는 정보가 없고, 데이터 캐시는 시간만 지나도 자동 최신화되지 않습니다. 모듈 scope 변수와 detached watcher를 가진 이 구현은 현재의 client SPA 전제를 이해하고 써야 합니다. SSR을 켜는 작업에서 그대로 재사용한다고 가정하지 않습니다.

## 5. 흔한 실수

- `useState`를 localStorage라고 생각해서 F5 뒤에도 유지된다고 기대합니다.
- 새 배열이 필요한 영속 ref를 `.push()`로 바꿔 저장 watcher를 건너뜁니다.
- 정규화된 팹을 다시 raw 문자열과 비교합니다.
- 같은 API를 여러 컴포넌트에서 직접 `$fetch`하여 공유 진입점을 우회합니다.
- 타입 검사 성공을 실제 데이터 소비 또는 회사 응답 검증의 증거로 봅니다.

## 6. 안전 실습

저장소 루트에서 호출자와 변경 지점을 읽습니다.

```bash
rg -n 'useSemList\(' frontend/app
rg -n 'usePersistedState|entries.value =' frontend/app/composables/useRecipeSelectionSet.ts
rg -n 'setFabs|canonicalFabList|readonly' frontend/app/stores/navigation.ts
```

홈과 사이드바가 같은 서버 데이터 진입점을 쓰는지, 레시피 변경이 배열을 교체하는지, 팹 정규화가 store 쓰기 경계에 있는지 설명하면 성공입니다. 다음 단계는 두 상세 문서의 무해한 실습입니다.

공식 기초는 [Nuxt 4 useState](https://nuxt.com/docs/4.x/api/composables/use-state), [Vue 3 computed](https://vuejs.org/guide/essentials/computed.html), [Nuxt 4.5.0 asyncData 소스](https://github.com/nuxt/nuxt/blob/v4.5.0/packages/nuxt/src/app/composables/asyncData.ts)입니다.
