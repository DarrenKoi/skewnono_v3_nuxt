# Vue 3 기초 다지기

본 장에서는 Vue.js로 웹 애플리케이션을 개발할 때 반드시 이해해야 할 핵심 개념들을 다룹니다. 컴포넌트 기반 아키텍처, 템플릿 문법, 반응성 시스템, 이벤트 처리, 조건부 렌더링, 리스트 렌더링까지 Vue의 주요 기능들을 설명하며, 마지막에는 실습 예제로 종합 정리합니다. 자세한 내용은 [Vue.js 공식 가이드 (한국어)](https://ko.vuejs.org/guide/introduction.html) 참고하세요.

## 컴포넌트의 개념

Vue에서 **컴포넌트(Component)**는 화면을 구성하는 독립적이며 재사용 가능한 UI 단위입니다. 이는 마치 레고 블록이나 반도체 장비의 모듈처럼, 작은 단위들을 조립하여 전체 애플리케이션을 구성하는 방식입니다.

### 주요 특징

- **재사용성**: 한 번 작성한 컴포넌트는 여러 곳에서 반복 사용할 수 있어 코드 중복을 줄이고 개발 효율성을 높입니다.

- **캡슐화**: 각 컴포넌트는 고유한 템플릿(HTML), 스크립트(JavaScript), 스타일(CSS)을 갖습니다. 보통 `.vue` 확장자를 사용하는 싱글 파일 컴포넌트(SFC)로 관리합니다.

- **계층 구조**: 컴포넌트는 다른 컴포넌트를 자식으로 포함할 수 있으며, 부모-자식 간 데이터 전달과 이벤트 전파를 통해 복잡한 UI를 체계적으로 구성할 수 있습니다.

## 템플릿 문법

Vue는 HTML 기반의 템플릿 문법을 통해 JavaScript 데이터와 UI를 선언적으로 연결할 수 있게 지원합니다. 개발자는 DOM을 직접 조작하지 않고 직관적인 코드로 화면을 구성할 수 있습니다.

### 주요 문법

#### 텍스트 보간

데이터를 텍스트로 출력하는 `{{ }}` 문법입니다.

```html
<p>메시지: {{ message }}</p>
```

#### 디렉티브

`v-` 접두사가 붙는 특수 속성입니다.

**v-bind** (또는 `:`): 속성 바인딩을 수행합니다.

```html
<img :src="imagePath" />
```

**v-html**: HTML 콘텐츠로 렌더링합니다. (주의: XSS 위험이 있으므로 신뢰할 수 있는 콘텐츠에만 사용해야 합니다.)

```html
<div v-html="rawHtmlContent"></div>
```

이 외에도 `v-if`, `v-for`, `v-on`, `v-model` 등 다양한 디렉티브가 제공됩니다.

> **⚠️ 보안 경고: XSS (Cross-Site Scripting) 취약점**
>
> XSS는 웹 애플리케이션의 심각한 보안 취약점으로, 공격자가 악의적인 스크립트를 웹 페이지에 삽입할 수 있는 공격 방식입니다.
>
> **XSS의 주요 위험:**
>
> - 사용자 세션 하이재킹
> - 개인정보 탈취
> - 악성 스크립트 실행
> - 웹사이트 변조
>
> **안전한 사용 방법:**
>
> - 가능한 `v-html` 사용 자제
> - 사용자 입력을 신중하게 검증 및 정제
> - HTML Sanitization 라이브러리 사용
> - Vue에서는 `DOMPurify` 같은 라이브러리 활용 권장
>
> **예시 공격 시나리오:**
>
> ```javascript
> // 악의적인 사용자 입력
> const maliciousInput =
>   '<script>alert("Your cookie: " + document.cookie)</script>';
> ```

## 반응성 시스템

Vue의 핵심 기능은 **반응형 시스템(Reactivity System)**입니다. 데이터가 변경되면 Vue가 이를 자동으로 감지하여 관련 UI를 업데이트합니다.

Vue 3에서는 두 가지 API로 반응형 데이터를 선언할 수 있습니다.

- **Options API**: `data()`, `methods`를 사용합니다.
- **Composition API**: `ref()`, `reactive()`를 사용합니다.

### Composition API 예시

```javascript
import { ref, reactive } from "vue";

const count = ref(0); // 기본형 데이터
const equipment = reactive({
  // 객체형 데이터
  model: "AFM-2000",
  status: "대기 중",
});
```

Composition API는 복잡한 로직을 더 유연하게 관리할 수 있도록 설계되었습니다. 개발 과정에서 우리는 Composition API 문법만을 사용합니다. LLM(대규모 언어 모델)에 코드를 요청할 때는 Composition API와 Script Setup 문법을 명시적으로 요구하는 것이 좋습니다. 그렇지 않으면 종종 Options API 문법으로 된 코드를 받게 될 수 있습니다.

## 계산된 속성 (Computed Properties)

계산된 속성은 다른 반응형 데이터를 기반으로 계산되는 값입니다. 마치 Excel의 수식처럼, 참조하는 데이터가 변경되면 자동으로 다시 계산됩니다.

### 계산된 속성의 특징

#### 캐싱

계산된 속성은 의존하는 데이터가 변경될 때만 다시 계산되고, 그렇지 않으면 캐시된 결과를 반환합니다.

#### 읽기 전용

기본적으로 계산된 속성은 읽기 전용입니다.

#### 반응형

의존하는 데이터가 변경되면 자동으로 업데이트됩니다.

### 계산된 속성 vs 메서드

```javascript
// 계산된 속성 (추천)
const totalPrice = computed(() => {
  return items.value.reduce((sum, item) => sum + item.price, 0);
});

// 메서드 방식 (비추천)
const getTotalPrice = () => {
  return items.value.reduce((sum, item) => sum + item.price, 0);
};
```

**차이점:**

- **계산된 속성**: 의존성이 변경될 때만 재계산 (성능상 유리)
- **메서드**: 호출될 때마다 매번 실행

### 실제 AFM 데이터 예시

```javascript
import { ref, computed } from "vue";

const measurements = ref([
  { sampleId: "A1", roughness: 2.5 },
  { sampleId: "A2", roughness: 3.1 },
  { sampleId: "A3", roughness: 1.8 },
]);

// 평균 거칠기 계산
const averageRoughness = computed(() => {
  if (measurements.value.length === 0) return 0;
  const sum = measurements.value.reduce((acc, m) => acc + m.roughness, 0);
  return (sum / measurements.value.length).toFixed(2);
});

// 품질 등급 분류
const qualityGrade = computed(() => {
  const avg = parseFloat(averageRoughness.value);
  if (avg < 2.0) return "A급";
  if (avg < 3.0) return "B급";
  return "C급";
});
```

템플릿에서 사용:

```html
<template>
  <div>
    <p>총 측정 개수: {{ measurements.length }}</p>
    <p>평균 거칠기: {{ averageRoughness }} nm</p>
    <p>품질 등급: {{ qualityGrade }}</p>
  </div>
</template>
```

## 이벤트 처리

Vue는 사용자 상호작용(예: 클릭, 입력)을 처리할 때 `v-on` 디렉티브(축약형 `@`)를 사용합니다.

### 예시

```html
<button @click="increment">증가</button> <input @keyup.enter="submitForm" />
```

### 이벤트 수식어

Vue는 이벤트 처리를 간소화하기 위한 수식어를 제공합니다.

- `.stop`: 이벤트 전파 중단
- `.prevent`: 기본 동작 방지
- `.once`: 한 번만 실행
- 키/마우스 수식어: `.enter`, `.left` 등

## 조건부 렌더링

애플리케이션의 상태에 따라 UI를 표시하거나 숨길 때는 다음을 사용합니다.

- `v-if` / `v-else-if` / `v-else`: 조건에 따라 DOM을 생성하거나 제거합니다.
- `v-show`: CSS `display` 속성만 토글합니다. (자주 토글되는 요소에 유리합니다.)

```html
<p v-if="isLoggedIn">환영합니다!</p>
<p v-show="isVisible">이 메시지는 보였다 숨겨졌다 합니다.</p>
```

## 리스트 렌더링

배열이나 객체 데이터를 반복 출력할 때는 `v-for`를 사용합니다.

```html
<ul>
  <li v-for="item in items" :key="item.id">{{ item.name }}</li>
</ul>
```

## 실습 예제: 간단한 측정 데이터 관리자

지금까지 배운 내용을 활용하여 AFM 측정 데이터를 관리하는 애플리케이션을 작성합니다. 주요 기능은 다음과 같습니다.

- 샘플 ID 및 측정값 입력
- 측정 데이터 목록 표시
- 평균값 계산 및 표시
- 데이터 삭제

```javascript
// Template
<template>
  <div>
    <!-- 입력 -->
    <input v-model="newMeasurement.sampleId" placeholder="샘플 ID">
    <input v-model.number="newMeasurement.value" type="number" placeholder="측정값">
    <button @click="addMeasurement" :disabled="!isValidInput">추가</button>

    <!-- 통계 -->
    <div v-if="measurements.length">
      <p>총 측정 횟수: {{ measurements.length }}</p>
      <p>평균값: {{ averageValue.toFixed(2) }} nm</p>
    </div>

    <!-- 리스트 -->
    <div v-for="m in measurements" :key="m.id">
      {{ m.sampleId }} - {{ m.value }} nm - {{ m.timestamp }}
      <button @click="removeMeasurement(m.id)">삭제</button>
    </div>

    <p v-else>아직 측정 데이터가 없습니다.</p>
  </div>
</template>

// Script
<script setup>
import { ref, reactive, computed } from 'vue';

// 반응형 데이터
const measurements = ref([]);
const newMeasurement = reactive({
  sampleId: '',
  value: null
});
const nextId = ref(1);

// 계산된 속성
const isValidInput = computed(() => {
  return newMeasurement.sampleId && newMeasurement.value > 0;
});

const averageValue = computed(() => {
  const sum = measurements.value.reduce((acc, m) => acc + m.value, 0);
  return sum / measurements.value.length || 0;
});

// 메서드
const addMeasurement = () => {
  if (!isValidInput.value) return;

  measurements.value.push({
    id: nextId.value++,
    sampleId: newMeasurement.sampleId,
    value: newMeasurement.value,
    timestamp: new Date().toLocaleString()
  });

  // 입력 필드 초기화
  newMeasurement.sampleId = '';
  newMeasurement.value = null;
};

const removeMeasurement = (id) => {
  measurements.value = measurements.value.filter(m => m.id !== id);
};
</script>
```

## 읽을 거리: JavaScript 함수 문법 완전 정복

### function(){}과 () => {}의 차이점

Vue 3 Composition API에서 자주 보게 되는 두 가지 함수 문법에 대해 자세히 알아보겠습니다. 이 차이를 이해하는 것은 현대적인 JavaScript 개발에서 매우 중요합니다.

#### 함수 선언 방식의 종류

JavaScript에서는 함수를 정의하는 여러 가지 방법이 있습니다:

**1. 함수 선언문 (Function Declaration)**

```javascript
function addMeasurement() {
  console.log("측정 데이터를 추가합니다");
}
```

**2. 함수 표현식 (Function Expression)**

```javascript
const addMeasurement = function () {
  console.log("측정 데이터를 추가합니다");
};
```

**3. 화살표 함수 (Arrow Function) - ES6+**

```javascript
const addMeasurement = () => {
  console.log("측정 데이터를 추가합니다");
};
```

### 호이스팅 (Hoisting) 이해하기

호이스팅은 JavaScript의 독특한 특성 중 하나로, 변수와 함수 선언이 스코프의 최상단으로 "끌어올려지는" 현상을 말합니다. 이는 코드 실행 전에 JavaScript 엔진이 변수와 함수 선언을 미리 처리하기 때문입니다.

#### 함수 선언문의 호이스팅

함수 선언문은 완전히 호이스팅되어 선언 이전에도 호출할 수 있습니다:

```javascript
// 이 코드는 정상 작동합니다!
console.log(calculateArea(5, 3)); // 15 출력

function calculateArea(width, height) {
  return width * height;
}

// JavaScript 엔진이 내부적으로 다음과 같이 처리:
// function calculateArea(width, height) {
//   return width * height;
// }
// console.log(calculateArea(5, 3));
```

#### 함수 표현식과 화살표 함수의 호이스팅

함수 표현식과 화살표 함수는 변수처럼 취급되므로 다르게 동작합니다:

```javascript
// 에러 발생! Cannot access 'calculateArea' before initialization
console.log(calculateArea(5, 3));

const calculateArea = function (width, height) {
  return width * height;
};

// 화살표 함수도 마찬가지
console.log(getAverage([1, 2, 3])); // 에러!

const getAverage = (numbers) => {
  return numbers.reduce((sum, num) => sum + num, 0) / numbers.length;
};
```

#### 변수 호이스팅의 차이점

```javascript
// var의 호이스팅 (구형 방식)
console.log(oldVar); // undefined (에러가 아님!)
var oldVar = "Hello";

// let/const의 호이스팅 (현대 방식)
console.log(newVar); // ReferenceError: Cannot access before initialization
let newVar = "Hello";
console.log(newConst); // ReferenceError: Cannot access before initialization
const newConst = "Hello";
```

### 성능과 메모리 관점에서의 함수 비교

#### 메모리 사용량 차이

```javascript
// 클래스에서 화살표 함수 사용 시 주의
class MeasurementProcessor {
  constructor() {
    // ❌ 각 인스턴스마다 새로운 함수가 생성됨 (메모리 비효율)
    this.process = () => {
      console.log("처리 중...");
    };
  }

  // ✅ 프로토타입에 공유되는 메서드 (메모리 효율적)
  processTraditional() {
    console.log("처리 중...");
  }
}

// 100개 인스턴스를 생성한다면
const processors = Array.from(
  { length: 100 },
  () => new MeasurementProcessor()
);
// 화살표 함수: 100개의 별도 함수 객체 생성 (더 많은 메모리 사용)
// 전통적 함수: 1개의 프로토타입 메서드 공유 (적은 메모리 사용)
```

#### 실행 성능 차이

```javascript
// 성능 테스트 예시
const data = Array.from({ length: 1000000 }, (_, i) => i);

// 화살표 함수
console.time("Arrow Function");
const resultArrow = data.map((x) => x * 2);
console.timeEnd("Arrow Function");

// 전통적 함수
function multiply(x) {
  return x * 2;
}

console.time("Traditional Function");
const resultTraditional = data.map(multiply);
console.timeEnd("Traditional Function");

// 결과: 큰 차이는 없지만, 전통적 함수가 미세하게 빠를 수 있음
// 이는 JavaScript 엔진 최적화 방식에 따라 달라질 수 있음
```

#### Vue 3에서의 성능 고려사항

```javascript
// ❌ 템플릿에서 인라인 화살표 함수 (성능상 좋지 않음)
// <template>
//   <button v-for="item in items" :key="item.id"
//           @click="() => handleClick(item.id)">
//     {{ item.name }}
//   </button>
// </template>

// ✅ 미리 정의된 함수 사용 (성능상 좋음)
// <template>
//   <button v-for="item in items" :key="item.id"
//           @click="handleClick(item.id)">
//     {{ item.name }}
//   </button>
// </template>

// <script setup>
const handleClick = (id) => {
  console.log("클릭된 항목:", id);
};
// </script>
```

### 구조 분해 할당과 함께 사용하기

#### 매개변수 구조 분해

```javascript
// 객체 매개변수의 구조 분해
const createMeasurement = ({ sampleId, value, timestamp = new Date() }) => ({
  id: Date.now(),
  sampleId,
  value,
  timestamp: timestamp.toISOString(),
  processed: true,
});

// 사용법
const newMeasurement = createMeasurement({
  sampleId: "A001",
  value: 2.5,
  // timestamp는 기본값 사용
});

// 배열 매개변수의 구조 분해
const calculateStats = ([min, max, ...values]) => {
  const average = values.reduce((sum, val) => sum + val, 0) / values.length;
  return { min, max, average, count: values.length };
};

// 사용법
const stats = calculateStats([0, 100, 2.5, 3.1, 1.8, 4.2]);
```

#### 반환값 구조 분해

```javascript
// 여러 값을 객체로 반환
const processData = (data) => {
  const validData = data.filter((item) => item.value > 0);
  const average =
    validData.reduce((sum, item) => sum + item.value, 0) / validData.length;

  return {
    processedData: validData,
    statistics: { average, count: validData.length },
    hasError: validData.length === 0,
  };
};

// 구조 분해로 필요한 값만 추출
const {
  processedData,
  statistics: { average },
} = processData(rawData);
```

#### Vue 3에서의 구조 분해 활용

```javascript
<script setup>
import { ref, computed, watch } from 'vue';

// props 구조 분해
const props = defineProps({
  measurements: Array,
  title: String,
  showStats: { type: Boolean, default: true }
});

// props 구조 분해 사용
const { measurements, title, showStats } = toRefs(props);

// 또는 직접 구조 분해 (반응성 유지 주의)
const { measurements: rawMeasurements } = props;

// computed에서 구조 분해 활용
const statistics = computed(() => {
  const data = measurements.value || [];
  const validMeasurements = data.filter(({ value }) => value > 0);

  if (validMeasurements.length === 0) {
    return { average: 0, min: 0, max: 0, count: 0 };
  }

  const values = validMeasurements.map(({ value }) => value);
  const sum = values.reduce((acc, val) => acc + val, 0);

  return {
    average: sum / values.length,
    min: Math.min(...values),
    max: Math.max(...values),
    count: values.length
  };
});

// 이벤트 핸들러에서 구조 분해
const handleMeasurementUpdate = ({ id, newValue, timestamp }) => {
  const index = measurements.value.findIndex(m => m.id === id);
  if (index !== -1) {
    measurements.value[index] = {
      ...measurements.value[index],
      value: newValue,
      lastUpdated: timestamp
    };
  }
};
</script>
```

### 실무에서의 사용 가이드라인

#### 화살표 함수를 사용하는 경우

```javascript
// 1. 배열 메서드 (map, filter, reduce 등)
const processedData = rawData.map(({ id, value, metadata }) => ({
  id,
  processedValue: value * 2,
  category: metadata.category || "unknown",
}));

// 2. Promise와 async/await
const fetchMeasurementData = async (sampleId) => {
  try {
    const response = await fetch(`/api/measurements/${sampleId}`);
    const { data, status, message } = await response.json();
    return { data, success: status === "ok", message };
  } catch (error) {
    console.error("데이터 로딩 실패:", error);
    return { data: null, success: false, message: error.message };
  }
};

// 3. 이벤트 핸들러 (Vue 3에서)
const handleFormSubmit = async ({ sampleId, value, notes }) => {
  const measurement = { sampleId, value, notes, timestamp: new Date() };
  await saveMeasurement(measurement);
};
```

#### 전통적인 함수를 사용해야 하는 경우

```javascript
// 1. 객체 메서드에서 this가 필요한 경우
const equipment = {
  name: "AFM Scanner",
  measurements: [],

  addMeasurement({ sampleId, value }) {
    // 화살표 함수 사용하면 안 됨
    this.measurements.push({ sampleId, value, timestamp: new Date() });
    console.log(`${this.name}에 측정 데이터 추가됨`);
  },

  getStatistics() {
    const values = this.measurements.map(({ value }) => value);
    return {
      count: values.length,
      average: values.reduce((sum, val) => sum + val, 0) / values.length,
    };
  },
};

// 2. 생성자 함수
function MeasurementDevice(name, type) {
  this.name = name;
  this.type = type;
  this.measurements = [];
}

MeasurementDevice.prototype.addMeasurement = function ({ sampleId, value }) {
  this.measurements.push({ sampleId, value, deviceName: this.name });
};
```

### Vue 3 프로젝트에서의 권장 사항

```javascript
// 권장 패턴
<script setup>
import { ref, computed, watch } from 'vue';

// 반응형 데이터
const measurements = ref([]);
const selectedSample = ref(null);

// 구조 분해를 활용한 computed
const statistics = computed(() => {
  const data = measurements.value;
  if (data.length === 0) return null;

  const { validMeasurements, invalidMeasurements } = data.reduce(
    (acc, measurement) => {
      const { value } = measurement;
      if (value > 0) {
        acc.validMeasurements.push(measurement);
      } else {
        acc.invalidMeasurements.push(measurement);
      }
      return acc;
    },
    { validMeasurements: [], invalidMeasurements: [] }
  );

  return {
    total: data.length,
    valid: validMeasurements.length,
    invalid: invalidMeasurements.length,
    validityRate: (validMeasurements.length / data.length * 100).toFixed(1)
  };
});

// 이벤트 핸들러들
const handleMeasurementAdd = ({ sampleId, value, metadata = {} }) => {
  measurements.value.push({
    id: Date.now(),
    sampleId,
    value,
    metadata,
    createdAt: new Date().toISOString()
  });
};

const handleMeasurementDelete = (targetId) => {
  measurements.value = measurements.value.filter(({ id }) => id !== targetId);
};

// 비동기 함수
const loadMeasurements = async () => {
  try {
    const { data, success, error } = await fetchMeasurements();
    if (success) {
      measurements.value = data;
    } else {
      console.error('측정 데이터 로딩 실패:', error);
    }
  } catch (err) {
    console.error('예상치 못한 오류:', err);
  }
};
</script>
```

이러한 현대적인 JavaScript 문법과 구조 분해 할당을 이해하고 적절히 사용하면, 더 읽기 쉽고 유지보수하기 좋은 Vue 애플리케이션을 만들 수 있습니다.
