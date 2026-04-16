# 04. NuxtUI 컴포넌트 가이드

[NuxtUI v4](https://ui.nuxt.com)는 Tailwind CSS v4 위에 얹힌 사전 제작 컴포넌트 라이브러리입니다. 이 프로젝트에서는 `@nuxt/ui` 모듈을 등록해서 모든 `U*` prefix 컴포넌트를 전역에서 사용합니다.

## 1. 설치와 등록

`package.json`:

```json
"dependencies": {
  "@nuxt/ui": "^4.6.1",
  "tailwindcss": "^4.1.18"
}
```

`nuxt.config.ts`:

```ts
modules: ['@nuxt/eslint', '@nuxt/ui'],
css: ['~/assets/css/main.css']
```

`app/assets/css/main.css`:

```css
@import "tailwindcss";
@import "@nuxt/ui";
```

이것만 하면 NuxtUI 컴포넌트(`<UButton>`, `<UCard>`, ...)와 Tailwind 유틸리티(`bg-zinc-900`, `rounded-2xl` 등)가 모두 활성화됩니다.

## 2. 최상위 래퍼: `<UApp>`

```vue
<!-- app.vue -->
<UApp>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</UApp>
```

`UApp`은 NuxtUI의 Toast, Modal, ConfirmDialog 등의 전역 컨테이너를 깔아줍니다. 모든 페이지 밖에 한 번만 두면 됩니다.

## 3. 이 프로젝트에서 실제로 쓰이는 컴포넌트

### 3.1 `<UHeader>`

상단 헤더 레이아웃. `#left`, `#right` slot을 제공합니다.

```vue
<UHeader class="dashboard-surface border-b ...">
  <template #left>
    <NuxtLink to="/">
      <AppLogo />
    </NuxtLink>
  </template>

  <template #right>
    <UButton icon="i-lucide-search" color="neutral" variant="ghost" />
    <UButton to="/settings" icon="i-lucide-settings" color="neutral" variant="ghost" />
    <UColorModeButton />
  </template>
</UHeader>
```

### 3.2 `<UButton>`

```vue
<UButton
  icon="i-lucide-search"        <!-- Iconify 아이콘 -->
  color="neutral"               <!-- primary / neutral / success / ... -->
  variant="ghost"               <!-- solid / soft / subtle / outline / ghost / link -->
  aria-label="Search"
/>
<UButton to="/settings" ...>   <!-- to 넣으면 NuxtLink처럼 동작 -->
```

color, variant, size의 조합으로 스타일이 결정됩니다. 자세한 props는 https://ui.nuxt.com/docs/components/button 참고.

### 3.3 `<UCard>`

```vue
<UCard
  class="dashboard-surface rounded-2xl"
  :ui="{ body: 'p-6' }"          <!-- 내부 섹션별 클래스 override -->
>
  <template #header>
    <!-- 헤더 slot -->
  </template>

  <!-- 기본 slot은 body -->
  <div>Content</div>

  <template #footer>
    <!-- 푸터 slot -->
  </template>
</UCard>
```

`:ui="{...}"` 패턴은 NuxtUI 전반에서 쓰입니다. 각 컴포넌트마다 내부 "파트"의 이름이 정해져 있고, 해당 키로 클래스를 override할 수 있습니다.

### 3.4 `<UBadge>`

작은 라벨.

```vue
<UBadge
  :label="todayLabel"            <!-- 또는 기본 slot에 직접 content -->
  color="neutral"
  variant="outline"              <!-- outline / solid / soft / subtle -->
  class="w-fit"
/>

<UBadge
  :label="row.available"
  :color="row.available === 'On' ? 'success' : 'neutral'"
  variant="subtle"
/>
```

### 3.5 `<UIcon>`

Iconify 아이콘 렌더러.

```vue
<UIcon name="i-lucide-microscope" class="w-6 h-6 text-zinc-700" />
<UIcon name="i-lucide-arrow-right" class="w-4 h-4" />
```

**아이콘 네이밍**: `i-<collection>-<name>`.

이 프로젝트 `package.json`에는 두 컬렉션이 설치되어 있습니다.

- `@iconify-json/lucide` → `i-lucide-*` (예: `i-lucide-microscope`, `i-lucide-star`)
- `@iconify-json/simple-icons` → `i-simple-icons-*` (로고용)

사용 가능한 lucide 아이콘 목록: https://icones.js.org/collection/lucide

### 3.6 `<UColorModeButton>`

다크모드 토글 버튼. `@nuxtjs/color-mode` 모듈과 연계되어 자동으로 `.dark` 클래스를 `<html>`에 토글합니다.

## 4. 컴포넌트 카탈로그 (자주 쓰일 것들)

이 프로젝트에 아직 등장하지 않았지만 앞으로 페이지를 확장하면 쓸 법한 것들:

| 카테고리 | 컴포넌트 | 용도 |
|---|---|---|
| 폼 | `UInput`, `UTextarea`, `USelect`, `USelectMenu`, `UCheckbox`, `URadio`, `USwitch` | 기본 입력 |
| 폼 | `UForm`, `UFormField` | 유효성 검사 (zod/valibot과 통합) |
| 표시 | `UTable` | 데이터 테이블 (sort/pagination 내장) |
| 표시 | `UAlert`, `UToast`, `UModal`, `UConfirmModal` | 알림/모달 |
| 네비게이션 | `UTabs`, `UBreadcrumb`, `UPagination`, `UDropdownMenu` | 네비 |
| 레이아웃 | `UContainer`, `UCard`, `UDivider`, `UAccordion` | 구조 |
| 기타 | `UAvatar`, `USkeleton`, `UTooltip`, `UPopover`, `UCommandPalette` | 부가 |

자세한 건 공식 문서에서 카테고리별로 살펴보세요: https://ui.nuxt.com/docs/getting-started/installation/nuxt

## 5. 컴포넌트 props override 패턴

모든 NuxtUI 컴포넌트는 다음 세 방식으로 커스터마이즈 가능합니다.

1. **`color`, `variant`, `size` props** — 미리 준비된 조합
2. **`class` prop** — Tailwind 유틸리티로 루트 요소 스타일링
3. **`:ui` prop** — 내부 파트별 클래스 override (가장 세밀)

```vue
<UButton
  color="primary"
  size="lg"
  class="rounded-full shadow-xl"
  :ui="{
    base: 'font-bold',
    leadingIcon: 'size-5'
  }"
>
  Click me
</UButton>
```

파트 이름은 각 컴포넌트의 "Theme" 섹션에서 확인할 수 있습니다. 예: `UCard`는 `root`, `header`, `body`, `footer`.

## 6. 글로벌 테마 (`app.config.ts`)

```ts
// app/app.config.ts (이 프로젝트에는 거의 비어있음)
export default defineAppConfig({
  ui: {
    primary: 'blue',      // 모든 primary color의 기본
    colors: {
      primary: 'blue',
      neutral: 'zinc'
    }
  }
})
```

색 팔레트는 Tailwind 팔레트 이름(`zinc`, `gray`, `blue`, `green`, `red` ...)을 씁니다. 자세한 내용은 https://ui.nuxt.com/docs/getting-started/theme.

## 7. 프로젝트 스타일의 핵심: `.dashboard-surface`

NuxtUI 컴포넌트에 프로젝트 고유의 반투명 + blur 효과를 주기 위해 custom CSS 클래스를 정의합니다.

```css
/* assets/css/main.css */
.dashboard-surface {
  border: 1px solid rgba(39, 39, 42, 0.08);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(8px);
  box-shadow: 0 10px 26px -22px rgba(9, 9, 11, 0.55);
}

.dark .dashboard-surface { ... }
```

그리고 컴포넌트에 한 번에 적용합니다:

```vue
<UCard class="dashboard-surface rounded-2xl">
<UHeader class="dashboard-surface border-b ...">
<aside class="dashboard-surface border-r ...">
```

이런 패턴은 "NuxtUI는 기본 스타일을 주고, Tailwind로 미세 조정, 프로젝트 custom CSS로 브랜드 통일"이라는 일반적인 접근입니다.

## 8. 참고

- NuxtUI 공식 문서: https://ui.nuxt.com/docs
- 모든 컴포넌트 Playground: https://ui.nuxt.com/docs/components
- 아이콘 탐색기 (Iconify): https://icones.js.org
- Tailwind v4 마이그레이션 차이점: https://tailwindcss.com/docs/v4-beta
