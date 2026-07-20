# 05. Tailwind CSS v4

Tailwind는 **유틸리티 CSS 프레임워크**입니다. `btn-primary` 같은 커스텀 클래스를 만드는 대신, `bg-blue-600 text-white rounded-lg px-4 py-2 hover:bg-blue-700` 같은 단일 목적 유틸리티를 조합해서 스타일링합니다.

이 프로젝트는 **Tailwind v4**를 사용합니다 — v3와 설정 방식이 크게 달라졌으니 v3 튜토리얼을 볼 땐 주의하세요.

## 1. v4의 핵심 변화

| 이슈 | v3 | v4 |
| --- | --- | --- |
| 설정 파일 | `tailwind.config.js` 필요 | CSS에 직접 `@theme` 선언 가능 |
| import 방식 | `@tailwind base/components/utilities` | `@import "tailwindcss"` 한 줄 |
| PostCSS 설정 | postcss.config 필요 | Vite 플러그인에서 바로 처리 |
| 테마 변수 | `theme.extend.colors` | CSS variable 직접 정의 |

이 프로젝트의 설정은 `nuxt.config.ts`의 `css: ['~/assets/css/main.css']` 한 줄과 `main.css`의 `@import "tailwindcss"` 한 줄로 끝납니다.

## 2. `main.css` 해석

```css
@import "tailwindcss";         /* Tailwind의 base + components + utilities */
@import "@nuxt/ui";            /* NuxtUI의 테마 */

/* 폰트는 외부 CDN이 아니라 self-host woff2를 @font-face로 직접 등록 */
@font-face {
  font-family: 'Spoqa Han Sans Neo';
  src: url('...Bold.woff2') format('woff2');
  font-weight: 700;
}
/* ... Regular(400)/Medium(500) 등 weight별로 반복 ... */

@theme {
  --font-sans: 'Spoqa Han Sans Neo', 'Public Sans', 'Apple SD Gothic Neo', 'Malgun Gothic', 'Segoe UI', sans-serif;
  --font-korean: 'Spoqa Han Sans Neo', 'Apple SD Gothic Neo', 'Malgun Gothic', 'Segoe UI', sans-serif;
  --color-zinc-50: #FAFAFA;
  ...
}
```

- `@theme` 블록은 Tailwind v4의 테마 확장 문법입니다. 선언된 CSS 변수는 모든 유틸리티에 자동 반영됩니다.
- `--color-zinc-500`을 여기서 정의했다면 `bg-zinc-500`, `text-zinc-500`, `border-zinc-500` 등이 모두 해당 색을 사용합니다.

### 폰트 설정의 배경 (중요한 학습 포인트)

기본 sans 폰트는 **Spoqa Han Sans Neo**입니다(예전 Noto Sans KR을 대체). Latin 보조로 Public Sans, 모노스페이스는 JetBrains Mono를 씁니다. 세 가지 실전 결정이 있습니다.

1. **CDN이 아니라 self-host.** 폰트는 `@fontsource/*` npm 패키지(woff2)와 `spoqa-han-sans` 패키지의 subset woff2를 `@font-face`로 직접 등록합니다. `nuxt.config.ts`의 `ui: { fonts: false }`로 NuxtUI/`@nuxt/fonts`의 **자동 폰트 해석을 꺼서** 빌드·개발 시점에 Google Fonts·Fontshare 같은 외부 CDN에 접속하지 않게 합니다. 이유: 사내 폐쇄망(오프라인)에서 돌아가야 하기 때문. (`06-vite-config/`의 `ui.fonts` 절 참고.)
2. **Spoqa Han Sans Neo에는 SemiBold(600)가 없습니다.** 그래서 Medium(500) `@font-face`의 `font-weight` 범위를 `500 600`으로 지정해, `font-semibold`(600)를 요청해도 Medium이 커버하도록 했습니다. weight가 없는 폰트를 억지로 굵게(가짜 볼드) 렌더링하는 것을 막는 트릭입니다.
3. **`--font-korean` 별도 정의.** 한글 전용 스택을 따로 두어, Latin 위주 컴포넌트와 한글 위주 화면의 폴백 순서를 다르게 제어할 수 있습니다.

## 3. 자주 쓰이는 유틸리티 범주

### 3.1 레이아웃

```text
flex            display: flex
grid            display: grid
block           display: block
hidden          display: none
inline-flex     display: inline-flex

flex-col        flex-direction: column
flex-row
items-center    align-items: center
justify-between justify-content: space-between
gap-4           gap: 1rem
space-y-6       자식 요소 사이 수직 간격
```

### 3.2 Grid

```text
grid md:grid-cols-2            모바일 1열, md부터 2열
grid md:grid-cols-3 gap-4
grid gap-4 md:grid-cols-4
```

### 3.3 Sizing / Spacing

단위는 1 = 0.25rem = 4px.

```text
p-4             padding: 1rem
px-4 py-3       padding-x: 1rem / padding-y: 0.75rem
m-2             margin
mb-4            margin-bottom
w-5 h-5         width/height (1.25rem)
w-full          100%
max-w-7xl       max-width: 80rem
min-h-screen    min-height: 100vh
size-4          = w-4 h-4
```

### 3.4 색상

팔레트: `zinc`, `gray`, `slate`, `neutral`, `red`, `orange`, `yellow`, `green`, `blue`, `indigo`, `purple`, `pink` — 각 팔레트는 50~950의 수치 scale이 있습니다.

```text
bg-zinc-900         배경
text-zinc-100       글자
border-zinc-200     테두리
dark:bg-zinc-900    다크 모드일 때 적용 (.dark 클래스 기반)
```

### 3.5 타이포그래피

```text
text-xs text-sm text-base text-lg text-xl text-2xl text-3xl
font-medium font-semibold font-bold
tracking-tight tracking-[0.18em]   <!-- 임의의 값 -->
uppercase lowercase capitalize
leading-tight
```

### 3.6 border / radius / shadow

```text
border border-2 border-t border-zinc-200
rounded rounded-xl rounded-2xl rounded-3xl rounded-full
shadow shadow-sm shadow-md shadow-xl
```

### 3.7 상호작용(hover, focus, ...)

```text
hover:bg-zinc-100
hover:text-zinc-900
focus:ring-2 focus:ring-primary-500
group-hover:text-zinc-800   <!-- 부모 .group이 hover일 때 -->
```

### 3.8 반응형 prefix

- 기본(모바일)
- `sm:` — 640px
- `md:` — 768px
- `lg:` — 1024px
- `xl:` — 1280px
- `2xl:` — 1536px

모바일 퍼스트 — prefix 없는 게 가장 작은 화면 기본입니다.

```html
<h1 class="text-2xl md:text-3xl">  <!-- 모바일 2xl, md 이상 3xl -->
```

### 3.9 다크 모드

`.dark` 클래스를 상위 요소(보통 `<html>`)에 붙이면 `dark:*` 유틸리티가 활성화됩니다. NuxtUI의 `<UColorModeButton>`이 자동 처리합니다.

```text
text-zinc-900 dark:text-zinc-100
bg-white dark:bg-zinc-900
```

## 4. 프로젝트 코드의 Tailwind 패턴 읽기

### 4.1 기본 카드

```vue
<UCard class="dashboard-surface rounded-2xl">
```

- `dashboard-surface` — 프로젝트 고유 클래스(배경 + blur + border + shadow)
- `rounded-2xl` — 큰 radius

### 4.2 반응형 헤더

```vue
<section class="dashboard-surface rounded-3xl p-6 md:p-8">
  <div class="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
    <h1 class="text-2xl md:text-3xl font-semibold tracking-tight">
```

- 모바일에선 세로 배치(`flex-col`), md 이상에서 가로 배치(`md:flex-row`)
- 폰트 크기도 단계별로 커짐

### 4.3 동적 클래스 (Vue 문법과 결합)

```vue
<button
  class="px-4 py-1.5 text-sm font-medium rounded-lg transition-all duration-200"
  :class="category === cat.id
    ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
    : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200'"
>
```

- 항상 적용되는 클래스는 `class`에
- 조건부는 `:class`(삼항 또는 배열/객체)에
- 하나의 요소에 두 prop 모두 가능

### 4.4 그리드 카드

```vue
<div class="grid md:grid-cols-2 gap-6">
<div class="grid gap-4 md:grid-cols-4">
<div class="grid gap-4 md:grid-cols-3">
```

모바일 1열, md부터 N열. 디자인 리사이즈가 자동입니다.

### 4.5 텍스트 계층

```vue
<p class="text-xs uppercase tracking-[0.18em] text-zinc-500 font-semibold mb-2">
  Operations Overview
</p>
<h1 class="text-2xl md:text-3xl font-semibold tracking-tight">
  Metrology Control Center
</h1>
<p class="text-sm text-zinc-600 mt-2">
  Unified monitoring and diagnostics ...
</p>
```

작은 대문자 태그 → 큰 제목 → 작은 설명. 이 패턴은 대시보드 섹션 헤더에 계속 반복되니 익혀두세요.

## 5. Arbitrary values (`[...]`)

Tailwind가 기본 제공하지 않는 값은 대괄호로 넣습니다.

```text
tracking-[0.18em]     letter-spacing: 0.18em
text-[11px]
bg-[#FF5733]
w-[420px]
```

## 6. @apply (SFC `<style>` 내부)

컴포넌트 파일에서 Tailwind 유틸리티를 묶어 재사용할 때. 이 프로젝트는 거의 안 쓰지만 참고.

```vue
<style scoped>
.card-header {
  @apply flex items-center justify-between mb-4;
}
</style>
```

v4에서는 `@apply`보다 **Tailwind 유틸리티 클래스를 템플릿에 그대로 쓰는 쪽**이 권장됩니다.

## 7. `prose` / typography 플러그인

이 프로젝트에는 없지만, 글이 많은 페이지(블로그/문서)에서는 `@tailwindcss/typography`의 `prose` 클래스를 자주 씁니다.

## 8. 자동 완성 설정 팁

VS Code 확장: **Tailwind CSS IntelliSense**. 설치하면 클래스 자동완성 + 현재 적용되는 CSS를 툴팁으로 볼 수 있습니다.

`.vscode/settings.json` 권장:

```json
{
  "tailwindCSS.experimental.classRegex": [
    ["class=\"([^\"]*)\"", ""]
  ]
}
```

## 9. 참고

- Tailwind v4 공식: https://tailwindcss.com/docs
- Tailwind Play (브라우저 실험): https://play.tailwindcss.com
- Cheatsheet: https://nerdcave.com/tailwind-cheat-sheet
