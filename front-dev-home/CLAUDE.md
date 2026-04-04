# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Manager

**Use `bun` for all package management and script execution** (not pnpm/npm/yarn, despite lockfiles present).

## Commands

```bash
bun dev              # Start dev server on http://localhost:3100
bun dev:remote       # Dev server bound to 0.0.0.0 (for remote access)
bun build            # Production build
bun preview          # Preview production build
bun lint             # ESLint
bun typecheck        # Type checking (vue-tsc + nuxt)
bun install          # Install dependencies
```

Dev port can be overridden via `NUXT_PORT` env var.

## Architecture

This is the **Phase 1 (Home/Offline)** workspace of the SKEWNONO project — a Nuxt 3 + NuxtUI 4 frontend for semiconductor metrology tool management. All data comes from mock composables (no backend needed).

### Layouts

- **`hub`** — Landing page layout with simple header/footer (used by `/` index page)
- **`default`** — Main operational layout with `AppHeader` + `ToolTypeTabs` + `FabSidebar` + `FeatureTabs` (used by all tool pages)

### Routing Structure

Routes follow: `/ebeam/{toolType}/{fab?}/{feature?}`

- Tool types: `cd-sem`, `hv-sem`, `verity-sem`, `provision`
- Fabs: `R3`, `M11`, `M12`, `M14`, `M15`, `M16` (dynamic `[fab]` param, lowercase in URL, uppercase in state)
- Features per fab: `index` (dashboard), `analysis`, `monitor`, `reports` (currently only CD-SEM has all four)

### State Management

Uses `useState` composable (not Pinia, despite root CLAUDE.md mentioning it):
- `app/stores/navigation.ts` — Navigation state store via `useState<NavigationState>`, managing category/toolType/fab/favorites/recent
- `app/composables/useNavigation.ts` — Wraps the store with router-aware navigation methods

### Mock Data Pattern (Phase 1)

Composables return **Promises** to mimic fetch API, enabling seamless swap to real API calls later:
- `useEquipmentData()` — Returns equipment data via `Promise.resolve(mockData)`
- `useToolData()` — Static config data for tool types and fabs (not async)

When adding new mock data composables, follow this pattern: export a composable that returns functions returning `Promise<T>`.

### ESLint

Configured via `@nuxt/eslint` with stylistic rules: `commaDangle: 'never'`, `braceStyle: '1tbs'`.

### Backend Proxy

Dev server proxies `/api/*` to `http://127.0.0.1:5000` (overridable via `NUXT_API_TARGET`). Not used in Phase 1 but wired up for Phase 2.

## Code Conventions

- Vue SFCs: `<template>` first, then `<script setup>` — but existing files in this repo use `<script setup>` first. Follow whichever pattern the file already uses.
- Icon set: `@iconify-json/lucide` (use `i-lucide-*` names)
- Tailwind CSS v4 via NuxtUI
