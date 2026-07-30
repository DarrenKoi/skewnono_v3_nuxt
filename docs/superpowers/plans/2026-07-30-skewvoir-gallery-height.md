# Skewvoir Image Gallery Height Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Skewvoir image-list viewport to the remaining workspace height while preserving square thumbnails.

**Architecture:** Keep the change local to `views/Gallery.vue`. Make the gallery panel and its body participate in the existing workspace flex height, then let the single- and set-scope image grids own their internal vertical scrolling instead of stopping at a fixed `34rem` ceiling.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, Tailwind utility classes, `@nuxt/ui`.

## Global Constraints

- Keep every thumbnail square.
- Apply the same height policy to single- and set-scope galleries.
- Do not change image loading, filtering, downloads, enlarged viewing, or evidence behavior.
- Do not modify the shared `PanelFrame.vue` or other Skewvoir views.
- The repository has no Vue mounting harness or automated E2E suite; this CSS-only change uses the user-approved typecheck, existing tests, and running-page visual verification.

---

### Task 1: Expand the image-list viewport

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue:2-6`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue:84-127`

**Interfaces:**

- Consumes: the existing `Workspace.vue` flex height and `PanelFrame.vue` `bodyClass` prop.
- Produces: a gallery panel whose image grid fills available vertical space and scrolls internally.

- [ ] **Step 1: Record the pre-change layout constraint**

Confirm both image grids currently use the fixed class below:

```vue
max-h-[34rem]
```

Confirm `EvidenceCard.vue` owns thumbnail shape through:

```vue
aspect-square
```

- [ ] **Step 2: Make the gallery panel consume available height**

Pass height and overflow utilities to the existing panel without changing the shared component:

```vue
<EbeamSkewvoirPanelFrame
  class="h-full min-h-0"
  body-class="flex min-h-0 flex-col overflow-hidden"
  title="SEM Gallery"
  :meta="frameMeta"
  icon="i-lucide-images"
>
```

- [ ] **Step 3: Let the single-scope content and grid use remaining space**

Change the single-scope wrapper and grid to:

```vue
<div
  v-else-if="analysis.scope.value === 'single'"
  class="flex min-h-0 flex-1 flex-col gap-3"
>
```

```vue
<div
  v-if="filteredEntries.length"
  class="grid min-h-0 flex-1 auto-rows-max grid-cols-2 content-start gap-2 overflow-auto sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
>
```

`auto-rows-max` preserves each square image row's content height, while
`content-start` prevents sparse rows from stretching vertically.

- [ ] **Step 4: Let the set-scope grid use remaining space**

Replace its fixed height ceiling with the same flex and overflow ownership:

```vue
<div
  v-else-if="images.length"
  class="grid min-h-0 flex-1 auto-rows-max grid-cols-3 content-start gap-2 overflow-auto sm:grid-cols-4 xl:grid-cols-6"
>
```

- [ ] **Step 5: Run static and regression verification**

Run:

```bash
/Users/daeyoung/.nvm/versions/node/v24.13.0/bin/node --test "app/**/*.test.ts"
/Users/daeyoung/.nvm/versions/node/v24.13.0/bin/node node_modules/.bin/nuxi typecheck
```

Expected: 897 tests pass, zero failures; typecheck exits with status 0.

- [ ] **Step 6: Verify the running page**

Open both CD-SEM and HV-SEM `skewvoir/analysis` gallery views with a selected measurement and confirm:

- The grid bottom reaches approximately the left-rail `Share` action.
- Thumbnails remain square.
- Single-scope filters remain visible above the independently scrolling grid.
- Set-scope images use the same height policy.
- The workspace does not gain a competing page-level scrollbar.

- [ ] **Step 7: Review the scoped diff**

Run:

```bash
git diff --check
git diff -- front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue
```

Expected: no whitespace errors and no behavioral changes outside gallery layout utilities.
