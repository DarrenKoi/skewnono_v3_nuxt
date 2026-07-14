---
name: verify
description: Build/launch/drive recipe for verifying changes in the running SKEWNONO app (Flask mock + Nuxt SPA).
---

# Verifying SKEWNONO changes end-to-end

## Launch (often already running — check first)

```bash
lsof -iTCP -sTCP:LISTEN -P | grep -E ":3000|:5050"
```

- Backend: `.venv/bin/python index.py` → Flask on `http://localhost:5050`
  (PORT env overrides; 5000 conflicts with macOS AirPlay). Debug mode is on
  at home, so backend edits hot-reload — no restart needed.
- Frontend: `cd front-dev-home && NUXT_API_TARGET=http://localhost:5050 npm run dev`
  → Nuxt on `http://localhost:3000`, Nitro proxies `/api/*` to Flask.

## Drive

- Identity is the `LASTUSER` cookie (home phase). Fastest API-level check:
  `curl -b "LASTUSER=<id>" http://localhost:3000/api/...` (goes through the
  Nitro proxy, same as the app).
- Browser flows: Playwright MCP. Set identity via
  `page.context().addCookies([{name:'LASTUSER', value:'<id>', url:'http://localhost:3000'}])`,
  then navigate. Clear with `context().clearCookies({name:'LASTUSER'})`.
- Useful identities: `local-dev` = home admin; any digits = normal user;
  `X...` prefix = blocked by access control (see `/admin/access`).
- Screenshots: always pass a relative filename under
  `.playwright-mcp/screenshots/` (CLAUDE.md convention).

## Gotchas

- Rate limit: 20 req / 5 s per user on `/api/*` — space out curl loops or
  vary `LASTUSER`.
- Backend unit tests: `.venv/bin/python -m unittest discover tests`
  (stdlib unittest; pytest is not installed).
- Frontend checks: `npm run lint` / `npm run typecheck` in `front-dev-home/`.
