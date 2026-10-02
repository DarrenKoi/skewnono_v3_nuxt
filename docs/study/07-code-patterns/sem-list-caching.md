# sem-list 캐싱: 재요청과 결과 재사용을 구분합니다

2026-10-03의 구현은 [useSemListApi.ts](../../../frontend/app/composables/useSemListApi.ts)와 [asyncDataCache.ts](../../../frontend/app/utils/asyncDataCache.ts)를 기준으로 합니다. 아래의 2026-04-26 사례는 당시 문제를 이해하는 역사 기록이며 현재 Nuxt 4.5.0의 결함이나 현재 브라우저 측정 결과를 뜻하지 않습니다.

## 1. 기초: 캐시는 보관이고 dedupe는 요청 처리입니다

같은 장비 목록을 홈·사이드바·장비 표가 읽습니다. 소비자마다 `$fetch`하면 요청과 오류 처리가 흩어집니다. `useSemList()`는 결과를 공유할 진입점입니다. 캐시가 있다는 말은 최신값이라는 뜻이 아닙니다. 또한 HTTP 요청을 합치는 것과 완료된 결과를 오래 쓰는 것은 별개입니다.

## 2. 용어

| 용어 | 역할 |
| --- | --- |
| key | `sem-list`라는 리소스 식별자 |
| payload | Nuxt 앱의 `payload.data[key]` 결과 |
| static data | `static.data[key]`에서 읽을 수 있는 정적 payload 데이터 |
| `getCachedData` | handler 실행 전에 재사용 결과를 고르는 함수 |
| handler | 실제 데이터를 만드는 함수, 여기서는 slot을 거친 fetch |
| `refresh` | AsyncData 재실행 요청, 반드시 새 HTTP 요청이라는 뜻은 아님 |
| dedupe `cancel` | 기존 Nuxt 실행을 취소하고 새 실행을 시도 |
| dedupe `defer` | 이미 진행 중이면 그 Nuxt 실행을 기다림 |
| slot | 앱이 따로 보관하는 Promise 한 칸 |

lock과 설치본 모두 Nuxt 4.5.0입니다. `package.json` 선언은 `^4.4.2`입니다. 패치 버전별 동작은 [4.5.0 공식 소스](https://github.com/nuxt/nuxt/blob/v4.5.0/packages/nuxt/src/app/composables/asyncData.ts)와 설치본을 대조했습니다. 최신 설명만 보고 다른 버전의 `force` 옵션을 복사하지 않습니다.

## 3. 실제 구현: 세 층을 통과합니다

```text
useSemList()
 → useAsyncData('sem-list', fetchOnce, { default: () => [], getCachedData: payloadCache })
 → 캐시가 반환되면 handler 생략
 → 없으면 fetchOnce()
 → semListSlot.run(fetchSemList)
 → slot이 없으면 $fetch('/api/sem-list'), 있으면 같은 Promise 반환
```

`payloadCache`는 `payload.data[key] ?? static.data[key]`를 반환합니다. 배열이 `[]`여도 존재하는 결과이므로 캐시입니다. `default: () => []`는 초기 화면의 안전한 값이며 그 자체를 서버가 답했다는 증거로 쓰면 안 됩니다.

`createInFlightSlot`은 **성공한 Promise를 완료 후에도 유지합니다.** 이름만 보고 요청 중에만 유지한다고 읽으면 안 됩니다. 실패하면 catch에서 null로 비워 재시도할 수 있습니다. `reset()`은 별도 기능이지만 `semListSlot`의 reset을 호출하는 코드는 현재 없습니다.

Nuxt의 key 기반 상태 공유와 dedupe는 내장 기능입니다. 프로젝트 주석은 과거 SPA 형제 컴포넌트 마운트 경쟁에 대비한 별도 slot의 배경을 설명합니다. 그것만으로 현재 Nuxt 4.5.0이 dedupe를 못 한다는 일반 결론을 내리지 않습니다. 중요한 현재 사실은 **Nuxt의 실행 Promise와 앱의 slot Promise가 서로 다른 보관소**라는 것입니다.

### 3.1 refresh, force, clear를 정확히 읽습니다

Nuxt 4.5.0의 실행 옵션에는 `dedupe`, `timeout`, `signal` 등이 있으며 **공개 `force` 옵션은 없습니다.** `refresh({ force: true })`는 이 버전의 해법이 아닙니다. 현재 `execute` 구현은 granular cache 설정 아래서 명시적 refresh도 `getCachedData`에 `refresh:manual` 또는 `refresh:hook` cause를 전달합니다. 이 앱의 `payloadCache`는 cause를 무시하므로 refresh에도 캐시를 돌려줄 수 있습니다.

[같은 유틸](../../../frontend/app/utils/asyncDataCache.ts)의 `payloadCacheOnInitial`은 cause가 `initial`일 때만 캐시를 쓰므로 별도 의미가 있습니다. 하지만 sem-list는 그것을 사용하지 않습니다. `clearNuxtData('sem-list')`로 Nuxt 결과만 비워도 slot의 완료 Promise는 남아 있습니다. handler가 실행되어도 기존 응답을 받을 수 있습니다. `dedupe: 'cancel'`도 앱 slot을 reset하지 않고, 이 fetcher는 Nuxt가 전달하는 abort signal을 `$fetch`에 넘기지도 않습니다.

| 상황 | 현재 구현의 결과 |
| --- | --- |
| 첫 진입, 두 캐시가 없음 | slot이 비었으면 HTTP 요청 |
| 겹친 handler 호출 | slot이 같은 Promise 반환 |
| 페이지 이동 | 남은 payload 또는 성공 Promise 재사용 가능 |
| 명시적 refresh | payload가 있으면 재사용 가능; handler가 실행돼도 성공 slot 재사용 가능 |
| Nuxt cache만 clear | slot까지 비운다는 뜻이 아님 |
| 최초 요청 실패 후 다시 실행 | slot이 비워져 HTTP 재시도 가능 |
| F5, 새 앱 인스턴스 | 메모리 cache와 모듈 slot이 새로 만들어짐 |

`static.data`는 모든 API 응답을 자동 영구 보관하는 브라우저 DB가 아닙니다. 두 cache의 수명은 Nuxt 앱·payload와 소비자 생명주기에 영향을 받습니다. 영속 장비 카탈로그가 필요하다는 요구는 현재 없습니다.

## 4. 선택 이유와 한계

현재 목록 재사용에는 Pinia가 필요하지 않습니다. 서버 응답은 `useAsyncData`, 영속 사용자 선택은 [usePersistedState](persisted-state.md)로 구분합니다. Vue Query의 TTL, focus 재조회, polling, key-prefix 무효화가 필요한 실제 요구가 생겼을 때 평가하며 즐겨찾기 구현만으로 Pinia를 자동 도입하지 않습니다. Nuxt UI 내부의 TanStack **Table** 사용과 TanStack **Query** 도입도 별개입니다.

현재 sem-list는 SPA 안에서 성공한 목록을 계속 재사용하는 방향입니다. 새 목록 보장이 필요한 버튼을 만들 때는 cache 정책, slot reset, signal 전달을 함께 설계해야 합니다. 이 장의 갱신은 런타임 동작을 바꾸는 작업이 아니므로 이 한계를 설명만 합니다.

## 5. 흔한 실수

- Promise가 resolve되면 slot도 자동으로 비워진다고 생각합니다.
- refresh/clear/dedupe를 모두 캐시 무효화의 동의어로 사용합니다.
- 모듈 변수는 페이지 이동 때마다 초기화된다고 생각합니다.
- 과거 Playwright 요청 횟수를 현재 코드의 새 측정처럼 인용합니다.
- 표가 쓰는 행과 카운터·다운로드가 쓰는 행을 서로 다르게 필터링합니다.

## 6. 안전 실습

실제 API에 요청하지 않고 소스에서 다음 세 사실을 찾습니다.

```bash
rg -n 'SEM_LIST_CACHE_KEY|semListSlot|getCachedData' frontend/app/composables/useSemListApi.ts
rg -n 'cause|inFlight|reset' frontend/app/utils/asyncDataCache.ts
rg -n 'useSemList\(' frontend/app
```

Promise 성공 뒤 null 대입이 없다는 점, reset 함수와 sem-list 호출의 차이, `payloadCacheOnInitial`의 cause 분기를 설명하면 성공입니다. 기존 [identity 회귀 테스트](../../../frontend/app/composables/useIdentity.test.ts)는 다른 리소스가 payload와 slot을 함께 비우는 사례입니다. 이 테스트 통과를 sem-list refresh나 실제 브라우저 중복 요청 검증으로 확대 해석하지 않습니다.

### 6.1 실제 유틸로 Promise 보관을 확인합니다

저장소 루트에서 Node 24로 실행합니다. Nuxt 앱이나 Flask 서버는 실행하지 않으며 HTTP 요청도 만들지 않습니다. `.ts`의 type-only import는 Node의 type stripping으로 제거됩니다.

```bash
node --input-type=module <<'JS'
import assert from 'node:assert/strict'
import { createInFlightSlot } from './frontend/app/utils/asyncDataCache.ts'
let calls = 0
const slot = createInFlightSlot()
const fetcher = async () => ++calls
assert.equal(await slot.run(fetcher), 1)
assert.equal(await slot.run(fetcher), 1)
assert.equal(calls, 1)
slot.reset()
assert.equal(await slot.run(fetcher), 2)
console.log('성공 Promise 재사용과 reset 확인 완료')
JS
```

완료된 첫 결과를 두 번째 run도 재사용하고 reset 이후만 새 fetcher 호출이 생기면 성공입니다. 이것은 이 유틸의 실행 검증이며 Nuxt 전체 마운트·dedupe 또는 브라우저 요청 횟수의 측정은 아닙니다.

## 7. 보존한 역사 사례: 2026-04-26

당시 정리한 유용한 학습 내용은 아래에 남깁니다. 절 번호와 과거 before/after 예제는 당시 맥락입니다. 현재 `ToolInventoryView`를 읽을 때도 화면·카운터·내보내기가 동일 파이프라인을 쓰는지 확인하는 질문은 유효합니다.

### 7.1 죽은 코드와 "write-only state" 패턴

#### 7.1.1 발견한 것

`/simplify` 리뷰 결과 다음 코드가 **사용되지 않는데도 작동하고 있었습니다.**

- `composables/useFavorites.ts` — 어디서도 `import`되지 않음
- `composables/useRecent.ts` — 어디서도 `import`되지 않음
- `stores/navigation.ts`의 `recent` 상태 + `addRecent` 액션
- `pages/ebeam/{cd-sem,hv-sem,veritysem,provision}/[fab]/index.vue` 4개 파일의 `addRecent(next)` 호출

흥미로운 점은 `recent`가 단순히 안 쓰인 게 아니라 **쓰이긴 하지만 읽히지 않았다**는 것입니다. 4개의 fab 페이지가 이동할 때마다 충실히 `addRecent`를 호출했지만, 그 결과를 화면에 보여줄 코드는 한 줄도 없었습니다. `pages/index.vue`의 "Recent" 카드는 단순히 `"No recent activity"`라는 하드코딩된 문자열만 표시하고 있었습니다.

#### 7.1.2 왜 이런 코드가 살아남았는가

타입 검사기는 **양 끝이 모두 정상이면** 통과시킵니다.

- 쓰는 쪽: `addRecent(next)` — 진짜 함수 호출, 시그니처 일치, 통과
- 받는 쪽: `state.value.recent = [...]` — 진짜 배열 mutation, 통과

타입스크립트가 잡지 못하는 것은 "이 데이터를 누군가 *읽긴 하는가?*" 입니다. 컴파일러는 함수가 호출되었는지, 변수가 쓰여졌는지는 알지만, 그 결과가 *소비*되는지는 모릅니다.

이런 패턴을 **write-only state** 또는 **dangling pipeline**이라고 부릅니다. 보통 다음과 같은 경위로 생깁니다.

1. 처음에 기능 A를 절반 구현하다 "Recent 표시는 나중에" 하고 미룬다.
2. 그 사이에 "쓰는 쪽"만 머지된다.
3. 시간이 지나면 누가 왜 만들었는지 잊힌다.
4. 컴파일도 되고 테스트도 통과하니 그 상태로 굳는다.

#### 7.1.3 발견 방법

`rg`으로 *읽기*와 *쓰기*를 분리해서 보면 드러납니다.

```bash
# recent를 쓰는 곳
rg -n "addRecent|state\.recent\s*=" frontend/app

# recent를 읽는 곳
rg -n "store\.recent|\.recent\b" frontend/app
```

쓰는 곳은 5곳(상태 정의 + 4개 페이지), 읽는 곳은 0곳이었습니다. 배경 노이즈가 0이라면 그 파이프라인은 죽은 것입니다.

#### 7.1.4 교훈

- **타입 검사 통과 ≠ 코드가 의미 있다.** 양 끝이 일치해도 중간에 소비자가 없으면 죽은 파이프라인입니다.
- 새 기능을 추가할 때 **소비자(UI 표시)부터** 만드는 것이 안전합니다. 표시할 곳이 없는 데이터는 일단 모으지 않습니다.
- 정기적으로 `useXxx`, `addXxx` 같은 함수의 호출자를 *읽기 측*만 따로 카운트해 보면 좋습니다.

### 7.2 UTable 필터 파이프라인 일치 (single source of truth)

#### 7.2.1 문제

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

이 JavaScript 파이프라인이 **헤더 카운터(`X of Y tools`)**와 **표 다운로드** 결과를 만들고 있었습니다.

즉, 사용자가 화면에서 보는 표는 *TanStack의 결과*, 카운터와 다운로드는 *JS의 결과*였습니다. 대부분의 입력에서는 두 결과가 일치했지만, 두 필터 구현체가 미묘하게 다를 수 있는 지점(예: 숫자 컬럼 `version`에 대한 globalFilter 동작)에서는 어긋날 수 있었습니다.

#### 7.2.2 수정

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

이제 화면 표시, 헤더 카운터, 표 다운로드 모두 **하나의 진실 공급원**(`exportRows`)에서 나옵니다.

#### 7.2.3 교훈

UI 라이브러리가 제공하는 "내부 필터링" 기능과 직접 작성한 `computed` 필터를 **같은 데이터에 대해 동시에 돌리지 마세요.** 둘 중 하나만 골라야 합니다.

- 라이브러리 내부에 맡길 거면: 카운터·내보내기 같은 부수 정보도 라이브러리 API(`getRowModel()` 등)에서 읽어야 합니다.
- 직접 만들 거면: 라이브러리에는 이미 처리된 데이터를 넘기고 라이브러리의 필터 기능은 끕니다.
