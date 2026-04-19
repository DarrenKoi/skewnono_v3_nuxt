# 01. TypeScript 문법 (백엔드 개발자용)

TypeScript는 JavaScript에 **정적 타입 시스템**을 얹은 언어입니다. Python의 `typing` 모듈이나 `mypy`와 비슷한 역할이지만, TS는 컴파일 타임에 타입 검사를 하고 최종적으로 JS로 변환됩니다.

## 1. 기본 타입

```ts
let count: number = 10          // 숫자
let name: string = 'Claude'     // 문자열
let active: boolean = true      // 불리언
let ids: number[] = [1, 2, 3]   // 배열
let pair: [string, number] = ['a', 1]  // 튜플 (고정 길이)
let anything: any = 'whatever'  // any — 쓰지 말 것 (타입 검사 비활성화)
let nothing: null = null
let notYet: undefined = undefined
```

Python 비교:

| Python | TypeScript |
| --- | --- |
| `int`, `float` | `number` |
| `str` | `string` |
| `bool` | `boolean` |
| `list[int]` | `number[]` 또는 `Array<number>` |
| `tuple[str, int]` | `[string, number]` |
| `None` | `null` / `undefined` |
| `Optional[int]` | `number \| undefined` 또는 `number \| null` |

## 2. 타입 별칭(type alias)과 인터페이스(interface)

```ts
// type alias — 어떤 타입이든 가능
type Category = 'ebeam' | 'thickness'
type Fab = 'all' | 'R3' | 'M11' | 'M12' | 'M14' | 'M15' | 'M16'

// interface — 객체 모양 전용 (extends 가능)
interface EbeamToolRow {
  fab_name: Exclude<Fab, 'all'>     // 유틸리티 타입: 'all' 제외
  eqp_id: string
  eqp_model_cd: string
  eqp_ip: string
  version: number
  available: 'On' | 'Off'           // 리터럴 유니온
}
```

**실무 팁**: 객체 모양에는 `interface`, 유니온/교차/기본 타입에는 `type`을 쓰는 것이 Nuxt 커뮤니티 관례입니다. 이 프로젝트의 `stores/navigation.ts`가 정확히 이 패턴을 따릅니다.

## 3. 유니온 타입과 리터럴 타입

프로젝트에서 가장 많이 쓰이는 패턴입니다.

```ts
// 리터럴 유니온 — 허용되는 값을 미리 제한
export type ToolType = 'cd-sem' | 'hv-sem' | 'verity-sem' | 'provision'

// 함수 인자에서 실수로 오타가 나면 컴파일러가 잡아줌
function setToolType(t: ToolType) { /* ... */ }
setToolType('cd-sm')  // ❌ 컴파일 에러
setToolType('cd-sem') // ✅
```

이는 Python의 `Literal['cd-sem', 'hv-sem']` (typing.Literal)과 같은 역할입니다.

## 4. 제네릭(Generics)

Python의 `TypeVar`와 유사합니다.

```ts
// Record<K, V>: 키가 K이고 값이 V인 객체 타입
export type EbeamToolInventoryResponse = Record<ToolType, EbeamToolRow[]>
// 내부적으로는 {
//   'cd-sem': EbeamToolRow[],
//   'hv-sem': EbeamToolRow[],
//   'verity-sem': EbeamToolRow[],
//   'provision': EbeamToolRow[]
// } 와 같음

// Map<K, V>: 자바스크립트의 Map 객체
const summaryMap = new Map<Exclude<Fab, 'all'>, FabToolSummary>()

// Promise<T>: T를 resolve하는 Promise
const fetchToolInventory = async (): Promise<EbeamToolInventoryResponse> => { ... }

// 사용자 정의 제네릭 함수
function identity<T>(value: T): T { return value }
```

## 5. 유틸리티 타입

TS가 내장한 제네릭 타입들. 자주 쓰는 것만 기록합니다.

```ts
type A = { a: number; b: string; c: boolean }

Partial<A>   // { a?: number; b?: string; c?: boolean } — 모든 속성 선택적
Required<A>  // 모든 속성 필수 (반대)
Readonly<A>  // 모든 속성 readonly
Pick<A, 'a' | 'b'>  // { a: number; b: string } — 고르기
Omit<A, 'c'>        // { a: number; b: string } — 제외
Record<'x' | 'y', number>  // { x: number; y: number }

type U = 'all' | 'R3' | 'M11'
Exclude<U, 'all'>   // 'R3' | 'M11'  ← 이 프로젝트에서 사용됨
Extract<U, 'all'>   // 'all'

type F = (a: number) => string
ReturnType<F>       // string
Parameters<F>       // [number]

type P = Promise<number>
Awaited<P>          // number
```

## 6. 함수 타입

```ts
// 화살표 함수
const add = (a: number, b: number): number => a + b

// 함수 타입 정의
type BinaryOp = (a: number, b: number) => number
const sub: BinaryOp = (a, b) => a - b

// 기본값 + 옵션 인자 (?)
function greet(name: string, msg: string = 'Hello', title?: string) { ... }

// 프로젝트 예시: composable
export const useEbeamToolApi = () => {
  const filterRows = (
    inventory: EbeamToolInventoryResponse,
    toolType: ToolType,
    fab: Fab = 'all'          // 기본값
  ): EbeamToolRow[] => { ... }
  return { filterRows, ... }
}
```

## 7. `import type` vs `import`

TS에서는 타입 전용 import와 값 import를 구분할 수 있습니다.

```ts
// 타입만 필요할 때 — 컴파일 후 완전히 제거됨
import type { Fab, ToolType } from '~/stores/navigation'

// 실제 값(함수/상수/클래스)을 import
import { useNavigationStore } from '~/stores/navigation'
```

**왜 구분하나?** 타입은 런타임에 존재하지 않으므로, `import type`으로 표시하면 번들 최적화에 유리하고 순환 참조를 줄일 수 있습니다. 이 프로젝트는 composable 상단에서 일관되게 `import type`을 사용합니다.

## 8. 옵셔널 체이닝(`?.`)과 널 병합(`??`)

```ts
// 예전: (a && a.b && a.b.c) 체크
// 지금: a?.b?.c — 중간이 null/undefined면 undefined 반환
inventory.value?.[tool.id].length ?? tool.count
//        ^^                        ^^
//        옵셔널 체이닝             널 병합 (왼쪽이 null/undefined면 오른쪽)

const summary = summaryMap.get(row.fab_name) ?? {
  fab_name: row.fab_name, total: 0, online: 0, offline: 0
}
```

Python 비교: `a.b.c if a and a.b else None` → `a?.b?.c`

## 9. `as` 타입 단언(type assertion)

```ts
const match = route.match(/\/ebeam\/(cd-sem|hv-sem|verity-sem|provision)/)
return match ? match[1] as ToolType : null
//                        ^^^^^^^^^
//                        "나는 이 문자열이 ToolType임을 보증한다"
```

타입을 강제로 내려받는 장치. 남발하면 타입 시스템이 무너집니다. 외부에서 들어온 데이터에서 타입을 좁힐 때만 쓰세요.

`as const`는 조금 다릅니다 — 값을 리터럴 타입으로 고정합니다.

```ts
const cats = [
  { id: 'ebeam' as const, label: 'E-Beam' },
  { id: 'thickness' as const, label: 'Thickness' }
]
// id의 타입이 string이 아닌 'ebeam' | 'thickness'로 좁혀짐
```

이 프로젝트 `AppHeader.vue`에서 사용됩니다.

## 10. `strict` 모드

`tsconfig.json`의 `strict: true`(Nuxt 기본값)이면 다음이 활성화됩니다.

- `strictNullChecks` — `null`/`undefined`를 명시적으로 처리해야 함
- `noImplicitAny` — 타입을 추론 못 하면 에러
- `strictFunctionTypes` — 함수 시그니처 엄격 검사

**처음 익힐 때 가장 많이 걸리는 것**: `obj.field`가 `undefined`일 수 있다는 에러. `obj?.field`나 `if (obj)` 가드로 해결합니다.

## 11. 프로젝트에 나타난 타입 패턴 요약

| 파일 | 사용한 TS 기능 |
| --- | --- |
| `stores/navigation.ts` | `type` union, `interface`, `readonly`, 제네릭 `useState<T>` |
| `mock-data/.../ebeam-tool-inventory.ts` | `interface`, `Record<K, V>`, `Exclude<T, U>`, 리터럴 유니온 |
| `composables/useEbeamToolApi.ts` | `import type`, 제네릭 `$fetch<T>`, `Map<K, V>`, 기본값 인자 |
| `components/ebeam/ToolInventoryView.vue` | `defineProps<{...}>()` + `withDefaults`, 제네릭 컴포저블 |
| `components/nav/AppHeader.vue` | `as const` 리터럴 좁히기 |

## 더 읽을 거리

- TypeScript Deep Dive (한국어 번역본): https://radlohead.gitbook.io/typescript-deep-dive/
- Effective TypeScript (책) — Item 중심으로 골라 읽기 권장
- Vue 공식 TS 가이드: https://vuejs.org/guide/typescript/overview.html
