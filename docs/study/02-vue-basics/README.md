# 02. Vue 3 기본 (Composition API + `<script setup>`)

Vue는 "반응형 상태를 정의하면 UI가 자동 갱신되는" 프론트엔드 프레임워크입니다. 이 프로젝트는 **Composition API**와 `<script setup>` 신텍스를 사용합니다(Vue 3 권장 스타일).

백엔드 개발자 관점의 비유:
- **상태(state)** = 데이터베이스 레코드
- **반응형(reactive)** = ORM의 lazy loading 대신, 값이 바뀌면 자동으로 view도 재계산
- **컴포넌트** = 재사용 가능한 UI 함수 (Flask의 Jinja 템플릿 + 로직 + 스타일을 한 파일에 묶은 것)

## 1. SFC 구조 (`.vue` 파일)

Single File Component는 세 블록으로 구성됩니다.

```vue
<script setup lang="ts">
// 여기에 로직 (TypeScript)
const count = ref(0)
const double = computed(() => count.value * 2)
</script>

<template>
  <!-- 여기에 HTML (Vue 문법 포함) -->
  <button @click="count++">
    {{ count }} × 2 = {{ double }}
  </button>
</template>

<style scoped>
/* 여기에 CSS (scoped면 이 컴포넌트 한정) */
button { padding: 8px; }
</style>
```

이 프로젝트는 CSS를 Tailwind 유틸리티로 처리해서 `<style>` 블록을 거의 쓰지 않습니다(전역 CSS는 `assets/css/main.css`에서 관리).

## 2. 반응형 primitives

### 2.1 `ref` — 단일 값

```ts
import { ref } from 'vue'  // Nuxt는 auto-import라 생략 가능

const count = ref(0)
console.log(count.value)   // 0  ← JS에서는 .value로 접근
count.value++              // 값 갱신

// template에서는 .value 자동 언랩
// <div>{{ count }}</div>  OK
```

프로젝트 예시 (`FabSidebar.vue`):

```ts
const sidebarCollapsed = ref(false)
// ... @click="sidebarCollapsed = !sidebarCollapsed"
```

### 2.2 `reactive` — 객체

```ts
import { reactive } from 'vue'

const state = reactive({ count: 0, name: 'Claude' })
state.count++  // .value 없음 (객체 자체가 Proxy)
```

Nuxt/Vue 3 커뮤니티는 "primitive에는 `ref`, 더 복잡해지면 ref/computed 조합"을 선호합니다. `reactive`는 거의 안 씁니다.

### 2.3 `computed` — 파생 값

```ts
const ebeamTools = computed(() => {
  return toolTypes.map(tool => ({
    ...tool,
    count: inventory.value?.[tool.id].length ?? tool.count
  }))
})
// ebeamTools.value 로 접근, 자동으로 캐시되고 의존성 바뀔 때만 재계산
```

Python 비교: `@property`와 매우 닮았지만 의존성이 바뀌기 전까지는 **캐시**됩니다.

### 2.4 `watch` / `watchEffect`

이 프로젝트 코드에는 거의 없지만 알아두면 좋습니다.

```ts
import { watch, watchEffect } from 'vue'

// watch — 특정 값이 바뀔 때 콜백
watch(count, (newVal, oldVal) => {
  console.log(`count: ${oldVal} → ${newVal}`)
})

// watchEffect — 함수 안에서 참조한 모든 반응형 값이 바뀔 때 재실행
watchEffect(() => {
  console.log(`count is ${count.value}`)
})
```

## 3. `<script setup>` 자동 노출

`<script setup>` 블록에서 선언한 `const`, `function`, `import`는 자동으로 템플릿에서 사용 가능합니다.

```vue
<script setup lang="ts">
const title = 'Hello'
const onClick = () => console.log('clicked')
</script>

<template>
  <h1 @click="onClick">{{ title }}</h1>
</template>
```

옛날 Options API의 `data()`, `methods`, `computed` 같은 객체 구조 없이도 동작합니다.

## 4. 템플릿 문법

### 4.1 보간 `{{ }}`

```html
<span>{{ tool.count }}</span>
<span>{{ String(tool.count) }}</span>  <!-- JS 표현식 가능 -->
```

### 4.2 디렉티브

| 디렉티브 | 기능 | 예시 |
|---|---|---|
| `v-if` / `v-else-if` / `v-else` | 조건부 렌더링 | `<div v-if="show">...</div>` |
| `v-show` | CSS display로 토글 (DOM은 유지) | `<div v-show="show">` |
| `v-for` | 반복 | `<li v-for="x in list" :key="x.id">` |
| `v-bind` / `:` | 속성 바인딩 | `:to="url"`, `:class="..."` |
| `v-on` / `@` | 이벤트 | `@click="onClick"` |
| `v-model` | 양방향 바인딩 (폼에 주로) | `<input v-model="name">` |

프로젝트 예시:

```vue
<!-- v-for + :key 필수 -->
<NuxtLink
  v-for="tool in ebeamTools"
  :key="tool.id"
  :to="`/ebeam/${tool.id}`"
>
  {{ tool.label }}
</NuxtLink>

<!-- 동적 클래스 (객체/배열 문법) -->
<button
  :class="item.active
    ? 'bg-zinc-900 text-zinc-100'
    : 'text-zinc-700 hover:bg-zinc-100'"
>

<!-- 조건부 블록 (template 태그는 DOM에 나오지 않음) -->
<template v-if="props.fab === 'all' && fabSummaries.length > 0">
  ...
</template>
```

### 4.3 Slot

컴포넌트 내부에 외부에서 content를 꽂는 장치. 이 프로젝트의 `UHeader` 같은 NuxtUI 컴포넌트에 많이 사용됩니다.

```vue
<!-- 사용처 -->
<UHeader>
  <template #left>
    <AppLogo />
  </template>
  <template #right>
    <UButton icon="i-lucide-search" />
  </template>
</UHeader>

<!-- 기본 slot은 #default -->
<UCard>
  <!-- 여기 내용이 UCard의 기본 slot으로 들어감 -->
  <div>Body</div>
</UCard>
```

## 5. Props와 Emits

### 5.1 Props (부모 → 자식)

TS 제네릭 방식이 표준입니다.

```ts
// ToolInventoryView.vue
const props = withDefaults(defineProps<{
  fab?: Fab                 // 선택(?) 속성
  subtitle: string
  title: string
  toolType: ToolType
}>(), {
  fab: 'all'                // 기본값 객체
})

// 사용
console.log(props.toolType)
```

부모에서 전달:

```vue
<EbeamToolInventoryView
  tool-type="cd-sem"        <!-- kebab-case 자동 변환 -->
  title="CD-SEM Overview"
  subtitle="..."
/>
```

### 5.2 Emits (자식 → 부모)

이 프로젝트에는 없지만 표준 패턴:

```ts
const emit = defineEmits<{
  click: [id: string]       // 이벤트 이름: [인자 타입들]
  save: [value: number]
}>()

emit('click', 'tool-1')
```

부모:

```vue
<MyBtn @click="handleClick" @save="handleSave" />
```

## 6. Lifecycle hooks

```ts
import { onMounted, onUnmounted, onBeforeMount } from 'vue'  // auto-import됨

onMounted(() => {
  // 컴포넌트가 DOM에 마운트된 직후
  setToolType('cd-sem')
  setFab('all')
})

onUnmounted(() => {
  // 언마운트 직전 (타이머 정리 등)
})
```

프로젝트 예시 (`pages/ebeam/cd-sem/index.vue`): 페이지 진입 시 navigation store를 동기화합니다.

## 7. 컴포넌트 이름 규칙

이 프로젝트는 Nuxt의 자동 컴포넌트 등록을 사용합니다. `components/nav/AppHeader.vue` 파일은 템플릿에서 **`<NavAppHeader />`**로 쓸 수 있습니다.

규칙: 폴더 경로 + 파일명을 **PascalCase**로 이어붙인 이름.

```
components/nav/AppHeader.vue        → <NavAppHeader />
components/nav/FabSidebar.vue       → <NavFabSidebar />
components/ebeam/ToolInventoryView.vue → <EbeamToolInventoryView />
components/AppLogo.vue              → <AppLogo />
```

이 기본값을 바꾸려면 `nuxt.config.ts`에서 `components` 키를 조정합니다.

## 8. 반응형 래퍼(ref)의 흔한 함정

백엔드 개발자가 가장 많이 실수하는 지점.

```ts
const count = ref(0)

// ❌ 틀림 — JS에서는 .value 필요
if (count > 0) { ... }

// ✅ 맞음
if (count.value > 0) { ... }

// 단, template에서는 .value 생략 (자동 언랩)
// <div v-if="count > 0">...</div>
```

함수 인자로 ref를 넘길 때 `.value`를 미리 꺼내면 반응성을 잃습니다. 원래 ref를 통째로 넘기세요.

## 9. 다음 단계

- `03-nuxt/`로 가서 Nuxt가 위 개념들에 더해주는 것들(auto-import, `useAsyncData`, `useState`, 파일 라우팅)을 이해하세요.
- Vue 공식 튜토리얼(인터랙티브): https://vuejs.org/tutorial/
- Vue 공식 가이드: https://vuejs.org/guide/introduction.html
