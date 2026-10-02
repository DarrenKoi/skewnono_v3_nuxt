# usePersistedState — localStorage 영속 상태 팩토리

2026-10-03 기준입니다. 실제 구현은 [usePersistedState.ts](../../../frontend/app/composables/usePersistedState.ts)입니다. Pinia는 직접 dependency로 선언되어 있지 않으며 현재 정책은 Nuxt 내장 상태를 우선 사용하는 것입니다. 팩토리 존재와 각 기능의 영속화 여부는 구분해서 읽습니다.

## 0. 먼저 알아둘 용어

| 용어 | 쉬운 뜻 |
| --- | --- |
| 영속화 | 앱을 다시 열어도 값이 남도록 보관하는 작업 |
| stateKey | Nuxt 메모리 안에서 ref를 공유하는 이름 |
| storageKey | 해당 origin의 localStorage에 저장하는 이름 |
| 직렬화 | 객체를 저장 가능한 문자열로 바꾸는 작업 |
| normalize | 저장 문자열을 복원한 값의 구조를 검증하는 작업 |
| scope | watcher 같은 반응형 동작의 수명을 묶는 범위 |
| detached | 컴포넌트 부모 scope와 독립적으로 만든 범위 |
| flush | watcher가 언제 실행될지 정하는 옵션 |

Nuxt 선언은 `^4.4.2`이며 lock과 확인한 설치본은 4.5.0입니다. Vue는 간접 의존성이고 lock·설치본은 3.5.40입니다. 이 장의 Vue 동작은 [watcher 공식 설명](https://vuejs.org/guide/essentials/watchers.html#sync-watchers)과 [effectScope API](https://vuejs.org/api/reactivity-advanced.html#effectscope)를 확인했습니다. 세부 패치 구현은 설치본을 기준으로 합니다.

## 1. 문제 — 새로고침에도 살아남아야 하는 클라이언트 상태

일부 상태는 F5를 눌러도 유지되어야 합니다.

- 장바구니(cart) 성격의 다중 선택 — 비교하려고 담아 둔 장비/레시피/측정 세트
- 저장된 프리셋, 최근 검색어, 최근 본 항목
- 화면 필터 선호 설정(선택한 fab, prod 카테고리 등)

`useState`는 SPA 세션 동안만 살아있고 새로고침하면 리셋됩니다. 그래서 localStorage가 필요합니다. 문제는 **컴포넌트마다 read/watch/write 플러밍을 손으로 짜다 보면** 미묘한 버그(SSR 가드 누락, 탭 닫힘 시 유실, 빈 값 축적)가 반복된다는 점입니다.

CLAUDE.md의 규칙: *"Do not hand-roll new localStorage read/write/watch plumbing in a composable; call `usePersistedState` instead."*

## 2. 팩토리 전문 — `composables/usePersistedState.ts`

```ts
export interface PersistedStateOptions<T> {
  default: () => T                          // storage가 비었/깨졌/검증 실패 시 초기값
  normalize: (parsed: unknown) => T         // 역직렬화 결과를 T로 검증/강제 (throw 가능)
  isEmpty?: (value: T) => boolean           // true면 키를 write 대신 remove. 기본: 빈 배열
  serialize?: (value: T) => string          // 기본 JSON.stringify
  deserialize?: (raw: string) => unknown    // 기본 JSON.parse
}

const persistenceScope = effectScope(true)
const attachedStateKeys = new Set<string>()

export const usePersistedState = <T>(
  stateKey: string,
  storageKey: string,
  options: PersistedStateOptions<T>
): Ref<T> => {
  const isEmpty = options.isEmpty ?? ((value: T) => Array.isArray(value) && value.length === 0)
  const serialize = options.serialize ?? ((value: T) => JSON.stringify(value))
  const deserialize = options.deserialize ?? ((raw: string): unknown => JSON.parse(raw))

  const read = (): T => {
    if (!import.meta.client) return options.default()
    try {
      const raw = window.localStorage.getItem(storageKey)
      if (raw === null) return options.default()
      return options.normalize(deserialize(raw))
    } catch {
      return options.default()
    }
  }

  const write = (value: T) => {
    if (!import.meta.client) return
    try {
      if (isEmpty(value)) {
        window.localStorage.removeItem(storageKey)
      } else {
        window.localStorage.setItem(storageKey, serialize(value))
      }
    } catch { /* localStorage can be unavailable in restricted browser contexts */ }
  }

  const state = useState<T>(stateKey, read)

  if (!attachedStateKeys.has(stateKey)) {
    attachedStateKeys.add(stateKey)
    persistenceScope.run(() => {
      watch(state, next => write(next), { flush: 'sync' })
    })
  }

  return state
}

// 흔한 normalizer: JSON 배열에서 문자열만 남김
export const normalizeStringArray = (parsed: unknown): string[] =>
  Array.isArray(parsed)
    ? parsed.filter((value): value is string => typeof value === 'string')
    : []
```

## 3. 이 팩토리가 옳게 한 다섯 가지

### 3.1 `useState`의 초기화 함수가 곧 `read()`

```ts
const state = useState<T>(stateKey, read)
```

`useState`는 첫 접근 시 초기화 함수를 부릅니다. 그 함수가 `read()`이므로, **최초 값이 정적 기본값이 아니라 localStorage에서 복원한 값**입니다. `stateKey`당 ref는 하나뿐이라 클라이언트 네비게이션 전체에서 공유됩니다.

### 3.2 detached effect scope — 컴포넌트가 사라져도 watcher가 산다

```ts
const persistenceScope = effectScope(true)   // 모듈 레벨, 한 번
...
persistenceScope.run(() => {
  watch(state, next => write(next), { flush: 'sync' })
})
```

보통 `watch`는 그걸 부른 컴포넌트가 unmount되면 함께 정리됩니다. 그러면 그 컴포넌트를 벗어난 뒤의 변경은 localStorage에 기록되지 않을 수 있습니다. **모듈 레벨 `effectScope(true)`**에 watcher를 등록하면, 그 watcher는 특정 컴포넌트가 아니라 **SPA 수명 전체**에 묶입니다. `attachedStateKeys` Set으로 `stateKey`당 watcher가 정확히 하나만 붙게 가드합니다.

### 3.3 `flush: 'sync'` — 상태 교체 직후 저장을 시도합니다

기본 `pre` watcher는 배치되어 부모 갱신 후, 해당 컴포넌트 DOM 갱신 전에 실행됩니다. 사용자가 "담기"를 누른 직후 탭을 닫으면, 변경과 flush 사이에 **write가 유실**될 수 있습니다. `flush: 'sync'`는 변경과 **같은 틱에 동기적으로** localStorage 쓰기를 시도합니다. 저장 공간 부족·차단 시 예외를 삼키므로 디스크 저장 성공까지 보장하는 표현은 아닙니다. 헤더 주석: *"an acknowledged user action ... is durable before the next event loop tick — a tab close right after the click cannot silently drop it."*

### 3.4 방어적 SSR/CSR + 예외 처리

`read`/`write` 모두 `if (!import.meta.client)`로 서버에서 단락(이 앱의 사용자 실행은 `ssr:false` SPA이며 서버에서는 window를 사용하지 않습니다). `read`는 `try/catch`로 감싸 storage가 null·깨짐·검증 실패면 `default()`로 폴백. `write`도 `try/catch` — Safari 프라이빗 모드처럼 localStorage가 막힌 환경 대비.

### 3.5 빈 키 위생

기본 `isEmpty`는 빈 배열을 "키 삭제"(`removeItem`)로 취급합니다. `[]`를 쓰지 않아서 **빈 선택이 키로 쌓이지 않습니다.**

## 4. 실제 사용례 — 옵션을 얼마나 쓰느냐로 3단계

### 4.1 가장 단순 — 문자열 배열 카트 (`useDeviceCart.ts`)

```ts
const selectedDeviceLots = usePersistedState<string[]>(
  'device-cart:selectedLots',
  'skewnono:deviceStatistics.selectedDeviceLots',
  { default: () => [], normalize: normalizeStringArray }
)
```

### 4.2 객체 배열 — 아이템별 타입가드를 normalize로 (`useDevicePresets.ts`)

```ts
const presets = usePersistedState<DevicePreset[]>(
  'device-presets:list',
  STORAGE_KEY,
  {
    default: () => [],
    normalize: parsed => Array.isArray(parsed) ? parsed.filter(isPreset) : []
  }
)
```

### 4.3 모든 옵션 총동원 — raw 문자열 저장 (`useDeviceStatisticsPreferences.ts`)

```ts
const selectedFab = usePersistedState<DeviceFab>(
  'device-stats:selectedFab',
  STORAGE_KEYS.fab,
  {
    default: () => DEFAULT_DEVICE_FAB,
    normalize: parsed =>
      typeof parsed === 'string' && isDeviceFab(parsed) ? parsed : DEFAULT_DEVICE_FAB,
    isEmpty: () => false,        // 절대 키 삭제 안 함
    serialize: value => value,   // JSON 아님 — 문자열 그대로
    deserialize: raw => raw
  }
)
```

`serialize`/`deserialize`를 오버라이드해 `"all"` 같은 값을 따옴표 없는 raw 문자열로 저장(JSON `"\"all\""` 대신), `isEmpty: () => false`로 항상 유지.

## 5. 클라이언트 다중 선택 "카트" 관용구

`useDeviceCart`, `useRecipeSelectionSet`, `useSkewvoirSearchSelection`, `useAfmCart`가 공유하는 모양:

1. **백킹 스토어** = `usePersistedState` 배열 ref.
2. **식별자에 맞는 멤버십 검사** — 문자열 카트는 `computed(() => new Set(selected.value))`와 `has(x)`를 쓰고 AFM은 filename Set으로 `isInGroup`을 계산합니다. 레시피는 `(name, fab_name)` 쌍이므로 `entries.value.some(...)`로 확인합니다. 모든 선택이 문자열 Set이라는 가정은 하지 않습니다.
3. **불변 재작성** — 모든 변경이 새 배열로 교체(spread/filter). in-place `.push` 금지 → 이 팩토리는 `deep: true`를 설정하지 않은 ref watcher이므로 이래야 `flush:'sync'` watcher가 발동. (대조: 비영속 `navigation` 스토어는 in-place `.push`를 씀.)
4. **비슷한 역할, 기능별 메서드** — 문자열·레시피 선택에는 `has / add / remove / toggle / clear`가 있고, AFM은 `isInGroup / addToGroup / removeFromGroup / toggleGroup / clearGroup`을 노출합니다. 역할이 같아도 메서드와 인자 계약이 같다고 단정하지 않습니다.
5. **키로 스코핑** — 각 기능이 실제 선택 단위를 키로 표현합니다. recipe는 toolType 단위이고 팹은 항목의 식별자에 포함됩니다. 다른 카트의 키 규칙을 추측해서 복사하지 않습니다.

현재 [useAfmCart.ts](../../../frontend/app/composables/useAfmCart.ts)는 여러 측정 행을 `addToGroup(...measurements)`로 받아 배열을 한 번 대입합니다. 각각 대입할 때마다 localStorage에 전체 배열을 직렬화하므로 일괄 추가를 한 번 저장하는 이유가 있습니다. 배열 형태만 검사하는 AFM normalizer를 모든 row의 필드 검증이라고 해석하지 않습니다.

현재 [useRecipeSelectionSet.ts](../../../frontend/app/composables/useRecipeSelectionSet.ts)는 문자열 배열 예제보다 풍부합니다. `RecipeSelectionEntry[]`를 저장하고 선택의 식별자는 `(name, fab_name)` 쌍입니다. storageKey는 `skewnono:recipe-search.selection.v2.${toolType}`로 **장비군별**이며 팹마다 별도 저장소를 만드는 구조가 아닙니다. 같은 레시피 이름을 여러 팹에서 선택할 수 있기 때문입니다. add/remove 경계에서 팹 대소문자를 정규화하고 utils의 upsert/remove 결과로 배열을 교체합니다.

[RecipeSwitcher.vue](../../../frontend/app/components/ebeam/RecipeSwitcher.vue)가 이 선택 목록을 읽어 open/lateral/meas-hist 화면에서 사용합니다. 여기서 `open`은 레시피 화면 기능명이며 Vue의 effect scope를 여는 옵션이 아닙니다. 저장 카트의 scope는 키가 정하고 watcher의 scope는 `effectScope(true)`가 정합니다. 두 의미를 섞지 않습니다.

```text
최초 stateKey 접근 → localStorage read → deserialize → normalize → useState ref
후속 같은 key 접근 → 이미 있는 ref (다시 read하지 않음)
배열 .value 교체 → shallow watch 감지 → sync write 시도
페이지 unmount → detached watcher 유지
F5 → 새 모듈 / 새 ref → 저장 문자열에서 복원
```

## 6. 아직 정리 안 된 부분 (정직하게)

- **`plugins/persist-fab.client.ts`는 아직 손수 짠 플러밍**입니다. 사이드바 fab 선택(`skewnono:fab_name.v2`)을 자체 read + `watch` + localStorage로 처리 — CLAUDE.md가 "이제 이렇게 짜지 말라"고 하는 바로 그 패턴. 팩토리로 이전할 후보지만 현재는 살아 있습니다.
- **`stores/navigation.ts`의 `favorites`는 여전히 인메모리 전용**입니다. 팩토리(영속 인프라)는 존재하지만, 장비 즐겨찾기는 아직 `usePersistedState`에 연결되지 않았습니다. 즉 "영속 인프라가 생겼다"와 "navigation의 favorites가 그걸 쓴다"는 별개 — 후자는 미완.
- 참고: 현재 `NavigationState`에는 예전 노트에 나오던 `recent` 필드가 **없습니다.** "최근 본 항목"은 전용 컴포저블(`useSkewvoirRecentlyViewed` 등)로 옮겨졌습니다.

## 7. Pinia를 현재 도입하지 않는 이유

CLAUDE.md 원문: *"Pinia is **not** used — prefer Nuxt built-ins. ... Revisit Pinia only if a real need appears (e.g. devtools time-travel debugging or cross-store orchestration that composables can't express cleanly)."*

현재는 **명시적으로 사용하지 않으며**, 아주 특정한 트리거(devtools 시간여행 디버깅, 컴포저블로 표현 안 되는 store 간 오케스트레이션)가 나타날 때만 재고합니다. 서버 데이터 캐시에는 `useAsyncData`(→ `sem-list-caching.md`), 영속 클라이언트 상태에는 `usePersistedState` — 이 둘로 현재 요구를 전부 감당합니다.

## 8. 선택 이유와 한계

한 팩토리는 읽기 가드·예외 처리·중복 watcher 방지를 공유합니다. `attachedStateKeys`는 stateKey만 기준으로 하므로 같은 stateKey에 다른 storageKey나 옵션을 넘기면 첫 watcher의 계약이 남습니다. 키와 옵션은 일관되게 사용해야 합니다. `watch`에 `immediate`가 없어서 초기 normalize 결과를 즉시 저장하거나 잘못된 원본 키를 자동 삭제하지는 않습니다.

동기 watcher는 변경마다 실행되어 쓰기를 배치하지 않습니다. 큰 배열을 연속 교체하는 작업에는 비용이 생길 수 있습니다. scope는 SPA 수명 동안 유지되고 별도 stop이 없으므로 방문한 서로 다른 키가 누적됩니다. 현재 키 수가 제한되는 사용을 전제로 하며 무한한 개별 항목 키를 만드는 용도로 확장하지 않습니다.

localStorage는 해당 origin의 브라우저 저장소입니다. 포트가 달라지면 별도 저장소이고 서버와 동기화되지 않으며 storage 이벤트 listener도 없어 다른 탭에서 수정한 값을 자동 반영하지 않습니다. 비밀 정보를 저장하지 않습니다. normalize는 구조를 확인할 뿐 서버에 레시피가 여전히 존재하는지 보장하지 않습니다. `useTttmScope`, `measHistCascade` 등 소비자가 카탈로그 응답 이후의 유효성 조정을 맡습니다.

## 9. 흔한 실수

- `.push()` 또는 객체 내부 필드 수정이 영속 watcher를 호출한다고 생각합니다. `.value`에 새 값을 대입해야 합니다.
- `flush: 'sync'`를 저장 성공 보장이나 탭 간 동기화로 오해합니다.
- 같은 stateKey를 쓰면서 storageKey만 바꿔 별개 상태를 기대합니다.
- 비영속 navigation favorites와 영속 비교 카트를 같은 구현이라고 생각합니다.
- 팹 플러그인 버전 키가 바뀌면 옛 키가 삭제된다고 기대합니다. 현재 플러그인은 옛 키를 읽지 않을 뿐 삭제하지 않습니다.

## 10. 안전 실습

저장소 루트에서 먼저 코드를 읽습니다.

```bash
rg -n 'effectScope|watch\(|flush|attachedStateKeys' frontend/app/composables/usePersistedState.ts
rg -n 'selectedDeviceLots.value =' frontend/app/composables/useDeviceCart.ts
rg -n 'STORAGE_KEY|watch|removeItem' frontend/app/plugins/persist-fab.client.ts
```

기존 Vue 설치본으로 아래 무해한 반응형 원리를 확인할 수 있습니다. localStorage·프로젝트 파일·서버에 쓰지 않는 메모리 실습입니다. `frontend`에서 실행합니다.

```bash
node --input-type=module <<'JS'
import assert from 'node:assert/strict'
import { ref, watch, effectScope } from 'vue'
const selected = ref([])
const writes = []
const scope = effectScope(true)
scope.run(() => watch(selected, value => writes.push([...value]), { flush: 'sync' }))
selected.value.push('A')
assert.equal(writes.length, 0)
selected.value = [...selected.value, 'B']
assert.deepEqual(writes, [['A', 'B']])
scope.stop()
console.log('배열 교체와 동기 watcher 확인 완료')
JS
```

첫 push는 내부 변경이라 watcher가 기록하지 않고 다음 배열 교체는 반환 전 기록됩니다. 이 결과는 watcher 원리 검증이며 실제 저장 quota·탭 닫힘·회사 브라우저 검증은 아닙니다.
