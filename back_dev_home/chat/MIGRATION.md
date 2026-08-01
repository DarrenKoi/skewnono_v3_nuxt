# Chat office RAG 전환 가이드

이 문서는 사내 coding LLM이 현재 Flask/Nuxt 계약을 변경하지 않고 chat RAG 연결점을
구현하기 위한 handoff 계약입니다. 실제 hostname, credential, index alias, raw mapping,
사내 sample 문서 및 원문은 저장소에 commit하지 않습니다.

## 현재 경계와 선택 matrix

Chat에는 서로 독립적인 선택점이 있습니다. 한 선택점의 값을 다른 선택점의 준비
상태로 간주하지 않습니다.

| 경계 | 선택값 | 역할 | 준비되지 않았을 때의 동작 |
| --- | --- | --- | --- |
| LLM gateway | `CHAT_BASE_URL`, `CHAT_API_KEY`, `CHAT_MODELS` | OpenAI-compatible model endpoint와 capability를 선택합니다. | Office mode에서 public gateway는 egress guard가 차단합니다. |
| Runtime | `SKEWNONO_CHAT_RUNTIME=direct` | Retrieval tool 없이 기존 대화 경로를 실행합니다. | Knowledge provider를 호출하지 않습니다. |
| Runtime | `SKEWNONO_CHAT_RUNTIME=agent` | 네 read-only retrieval tool을 제한된 횟수로 실행합니다. | `supports_tools=false` model은 user turn 저장 전에 `400`으로 거절합니다. |
| Knowledge | `SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=mock` | Synthetic fixture를 결정적으로 검색합니다. | Office source나 network가 필요하지 않습니다. |
| Knowledge | `SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office` | 사내 read-only index를 검색합니다. | Adapter 또는 설정이 없으면 `503`이며 mock으로 전환하지 않습니다. |
| Scope | `SKEWNONO_CHAT_SCOPE_PROVIDER=mock` | 제한된 deterministic classifier를 사용합니다. | Office dependency가 필요하지 않습니다. |
| Scope | `SKEWNONO_CHAT_SCOPE_PROVIDER=office` | 승인된 사내 scope classifier를 사용합니다. | Adapter가 없으면 `503`이며 mock으로 전환하지 않습니다. |
| Thread storage | `SKEWNONO_CHAT_PROVIDER=mock` | SQLite에 thread, turn, source, trace, feedback을 저장합니다. | 기본 보존 기간은 30일입니다. |
| Thread storage | `SKEWNONO_CHAT_PROVIDER=office` | 승인된 사내 저장소를 사용합니다. | `providers/office.py`가 없으면 명시적 office 선택은 boot 단계에서 실패합니다. Stub copy는 호출 시 실패합니다. |

권장 전환 순서는 `direct/mock/mock` baseline, `agent/mock/mock` synthetic RAG,
`agent/office/mock` knowledge integration, `agent/office/office` scope integration
순서입니다. Thread storage는 RAG 전환과 독립적으로 검증합니다. 장애 시 runtime 또는
provider 값을 명시적으로 되돌리며, 요청 중 자동 fallback은 구현하지 않습니다.

`SKEWNONO_CHAT_PROVIDER`만 generic feature-provider selector이며 thread 저장소를
선택합니다. `SKEWNONO_CHAT_KNOWLEDGE_PROVIDER`와
`SKEWNONO_CHAT_SCOPE_PROVIDER`는 chat 내부 lazy selector입니다. 따라서 두 selector를
`office`로 설정해도 gitignored adapter copy가 없다는 이유만으로 Flask boot가 실패하지
않습니다. 해당 scope 또는 knowledge 경로를 처음 호출할 때 typed `503`을 반환하며
mock으로 fallback하지 않습니다. 단 두 selector의 raw 값은 boot에서 먼저 검증하며,
`mock` 또는 `office`가 아닌 값은 명확한 `RuntimeError`로 startup을 중단합니다.

## Agent server-side bound

아래 bound는 model이나 office adapter가 변경할 수 없는 application-owned 설정입니다.

| 환경 변수 | 기본값 | Code hard maximum | 적용 의미 |
| --- | --- | --- | --- |
| `SKEWNONO_CHAT_MAX_TOOL_CALLS` | 6 | 12 | 한 agent invocation의 전체 tool call 수입니다. |
| `SKEWNONO_CHAT_MAX_CONCURRENT_AGENT_RUNS` | 4 | 32 | 한 process에서 동시에 실행하거나 timeout 뒤 남아 있을 수 있는 agent worker 수입니다. |
| Tool별 result 수 | 5 | 5 | 각 knowledge search 결과를 application이 다시 제한합니다. |
| `SKEWNONO_CHAT_MAX_SNIPPET_CHARS` | 1200 | 4000 | 각 source snippet을 tool content와 artifact 생성 전에 자릅니다. |
| `SKEWNONO_CHAT_MAX_EVIDENCE_CHARS` | 12000 | 40000 | Invocation 전체의 model-facing tool content 문자 예산입니다. |
| `SKEWNONO_CHAT_AGENT_TIMEOUT` | 60초 | 120초 | Model과 tool round 전체를 포함하는 wall-clock deadline입니다. |

Snippet 상한은 model 입력과 저장/API `SourceRef`에 동일하게 적용합니다. Aggregate
evidence 상한을 넘으면 `422 runtime_limit_exceeded`, 전체 invocation deadline을 넘으면
`504 gateway_timeout`입니다. 두 경우 모두 user turn만 유지하고 assistant, source,
tool trace를 저장하지 않습니다. Deadline 뒤 background graph 결과도 conversation
store에 접근하지 못하며 나중에 assistant turn을 추가하지 않습니다. Timeout HTTP 응답을
보냈다는 이유로 worker slot을 반환하지 않으며, synchronous graph worker가 실제 종료한
뒤에만 반환합니다. 모든 slot이 사용 중이면 새 worker를 만들지 않고 즉시
`422 runtime_limit_exceeded`를 반환합니다. 따라서 cooperative cancellation을 지원하지
않는 upstream이 멈춰도 process별 lingering worker 수는 설정값을 넘지 않습니다.
`SKEWNONO_CHAT_MAX_CONCURRENT_AGENT_RUNS`는 1 이상 32 이하의 정수만 허용합니다.

## HTTP rollout 계약

`POST /api/chat/threads/<thread_id>/messages` body는 다음 두 필드를 모두 요구합니다.

```json
{
  "content": "승인된 업무 질문",
  "request_id": "64d35cd4-9e07-4be8-90a3-683f94c29408"
}
```

`request_id`는 lowercase canonical UUID string이어야 합니다. Network retry는 동일한
UUID를 재사용하고, 같은 문장의 새 질문은 새 UUID를 생성합니다. 이 필드는 기존 client와
호환되지 않는 필수 계약이므로 backend와 Nuxt를 같은 release에서 함께 배포합니다.
구형 frontend가 새 backend에 message를 보내거나 새 frontend가 구형 backend에
message를 보내는 혼합 배포를 허용하지 않습니다.

Assistant message는 `runtime`, `scope_status`, `sources`, `feedback`을 포함합니다.
Frontend와 backend의 해당 타입도 같은 release 단위로 유지합니다.

## Office knowledge provider 구현 계약

Tracked template인 `knowledge/providers/office_example.py`를
`knowledge/providers/office.py`로 복사한 뒤 gitignored copy만 구현합니다. Template은
계약 절반(`_search` limit/오류 변환, `_to_evidence` 엄격 검증, 네 공개 함수)이 이미
작성된 skeleton이며, office copy는 `OFFICE-TODO`로 표시된 세 seam —
`_config()`, `_build_request()`, `_execute()` — 과 `_translate_error()`의 client별
오류 mapping만 구현합니다. "do not edit below" 표시 아래의 계약 절반은 수정하지
않습니다. 다음 네 공개 signature를 그대로 유지합니다.

```python
search_manuals(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]

search_meeting_summaries(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]

search_emails(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]

search_reports(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]
```

각 반환 행은 `knowledge/contracts.py`의 다음 `Evidence` field를 모두 포함합니다.

| Field | 규칙 |
| --- | --- |
| `source_id` | Revision이 바뀌지 않는 한 재색인 후에도 유지되는 stable ID입니다. |
| `source_type` | `manual`, `meeting`, `email`, `report` 중 하나입니다. |
| `title` | 사용자가 볼 수 있도록 승인된 제목만 반환합니다. |
| `snippet` | 승인된 최소 근거 text이며 원문 전체를 반환하지 않습니다. |
| `revision` | Manual/report revision이 없으면 `None`입니다. |
| `occurred_at` | Source 기준일을 정규화하며 적용할 수 없으면 `None`입니다. |
| `section` | Section provenance가 없으면 `None`입니다. |
| `page` | 1-based page 번호이며 적용할 수 없으면 `None`입니다. |
| `region` | 승인된 page region/bounding reference이며 없으면 `None`입니다. |
| `locator` | 임의 URL이나 filesystem path가 아닌 안정된 승인 locator입니다. |
| `score` | 같은 source 검색 결과의 ranking 진단용 값이며 없으면 `None`입니다. |

Access filter는 retrieval query 단계에 적용합니다. 검색 후 Python filtering만으로 권한을
보완하지 않습니다. 권한이 없는 source의 존재, title, count 또는 score도 노출하지
않습니다. Empty result는 빈 list이며 다른 source나 mock 검색으로 대체하지 않습니다.

Agent model에 공개되는 tool argument는 `query`뿐입니다. `AccessScope`의 `user_id`,
`groups`, `fabs`, index/collection 이름, host, credential, limit은 Flask가 인증·설정에서
만들어 tool closure와 provider에 전달합니다. 이를 model argument나 user 입력에서
받지 않습니다.

현재 구현은 인증된 `user_id`만 채우고 `groups`와 `fabs`에는 빈 list를 전달합니다.
따라서 group/FAB 제한 source를 연결하기 전에 authoritative access resolver를 별도
server-side seam으로 구현하고, 인증 middleware의 값과 resolver 결과만으로
`AccessScope`를 구성해야 합니다. Resolver unavailable 또는 identity 누락 시 권한을
넓히지 않고 요청을 거절합니다.

Provider는 오류를 다음 typed exception으로 변환합니다.

- 접근 거부는 `KnowledgeDenied`입니다.
- 제한 시간 초과는 `KnowledgeTimeout`입니다.
- 설정 누락, index 불일치, source unavailable은 `KnowledgeUnavailable`입니다.

Agent runtime은 이를 각각 `403`, `504`, `503` 계열로 변환합니다. Retrieval 실패를
direct runtime, mock provider 또는 다른 source로 자동 전환하지 않습니다. Partial
assistant/source/trace row도 저장하지 않으며, 이미 저장된 user turn은 같은
`request_id` retry를 위해 유지합니다.

## Scope provider 구현 계약

`scope/providers/office_example.py`를 `scope/providers/office.py`로 복사하고
`classify(query: str) -> ScopeDecision`만 구현합니다. 반환 `status`는 `in_scope`,
`mixed`, `out_of_scope`, `unsafe` 중 하나이며 `reason_code`와 `supported_query`를 함께
정규화합니다. `mixed`일 때만 지원되는 부분을 `supported_query`로 전달합니다.
Unavailable 상태는 `ScopeUnavailable`을 발생시키며 mock으로 fallback하지 않습니다.

## Thread storage 동기화

Office thread storage는 `providers/office_example.py`의 모든 함수를 구현하고
`contracts.py`와 mock provider의 의미를 유지합니다. 특히 다음을 보장합니다.

```python
create_thread(user_id, model, system_prompt=None)
list_threads(user_id)
get_thread(user_id, thread_id)
rename_thread(user_id, thread_id, title)
delete_thread(user_id, thread_id)
append_message(thread_id, role, content, meta=None)
get_message_by_request(thread_id, request_id, role)
get_owned_message(user_id, message_id)
append_user_message(thread_id, content, request_id)
set_scope_decision(thread_id, request_id, decision)
complete_turn(thread_id, request_id, result)
put_feedback(user_id, message_id, feedback)
delete_feedback(user_id, message_id)
purge_expired(days=30)
```

- `(thread_id, request_id, role)` uniqueness와 동일 request ID replay를 보장합니다.
- Assistant, source, tool trace를 한 transaction으로 완료합니다.
- 모든 read/write에 thread owner의 `user_id`를 적용합니다.
- Thread 삭제와 retention purge가 source, trace, feedback을 함께 삭제합니다.
- `get_thread()`는 message와 source/feedback을 빠짐없이 hydrate합니다.

`providers/office_example.py`를 구현하지 않은 채 `office.py`로 복사하면 presence-based
selector가 thread storage를 stub으로 전환합니다. 구현과 fake-client 검증 전에는
복사하지 않습니다.

### Office retention job rollout checklist

Office thread storage는 mock의 list 요청 시 purge에 의존하지 않고 별도 scheduled
retention job을 운영해야 합니다. 다음 항목의 실제 값은 확인되지 않았으며, 모두 사내
운영 결정으로 rollout 전에 담당자와 값을 배정하고 승인 기록을 남겨야 합니다.

- [ ] **Owner:** Job 운영 책임자와 부재 시 대응 책임자를 지정합니다. 실제 team 또는
  담당자 이름은 사내 운영 문서에만 기록합니다.
- [ ] **Execution schedule:** 실행 주기, timezone, 허용 maintenance window와 중복 실행
  방지 방식을 결정합니다. 이 문서는 확인되지 않은 시각이나 주기를 기본값으로
  가정하지 않습니다.
- [ ] **Purge contract:** Job은 office provider의 `purge_expired(days=...)`와 같은
  cutoff 의미를 사용합니다. 만료 thread 삭제 시 message, source, tool trace,
  feedback이 같은 transaction 또는 검증된 cascade로 함께 삭제되어야 하며 orphan
  row를 허용하지 않습니다.
- [ ] **Retry와 failure 처리:** Idempotent 재실행 조건, retry 횟수와 backoff,
  partial failure 복구 절차를 결정합니다. 실패를 성공으로 기록하거나 다음 주기까지
  조용히 방치하지 않습니다.
- [ ] **Monitoring과 alerting:** 실행 시작·종료, duration, cutoff, 삭제 건수, failure
  class를 content 없이 관측하고, failure threshold, alert 수신 경로와 escalation
  책임자를 지정합니다.
- [ ] **Verification evidence:** Office-local dry run과 실제 scheduled run의 job ID,
  적용 cutoff, 삭제·잔존 건수, orphan 0건 확인, 의도적 failure 뒤 retry/alert 결과를
  승인 기록에 남깁니다. Query, message, feedback 본문이나 credential은 증빙에
  포함하지 않습니다.

## Source와 index 준비 checklist

다음 값은 사내에서 실제 system owner와 mapping을 확인한 뒤 office-local 설정 또는
승인된 비밀 관리 체계에 기록합니다. 이 저장소에는 실제 값을 기록하지 않습니다.

- [ ] Source별 index/collection과 현재 alias를 확인합니다.
- [ ] Source별 raw schema, schema version과 허용 field projection을 확인합니다.
- [ ] Embedding model identity, dimension과 index build version의 일치를 확인합니다.
- [ ] Chunk/vector ID에서 document, section, page, region으로 가는 manifest를 확인합니다.
- [ ] Manual revision 우선순위, superseded 문서 제외 규칙과 stable source ID를 확인합니다.
- [ ] Meeting, email, report의 기준 date field, timezone과 retention을 확인합니다.
- [ ] Identity에서 email recipient, group, FAB를 계산하는 authoritative access resolver와 identity 누락 시 deny 규칙을 확인합니다.
- [ ] Access filter가 query 단계에 적용되고 허용되지 않은 field가 projection에서 제외되는지 확인합니다.
- [ ] Source별 timeout, result/rerank limit, 허용 date range를 확인합니다.
- [ ] Versioned index 배포와 atomic active-version switch 절차를 확인합니다.
- [ ] Flask worker 수, worker별 index memory와 client connection budget을 확인합니다.
- [ ] 승인된 tool-capable model의 tool-call contract와 `CHAT_MODELS` capability flag를 확인합니다.

`SKEWNONO_RAG_SOURCE_ROOT`는 승인된 외부 root를 가리킵니다. Runtime은 이 경로를
scan하여 index를 build하지 않으며, offline ingestion이 만든 immutable/versioned
artifact만 read-only로 엽니다.

## Feedback와 evaluation 제한

현재 feedback은 chat history와 같은 retention 정책을 따르며 mock 기본값은 30일입니다.
Office에서 더 길게 보존하려면 개인정보·보안 승인, 삭제 job, 목적과 접근자를 먼저
문서화한 후 정책을 분리합니다. Feedback은 자동 학습 label이 아니며 model fine-tuning에
직접 사용하지 않습니다.

Evaluation bundle에는 user query, assistant answer, scope decision, runtime/model,
tool trace, source reference/score, rating/reason/comment가 결합될 수 있으므로 민감
업무 데이터로 취급합니다. 이번 scaffold에는 export, dashboard, training dataset 생성이
포함되지 않습니다. Application log에는 query, answer, retrieval query/snippet, 원문,
page image, 내부 hostname/index, credential을 남기지 않습니다.

Raw 운영 query, reaction과 tool trace는 원형 그대로 evaluation dataset에 사용하지
않습니다. 향후 evaluation case가 필요하면 사람이 내용과 권한을 검토하고 식별자·사내
경로·민감 업무 내용을 de-identify한 case에 한하여, 목적·보존 기간·접근자·삭제 절차를
정한 별도의 문서 승인을 받은 뒤 포함할 수 있습니다. Human review, de-identification,
별도 승인은 모두 필수이며 하나라도 없으면 dataset으로 이동하지 않습니다. Evaluation
export, training dataset 생성과 model training/fine-tuning은 계속 이 scaffold의 범위
밖입니다.

## 검증 순서

### Home 및 fake-client contract

먼저 현재 mock/fake 계약을 실행합니다.

```bash
.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge.py back_dev_home/chat/tests/test_runtime.py back_dev_home/chat/tests/test_scope.py -q
```

`back_dev_home/chat/tests/test_knowledge_office.py`는 tracked skeleton으로 이미
존재합니다. Home에서는 gitignored `office.py`가 없어 module 단위로 skip하고,
office에서 복사 직후부터 계약 절반(정확한 `Evidence` field mapping, limit,
empty result, rank ordering 유지, typed exception)을 fake seam으로 검증합니다.
Office 구현 시에는 파일 하단의 `OFFICE-TODO` skip test 세 건 — query-time access
filter 증명, raw row 정규화, client 오류 mapping — 을 fake client/raw result 주입
방식으로 채웁니다. Live service는 호출하지 않습니다.

```bash
.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge_office.py -q
```

### Office-local smoke

Fake-client test가 통과한 뒤에만 gitignored `knowledge/providers/office.py`와 승인된
office-local 설정을 사용합니다. `tests/test_chat_rag_local.py`는 `TEST_STAGE=local`과
필수 환경변수가 없으면 명확한 이유로 skip하고, 승인된 비민감 query 한 건으로 실제
source type, provenance와 access denial을 확인하도록 작성합니다. Thread storage가 아직
준비되지 않았으면 mock으로 명시하여 RAG source smoke와 분리합니다.

```bash
TEST_STAGE=local SKEWNONO_CHAT_PROVIDER=mock SKEWNONO_CHAT_RUNTIME=agent SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office SKEWNONO_CHAT_SCOPE_PROVIDER=office .venv/bin/python -m pytest tests/test_chat_rag_local.py -q
```

실제 source content, query 결과, 내부 경로와 credential은 test assertion, fixture,
console log 또는 commit에 남기지 않습니다. Office smoke가 통과한 뒤에도 전체 home
suite를 다시 실행하여 환경 전환이 frontend/backend 계약을 바꾸지 않았는지 확인합니다.

## Repository gate

Repository root에서 다음을 실행합니다.

```bash
.venv/bin/python -m pytest tests back_dev_home -q
uv run --no-project ruff check back_dev_home/chat
npm run lint:md
git diff --check
```

`front-dev-home/`에서는 다음을 실행합니다.

```bash
npm test
npm run typecheck
npm run lint
npm run build
```
