# Chat Agentic RAG Foundation — Design Spec

- **Date:** 2026-07-17
- **Status:** Approved in conversation, pending written-spec review
- **Feature slug:** `chat-agentic-rag-foundation`
- **Implementation scope:** RAG-ready chat refactor and deterministic scaffold

## Goal

Refactor the existing Flask chat feature so an in-process LangChain Deep Agent
can become the chat runtime without coupling Flask routes, conversation
persistence, or the Nuxt frontend to LangChain internals.

The long-term primary knowledge source is an immutable local FAISS index built
from equipment manuals. Manuals contain many pages, diagrams, graphs, and
charts, so retrieved evidence must retain document, page, and visual-region
provenance. OpenSearch and approved company systems provide secondary,
current operational context through read-only tools.

The first implementation is a compatibility foundation. It installs and
exercises Deep Agents with deterministic fake manual evidence, preserves the
current direct chat runtime, and creates explicit office hookup points. It does
not invent company interfaces, OpenSearch mappings, or a production manual
indexing pipeline.

## Current State and Validated Gaps

The current chat feature is a complete non-streaming vertical slice:

- `routes.py` owns thread CRUD and send-message orchestration.
- `data.py` selects the SQLite or office conversation-store adapter.
- `llm.py` calls an OpenAI-compatible `/chat/completions` endpoint.
- The Nuxt `/chat` page supports threads, model selection, system prompts,
  retries, Markdown rendering, copy, and response metadata.
- The 24 backend chat tests pass.

The review found two gaps that this refactor must address:

1. `chat_send_message()` currently combines HTTP behavior, ownership checks,
   retry detection, persistence, prompt construction, model invocation, and
   response mapping. Adding RAG in that route would make it a shallow and
   unstable integration point.
2. The frontend suite currently reports 425 passing tests and two failures.
   `chatMarkdown.test.ts` and `relativeTime.test.ts` import `vitest`, but the
   project test command is Node's built-in test runner and `vitest` is not an
   installed dependency.

The current retry heuristic also treats equal message text as proof that a
request is a retry. Repeating the same legitimate user question can therefore
be misclassified.

## Design Principles

- Flask owns authentication, HTTP behavior, conversation history, and the
  stable frontend contract.
- LangChain and Deep Agents stay behind an in-process runtime seam.
- SQLite or the office conversation store remains the authoritative chat
  history; LangGraph checkpoint state does not become a second source of truth
  in this phase.
- Agent tools expose narrow user questions, not general database clients,
  arbitrary query DSL, host filesystem access, or shell execution.
- Tool authorization scope is injected from Flask identity, never accepted
  from model-generated arguments.
- Manual evidence is citation-first and supports both text and visual pages.
- RAG failures are visible and never silently downgraded to ungrounded direct
  answers.
- Home-to-office transition follows the repository's existing
  `contracts.py` -> `data.py` -> `providers/mock.py|office.py` pattern.

## Considered Approaches

### 1. Runtime seam with direct and Deep Agent adapters — selected

Move send-message behavior into a `ChatOrchestrator`. It invokes a small
`ChatRuntime` interface implemented by the existing direct LLM client and a
new Deep Agent adapter. This gives the seam two real adapters, keeps the route
thin, preserves non-tool-capable models, and makes runtime tests independent
of Flask.

### 2. Replace `llm.send_chat()` with Deep Agents — rejected

This is a smaller initial diff but makes all chat requests depend on LangChain,
tool-calling support, and agent result-state details. It also leaves the route
responsible for orchestration and prevents a safe direct-chat fallback mode.

### 3. Add separate direct-chat and RAG endpoints — rejected

Separate endpoints make runtime choice explicit but duplicate retry,
persistence, error, frontend, and authorization behavior. The runtime is an
implementation choice within one stable chat interface, not a second product
interface.

## Target Feature Tree

The chat tree follows existing provider-backed features such as `sem_list` and
`ebeam/hitachi/storage` while adding feature-local runtime and knowledge
modules:

```text
back_dev_home/chat/
|-- __init__.py
|-- routes.py
|-- contracts.py
|-- data.py
|-- orchestration.py
|-- config.py
|-- providers/
|   |-- __init__.py
|   |-- mock.py
|   `-- office.py
|-- runtime/
|   |-- __init__.py
|   |-- contracts.py
|   |-- data.py
|   `-- providers/
|       |-- __init__.py
|       |-- direct.py
|       `-- deep_agent.py
|-- knowledge/
|   |-- __init__.py
|   |-- contracts.py
|   |-- data.py
|   `-- providers/
|       |-- __init__.py
|       |-- mock.py
|       `-- office.py
|-- tools/
|   |-- __init__.py
|   |-- manuals.py
|   |-- operations.py
|   `-- company.py
|-- __fixtures__/
|-- tests/
`-- MIGRATION.md
```

Responsibilities remain distinct:

- Root `data.py` is only the conversation persistence swap surface.
- `orchestration.py` owns the send-message use case.
- `runtime/data.py` selects direct or Deep Agent execution.
- `knowledge/data.py` selects deterministic mock knowledge or the office FAISS
  manual corpus.
- `tools/` converts domain-oriented questions into calls across stable data
  interfaces.
- Source-specific formats and clients stay inside provider adapters.

## Deep Module Interfaces

### Chat orchestrator

The route calls one deep module interface:

```python
send_message(
    *,
    user_id: str,
    thread_id: str,
    content: str,
    request_id: str,
) -> Message
```

The orchestrator hides ownership validation, idempotency, history assembly,
runtime selection, error translation, and persistence. Flask tests and callers
use this same interface.

### Chat runtime

```python
class RuntimeRequest(TypedDict):
    request_id: str
    thread_id: str
    access_scope: AccessScope
    model: str
    system_prompt: str | None
    messages: list[RuntimeMessage]


class RuntimeResult(TypedDict):
    content: str
    runtime: Literal["direct", "deep_agent"]
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int
    sources: list[SourceRef]
```

`DirectChatRuntime` adapts the current `llm.send_chat()` implementation and
always returns an empty source list. `DeepAgentRuntime` adapts LangChain model
messages, builds the approved tool set, invokes the agent, extracts the final
assistant response and usage metadata, and deduplicates evidence artifacts.

`AccessScope` always contains the authenticated `user_id` and may contain
resolved group and FAB identifiers. The current identity middleware provides
only `g.user_id`, so the first scaffold supplies empty group/FAB collections.
Office activation requires an authoritative access-scope resolver; neither the
frontend nor the model may populate these fields.

### Manual knowledge

The manual corpus exposes two operations:

```python
search_manuals(query, filters, top_k, access_scope) -> list[ManualEvidence]
read_manual_page(document_id, page, access_scope) -> ManualPage
```

`search_manuals` returns small model-facing text plus stable evidence metadata.
`read_manual_page` retrieves one selected rendered page for visual inspection;
it does not allow arbitrary filesystem paths. Both operations enforce hard
limits inside the module rather than trusting model-generated values.

## Request Lifecycle and Idempotency

`POST /api/chat/threads/<thread_id>/messages` accepts `content` and a frontend
generated `request_id`.

1. The route validates the request shape and calls the orchestrator.
2. The orchestrator loads the user-owned thread.
3. If an assistant message already exists for the request ID, it is returned
   unchanged.
4. If no user message exists for the request ID, the user message is stored.
5. The runtime receives the persisted history and authenticated scope.
6. The Deep Agent may retrieve manual evidence and call approved read-only
   operational tools.
7. The runtime returns one normalized result.
8. The assistant message and its source rows are committed atomically.
9. If runtime execution fails, the stored user message remains available for a
   retry using the same request ID.

The message store adds `request_id` and `runtime`. A uniqueness rule on
`(thread_id, request_id, role)` prevents duplicate user or assistant messages
while allowing the paired roles to share one request ID.

## Source and Citation Contract

Assistant messages expose `sources: list[SourceRef]`; direct answers return an
empty list. A source contains only stable, renderable provenance:

```python
class SourceRef(TypedDict):
    source_id: str
    source_type: Literal["manual", "opensearch", "company"]
    title: str
    revision: str | None
    section: str | None
    page: int | None
    region: str | None
    locator: str | None
    snippet: str | None
```

SQLite adds a `message_sources` table keyed to the assistant message. Provider
adapters normalize raw retrieval results to this contract before the
orchestrator sees them.

LangChain tool messages use model-facing `content` for projected evidence and
`artifact` for full source metadata. The runtime collects artifacts after the
agent completes and never depends on the model to reproduce citation metadata
correctly.

The Nuxt `ChatMessage` interface adds `sources`. Assistant messages render
compact source chips containing manual title/revision/page when available.
Artifact download and page-preview endpoints are deferred until the real
manual corpus is connected.

## Manual Corpus and Visual Evidence

FAISS stores vectors and stable chunk identifiers, not original manuals. The
office manual adapter reads an immutable index bundle:

```text
manual-index/<version>/
|-- index.faiss
|-- manifest.jsonl
|-- documents/
|   `-- <document-id>.pdf
`-- pages/
    `-- <document-id>/<page>.png
```

Each manifest record maps a vector ID to document ID, manual revision,
section, page, optional region/bounding box, projected text, and artifact
locator. Text extraction, OCR, chart/table descriptions, and page rendering
occur in a separate offline ingestion workflow. The running Flask application
never mutates or incrementally updates the index.

Index deployment uses a versioned directory and an atomic active-version
switch. This prevents Flask workers from observing a partially rebuilt index.
The office adapter opens the configured active bundle lazily and reuses it
within one worker process.

The retrieval flow is text-first and image-selective:

1. Search text, OCR, and visual descriptions in FAISS.
2. Return the best evidence with page locators.
3. Open only pages the agent judges relevant.
4. Send page images only when the selected model declares vision support.

Models without vision support can still answer from extracted text and visual
descriptions. They do not receive image-only references they cannot inspect.

## Agent and Tool Design

Deep Agents runs inside Flask and receives a LangChain OpenAI-compatible chat
model configured with the existing base URL, API key, and model ID. Deep Agents
and the OpenAI integration use bounded dependency ranges so an upstream major
or Deep Agents minor release cannot silently change the application.

The first implementation uses Deep Agents' state-backed virtual filesystem and
does not grant host filesystem or shell execution. No persistent LangGraph
checkpointer is configured in this phase. Existing SQLite messages are passed
to each invocation as the complete conversation record.

The initial agent has a manual-research tool backed by deterministic fixture
evidence. FAISS, OpenSearch, and company adapters raise explicit unconfigured
errors until their required office settings and contracts exist.

OpenSearch and company tools follow these rules:

- Prefer an existing feature `data.py` interface over querying a source
  directly.
- When a new OpenSearch query is necessary, use `ops_store.OSSearch` inside an
  office adapter.
- Expose one tool per user question shape, never the full `OSSearch` surface or
  raw OpenSearch DSL.
- Company tools call approved internal clients behind read-only adapters.
- No tool accepts user ID, groups, FAB scope, index name, host, credential, or
  arbitrary URL from the model.
- Tool results project only approved fields and enforce row, character, date
  range, page, image-size, iteration, and timeout limits.

## Configuration

Runtime and knowledge selection remain explicit and independent:

```text
SKEWNONO_CHAT_RUNTIME=direct
SKEWNONO_CHAT_RUNTIME=deep_agent

SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=mock
SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office
```

Defaults are `direct` and `mock`. Selecting `deep_agent` requires a configured
tool-capable model. Selecting the office knowledge provider requires a valid
immutable manual-index bundle. Startup in direct/mock mode does not access
FAISS, OpenSearch, or a company endpoint.

Each configured chat model declares `supports_tools` and `supports_vision`.
Deep Agent mode rejects a model without tool support before storing a new user
turn. Page-image tools remain unavailable to models without vision support.

## Error Behavior

Errors retain the repository's `{"error":{"code","message"}}` envelope.

| Failure | HTTP status | Behavior |
| --- | --- | --- |
| Invalid or missing request ID/content | 400 | Reject before persistence |
| Model lacks required tool support | 400 | Explain configuration mismatch |
| Thread missing or not owned | 404 | Do not reveal ownership information |
| Runtime or knowledge provider unconfigured | 503 | Preserve any already-stored user turn |
| Manual/OpenSearch/company timeout | 504 | Report the failed grounded request; no direct fallback |
| Upstream model failure | 502/504 | Preserve user turn for same-ID retry |
| Agent iteration/size limit | 422 | Stop deterministically and expose a safe error |
| Tool authorization denial | 403 | Do not invoke the underlying source |

Logs include request ID, runtime, tool name, duration, result count, source
type, and error class. Logs exclude prompts, answers, retrieved manual text,
page images, company records, secrets, internal hostnames, and credentials.

## Office Migration Contract

`back_dev_home/chat/MIGRATION.md` will make the office transition mechanical.
Before the office knowledge adapter can be activated, the office implementation
must supply and validate:

- manual bundle root and active version selection;
- embedding model identity and dimension matching the FAISS index;
- manifest schema/version and vector-ID mapping;
- PDF and rendered-page artifact locations;
- permitted manual, group, and FAB scopes;
- authoritative group/FAB scope resolver and its missing-identity behavior;
- model tool/vision capabilities;
- approved OpenSearch index aliases, fields, projections, and query limits;
- approved company read clients, methods, field projections, and timeouts;
- maximum index memory, Flask worker count, and per-worker load budget;
- acceptance commands using fake clients plus separate office smoke checks.

Secrets, real company values, internal hosts, raw mappings, and sensitive sample
documents are not committed. The checked-in office adapters remain explicit
stubs until this information is available in the office environment.

## Testing Strategy

Tests use the same interfaces as production callers and never access live
models or office systems.

### Backend

- Preserve all current chat tests.
- Test `ChatOrchestrator` through its public interface with injected fake store
  and runtime adapters.
- Verify request-ID replay, same-text/different-ID messages, user persistence
  on failure, assistant replay, and atomic source persistence.
- Contract-test direct and Deep Agent `RuntimeResult` shapes.
- Run the Deep Agent adapter with a fake LangChain chat model and deterministic
  manual tool; no HTTP model call is allowed.
- Contract-test mock manual search, page lookup, limits, access scope, source
  deduplication, and unconfigured office behavior.
- Verify agent tools cannot override identity scope or access host filesystem,
  shell, arbitrary indexes, or arbitrary URLs.
- Verify direct/mock app startup does not initialize office dependencies.

### Frontend

- Convert the two chat utility tests to `node:test` and `node:assert/strict`,
  matching the configured project runner.
- Test source-chip formatting as a pure utility.
- Run the complete Node test suite, ESLint, Nuxt typecheck, and production
  build.

### Repository gates

- Run the complete backend test suite.
- Run Markdown lint for changed documentation.
- Run `git diff --check`.
- Keep live FAISS, OpenSearch, company-system, and model smoke tests as explicit
  office-only acceptance steps.

## First Implementation Scope

Included:

- runtime and knowledge contracts;
- `ChatOrchestrator` extraction;
- direct and disabled-by-default Deep Agent adapters;
- bounded Deep Agents and LangChain OpenAI dependencies;
- deterministic fake manual retrieval/page evidence;
- request-ID idempotency;
- assistant source persistence and source chips;
- model tool/vision capability validation;
- explicit FAISS/OpenSearch/company office stubs;
- chat migration documentation;
- frontend chat test-runner correction;
- proportional backend and frontend verification.

Deferred:

- production PDF parsing, OCR, visual description, embedding, and FAISS build;
- real FAISS index loading and page artifact serving;
- real OpenSearch query tools and company clients;
- write/action tools of any kind;
- persistent LangGraph checkpoints or long-term agent memory;
- streaming agent progress, tool events, or intermediate reasoning;
- human approval flows, because the first tool set is strictly read-only;
- live office/model smoke tests outside the office environment.

## Definition of Done

The foundation is complete when direct chat behavior remains compatible, Deep
Agent mode can answer through deterministic fake manual evidence with persisted
source references, retries are request-ID idempotent, no tool can write or
escape its approved scope, office adapters fail explicitly until configured,
the documented office migration inputs are sufficient to replace those stubs,
and all required local verification gates pass.
