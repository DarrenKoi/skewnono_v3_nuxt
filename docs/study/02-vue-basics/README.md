# 02. Vue 3 기본: 상태와 화면의 연결


HTML(Hypertext Markup Language)은 화면 구조, CSS(Cascading Style Sheets)는 표시 스타일, DOM(Document Object Model)은 브라우저가 만든 문서 객체 구조입니다. 화면 변경은 이 객체 구조의 갱신으로 이어집니다.

## 1. 기초: 데이터 변경을 화면 변경으로 연결합니다

Vue는 브라우저 화면을 컴포넌트로 나누는 프레임워크입니다. 컴포넌트는 입력(props)을 받고, 내부 상태를 보관하고, HTML을 만들며, 사용자 행동을 이벤트로 알립니다. Flask가 서버에서 템플릿을 렌더링하는 것과 달리, 이 프로젝트의 Vue 화면은 브라우저에서 계속 살아 있으면서 상태 변경에 따라 갱신됩니다.

반응형 상태는 DB 레코드나 ORM lazy loading과 같지 않습니다. JavaScript 메모리 안의 값에 대한 **읽기와 변경을 추적**하여 필요한 계산과 화면 갱신을 예약하는 장치입니다. 저장하거나 API를 호출하는 일은 따로 작성해야 합니다.

**2026-10-03 확인:** Vue는 [package.json](../../../frontend/package.json)에 직접 선언되어 있지 않습니다. Nuxt가 끌고 오는 의존성이며 [package-lock.json](../../../frontend/package-lock.json)과 원본 작업 공간 `frontend/node_modules/vue/package.json`에서 **3.5.40**을 확인했습니다. 이 문서는 Composition API와 `<script setup lang="ts">`를 기준으로 합니다.

## 2. 용어: SFC, ref, computed, props, emit

| 용어 | 뜻 |
| --- | --- |
| SFC | `.vue` 파일 안에 script, template, style을 묶는 Single File Component입니다. |
| Composition API | 함수로 상태, 계산, 생명주기를 조합하는 방식입니다. |
| ref | `.value`에 실제 값을 보관하는 반응형 상자입니다. |
| reactive | 객체를 Proxy로 감싸 속성 접근과 변경을 추적합니다. |
| computed | 다른 반응형 값에서 계산한 결과입니다. |
| watch | 특정 상태 변경에 따라 부수효과를 실행합니다. |
| props | 부모가 자식에게 주는 입력입니다. |
| emit | 자식이 부모에게 알리는 이벤트입니다. |
| slot | 부모가 자식의 정해진 위치에 넣는 화면 내용입니다. |

SFC의 기본 구조는 다음과 같습니다. **학습 예시**이며 현재 소스에 이 카운터가 있다는 뜻은 아닙니다. 일반 Vue에서 실행할 수 있도록 import를 명시했습니다.

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'

const count = ref(0)
const double = computed(() => count.value * 2)
</script>

<template>
  <button type="button" @click="count++">
    {{ count }} × 2 = {{ double }}
  </button>
</template>

<style scoped>
button { padding: 8px; }
</style>
```

`<script setup>`의 최상위 변수와 함수는 같은 파일의 template에서 사용할 수 있습니다. 다른 컴포넌트에 자동으로 공개되는 것은 아닙니다. `scoped` CSS는 빌드 시 속성 선택자를 붙여 범위를 제한하며, Shadow DOM을 만드는 것은 아닙니다.

## 3. 실제 구현을 읽는 순서

### 3.1 `ref`와 `reactive`

```ts
const count = ref(0)
count.value += 1                 // script에서는 .value입니다.
const state = reactive({ count: 0 })
state.count += 1                 // reactive 객체는 .value가 없습니다.
const rows = ref([{ id: 'A' }])  // ref는 객체 / 배열도 담을 수 있습니다.
```

`ref`는 숫자 전용이 아닙니다. 기본 `ref`는 객체의 중첩 변경도 반응형으로 다룰 수 있습니다. `shallowRef`는 `.value`의 교체를 추적하며 중첩 객체를 깊게 감싸지 않습니다. **Nuxt 4 `useAsyncData`의 기본 data는 얕은 ref**이므로 모든 ref의 동작을 같게 생각하면 안 됩니다.

Template에서 최상위 ref는 보통 자동으로 풀리므로 `{{ count }}`를 씁니다. 그러나 배열 / Map 속 ref나 중첩된 일반 객체의 ref는 자동 해제가 동일하게 적용되지 않습니다. [공식 반응형 기초](https://vuejs.org/guide/essentials/reactivity-fundamentals.html)의 제한을 참고합니다.

### 3.2 `computed`는 읽기 계산입니다

```ts
const keyword = ref('')
const rows = ref([{ id: 'SEM-01' }, { id: 'SEM-02' }])
const visibleRows = computed(() =>
  rows.value.filter(row => row.id.includes(keyword.value))
)
```

의존성이 바뀌면 computed가 다시 평가될 필요가 생깁니다. 읽을 때 결과를 계산하고 캐시합니다. 단순 함수나 Python `@property`와 달리 반응형 의존성을 추적합니다. computed 안에서 API 요청, localStorage 쓰기, 다른 상태 변경을 하지 않습니다. 이런 부수효과는 계산이 몇 번 읽혔는지에 의존하면 안 됩니다.

[ToolInventoryView.vue](../../../frontend/app/components/ebeam/ToolInventoryView.vue)는 서버 원본 목록, FAB 선택, 검색 필터를 바탕으로 표시할 목록과 통계를 계산합니다. 학습할 때 먼저 입력 상태를 찾고, 그 상태를 읽는 computed를 찾고, 마지막에 template 사용처를 읽습니다.

### 3.3 `watch`와 `watchEffect`

```ts
watch(keyword, (next, previous) => {
  console.log(previous, '→', next)
})

watchEffect(() => {
  console.log(keyword.value)
})
```

`watch`는 지정한 source를 감시하며 기본적으로 첫 설정 시 콜백을 실행하지 않습니다. `watchEffect`는 바로 실행하고 동기 실행 구간에서 읽은 반응형 값을 자동 추적합니다. 비동기 함수의 `await` 뒤에 처음 읽은 값까지 모두 추적한다고 가정하면 안 됩니다.

객체의 일반 속성을 감시할 때는 `watch(() => state.count, callback)`처럼 getter를 전달합니다. `watch(state.count, callback)`는 현재 숫자를 전달할 뿐입니다. 중첩 변경 여부는 source와 `deep` 옵션의 영향을 받습니다.

현재 watch는 드문 기능이 아닙니다. [FabSidebar.vue](../../../frontend/app/components/nav/FabSidebar.vue)에 접힘 상태 감시가 있으며 [usePersistedState.ts](../../../frontend/app/composables/usePersistedState.ts)는 watcher로 상태를 저장합니다. 기본 갱신은 배치되지만 `flush: 'sync'` watcher는 동기 실행합니다. 이 선택은 저장 시점의 이유가 있으므로 모든 watch에 복사하지 않습니다.

### 3.4 템플릿 문법

| 문법 | 책임 | 확인할 점 |
| --- | --- | --- |
| `{{ value }}` | 텍스트 출력 | HTML은 텍스트로 이스케이프됩니다. |
| `:disabled="busy"` | 속성 바인딩 | 문자열 `"false"`와 boolean false는 다릅니다. |
| `@click="submit"` | 이벤트 처리 | DOM 이벤트와 자식 emit을 구분합니다. |
| `v-if` | 조건에 따라 생성 / 제거 | 자식의 상태와 생명주기에 영향을 줍니다. |
| `v-show` | CSS display로 표시 / 숨김 | 컴포넌트와 DOM은 유지됩니다. |
| `v-for` | 반복 렌더링 | 안정적인 데이터 ID를 key로 사용합니다. |
| `v-model` | 입력값과 상태 연결 | 자식 컴포넌트에서는 props + update 이벤트 계약입니다. |

```vue
<template>
  <ul>
    <li v-for="row in visibleRows" :key="row.id">
      {{ row.id }}
    </li>
  </ul>
</template>
```

정렬하거나 필터링하는 목록에서 배열 index를 key로 쓰면 기존 입력이나 자식 상태가 다른 행과 연결될 수 있습니다. `v-if`와 `v-for`를 같은 요소에 붙여 해석 순서를 혼동하지 말고 computed로 필터링합니다. `v-html`은 신뢰하지 않는 입력을 넣는 지점에서 XSS 위험이 있으므로 일반 데이터는 보간을 사용합니다.

### 3.5 부모 입력과 자식 이벤트

```vue
<script setup lang="ts">
const props = withDefaults(defineProps<{
  title: string
  disabled?: boolean
}>(), { disabled: false })

const emit = defineEmits<{ save: [title: string] }>()
const save = () => {
  if (!props.disabled) emit('save', props.title)
}
</script>

<template>
  <button type="button" :disabled="disabled" @click="save">
    {{ title }}
  </button>
</template>
```

`defineProps`, `defineEmits`, `withDefaults`는 `<script setup>` 컴파일러 매크로입니다. Nuxt auto-import와는 다른 이유로 import가 필요 없습니다. Props 자체를 자식에서 대입해서 고치지 않습니다. 중첩 객체를 직접 고치면 부모 값도 바뀔 수 있으므로 “읽기 전용 입력 → 이벤트 → 부모 갱신” 흐름을 지킵니다.

현재 [ChatComposer.vue](../../../frontend/app/components/chat/ChatComposer.vue)는 `defineEmits<{ send: [text: string] }>()`로 전송 내용을 알리고 `defineModel<string>`로 초안을 연결합니다. [SegmentedToggle.vue](../../../frontend/app/components/sk/SegmentedToggle.vue)는 `modelValue`를 받고 `update:modelValue` 이벤트를 내보냅니다. Emits가 없는 프로젝트라는 예전 설명은 현재와 다릅니다.

```text
부모 model 상태
  → 자식 modelValue / defineModel 입력
      → 사용자 선택
          → update:modelValue 이벤트
              → 부모 상태 갱신
                  → 새 입력과 화면 갱신
```

Vue 3.5의 같은 `<script setup>` 안에서는 `defineProps`의 구조 분해가 컴파일러에 의해 반응형으로 처리될 수 있습니다. 그렇다고 일반 reactive 객체의 구조 분해까지 모두 안전한 것은 아닙니다. 다른 함수에 `props.title`의 현재 문자열을 넘기는 것과 `() => props.title`을 넘기는 것도 구분합니다.

### 3.6 Slot과 생명주기

```vue
<UCard>
  <template #header>
    <h2 class="sk-heading">장비 목록</h2>
  </template>
  <p class="sk-body">이 내용은 기본 slot입니다.</p>
</UCard>
```

`#header`는 이름 있는 slot입니다. 자식이 slot props를 제공하면 `#default="{ row }"`처럼 부모가 그 값을 받을 수 있습니다. Props는 데이터 전달, slot은 화면 구조 전달이라는 차이를 먼저 익힙니다.

`onMounted`는 DOM 생성 후에 실행되며, `onUnmounted`는 제거 후 정리에 사용합니다. 타이머와 외부 이벤트 리스너를 설치했다면 해제를 짝지어 읽습니다. 상태 변경 직후 DOM도 즉시 바뀐다고 가정하지 않습니다. 새 DOM을 읽어야 할 때는 `await nextTick()`을 사용합니다. 모든 계산을 `onMounted`로 미루는 것은 필요한 초기 상태를 늦추므로 목적을 확인합니다.

Nuxt는 `components/nav/AppHeader.vue`를 `<NavAppHeader />`로 등록합니다. 이 등록은 Vue 자체의 기본 기능과 구분하며 [Nuxt 문서](../03-nuxt/README.md)에서 이어서 학습합니다.

## 4. 선택 이유와 한계

Composition API는 상태와 계산을 기능별로 가까이 둘 수 있습니다. TypeScript와 `<script setup>`를 함께 쓰면 props와 이벤트 계약을 읽기 쉽습니다. 그러나 자동 반응성은 저장, API 최신성, 비동기 경쟁, 화면 접근성을 대신하지 않습니다. `reactive`는 잘못된 API가 아니며, 객체 사용 목적과 교체 방식에 따라 ref와 선택합니다.

CSS도 Tailwind만 사용하지 않습니다. [ChatComposer.vue](../../../frontend/app/components/chat/ChatComposer.vue)처럼 실제로 scoped CSS와 `:deep()`을 사용합니다. 스타일은 [Tailwind 문서](../05-tailwind/README.md)와 `DESIGN.md` 기준을 함께 읽습니다.

## 5. 흔한 실수

1. Script에서 ref의 `.value`를 생략합니다. Template의 자동 해제와 구분합니다.
2. 현재 primitive 값만 전달하고 이후 변경을 구독할 것으로 기대합니다. 함수가 반응형 입력을 요구할 때 ref 또는 getter를 사용합니다. 단순 값만 요구하는 함수에는 `.value`가 맞습니다.
3. Computed를 watch처럼 부수효과 실행 장소로 씁니다. 계산과 외부 작업을 나눕니다.
4. 자식이 props를 직접 고칩니다. 이벤트나 v-model 계약을 사용합니다.
5. 상태 변경 직후 DOM 치수를 읽습니다. Vue의 갱신 배치를 고려합니다.
6. `v-show`가 타이머와 네트워크 처리를 중단한다고 생각합니다. 숨기는 것과 제거하는 것은 다릅니다.

## 6. 안전 실습

저장소 파일을 바꾸지 않는 첫 실습은 [Vue 공식 Playground](https://play.vuejs.org/)에 위 카운터 예시를 넣는 것입니다. 온라인 Playground는 사내 오프라인 실행 경로가 아니라 개인 학습 도구입니다.

1. 버튼을 세 번 누릅니다. `count`는 3, `double`은 6이어야 합니다.
2. Script의 `count.value`를 `count`로 바꾸고 타입 오류를 확인합니다.
3. Template에는 `.value`를 쓰지 않아도 값이 표시되는지 확인합니다.
4. `watch(count, ...)`를 추가하면 클릭 때만 로그가 나오고, `watchEffect`는 최초에도 실행되는지 봅니다.
5. 위 slot 예시를 실제 소스와 비교합니다. 일반 Vue Playground에는 `UCard`가 자동 등록되지 않으므로 프로젝트 라이브러리 예시는 읽기 실습으로만 사용합니다.

로컬에서는 프로젝트 루트에서 다음을 읽습니다.

```bash
rg -n 'defineProps|defineEmits|defineModel' frontend/app/components/chat/ChatComposer.vue
rg -n 'modelValue|update:modelValue' frontend/app/components/sk/SegmentedToggle.vue
rg -n 'watch|flush|effectScope' frontend/app/composables/usePersistedState.ts
```

완료 기준은 “초안 상태 → 버튼 이벤트 → send emit”과 “부모 선택 → modelValue → update 이벤트”를 자기 말로 설명하는 것입니다. 이 읽기 실습은 브라우저 검증이나 office 장비 검증을 의미하지 않습니다.

## 7. 공식 근거와 다음 단계

- [Vue 반응형 기초](https://vuejs.org/guide/essentials/reactivity-fundamentals.html)
- [Vue computed](https://vuejs.org/guide/essentials/computed.html)
- [Vue watch](https://vuejs.org/guide/essentials/watchers.html)
- [Vue script setup와 3.5 props 구조 분해](https://vuejs.org/api/sfc-script-setup.html)
- [Vue 컴포넌트 v-model](https://vuejs.org/guide/components/v-model.html)
- [다음: Nuxt](../03-nuxt/README.md)
