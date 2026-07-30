# Skewvoir 이미지 갤러리 전체 다운로드 제거 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** `skewvoir/analysis` 이미지 갤러리에서 서비스 부하를 일으킬 수 있는
전체 다운로드 액션을 당분간 제거합니다.

**Architecture:** 변경은 갤러리 Vue 컴포넌트의 표시 계층과 해당 컴포넌트가
소유한 다운로드 작업 상태에만 적용합니다. 백엔드 `/api/msr-images` 작업
API와 공용 `useMsrImageApi` 다운로드 함수는 향후 재공개를 위해 유지합니다.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, `@nuxt/ui`, Node test runner

## Global Constraints

- `전체 다운로드` 버튼과 그 진행률·오류 UI를 갤러리에서 제거합니다.
- 선택 파라미터 묶음 다운로드를 이번 변경에 추가하지 않습니다.
- 백엔드 API와 `useMsrImageApi`의 다운로드 함수는 변경하지 않습니다.
- 갤러리 이미지, 필터, 뷰어와 개별 TIFF 다운로드 동작을 유지합니다.
- `.vue` 컴포넌트용 mounting test harness가 없는 저장소 제약을 따릅니다.
- 변경 파일만 명시적으로 스테이징합니다.

---

### Task 1: 갤러리 전체 다운로드 액션 제거

**Files:**

- Modify:
  `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue:9-73`
- Modify:
  `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue:192-264`

**Interfaces:**

- Consumes: `useMsrImageApi().imageUrl`
- Preserves: `/api/msr-images`, `startDownloadAll`, `pollJob`,
  `DownloadJobStatus`, `downloadErrorMessage`
- Produces: 다운로드 작업을 시작하지 않는 `SEM Gallery` UI

- [ ] **Step 1: 현재 동작과 저장소 테스트 제약을 확인합니다**

`Gallery.vue`의 헤더 액션이 `startDownload`를 호출하고, 컴포넌트가
`startDownloadAll`과 `pollJob`을 소유하는지 확인합니다.

Run:

```bash
rg -n "전체 다운로드|startDownload|startDownloadAll|pollJob|downloadStatus|downloadError" \
  front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue
```

Expected: 버튼, 진행률·오류 블록, 다운로드 작업 상태가 검색됩니다.

이 저장소에는 Vue mounting test harness가 없으므로 삭제 전용 UI 변경을
검증하기 위한 새 source-text test를 만들지 않습니다. 해당 테스트는 실제
사용자 동작을 실행하지 못하는 change detector가 되기 때문입니다. 기존
Node 테스트를 회귀 기준으로 사용하고 typecheck와 변경 파일 ESLint로
컴포넌트 계약을 검증합니다.

- [ ] **Step 2: 전체 다운로드 템플릿을 제거합니다**

`<template #actions>` 전체와 바로 뒤의 `downloadError`,
`downloadStatus?.failures.length` 블록을 삭제합니다. 다음 갤러리 본문인
`<!-- Loading -->`부터는 그대로 유지합니다.

- [ ] **Step 3: 컴포넌트 전용 다운로드 상태를 제거합니다**

다음 import를 삭제합니다.

```ts
import { downloadErrorMessage, type DownloadJobStatus } from '~/composables/useMsrImageApi'
```

API 구조 분해는 이미지 렌더링에 필요한 함수만 남깁니다.

```ts
const { imageUrl } = useMsrImageApi()
```

`// ── Download-all`부터 `watch(focusCtx, ...)` 끝까지 삭제합니다. 아래
`// ── SINGLE scope` 큐 계산부터는 그대로 유지합니다.

- [ ] **Step 4: 제거 범위와 보존 범위를 정적으로 확인합니다**

Run:

```bash
rg -n "전체 다운로드|startDownload|startDownloadAll|pollJob|downloadStatus|downloadError" \
  front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue
```

Expected: exit 1, no matches.

Run:

```bash
rg -n "imageUrl|isTiffName|ImageViewer|ReviewFilters" \
  front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue
```

Expected: 이미지 URL, TIFF 개별 다운로드, 뷰어, 필터 사용이 검색됩니다.

- [ ] **Step 5: 프런트엔드 검증을 실행합니다**

Run:

```bash
/Users/daeyoung/.nvm/versions/node/v24.13.0/bin/node \
  --test "app/**/*.test.ts"
```

Working directory: `front-dev-home/`

Expected: 897 tests, 0 failures.

Run:

```bash
/Users/daeyoung/.nvm/versions/node/v24.13.0/bin/node \
  node_modules/nuxt/bin/nuxt.mjs typecheck
```

Working directory: `front-dev-home/`

Expected: exit 0. 저장소의 `npm run typecheck`와 같은 Nuxt typecheck를
정상 동작하는 Node 24 실행 경로로 실행합니다.

Run:

```bash
/Users/daeyoung/.nvm/versions/node/v24.13.0/bin/node \
  node_modules/eslint/bin/eslint.js \
  app/components/ebeam/skewvoir/views/Gallery.vue
```

Working directory: `front-dev-home/`

Expected: exit 0.

Run:

```bash
git diff --check
git diff -- \
  front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue
```

Expected: 공백 오류가 없고, diff가 전체 다운로드 UI와 전용 상태 제거에만
한정됩니다.

- [ ] **Step 6: 구현을 커밋합니다**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue
git commit -m "fix(skewvoir): remove gallery download-all action" \
  -m "Hide the service-heavy whole-MSR image download action from the analysis gallery. Keep the backend job API and shared client functions available for a later, technically stabilized reintroduction."
```
