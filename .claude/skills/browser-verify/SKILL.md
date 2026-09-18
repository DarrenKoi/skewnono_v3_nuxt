---
name: browser-verify
description: How to verify SKEWNONO in a real browser — agent-browser CLI first, Claude-in-Chrome or Playwright MCP when the situation calls for them; tool-loading, screenshot paths, app URL and LASTUSER identity. Use before any browser check, screenshot, or "does this look right?" review of the Nuxt app.
---

# Browser verification

**Default: `agent-browser`** (user preference, 2026-09-19). It replaced the
Playwright MCP run for the chat attachments check one-for-one: open, fill,
press, `wait --text`, `eval --stdin` for DOM assertions, `screenshot`,
`console`, `close`. Load the `agent-browser` skill first, then
`agent-browser skills get core` for the current command set. Always work in a
named session so a parallel agent cannot hijack the tab:

```bash
export AGENT_BROWSER_SESSION="$(agent-browser session id --scope worktree --prefix verify)"
agent-browser open http://localhost:3000/chat
agent-browser snapshot -i -c          # refs @eN; re-snapshot after navigation
agent-browser fill @e28 "질문" && agent-browser press Enter
agent-browser wait --text "어시스턴트"  # wait on text you KNOW the answer contains
cat <<'EOF' | agent-browser eval --stdin
(() => ({ charts: document.querySelectorAll('.sk-chat-attachment canvas').length }))()
EOF
agent-browser screenshot .playwright-mcp/screenshots/<name>.png
agent-browser console | grep -c "\[error\]"
agent-browser close
```

Gotchas seen so far: `wait --text` times out at 25 s with no partial output,
so wait on a string the mock is guaranteed to emit, not on one branch of it;
a fresh profile has no persisted chart theme, so ECharts may render with a
different theme than your own browser shows — compare structure, not colour,
unless the theme is what you are checking. Identity works with no cookie step
because the dev server's default `LASTUSER` is admin.

The other two remain available — pick by situation:

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
