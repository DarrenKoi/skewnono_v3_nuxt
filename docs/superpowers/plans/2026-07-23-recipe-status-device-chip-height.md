# Recipe Status Device Chip Height Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Increase the vertical space of the Recipe Status `lot_cd` device-code chips without changing adjacent filters or layout behavior.

**Architecture:** Keep the change inside the shared `AnalyticsDevicePicker` presentation component used by Recipe TAT and Fail Issue. Modify only the fixed height utility on the `lot_cd` device buttons, then use static diff review and the existing frontend quality gates to verify scope and correctness.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, Tailwind CSS utilities, ESLint, Nuxt TypeScript checks

## Global Constraints

- Change only the `lot_cd` device-code button height from `h-6` to `h-7`.
- Preserve category-filter chip height, horizontal padding, typography, gaps, wrapping, scrolling, and selection behavior.
- Keep the shared behavior across Recipe TAT and Fail Issue.

---

### Task 1: Increase Device-Code Chip Height

**Files:**

- Modify: `front-dev-home/app/components/ebeam/AnalyticsDevicePicker.vue:58`
- Test: Static template inspection plus existing frontend lint and typecheck commands

**Interfaces:**

- Consumes: Existing `chipStrip`, `selectedLot`, `chipClass()`, and `toggleLot()` bindings.
- Produces: The same device-picker interface and behavior with a `h-7` device-code chip height.

- [ ] **Step 1: Confirm the current scoped styling**

Run:

```bash
rg -n 'class="inline-flex h-6 shrink-0' front-dev-home/app/components/ebeam/AnalyticsDevicePicker.vue
```

Expected: one match on the `v-for="device in chipStrip"` button.

- [ ] **Step 2: Apply the minimal template change**

Change the device button class from:

```vue
class="inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-2 font-mono text-[11px] font-medium ring-1 transition-colors"
```

to:

```vue
class="inline-flex h-7 shrink-0 items-center gap-1 rounded-md px-2 font-mono text-[11px] font-medium ring-1 transition-colors"
```

- [ ] **Step 3: Verify the diff is limited to the intended class**

Run:

```bash
git diff --check -- front-dev-home/app/components/ebeam/AnalyticsDevicePicker.vue
git diff -- front-dev-home/app/components/ebeam/AnalyticsDevicePicker.vue
```

Expected: no whitespace errors and a one-line `h-6` to `h-7` replacement.

- [ ] **Step 4: Run frontend quality gates**

Run from `front-dev-home/`:

```bash
npm run lint
npm run typecheck
```

Expected: both commands exit successfully with no errors.

- [ ] **Step 5: Commit the implementation if publishing is requested**

```bash
git add front-dev-home/app/components/ebeam/AnalyticsDevicePicker.vue
git commit -m "style(recipe-status): increase device chip height"
```

Do not include unrelated working-tree changes in the commit.
