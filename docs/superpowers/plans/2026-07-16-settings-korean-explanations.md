# Settings Korean Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the About card and show the API token and Appearance supporting text in plain Korean.

**Architecture:** Keep the existing settings components, state, storage, API calls, layout, and accessibility attributes unchanged. Make copy-only edits where each string is currently owned, plus remove the standalone About card from the page.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, `@nuxt/ui`, ESLint, Nuxt type checking

## Global Constraints

- Prefer plain Korean words and short sentences.
- Keep `/api/*` and `Authorization: Bearer ...` unchanged because they are literal API usage forms.
- Keep mode and theme names such as `Light`, `Dark`, `System`, `Default`, `Vintage`, and `Macarons` unchanged.
- Do not change data flow, state storage, API calls, accessibility attributes, or layout.
- Do not translate the remaining API token buttons, tables, dialogs, or status messages in this change.

---

### Task 1: Remove About and translate settings explanations

**Files:**
- Modify: `front-dev-home/app/pages/settings.vue`
- Modify: `front-dev-home/app/components/settings/ApiTokens.vue`
- Modify: `front-dev-home/app/components/settings/ColorModeSelector.vue`
- Modify: `front-dev-home/app/components/settings/EchartThemeSelector.vue`
- Modify: `front-dev-home/app/utils/echartsThemes.ts`

**Interfaces:**
- Consumes: Existing `SettingsApiTokens`, `SettingsColorModeSelector`, `SettingsEchartThemeSelector`, `useColorMode()`, and `useEchartsTheme()` behavior.
- Produces: The same settings UI behavior with the About card removed and supporting explanations shown in Korean.

- [ ] **Step 1: Record the current English copy and About card presence**

Run:

```bash
rg -n "About|Generate a token|Choose how|A bright interface|A low-light interface|Automatically match|Choose the visual style|Selected mode|Selected theme|Keeps the current app behavior|Warm paper-like|High-contrast|Soft pastel|Bold red|Strong primary|Deep red" front-dev-home/app/pages/settings.vue front-dev-home/app/components/settings front-dev-home/app/utils/echartsThemes.ts
```

Expected: Matches appear for the About card and every English explanation targeted by this task.

- [ ] **Step 2: Remove the About card**

Delete the final About `<UCard>` block from `front-dev-home/app/pages/settings.vue`, leaving the Appearance card and API token section unchanged.

- [ ] **Step 3: Translate the API token explanation**

Replace the explanatory paragraph in `front-dev-home/app/components/settings/ApiTokens.vue` with:

```vue
<p class="mb-4 text-sm text-gray-500 dark:text-zinc-400">
  내부 서비스나 스크립트에서 <code class="text-xs">/api/*</code>를 호출하려면 토큰을 만드세요.
  토큰은 <code class="text-xs">Authorization: Bearer ...</code> 헤더에 넣어 사용합니다.
  토큰은 내 계정과 같은 읽기 권한을 가집니다. 유출되면 바로 폐기하세요.
</p>
```

- [ ] **Step 4: Translate color-mode supporting text**

In `front-dev-home/app/components/settings/ColorModeSelector.vue`, keep option labels unchanged and use these strings:

```ts
description: '낮이나 밝은 곳에서 보기 편한 화면입니다.'
description: '어두운 곳에서 눈이 덜 피로한 화면입니다.'
description: '기기의 화면 설정에 맞춰 자동으로 바뀝니다.'
```

Use these template strings:

```vue
<p class="text-sm text-(--sk-ink-muted)">
  이 기기에서 사용할 화면 밝기를 선택하세요.
</p>
<span class="whitespace-nowrap">적용 중: {{ resolvedLabel }}</span>
<p class="sk-meta">
  선택한 모드: {{ selectedLabel }}. 이 설정은 이 브라우저에 저장됩니다.
</p>
```

- [ ] **Step 5: Translate chart-theme supporting text**

In `front-dev-home/app/components/settings/EchartThemeSelector.vue`, use:

```vue
<p class="text-sm text-(--sk-ink-muted)">
  대시보드 차트에 사용할 색상과 모양을 선택하세요.
</p>
<span class="whitespace-nowrap">적용 중: {{ appliedLabel }}</span>
<p class="sk-meta">
  선택한 테마: {{ selectedLabel }}. 이 설정은 이 브라우저에 저장됩니다.
</p>
```

In `front-dev-home/app/utils/echartsThemes.ts`, keep theme labels unchanged and replace descriptions with:

```ts
description: '밝은 화면에서는 Vintage, 어두운 화면에서는 Dark 테마를 자동으로 사용합니다.'
description: '종이처럼 따뜻한 배경에 차분한 빨강, 초록, 황토색을 사용합니다.'
description: '어두운 배경에 밝은 파랑, 초록, 노랑, 빨강을 사용합니다.'
description: '밝고 부드러운 느낌의 연한 색을 사용합니다.'
description: '발표용 차트에 어울리는 선명한 빨강, 청록, 노랑, 주황을 사용합니다.'
description: '업무 보고서에 어울리는 또렷한 기본 색을 사용합니다.'
description: '짙은 빨강과 남색에 차분한 크림색과 초록을 함께 사용합니다.'
```

- [ ] **Step 6: Confirm targeted English copy is gone**

Run the command from Step 1 again.

Expected: No matches. The command exits with status 1 because `rg` found none.

- [ ] **Step 7: Run frontend validation**

Run:

```bash
cd front-dev-home
npm run lint
npm run typecheck
```

Expected: Both commands exit with status 0.

- [ ] **Step 8: Check patch hygiene**

Run:

```bash
git diff --check
git diff -- front-dev-home/app/pages/settings.vue front-dev-home/app/components/settings/ApiTokens.vue front-dev-home/app/components/settings/ColorModeSelector.vue front-dev-home/app/components/settings/EchartThemeSelector.vue front-dev-home/app/utils/echartsThemes.ts
```

Expected: `git diff --check` produces no output. The diff contains only the approved About removal and Korean copy changes in the five target files.

- [ ] **Step 9: Commit the implementation**

Run:

```bash
git add front-dev-home/app/pages/settings.vue front-dev-home/app/components/settings/ApiTokens.vue front-dev-home/app/components/settings/ColorModeSelector.vue front-dev-home/app/components/settings/EchartThemeSelector.vue front-dev-home/app/utils/echartsThemes.ts docs/superpowers/plans/2026-07-16-settings-korean-explanations.md
git commit -m "settings: translate explanations into Korean"
```

Expected: One commit containing only the five implementation files and this plan.
