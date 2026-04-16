# Repository Guidelines

## Project Structure & Module Organization
This repository is an npm-based Nuxt 4 frontend. Keep application code under `app/`:

- `app/pages/` file-based routes such as `ebeam/` and `thickness/`
- `app/components/` shared UI, with navigation pieces in `app/components/nav/`
- `app/layouts/` page shells (`hub`, `default`)
- `app/composables/` data and navigation helpers
- `app/stores/` shared `useState` stores
- `app/assets/css/main.css` global styling
- `app/mock-data/` local mock content for Phase 1
- `public/` static assets such as `favicon.ico`

Generated output lives in `.nuxt/` and `.output/`; do not hand-edit those directories.

## Build, Test, and Development Commands
Use `npm` for all package management and scripts.

- `npm install` installs dependencies
- `npm run dev` starts Nuxt on `http://localhost:3100`
- `npm run dev:remote` binds to `0.0.0.0` for remote access
- `npm run build` creates the production build
- `npm run preview` serves the built app locally
- `npm run lint` runs ESLint
- `npm run typecheck` runs Nuxt/Vue TypeScript checks

CI currently enforces `npm ci`, `npm run lint`, and `npm run typecheck`.

## Coding Style & Naming Conventions
Follow `.editorconfig`: 2-space indentation, LF line endings, UTF-8, and trailing newline. Prefer TypeScript and Vue SFCs. Use PascalCase for component files (`AppHeader.vue`), `useX.ts` for composables (`useNavigation.ts`), and lowercase route folders for pages.

Rely on the Nuxt ESLint config in `eslint.config.mjs`. Stylistic rules already configured include `commaDangle: 'never'` and `braceStyle: '1tbs'`. Match the surrounding file's `<template>` and `<script setup>` ordering instead of reformatting unrelated code.

## Testing Guidelines
There is no dedicated unit or E2E test suite yet. Until one is added, treat `npm run lint` and `npm run typecheck` as required before every PR. For new data-access code, keep the current mock-data pattern: composables should return functions that resolve `Promise<T>` so backend integration can replace mocks later with minimal churn.

## Commit & Pull Request Guidelines
Recent history uses short imperative subjects such as `Add ...`, `Update ...`, and `Rename ...`. Keep commits focused and descriptive; avoid vague messages like `set default`.

PRs should include a concise summary, linked issue when applicable, and screenshots or short recordings for UI changes. Call out route changes, new environment variables such as `NUXT_PORT`, `NUXT_API_TARGET`, or `NUXT_PUBLIC_API_BASE`, and confirm lint/typecheck status in the PR description.
