# 08. ESLint 규칙과 코드 스타일

2026-10-03 기준으로 ESLint 설정·타입 검사·테스트·CI를 구분합니다. ESLint는 코드를 실행하기 전에 잠재 오류와 정해진 스타일을 검사하는 도구입니다. 컴파일러나 브라우저 검증을 대체하지 않습니다.

## 1. 기초: 각 검사에 다른 질문을 합니다

| 검사 | 질문 | 명령 위치 |
| --- | --- | --- |
| ESLint | 정적 규칙과 스타일에 맞는가? | frontend: `npm run lint` |
| TypeScript/vue-tsc | 값과 API 타입이 맞는가? | frontend: `npm run typecheck` |
| node:test | 순수 함수의 기대 동작이 맞는가? | frontend: `npm test` |
| Markdown lint | 문서 구조와 표 스타일이 맞는가? | 저장소 루트: `npm run lint:md` |
| 브라우저 확인 | 화면과 실제 상호작용이 맞는가? | 프로젝트 browser-verify 절차 |

`Type string is not assignable to ToolType` 같은 메시지는 보통 타입 검사입니다. 콤마 스타일 메시지와 같은 종류의 오류로 묶지 않습니다. `as ToolType`로 검사만 통과시키는 것보다 입력 guard로 실제 허용 값인지 확인합니다.

## 2. 용어와 버전

flat config는 설정 객체 배열을 순서대로 적용하는 ESLint 구성 방식입니다. `.mjs`는 ESM JavaScript 파일입니다. rule은 검사 하나, severity는 off/warn/error, fix는 자동 수정 가능 여부입니다. warn도 `--max-warnings` 같은 실행 옵션에 따라 실패 조건이 될 수 있습니다.

| 패키지 | 직접 선언 | lock | 확인한 설치본 |
| --- | --- | --- | --- |
| ESLint | `^9.39.2` | 9.39.5 | 9.39.5 |
| `@nuxt/eslint` | `^1.13.0` | 1.16.0 | 1.16.0 |
| TypeScript | `^5.9.3` | 5.9.3 | 5.9.3 |

`@nuxt/eslint`의 버전이 9.39라는 옛 설명은 ESLint 본체와 모듈을 혼동한 것입니다. 근거는 [package.json](../../../frontend/package.json)과 [package-lock.json](../../../frontend/package-lock.json)입니다. [ESLint 9 flat config](https://eslint.org/docs/v9.x/use/configure/configuration-files)를 기준으로 읽습니다.

## 3. 실제 구성

### 3.1 생성 설정과 저장소 설정

[eslint.config.mjs](../../../frontend/eslint.config.mjs)는 생성된 `.nuxt/eslint.config.mjs`의 `withNuxt`를 불러옵니다. 저장소 자체 추가 설정은 ECharts의 vendor UMD 테마 파일 `app/assets/echarts-theme/**`를 ignore합니다. 그대로 보존하는 외부 파일을 프로젝트 스타일로 바꾸지 않기 위한 것입니다. `.nuxt` 설정은 직접 편집하지 않고 Nuxt 설정 또는 withNuxt 인자로 조정합니다.

[nuxt.config.ts](../../../frontend/nuxt.config.ts)는 다음을 명시합니다.

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

객체·배열 마지막 항목 뒤 콤마를 금지하고 여는 중괄호를 같은 줄에 둡니다. 코드의 일반 관례는 2칸 들여쓰기·단일 따옴표·세미콜론 생략입니다. 다만 관찰한 관례와 활성 rule은 구분합니다. import 순서, 함수 선언 스타일, 속성 개수 제한 등을 이 저장소의 확인 없는 강제 규칙으로 선언하지 않습니다.

### 3.2 Vue와 TypeScript를 읽는 예

```vue
<button
  type="button"
  :aria-expanded="!sidebarCollapsed"
  :aria-controls="sidebarNavId"
  @click="sidebarCollapsed = !sidebarCollapsed"
>
  팹 메뉴
</button>
```

`type="button"`은 form 안에서 의도하지 않은 submit을 막습니다. `aria-expanded`는 펼침 상태, `aria-controls`는 연결한 요소의 id를 전달합니다. `v-for`에는 안정적인 key가 필요합니다. 이런 작성 이유를 이해하되 **현재 ESLint가 모든 접근성 누락을 잡는다고 보장하지 않습니다.**

Vue 3는 template의 여러 root를 허용합니다. Vue 2의 `vue/no-multiple-template-root`를 복사해 현재 앱의 필수 규칙이라고 가르치지 않습니다. `any`나 미사용 변수 처리도 생성 설정을 확인합니다. underscore를 붙이면 어떤 rule에서도 면제된다는 일반 규칙은 없습니다.

### 3.3 현재 CI

[ci.yml](../../../.github/workflows/ci.yml)의 frontend job은 Node 24에서 `npm ci` → `npm run typecheck` → `npm test`입니다. **frontend ESLint는 아직 CI gate가 아닙니다.** 기존 untouched 파일의 오류 때문에 의도적으로 빠져 있다는 주석이 있습니다. backend job은 ruff를 먼저 실행한 뒤 pytest를 실행합니다. 문서 검사 명령과 backend lint를 frontend ESLint gate로 혼동하지 않습니다.

## 4. 선택 이유와 한계

ESLint Stylistic과 Nuxt 생성 설정으로 현재 스타일을 처리합니다. 별도 Prettier가 반드시 필요하지는 않지만 이것은 프로젝트 선택이며 Nuxt 전체가 Prettier를 금지하는 관례가 아닙니다. `--fix`는 가능한 규칙만 고치므로 타입 오류·데이터 계약·UI 동작까지 수정하지 않습니다.

에디터 설정은 개인 환경에 의존합니다. `.vscode/settings.json` 파일을 확인하지 않고 저장 시 fix가 구성되어 있다고 주장하지 않습니다. ESLint 9의 flat config는 기본 방식이므로 옛 실험용 `eslint.experimental.useFlatConfig` 설정을 필수로 추가하지 않습니다. 필요하면 [VS Code ESLint 공식 확장 설명](https://github.com/microsoft/vscode-eslint)을 따릅니다.

## 5. 흔한 실수

- frontend lint가 CI에 없으니 로컬 오류도 무시해도 된다고 생각합니다.
- 경고를 없애려고 타입 assertion이나 rule disable을 먼저 추가합니다.
- 루트에서 frontend 명령을 실행하거나 `.nuxt`를 직접 수정합니다.
- `npm run lint -- --fix`를 읽기 전용 검사로 실행합니다. 이 명령은 파일을 바꿉니다.
- 문서 작업 때문에 관련 없는 앱 파일 전체를 자동 수정합니다.

## 6. 안전 실습

먼저 설정을 읽고, 생성 설정과 설치본이 있는 환경에서 읽기 전용 검사를 합니다.

```bash
# 저장소 루트
cat frontend/eslint.config.mjs
rg -n 'stylistic|commaDangle|braceStyle' frontend/nuxt.config.ts
rg -n 'Typecheck|Lint|npm run lint|npm test' .github/workflows/ci.yml

# frontend에서: 파일 변경 없는 검사
npx eslint app/composables/usePersistedState.ts
```

검사 결과의 파일·행·rule id를 읽어 어떤 규칙인지 확인하면 성공입니다. `.nuxt`가 없다면 설치/prepare가 필요한 환경이지 문법 오류라는 결론이 아닙니다. 자동 수정은 별도 작업 공간에서 diff를 검토하는 학습 단계로 남깁니다.

공식 참고는 [Nuxt ESLint 설정](https://eslint.nuxt.com/packages/module), [ESLint 9 CLI](https://eslint.org/docs/v9.x/use/command-line-interface), [Stylistic comma-dangle](https://eslint.style/rules/comma-dangle), [Vue 3 template 기초](https://vuejs.org/guide/essentials/template-syntax.html)입니다.
