# Frontend 학습 노트 (front-dev-home)

백엔드 개발자 최대영이 `front-dev-home`(Nuxt 4 + NuxtUI + TypeScript) 코드베이스를 공부하기 위한 정리본입니다.

## 학습 개요

`front-dev-home`은 **SKEWNONO** 프로젝트의 Phase 1(오프라인 집에서 개발) 단계로, 다음 스택으로 구성되어 있습니다.

- **Nuxt 4.4.2** (Vue 3 기반 풀스택 프레임워크)
- **NuxtUI 4.6.1** (사전 제작 UI 컴포넌트 + Tailwind v4 프리셋)
- **Tailwind CSS 4.1.18** (유틸리티 CSS)
- **TypeScript 5.9.3** (정적 타입)
- **Vite** (Nuxt 내부 번들러. 별도 설정 없이 `nuxt.config.ts`의 `vite` 키로 조정)
- **ESLint 9.39.2** + `@nuxt/eslint` (린팅 + 스타일 강제)

Phase 1이라 백엔드가 없고, 모든 데이터가 `app/mock-data/`의 TS 모듈에서 오지만, `fetch` 계층은 나중에 Flask로 바꿀 수 있도록 설계되어 있습니다.

## 디렉토리 가이드

```text
docs/study/
├── README.md                    (이 파일)
├── 01-typescript/               TypeScript 문법 기본 + 코드에 나온 패턴
├── 02-vue-basics/               Vue 3 Composition API 기본
├── 03-nuxt/                     Nuxt 4의 핵심 개념 (라우팅, 오토임포트, useAsyncData 등)
├── 04-nuxt-ui/                  NuxtUI 컴포넌트 (UCard, UButton, UIcon ...)
├── 05-tailwind/                 Tailwind v4 기본 + 프로젝트에서 쓰는 패턴
├── 06-vite-config/              Vite / nuxt.config.ts 설정 해설
├── 07-code-patterns/            프로젝트 고유 패턴 (composable, store, api 추상화)
├── 08-eslint-style/             ESLint 규칙과 코드 스타일
└── 09-ui-terminology/           한국 엔지니어 대상 UI 용어/문구 가이드
```

## 학습 순서 추천

백엔드 개발자 관점에서 이해 난이도 순으로 읽는 것을 권합니다.

1. **`01-typescript/`** — Python 백엔드에서 넘어왔다면 가장 먼저 타입 시스템을 이해해야 합니다. Union 타입, interface, generics를 숙지하세요.
2. **`02-vue-basics/`** — Vue 3 Composition API(`ref`, `computed`, `<script setup>`)를 익힙니다. 백엔드 관점에서는 "상태 = 데이터", "반응형 = 데이터가 바뀌면 UI가 자동 업데이트"로 이해하면 편합니다.
3. **`03-nuxt/`** — 파일 기반 라우팅, 오토 임포트, `useAsyncData`, `$fetch` 등 Nuxt가 Vue 위에 얹는 편의 기능들입니다. Flask의 Blueprint가 URL → 함수 매핑을 수동으로 하는 반면 Nuxt는 파일 구조로 자동 매핑합니다.
4. **`07-code-patterns/`** — 실제 이 프로젝트에서 composable(`useEbeamToolApi`)과 store(`useNavigationStore`)를 어떻게 설계했는지 이해합니다. Phase 2/3 이식을 위한 API 추상화 레이어가 핵심입니다.
5. **`04-nuxt-ui/`** — 사용 중인 NuxtUI 컴포넌트 카탈로그.
6. **`05-tailwind/`** — 유틸리티 CSS의 작동 원리와 프로젝트에서 자주 쓰는 클래스.
7. **`06-vite-config/`** — 빌드 도구 설정 파일의 해석.
8. **`08-eslint-style/`** — 커밋 전 지켜야 할 규칙들.
9. **`09-ui-terminology/`** — 현장 엔지니어가 실제로 보게 되는 한글 UI 문구 기준.

## `questions.md`

`docs/study/questions.md`에 질문을 추가하시면, 다음 학습 세션에서 그에 대한 답변을 구체적으로 생성합니다.
현재 세션에서는 `questions.md`가 존재하지 않아 답변 생성은 건너뜁니다.

## 참고 레퍼런스

- Nuxt 4 공식 문서: https://nuxt.com/docs
- Vue 3 공식 문서: https://vuejs.org/guide/introduction.html
- NuxtUI 공식 문서: https://ui.nuxt.com
- Tailwind CSS v4 공식 문서: https://tailwindcss.com/docs
- TypeScript 공식 문서: https://www.typescriptlang.org/docs/

---

*생성일: 2026-04-16 (scheduled task: front-end-study)*
