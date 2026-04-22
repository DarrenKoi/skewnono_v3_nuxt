# Project Memory

- E-beam inventory mock data is consumed through HTTP, not by direct client-side imports of mock objects.
- Phase 1 mock backend is a local Flask server under `back_dev_home/`. Nitro's dev proxy forwards `/api/*` to `NUXT_API_TARGET` (default `http://localhost:5000`); the frontend reads the base path from `runtimeConfig.public.apiBase` (default `/api`). Same wiring carries into Phase 2/3 — only `NUXT_API_TARGET` changes.
- Markdown files under `docs/` and study materials should be written in Korean for teammate sharing.
- For those Markdown documents, use formal sentence endings such as `~입니다.` and `~합니다.` consistently.
