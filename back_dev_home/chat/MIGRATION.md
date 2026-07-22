# chat — office migration

Chat is a **two-swap-surface** feature. The surfaces are independent and are
selected differently — do not conflate them:

| Surface | What swaps | Selector | Office state |
| --- | --- | --- | --- |
| A · LLM gateway | which OpenAI-compatible endpoint generates replies | env vars only (`CHAT_*`) — no code | ready (set env) |
| B · Thread storage | where threads/messages persist | `SKEWNONO_CHAT_PROVIDER` → `providers/office.py` | **stub — not connected** |

## Status

- **LLM 게이트웨이 연결(Surface A):** 환경변수만으로 전환되며 코드 변경이 없습니다.
  사내 게이트웨이는 `back_dev_home/.env`의 `CHAT_BASE_URL`로 지정합니다.
  OpenRouter(home) ↔ 사내 게이트웨이(office)가 동일한 `llm.send_chat` 경로를
  사용하므로, 기능 검증은 게이트웨이와 무관합니다. 2026-07-23 로컬에서 OpenRouter로
  기능 전체(모델 목록·스레드 CRUD·멀티턴 기억·재시작 후 영속성·업스트림 오류 처리)를
  검증 완료했습니다. 사내 게이트웨이 실연결은 사내망에서만 확인할 수 있습니다(집
  네트워크에서는 호스트가 DNS에 없어 도달 불가).
- **스레드 저장소(Surface B):** 미구현입니다. `providers/office_example.py`는 아직
  모든 함수가 `NotImplementedError`를 던지는 뼈대입니다. 승인된 데이터 플랫폼에
  연결하기 전에는 office 저장소 모드를 선택하지 마십시오. chat 페이지는 현재 parked
  상태입니다.

## Rules

- (Surface B only) FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is gitignored
  and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`,
  `config.py`, `llm.py`, `guard.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Surface A needs **no code**. Never hardcode a gateway URL or key in
  `config.py` — the internal URL/key is a 사내 detail and stays out of git; set it
  in `back_dev_home/.env` (gitignored).
- Definition of done: the relevant Verify command at the bottom is green.

## Surface A — LLM gateway (env-only)

`llm.send_chat` POSTs `{model, messages}` to `{CHAT_BASE_URL}/chat/completions`
and reads back `choices[0].message.content` + `usage`. Any OpenAI-compatible
gateway drops in with zero code change.

Env vars (all in `back_dev_home/.env`):

- `CHAT_BASE_URL` — approved internal gateway base URL. The client appends
  `/chat/completions`. Unset → OpenRouter default, which is **blocked** in office
  mode (see guard). Set the internal gateway explicitly at the office.
- `CHAT_API_KEY` — bearer token, sent as `Authorization: Bearer <key>`. If unset,
  no auth header is sent.
- `CHAT_MODELS` — JSON array `[{"id","label"}]`. `id` becomes the request `model`;
  `label` is the picker text. Defaults go stale — set explicitly.
- `CHAT_TIMEOUT` — request timeout in seconds (default `60`).
- `CHAT_BLOCKED_HOSTS` — comma-separated extra hosts to block. Can only **add** to
  the blocklist, never remove.

Gateway contract the internal endpoint must satisfy: `POST {base}/chat/completions`
accepting `{"model": <id>, "messages": [{role, content}, …]}` and returning
`choices[0].message.content`, plus (ideally) `usage.prompt_tokens` /
`usage.completion_tokens` — those are surfaced as per-message metadata alongside
the measured `latency_ms`.

Egress guard (`guard.py`): keyed on **MODE** (`get_mode()`), NOT on
`get_data_provider("chat")`. In office mode it fails closed — a resolved host
matching a known public gateway (`openrouter.ai`, `api.openai.com`,
`api.anthropic.com`, …) is refused before any byte leaves the process, surfaced
as `403 egress_blocked`. The internal gateway is not on the blocklist, so it
passes. **Consequence:** at the office you MUST set `CHAT_BASE_URL` to the
internal gateway; leaving the OpenRouter default will be blocked.

## Surface B — thread storage (office adapter)

Selector: `SKEWNONO_CHAT_PROVIDER` → `get_data_provider("chat")`. Home/mock uses
`providers/mock.py` (SQLite `chat.db` — survives restart, keeps a 30-day archive).
Office must implement `providers/office.py` against the approved store, mirroring
the mock signatures and returning `contracts.py` shapes.

Functions to implement:

- `create_thread(user_id, model, system_prompt=None) -> Thread`
- `list_threads(user_id) -> list[ThreadSummary]` — newest first (`updated_at` desc)
- `get_thread(user_id, thread_id) -> ThreadDetail | None` — messages ordered
  oldest→newest; `None` if the thread is missing or owned by another user
- `rename_thread(user_id, thread_id, title) -> bool`
- `delete_thread(user_id, thread_id) -> bool` — must also delete the thread's messages
- `append_message(thread_id, role, content, meta=None) -> Message` — `meta` carries
  `model` / `prompt_tokens` / `completion_tokens` / `latency_ms`; also bump the
  thread's `updated_at`
- `purge_expired(days=30) -> int` — delete threads (and their messages) whose
  `updated_at` is older than the cutoff; return the count removed

Contracts (`contracts.py`): `Thread`, `ThreadDetail` (= `Thread` + `messages:
list[Message]`), `ThreadSummary`, `Message` (`id, thread_id, role, content,
model|None, prompt_tokens|None, completion_tokens|None, latency_ms|None,
created_at`).

Ownership invariant: every read/write is scoped by `user_id`. `get`/`rename`/
`delete` must never touch another user's thread.

## Critical operational note — the master switch

When `SKEWNONO_DATA_PROVIDER=office` (master switch) is set to give OTHER features
office data, chat **storage** also flips to `providers/office.py` — currently the
`_not_connected` stub — so every thread call raises `NotImplementedError` and the
page breaks. Until Surface B is implemented, pin chat storage to mock:

```bash
SKEWNONO_DATA_PROVIDER=office   # other features → office
SKEWNONO_CHAT_PROVIDER=mock     # chat storage stays on SQLite (works today)
CHAT_BASE_URL=<internal gateway>   # Surface A — generation still uses the env gateway
```

Surface A is unaffected by the provider switch; the two surfaces are orthogonal.

## Endpoints

- `GET /api/chat/models` → `{data: ModelInfo[]}` from `CHAT_MODELS`. No store/LLM call.
- `GET /api/chat/threads` → `{data: ThreadSummary[]}`; runs `purge_expired(30)` first.
- `POST /api/chat/threads` `{model, system_prompt?}` → `{data: ThreadDetail}` `201`;
  `400` if `model` is missing.
- `GET /api/chat/threads/<id>` → `{data: ThreadDetail}`; `404` if not found/owned.
- `PATCH /api/chat/threads/<id>` `{title}` → rename; `400` on blank title, `404` if missing.
- `DELETE /api/chat/threads/<id>` → delete; `404` if missing.
- `POST /api/chat/threads/<id>/messages` `{content}` → persists the user turn, calls
  the LLM, persists the assistant turn, returns `{data: Message}`. Errors: `400`
  blank content, `404` thread, `403 egress_blocked`, `504 gateway_timeout`,
  `502 bad_gateway`. Retry-safe: if the last stored turn is an identical user
  message (a prior failed attempt), the user turn is neither written nor sent twice.

## Verify

Surface A (home — LLM client, config, egress guard):

    .venv/bin/pytest back_dev_home/chat/tests/test_config.py back_dev_home/chat/tests/test_guard.py back_dev_home/chat/tests/test_llm.py

Surface B — mock (home; the full chat suite runs in mock mode):

    .venv/bin/pytest back_dev_home/chat

Surface B — office (ONLY after `providers/office.py` is implemented):

    SKEWNONO_CHAT_PROVIDER=office .venv/bin/pytest back_dev_home/chat

The provider key is `get_data_provider("chat")` → env var `SKEWNONO_CHAT_PROVIDER`.
Run all commands from the repo root.
