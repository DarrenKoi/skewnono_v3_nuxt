# Chat Feature — Design Spec

- **Date:** 2026-07-17
- **Status:** Approved (design), pending implementation plan
- **Feature slug:** `chat`

## Goal

Add a full chat page to SKEWNONO. At **home (Phase 1)** it talks to
**OpenRouter** (many models, including free ones) so chat features can be tested.
At **office/prod (Phase 2/3)** it talks to the **company internal LLM**
(GLM-5.2, Kimi-2.6, …). The internal gateway is **OpenAI-compatible**, so the
swap is configuration-only — no code change — consistent with the cross-phase
principle in `CLAUDE.md`.

## Requirements (from brainstorming)

- **Non-streaming** for v1 (lowest common denominator; works on any
  OpenAI-compatible endpoint whether or not it supports streaming).
- **Multi-turn conversations** — thread history is re-sent to the LLM each turn
  ("checkpoint" = reopen a past conversation and keep talking).
- **Long-term memory** = a **30-day archive** of all conversations, read
  **offline** to study user style/questions and to enhance RAG later. It is
  **never injected into prompts at runtime**.
- **Full chat page** with a thread sidebar.
- **User-selectable model** per conversation, list driven by config per phase.
- **RAG is out of scope** here; this feature only produces the archive RAG will
  later consume.

## Chosen approach

**Thin custom store** (not LangGraph). "Checkpoint" reduced to *multi-turn
history* and "long-term memory" reduced to *a retained, queryable archive* —
both satisfied by a single message store. LangGraph's checkpointer/store would
add a heavy dependency and a state model that does not match the existing
`provider` seam, for capabilities not required by v1. If agentic RAG later
demands graph flows, LangGraph can be introduced *inside the office provider*
without disturbing this design.

## Architecture

### Two independent swap surfaces

| Surface | Home | Office/Prod | Swap mechanism |
| --- | --- | --- | --- |
| **Storage** | SQLite file | OpenSearch | Provider seam (`SKEWNONO_CHAT_PROVIDER`), mirrors `afm` |
| **LLM endpoint + model list** | OpenRouter | Internal gateway | Pure config (env vars), same client code |

The LLM client is **not** a provider seam — both phases run identical
OpenAI-compatible code; only env values differ.

### Feature layout (mirrors `back_dev_home/afm/`)

```text
back_dev_home/chat/
  __init__.py          # re-exports bp
  routes.py            # blueprint + handlers
  data.py              # storage seam: delegates to selected provider
  contracts.py         # Thread, Message shapes
  llm.py               # OpenAI-compatible client (shared, config-driven)
  config.py            # resolves CHAT_BASE_URL / key / CHAT_MODELS / timeout
  providers/
    __init__.py
    mock.py            # SQLite implementation (home)
    office.py          # OpenSearch stub -> _not_connected() until wired
  tests/
    test_contract.py
```

### SQLite schema (home; `back_dev_home/chat/chat.db`, gitignored)

```sql
threads(
  id TEXT PRIMARY KEY,
  user_id TEXT,
  title TEXT,
  model TEXT,
  system_prompt TEXT,
  created_at TEXT,
  updated_at TEXT
)

messages(
  id TEXT PRIMARY KEY,
  thread_id TEXT,                 -- FK -> threads.id
  role TEXT,                      -- user | assistant | system
  content TEXT,
  model TEXT,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  latency_ms INTEGER,
  created_at TEXT
)
```

### Storage seam interface (`data.py`, all scoped by `user_id` via `g.user_id`)

- `list_threads(user_id)` -> thread summaries (also runs `purge_expired`)
- `create_thread(user_id, model, system_prompt=None)` -> thread
- `get_thread(user_id, thread_id)` -> thread + messages (owner-checked)
- `rename_thread(user_id, thread_id, title)`
- `delete_thread(user_id, thread_id)`
- `append_message(thread_id, role, content, meta)` -> message
- `purge_expired(days=30)` -> retention sweep

### Retention

`purge_expired(30)` deletes threads (and their messages) whose `updated_at`
is older than 30 days. Called at app startup and opportunistically on
`list_threads`. No scheduler. SQLite `DELETE WHERE updated_at < now-30d` is
cheap. Office/OpenSearch can use an ILM policy later.

## API endpoints (`/api/chat`, all scoped to `g.user_id`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/chat/models` | Models the active phase exposes (from `CHAT_MODELS`) |
| GET | `/chat/threads` | List user's threads (also triggers `purge_expired`) |
| POST | `/chat/threads` | Create `{model, system_prompt?}` |
| GET | `/chat/threads/<id>` | Thread + full message history |
| PATCH | `/chat/threads/<id>` | Rename `{title}` |
| DELETE | `/chat/threads/<id>` | Delete thread |
| POST | `/chat/threads/<id>/messages` | Send `{content}` -> assistant reply |

### Orchestration flow — `POST /chat/threads/<id>/messages`

```text
1. load thread + history from store           (404 if not owned by user)
2. persist the user message                   <- BEFORE the LLM call
3. payload = [system_prompt?] + history + new user msg
4. reply = llm.send_chat(thread.model, payload)   <- only network call
5. persist assistant message (content, tokens, latency_ms)
6. touch thread.updated_at
7. return the assistant message
```

Persisting the user message **before** the LLM call and the assistant message
only **on success** means a timeout/error never loses the user's input — the
frontend offers Retry from saved history.

## LLM client & configuration

`llm.py` is stateless. `send_chat(model, messages)` issues
`POST {CHAT_BASE_URL}/chat/completions` via `httpx` and returns
`{content, prompt_tokens, completion_tokens, latency_ms}`. No `stream` flag in
v1.

### Environment variables

```text
CHAT_BASE_URL   # home: https://openrouter.ai/api/v1   office: http://internal-llm/v1
CHAT_API_KEY    # office key; at home falls back to OPENROUTER_API_KEY (see below)
CHAT_MODELS     # JSON list: [{"id":"...","label":"..."}]
CHAT_TIMEOUT    # seconds, default 60
```

- **Key resolution:** `config.py` reads `CHAT_API_KEY`, falling back to the
  existing **`OPENROUTER_API_KEY`** already present in `back_dev_home/.env`.
  Home works with the key already on disk; office sets `CHAT_API_KEY`.
- **`.env` loading:** the app does **not** currently load `.env`
  (no `load_dotenv` anywhere). This feature adds `python-dotenv` and calls
  `load_dotenv()` at startup so the key is actually read. New dependency:
  `python-dotenv` (added to `requirements.txt`).
- **`CHAT_MODELS`:** home lists free OpenRouter model ids; office lists
  GLM-5.2, Kimi-2.6. `/chat/models` reflects whatever the active phase exposes.

## Error handling

All failures return the standard `error_json(code, message, status)` shape.

| Failure | Status | Frontend behavior |
| --- | --- | --- |
| LLM timeout / network error | 504 | Error bubble + Retry (user msg preserved) |
| LLM non-200 (bad key/model) | 502 | Error bubble with gateway message |
| Thread not found / not owned | 404 | Redirect to new chat |
| Empty content | 400 | Inline composer validation |

## Frontend

```text
front-dev-home/app/pages/chat.vue
front-dev-home/app/composables/useChatApi.ts
front-dev-home/app/components/chat/
  ChatSidebar.vue        # thread list + New chat; delete on hover
  ChatThread.vue         # message bubbles (user/assistant/error)
  ChatComposer.vue       # textarea + send; Enter=send, Shift+Enter=newline
  ChatMessage.vue        # one bubble; assistant shows tokens + latency
  ModelPicker.vue        # dropdown from /chat/models
  SystemPromptField.vue  # collapsible per-thread system prompt editor
```

- **Layout:** two-pane. Left sidebar (thread list, active highlighted, New chat,
  delete on hover). Right pane: collapsible system-prompt field at top ->
  scrolling message list -> composer pinned at bottom with the model picker.
- **Data flow:** `useChatApi()` exposes `useThreads()` (shared cache key
  `'chat-threads'`, per `useSemList()` pattern), plus `sendMessage`,
  `createThread`, `deleteThread`, `renameThread`, `fetchModels`.
- **Sending:** optimistically append the user bubble -> show a pending "..."
  assistant bubble -> replace on reply; on error swap to an error bubble + Retry.
- **Nav:** wire `chat.vue` into existing nav; nav *structure* unchanged.

## v1 feature set

**In:** thread sidebar + delete, thread rename, per-thread model picker,
per-thread system prompt, latency/token display per reply.

**Deferred:** auto-title (fallback label = first ~40 chars of first user
message), streaming, copy-message button.

## Testing (mirrors `afm/tests/test_contract.py`)

- Store CRUD + `purge_expired` 30-day boundary against a temp SQLite file.
- Orchestration flow with a **faked `llm.send_chat`** (no network): asserts
  user-msg-persisted-before-call, assistant-msg-persisted-on-success,
  user-msg-preserved-on-LLM-error.
- Contract test: response shapes match `contracts.py`.
- Office provider raises `_not_connected()` until wired (matches `afm/office.py`).

## Out of scope

- **RAG** — prepared separately; this feature only produces the 30-day archive
  it will consume.
- **Streaming** — deferred; non-streaming client only.
- **Long-term-memory-into-prompt** — archive is read offline, never injected.
- **Auth** — reuses existing identity middleware (`g.user_id`); no new auth.

## Housekeeping

- Add `back_dev_home/chat/chat.db` (and `*.db`) to `.gitignore`.
- Add `python-dotenv` to `back_dev_home/requirements.txt`; call `load_dotenv()`
  at app startup.
