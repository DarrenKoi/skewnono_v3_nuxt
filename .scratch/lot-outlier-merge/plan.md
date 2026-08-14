# Lot 상세 팝업 outlier 통합 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 디바이스 비교 페이지의 Lot 요약에서, 스텝·recipe 상세와 과다 측정
(outlier) 정보를 오버레이 하나(Lot 상세 모달)에서 함께 읽게 합니다.

**Architecture:** 새 데이터도 새 요청도 없습니다. 페이지가 이미 만들고 있는
`DrillDevice`(recipe grain) 를 모달의 스텝 카드(step grain) 에 `recipe_id` 로
1:N 조인하는 **순수 함수 한 개**를 새로 만들고, 모달이 그것을 받아 배지 ·
펼침 · 필터로 그립니다. 슬라이드오버는 이 페이지에서만 떼고 컴포넌트와 어댑터
(`toOutlierDrill`) 는 그대로 재사용합니다.

**Tech Stack:** Nuxt 4 SPA (`ssr: false`), NuxtUI (`UModal`), Vue 3
`<script setup>`, TypeScript, `node --test` (순수 함수 전용), Tailwind + `--sk-*`
디자인 토큰.

**Spec:** [`spec.md`](spec.md)

## Global Constraints

- 색은 `--sk-*` 토큰과 기존 rose 계열 클래스만 씁니다. 인라인 hex 금지 —
  `DESIGN.md` 가 프런트엔드 시각 언어의 단일 진실 원천입니다.
- 카드 `:key` 는 `recipeStepKey(step)` 입니다. `recipe_id` 를 키로 쓰지 않습니다.
- 초과 총계는 `DeviceOutlierResult.outlier_count` 를 씁니다. 카드 배지의 합이
  아닙니다.
- `분석 제외` 배지와 그 `title` 문구는 recipe 층·파라미터 층 모두 그대로
  옮깁니다.
- 백엔드(`back_dev_home/`) 는 건드리지 않습니다.
- 테스트는 순수 함수만. `npm test` 는 `node --test app/**/*.test.ts` 이고 DOM 도
  마운트 하네스도 없습니다. 컴포넌트 티켓의 검증은 타입체크 + 린트 +
  브라우저 확인입니다.
- 작업 트리: `../skewnono-lot-outlier-merge` (브랜치 `work/lot-outlier-merge`).
  01 티켓 Step 1 에서 만들고, 05 티켓 마지막에 `--ff-only` 병합 후 제거합니다.
- 커밋은 **직접 고친 파일만** 경로로 지정합니다. `git add -A` 금지.

## File Structure

| 파일 | 역할 | 티켓 |
| --- | --- | --- |
| `front-dev-home/app/utils/lotOutlierSteps.ts` | 신규. 스텝 × `DrillDevice` 조인, 필터, 초과 스텝 수. 순수 함수만. | 01 |
| `front-dev-home/app/utils/lotOutlierSteps.test.ts` | 신규. 위의 `node --test` 스위트. | 01 |
| `front-dev-home/app/components/cdsem/comparison/LotDetailModal.vue` | 카드에 배지·펼침 추가, 필터 칩, 헤더 기준선. props 2개 추가. | 02·03 |
| `front-dev-home/app/utils/lotParamExport.ts` | `lotParamFileName` 에 `flagged` 인자 추가. | 03 |
| `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue` | `open-outliers` 수신부를 모달로 돌리고 슬라이드오버 제거. | 04 |
| `front-dev-home/app/components/ebeam/devstat/DrillSlideover.vue` | **변경 없음.** `ComplianceTable` 이 계속 씁니다. | — |
| `front-dev-home/app/utils/deviceDrill.ts` | **변경 없음.** `toOutlierDrill` 을 그대로 씁니다. | — |

## Tasks

각 티켓의 단계별 지시는 `issues/` 아래 파일에 있습니다.

| # | 티켓 | 산출물 | 테스트 |
| --- | --- | --- | --- |
| 01 | [`01-step-outlier-join.md`](issues/01-step-outlier-join.md) | `lotOutlierSteps.ts` — 조인·필터 순수 함수 | `node --test` (TDD) |
| 02 | [`02-modal-outlier-cards.md`](issues/02-modal-outlier-cards.md) | 모달 카드의 `초과 N`·`분석 제외` 배지 + 파라미터 펼침 | 타입체크·린트·브라우저 |
| 03 | [`03-modal-filter-and-baseline.md`](issues/03-modal-filter-and-baseline.md) | `전체 / 초과만` 칩, 헤더 기준선, 내보내기 연동 | `node --test`(파일명) + 브라우저 |
| 04 | [`04-page-rewire.md`](issues/04-page-rewire.md) | 배지 → 모달(`초과만`), 슬라이드오버 제거 | 타입체크·린트·브라우저 |
| 05 | [`05-browser-verify.md`](issues/05-browser-verify.md) | 브라우저 확인 + 병합 + 워크트리 정리 | 손으로 확인 |

## Interfaces (티켓 간 계약)

01 이 만들고 02~04 가 쓰는 이름입니다. 티켓을 순서대로 읽지 않는 사람을 위해
여기 한 벌 모아 둡니다.

```ts
// utils/lotOutlierSteps.ts
export type StepFilter = 'all' | 'flagged'

export interface StepOutlier {
  step: RecipeInfoRow          // 카드가 그리는 스텝 (grain 의 주인)
  drill: DrillRecipe | null    // 같은 recipe_id 의 outlier 정보. 없으면 null
  stepSpan: number             // 이 lot 안에서 같은 recipe_id 를 쓰는 스텝 수
}

export const buildStepOutliers: (
  steps: RecipeInfoRow[],
  device: DrillDevice | null
) => StepOutlier[]

export const filterStepOutliers: (
  cards: StepOutlier[],
  filter: StepFilter
) => StepOutlier[]

export const flaggedStepCount: (cards: StepOutlier[]) => number
```

```ts
// LotDetailModal.vue 가 새로 받는 것
defineProps<{
  /* ...기존 props... */
  drill: DrillDevice | null            // toOutlierDrill 산출물. 페이지가 만듭니다
  outlier: DeviceOutlierResult | null  // median / threshold / outlier_count
}>()
const filter = defineModel<StepFilter>('filter', { default: 'all' })
```

```ts
// utils/lotParamExport.ts (03 에서 인자 하나 추가)
export const lotParamFileName: (
  lotCd: string,
  bucket: string,
  flagged?: boolean
) => string
```

## Self-Review

- **스펙 커버리지** — 목표 4개는 각각 01·02(전체 화면에서 초과 읽기),
  03(토글·기준선), 04(배지 진입점) 에 붙습니다. 결정 D1→03·04, D2→01·02,
  D3→04, D4→03, D5→02.
- **미정 항목 없음** — 01 의 코드는 전문이 티켓에 있고, 02~04 는 붙일 마크업과
  고칠 줄 번호가 적혀 있습니다.
- **이름 정합성** — `StepOutlier.drill` / `stepSpan` / `filterStepOutliers` /
  `flaggedStepCount` 는 01 정의와 02~04 사용처가 같은 철자입니다.
