# 상태 관리 - Pinia 활용하기

## 상태 관리 패키지가 탄생한 이유

### 웹 애플리케이션의 진화

초기 웹사이트는 단순한 정적 페이지였습니다. 사용자가 링크를 클릭하면 새로운 페이지로 이동하고, 각 페이지는 독립적이었습니다. 하지만 웹 기술이 발전하면서 **단일 페이지 애플리케이션(SPA, Single Page Application)**이 등장했습니다.

SPA에서는 페이지 전체를 새로 로드하지 않고, 필요한 부분만 동적으로 업데이트합니다. 이는 사용자 경험을 크게 향상시켰지만, 동시에 새로운 문제들을 만들어냈습니다.

### 컴포넌트 기반 아키텍처의 등장과 문제점

React, Vue, Angular과 같은 현대적 프론트엔드 프레임워크는 **컴포넌트 기반 아키텍처**를 도입했습니다. 이는 UI를 독립적이고 재사용 가능한 컴포넌트로 나누어 개발하는 방식입니다.

하지만 애플리케이션이 복잡해지면서 다음과 같은 문제들이 나타났습니다:

#### 1. 상태 공유의 어려움

```text
현실적인 예시: 쇼핑몰 애플리케이션

헤더 컴포넌트 (장바구니 개수 표시)
   ↓
메인 페이지
   ├── 상품 목록 컴포넌트
   │   └── 상품 카드 컴포넌트 (장바구니 추가 버튼)
   └── 사이드바 컴포넌트
       └── 장바구니 요약 컴포넌트
```

사용자가 상품을 장바구니에 추가하면, 헤더의 장바구니 개수, 사이드바의 장바구니 요약이 모두 업데이트되어야 합니다. 하지만 이 컴포넌트들은 서로 직접적인 부모-자식 관계가 아닙니다.

#### 2. Props Drilling의 악몽

```javascript
// 7단계를 거쳐 사용자 정보를 전달해야 하는 상황
App.vue (사용자 정보 보유)
└── Layout.vue (단순 전달)
    └── Dashboard.vue (단순 전달)
        └── ContentArea.vue (단순 전달)
            └── DataSection.vue (단순 전달)
                └── ChartContainer.vue (단순 전달)
                    └── ChartLegend.vue (실제 사용)
```

중간의 5개 컴포넌트는 사용자 정보를 전혀 사용하지 않으면서도 props로 받아서 전달만 해야 합니다.

#### 3. 예측 불가능한 상태 변화

여러 컴포넌트에서 동일한 데이터를 변경할 수 있게 되면서, 언제 어디서 상태가 변경되는지 추적하기 어려워졌습니다.

### Flux 아키텍처의 등장

이러한 문제를 해결하기 위해 Facebook에서 **Flux 아키텍처**를 제안했습니다. Flux는 **단방향 데이터 흐름**을 강제하여 상태 관리를 예측 가능하게 만들었습니다.

```text
Flux 패턴:
Action → Dispatcher → Store → View → Action
```

### Redux와 Vuex의 탄생

Flux 아키텍처를 구현한 대표적인 라이브러리들이 등장했습니다:

- **Redux** (React 생태계): Flux + 함수형 프로그래밍 개념
- **Vuex** (Vue 생태계): Vue에 최적화된 상태 관리

### Pinia가 필요한 이유

Vuex는 훌륭한 상태 관리 도구였지만, Vue 3와 Composition API의 등장으로 몇 가지 한계가 드러났습니다:

#### Vuex의 한계점

1. **복잡한 타입 추론**: TypeScript와 함께 사용할 때 타입 정의가 복잡
2. **보일러플레이트 코드**: mutations, actions 등 많은 코드 작성 필요
3. **모듈 시스템의 복잡성**: 네임스페이스 모듈 관리가 어려움

#### Pinia의 혁신

```javascript
// Vuex (복잡함)
const store = new Vuex.Store({
  state: { count: 0 },
  mutations: {
    INCREMENT(state) {
      state.count++;
    },
  },
  actions: {
    increment({ commit }) {
      commit("INCREMENT");
    },
  },
});

// Pinia (간단함)
export const useCounterStore = defineStore("counter", () => {
  const count = ref(0);
  function increment() {
    count.value++;
  }
  return { count, increment };
});
```

## 상태 관리의 필요성

Vue 애플리케이션이 성장하면서 컴포넌트 간 데이터 공유가 복잡해집니다. 부모-자식 관계가 아닌 컴포넌트들이 같은 데이터를 사용해야 하거나, 여러 컴포넌트에서 동일한 상태를 변경해야 할 때 상태 관리가 필요합니다.

### 상태 관리가 필요한 시나리오

- 사용자 로그인 정보를 여러 컴포넌트에서 사용
- AFM 장비 목록을 대시보드, 분석 페이지, 설정 페이지에서 공유
- 실시간 알림을 여러 화면에서 동시에 표시
- 필터링된 데이터를 페이지 이동 후에도 유지

## Pinia 설치 및 설정

Pinia는 Vue 3를 위한 공식 상태 관리 라이브러리입니다. Vuex의 후속 버전으로, 더 간단하고 TypeScript 친화적인 API를 제공합니다. Vue Router처럼 Vue 설치 진행 시 Pinia를 함께 설치할 건지 물어보는 경우가 많습니다.

### TypeScript란?

TypeScript는 JavaScript에 **정적 타입**을 추가한 **프로그래밍 언어**입니다. JavaScript의 상위 집합(Superset)으로, JavaScript 코드에 타입을 명시할 수 있게 해 주어 **코드 오류를 사전에 방지**하고 **더 안전하고 유지보수하기 쉬운 코드**를 작성할 수 있게 합니다.

TypeScript 코드는 브라우저에서 실행될 수 있도록 **JavaScript로 컴파일**됩니다. 코드가 방대해지고 협업이 진행될 때 TypeScript를 주로 사용하게 됩니다. JavaScript가 익숙해지면 TypeScript를 공부해봅시다.

### 설치

```bash
npm install pinia
```

### main.js 설정

```javascript
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);

app.mount("#app");
```

## Store 만들기

Pinia에서는 `defineStore` 함수를 사용하여 스토어를 정의합니다. Composition API 스타일로 작성하면 더 직관적입니다.

### src/stores/equipment.js

```javascript
import { defineStore } from "pinia";
import { ref, computed } from "vue";

export const useEquipmentStore = defineStore("equipment", () => {
  // State
  const equipments = ref([]);
  const loading = ref(false);
  const selectedEquipmentId = ref(null);

  // Getters
  const activeEquipments = computed(() => {
    return equipments.value.filter((eq) => eq.status === "active");
  });

  const selectedEquipment = computed(() => {
    return equipments.value.find((eq) => eq.id === selectedEquipmentId.value);
  });

  const equipmentCount = computed(() => equipments.value.length);

  // Actions
  async function fetchEquipments() {
    loading.value = true;
    try {
      const response = await fetch("/api/equipments");
      equipments.value = await response.json();
    } catch (error) {
      console.error("장비 목록 로드 실패:", error);
    } finally {
      loading.value = false;
    }
  }

  function addEquipment(equipment) {
    equipments.value.push({
      id: Date.now(),
      ...equipment,
      createdAt: new Date().toISOString(),
    });
  }

  function updateEquipment(id, updates) {
    const index = equipments.value.findIndex((eq) => eq.id === id);
    if (index !== -1) {
      equipments.value[index] = { ...equipments.value[index], ...updates };
    }
  }

  function deleteEquipment(id) {
    equipments.value = equipments.value.filter((eq) => eq.id !== id);
  }

  function selectEquipment(id) {
    selectedEquipmentId.value = id;
  }

  return {
    // State
    equipments,
    loading,
    selectedEquipmentId,

    // Getters
    activeEquipments,
    selectedEquipment,
    equipmentCount,

    // Actions
    fetchEquipments,
    addEquipment,
    updateEquipment,
    deleteEquipment,
    selectEquipment,
  };
});
```

## State, Getters, Actions 설명

### State (상태)

애플리케이션의 중앙 데이터 저장소입니다. Composition API에서는 `ref()`나 `reactive()`를 사용하여 반응형 상태를 정의합니다.

```javascript
const equipments = ref([]); // 장비 목록
const loading = ref(false); // 로딩 상태
const filters = reactive({
  // 필터 옵션
  status: "all",
  type: null,
});
```

### Getters (계산된 속성)

State를 기반으로 파생된 값을 반환합니다. `computed()`를 사용하여 정의하며, 종속된 상태가 변경될 때만 재계산됩니다.

```javascript
const activeCount = computed(() => {
  return equipments.value.filter((eq) => eq.status === "active").length;
});

const filteredEquipments = computed(() => {
  return equipments.value.filter((eq) => {
    if (filters.status !== "all" && eq.status !== filters.status) return false;
    if (filters.type && eq.type !== filters.type) return false;
    return true;
  });
});
```

### Actions (액션)

상태를 변경하는 함수들입니다. 비동기 작업도 처리할 수 있으며, 일반 함수로 정의합니다.

```javascript
async function fetchMeasurementData(equipmentId) {
  try {
    const response = await fetch(`/api/equipments/${equipmentId}/measurements`);
    const data = await response.json();

    // 상태 업데이트
    const equipment = equipments.value.find((eq) => eq.id === equipmentId);
    if (equipment) {
      equipment.measurements = data;
    }
  } catch (error) {
    console.error("측정 데이터 로드 실패:", error);
  }
}
```

## Composition API의 변화

### Options API vs Composition API

**기존 Options API 방식**

```javascript
export const useEquipmentStore = defineStore("equipment", {
  state: () => ({
    equipments: [],
    loading: false,
  }),

  getters: {
    activeEquipments: (state) => {
      return state.equipments.filter((eq) => eq.status === "active");
    },
  },

  actions: {
    async fetchEquipments() {
      this.loading = true;
      // ...
    },
  },
});
```

**Composition API 방식**

```javascript
export const useEquipmentStore = defineStore("equipment", () => {
  // 모든 로직을 하나의 setup 함수 안에 작성
  const equipments = ref([]);
  const loading = ref(false);

  const activeEquipments = computed(() => {
    return equipments.value.filter((eq) => eq.status === "active");
  });

  async function fetchEquipments() {
    loading.value = true;
    // ...
  }

  return { equipments, loading, activeEquipments, fetchEquipments };
});
```

### Composition API의 장점

1. **타입 추론 향상**: TypeScript와 함께 사용할 때 더 정확한 타입 추론
2. **코드 재사용**: Composable 함수로 로직을 쉽게 추출하고 재사용
3. **더 나은 구조화**: 관련된 로직을 함께 그룹화
4. **IDE 지원**: 자동 완성과 리팩토링이 더 효과적

**Composable 함수**란 **다른 함수들과 조합**하여 더 복잡한 동작을 만들어낼 수 있는 함수입니다. 보통 입력과 출력을 명확히 하고, 부작용이 없는 순수 함수인 경우가 많습니다.

## 컴포넌트에서 Store 사용하기

### 대시보드 컴포넌트

```javascript
// Template
<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <h1>장비 현황</h1>
        <p>총 {{ equipmentCount }}대 중 {{ activeEquipments.length }}대 운영 중</p>
      </v-col>
    </v-row>

    <v-row>
      <v-col v-for="equipment in activeEquipments" :key="equipment.id" cols="12" md="4">
        <v-card @click="selectEquipment(equipment.id)">
          <v-card-title>{{ equipment.name }}</v-card-title>
          <v-card-text>
            <p>상태: {{ equipment.status }}</p>
            <p>마지막 측정: {{ equipment.lastMeasurement }}</p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-progress-linear v-if="loading" indeterminate></v-progress-linear>
  </v-container>
</template>

// Script
<script setup>
import { onMounted } from 'vue'
import { useEquipmentStore } from '@/stores/equipment'
import { storeToRefs } from 'pinia'

// Store 사용
const equipmentStore = useEquipmentStore()

// 반응형 상태 추출 (storeToRefs 사용)
const { activeEquipments, loading, equipmentCount } = storeToRefs(equipmentStore)

// Actions는 직접 구조 분해
const { fetchEquipments, selectEquipment } = equipmentStore

// 컴포넌트 마운트 시 데이터 로드
onMounted(() => {
  fetchEquipments()
})
</script>
```

### 장비 추가 폼 컴포넌트

```javascript
// Template
<template>
  <v-dialog v-model="dialog" max-width="600">
    <v-card>
      <v-card-title>새 장비 추가</v-card-title>
      <v-card-text>
        <v-form @submit.prevent="handleSubmit">
          <v-text-field
            v-model="formData.name"
            label="장비명"
            required
          ></v-text-field>

          <v-select
            v-model="formData.type"
            :items="equipmentTypes"
            label="장비 타입"
          ></v-select>

          <v-select
            v-model="formData.status"
            :items="['active', 'maintenance', 'inactive']"
            label="상태"
          ></v-select>
        </v-form>
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn @click="dialog = false">취소</v-btn>
        <v-btn color="primary" @click="handleSubmit">추가</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

// Script
<script setup>
import { ref, reactive } from 'vue'
import { useEquipmentStore } from '@/stores/equipment'

const equipmentStore = useEquipmentStore()
const dialog = ref(false)

const formData = reactive({
  name: '',
  type: '',
  status: 'active'
})

const equipmentTypes = ['AFM', 'SEM', 'TEM', 'XRD']

function handleSubmit() {
  // Store의 action 호출
  equipmentStore.addEquipment(formData)

  // 폼 초기화
  Object.assign(formData, {
    name: '',
    type: '',
    status: 'active'
  })

  dialog.value = false
}
</script>
```

### 여러 Store 함께 사용하기

```javascript
<script setup>
import { useEquipmentStore } from '@/stores/equipment'
import { useUserStore } from '@/stores/user'
import { useMeasurementStore } from '@/stores/measurement'
import { storeToRefs } from 'pinia'

const equipmentStore = useEquipmentStore()
const userStore = useUserStore()
const measurementStore = useMeasurementStore()

// 각 Store의 상태와 액션 사용
const { currentUser } = storeToRefs(userStore)
const { selectedEquipment } = storeToRefs(equipmentStore)

async function loadMeasurements() {
  if (selectedEquipment.value && currentUser.value) {
    await measurementStore.fetchMeasurements({
      equipmentId: selectedEquipment.value.id,
      userId: currentUser.value.id
    })
  }
}
</script>
```

## Vue 컴포넌트 통신 방법

### 기본 컴포넌트 통신

Vue에서 컴포넌트 간 데이터 전달은 계층 구조에 따라 다릅니다.

#### Props - 부모에서 자식으로

```javascript
// 부모 컴포넌트
<template>
  <EquipmentCard
    :equipment="equipmentData"
    :status="activeStatus"
    @update="handleUpdate"
  />
</template>

// 자식 컴포넌트 (EquipmentCard.vue)
<template>
  <div>
    <h3>{{ equipment.name }}</h3>
    <p>상태: {{ status }}</p>
  </div>
</template>

<script setup>
defineProps({
  equipment: Object,
  status: String
})
</script>
```

#### Emit - 자식에서 부모로

```javascript
// 자식 컴포넌트
<script setup>
  const emit = defineEmits(['update', 'delete']) function updateEquipment(){" "}
  {emit("update", { id: 1, name: "새 이름" })}
</script>
```

### Props Drilling 문제

여러 단계를 거쳐 데이터를 전달해야 할 때 발생하는 문제입니다.

```text
App.vue → Dashboard.vue → EquipmentList.vue → EquipmentCard.vue
4단계를 거쳐 userData를 전달해야 함
```

### Provide/Inject - 깊은 계층 구조 해결

Provide/Inject는 Vue에서 제공하는 의존성 주입 시스템입니다. Props Drilling 문제를 해결하기 위한 중간 단계 해결책으로, 조상 컴포넌트에서 후손 컴포넌트로 직접 데이터를 전달할 수 있게 해줍니다.

#### 기본 사용법

```javascript
// 최상위 컴포넌트 (조상)
<template>
  <div>
    <UserProfile />
  </div>
</template>

<script setup>
import { provide, ref } from 'vue'
import UserProfile from './UserProfile.vue'

const userData = ref({
  name: '홍길동',
  role: 'engineer',
  department: 'AI/DT TF'
})

const theme = ref('dark')

// 여러 데이터를 provide할 수 있음
provide('user', userData)
provide('theme', theme)
</script>

// 깊은 하위 컴포넌트 (후손)
<template>
  <div :class="theme">
    <h3>{{ user.name }}</h3>
    <p>부서: {{ user.department }}</p>
    <p>역할: {{ user.role }}</p>
  </div>
</template>

<script setup>
import { inject } from 'vue'

// inject로 조상 컴포넌트의 데이터 접근
const user = inject('user')
const theme = inject('theme')

// 기본값 설정 가능
const settings = inject('settings', { notifications: true })
</script>
```

#### 실제 활용 예시 - 다국어 지원

```javascript
// App.vue (최상위)
<script setup>
import { provide, ref } from 'vue'

const locale = ref('ko')
const translations = ref({
  ko: {
    welcome: '환영합니다',
    equipment: '장비',
    status: '상태'
  },
  en: {
    welcome: 'Welcome',
    equipment: 'Equipment',
    status: 'Status'
  }
})

function t(key) {
  return translations.value[locale.value][key] || key
}

function changeLocale(newLocale) {
  locale.value = newLocale
}

// 번역 함수와 로케일 변경 함수 제공
provide('i18n', { t, changeLocale, locale })
</script>

// 깊은 하위 컴포넌트에서 사용
<template>
  <div>
    <h1>{{ t('welcome') }}</h1>
    <p>{{ t('equipment') }}: AFM-001</p>
    <select @change="changeLocale($event.target.value)">
      <option value="ko">한국어</option>
      <option value="en">English</option>
    </select>
  </div>
</template>

<script setup>
import { inject } from 'vue'

const { t, changeLocale } = inject('i18n')
</script>
```

#### 반응형 Provide/Inject

```javascript
// 부모 컴포넌트
<script setup>
import { provide, ref, readonly } from 'vue'

const count = ref(0)
const message = ref('Hello')

// 읽기 전용으로 제공하여 자식에서 직접 수정 방지
provide('count', readonly(count))
provide('message', readonly(message))

// 수정 함수들을 따로 제공
provide('updateCount', (newCount) => {
  count.value = newCount
})

provide('updateMessage', (newMessage) => {
  message.value = newMessage
})
</script>

// 자식 컴포넌트
<script setup>
import { inject } from 'vue'

const count = inject('count')
const message = inject('message')
const updateCount = inject('updateCount')
const updateMessage = inject('updateMessage')

function increment() {
  updateCount(count.value + 1)
}
</script>
```

#### Provide/Inject의 장단점

**장점:**

- Props Drilling 문제 해결
- 중간 컴포넌트에 불필요한 props 전달 불필요
- 플러그인이나 라이브러리에서 설정 주입에 유용
- 컴포넌트 트리의 특정 부분에만 필요한 데이터 공유에 적합

**단점:**

- 어떤 조상 컴포넌트에서 데이터가 오는지 추적하기 어려움
- 전역적이지 않아 형제 컴포넌트 간 통신에는 부적합
- 의존성이 명시적이지 않아 코드 이해가 어려울 수 있음
- 너무 많이 사용하면 컴포넌트 간 결합도가 높아짐

#### 언제 Provide/Inject를 사용해야 하나

**적합한 경우:**

```javascript
// 테마 제공자
provide("theme", themeConfig);

// 폼 컨텍스트 제공
provide("form", formMethods);

// 모달/다이얼로그 컨텍스트
provide("modal", modalControls);

// 권한 시스템
provide("permissions", userPermissions);
```

**부적합한 경우:**

```javascript
// ❌ 비즈니스 로직 상태 (Pinia 사용 권장)
provide("equipmentList", equipments);

// ❌ 자주 변경되는 전역 상태
provide("notifications", notifications);

// ❌ 단순한 부모-자식 통신 (Props 사용 권장)
provide("buttonColor", "primary");
```

### Pinia가 해결하는 문제

#### 형제 컴포넌트 간 통신

```javascript
// Header.vue
<script setup>
import { useUserStore } from '@/stores/user'
const userStore = useUserStore()
</script>

// Sidebar.vue
<script setup>
import { useUserStore } from '@/stores/user'
const userStore = useUserStore()
// 동일한 상태 공유
</script>
```

#### 전역 상태 관리

```javascript
// stores/notification.js
export const useNotificationStore = defineStore("notification", () => {
  const notifications = ref([]);

  function addNotification(message) {
    notifications.value.push({
      id: Date.now(),
      message,
      timestamp: new Date(),
    });
  }

  return { notifications, addNotification };
});
```

모든 컴포넌트에서 알림 상태에 접근 가능합니다.

## 언제 무엇을 사용해야 하나

### Props/Emit 사용 시나리오

- 부모-자식 관계가 명확한 경우
- 컴포넌트가 재사용 가능해야 하는 경우
- 데이터 흐름이 단순한 경우
- UI 컴포넌트 (버튼, 카드, 모달)
- 폼 입력 컴포넌트
- 임시 상태나 로컬 UI 상태

### Provide/Inject 사용 시나리오

- 깊은 계층 구조에서 특정 데이터 공유
- 플러그인이나 라이브러리 설정 주입
- 컴포넌트 트리의 일부분에만 필요한 데이터

### Pinia 사용 시나리오

- 여러 컴포넌트에서 공유하는 상태
- 페이지 이동 후에도 유지되어야 하는 데이터
- 복잡한 상태 로직이 필요한 경우
- 형제 컴포넌트 간 통신
- 사용자 인증 정보
- 전역 설정
- 서버에서 가져온 데이터 캐싱

## Pinia와 Props/Emit 비교

### Props/Emit의 장점과 한계

#### 장점

**컴포넌트 재사용성**

```javascript
// 재사용 가능한 컴포넌트
<EquipmentCard
  :title="장비1"
  :status="active"
  @click="handleClick"
/>

// 다른 프로젝트에서도 사용 가능
<EquipmentCard
  :title="다른장비"
  :status="inactive"
  @click="differentHandler"
/>
```

**명확한 인터페이스**

```javascript
<script setup>
// Props로 컴포넌트가 필요한 데이터가 명확함
defineProps({
  equipment: {
    type: Object,
    required: true
  },
  showDetails: {
    type: Boolean,
    default: false
  }
})
</script>
```

**단방향 데이터 흐름**

```javascript
// 부모 → 자식
<ChildComponent :data="parentData" />

// 자식 → 부모
<ChildComponent @update="parentData = $event" />
```

#### 한계점

**Props Drilling 문제**

여러 컴포넌트 계층을 통해 데이터를 전달할 때 발생하는 문제입니다.

- 중간 컴포넌트들은 단순히 데이터를 전달하는 역할만 함
- 코드가 장황해지고 유지보수가 어려워짐

**형제 컴포넌트 간 통신 어려움**

동일한 부모를 가진 컴포넌트 간에 데이터를 공유하려면 부모를 통해 우회해야 합니다.

- 복잡한 상태 공유 시 부모 컴포넌트가 과도하게 복잡해짐
- 관련 없는 컴포넌트가 데이터 전달 책임을 가지게 됨

**전역 상태 관리 불가능**

애플리케이션 전체에서 필요한 데이터(사용자 인증, 전역 설정 등)를 관리하기 어렵습니다.

### Pinia의 장점과 한계

#### 장점

- 여러 컴포넌트 간 상태 공유 용이
- 중앙 집중식 상태 관리
- TypeScript 지원
- 개발자 도구 지원

#### 한계점

**과도한 전역 상태**

```javascript
// 모든 것을 Store에 넣으면 안 됨
const useFormStore = defineStore("form", () => {
  const tempInput = ref(""); // ❌ 임시 입력값
  const isModalOpen = ref(false); // ❌ 로컬 UI 상태
});
```

**컴포넌트 간 결합도 증가**

```javascript
// Button.vue - 재사용 불가
<script setup>
  import {useAppStore} from '@/stores/app' // 특정 스토어에 종속 const store =
  useAppStore()
</script>
```

## 실제 사용 예시

### 비효율적인 방법 (Props만 사용)

```javascript
<template>
  <Dashboard :equipments="equipments" @update="updateEquipment">
    <EquipmentList :equipments="equipments" @update="$emit('update', $event)">
      <EquipmentCard
        v-for="eq in equipments"
        :equipment="eq"
        @update="$emit('update', $event)"
      />
    </EquipmentList>
  </Dashboard>
</template>
```

### 효율적인 방법 (Pinia 사용)

```javascript
<template>
  <Dashboard /> <!-- 각 컴포넌트가 독립적으로 Store 접근 -->
</template>
```

## 결론

Pinia와 Props/Emit은 서로 다른 목적과 사용 사례를 가지고 있어 **완전히 대체할 수 없습니다**. 각 방법의 고유한 장점을 활용하여 상황에 맞게 사용하는 것이 가장 효과적입니다.

### 균형 잡힌 접근법

- **Props/Emit**: 컴포넌트별 로컬 데이터 전달과 이벤트 처리
- **Pinia**: 전역 상태 관리와 복잡한 상태 로직
- **Provide/Inject**: 깊은 계층 구조에서의 특정 데이터 공유

이러한 방식으로 Pinia를 사용하면 애플리케이션의 상태를 체계적으로 관리할 수 있으며, 컴포넌트 간 데이터 공유가 매우 간단해집니다. 특히 Composition API 스타일로 작성하면 더 직관적이고 유지보수가 용이한 코드를 작성할 수 있습니다.

## 참고 자료

- [Pinia 공식 문서](https://pinia.vuejs.org/)
- [Vue 3 Composition API 가이드](https://vuejs.org/guide/extras/composition-api-faq.html)
- [Pinia 한국어 문서](https://pinia.vuejs.kr/)
