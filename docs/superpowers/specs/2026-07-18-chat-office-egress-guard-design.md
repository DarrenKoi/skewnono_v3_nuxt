# Chat office egress guard — design

- **Date:** 2026-07-18
- **Feature:** `back_dev_home/chat`
- **Status:** Implemented (2026-07-18)

## Problem

`config.get_base_url()` defaults to `https://openrouter.ai/api/v1`. The base URL is
only swapped by the `CHAT_BASE_URL` env var. If an office deployment forgets to
override that variable, `llm.send_chat()` makes a real outbound request to
`openrouter.ai` — an external host. The company's end-to-end network/DLP
monitoring then notices the external egress and warns about it.

The default **fails open**: a *missing* config silently produces an *external*
call. In the office we want the app itself to **fail closed** — block the call
before any byte leaves the process, so the company monitor is never the thing
that catches it.

## Trigger

Reuse the existing data-provider seam. When `get_data_provider("chat") == "office"`
the app is an office deployment and the egress policy is enforced. Home/mock mode
is unaffected — OpenRouter stays allowed there, which is the whole point of the
offline home phase.

No new phase flag is introduced.

## Enforcement decision

- **Behavior:** hard block. In office mode a request whose resolved host is on the
  blocklist is refused; nothing is sent upstream.
- **Rule:** blocklist. Known public LLM gateways are blocked by name; any other
  host is allowed. This is simpler than an allowlist and accepts one residual
  gap — a brand-new public gateway not on the list would pass through. That
  trade-off was accepted explicitly.

## New component — `back_dev_home/chat/guard.py`

A small module, testable in isolation, that owns the egress policy.

- `DEFAULT_BLOCKED_HOSTS: frozenset[str]` — known public LLM gateways:
  `openrouter.ai`, `api.openai.com`, `api.anthropic.com`,
  `generativelanguage.googleapis.com`, `api.groq.com`, `api.mistral.ai`,
  `api.together.ai`, `api.cohere.com`, `api.perplexity.ai`, `api.deepseek.com`,
  `api.x.ai`.
- `CHAT_BLOCKED_HOSTS` env var — comma-separated hosts that **extend** the
  defaults. It can only add hosts, never remove them, so configuration can only
  tighten the guard, never weaken it.
- `class ChatEgressBlocked(Exception)` — carries a `.message` attribute. Defined
  here (not in `llm.py`) so `guard.py` never imports `llm.py` and there is no
  import cycle.
- `get_blocked_hosts() -> set[str]` — defaults merged with the env additions,
  all lowercased.
- `host_is_blocked(host: str, blocked: set[str]) -> bool` — pure. Case-insensitive.
  Suffix match: a host is blocked when it equals a blocked host or ends with
  `"." + blocked` (so `x.openrouter.ai` is caught).
- `enforce_egress_policy(base_url: str) -> None` — if
  `get_data_provider("chat") == "office"` **and** the URL's host is blocked, emit
  a `logging.warning` and raise `ChatEgressBlocked` with a clear message.
  Otherwise it is a no-op. Host is extracted via
  `urllib.parse.urlparse(base_url).hostname`, lowercased.

## Wiring

- `llm.send_chat()` calls `guard.enforce_egress_policy(config.get_base_url())`
  **before** the `httpx.post`. Placing the check inside the client — not in a
  route or middleware — covers every caller of `send_chat` and guarantees the
  block happens before any network I/O.
- `routes.py` adds one handler:
  `except guard.ChatEgressBlocked as exc: return error_json("egress_blocked", exc.message, 403)`.
  The 403 surfaces in the chat UI with a message such as
  *"OpenRouter is blocked in office mode — configure an approved internal LLM
  gateway (CHAT_BASE_URL)."*

## Error handling / "warning"

Hard block was chosen; the block **is** the warning:

- a `403 egress_blocked` response surfaced in the chat UI, and
- a server-side `logging.warning` in the Flask log.

Nothing silently reaches OpenRouter.

## Testing

New `back_dev_home/chat/tests/test_guard.py`:

- mock mode + `openrouter.ai` → allowed (no raise)
- office mode + default `openrouter.ai` → raises `ChatEgressBlocked`
- office mode + `x.openrouter.ai` (subdomain) → raises
- office mode + `api.openai.com` → raises
- office mode + internal host (e.g. `llm.sknn.local`) → allowed
- office mode + host added via `CHAT_BLOCKED_HOSTS` → raises
- host match is case-insensitive

Integration:

- `test_llm.py`: in office mode with the default URL, `send_chat` raises and
  `httpx.post` is **never called** (assert via monkeypatch).
- `test_routes.py`: sending a message in office mode returns `403 egress_blocked`.

## Out of scope

- Allowlist of approved internal hosts (rejected in favor of the blocklist).
- Connecting the real office LLM gateway / office chat store (tracked separately;
  office store is still a stub).
