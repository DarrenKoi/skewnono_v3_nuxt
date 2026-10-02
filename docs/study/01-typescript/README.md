# 01. TypeScript 문법 (백엔드 개발자용)

TypeScript는 JavaScript에 **정적 타입 시스템**을 얹은 언어입니다. Python의 `typing` 모듈이나 `mypy`와 비슷한 역할이지만, TS는 컴파일 타임에 타입 검사를 하고 최종적으로 JS로 변환됩니다.

**2026-10-03 확인:** [package.json](../../../frontend/package.json)의 `typescript: ^5.9.3`은 허용 범위입니다. [package-lock.json](../../../frontend/package-lock.json)과 원본 작업 공간의 설치 버전은 **5.9.3**입니다. `vue-tsc`는 선언 `^3.2.4`, lock/설치 **3.3.8**입니다. 이 문서의 문법 예시는 학습용이며 아래에서 현재 소스와 별도로 연결합니다.


이 장에서 API는 Application Programming Interface(프로그램 간 입출력 약속), JSON은 JavaScript Object Notation(텍스트 데이터 교환 형식), TS는 TypeScript의 줄임말입니다. 네트워크 응답을 타입으로 표현하는 일과 실제 값을 검증하는 일은 다릅니다.

## 1. 기초: 타입은 실행 전에 검사합니다

TypeScript 타입은 보통 JavaScript로 변환할 때 제거됩니다. 브라우저는 타입이 아니라 JavaScript를 실행합니다. 따라서 타입 검사 통과와 서버 JSON 검증은 다른 일입니다. `npm run typecheck`는 Nuxt/Vue 타입 검사이며, Vite 개발 변환이나 `npm run build`만으로 동일한 검사를 했다고 가정하지 않습니다.

```text
TypeScript / Vue 소스
  → vue-tsc와 Nuxt typecheck: 정적 계약 검사
  → Vite 변환 / 번들링: 브라우저 JavaScript 생성
  → 실행 중 API JSON 수신: 실제 값 확인은 별도 책임
```

## 2. 용어

| 용어 | 의미 |
| --- | --- |
| inference / 추론 | 타입을 적지 않아도 값과 문맥으로 타입을 계산합니다. |
| annotation / 주석 | `: string`처럼 기대 타입을 명시합니다. |
| union / 유니온 | 여러 타입 중 하나입니다. |
| generic / 제네릭 | 타입을 인자로 받는 계약입니다. |
| narrowing / 좁히기 | 조건 확인으로 가능한 타입의 범위를 줄입니다. |
| assertion / 단언 | 값 검증 없이 컴파일러에게 타입 가정을 전달합니다. |
| structural typing | 이름보다 필요한 필드 모양을 기준으로 호환성을 판단합니다. |

## 3. 문법에서 실제 코드로

아래 조각은 각 문법의 형태를 보여 줍니다. 모든 코드 블록을 한 파일에 합쳐 실행하는 예제가 아니며, 생략된 문맥의 이름은 설명용입니다. 실행 가능한 작은 예제는 6절에 별도로 제공합니다.

### 3.1 기본 타입

```ts
let count: number = 10          // 숫자
let userName: string = 'Claude'     // 문자열
let active: boolean = true      // 불리언
let ids: number[] = [1, 2, 3]   // 배열
let pair: [string, number] = ['a', 1]  // 튜플 (고정 길이)
let anything: any = 'whatever'  // any — 타입 검사 우회, 경계 입력에는 unknown 우선
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

### 3.2. 타입 별칭(type alias)과 인터페이스(interface)

```ts
// type alias — 어떤 타입이든 가능
// 학습용 유니온입니다. 현재 navigation store에 Category는 없습니다.
type Category = 'ebeam' | 'thickness'
type ExampleFab = 'all' | 'R3' | 'M11'

// interface — 객체 모양 전용 (extends 가능)
interface EbeamToolRow {
  fab_name: Exclude<ExampleFab, 'all'>     // 유틸리티 타입: 'all' 제외
  eqp_id: string
  eqp_model_cd: string
  eqp_ip: string
  version: string
  available: 'On' | 'Off'           // 리터럴 유니온
}
```

**실무 팁**: 객체 모양에는 `interface`, 유니온/교차/기본 타입에는 `type`을 쓰는 것이 Nuxt 커뮤니티 관례입니다. 프로젝트가 주로 사용하는 스타일이며 Nuxt가 강제하는 규칙은 아닙니다. 현재 `ToolType` 원본은 [utils/toolType.ts](../../../frontend/app/utils/toolType.ts), `Fab`는 [stores/navigation.ts](../../../frontend/app/stores/navigation.ts)의 `string` 별칭입니다. 위 `ExampleFab`처럼 고정 유니온으로 현재 FAB 전체를 제한하지 않습니다.

### 3.3. 유니온 타입과 리터럴 타입

프로젝트에서 가장 많이 쓰이는 패턴입니다.

```ts
// 리터럴 유니온 — 허용되는 값을 미리 제한
export type ToolType = 'cd-sem' | 'hv-sem' | 'veritysem' | 'provision'

// 함수 인자에서 실수로 오타가 나면 컴파일러가 잡아줌
function setToolType(t: ToolType) { /* ... */ }
setToolType('cd-sm')  // ❌ 컴파일 에러
setToolType('cd-sem') // ✅
```

이는 Python의 `Literal['cd-sem', 'hv-sem']` (typing.Literal)과 같은 역할입니다.

### 3.4. 제네릭(Generics)

Python의 `TypeVar`처럼 여러 타입에 대해 관계를 유지하는 표현입니다. 아래 InventoryResponse는 제네릭 학습용 모델이며 현재 SEM API의 응답은 `SemListRow[]`입니다.

```ts
// Record<K, V>: 키가 K이고 값이 V인 객체 타입
export type EbeamToolInventoryResponse = Record<ToolType, EbeamToolRow[]>
// 내부적으로는 {
//   'cd-sem': EbeamToolRow[],
//   'hv-sem': EbeamToolRow[],
//   'veritysem': EbeamToolRow[],
//   'provision': EbeamToolRow[]
// } 와 같음

// Map<K, V>: 자바스크립트의 Map 객체
const summaryMap = new Map<Exclude<ExampleFab, 'all'>, FabToolSummary>()

// Promise<T>: T를 resolve하는 Promise
const fetchToolInventory = async (): Promise<EbeamToolInventoryResponse> => { /* 구현 생략 */ }

// 사용자 정의 제네릭 함수
function identity<T>(value: T): T { return value }
```

### 3.5. 유틸리티 타입

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

### 3.6. 함수 타입

```ts
// 화살표 함수
const add = (a: number, b: number): number => a + b

// 함수 타입 정의
type BinaryOp = (a: number, b: number) => number
const sub: BinaryOp = (a, b) => a - b

// 기본값 + 옵션 인자 (?)
function greet(name: string, msg: string = 'Hello', title?: string) {
  return `${msg}, ${title ?? ''} ${name}`
}

// 함수 계약을 보여 주는 학습용 composable입니다. 현재 API 모듈과 구분합니다.
const makeInventoryFilter = () => {
  const filterRows = (
    inventory: EbeamToolInventoryResponse,
    toolType: ToolType,
    fab: ExampleFab = 'all'          // 기본값
  ): EbeamToolRow[] => inventory[toolType].filter(row => fab === 'all' || row.fab_name === fab)
  return { filterRows }
}
```

### 3.7. `import type` vs `import`

TS에서는 타입 전용 import와 값 import를 구분할 수 있습니다.

```ts
// 타입만 필요할 때 — 컴파일 후 완전히 제거됨
import type { Fab, ToolType } from '~/stores/navigation'

// 실제 값(함수/상수/클래스)을 import
import { useNavigationStore } from '~/stores/navigation'
```

**왜 구분하나?** 타입은 런타임에 존재하지 않으므로, `import type`으로 표시하면 번들 최적화에 유리하고 순환 참조를 줄일 수 있습니다. 이 프로젝트는 composable 상단에서 일관되게 `import type`을 사용합니다.

### 3.8. 옵셔널 체이닝(`?.`)과 널 병합(`??`)

```ts
// 예전: (a && a.b && a.b.c) 체크
// 지금: a?.b?.c — 중간이 null/undefined면 undefined 반환
inventory.value?.[tool.id]?.length ?? tool.count
//        ^^                        ^^
//        옵셔널 체이닝             널 병합 (왼쪽이 null/undefined면 오른쪽)

const summary = summaryMap.get(row.fab_name) ?? {
  fab_name: row.fab_name, total: 0, online: 0, offline: 0
}
```

Python 비교: `a.b.c if a and a.b else None` → `a?.b?.c`

### 3.9. `as` 타입 단언(type assertion)

```ts
const match = route.match(/\/ebeam\/(cd-sem|hv-sem|veritysem|provision)/)
return match ? match[1] as ToolType : null
//                        ^^^^^^^^^
//                        "나는 이 문자열이 ToolType임을 보증한다"
```

`as`는 검사 결과를 만들어 내는 장치가 아닙니다. 외부 입력은 먼저 실제 값을 검사하고 그 결과로 타입을 좁힙니다. 단언은 컴파일러가 표현하기 어려운 사실을 별도 근거로 보장할 수 있을 때만 제한적으로 사용합니다.

```ts
function parseAvailable(value: unknown): 'On' | 'Off' | null {
  if (value === 'On' || value === 'Off') return value
  return null
}
```

`unknown`은 사용 전에 확인하도록 강제합니다. `any`는 검사를 우회합니다. 오류가 난다고 외부 JSON을 `any`로 바꾸지 않습니다. `satisfies`는 추론을 유지한 채 타입 적합성을 검사하며 런타임 검증은 아닙니다.

`as const`는 조금 다릅니다 — 값을 리터럴 타입으로 고정합니다.

```ts
const cats = [
  { id: 'ebeam' as const, label: 'E-Beam' },
  { id: 'thickness' as const, label: 'Thickness' }
]
// id의 타입이 string이 아닌 'ebeam' | 'thickness'로 좁혀짐
```

현재 단일 원천에서 읽을 수 있는 예시는 utils/toolType.ts의 TOOL_TYPES입니다. UI 목록도 같은 owner 타입과 맞춰 읽습니다.

### 3.10. `strict` 모드

[frontend/tsconfig.json](../../../frontend/tsconfig.json)은 `.nuxt/tsconfig.app.json` 등 네 개의 생성 설정을 project reference로 연결합니다. 루트 파일에 strict를 직접 적은 구조가 아닙니다. Nuxt는 strict 타입 검사를 기본으로 구성하며 strict가 켜지면 다음을 확인합니다.

- `strictNullChecks` — `null`/`undefined`를 명시적으로 처리해야 함
- `noImplicitAny` — 타입을 추론 못 하면 에러
- `strictFunctionTypes` — 함수 시그니처 엄격 검사

**처음 익힐 때 흔한 오류**는 값이 `undefined`일 수 있다는 것입니다. 없는 상태가 실제로 허용되면 `?.`와 `??`로 처리하고, 필수 데이터라면 존재 여부를 검사해 오류나 로딩 상태를 표현합니다. 단순히 에러를 없애려고 모든 필드에 `!`나 기본값을 붙이면 계약 문제를 숨길 수 있습니다. `.nuxt/` 설정은 직접 고치지 않고 [nuxt.config.ts](../../../frontend/nuxt.config.ts)의 입력 설정을 고칩니다.

### 3.11 실제 저장소 연결

| 파일 | 현재 사용한 타입 기능 |
| --- | --- |
| [utils/toolType.ts](../../../frontend/app/utils/toolType.ts) | `as const`, indexed access, satisfies, 분류 결과 `ToolType \| null` |
| [stores/navigation.ts](../../../frontend/app/stores/navigation.ts) | `Fab = string`, `NavigationState`, ToolType 재수출 |
| [useSemListApi.ts](../../../frontend/app/composables/useSemListApi.ts) | `SemListRow`, `SemListResponse`, `$fetch<T>`, API 필터 |
| [ToolInventoryView.vue](../../../frontend/app/components/ebeam/ToolInventoryView.vue) | props, Nuxt UI TableColumn, 화면 계산 |
| [ChatComposer.vue](../../../frontend/app/components/chat/ChatComposer.vue) | typed emits, `defineModel<string>` |

현재 SEM 응답은 배열이며 `version`은 숫자가 아니라 string입니다. `'1A'` 같은 값도 표현합니다. 프런트 `mock-data/`와 `useEbeamToolApi.ts`는 현재 존재하지 않으며 위의 과거 Inventory 모델을 실제 소스라고 찾지 않습니다. 집/office 모두 Flask API를 사용합니다.

API 타입 매개변수와 Python [contracts.py](../../../backend/sem_list/contracts.py)는 기대 계약입니다. 타입 검사만으로 실제 office 데이터가 이 계약을 만족함을 증명하지는 않습니다.

## 4. 선택 이유와 한계

TypeScript는 오타와 누락된 필드, 함수 인자 오류를 실행 전에 찾는 데 유용합니다. 짧은 지역 변수는 추론을 사용하고 API 경계와 재사용 함수의 계약을 명시하면 불필요한 타입 표기를 줄일 수 있습니다. Python `int`/`float`가 모두 TS number와 같다는 비교는 기본 이해용입니다. JavaScript number는 부동소수점이므로 매우 큰 정수에는 정밀도 한계가 있습니다.

튜플과 Readonly 타입도 실행 중 배열 길이나 객체 변경을 막는 장치가 아닙니다. `readonly` 타입과 Vue `readonly()` Proxy 역시 다른 기능입니다. 컴파일러 보장, 실제 값 검증, 화면 반응성을 분리해서 읽습니다.

## 5. 흔한 실수

1. `as`로 외부 JSON 검증을 대체합니다. unknown을 실제 조건으로 좁힙니다.
2. `||`로 0, false, 빈 문자열을 없애 버립니다. null/undefined만 대체할 때는 `??`를 사용합니다.
3. `array?.[index].length`가 모든 단계의 누락을 막는다고 생각합니다. 요소도 없을 수 있으면 `array?.[index]?.length`처럼 해당 경계를 확인합니다.
4. IDE 오류를 없애려고 `.nuxt/`를 고칩니다. 생성 입력을 수정하고 필요한 경우 다시 prepare합니다.
5. 단언이나 `!`로 필수 값 부재를 감춥니다. 로딩, 실패, 누락을 명시합니다.
6. Nuxt alias / auto-import가 일반 Node 테스트에도 있다고 기대합니다. 순수 함수는 상대 import를 사용합니다.

## 6. 안전 실습

[TypeScript Playground](https://www.typescriptlang.org/play/)의 strict 설정에서 다음 코드만 실행합니다. 저장소 파일은 수정하지 않습니다.

```ts
type Available = 'On' | 'Off'
function parseAvailable(value: unknown): Available | null {
  return value === 'On' || value === 'Off' ? value : null
}

console.assert(parseAvailable('On') === 'On')
console.assert(parseAvailable(false) === null)
console.assert(parseAvailable('on') === null)
const sampleCount: number | null = 0
console.assert((sampleCount ?? 10) === 0)
```

`parseAvailable`의 반환 타입에 `null`을 빼면 strict 검사에 오류가 나야 합니다. 실제 타입 좁히기는 코드를 실행할 때도 잘못된 값에 null을 반환합니다. 입력 뒤에 `as Available`만 붙이는 경우와의 차이를 설명하면 완료입니다.

설치가 완료된 로컬에서는 `frontend/`에서 `npm run typecheck`와 `npm test`를 실행할 수 있습니다. npm test는 Node의 순수 함수 검사이며 Vue 컴포넌트 mount나 브라우저 검사가 아닙니다. `.nuxt/`가 없는 학습 사본에서 typecheck가 실패하면 설정 생성/의존성 상태 문제와 코드 타입 오류를 구분합니다.

## 7. 더 읽을 거리

- [TypeScript Handbook 기본](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html)
- [TypeScript 타입 좁히기](https://www.typescriptlang.org/docs/handbook/2/narrowing.html)
- [TypeScript utility types](https://www.typescriptlang.org/docs/handbook/utility-types.html)
- [Vue 공식 TypeScript 가이드](https://vuejs.org/guide/typescript/overview.html)
- [다음: 타입 소유권 관례](02-type-management-conventions.md)
- [값 없음의 의미](03-null-undefined-false-none-empty-string.md)
