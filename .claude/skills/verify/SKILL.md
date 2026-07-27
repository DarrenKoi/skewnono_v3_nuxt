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

- Rate limit: 10 req / 5 s per user on `/api/*` — space out curl loops or
  vary `LASTUSER`.
- Backend tests: `.venv/bin/python -m pytest tests back_dev_home -q` from the
  repo root (~1320 tests, ~17 s). Both roots are required — `tests/` alone
  skips every `back_dev_home/<feature>/tests/` provider contract suite, which
  is the larger half of the suite. A bare `.venv/bin/python -m pytest -q`
  collects the same set (`testpaths` in root `pyproject.toml`).
- Office gate for one feature (Phase 2, at the office):
  `SKEWNONO_<FEATURE>_PROVIDER=office .venv/bin/python -m pytest back_dev_home/<feature> -q`
  With no `providers/office.py` it fails with a `RuntimeError` naming the
  `cp office_example.py office.py` command — it never falls back to mock, so
  a green run really did hit the office adapter.
- Frontend checks: `npm test` / `npm run lint` / `npm run typecheck` in
  `front-dev-home/`. `npm test` is `node --test "app/**/*.test.ts"` over pure
  functions only.
- There is no automated E2E suite — no Playwright config, no spec files.
  `npx playwright test` ends in `Error: No tests found` (and confusingly
  side-effect-runs the `node:test` files it collected first). Browser
  verification means driving Playwright MCP by hand, as above.
