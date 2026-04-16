# 08. ESLint 규칙과 코드 스타일

이 프로젝트는 `@nuxt/eslint` 9.39 + flat config (`eslint.config.mjs`) 기반입니다. `npm run lint`로 검사하고 CI에서 강제됩니다.

## 1. 설정 파일 구조

```mjs
// eslint.config.mjs
// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  // Your custom configs here
)
```

`.nuxt/eslint.config.mjs`는 `@nuxt/eslint` 모듈이 자동 생성하는 config이며, `withNuxt(...)`로 그 위에 추가 rule을 얹을 수 있습니다.

`nuxt.config.ts`의 `eslint.config.stylistic` 키가 기본 포매팅을 결정합니다.

```ts
eslint: {
  config: {
    stylistic: {
      commaDangle: 'never',
      braceStyle: '1tbs'
    }
  }
}
```

- `commaDangle: 'never'` — 배열/객체 마지막에 trailing comma 금지.
- `braceStyle: '1tbs'` — one-true-brace-style. `if (...) {` 같은 식으로 `{`를 같은 줄에.

## 2. 코드베이스의 실제 스타일 관찰

실제 코드를 보며 규칙을 역추적해보세요.

### 2.1 따옴표 / 세미콜론

- **문자열 따옴표**: `'single quote'` (백틱은 interpolation 시)
- **세미콜론**: **생략**. Nuxt 커뮤니티 관례.

```ts
const apiBase = import.meta.env.NUXT_PUBLIC_API_BASE || (apiTarget ? '/api' : '/mock-api')
const todayLabel = useState('hub-today-label', () => new Intl.DateTimeFormat('ko-KR', ...))
```

### 2.2 들여쓰기

- **2 spaces**
- 여닫는 괄호가 여러 줄이면 안쪽 콘텐츠 2칸 들여쓰기

### 2.3 객체/배열 리터럴

```ts
// 인라인
const range = { start: 0, end: 100 }

// 여러 줄: 트레일링 콤마 없음
const toolTypes: ToolTypeConfig[] = [
  { id: 'cd-sem', label: 'CD-SEM', count: 0, enabled: true },
  { id: 'hv-sem', label: 'HV-SEM', count: 0, enabled: true },
  { id: 'verity-sem', label: 'VeritySEM', count: 0, enabled: true },
  { id: 'provision', label: 'Provision', count: 0, enabled: true }  // ← trailing comma 없음
]
```

### 2.4 import 순서

관찰된 패턴:

1. 외부 패키지 (`from 'vue'`, `from 'nuxt/app'`)
2. 프로젝트 내부 (`~/stores/...`, `~/mock-data/...`)
3. 가능하면 타입 import를 먼저

```ts
import { useState } from 'nuxt/app'
import { computed, readonly } from 'vue'
// ↓ import type은 가능하면 분리
import type { Fab, ToolType } from '~/stores/navigation'
import type { EbeamToolInventoryResponse, EbeamToolRow } from '~/mock-data/ebeam-tool-inventory/ebeam-tool-inventory'
```

### 2.5 함수 선언

- 컴포저블/외부 export 가능한 것: 화살표 함수 + `const`
- React/Vue 설명 블로그에서 종종 나오는 `function`도 가능하지만, 이 프로젝트는 대체로 화살표 함수 사용

```ts
export const useEbeamToolApi = () => {
  const filterRows = (inventory, toolType, fab = 'all') => { ... }
  return { filterRows }
}

// 예외: store 팩토리 함수는 function declaration
export function useNavigationStore() { ... }
```

### 2.6 Vue template 스타일

- **속성이 2개 이하면 한 줄**, 3개 이상이면 각 속성을 새 줄에

```vue
<!-- 인라인 -->
<UButton icon="i-lucide-search" />

<!-- 여러 줄 -->
<UBadge
  :label="todayLabel"
  color="neutral"
  variant="outline"
  class="w-fit"
/>
```

- **여는 태그 끝은 다음 줄에 `>`** (attribute가 많을 때)
- **셀프 클로징** 가능한 요소는 `<X />`로

### 2.7 v-for에는 반드시 `:key`

Vue 린트가 에러로 잡습니다.

```vue
<NuxtLink v-for="tool in ebeamTools" :key="tool.id" ... />
```

### 2.8 인라인 핸들러 vs 메서드

- 간단한 토글: 인라인 OK
- 로직이 2줄 넘어가면 메서드로

```vue
<!-- 간단 -->
<button @click="sidebarCollapsed = !sidebarCollapsed">

<!-- 메서드 -->
<button @click="navigateToFab(item.id)">
```

## 3. TypeScript 관련 규칙

- `any` 사용 최소화 — `@typescript-eslint/no-explicit-any`
- 명시적 return 타입은 공개 API(export)에만, 내부 함수는 추론 맡김 — `@typescript-eslint/explicit-function-return-type`은 꺼져 있음
- `unused-vars`는 기본 off, `@typescript-eslint/no-unused-vars`가 on

## 4. 접근성 (`aria-*`)

NuxtUI와 기본 ESLint가 접근성 관련 속성을 종종 요구합니다.

```vue
<button
  :aria-expanded="!sidebarCollapsed"
  :aria-label="sidebarCollapsed ? 'Expand FAB sidebar' : 'Collapse FAB sidebar'"
  :aria-controls="sidebarNavId"
  type="button"
>

<nav aria-label="Category navigation">
```

`type="button"`을 명시하지 않으면 form 안에서 submit처럼 동작할 수 있어 린트가 경고합니다.

## 5. 자주 마주치는 린트 에러와 해결

| 에러 | 원인 | 해결 |
|---|---|---|
| `Comma dangle is not allowed` | 배열/객체 끝에 콤마 | 삭제 |
| `Expected indentation of N spaces` | 들여쓰기 불일치 | 2 space 사용 |
| `Missing key in v-for` | `:key` 누락 | `:key="item.id"` 추가 |
| `Unused variable 'x'` | 선언만 하고 미사용 | 삭제 or `_` prefix |
| `Type string is not assignable to ToolType` | 문자열을 좁은 타입에 | `as ToolType` 또는 guard 함수 |
| `Property 'value' missing on type X` | ref의 `.value` 누락 | 추가 |
| `vue/no-multiple-template-root` | template에 root 여러 개 | Vue 3에선 OK여야 함 — NuxtUI v4 + ESLint 조합에서 가끔 나옴. 허용 설정 필요 |

## 6. 린트 자동 수정

```bash
npm run lint -- --fix
```

대부분의 스타일 이슈(들여쓰기, 세미콜론, 콤마)는 `--fix`로 자동 수정됩니다.

## 7. VS Code 통합

`.vscode/settings.json`:

```json
{
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit"
  },
  "eslint.experimental.useFlatConfig": true,
  "editor.formatOnSave": false
}
```

저장 시 ESLint가 자동으로 고쳐줍니다. Prettier는 쓰지 않는 것이 Nuxt 커뮤니티 관례 (ESLint stylistic이 대체).

## 8. 커밋 전 체크리스트

```bash
npm run lint        # 스타일 + 정적 분석
npm run typecheck   # 타입 검사 (vue-tsc)
npm run build       # 빌드까지 통과하는지
```

CI가 `npm ci && npm run lint && npm run typecheck`를 실행하므로 PR 전에 로컬에서 돌려 확인하는 것이 빠릅니다.

## 9. 추가 참고

- ESLint flat config 가이드: https://eslint.org/docs/latest/use/configure/configuration-files-new
- `@nuxt/eslint` 모듈: https://eslint.nuxt.com
- ESLint Stylistic rules: https://eslint.style/

## 10. 한 줄 요약

> "Prettier 없음. 세미콜론 없음. trailing comma 없음. 2 space. 자동 import는 마음껏. `.value` 잊지 말기. `:key` 잊지 말기."
