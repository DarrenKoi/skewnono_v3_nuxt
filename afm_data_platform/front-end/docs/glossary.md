# 용어집 (Glossary)

웹 개발에서 자주 나오는 용어들을 쉽게 설명합니다.

## A

### API (Application Programming Interface)
서로 다른 프로그램이 소통하는 방법
- **예시**: 프론트엔드가 백엔드에서 데이터를 가져올 때 사용
- **우리 프로젝트**: `src/dummy/searchApi.js`에서 가짜 API 사용

### App.vue
Vue.js 애플리케이션의 최상위 컴포넌트
- **역할**: 헤더, 메인 내용, 푸터를 조합
- **위치**: `src/App.vue`

## C

### Component (컴포넌트)
재사용 가능한 UI 조각
- **예시**: 버튼, 카드, 헤더
- **파일 확장자**: `.vue`
- **비유**: 레고 블록

### CSS (Cascading Style Sheets)
웹페이지의 디자인과 레이아웃을 담당
- **역할**: 색깔, 크기, 위치 지정
- **예시**: `color: blue`, `font-size: 20px`

## D

### Directive (디렉티브)
Vue.js에서 HTML에 특별한 기능을 추가하는 문법
- **예시**: `v-if`, `v-for`, `v-model`
- **`v-if`**: 조건에 따라 보이기/숨기기
- **`v-for`**: 목록을 반복해서 표시
- **`v-model`**: 입력 필드와 데이터 연결

## F

### Framework (프레임워크)
웹 개발을 위한 기본 구조와 도구들의 모음
- **예시**: Vue.js, React, Angular
- **비유**: 집을 지을 때 사용하는 기본 틀

### Frontend (프론트엔드)
사용자가 직접 보고 상호작용하는 부분
- **기술**: HTML, CSS, JavaScript, Vue.js
- **반대**: Backend (백엔드)

## H

### HTML (HyperText Markup Language)
웹페이지의 구조와 내용을 정의
- **역할**: 제목, 문단, 버튼 등의 요소 배치
- **예시**: `<h1>제목</h1>`, `<button>클릭</button>`

## J

### JavaScript
웹페이지에 동작과 상호작용을 추가하는 프로그래밍 언어
- **역할**: 버튼 클릭 처리, 데이터 계산, API 호출
- **파일 확장자**: `.js`

### JSON (JavaScript Object Notation)
데이터를 주고받을 때 사용하는 형식
```json
{
  "name": "김철수",
  "age": 30,
  "city": "서울"
}
```

## N

### npm (Node Package Manager)
JavaScript 패키지를 관리하는 도구
- **명령어**: `npm install`, `npm run dev`
- **파일**: `package.json`에 설정 저장

## P

### Page (페이지)
사용자가 방문하는 완전한 화면
- **특징**: URL이 있음
- **위치**: `src/pages/` 폴더
- **예시**: 홈페이지, 로그인 페이지

### Props (프롭스)
부모 컴포넌트에서 자식 컴포넌트로 데이터를 전달하는 방법
```vue
<!-- 부모 -->
<ChildComponent :title="제목입니다" />

<!-- 자식 -->
<script setup>
const props = defineProps(['title'])
</script>
```

## R

### Reactive (반응형)
데이터가 변하면 자동으로 화면이 업데이트되는 특성
- **Vue.js**: `ref()`, `reactive()` 사용
- **예시**: 검색어를 입력하면 즉시 결과 표시

### Router (라우터)
URL과 페이지를 연결하는 시스템
- **파일**: `src/router/index.js`
- **예시**: `/` → MainPage, `/result/123` → ResultPage

### Route (라우트)
특정 URL 경로
- **예시**: `/`, `/about`, `/result/data_trend`

## S

### SPA (Single Page Application)
페이지를 새로고침하지 않고 내용만 바뀌는 웹앱
- **장점**: 빠르고 부드러운 화면 전환
- **우리 프로젝트**: Vue.js로 만든 SPA

### Store (스토어)
여러 컴포넌트가 공유하는 데이터 저장소
- **도구**: Pinia
- **위치**: `src/stores/` 폴더
- **예시**: 로그인 정보, 검색 기록

## T

### Template (템플릿)
Vue 컴포넌트의 HTML 부분
```vue
<template>
  <div>
    <h1>{{ title }}</h1>
    <button @click="handleClick">클릭</button>
  </div>
</template>
```

## U

### URL (Uniform Resource Locator)
웹페이지의 주소
- **예시**: `https://example.com/result/123`
- **구성**: 프로토콜 + 도메인 + 경로

## V

### Vue.js
웹 애플리케이션을 만들기 위한 JavaScript 프레임워크
- **특징**: 배우기 쉽고 직관적
- **파일**: `.vue` 확장자 사용

### Vuetify
Vue.js용 UI 컴포넌트 라이브러리
- **제공**: 버튼, 카드, 텍스트 필드 등 미리 만들어진 컴포넌트
- **스타일**: Material Design 기반

## 기호

### @ (At 기호)
`src/` 폴더를 가리키는 별칭
- **예시**: `@/components/Button.vue` = `src/components/Button.vue`

### {{ }} (이중 중괄호)
Vue 템플릿에서 JavaScript 값을 표시
```vue
<template>
  <p>안녕하세요, {{ userName }}님!</p>
</template>
```

### v- (디렉티브 접두사)
Vue.js 디렉티브를 나타내는 접두사
- **예시**: `v-if`, `v-for`, `v-model`, `v-on`

---

## 💡 팁

- **모르는 용어가 나오면**: 이 페이지에서 Ctrl+F로 검색해보세요
- **더 자세한 설명이 필요하면**: [Vue.js 공식 문서](https://vuejs.org/) 참고
- **영어 용어가 어려우면**: 한국어로 설명된 부분을 먼저 읽어보세요