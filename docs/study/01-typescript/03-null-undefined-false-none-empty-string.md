# 03. `null`, `undefined`, `false`, `None`, `""`

이 주제는 매우 중요합니다. 이 값들은 개념적으로 자주 섞여서 사용되지만, 실제 의미는 서로 같지 않기 때문입니다.

TypeScript와 JavaScript에서 핵심 질문은 보통 다음과 같습니다.

"이 값이 없는 것인가, 의도적으로 비어 있는 것인가, 비활성 상태인가, 아니면 단순히 falsy인가?"

이것들은 서로 다른 의미이며, 대부분의 경우 타입 모델도 다르게 잡아야 합니다.

## 짧은 요약

| 값 | 언어 | 의미 |
| --- | --- | --- |
| `undefined` | JavaScript / TypeScript | 아직 전달되지 않았거나, 할당되지 않았거나, 누락된 값입니다. |
| `null` | JavaScript / TypeScript | 의도적으로 비워 두었거나, 명시적으로 값이 없음을 뜻합니다. |
| `false` | JavaScript / TypeScript / Python | 불리언 거짓 값입니다. |
| `None` | Python | 값이 없음을 나타내는 객체입니다. |
| `""` | JavaScript / TypeScript / Python | 빈 문자열이지만, 여전히 문자열 값입니다. |

## 가장 중요한 구분

이 값들은 서로 바꿔 쓸 수 없습니다.

- `undefined`는 값이 없거나 빠졌음을 뜻합니다.
- `null`은 명시적으로 비어 있음을 뜻합니다.
- `false`는 실제 불리언 값입니다.
- `""`는 실제 문자열 값입니다.

즉, 다음과 같은 사고방식은 잘못된 경우가 많습니다.

- "`false`는 값이 없다는 뜻이다"
- "`""`는 null이다"
- "`undefined`와 `null`은 완전히 같다"

이 값들은 조건식에서 모두 falsy처럼 동작할 수 있지만, 의미적으로는 서로 다릅니다.

## 1. `undefined`

JavaScript와 TypeScript에서 `undefined`는 보통 다음 뜻으로 쓰입니다.

- 값이 한 번도 할당되지 않았습니다.
- 함수 인자가 생략되었습니다.
- 객체 속성이 존재하지 않습니다.
- 함수가 아무것도 반환하지 않았습니다.

예시는 다음과 같습니다.

```ts
let a: string | undefined
console.log(a) // undefined

function greet(name?: string) {
  return name
}

console.log(greet()) // undefined
```

일반적인 해석은 다음과 같습니다.

- "전달되지 않았습니다"
- "아직 설정되지 않았습니다"
- "누락되었습니다"

TypeScript에서는 선택적 값(optional value)의 기본 표현으로 `undefined`를 쓰는 경우가 많습니다.

예시는 다음과 같습니다.

```ts
interface User {
  nickname?: string
}
```

여기서 `nickname?: string`은 실질적으로 다음과 비슷한 의미입니다.

```ts
nickname: string | undefined
```

## 2. `null`

`null`은 보통 다음 의미를 가집니다.

- 값을 의도적으로 비워 두었습니다.
- 프로그램이 "여기에는 객체가 없습니다"를 표현하려고 합니다.

예시는 다음과 같습니다.

```ts
let selectedTool: string | null = null
```

일반적인 해석은 다음과 같습니다.

- "확인해 봤지만 결과가 없습니다"
- "현재 선택을 의도적으로 지웠습니다"

관례적으로는 다음과 같이 구분하는 편이 좋습니다.

- 빠졌거나 누락된 값에는 `undefined`를 사용합니다.
- 코드가 명시적으로 빈 상태를 전달하고 싶을 때는 `null`을 사용합니다.

예시는 다음과 같습니다.

```ts
function findTool(id: string): string | null {
  return id === 'cd-sem' ? 'CD-SEM' : null
}
```

이 함수는 단순히 `undefined`를 반환하는 것보다 더 많은 정보를 줍니다. 의도적으로 "일치하는 항목이 없습니다"를 반환하기 때문입니다.

## 3. `false`

`false`는 "비어 있음"이 아닙니다. `false`는 유효한 불리언 값입니다.

예시는 다음과 같습니다.

```ts
const enabled: boolean = false
const isOnline: boolean = false
```

의미는 다음과 같습니다.

- 답이 아니오입니다.
- 플래그가 꺼져 있습니다.
- 조건이 만족되지 않았습니다.

이것은 `undefined`와 매우 다릅니다.

예시는 다음과 같습니다.

```ts
type Example = {
  enabled?: boolean
}
```

가능한 해석은 다음과 같습니다.

- `enabled === true`: 명시적으로 활성화되었습니다.
- `enabled === false`: 명시적으로 비활성화되었습니다.
- `enabled === undefined`: 설정되지 않았습니다.

이 구분은 UI 설정, 필터, 기능 플래그에서 자주 중요합니다.

## 4. Python `None`

Python의 `None`은 의미상 다음 값과 가장 가깝습니다.

- `null`
- 경우에 따라서는 `undefined`

다만 둘과 완전히 1:1로 대응되지는 않습니다.

Python에는 대표적인 "값 없음" 객체가 하나 있습니다.

```py
value = None
```

반면 JavaScript는 이 개념을 보통 두 가지 의미로 나눕니다.

- `undefined`: 누락됨 / 생략됨
- `null`: 명시적으로 비어 있음

따라서 Python에 익숙하다면 다음처럼 이해하면 편합니다.

- Python의 `None`은 대략 TypeScript의 `null | undefined`와 비슷합니다.
- 실제 코드에서는 의도에 따라 둘 중 더 정확한 쪽을 선택하면 됩니다.

## 5. `""` 빈 문자열

`""`는 `null`도 아니고 `undefined`도 아닙니다.

길이가 `0`인 실제 문자열 값입니다.

예시는 다음과 같습니다.

```ts
const name = ''
console.log(typeof name) // "string"
console.log(name.length) // 0
```

의미는 다음과 같습니다.

- 값은 존재합니다.
- 텍스트입니다.
- 다만 텍스트 내용이 비어 있습니다.

이것이 중요한 이유는, 빈 문자열이 보통 다음 뜻으로 쓰이기 때문입니다.

- 사용자가 빈 입력을 제출했습니다.
- 백엔드가 빈 텍스트 필드를 반환했습니다.
- 값이 누락된 것이 아니라, 의도적으로 빈 텍스트입니다.

## Falsy 동작은 오해를 만들 수 있습니다

JavaScript에서 다음 값들은 모두 falsy입니다.

- `false`
- `0`
- `""`
- `null`
- `undefined`
- `NaN`

그래서 다음과 같은 체크는:

```ts
if (!value) {
  // ...
}
```

다음 상태를 구분하지 못합니다.

- 값이 누락된 상태
- 빈 문자열
- 불리언 false
- 숫자 0

그래서 넓은 범위의 falsy 체크는 보통 너무 느슨합니다.

## 더 나은 체크 방법

### 누락 여부만 확인하기

```ts
if (value == null) {
  // null과 undefined를 함께 잡습니다.
}
```

이 경우는 느슨한 동등 비교를 의도적으로 쓰는 몇 안 되는 예입니다.

이 의미는 다음과 같습니다.

- `value === null || value === undefined`

### `undefined`만 확인하기

```ts
if (value === undefined) {
  // 생략되었거나 아직 할당되지 않았습니다.
}
```

### `null`만 확인하기

```ts
if (value === null) {
  // 명시적으로 비어 있습니다.
}
```

### 빈 문자열만 확인하기

```ts
if (value === '') {
  // 빈 텍스트입니다.
}
```

### 불리언 false만 확인하기

```ts
if (value === false) {
  // 명시적인 아니오 상태입니다.
}
```

## Optional chaining과 nullish coalescing

이 연산자들은 모든 falsy 값을 기준으로 동작하는 것이 아니라, `null`과 `undefined`를 기준으로 설계되어 있습니다.

### `?.`

```ts
const name = user?.profile?.name
```

이 연산은 왼쪽 값이 `null` 또는 `undefined`일 때만 멈춥니다.

### `??`

```ts
const label = input ?? 'default'
```

이 연산은 `input`이 `null` 또는 `undefined`일 때만 `'default'`를 사용합니다.

중요한 예시는 다음과 같습니다.

```ts
const a = '' || 'fallback'   // "fallback"
const b = '' ?? 'fallback'   // ""

const c = false || true      // true
const d = false ?? true      // false
```

정리하면 다음과 같습니다.

- `||`는 많은 falsy 값을 "없음"처럼 취급합니다.
- `??`는 `null`과 `undefined`만 "없음"처럼 취급합니다.

TypeScript 코드에서는 `false`, `0`, `""`가 유효한 값일 수 있다면 `??`가 더 안전한 선택인 경우가 많습니다.

## 권장 관례

코드를 읽기 쉽게 유지하려면 다음과 같은 관례가 실용적입니다.

### 선택 필드에는 `undefined`를 사용합니다

```ts
interface Filters {
  fab?: string
}
```

의미는 다음과 같습니다.

- fab 필터가 전달되지 않았습니다.

### 의도적인 "선택 없음"에는 `null`을 사용합니다

```ts
const selectedFab: string | null = null
```

의미는 다음과 같습니다.

- UI에 현재 선택된 항목이 의도적으로 없습니다.

### `false`는 오직 불리언에만 사용합니다

```ts
const hasAlerts = false
```

의미는 다음과 같습니다.

- 알림이 없습니다.

다음 의미로 쓰면 안 됩니다.

- "알림 데이터가 누락되었습니다"

### 빈 텍스트가 유효한 상태일 때만 `""`를 사용합니다

```ts
const searchText = ''
```

의미는 다음과 같습니다.

- 사용자 입력은 존재하지만 현재 빈 상태입니다.

만약 "검색어가 아직 초기화되지 않았습니다"를 뜻하고 싶다면, 보통 `undefined`나 `null`이 더 명확합니다.

## 프론트엔드 코드에서의 예시

### 폼 입력

```ts
type FormState = {
  keyword: string
  description?: string
  selectedTool: string | null
  includeOffline: boolean
}
```

해석은 다음과 같습니다.

- `keyword: ''`는 빈 텍스트 박스를 뜻합니다.
- `description: undefined`는 선택 필드가 제공되지 않았다는 뜻입니다.
- `selectedTool: null`은 현재 선택이 없다는 뜻입니다.
- `includeOffline: false`는 명시적으로 꺼 두었다는 뜻입니다.

### API 결과

```ts
type ApiResult = {
  message: string
  detail: string | null
}
```

해석은 다음과 같습니다.

- `detail: null`은 API가 명시적으로 상세 정보가 없다고 말하는 상태입니다.
- `detail: ''`는 상세 정보 필드는 존재하지만 텍스트가 비어 있다는 뜻입니다.

## 자주 하는 실수

### 실수 1. `""`나 `false`가 유효한데 `||`를 쓰는 경우

```ts
const label = value || 'default'
```

`value`가 `''` 또는 `false`일 수 있다면 잘못된 결과가 나올 수 있습니다.

더 안전한 방식은 다음과 같습니다.

```ts
const label = value ?? 'default'
```

### 실수 2. `false`를 누락값처럼 다루는 경우

```ts
if (!config.enabled) {
  // false일 수도 있고
  // undefined일 수도 있습니다.
}
```

이 차이가 중요하다면 더 정확하게 검사해야 합니다.

### 실수 3. 기준 없이 `null`과 `undefined`를 섞어 쓰는 경우

같은 의미에 대해 코드베이스가 `null`과 `undefined`를 무작위로 섞어 쓰면, 코드를 추론하기가 어려워집니다.

명확한 규칙을 정하는 편이 좋습니다.

- optional / omitted -> `undefined`
- explicit empty -> `null`

## 짧은 답

다음 의미를 일관되게 사용하면 됩니다.

- `undefined`: 누락되었거나 전달되지 않았습니다.
- `null`: 의도적으로 값이 없습니다.
- `false`: 명시적인 불리언 거짓입니다.
- `None`: Python의 값 없음 객체이며, 대략 `null | undefined`에 가깝습니다.
- `""`: 빈 텍스트이지만 여전히 문자열입니다.

코드에서 이 상태들을 구분해야 한다면, `if (!value)` 같은 넓은 falsy 체크에 의존하면 안 됩니다.
