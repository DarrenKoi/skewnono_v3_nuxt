# Frontend 학습 노트 (front-dev-home)

백엔드 개발자 최대영이 `front-dev-home`(Nuxt 4 + NuxtUI + TypeScript) 코드베이스를 공부하기 위한 정리본입니다.

## 학습 개요

`front-dev-home`은 **SKEWNONO** 프로젝트의 Nuxt SPA로, 다음 스택으로 구성되어 있습니다.

- **Nuxt 4.4.2** (Vue 3 기반 프레임워크, `ssr: false` SPA)
- **NuxtUI 4.6.1** (사전 제작 UI 컴포넌트 + Tailwind v4 프리셋)
- **Tailwind CSS 4.1.18** (유틸리티 CSS) — 폰트는 Spoqa Han Sans Neo self-host
- **TypeScript 5.9.3** (정적 타입)
- **ECharts 6.1.0** (데이터 시각화) + **ExcelJS 4.4.0** (엑셀 export)
- **Vite** (Nuxt 내부 번들러. `nuxt.config.ts`의 `vite` 키로 조정)
- **ESLint 9.39.2** + `@nuxt/eslint` (린팅 + 스타일 강제)
- 테스트: **`node --test`**(순수 함수 단위) — 프론트엔드에서 자동화된 테스트는 이것뿐입니다. Vitest·Jest·jsdom은 쓰지 않으며, 자동화된 E2E 스위트도 없습니다(자세히는 `13-testing/`).

> **갱신 메모(2026-07):** 이 학습 노트들은 처음에 초기 ebeam/sem-list 단계(2026-04)를 기준으로 작성됐습니다. 이후 프로젝트가 크게 성장하여(55+ 컴포저블, 프론트 테스트 파일 77개, 백엔드 provider 아키텍처, 차트·웨이퍼 분석 등), 일부 문서를 갱신하고 `10`~`13` 챕터를 새로 추가했습니다. 갱신된 문서에는 이 메모나 "갱신" 표시가 붙어 있습니다.

**데이터 소스에 대한 정정:** 예전 노트는 "Phase 1에는 백엔드가 없고 `app/mock-data/`의 TS 모듈에서 데이터가 온다"고 적었지만, **현재는 세 Phase 모두 Flask 백엔드**(`back_dev_home/`)가 `/api/*`를 서빙합니다. 집(Phase 1)에서는 Flask가 `providers/mock.py`의 결정론적 mock을, 회사(Phase 2/3)에서는 `providers/office.py`가 실제 Redis/OpenSearch를 반환합니다. 프론트엔드 코드는 Phase를 구별하지 않습니다. 백엔드 구조는 `10-backend-providers/`를 보세요.

## 디렉토리 가이드

```text
docs/study/
├── README.md                    (이 파일)
├── 01-typescript/               TypeScript 문법 기본 + 코드에 나온 패턴
├── 02-vue-basics/               Vue 3 Composition API 기본
├── 03-nuxt/                     Nuxt 4의 핵심 개념 (라우팅, 오토임포트, useAsyncData 등)
├── 04-nuxt-ui/                  NuxtUI 컴포넌트 (UCard, UButton, UIcon ...)
├── 05-tailwind/                 Tailwind v4 기본 + 폰트 self-host + 프로젝트 패턴
├── 06-vite-config/              Vite / nuxt.config.ts (프록시·오프라인 아이콘·폰트·포트)
├── 07-code-patterns/            프로젝트 고유 패턴 (composable, store, api 추상화, 캐싱, 영속 상태)
├── 08-eslint-style/             ESLint 규칙과 코드 스타일
├── 09-ui-terminology/           한국 엔지니어 대상 UI 용어/문구 가이드
├── 10-backend-providers/        ★ 백엔드 mock↔office Ports & Adapters (Python/Flask)
├── 11-echarts-dataviz/          ECharts 래퍼·테마·클라이언트 export
├── 12-statistics-wafer/         로버스트 통계(median/MAD)·웨이퍼 물리 좌표 모델
└── 13-testing/                  node:test 순수 함수 규율 + 백엔드 pytest, 그리고 자동화되지 않은 계층
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

**심화 (프로젝트가 성장하며 추가된 챕터):**

10. **`10-backend-providers/`** — 백엔드 개발자라면 여기가 홈그라운드입니다. mock↔office 교체 아키텍처는 이 프로젝트 전체를 관통하는 핵심 패턴이므로, 프론트가 부담스러우면 **여기부터 읽어도 좋습니다.**
11. **`11-echarts-dataviz/`** — 계측 도구의 UI 절반은 차트입니다. ECharts 명령형 API를 Vue 반응성에 잇는 방법.
12. **`12-statistics-wafer/`** — "UI 로직"처럼 보이던 것이 사실은 로버스트 통계와 물리 좌표 변환이라는 것. 도메인 수학의 *이유*.
13. **`13-testing/`** — 순수 함수 + 콜로케이트 테스트 규율. "테스트 가능성 = 좋은 경계"가 아키텍처에 주는 압력.

## `questions.md`

`docs/study/questions.md`에 질문을 추가하시면, 다음 학습 세션에서 그에 대한 답변을 구체적으로 생성합니다. (파일은 이미 존재하며 템플릿과 예시가 들어 있습니다.)

## 참고 레퍼런스

- Nuxt 4 공식 문서: https://nuxt.com/docs
- Vue 3 공식 문서: https://vuejs.org/guide/introduction.html
- NuxtUI 공식 문서: https://ui.nuxt.com
- Tailwind CSS v4 공식 문서: https://tailwindcss.com/docs
- TypeScript 공식 문서: https://www.typescriptlang.org/docs/
- Apache ECharts 공식 문서: https://echarts.apache.org/en/option.html
- Ports & Adapters (Hexagonal Architecture): https://alistair.cockburn.us/hexagonal-architecture/

---

*최초 생성: 2026-04-16 (scheduled task: front-end-study)*
*대규모 갱신: 2026-07-21 — 10~13 챕터 추가, 상태관리·폰트·포트·데이터소스 정정*
