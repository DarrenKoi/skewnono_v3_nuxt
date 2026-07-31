# Tool Roster Landing Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 랜딩의 System Status 아래에서 Tool Roster로 이동하고, 전용 페이지 진입 시 자동 조회한 compact 표를 바로 표시합니다.

**Architecture:** 랜딩은 `/tool-roster`로 이동하는 링크만 제공하여 pending-tools API를 호출하지 않습니다. 전용 페이지의 기존 `usePendingTools()` 호출을 즉시 실행 방식으로 바꾸고 idle UI를 제거하며, 기존 집계·복사·CSV 로직은 그대로 둡니다. Topnav의 중복 진입점은 제거하고 표 밀도는 페이지 로컬 Tailwind 및 Nuxt UI slot class로 조정합니다.

**Tech Stack:** Nuxt 4, Vue 3 `<script setup lang="ts">`, Nuxt UI 4, Tailwind CSS 4, Node test runner, ESLint, Nuxt typecheck

## Global Constraints

- 설계 기준은 `docs/superpowers/specs/2026-07-31-tool-roster-landing-entry-design.md`입니다.
- 구현 시작 전에 `superpowers:using-git-worktrees`를 사용하여 `main`에서 격리된 worktree를 만듭니다.
- 여러 세션이 공유하는 기본 작업 트리의 `.remember/**` 변경은 읽거나 stage하거나 커밋하지 않습니다.
- stage와 commit은 각 작업에 적힌 정확한 파일 경로만 사용합니다. `git add -A`, `git add .`, `git commit -a`를 사용하지 않습니다.
- 랜딩 `/`에서는 `/api/sem-list/pending`을 호출하지 않습니다.
- `/tool-roster` URL과 `GET /api/sem-list/pending` 계약은 유지합니다.
- Tool Type 필터, Fab×모델 집계, 드릴다운, IP 복사, CSV 형식은 변경하지 않습니다.
- Vue 컴포넌트 마운팅 테스트와 자동 E2E가 없는 저장소이므로 `.vue` 동작은 typecheck와 실행 앱의 라우팅·네트워크·화면으로 검증합니다.
- Homebrew Node 25가 `libllhttp.9.3.dylib` 불일치로 실행되지 않으므로 모든 npm 명령은 `PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin`을 앞에 붙입니다.

## File Structure

| File | Responsibility |
| --- | --- |
| `front-dev-home/app/utils/headerNav.test.ts` | Tool Roster가 Topnav와 info-path 목록에서 빠진다는 회귀 테스트 |
| `front-dev-home/app/utils/headerNav.ts` | Topnav 링크의 단일 진실 원천에서 `/tool-roster` 제거 |
| `front-dev-home/app/composables/usePendingToolsApi.ts` | 전용 페이지 mount 시 pending-tools 요청 시작 |
| `front-dev-home/app/pages/tool-roster.vue` | 자동 조회 상태 UI, 새로고침, compact 집계표와 드릴다운 |
| `front-dev-home/app/pages/index.vue` | System Status 아래의 `/tool-roster` 이동 버튼 |

---

### Task 1: Topnav의 미연결 장비 진입점 제거

**Files:**

- Modify: `front-dev-home/app/utils/headerNav.test.ts`
- Modify: `front-dev-home/app/utils/headerNav.ts:26-42`

**Interfaces:**

- Consumes: `HEADER_LINKS`, `HEADER_INFO_PATHS`, `isHeaderInfoPath(path: string): boolean`
- Produces: `/tool-roster`가 없는 Topnav 링크 및 info-path 목록

- [ ] **Step 1: 제거 규칙을 나타내는 실패 테스트 작성**

`front-dev-home/app/utils/headerNav.test.ts`의 `/chat` 테스트 다음에 추가합니다.

```ts
test('/tool-roster is reached from the landing page, not the header', () => {
  assert.equal(HEADER_LINKS.some(link => link.to === '/tool-roster'), false)
  assert.equal(HEADER_INFO_PATHS.includes('/tool-roster'), false)
  assert.equal(isHeaderInfoPath('/tool-roster'), false)
})
```

- [ ] **Step 2: 대상 테스트가 기존 구현에서 실패하는지 확인**

Run:

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  node --test front-dev-home/app/utils/headerNav.test.ts
```

Expected: 새 테스트가 `true !== false`로 FAIL합니다.

- [ ] **Step 3: Topnav 링크 제거**

`front-dev-home/app/utils/headerNav.ts`에서 다음 레코드와 바로 위의 network 설명
주석을 제거합니다.

```ts
{ to: '/tool-roster', icon: 'i-lucide-network', label: '미연결 장비' },
```

다른 `HEADER_LINKS`의 순서와 값은 변경하지 않습니다.

- [ ] **Step 4: 순수 내비게이션 테스트 통과 확인**

Run:

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  node --test front-dev-home/app/utils/headerNav.test.ts
```

Expected: `headerNav.test.ts`가 0 failures로 종료합니다. 전체 프론트엔드
테스트는 Task 5에서 별도로 실행합니다.

- [ ] **Step 5: 정확한 두 파일만 커밋**

```bash
git add front-dev-home/app/utils/headerNav.test.ts \
  front-dev-home/app/utils/headerNav.ts
git diff --cached --check
git commit -m "refactor(tool-roster): remove the Topnav entry" \
  -m "Tool Roster is now reached from the landing System Status area, so the global header no longer carries a duplicate icon or info-path entry."
```

---

### Task 2: `/tool-roster` 진입 시 자동 조회

**Files:**

- Modify: `front-dev-home/app/composables/usePendingToolsApi.ts:4-28`
- Modify: `front-dev-home/app/pages/tool-roster.vue:7-58`
- Modify: `front-dev-home/app/pages/tool-roster.vue:230-270`

**Interfaces:**

- Consumes: `usePendingTools()`의 `{ data, status, error, execute }`
- Produces: route mount 시 자동 실행되는 `useAsyncData`와
  `pending | error | success-empty | success-data` 화면 상태

- [ ] **Step 1: 현재 route-entry 동작을 RED acceptance로 기록**

프론트엔드와 mock backend를 실행하고 `/tool-roster`를 새 탭에서 엽니다.

```bash
.venv/bin/python index.py
```

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run dev
```

브라우저에서 다음 기존 동작을 확인합니다.

- 초기 화면에 `전사 장비 명부는 조회 시점에만 불러옵니다.`가 보입니다.
- `/api/sem-list/pending` 요청은 발생하지 않습니다.
- `조회` 버튼을 눌러야 데이터가 나타납니다.

Expected: 세 항목 모두 현재 설계와 반대이므로 acceptance 결과는 FAIL입니다.

- [ ] **Step 2: composable을 route-entry 즉시 실행으로 변경**

`front-dev-home/app/composables/usePendingToolsApi.ts`의 docstring을 다음 내용으로
교체합니다.

```ts
/**
 * The roster tools skewnono cannot reach yet.
 *
 * This composable is used only by `/tool-roster`, so reaching that dedicated
 * route is the user's request to load the full company roster. Fetch on mount,
 * keep the result cached for the session, and expose `execute()` for refresh.
 *
 * The landing page links to the route but never calls this composable, so a
 * landing visit does not touch `v3_df_sem_list`.
 */
```

`useAsyncData` 옵션은 즉시 실행 의도가 명확하도록 다음과 같이 바꿉니다.

```ts
{ immediate: true, default: () => [] as PendingToolRow[] }
```

- [ ] **Step 3: idle 화면과 조회 전용 copy 제거**

`front-dev-home/app/pages/tool-roster.vue`의 헤더 버튼을 다음 고정 새로고침
버튼으로 바꿉니다.

```vue
<UButton
  size="sm"
  color="neutral"
  variant="outline"
  icon="i-lucide-rotate-ccw"
  label="새로고침"
  :loading="status === 'pending'"
  @click="load"
/>
```

idle 전용 주석과 `v-if="status === 'idle'"`의 `AppStatusMessage`를 제거하고,
로딩 분기를 첫 분기로 바꿉니다.

```vue
<AppLoadingState
  v-if="status === 'pending'"
  title="전사 장비 명부를 불러오는 중입니다."
  description="장비 수에 따라 시간이 걸릴 수 있습니다."
/>
```

`statusMessages`는 idle 항목 없이 다음 타입과 내용만 유지합니다.

```ts
const statusMessages = computed<Record<'error' | 'empty', StatusMessageContent>>(() => ({
  error: {
    icon: 'i-lucide-triangle-alert',
    iconClass: 'text-(--sk-bad)',
    title: '명부를 불러오지 못했습니다.',
    description: error.value?.message
  },
  empty: {
    icon: 'i-lucide-check',
    iconClass: 'text-(--sk-ok)',
    title: '명부의 모든 장비가 연결되어 있습니다.'
  }
}))
```

`load()`는 기존처럼 드릴다운 선택을 초기화하고 `execute()`를 호출합니다.

- [ ] **Step 4: 정적 검증 실행**

Run:

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run typecheck
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run lint -- \
  app/composables/usePendingToolsApi.ts app/pages/tool-roster.vue
```

Expected: 두 명령 모두 exit 0입니다.

- [ ] **Step 5: route-entry 동작을 GREEN acceptance로 확인**

브라우저에서 `/tool-roster`를 새로 열고 다음을 확인합니다.

- 첫 요청 동안 `전사 장비 명부를 불러오는 중입니다.`가 표시됩니다.
- 페이지 진입으로 `/api/sem-list/pending` 요청이 한 번 발생합니다.
- 성공하면 별도 `조회` 클릭 없이 필터와 집계표가 표시됩니다.
- 헤더 버튼의 label은 처음부터 끝까지 `새로고침`입니다.
- `새로고침`을 누르면 요청이 한 번 더 발생하며 선택한 드릴다운이 닫힙니다.

Expected: 다섯 항목 모두 PASS합니다.

- [ ] **Step 6: 정확한 두 파일만 커밋**

```bash
git add front-dev-home/app/composables/usePendingToolsApi.ts \
  front-dev-home/app/pages/tool-roster.vue
git diff --cached --check
git commit -m "feat(tool-roster): load the roster on route entry" \
  -m "Entering the dedicated Tool Roster route now starts the pending-tools request immediately. The idle prompt is removed while refresh, errors, empty results, and session caching remain available."
```

---

### Task 3: 랜딩 System Status 아래에 이동 버튼 추가

**Files:**

- Modify: `front-dev-home/app/pages/index.vue:231-250`

**Interfaces:**

- Consumes: Nuxt UI `UButton`의 internal `to` prop
- Produces: `/`에서 `/tool-roster`로 이동하는 `미연결 장비 보기` 버튼

- [ ] **Step 1: 현재 랜딩을 RED acceptance로 확인**

브라우저에서 `/`를 열어 다음을 확인합니다.

- `System Status`와 장비별 `online/total` 연결 현황은 보입니다.
- 그 아래에 `/tool-roster` 이동 버튼은 없습니다.

Expected: 이동 버튼 요구사항이 FAIL합니다. Network 기록에서
`/api/sem-list/pending` 요청은 없어야 합니다.

- [ ] **Step 2: System Status 카드 바로 아래에 버튼 추가**

`front-dev-home/app/pages/index.vue`의 System Status `UCard` 닫는 태그 바로 뒤에
다음을 추가합니다.

```vue
<div class="flex justify-end">
  <UButton
    to="/tool-roster"
    color="neutral"
    variant="outline"
    icon="i-lucide-network"
    trailing-icon="i-lucide-arrow-right"
    label="미연결 장비 보기"
  />
</div>
```

랜딩의 `<script setup>`에는 `usePendingTools()` 또는 pending-tools 관련 import를
추가하지 않습니다.

- [ ] **Step 3: 정적 검증 실행**

Run:

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run typecheck
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run lint -- app/pages/index.vue
```

Expected: 두 명령 모두 exit 0입니다.

- [ ] **Step 4: 랜딩과 페이지 전환을 GREEN acceptance로 확인**

브라우저 Network 기록을 비운 뒤 `/`를 새로 엽니다.

- `System Status` 연결 현황 아래에 `미연결 장비 보기`가 보입니다.
- 랜딩에 머무는 동안 `/api/sem-list/pending` 요청은 0건입니다.
- 버튼을 클릭하면 URL이 `/tool-roster`로 바뀝니다.
- 전환 후 `/api/sem-list/pending` 요청이 발생하고 표가 자동으로 나타납니다.
- Topnav에는 미연결 장비 아이콘이 없습니다.

Expected: 다섯 항목 모두 PASS합니다.

- [ ] **Step 5: 랜딩 파일만 커밋**

```bash
git add front-dev-home/app/pages/index.vue
git diff --cached --check
git commit -m "feat(home): link System Status to Tool Roster" \
  -m "The landing page now exposes the pending-tool workflow directly below connection status without prefetching the full company roster."
```

---

### Task 4: 집계표와 드릴다운 표를 compact 밀도로 변경

**Files:**

- Modify: `front-dev-home/app/pages/tool-roster.vue:96-207`
- Modify: `front-dev-home/app/pages/tool-roster.vue:317-326`

**Interfaces:**

- Consumes: 기존 `matrix`, `cellCount()`, `drilldownRows`,
  `drilldownTableMeta`
- Produces: 콘텐츠 너비 집계표와 compact Nuxt UI 드릴다운 표

- [ ] **Step 1: 현재 표 밀도를 RED acceptance로 기록**

브라우저에서 `/tool-roster`의 전체 필터 표와 한 셀의 드릴다운을 엽니다.
desktop viewport에서 before screenshot을 저장하고 다음을 확인합니다.

- 집계표가 `w-full`로 카드 전체 너비를 채웁니다.
- 집계표 셀은 `px-3`, 본문 `py-1.5`, 헤더·합계 `py-2`입니다.
- 드릴다운 기본 table은 `min-w-full`이고 셀은 `px-3`입니다.

Expected: compact 요구사항이 FAIL합니다.

- [ ] **Step 2: 집계표를 콘텐츠 너비와 작은 패딩으로 변경**

집계표 class를 다음으로 바꿉니다.

```vue
<table class="w-max text-left">
```

집계표의 모든 `th`와 `td`에서 다음 class를 사용합니다.

```text
헤더: py-1.5 px-2
본문: py-1 px-2
합계: py-1.5 px-2
```

기존 `sk-label`, `sk-value`, `sk-value-num`, `text-right` class와 sticky header,
hover, zero-dot, 클릭 버튼은 유지합니다.

- [ ] **Step 3: 드릴다운 UTable의 base 너비와 패딩 축소**

`UTable`에 다음 `ui` prop을 추가합니다.

```vue
:ui="{
  root: 'w-fit max-w-full',
  base: 'min-w-0 w-max'
}"
```

`drilldownTableMeta.class`는 다음 값으로 바꿉니다.

```ts
const drilldownTableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1 px-2 sk-value',
    th: 'py-1.5 px-2 sk-label'
  }
}
```

- [ ] **Step 4: 정적 검증 실행**

Run:

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run typecheck
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run lint -- app/pages/tool-roster.vue
```

Expected: 두 명령 모두 exit 0입니다.

- [ ] **Step 5: compact 표를 GREEN acceptance로 확인**

Task 4 Step 1과 같은 데이터, 필터, viewport로 after screenshot을 저장합니다.

- 집계표는 콘텐츠 너비만 사용하고 남는 카드 폭으로 열을 늘리지 않습니다.
- 헤더, 본문, 합계 행의 패딩이 줄어듭니다.
- 드릴다운도 콘텐츠 너비와 같은 compact 행 밀도를 사용합니다.
- 숫자 셀 버튼, zero-dot, 합계, hover, 드릴다운 선택은 그대로 동작합니다.
- 좁은 viewport 또는 많은 모델 열에서는 바깥 컨테이너가 가로 스크롤합니다.

Expected: 다섯 항목 모두 PASS합니다.

- [ ] **Step 6: Tool Roster 페이지 파일만 커밋**

```bash
git add front-dev-home/app/pages/tool-roster.vue
git diff --cached --check
git commit -m "style(tool-roster): compact the roster tables" \
  -m "The matrix and drill-down now size to their content with tighter cell padding while preserving horizontal scrolling, totals, and drill-down interactions."
```

---

### Task 5: 전체 회귀 검증과 기본 트리 통합

**Files:**

- Verify: `front-dev-home/app/utils/headerNav.test.ts`
- Verify: `front-dev-home/app/utils/headerNav.ts`
- Verify: `front-dev-home/app/composables/usePendingToolsApi.ts`
- Verify: `front-dev-home/app/pages/index.vue`
- Verify: `front-dev-home/app/pages/tool-roster.vue`

**Interfaces:**

- Consumes: Tasks 1-4의 커밋
- Produces: 검증된 `main` fast-forward와 제거된 임시 worktree

- [ ] **Step 1: 전체 프론트엔드 테스트 실행**

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home test
```

Expected: 0 failures입니다.

- [ ] **Step 2: 전체 typecheck 실행**

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run typecheck
```

Expected: exit 0입니다.

- [ ] **Step 3: 전체 ESLint 실행**

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run lint
```

Expected: 이번 변경 파일에 오류가 없습니다. `main`의 기존 무관한 lint 오류가
나오면 파일과 규칙을 기록하고 다음 단계에서 변경 파일만 다시 검사합니다.

- [ ] **Step 4: 변경 파일 ESLint 재확인**

전체 lint가 기존 오류로 실패한 경우에만 실행합니다.

```bash
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:/usr/bin:/bin \
  npm --prefix front-dev-home run lint -- \
  app/utils/headerNav.test.ts \
  app/utils/headerNav.ts \
  app/composables/usePendingToolsApi.ts \
  app/pages/index.vue \
  app/pages/tool-roster.vue
```

Expected: exit 0입니다.

- [ ] **Step 5: 최종 브라우저 시나리오 확인**

새 브라우저 탭에서 `/`부터 시작합니다.

1. 랜딩에서 pending-tools 요청이 없는지 확인합니다.
2. System Status 아래 버튼과 Topnav 아이콘 제거를 확인합니다.
3. 버튼으로 `/tool-roster`에 이동합니다.
4. 진입 요청, 로딩, 자동 표 표시를 확인합니다.
5. Tool Type 필터와 집계 합계를 확인합니다.
6. 셀 드릴다운, IP 복사, CSV 다운로드, 새로고침을 확인합니다.
7. desktop과 좁은 viewport에서 compact 표와 가로 스크롤을 확인합니다.

Expected: 일곱 시나리오가 모두 PASS합니다.

- [ ] **Step 6: diff와 커밋 범위 확인**

```bash
git status --short
git diff --check main...HEAD
git diff --stat main...HEAD
git log --oneline main..HEAD
```

Expected: Tasks 1-4의 다섯 제품·테스트 파일만 변경되며 `.remember/**`는 없습니다.

- [ ] **Step 7: 기본 작업 트리를 fast-forward하고 worktree 제거**

기본 작업 트리에서 현재 `main`이 execution 시작점 그대로인지 확인한 뒤
다음 명령을 실행합니다.

```bash
git merge --ff-only work/tool-roster-landing
git worktree remove ../skewnono-tool-roster-landing
git branch -d work/tool-roster-landing
git worktree list
```

Expected: `main`이 Tasks 1-4 커밋으로 fast-forward되고 임시 worktree와
`work/tool-roster-landing` branch가 제거됩니다. 사용자가 별도로 요청하지
않았으므로 remote push는 실행하지 않습니다.
