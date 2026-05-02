# Vue 프로젝트 시작하기

## Vue.js 프레임워크 이해하기

### Vue.js란 무엇인가?

Vue.js는 사용자 인터페이스를 구축하기 위한 **프로그레시브 자바스크립트 프레임워크**입니다. 다른 단일체 프레임워크와 달리 Vue는 점진적으로 채택할 수 있도록 설계되었습니다.

#### 건물 건축으로 이해하는 Vue.js

- **HTML**: 건물의 기본 구조 (골조)
- **CSS**: 건물의 외관과 인테리어 (디자인)
- **Vue.js**: 건물의 지능형 시스템 (자동화, 상호작용)

### 점진적(Progressive)이라는 의미

Vue는 처음부터 모든 기능을 다 배워야 하는 "올인원 프레임워크"가 아닙니다. 필요한 부분만 골라서 작은 부분에만 적용할 수 있고, 나중에 필요할 때 더 많은 기능을 점점 추가해나갈 수 있습니다.

#### 아파트 리모델링으로 이해하기

1. **1단계**: 거실 한 곳만 스마트홈 적용 (간단한 데이터 바인딩)
2. **2단계**: 전체 방에 스마트 시스템 확장 (컴포넌트 활용)
3. **3단계**: 건물 전체 통합 관리 시스템 (라우터, 상태관리)

#### AFM 프로젝트 적용 예시

| 단계      | 기능                          | 적용 범위        |
| --------- | ----------------------------- | ---------------- |
| **1단계** | `{{ measurementData }}`       | 단순 데이터 표시 |
| **2단계** | 검색 컴포넌트, 차트 컴포넌트  | 재사용 가능한 UI |
| **3단계** | 페이지 라우팅, 전역 상태 관리 | 완전한 SPA       |

### Vue.js의 주요 특징

#### 1. 템플릿 문법

- HTML 기반 템플릿 문법을 사용하여 DOM에 데이터를 선언적으로 바인딩
- 기존 HTML/CSS/JS 지식을 가진 개발자들이 쉽게 접근 가능

```html
<!-- 기존 HTML -->
<h1>AFM 측정 데이터</h1>

<!-- Vue 템플릿 -->
<h1>{{ pageTitle }}</h1>
<!-- 동적으로 변경 가능! -->
```

#### 2. 반응성 시스템

반응형 데이터 바인딩 시스템으로 데이터 변경 시 자동으로 화면 업데이트됩니다. DOM 직접 조작의 복잡성을 해결하고 상태 관리에 집중할 수 있는 개발 환경을 제공합니다.

Vue 3에서는 `ref()`를 사용하여 반응성 데이터를 생성합니다. `ref()`로 감싼 데이터는 `.value` 속성을 통해 접근하며, 이 값이 변경되면 템플릿에서 자동으로 화면이 업데이트됩니다.

```javascript
import { ref } from "vue";

// 반응성 데이터 생성
const measurementCount = ref(0);

// 값 변경 시 화면에 자동 반영
measurementCount.value = 150;
```

> **DOM이란?**
>
> DOM은 웹 페이지의 구조를 프로그래밍적으로 표현하는 인터페이스입니다. 브라우저는 HTML 문서를 트리 구조의 객체로 변환하여, 개발자가 JavaScript를 통해 웹 페이지의 내용과 구조를 동적으로 접근하고 조작할 수 있게 합니다.

**전통적인 DOM 조작 방식의 한계:**

- 복잡한 상태 변경 시 수동 업데이트 필요
- 직접적인 요소 조작으로 인한 성능 오버헤드
- 코드의 가독성과 유지보수성 저하

**반응성 시스템의 장점:**

- 자동 화면 동기화
- 선언적이고 직관적인 상태 관리
- 성능 최적화 및 코드 간소화

#### 3. 컴포넌트 기반 아키텍처

재사용 가능한 컴포넌트를 통해 애플리케이션을 구축하여 코드의 모듈성과 유지보수성을 향상시킵니다.

```text
AFM 데이터 뷰어
├── 검색 컴포넌트 (SearchComponent)
├── 차트 컴포넌트 (ChartComponent)
├── 데이터 테이블 컴포넌트 (DataTableComponent)
└── 태그 컴포넌트 (TagComponent)
```

#### 4. 싱글 파일 컴포넌트 (SFC)

`.vue` 파일 안에 HTML, JavaScript, CSS를 함께 작성하여 컴포넌트 단위의 개발과 관리가 용이합니다.

```vue
<template>
  <!-- HTML 구조 -->
</template>

<script setup>
// JavaScript 로직
</script>

<style scoped>
/* CSS 스타일 */
</style>
```

## 다른 프레임워크와의 비교

### 주요 프레임워크 비교표

| 항목          | Vue.js                  | React                | Angular           |
| ------------- | ----------------------- | -------------------- | ----------------- |
| **개발사**    | Evan You & 커뮤니티     | Meta (Facebook)      | Google            |
| **유형**      | 프로그레시브 프레임워크 | 라이브러리           | 완전한 프레임워크 |
| **학습 곡선** | ⭐⭐ 완만함             | ⭐⭐⭐ 중간          | ⭐⭐⭐⭐ 가파름   |
| **유연성**    | ⭐⭐⭐⭐ 높음           | ⭐⭐⭐⭐⭐ 매우 높음 | ⭐⭐ 구조화됨     |
| **상태 관리** | Pinia, Vuex             | Redux, MobX          | 내장 상태 관리    |
| **커뮤니티**  | ⭐⭐⭐ 성장 중          | ⭐⭐⭐⭐⭐ 매우 활발 | ⭐⭐⭐ 안정적     |

### 자동차로 비유한 프레임워크 특징

#### Vue.js = 현대 아반떼

- 배우기 쉽고 운전하기 편함
- 적당한 가격에 필요한 기능 모두 포함
- 유지보수 비용이 적절함
- 가족용으로 적당함 (중소규모 프로젝트)

#### React = BMW 3시리즈

- 높은 성능과 인지도
- 커스터마이징 옵션이 매우 많음
- 개발 비용이 높을 수 있음
- 프리미엄 브랜드 (대기업 선호)

#### Angular = 벤츠 E클래스

- 안전하고 체계적인 구조
- 모든 기능이 기본으로 포함
- 전문 기술자 필요 (고급 개발자)
- 기업용으로 적합 (대규모 프로젝트)

### Vue.js를 사용하는 주요 기업들

#### 해외 기업

- **Netflix** - 일부 사용자 인터페이스
- **Adobe** - 포트폴리오 관리 도구
- **GitLab** - 메인 웹 애플리케이션
- **Xiaomi** - 공식 웹사이트
- **Alibaba** - 일부 전자상거래 플랫폼
- **Nintendo** - 공식 웹사이트 일부

#### 국내 기업

- **카카오** - 일부 서비스 인터페이스
- **네이버 바이브** - 음악 스트리밍 플랫폼
- **쿠팡플레이** - 동영상 서비스 일부

## 첫 번째 Vue 컴포넌트 만들기

### Hello World 예제

**src/components/HelloWorld.vue 수정**

```javascript
<template>
  <div class="hello">
    <h1>{{ greeting }}</h1>
    <p>현재 카운트: {{ count }}</p>
    <button @click="increment">카운트 증가</button>
  </div>
</template>

<script setup>
import { ref } from "vue";

// ref()로 반응성 데이터 생성
const greeting = ref("Vue3 학습을 시작합니다!");
const count = ref(0);

// 함수에서 .value로 값 접근 및 수정
const increment = () => {
  count.value++; // 이 값이 변경되면 템플릿에 자동 반영
};
</script>

<style scoped>
.hello {
  text-align: center;
  padding: 20px;
}

button {
  background-color: #42b883;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
}

button:hover {
  background-color: #35955f;
}
</style>
```

### 데이터 바인딩 실습

```javascript
<template>
  <div>
    <h2>데이터 바인딩 예제</h2>

    <!-- 텍스트 보간 -->
    <p>메시지: {{ message }}</p>

    <!-- 양방향 바인딩 -->
    <input v-model="message" placeholder="메시지를 입력하세요" />

    <!-- 조건부 렌더링 -->
    <p v-if="message.length > 0">입력한 메시지 길이: {{ message.length }}자</p>

    <!-- 리스트 렌더링 -->
    <ul>
      <li v-for="(item, index) in items" :key="index">
        {{ index + 1 }}. {{ item }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from "vue";

// ref()로 생성된 반응성 데이터
const message = ref("");
const items = ref(["Vue 학습", "Component 만들기", "실습하기"]);
</script>
```

## 개발 환경 문제 해결

### 자주 발생하는 문제들

#### 포트 충돌 문제

```json
// package.json 수정
{
  "scripts": {
    "dev": "vite --port 3000"
  }
}
```

#### npm 패키지 설치 오류

```bash
# 캐시 삭제
npm cache clean --force

# node_modules 삭제 후 재설치
rm -rf node_modules package-lock.json
npm install
```

#### Vite HMR(Hot Module Replacement) 문제

```javascript
// vite.config.js
export default {
  server: {
    watch: {
      usePolling: true, // Windows에서 파일 변경 감지 문제 해결
    },
  },
};
```

#### Windows 환경 고려사항

**PowerShell 실행 정책 설정**

Windows에서 npm 스크립트 실행 시 오류가 발생하는 경우:

```bash
# 관리자 권한으로 PowerShell 실행 후
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**경로 구분자 주의**

Windows에서는 경로 구분자로 백슬래시(`\`)를 사용하지만, import 문에서는 슬래시(`/`)를 사용해야 합니다:

```javascript
// 올바른 예
import HelloWorld from "./components/HelloWorld.vue";

// 잘못된 예 (Windows 경로 스타일)
import HelloWorld from ".\\components\\HelloWorld.vue";
```

## Vue2 vs Vue3 주요 차이점

가장 큰 변화는 Composition API의 도입입니다. Vue2에서는 데이터와 메서드를 각각 data()와 methods 객체에 분리해서 작성했다면, Vue3에서는 setup() 함수 안에서 관련된 로직들을 함께 묶어서 관리할 수 있게 되었습니다. 이는 특히 복잡한 컴포넌트에서 코드의 가독성과 재사용성을 크게 향상시킵니다.

성능 면에서도 상당한 개선이 있습니다. 번들 크기가 최대 41% 줄어들어 애플리케이션 로딩 속도가 빨라졌고, 초기 렌더링 속도는 최대 55% 향상되었습니다. 또한 메모리 사용량도 최대 54% 감소하여 더 효율적인 애플리케이션 개발이 가능합니다.

TypeScript 지원도 크게 강화되었습니다. 타입 추론 기능이 개선되어 개발 중 오류를 사전에 발견하기 쉬워졌고, VS Code 같은 IDE에서의 자동 완성과 오류 감지 기능도 훨씬 정확해졌습니다.

## 추가 학습 권장사항

이 가이드는 Vue.js의 핵심 개념을 간추린 설명이 주를 이루므로, 더 자세한 내용을 학습하기 위해서는 [Vue.js 공식 가이드 (한국어)](https://ko.vuejs.org/guide/introduction.html)를 적극 활용하시길 권장합니다.
