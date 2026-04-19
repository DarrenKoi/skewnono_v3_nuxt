# Project Memory

- E-beam inventory mock data should be consumed through HTTP, not by direct client-side imports of mock objects.
- In Nuxt development, use a local server route such as `server/routes/mock-api/...` for mock responses and read it through `runtimeConfig.public.apiBase`.
- When switching to Flask, prefer environment-based wiring with `NUXT_PUBLIC_API_BASE=/api` and `NUXT_API_TARGET=<flask-server-url>` so UI fetch flows stay unchanged.
- Markdown files under `docs/` and study materials should be written in Korean for teammate sharing.
- For those Markdown documents, use formal sentence endings such as `~입니다.` and `~합니다.` consistently.
