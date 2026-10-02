# 04. Nuxt UI: 준비된 화면 부품과 프로젝트 디자인

## 1. 기초: 반복되는 UI 동작을 컴포넌트로 사용합니다

Nuxt UI는 버튼, 입력, 테이블, 모달 같은 Vue 컴포넌트를 제공합니다. Tailwind가 CSS 유틸리티를 제공한다면 Nuxt UI는 동작과 구조가 있는 화면 부품을 제공합니다. 버튼의 텍스트, 클릭 행동, disabled 상태와 화면 의미는 여전히 앱이 결정해야 합니다.

**2026-10-03 확인:** [package.json](../../../frontend/package.json)의 `@nuxt/ui: ^4.6.1`은 허용 범위입니다. [package-lock.json](../../../frontend/package-lock.json)과 원본 `frontend/node_modules/@nuxt/ui/package.json`의 실제 버전은 **4.10.0**입니다. 예제는 v4 기준이며 v2의 props나 컴포넌트 이름을 혼합하지 않습니다. 온라인 문서가 더 새 버전을 설명할 수 있으므로 [v4.10.0 공식 소스](https://github.com/nuxt/ui/tree/v4.10.0/src/runtime/components)도 확인합니다.

목표는 설치 방법을 외우는 것이 아니라, 현재 컴포넌트의 props와 slot을 읽고 프로젝트 토큰을 유지하면서 수정할 위치를 찾는 것입니다.

## 2. 용어: props, slot, theme slot, color, variant

| 용어 | 의미 | 예 |
| --- | --- | --- |
| props | 컴포넌트의 데이터 / 동작 입력 | `disabled`, `loading`, `to` |
| Vue slot | 부모가 넣는 화면 내용 | `#header`, 기본 slot |
| theme slot | 내부 요소에 클래스가 적용되는 자리 | `root`, `body`, `leadingIcon` |
| color | 의미 있는 색 역할 | `primary`, `neutral`, `success` |
| variant | 같은 역할의 표현 방식 | `solid`, `outline`, `ghost` |
| `class` | 보통 루트 요소를 조정하는 클래스 | `flex-1` |
| `ui` | 개별 내부 파트의 클래스 설정 | `:ui="{ body: 'p-0' }"` |

Vue의 `#header` slot과 테마의 `header` slot은 이름이 같더라도 책임이 다릅니다. 앞의 것은 **내용**, 뒤의 것은 **스타일**입니다. 컴포넌트마다 유효한 props, variant, slot 이름이 다르므로 모든 `U*`에 같은 키가 있다고 생각하면 안 됩니다.

## 3. 실제 구현

### 3.1 등록, CSS와 최상위 UApp

[nuxt.config.ts](../../../frontend/nuxt.config.ts)에 `@nuxt/ui`가 등록되어 있고 [main.css](../../../frontend/app/assets/css/main.css)에서 두 스타일을 가져옵니다.

```css
@import "tailwindcss";
@import "@nuxt/ui";
```

이 프로젝트에서는 Nuxt UI 모듈이 Tailwind Vite 통합도 구성합니다. 따라서 초보 실습을 위해 플러그인을 다시 설치하거나 별도 PostCSS 구성을 중복 추가하지 않습니다.

[app.vue](../../../frontend/app/app.vue)는 다음 구조를 갖습니다. 접근 제한 분기 부분을 생략한 **구조 설명**입니다.

```vue
<UApp>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</UApp>
```

UApp은 tooltip/config provider, toaster, overlay provider를 묶습니다. “모든 확인창을 자동 생성하는 ConfirmDialog 컨테이너”라고 설명하면 안 됩니다. 확인 UI는 실제 Modal이나 앱 컴포넌트로 작성해야 합니다. [4.10.0 UApp 소스](https://github.com/nuxt/ui/blob/v4.10.0/src/runtime/components/App.vue)에서 이 구성을 확인할 수 있습니다.

### 3.2 UButton과 UIcon

```vue
<UButton
  icon="i-lucide-search"
  color="neutral"
  variant="ghost"
  aria-label="검색"
/>

<UButton to="/settings" color="neutral" variant="outline">
  설정
</UButton>
```

`to`를 사용하는 버튼은 링크 동작을 갖습니다. 동작 실행용 버튼과 페이지 이동용 링크를 구분합니다. 아이콘만 있는 버튼에는 읽을 수 있는 이름이 필요하므로 `aria-label`을 제공합니다. disabled는 시각 표현뿐 아니라 클릭 가능 여부도 바꿉니다. loading 상태가 언제 끝나는지는 앱의 비동기 로직이 결정합니다.

아이콘 이름은 보통 `i-lucide-search`처럼 씁니다. 현재 lucide와 simple-icons JSON 패키지가 선언되어 있습니다. 하지만 패키지가 존재한다고 모든 동적 아이콘이 정적 배포에 자동 포함되는 것은 아닙니다.

[nuxt.config.ts](../../../frontend/nuxt.config.ts)의 `icon.fallbackToApi: false`는 런타임 외부 Iconify API 호출을 막습니다. `clientBundle.scan`은 앱 소스와 Nuxt UI 컴포넌트를 검색하고, 동적 이름은 `clientBundle.icons`에 `lucide:search` 형태로 명시합니다. Template 이름의 `i-lucide-*`와 설정의 `lucide:*` 표기를 구분합니다. 사내에서는 fallback을 켜서 빈 아이콘 문제를 덮지 않고 번들 포함 여부를 고칩니다.

### 3.3 UCard, UHeader, UBadge

[ToolInventoryView.vue](../../../frontend/app/components/ebeam/ToolInventoryView.vue)의 축약 예시입니다.

```vue
<UCard class="dashboard-surface" :ui="{ body: 'p-0 sm:p-0' }">
  <template #header>
    <h2 class="sk-heading">장비 리스트</h2>
    <UBadge color="neutral" variant="subtle">
      {{ filteredRows.length }} / {{ rows.length }}
    </UBadge>
  </template>
  <!-- 표는 기본 slot에 들어갑니다. -->
</UCard>
```

`class`만으로 내부 body의 padding을 없앨 수 있다고 가정하지 않습니다. 내부 파트는 `ui`를 확인합니다. 기본 테마에 `sm:p-*`가 있으면 `p-0`만으로 모든 화면 크기의 padding을 덮는 것이 아닐 수 있습니다. 실제 클래스와 브라우저 computed style을 확인합니다.

UHeader의 left / right 같은 named slot에는 로고나 제어 버튼을 넣습니다. UBadge는 짧은 상태나 수량을 표시하며 클릭 필터와는 의미가 다릅니다. 프로젝트에서는 정보 라벨, 필터 칩, 탐색 pill의 역할을 [DESIGN.md](../../../DESIGN.md)로 구분합니다.

### 3.4 입력과 표

현재 앱에는 `UInput`, `UTextarea`, `USelect`, `UTable`, `UModal`, `UTooltip` 등이 이미 사용됩니다. 미래 후보 목록처럼 적지 않습니다. [ChatComposer.vue](../../../frontend/app/components/chat/ChatComposer.vue)는 UTextarea의 `v-model`, autoresize, disabled와 UButton 이벤트를 연결합니다.

UTable은 TanStack Table을 바탕으로 행과 열을 다룹니다. 열 타입 `TableColumn<T>`는 Nuxt UI에서 가져오며 실제 정렬 상태 타입 등은 해당 라이브러리의 타입을 사용합니다. 현재 `@tanstack/vue-table`은 Nuxt UI 의존성 경로로 lock에 있습니다. 테이블이 있다는 이유로 서버 조회, 정렬 버튼, 페이지 이동 UI가 모두 자동 완성되는 것은 아닙니다.

```text
API rows
  → 앱 검색 / 필터 정책
      → UTable의 columns + data + 상태
          → 사용자가 헤더 / 페이지 버튼을 조작
              → 앱 상태 또는 API 요청 갱신
```

클라이언트 정렬은 내려받은 데이터만 정렬합니다. 서버 페이지의 일부만 받은 상황에서 전체 목록 정렬이라고 표시하면 잘못된 의미가 됩니다. 대용량 데이터의 필터/페이지 정책은 별도 요구 사항입니다.

v4에서 `URadioGroup`, `USeparator` 등 현재 이름을 확인합니다. 예전 문서의 `URadio`, `UDivider`, `UConfirmModal`을 v4 공식 컴포넌트라고 그대로 복사하지 않습니다. 원하는 확인창은 UModal 내용으로 구현할 수 있습니다.

### 3.5 프로젝트 테마와 CSS 토큰

[app.config.ts](../../../frontend/app/app.config.ts)는 거의 비어 있지 않습니다. 현재 primary와 neutral을 `paper` 팔레트로 매핑하며 카드/버튼/입력의 radius와 header, slideover, tooltip 파트를 설정합니다.

```ts
// 실제 설정 중 색 역할 부분입니다.
ui: {
  colors: {
    primary: 'paper',
    neutral: 'paper'
  }
}
```

`paper`는 main.css의 `@theme static`에서 정의합니다. `--ui-*`와 `--sk-*` 연결로 Nuxt UI와 앱 스타일의 의미를 맞춥니다. “기본 primary는 blue이니 개별 버튼을 파란색으로 바꿉니다”라는 식으로 테마를 우회하면 안 됩니다. 개별 사용처에서 반복 수정하기 전에 app.config의 기존 공통 설정을 확인합니다.

`.dashboard-surface`는 현재 `--sk-border`, `--sk-surface`와 부드러운 shadow를 쓰는 종이 느낌의 표면입니다. 예전의 반투명 흰 배경 + blur 카드가 아닙니다. 헤더에는 별도의 반투명 / backdrop blur 설정이 있으므로 모든 표면이 같은 blur 효과라고 설명하지 않습니다.

UColorModeButton은 color-mode 통합으로 테마를 바꿉니다. Nuxt UI 모듈이 이를 구성하며 `.dark`에 따른 CSS 토큰도 바뀝니다. 다크모드를 위해 모든 컴포넌트에 색상 hex를 따로 넣는 대신 의미 토큰을 재사용합니다.

## 4. 선택 이유와 한계

Nuxt UI는 기본 구조와 키보드/포커스 동작을 재사용하는 데 도움이 됩니다. 프로젝트 디자인은 `DESIGN.md`, app.config, main.css로 통일합니다. 다만 라이브러리가 있다고 앱 전체 접근성이 자동 검증되는 것은 아닙니다. 버튼 이름, 제목 계층, 입력 label, 표 의미, 모달 포커스가 실제 사용처에서 맞는지 확인해야 합니다.

`zod`, `valibot`는 현재 lock과 설치에 있지만 프런트 package의 직접 선언은 아닙니다. Form 검증과 통합 가능한 라이브러리라는 사실을 이 앱의 모든 API가 런타임 검증된다는 주장으로 바꾸지 않습니다. 실제 사용처를 확인한 뒤 설명합니다.

## 5. 흔한 실수

1. v2 예제의 props와 컴포넌트 이름을 v4에 사용합니다. 4.10.0 타입과 문서를 대조합니다.
2. `class`로 내부 파트를 고치려 합니다. 컴포넌트의 Theme slot을 확인합니다.
3. JSX/HTML 주석을 Vue 태그 속성 중간에 넣습니다. 주석은 태그 밖에 작성합니다.
4. 아이콘 패키지 설치만으로 사내 배포 아이콘이 보장된다고 생각합니다. scan과 동적 번들 목록을 확인합니다.
5. 새 색과 radius를 임의로 추가합니다. DESIGN과 `--sk-*` 토큰을 먼저 읽습니다.
6. UTable이 서버 페이지 처리까지 수행한다고 생각합니다. 데이터 범위와 앱의 요청 로직을 확인합니다.

## 6. 안전 실습

저장소 루트에서 읽기만 하는 실습입니다.

```bash
cat frontend/app/app.config.ts
rg -n 'fallbackToApi|clientBundle|fonts:' frontend/nuxt.config.ts
rg -n 'UCard|UBadge|:ui=|aria-label' frontend/app/components/ebeam/ToolInventoryView.vue
rg -n 'dashboard-surface|--sk-surface|--ui-' frontend/app/assets/css/main.css
```

완료 기준은 다음과 같습니다.

- UCard header의 내용은 Vue slot, body padding은 theme slot이라고 구분합니다.
- primary와 neutral의 실제 팔레트가 `paper`라고 답합니다.
- 아이콘이 없는 이유를 외부 네트워크 실패만으로 단정하지 않고 정적 번들 목록도 확인합니다.
- 표의 클라이언트 정렬과 서버 정렬이 같은 기능이 아니라고 설명합니다.

UI 변경을 실습할 때는 개인 학습 사본에서 버튼 하나의 `variant`만 바꾸고, 밝은/어두운 테마, 키보드 focus, 좁은 화면을 확인합니다. 공유 앱이나 운영 설정을 수정하지 않습니다. 타입 검사는 props 실수를 찾지만 시각 결과는 브라우저에서 확인해야 합니다.

## 7. 공식 근거

- [Nuxt UI Nuxt 설치](https://ui.nuxt.com/docs/getting-started/installation/nuxt)
- [Nuxt UI Button](https://ui.nuxt.com/docs/components/button)
- [Nuxt UI Card](https://ui.nuxt.com/docs/components/card)
- [Nuxt UI Table](https://ui.nuxt.com/docs/components/table)
- [Nuxt UI v4.10.0 Table 소스](https://github.com/nuxt/ui/blob/v4.10.0/src/runtime/components/Table.vue)
- [Nuxt UI v4.10.0 모듈 소스](https://github.com/nuxt/ui/blob/v4.10.0/src/module.ts)
- [다음: Tailwind CSS](../05-tailwind/README.md)
