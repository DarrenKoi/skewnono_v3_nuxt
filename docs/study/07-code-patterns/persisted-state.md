# usePersistedState — localStorage 영속 상태 팩토리

> **이 문서는 예전 노트를 정정합니다.** 이 폴더 README의 옛 서술("Favorites 영속화 미구현", "Pinia 도입 검토")은 **낡았습니다.** 지금은 `usePersistedState` 팩토리가 있고 8개 컴포저블이 씁니다. CLAUDE.md는 Pinia를 명시적으로 **거부**합니다("no Pinia"). Pinia는 `package.json`에 설치돼 있지도 않습니다.

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

### 3.3 `flush: 'sync'` — 클릭이 확인됐으면 즉시 durable

기본 Vue watcher는 microtask 큐(`'pre'`)에서 flush됩니다. 사용자가 "담기"를 누른 직후 탭을 닫으면, 변경과 flush 사이에 **write가 유실**될 수 있습니다. `flush: 'sync'`는 변경과 **같은 틱에 동기적으로** localStorage에 씁니다. 헤더 주석: *"an acknowledged user action ... is durable before the next event loop tick — a tab close right after the click cannot silently drop it."*

### 3.4 방어적 SSR/CSR + 예외 처리

`read`/`write` 모두 `if (!import.meta.client)`로 서버에서 단락(이 앱은 `ssr:false`라 클라이언트 분기만 실제로 돎). `read`는 `try/catch`로 감싸 storage가 null·깨짐·검증 실패면 `default()`로 폴백. `write`도 `try/catch` — Safari 프라이빗 모드처럼 localStorage가 막힌 환경 대비.

### 3.5 빈 키 위생

기본 `isEmpty`는 빈 배열을 "키 삭제"(`removeItem`)로 취급합니다. `[]`를 쓰지 않아서 **빈 선택이 키로 쌓이지 않습니다.**

## 4. 사용례 — 옵션을 얼마나 쓰느냐로 3단계

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
2. **멤버십은 파생 Set으로** — `computed(() => new Set(selected.value))` + `has(x) => set.has(x)`.
3. **불변 재작성** — 모든 변경이 새 배열로 교체(spread/filter). in-place `.push` 금지 → 이래야 `flush:'sync'` watcher가 발동. (대조: 비영속 `navigation` 스토어는 in-place `.push`를 씀.)
4. **균일한 메서드 표면** — `has / add / remove / toggle / clear` + `count = computed(...)`.
5. **키로 스코핑** — recipe·skewvoir 선택은 `toolType`(+`fab`)로 `stateKey`와 `storageKey`를 네임스페이스해, tool/fab 조합마다 독립 카트.

정규 `toggle` 예 (`useRecipeSelectionSet.ts`):

```ts
const has = (name: string) => selected.value.includes(name)
const add = (name: string) => {
  const trimmed = name.trim()
  if (!trimmed || has(trimmed)) return
  selected.value = [...selected.value, trimmed]   // 불변 교체
}
const remove = (name: string) => {
  selected.value = selected.value.filter(existing => existing !== name)
}
const toggle = (name: string) => { if (has(name)) remove(name); else add(name) }
```

## 6. 아직 정리 안 된 부분 (정직하게)

- **`plugins/persist-fab.client.ts`는 아직 손수 짠 플러밍**입니다. 사이드바 fab 선택(`skewnono:fab_name`)을 자체 read + `watch` + localStorage로 처리 — CLAUDE.md가 "이제 이렇게 짜지 말라"고 하는 바로 그 패턴. 팩토리로 이전할 후보지만 현재는 살아 있습니다.
- **`stores/navigation.ts`의 `favorites`는 여전히 인메모리 전용**입니다. 팩토리(영속 인프라)는 존재하지만, 장비 즐겨찾기는 아직 `usePersistedState`에 연결되지 않았습니다. 즉 "영속 인프라가 생겼다"와 "navigation의 favorites가 그걸 쓴다"는 별개 — 후자는 미완.
- 참고: 현재 `NavigationState`에는 예전 노트에 나오던 `recent` 필드가 **없습니다.** "최근 본 항목"은 전용 컴포저블(`useSkewvoirRecentlyViewed` 등)로 옮겨졌습니다.

## 7. Pinia는 왜 안 쓰나 (확정)

CLAUDE.md 원문: *"Pinia is **not** used — prefer Nuxt built-ins. ... Revisit Pinia only if a real need appears (e.g. devtools time-travel debugging or cross-store orchestration that composables can't express cleanly)."*

즉 "나중에 도입 검토"가 아니라 **명시적으로 안 씀**이고, 아주 특정한 트리거(devtools 시간여행 디버깅, 컴포저블로 표현 안 되는 store 간 오케스트레이션)가 나타날 때만 재고합니다. 서버 데이터 캐시에는 `useAsyncData`(→ `sem-list-caching.md`), 영속 클라이언트 상태에는 `usePersistedState` — 이 둘로 현재 요구를 전부 감당합니다.
