# Repository Guidelines

## Project Structure & Module Organization
This repository contains a Nuxt 4 frontend workspace in `front-dev-home/`.
- `front-dev-home/app/pages/`: route-driven views (for example `ebeam/cd-sem/[fab]/index.vue`).
- `front-dev-home/app/components/`: reusable UI pieces (navigation is under `components/nav/`).
- `front-dev-home/app/composables/`: shared Composition API logic (`use*.ts`).
- `front-dev-home/app/stores/`: state modules.
- `front-dev-home/app/assets/css/`: global styles (`main.css`).
- `front-dev-home/public/`: static assets.
- `front-dev-home/app/mock-data/`: local mock/reference content.

## Build, Test, and Development Commands
Run commands from `front-dev-home/`:
- `pnpm install`: install dependencies.
- `pnpm dev`: start local dev server at `http://localhost:3000`.
- `pnpm build`: create a production build.
- `pnpm preview`: serve the production build locally.
- `pnpm lint`: run ESLint checks.
- `pnpm typecheck`: run Nuxt/Vue TypeScript checks.

## Coding Style & Naming Conventions
- Use Vue 3 + TypeScript patterns with Nuxt file-based routing.
- Follow ESLint via `@nuxt/eslint`; do not bypass lint errors.
- Stylistic rules in `nuxt.config.ts` enforce no trailing commas and `1tbs` brace style.
- Prefer 2-space indentation and keep files auto-format-friendly.
- Name composables as `useXxx.ts`, stores by domain (`navigation.ts`), and components in PascalCase (`AppHeader.vue`).
- Keep route files descriptive and colocated by feature (`app/pages/ebeam/...`).

## Testing Guidelines
A dedicated unit test runner is not configured yet. For now, treat `pnpm lint` and `pnpm typecheck` as required pre-merge quality gates. When adding tests, colocate them with features (for example `app/components/nav/AppHeader.test.ts`) and prioritize critical composables/stores.

## Commit & Pull Request Guidelines
Current history uses short, descriptive commit messages (for example `Add hub layout...`, `first front-end commit`). Continue with concise, imperative summaries focused on one change.
- Keep commits scoped and reviewable.
- PRs should include: purpose, key changes, impacted routes/components, and manual verification steps.
- Attach screenshots or short recordings for UI changes.
- Link related issues/tasks when applicable.
