# 05. Tailwind CSS v4: 화면 배치와 디자인 토큰


CSS는 Cascading Style Sheets(스타일 규칙), HTML은 Hypertext Markup Language(문서 구조), DOM은 Document Object Model(브라우저 문서 객체 구조)입니다. 클래스는 HTML 요소에 붙이는 이름이고 실제 표시 규칙은 CSS가 결정합니다.

## 1. 기초: 작은 CSS 기능을 조합합니다

Tailwind는 `flex`, `gap-4`, `p-4`처럼 한 목적을 가진 CSS 클래스를 제공합니다. `class="flex items-center gap-4"`는 가로 배치, 교차축 정렬, 자식 간격을 한 요소에 적용하는 표현입니다. CSS를 대신하는 언어가 아니라 CSS를 정해진 이름으로 사용하는 도구이므로, flex/grid/box model의 의미를 함께 익혀야 합니다.

**2026-10-03 확인:** [package.json](../../../frontend/package.json)의 `tailwindcss: ^4.1.18`은 허용 범위입니다. [package-lock.json](../../../frontend/package-lock.json)과 원본 `frontend/node_modules/tailwindcss/package.json`은 **4.3.3**입니다. Nuxt UI 4.10.0이 구성하는 `@tailwindcss/vite`도 lock/설치에서 4.3.3입니다. 이 문서는 v4 기준이며 v3 설정을 그대로 복사하지 않습니다.

## 2. 용어와 v3 → v4 변화

| 용어 | 뜻 |
| --- | --- |
| utility | 특정 CSS 기능을 적용하는 클래스입니다. |
| variant | 조건에 따라 utility를 적용합니다. 예: `md:`, `hover:` |
| theme variable | `--color-*`, `--font-*`처럼 utility 생성과 연결되는 변수입니다. |
| CSS custom property | `var(--sk-surface)`처럼 실행 시 읽는 CSS 변수입니다. |
| arbitrary value | `w-[420px]`처럼 미리 이름 없는 값입니다. |
| cascade layer | CSS 우선순위를 묶는 계층입니다. |
| source detection | 파일에서 완전한 클래스 문자열을 찾아 CSS를 생성하는 과정입니다. |

| 주제 | v3의 흔한 구성 | 현재 v4 구성 |
| --- | --- | --- |
| CSS 입력 | `@tailwind` 지시문 | `@import "tailwindcss"` |
| 테마 | JS config의 theme.extend | CSS의 `@theme` |
| Vite 통합 | 구성에 따라 PostCSS 사용 | Nuxt UI 모듈이 Tailwind Vite 플러그인을 등록 |
| 소스 검색 | content 목록 | 자동 검색과 필요 시 `@source` |

v3에서 모든 프로젝트가 반드시 같은 설정을 쓰는 것은 아닙니다. v4도 CSS import만 브라우저에 그대로 보내면 동작하는 것이 아닙니다. **빌드 통합이 그 지시문을 처리**해야 하며 이 프로젝트에서는 기존 Nuxt UI 모듈이 담당합니다.

## 3. 실제 구현: main.css에서 화면까지

### 3.1 CSS 입력과 폰트

[nuxt.config.ts](../../../frontend/nuxt.config.ts)는 `css: ['~/assets/css/main.css']`를 등록합니다. [main.css](../../../frontend/app/assets/css/main.css)는 Tailwind와 Nuxt UI를 import하고 폰트를 등록합니다.

```css
@import "tailwindcss";
@import "@nuxt/ui";

/* 실제 설정의 일부입니다. */
@theme static {
  --font-sans: 'Spoqa Han Sans Neo', 'Public Sans', 'Apple SD Gothic Neo', 'Malgun Gothic', 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;
}
```

`@theme static`은 정의한 테마 변수를 사용 여부와 무관하게 출력하도록 합니다. `--font-sans`는 `font-sans`, `--color-paper-*`는 paper 색 utility와 연결됩니다. 일반 `:root { --sk-surface: ... }` 변수는 단지 CSS 변수이므로 이름 하나만 만들었다고 `bg-sk-surface`가 자동 생성되지는 않습니다.

폰트 파일은 [public/fonts](../../../frontend/public/fonts/)의 woff2를 `/fonts/...` URL로 읽습니다. Public Sans / JetBrains Mono의 출처는 Fontsource 패키지이고 Spoqa 파일의 출처는 CSS 주석에 적혀 있습니다. **`spoqa-han-sans`가 현재 dependency로 설치되어 있다는 뜻은 아닙니다.** 현재 앱은 이미 복사한 정적 파일을 사용합니다. Nuxt UI 자동 폰트 해석은 `ui.fonts: false`로 꺼져 사내 외부 CDN 요청을 피합니다.

Spoqa에는 별도 600 파일이 없으므로 Medium face에 `font-weight: 500 600`을 선언합니다. `font-semibold` 요청을 Medium 파일로 매핑하는 선택이며 진짜 600 굵기의 글꼴이 생기는 것은 아닙니다. `--font-korean`은 한글 폴백 순서를 별도로 지정합니다.

### 3.2 프로젝트 색과 표면

현재 새 화면의 색 기준은 [DESIGN.md](../../../DESIGN.md)와 `--sk-*` 토큰입니다. 일반 Tailwind 색상 문법을 알기 위해 `text-zinc-500`을 읽을 수 있지만, 새 제품 색을 임의의 blue/hex로 추가하는 근거가 되지 않습니다.

```vue
<section class="dashboard-surface p-4">
  <h2 class="sk-heading">장비 목록</h2>
  <p class="text-(--sk-ink-muted)">조회한 결과를 표시합니다.</p>
</section>
```

`text-(--sk-ink-muted)`는 v4의 CSS 변수 단축 표현이며 `text-[var(--sk-ink-muted)]`와 같은 용도로 읽습니다. `bg-(--sk-surface)`, `border-(--sk-border)`도 같은 방식입니다. `.dashboard-surface`는 현재 토큰 배경과 테두리, 부드러운 shadow입니다. 예전의 반투명/blur 카드 설명은 맞지 않습니다.

`sk-value`, `sk-value-num`, `sk-meta`, `sk-heading`은 글자 역할을 묶습니다. 데이터 값과 라벨은 읽기 크기가 다릅니다. 화면마다 `text-[10px]`로 값을 줄이지 않고 기존 역할 클래스를 먼저 확인합니다.

### 3.3 레이아웃과 크기 utility

| 클래스 | CSS 의미 |
| --- | --- |
| `flex`, `inline-flex` | flex layout을 시작합니다. |
| `flex-col` | 주축을 세로로 둡니다. |
| `items-center` | 교차축 중심 정렬입니다. |
| `justify-between` | 주축의 양끝으로 공간을 나눕니다. |
| `grid`, `grid-cols-2` | grid와 두 열을 만듭니다. |
| `gap-4` | 기본 spacing 기준 1rem 간격입니다. |
| `p-4`, `px-4`, `py-3` | 전체 / 좌우 / 위아래 padding입니다. |
| `w-full`, `min-w-0` | 전체 너비 / 최소 너비 제한 해제입니다. |
| `flex-1`, `min-h-0` | 남은 공간 사용 / flex 자식의 넘침 제어입니다. |
| `size-4` | width와 height를 함께 지정합니다. |
| `hidden` | `display: none`입니다. |

기본 `--spacing`은 0.25rem이며 `p-4`는 1rem입니다. 1rem=16px인 브라우저 기본 설정에서 16px이고, 사용자가 루트 글자 크기를 바꾸면 px 값도 달라집니다. “1은 언제나 4px”이라고 외우면 안 됩니다.

[ToolInventoryView.vue](../../../frontend/app/components/ebeam/ToolInventoryView.vue)의 `flex flex-col ... h-full min-h-0`는 제한된 높이 안에서 도구 영역과 표를 배치하는 데 사용됩니다. `min-h-0`는 장식이 아니라 flex 자식이 내용의 최소 높이 때문에 바깥으로 밀려나는 문제를 제어합니다.

### 3.4 반응형과 상태 variant

```html
<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
  <!-- 작은 화면은 1열, md 이상은 2열입니다. -->
</div>
```

prefix 없는 utility가 기본이고 `md:`는 기본 breakpoint 48rem 이상에서 적용됩니다. 기본값은 `sm` 40rem, `md` 48rem, `lg` 64rem, `xl` 80rem, `2xl` 96rem입니다. 이는 16px 기준 640/768/1024/1280/1536px이며 테마가 breakpoint를 바꾸면 달라집니다. `sm:`는 “모바일만”이 아니라 그 이상입니다.

`hover:`는 포인터 상태, `focus-visible:`은 키보드 등으로 드러나는 focus, `disabled:`는 비활성 상태에 적용됩니다. 입력이나 버튼에서 focus 표시를 지우면 안 됩니다. `group-hover:`는 상위 `group` 상태를 사용합니다.

Tailwind 자체의 dark variant 기본은 시스템 선호와 연결될 수 있습니다. **이 앱은 Nuxt UI/color-mode 통합으로 `.dark` 클래스 전환을 사용**하며 토큰도 `.dark`에서 바뀝니다. 이를 Tailwind의 모든 설치에 적용되는 기본이라고 일반화하지 않습니다.

### 3.5 Vue 동적 class와 정적 문자열

[SegmentedToggle.vue](../../../frontend/app/components/sk/SegmentedToggle.vue)의 실제 패턴입니다.

```vue
<button
  class="px-2.5 py-1 font-mono text-xs"
  :class="active
    ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
    : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
>
  선택
</button>
```

위 예시의 `active`는 설명용 boolean입니다. 실제 파일은 `item.value === modelValue`를 사용합니다. `class`는 공통 스타일, `:class`는 Vue가 계산하는 조건부 스타일입니다. 문자열 전체가 소스에 있으므로 Tailwind가 찾을 수 있습니다.

```ts
// 학습 예시: 클래스 전체 문자열을 보관합니다.
const tones = {
  normal: 'text-(--sk-ink)',
  muted: 'text-(--sk-ink-muted)'
}
```

`'text-' + color + '-500'`처럼 실행 중 조합한 클래스는 Tailwind가 자동 추론하지 않습니다. 존재하는 전체 문자열을 매핑하거나 필요한 경우 CSS 변수 / 명시적 source 정책을 사용합니다. [소스 검색 공식 설명](https://tailwindcss.com/docs/detecting-classes-in-source-files)을 확인합니다.

### 3.6 CSS 우선순위, arbitrary value와 @apply

`w-[420px]`, `tracking-[0.18em]`은 유효한 arbitrary value입니다. 그러나 `bg-[#FF5733]`가 문법상 가능하다고 프로젝트의 토큰 규칙까지 허용하는 것은 아닙니다. 크기도 기존 radius 역할 토큰을 먼저 사용합니다.

Nuxt UI의 `ui` prop은 내부 파트 조정에 사용합니다. 일반 `class` 목록에서 뒤에 쓴 utility가 무조건 승리한다는 규칙은 없습니다. 생성된 CSS 순서, specificity, layer와 라이브러리의 class 병합이 결정합니다. main.css의 역할 클래스는 `@layer components` 안에 두어 utility 조정이 이길 수 있게 하고, 일부 chrome 규칙은 의도적으로 layer 밖에 둡니다.

SFC `<style scoped>`에서 Tailwind v4의 `@apply`를 사용할 때는 별도 CSS 처리 맥락에 테마를 알려야 할 수 있습니다.

```vue
<!-- components/ 바로 아래에 있는 학습용 파일 기준 경로입니다. -->
<style scoped>
@reference "../assets/css/main.css";

.panel {
  @apply flex items-center gap-4;
}
</style>
```

`@reference`는 CSS를 다시 출력하지 않고 테마/utility 정보를 참조합니다. 실제 파일 위치에 맞게 경로를 바꿔야 합니다. 단순 스타일은 template utility나 일반 CSS로 충분하며, 기존 프로젝트가 @apply를 요구하는 것은 아닙니다. [v4 마이그레이션의 Vue 관련 설명](https://tailwindcss.com/docs/upgrade-guide#using-apply-with-vue-svelte-or-css-modules)을 확인합니다.

`@tailwindcss/typography`는 현재 package 선언, lock, 설치에서 없습니다. `prose`를 클래스 하나만 추가한다고 typography 플러그인이 생기지 않습니다. 필요가 확인되기 전에는 설치하지 않습니다. IntelliSense는 에디터 편의이며 빌드 동작과 별개입니다. 일반 Vue class 인식을 위해 오래된 실험 `classRegex` 설정을 무조건 추가할 필요는 없습니다.

## 4. 선택 이유와 한계

Tailwind는 간격과 배치 같은 반복 표현을 짧게 만들고 Nuxt UI와 잘 연결됩니다. 의미 있는 색과 글자 역할은 custom CSS 토큰과 역할 클래스로 유지합니다. 긴 class 목록을 줄이기 위해 모든 요소를 새 컴포넌트로 감쌀 필요는 없지만, 반복되는 역할이 이미 존재하면 재사용합니다.

유틸리티를 알아도 화면이 좁아질 때 넘침, 표의 읽기 크기, contrast, focus, motion을 자동으로 검증하지는 않습니다. CSS 문법 검사와 실제 브라우저 결과를 구분합니다.

## 5. 흔한 실수

1. v3의 config/content/PostCSS 튜토리얼을 현재 구성에 추가합니다. 기존 모듈 통합을 먼저 봅니다.
2. CSS 변수를 만들면 이름이 같은 utility도 생긴다고 생각합니다. `@theme`와 일반 변수의 차이를 확인합니다.
3. 런타임 문자열 조합이 CSS 생성기에 보인다고 기대합니다. 완전한 클래스 문자열을 사용합니다.
4. `sm:`를 좁은 화면 전용으로 읽습니다. 최소 너비 조건입니다.
5. class 순서만 바꾸어 우선순위를 고치려 합니다. computed style과 CSS layer를 확인합니다.
6. 토큰 대신 새 hex와 작은 글자 크기를 추가합니다. DESIGN 기준을 유지합니다.

## 6. 안전 실습

첫 단계는 저장소 루트에서 파일을 읽는 것입니다.

```bash
rg -n '@import|@theme|--font-|dashboard-surface' frontend/app/assets/css/main.css
rg -n 'flex|min-h-0|:class=' frontend/app/components/ebeam/ToolInventoryView.vue
rg -n 'modelValue|text-\(|bg-\(' frontend/app/components/sk/SegmentedToggle.vue
```

두 번째 단계는 개인 학습 HTML이나 [Tailwind Play](https://play.tailwindcss.com/)에서 `grid-cols-1 md:grid-cols-2`를 비교하는 것입니다. 온라인 도구는 사내 배포 경로가 아닙니다. 너비를 경계 전후로 바꾸고 열 개수가 바뀌는지 확인합니다. 프로젝트의 `--sk-*`는 일반 Playground에 없으므로 토큰 없는 화면에서 색이 보이지 않는 것을 Tailwind 버그로 오해하지 않습니다.

완료 기준은 `p-4`를 rem으로 설명하고, utility와 역할 클래스의 책임을 구분하며, 현재 표면이 blur 카드가 아니라고 확인하는 것입니다. 운영 디자인이나 패키지 설정은 이 실습에서 바꾸지 않습니다.

## 7. 공식 근거

- [Tailwind theme variables](https://tailwindcss.com/docs/theme)
- [Tailwind source detection](https://tailwindcss.com/docs/detecting-classes-in-source-files)
- [Tailwind responsive design](https://tailwindcss.com/docs/responsive-design)
- [Tailwind dark mode](https://tailwindcss.com/docs/dark-mode)
- [Tailwind v4 upgrade guide](https://tailwindcss.com/docs/upgrade-guide)
- [다음: Vite 설정](../06-vite-config/README.md)
