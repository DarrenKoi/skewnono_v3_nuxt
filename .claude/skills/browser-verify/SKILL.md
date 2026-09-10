---
name: browser-verify
description: How to verify SKEWNONO in a real browser — choosing Claude-in-Chrome vs Playwright MCP, tool-loading, screenshot paths, app URL and LASTUSER identity. Use before any browser check, screenshot, or "does this look right?" review of the Nuxt app.
---

# Browser verification

Two tools, both fine — pick by situation:

| Situation | Tool |
| --- | --- |
| Reviewing a feature the way I will see it; my real session, cookies, extensions | Claude-in-Chrome (`mcp__claude-in-chrome__*`) |
| Scripted or repeatable driving, precise cookie/identity control, a clean profile | Playwright MCP |

Default to the Chrome extension for "does this look and behave right?"; reach
for Playwright when the check needs a controlled browser rather than mine — e.g.
setting `LASTUSER` per-identity with `addCookies`, or replaying a sequence.
If the extension reports "Browser extension is not connected", switching to
Playwright is a fine answer — just say which one is being used.

- **Chrome extension:** load the tools in **one** `ToolSearch` call
  (`select:…tabs_context_mcp,…navigate,…computer,…read_page,…tabs_create_mcp,…tabs_close_mcp`,
  plus `…read_console_messages` / `…read_network_requests` when debugging), call
  `tabs_context_mcp` first, and close tabs you opened. Console and network
  readers are **not retroactive** — call them before triggering the action.
  Batch click/type/screenshot sequences through `browser_batch`.
  Screenshots return via `computer`'s `save_to_disk`, which names the file itself.
- **Playwright MCP:** pass a relative `filename` under
  `.playwright-mcp/screenshots/` to `browser_take_screenshot` — the server
  resolves relative paths from the project cwd, so omitting it dumps PNGs at
  the repo root. That folder is in `.gitignore`.
- App URL is `http://localhost:3000` (Nuxt takes the next free port when 3000
  is busy — read the dev-server log rather than assuming). Identity is the
  `LASTUSER` cookie: `local-dev` = admin, digits = normal user, `X`-prefix =
  blocked.
