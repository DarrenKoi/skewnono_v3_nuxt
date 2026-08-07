# SKEWNONO LLM/RAG 챗봇 도입 타당성 조사

- 조사일: 2026-07-15
- 범위: Nuxt UI Chat template 재사용, 상단 내비게이션 추가, API 기반 LLM 연동, 외부 RAG 서비스 연결
- 전제: GLM-5.2를 포함한 LLM 추론은 OpenAI 호환 API가 제공하며, RAG 구축과 운영은 별도 side project가 담당합니다.

## 1. 결론

도입은 가능합니다. `chat-template.nuxt.dev` 전체를 병합하지 않고, Nuxt UI Chat 컴포넌트와 interaction pattern만 SKEWNONO에 맞게 이식하는 방식을 권장합니다.

LLM 호출은 Flask에서 Python `requests` 기반의 작은 OpenAI-compatible client로 처리합니다. RAG는 이 repository에서 ingestion, chunking, embedding, vector index를 구현하지 않습니다. 별도 RAG 서비스가 검색 근거를 반환하는 HTTP API만 정의하고 연결합니다.

| 항목 | 판정 | 권고 |
| --- | --- | --- |
| 상단 내비게이션에 Chat 탭 추가 | 높음 | 전역 `/chat` direct route를 추가합니다. |
| Nuxt UI Chat 화면 재사용 | 높음 | 현재 설치된 `@nuxt/ui`의 Chat primitive를 사용합니다. |
| 공식 Chat template 전체 병합 | 낮음 | Nitro, OAuth, NuxtHub, Vercel runtime은 가져오지 않습니다. |
| GLM-5.2 및 다른 LLM API 연동 | 높음 | Flask가 OpenAI 호환 `/v1/chat/completions`를 호출합니다. |
| 별도 RAG side project 연결 | 높음 | versioned retrieval-only API를 우선 사용합니다. |
| Flask에서 대화 이력 저장 | 높음 | SQLite로 시작하고 운영 규모에 따라 MongoDB로 이동합니다. |
| 현재 Flask/uWSGI에서 streaming 운영 | 조건부 | timeout, worker 점유, proxy buffering, 취소 전파를 검증합니다. |

권장 구조는 다음과 같습니다.

```text
Nuxt /chat
  -> Flask /api/chat/*
       -> existing identity / ACL / rate policy
       -> conversation history (SQLite first, MongoDB later)
       -> RagClient -> external RAG API /retrieve
       -> prompt + citation builder
       -> LlmClient -> OpenAI-compatible API /v1/chat/completions
  <- normalized answer stream + source citations

Redis      -> active-request lock, rate/quota, cancellation, short cache
OpenSearch -> redacted operational search/observability only
```

RAG 서비스가 준비되기 전에도 일반 LLM chat을 출시할 수 있습니다. 다만 사용자가 RAG mode를 선택한 요청에서 RAG가 실패하면 일반 답변으로 조용히 전환하지 않아야 합니다. 근거가 없는 답변을 근거 기반 답변처럼 보이게 하는 것보다 명시적인 오류나 재시도가 안전합니다.

## 2. Nuxt UI Chat template 적용성

### 2.1 재사용할 부분

공식 [Nuxt AI Chatbot Template](https://github.com/nuxt-ui-templates/chat)은 streaming message, model 선택, 대화 이력, Markdown, 도구 실행 UI의 좋은 참조 구현입니다. 현재 SKEWNONO의 Nuxt UI package에도 다음 Chat 컴포넌트가 포함되어 있습니다.

- `UChatMessages`
- `UChatMessage`
- `UChatPrompt`
- `UChatPromptSubmit`
- `UChatReasoning`
- `UChatTool`
- `UChatPalette`

공식 [Nuxt UI AI Chat 컴포넌트 목록](https://ui.nuxt.com/docs/components/?page=4)도 이 요소들을 Chat UI primitive로 제공합니다. 따라서 message list, prompt, streaming 상태, source 표시를 새로 설계할 필요는 없습니다.

### 2.2 가져오지 않을 부분

공식 template은 Nitro server API, GitHub OAuth, NuxtHub SQLite/Turso, Blob storage, Vercel AI Gateway 등을 전제로 합니다. SKEWNONO는 `ssr: false` SPA와 Flask API, 기존 SSO middleware, Phase별 backend provider seam을 사용합니다.

| Template 요소 | SKEWNONO 적용 방식 |
| --- | --- |
| Chat page/layout | 필요한 UI 구조만 `/chat` page로 이식합니다. |
| Nuxt UI Chat components | 사용합니다. |
| `@ai-sdk/vue` transport | 필수로 도입하지 않습니다. |
| Nitro chat API | Flask `/api/chat/*`로 대체합니다. |
| Vercel AI Gateway | 승인된 OpenAI-compatible LLM API로 대체합니다. |
| GitHub OAuth | 기존 Flask SSO와 `g.user_id`를 유지합니다. |
| NuxtHub/Turso history | Flask가 local SQLite 또는 MongoDB에 저장합니다. |
| Template의 RAG/index 구현 | 가져오지 않고 외부 RAG API를 연결합니다. |

Nuxt UI Chat 타입이 `ai` package의 `UIMessage`를 참조하는 사용 경로가 있으므로, 구현 시 현재 설치 package의 실제 type dependency를 확인해야 합니다. 필요하면 호환되는 `ai` package만 명시적으로 추가하되 Vercel transport 전체를 도입할 필요는 없습니다.

### 2.3 Frontend seam

Chat은 특정 SEM feature가 아니라 전역 기능으로 두는 것이 적합합니다.

- route: `front-dev-home/app/pages/chat.vue`
- components: `front-dev-home/app/components/chat/*`
- API/stream state: `front-dev-home/app/composables/useChatApi.ts`
- top navigation: `front-dev-home/app/components/nav/FeatureTabs.vue`

`chat`을 기존 `FEATURE_SLUGS`에 넣으면 tool type과 FAB를 바꾸는 route rewrite 규칙에 결합될 수 있습니다. `FeatureTabs.vue`가 direct route를 지원하게 하고 `/chat`을 전역 tab으로 추가하는 편이 명확합니다.

Chat page는 다음 layout을 권장합니다.

- `definePageMeta({ lockDesktopPageScroll: true })`를 사용합니다.
- page 전체가 아니라 message viewport만 scroll합니다.
- prompt를 아래에 고정합니다.
- citation을 assistant message 아래의 source card로 표시합니다.
- backend가 반환한 model allowlist만 selector에 표시합니다.
- raw chain-of-thought 대신 `자료 검색 중`, `답변 생성 중` 상태만 표시합니다.

## 3. 책임 경계

### 3.1 SKEWNONO가 담당할 범위

- Nuxt Chat UI와 top navigation
- 로그인 사용자 확인, 권한 scope 생성, request validation
- model registry와 LLM API 호출
- 외부 RAG API 호출과 결과 검증
- retrieved chunk를 사용한 prompt 조립
- answer stream과 citation의 frontend 전달
- 대화 이력, feedback, 사용량과 오류 metadata 저장
- timeout, rate limit, cancellation, audit policy

### 3.2 RAG side project가 담당할 범위

- source 수집, parsing, OCR, chunking
- embedding model과 version 관리
- vector/lexical index, reranking, retrieval tuning
- 원본 갱신, 삭제, 재색인, stale data 처리
- 검색 품질 평가와 corpus lifecycle
- 전달받은 권한 scope에 따른 검색 결과 filtering
- 안정적인 source locator와 corpus version 제공

SKEWNONO는 embedding dimension, OpenSearch mapping, chunk size 같은 RAG 내부 선택을 알 필요가 없습니다. 이 경계는 RAG side project가 OpenSearch, 다른 vector DB, 또는 다른 retrieval framework로 변경되어도 SKEWNONO API를 유지할 수 있게 합니다.

### 3.3 권장 orchestration 소유권

두 가지 연결 방식이 가능합니다.

| 방식 | 설명 | 판정 |
| --- | --- | --- |
| Retrieval-only | RAG API가 chunk와 citation을 반환하고 SKEWNONO가 LLM을 호출합니다. | 권장 |
| Answer API | RAG service가 retrieval과 LLM 답변까지 수행합니다. | 특정 corpus 전용 agent가 필요할 때만 고려 |

Retrieval-only가 현재 상황에 더 적합한 이유는 다음과 같습니다.

- model 선택과 API credential을 SKEWNONO의 기존 정책 안에 둘 수 있습니다.
- RAG 구축과 LLM provider 교체를 서로 독립적으로 진행할 수 있습니다.
- 일반 chat과 RAG chat이 같은 streaming/cost/audit 경로를 사용합니다.
- source와 answer를 별도로 검증할 수 있습니다.

## 4. LLM API client 설계

### 4.1 `requests` 기반 OpenAI-compatible client

Provider SDK 대신 `requests.Session`을 감싼 작은 client를 권장합니다. Requests의 [Session 문서](https://requests.readthedocs.io/en/stable/user/advanced/)는 connection pooling과 keep-alive 재사용을 지원하며, streaming response는 `stream=True`와 `iter_lines()`로 읽을 수 있습니다.

구현 원칙은 다음과 같습니다.

- `back_dev_home/requirements.txt`에 `requests>=2.32,<3`을 직접 명시합니다.
- API key, base URL, upstream model ID는 server-side 설정으로만 관리합니다.
- frontend는 allowlisted logical `model_id`만 전송합니다.
- 각 worker에서 생성된 thread-local `Session`을 사용하고 process 간 Session을 공유하지 않습니다.
- `timeout=(connect_timeout, read_timeout)`을 항상 지정합니다. Requests는 기본 timeout이 없습니다.
- 별도의 전체 request deadline을 두어 streaming이 무한히 유지되지 않게 합니다.
- response를 context manager로 닫고 browser disconnect 시 upstream response도 닫습니다.
- provider의 SSE field를 browser로 그대로 전달하지 않고 SKEWNONO event로 정규화합니다.
- retry는 연결 전 실패 또는 명확히 idempotent한 호출에만 제한합니다. 생성 중 자동 재시도는 답변 중복을 만들 수 있습니다.

`requests`는 blocking client입니다. 현재 Flask/uWSGI가 thread 기반으로 요청을 처리하므로 pilot에는 사용할 수 있지만, 한 streaming request가 한 thread를 점유한다는 제약은 유지됩니다.

### 4.2 Model registry

GLM-5.2를 source code와 frontend에 직접 하드코딩하지 않습니다.

```text
logical_id: glm-5.2-default
display_name: GLM-5.2
base_url: server-side config
upstream_model: provider-specific name
capabilities: streaming, tools, reasoning
data_class: internal-allowed or public-only
```

권장 환경 변수는 다음과 같습니다.

```text
SKEWNONO_LLM_BASE_URL
SKEWNONO_LLM_API_KEY
SKEWNONO_LLM_MODEL_CONFIG
SKEWNONO_LLM_CONNECT_TIMEOUT_SECONDS
SKEWNONO_LLM_READ_TIMEOUT_SECONDS
SKEWNONO_LLM_REQUEST_DEADLINE_SECONDS
```

공식 [GLM-5.2 model card](https://huggingface.co/zai-org/GLM-5.2)와 [vLLM GLM-5.2 recipe](https://recipes.vllm.ai/zai-org/GLM-5.2)는 OpenAI-compatible Chat Completions serving 예제를 제공합니다. 따라서 실제 공급 API가 `/v1/chat/completions` 계약을 만족하면 GLM-5.2와 다른 open-weight model을 같은 client로 처리할 수 있습니다. 정확한 model ID, reasoning field, tool-call format, context limit은 API 운영자별 capability로 확인해야 합니다.

### 4.3 SKEWNONO Chat API

| Method | Path | 역할 |
| --- | --- | --- |
| `GET` | `/api/chat/models` | 로그인 사용자에게 허용된 논리 model 목록을 반환합니다. |
| `GET` | `/api/chat/conversations` | 사용자 자신의 대화 목록을 반환합니다. |
| `GET` | `/api/chat/conversations/:id` | message와 citation을 반환합니다. |
| `POST` | `/api/chat/completions` | history, optional retrieval, LLM generation을 수행합니다. |
| `POST` | `/api/chat/requests/:id/cancel` | 선택 사항으로 active request를 취소합니다. |
| `POST` | `/api/chat/feedback` | 선택 사항으로 answer 평가를 저장합니다. |

Browser가 LLM provider나 RAG service를 직접 호출하면 API key, SSO, ACL, audit를 우회합니다. 두 외부 API 모두 Flask를 통해야 합니다.

### 4.4 Frontend streaming contract

Frontend와 backend는 작은 SSE 또는 NDJSON protocol로 연결할 수 있습니다.

| Event | 주요 필드 | 역할 |
| --- | --- | --- |
| `meta` | request ID, conversation ID, model ID, RAG mode | 요청 시작 정보입니다. |
| `source` | source ID, title, locator, excerpt | retrieval 근거입니다. |
| `delta` | text | assistant 답변 증분입니다. |
| `done` | finish reason, usage, latency | 정상 종료 정보입니다. |
| `error` | safe code, retryable, safe message | stream 중 오류입니다. |

`AbortController`로 frontend 취소를 Flask와 upstream LLM response close까지 전달합니다.

## 5. 외부 RAG 서비스 연결 계약

### 5.1 최소 endpoint

| Method | Path | 역할 |
| --- | --- | --- |
| `GET` | `/health` | liveness/readiness를 확인합니다. |
| `GET` | `/capabilities` | contract version, corpus, filter, limit을 확인합니다. |
| `POST` | `/retrieve` | query와 권한 scope에 맞는 근거 chunk를 반환합니다. |

권장 request 예시는 다음과 같습니다.

```json
{
  "request_id": "chat-request-uuid",
  "query": "질문 본문",
  "top_k": 6,
  "corpus_ids": ["sem-runbooks"],
  "filters": {
    "document_type": ["runbook"]
  },
  "access_scopes": ["group:sem-engineer"],
  "locale": "ko-KR"
}
```

`access_scopes`는 browser 입력을 그대로 전달하지 않고 Flask가 인증 정보에서 생성해야 합니다. RAG service도 service credential과 사용자 scope를 모두 검증해야 합니다.

권장 response 예시는 다음과 같습니다.

```json
{
  "request_id": "chat-request-uuid",
  "contract_version": "1.0",
  "corpus_version": "2026-07-15T03:00:00Z",
  "chunks": [
    {
      "source_id": "runbook-42#section-3",
      "title": "CD-SEM 장애 대응 Runbook",
      "locator": "https://approved-source/runbook-42#section-3",
      "section": "3. 진공 이상",
      "text": "검색된 근거 본문",
      "score": 0.83,
      "metadata": {
        "updated_at": "2026-07-10T02:00:00Z"
      }
    }
  ]
}
```

SKEWNONO는 response schema, chunk 수, 개별/전체 text 길이, 허용 locator scheme을 검증한 뒤 prompt에 넣어야 합니다. `score`는 RAG 내부 model에 종속되므로 SKEWNONO가 고정 threshold 의미를 추정하지 않고 ordering과 표시용 metadata로만 취급하는 것이 안전합니다.

### 5.2 연결 설정

```text
SKEWNONO_RAG_ENABLED
SKEWNONO_RAG_BASE_URL
SKEWNONO_RAG_API_KEY
SKEWNONO_RAG_CONTRACT_VERSION
SKEWNONO_RAG_CONNECT_TIMEOUT_SECONDS
SKEWNONO_RAG_READ_TIMEOUT_SECONDS
SKEWNONO_RAG_MAX_CHUNKS
SKEWNONO_RAG_MAX_CONTEXT_CHARS
```

RAG service-to-service 인증은 static token보다 사내 gateway, mTLS, short-lived credential을 사용할 수 있으면 우선합니다. 어떤 방식을 쓰더라도 secret을 browser와 application log에 노출하지 않습니다.

### 5.3 실패 정책

- RAG가 비활성화된 일반 chat은 LLM만 호출할 수 있습니다.
- RAG mode에서 timeout, schema mismatch, ACL 실패가 발생하면 `rag_unavailable`로 종료합니다.
- UI는 `자료 검색에 실패했습니다`와 재시도 동작을 명확히 표시합니다.
- 일반 LLM answer로의 fallback은 사용자가 명시적으로 선택한 경우에만 새 요청으로 수행합니다.
- circuit breaker가 열리면 RAG 호출을 빠르게 실패시키되 health recovery를 주기적으로 확인합니다.
- source가 없으면 model에게 근거 부족을 알리고, UI에도 `검색 근거 없음`을 표시합니다.

## 6. 저장소 선택과 역할

사용 가능한 SQLite, MongoDB, Redis, OpenSearch를 모두 같은 목적으로 사용할 필요는 없습니다. 각 저장소에 한 가지 명확한 책임을 주는 것이 운영이 단순합니다.

| 저장소 | 초기 역할 | 장기 역할 | 권고 |
| --- | --- | --- | --- |
| SQLite | conversation, message, citation, feedback | 단일 host pilot/소규모 운영 | 첫 선택 |
| MongoDB | 초기에는 불필요 | 다중 instance의 공유 대화 이력과 feedback | 규모 증가 시 이동 |
| Redis | active-request lock, quota/rate counter, cancellation, 짧은 cache | 동일 | 보조 상태만 저장 |
| OpenSearch | redacted usage/error/latency 검색 | 운영 분석 | 대화 원문과 RAG index의 소유 저장소로 사용하지 않음 |

### 6.1 SQLite로 시작

현재 pilot은 Flask local SQLite가 가장 단순합니다. ORM을 먼저 도입하지 않고 Python 표준 `sqlite3`와 작은 repository interface로 시작할 수 있습니다.

권장 table은 다음과 같습니다.

```text
conversations(
  id, user_id, title, selected_model_id,
  rag_mode, created_at, updated_at, deleted_at
)

messages(
  id, conversation_id, role, content,
  model_id, request_id, status,
  input_tokens, output_tokens, latency_ms, created_at
)

message_sources(
  id, message_id, source_id, title, locator,
  section, excerpt, corpus_version, position
)

feedback(
  id, message_id, user_id, rating, reason, created_at
)
```

권장 설정과 주의 사항은 다음과 같습니다.

- DB 파일은 `SKEWNONO_CHAT_DB_PATH`로 지정하고 runtime state directory를 Git에서 제외합니다.
- 한 request 또는 thread가 connection 하나를 소유하게 하고 connection을 thread 간 공유하지 않습니다.
- transaction을 짧게 유지하고 streaming 중 transaction을 열어 두지 않습니다.
- user message를 먼저 저장하고, stream 종료 시 assistant message와 usage를 별도 transaction으로 확정합니다.
- `busy_timeout`을 설정하고 `database is locked`를 관측 가능한 오류로 처리합니다.
- `user_id`, `conversation_id`, `updated_at`에 필요한 index를 둡니다.
- backup, retention, user delete 동작을 pilot 전에 정합니다.

현재 `wsgi.ini`는 4 process와 process당 2 thread를 사용하므로 concurrent write가 발생할 수 있습니다. SQLite [WAL 문서](https://sqlite.org/wal.html)는 WAL의 read/write concurrency 장점과 함께 여러 connection이 동시에 write/checkpoint할 때 영향을 주는 WAL-reset 문제 및 수정 version을 안내합니다. 배포 환경의 `sqlite3.sqlite_version`이 수정 version인지 확인한 뒤 WAL을 사용해야 합니다. 확인되지 않으면 기본 rollback journal과 짧은 write, application-level 직렬화를 우선합니다.

SQLite는 network filesystem이나 여러 application replica가 하나의 DB 파일을 공유하는 운영 형태에는 권장하지 않습니다.

### 6.2 MongoDB로 이동하는 기준

다음 조건이 생기면 history repository 구현을 MongoDB로 교체합니다.

- Flask/chat instance가 여러 host 또는 container로 늘어납니다.
- SQLite write lock이 실제 병목으로 측정됩니다.
- 대화 metadata에 유연한 schema와 운영 query가 필요합니다.
- 별도 worker가 feedback, retention, export를 동시에 처리합니다.

대화와 message를 한 document에 무제한 append하기보다 conversation과 message collection을 분리하는 편이 document growth를 제어하기 쉽습니다. `messages`에는 `{ conversation_id, created_at }`, conversation list에는 `{ user_id, updated_at }` compound index를 권장합니다. 자동 retention이 필요하면 MongoDB [TTL index](https://www.mongodb.com/docs/manual/core/index-ttl/)를 사용할 수 있지만 TTL은 single-field index이므로 보존 정책과 조회 index를 별도로 설계합니다.

### 6.3 Redis의 역할

Redis는 다음 ephemeral state에 적합합니다.

- 사용자별 active generation 1개 lock
- 분당 request와 일별 token quota counter
- cancellation flag와 request idempotency key
- 짧은 model/capability cache와 RAG health cache
- instance가 여러 개일 때의 circuit breaker 상태

Redis를 conversation의 유일한 source of truth로 사용하지 않습니다. eviction, restart, TTL이 대화 이력 손실로 이어지지 않아야 합니다.

### 6.4 OpenSearch의 역할

이 repository의 OpenSearch는 redacted operational event 검색에만 우선 사용합니다.

- model logical ID, RAG corpus ID, source ID
- latency, time-to-first-token, token 수
- safe error code, retry 여부, request 상태
- 사용자 원문 대신 필요한 경우 irreversible hash 또는 승인된 audit ID

Prompt, retrieved chunk, answer 원문을 기본 index에 저장하지 않습니다. RAG side project가 사용하는 vector index는 해당 project가 소유하며, SKEWNONO가 동일 OpenSearch cluster를 직접 조회하지 않습니다.

## 7. Backend module 경계

기존 `routes.py -> data.py -> providers/mock.py|office.py` 규칙을 유지하면 다음 구조가 적합합니다.

```text
back_dev_home/chat/
|-- routes.py
|-- data.py
|-- contracts.py
|-- prompt_builder.py
|-- providers/
|   |-- mock.py
|   `-- office.py
|-- clients/
|   |-- llm.py
|   `-- rag.py
`-- history/
    |-- base.py
    |-- sqlite_store.py
    `-- mongo_store.py
```

- `routes.py`: HTTP validation, auth context, stream response만 담당합니다.
- `data.py`: public use case와 mock/office provider 선택을 담당합니다.
- `clients/llm.py`: `requests` 기반 OpenAI-compatible protocol을 격리합니다.
- `clients/rag.py`: 외부 `/retrieve` 계약, auth, timeout, response validation을 격리합니다.
- `history/base.py`: SQLite와 MongoDB가 공유할 최소 interface를 정의합니다.
- `prompt_builder.py`: retrieval text를 untrusted reference로 명확히 구분합니다.

`routes.py`가 provider-specific field, MongoDB query, OpenSearch DSL을 직접 다루지 않게 해야 합니다.

## 8. 보안과 운영 조건

### 8.1 Guardrail

- LLM과 RAG API key/base URL을 Flask server-side secret으로만 보관합니다.
- 사용자가 임의 endpoint, upstream model, corpus, tool을 지정하지 못하게 합니다.
- `g.user_id`와 승인된 group 정보를 conversation owner와 RAG access scope에 사용합니다.
- conversation 조회와 삭제마다 owner 조건을 적용합니다.
- retrieved text를 명령이 아닌 신뢰하지 않는 자료로 구분하도록 system prompt를 구성합니다.
- prompt, context, answer 원문을 request/access log에 남기지 않습니다.
- input/history/output token, context 크기, source 수, 동시 요청에 hard cap을 둡니다.
- Markdown을 sanitize하고 link scheme을 allowlist로 제한합니다.
- 외부 provider에 전송 가능한 data class를 model registry가 강제합니다.
- 승인되지 않은 외부 LLM이나 RAG provider로 자동 fallback하지 않습니다.

### 8.2 현재 deployment 검증

`wsgi.ini`는 `processes = 4`, `threads = 2`, `harakiri = 60`입니다. 한 blocking streaming chat은 완료될 때까지 thread 하나를 점유합니다.

Pilot 전에 다음을 검증합니다.

- 60초를 넘는 요청이 uWSGI에서 어떻게 종료되는지 확인합니다.
- reverse proxy가 SSE/NDJSON을 buffer하지 않게 설정합니다.
- browser disconnect가 upstream Requests response close로 이어지는지 확인합니다.
- 8개 이상의 동시 chat에서 queue와 기존 API latency를 측정합니다.
- 사용자별 active request를 Redis lock 또는 process-independent 방식으로 제한합니다.
- LLM과 RAG 각각의 timeout, error code, circuit breaker를 분리합니다.

동시 stream이 기존 API를 방해하면 chat orchestration을 별도 service로 분리하는 것이 다음 단계입니다. 처음부터 async stack으로 재작성할 필요는 없지만 load test 결과로 판단해야 합니다.

## 9. 권장 단계

### Phase 0: API 계약과 정책

- LLM base URL, logical/upstream model ID, streaming format을 실제 API로 확인합니다.
- `requests` client의 timeout, deadline, cancellation, normalized event 계약을 정합니다.
- RAG `/capabilities`와 `/retrieve` schema version을 side project와 합의합니다.
- 사용자/group scope, citation locator, corpus ID의 의미를 합의합니다.
- SQLite runtime path, retention, backup, 삭제 정책을 정합니다.

완료 조건은 fake LLM server와 fake RAG server로 정상, timeout, malformed response, ACL 실패를 재현하는 것입니다.

### Phase 1: RAG 없는 vertical slice

- Nuxt UI Chat component로 `/chat` page와 top-nav tab을 만듭니다.
- `GET /api/chat/models`와 `POST /api/chat/completions`를 구현합니다.
- home mock provider가 결정론적인 stream을 반환하게 합니다.
- office provider가 `requests`로 승인된 LLM API를 호출합니다.
- SQLite에 user-owned conversation과 message를 저장합니다.
- Redis가 준비되어 있으면 active-request lock과 quota에만 사용합니다.

완료 조건은 lint/typecheck, backend contract test, 실제 LLM smoke test, 취소/timeout test 통과입니다.

### Phase 2: 외부 RAG connector

- `RagClient`와 retrieval-only 계약을 구현합니다.
- side project 준비 전에는 fake RAG server 또는 contract fixture로 개발합니다.
- source schema, context cap, citation rendering을 검증합니다.
- RAG failure를 명시적으로 표시하고 silent fallback을 금지합니다.
- ACL scope와 cross-user/cross-group 누출을 test합니다.

이 Phase에는 ingestion, chunking, embedding, vector index 구축을 포함하지 않습니다. 완료 조건은 side project의 staging API에 대한 contract test와 대표 질문의 citation 확인입니다.

### Phase 3: 운영 확장

- SQLite lock/latency와 history 용량을 측정해 MongoDB 이동 여부를 결정합니다.
- Redis에 distributed quota, cancellation, circuit breaker를 적용합니다.
- OpenSearch에 redacted latency/error/usage event를 적재합니다.
- 동시 stream load test 결과에 따라 Flask 유지 또는 chat service 분리를 결정합니다.
- 실제 요구가 확인된 경우에만 제한된 read-only tool을 별도 추가합니다.

## 10. 최소 검증 계획

| 계층 | 검증 |
| --- | --- |
| Frontend | stream parser, abort, retry, source card, top-nav route, viewport scroll |
| Flask contract | invalid model, oversized input, unauthenticated user, ownership, stream error |
| LLM client | fake OpenAI-compatible SSE, timeout, 429, 5xx, malformed event, disconnect |
| RAG client | auth header, ACL scope, timeout, schema/version mismatch, empty result, size cap |
| SQLite history | cross-user access, concurrent write, rollback, retention/delete, process restart |
| Security | prompt injection, secret leakage, unsafe locator, external-provider data policy |
| Load | concurrent stream, TTFT, existing API latency, worker exhaustion, cancellation cleanup |

Frontend 구현 후 `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`를 실행합니다. Backend에는 실제 provider를 호출하지 않는 fake LLM/RAG integration test를 우선 추가하고, office에서 별도 smoke test를 실행합니다.

## 11. 구현 전에 확정할 질문

1. 각 LLM API의 base URL, upstream model ID, streaming/reasoning/tool format은 무엇입니까?
2. 내부와 외부 provider가 각각 받을 수 있는 data classification은 무엇입니까?
3. RAG service의 base URL, 인증 방식, contract version은 무엇입니까?
4. Flask가 RAG에 전달할 사용자/group scope의 authoritative source는 무엇입니까?
5. side project가 보장할 corpus ID, source locator, update/corpus version의 의미는 무엇입니까?
6. RAG timeout 또는 근거 없음 상태에서 UI가 제공할 재시도/일반 chat 선택은 무엇입니까?
7. 대화 이력 retention, 삭제, backup, 감사 접근 정책은 무엇입니까?
8. 예상 동시 사용자, 목표 time-to-first-token, 최대 answer 시간은 얼마입니까?

Chunking, embedding model, vector dimension, index mapping은 SKEWNONO 구현 전 확정 질문이 아니라 RAG side project의 내부 설계 사항입니다. 해당 값이 `/retrieve` response 계약을 변경할 때만 contract version으로 조율합니다.

## 12. 최종 권고

다음 vertical slice로 진행하는 것을 권장합니다.

```text
전역 /chat tab
+ Nuxt UI Chat components
+ Flask-authenticated Chat API
+ requests 기반 OpenAI-compatible LlmClient
+ SQLite conversation history
+ deterministic home mock
+ external retrieval-only RagClient contract
```

첫 release는 `RAG_DISABLED` 상태의 LLM chat으로도 완성할 수 있습니다. 이후 side project의 `/retrieve` API가 준비되면 frontend나 LLM provider를 바꾸지 않고 `RagClient`를 활성화합니다. MongoDB는 공유 persistence가 필요할 때, Redis는 ephemeral coordination에, OpenSearch는 redacted operations 분석에 사용하는 구성이 현재 환경에 가장 적합합니다.

## 13. 근거 자료

### 외부 primary sources

- [Nuxt UI Chat template repository](https://github.com/nuxt-ui-templates/chat)
- [Nuxt UI component catalog - AI Chat](https://ui.nuxt.com/docs/components/?page=4)
- [Requests advanced usage](https://requests.readthedocs.io/en/stable/user/advanced/)
- [Requests API reference](https://requests.readthedocs.io/en/stable/api/)
- [Python sqlite3 documentation](https://docs.python.org/3/library/sqlite3.html)
- [SQLite write-ahead logging](https://sqlite.org/wal.html)
- [MongoDB TTL indexes](https://www.mongodb.com/docs/manual/core/index-ttl/)
- [MongoDB index types](https://www.mongodb.com/docs/manual/core/indexes/index-types/)
- [GLM-5.2 official model card](https://huggingface.co/zai-org/GLM-5.2)
- [vLLM GLM-5.2 serving recipe](https://recipes.vllm.ai/zai-org/GLM-5.2)

### 현재 repository evidence

- `front-dev-home/package.json`
- `front-dev-home/nuxt.config.ts`
- `front-dev-home/app/layouts/default.vue`
- `front-dev-home/app/components/nav/FeatureTabs.vue`
- `front-dev-home/app/components/nav/AppHeader.vue`
- `back_dev_home/__init__.py`
- `back_dev_home/_auth/middleware.py`
- `back_dev_home/_runtime/data_provider.py`
- `back_dev_home/requirements.txt`
- `back_dev_home/_infra/opensearch.py`
- `back_dev_home/_infra/redis.py`
- `wsgi.ini`
- `docs/back-end/office-data-adapters.md`
- `docs/development-workflow.md` (이후 삭제 — git 이력에서만 확인 가능합니다)
