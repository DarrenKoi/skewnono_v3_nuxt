# Chat office RAG 전환 가이드

이 문서는 사내 coding LLM이 현재 Flask/Nuxt 계약을 변경하지 않고 chat RAG 연결점을
구현하기 위한 handoff 계약입니다. 실제 hostname, credential, index alias, raw mapping,
사내 sample 문서 및 원문은 저장소에 commit하지 않습니다.

## 페이지 공개 여부

Chat은 아직 서비스 시작 전이므로 production cloud에서는 페이지가 "준비 중" 안내로
대체됩니다. 집과 사무실에서는 평소대로 열립니다.

| 항목 | 값 |
| --- | --- |
| 환경 변수 | `SKEWNONO_CHAT_UNDER_DEVELOPMENT` (1/0) |
| 기본값 | `is_cloud()` — cloud면 안내, 나머지는 정상 |
| Endpoint | `GET /api/chat/availability` → `{"data": {"available": bool}}` |
| SPA | `pages/chat.vue`가 mount 시 1회 조회합니다. |

**서비스 시작은 cloud host의 `.env`에 `SKEWNONO_CHAT_UNDER_DEVELOPMENT=0`을 넣고
재기동하는 것이 전부입니다.** 코드 변경도 재배포도 필요하지 않습니다.

이것은 **페이지 gate이며 authorization gate가 아닙니다.** `/api/chat/*`는 cloud에서도
계속 응답하므로 페이지가 가려진 상태에서도 API를 그대로 시험할 수 있습니다. 접근을
막아야 하는 상황이 오면 이 flag를 확장하지 말고 별도의 인증 장치를 씁니다.

SPA는 하나의 bundle이 세 phase에 모두 배포되므로 phase를 스스로 알 수 없습니다.
따라서 backend가 데이터로 알려주는 형태여야 하며, 프론트가 phase로 분기하지
않습니다. Availability 조회가 실패하면 안내가 아니라 정상 UI로 falls through
합니다 — backend 장애를 "서비스 시작 안 함"으로 잘못 표시하지 않기 위해서입니다.

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
| Knowledge | `SKEWNONO_CHAT_KNOWLEDGE_SOURCES`(기본 `manual`) | Office provider가 실제로 답할 수 있는 source 집합을 고릅니다(`manual`/`meeting`/`email`/`report`의 comma-separated subset). | `SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office`일 때만 boot에서 함께 검증하며, 알 수 없는 값이나 빈 값은 `RuntimeError`로 startup을 중단합니다. `mock`일 때는 검증하지 않습니다(lazy). 준비되지 않은 source는 tool로도 노출되지 않습니다. |
| Figures | `SKEWNONO_CHAT_FIGURES_DIR` / `SKEWNONO_CHAT_FIGURE_BUCKET` / `SKEWNONO_CHAT_FIGURE_PREFIX` | 그림 저장소는 knowledge provider 를 따라갑니다 — `mock`이면 디스크, `office`면 MinIO. 별도 selector 는 없습니다. | 미설정·미저장·형식 불일치 모두 `404`입니다(아래 "Figure serving" 절). |
| Knowledge | `SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES`(기본 `24`) | Office retrieval이 rerank 전에 가져오는 후보 수입니다(5~50으로 clamp). | Application이 소유하는 상한이며 adapter가 자기 입력을 넓힐 수 없습니다. |
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

## RAG 동거(co-location) — 사내 RAG 저장소를 chat 아래에 두는 방법 (2026-08-28)

사내 RAG는 별도의 git 저장소이며(공개 저장소인 이곳에 절대 push 하지 않습니다),
chat 은 그것을 **같은 프로세스 안에서 import** 합니다 — Flask 와 인덱스 사이에
서비스가 없습니다. RAG 측 handoff 는 `docs/datatables/chat/chat_office_adapter_handoff.txt`
(2026-08-27)이고, 공개 API 는 다음 셋입니다(office 확인 2026-08-27).

| 단계 | RAG 함수 | chat 쪽 호출 지점 |
| --- | --- | --- |
| Agent loop 전 1회 | `src.retrieve.agent.rewrite_query(question) -> str` | `orchestration.py` → `knowledge/data.py:rewrite_query()` |
| Loop 안 tool 호출마다 | `src.retrieve.serve.search_manuals(query, scope, limit=, index_dir=)` | `knowledge/providers/office.py:_execute()` |
| 답변 후 1회 | `src.retrieve.agent.generate_follow_ups(question, answer, sources) -> list[str]` | `orchestration.py` → `knowledge/data.py:generate_follow_ups()` |

RAG 측은 자체 agent loop 를 돌리지 않습니다 — chat 의 LangChain agent 가
`search_manuals` 를 반복 호출하고, `_execute()` 안에 두 번째 loop 가 있으면 LLM
호출이 곱해집니다.

**배치.** RAG checkout 은 `back_dev_home/chat/_rag/` 에 둡니다(자체 `.git` 포함).
앞머리 밑줄이 이 배치를 안전하게 만드는 전부입니다.

| 걸림돌 | 왜 `_rag/` 가 걸리지 않는가 |
| --- | --- |
| Blueprint 자동 탐색(`routes.py` rglob) | `_` 로 시작하는 경로를 건너뜁니다. RAG 에 `routes.py` 가 있어도 boot 가 깨지지 않습니다. |
| Office registry(`**/providers/{mock,office}.py` glob) | 같은 규칙. RAG 안의 `providers/` 폴더가 중복 slug 로 잡히지 않습니다. |
| Deploy pack | `_` 경로를 걷지 않는 규칙은 없지만 `back_dev_home` 통째로 복사하므로 **함께 실립니다**(의도). 대신 `.git` 은 `PRUNE_DIRS` 로 버립니다. |
| ruff | `.gitignore` 를 따르므로 무시합니다. |
| pytest | `.gitignore` 를 따르지 **않으므로** `pyproject.toml` 의 `--ignore=back_dev_home/chat/_rag` 가 막습니다. |
| git | `.gitignore` 의 `back_dev_home/chat/_rag/`. 중첩 저장소는 `git -C back_dev_home/chat/_rag pull` 로 따로 갱신합니다. Submodule 은 쓰지 않습니다 — 사무실은 GitHub 에 로그인할 수 없고 RAG 저장소는 사내 전용입니다. |

`from src.retrieve...` 가 동작하려면 checkout 루트가 `sys.path` 에 있어야 하는데,
Flask 는 저장소 루트에서 뜨므로 저절로 되지 않습니다. `chat/rag.py` 의
`import_rag("retrieve.serve")` 가 유일한 import 경로입니다 — 루트를
`SKEWNONO_CHAT_RAG_ROOT`(미설정이면 `_rag/`)에서 찾아 한 번만 `sys.path` 에 넣고,
checkout 이 없거나 사내 의존성이 빠진 모든 실패를 `KnowledgeUnavailable`(503)로
바꿉니다. 인덱스 경로는 `SKEWNONO_RAG_INDEX_DIR`(미설정이면 `{checkout}/index`)이며
항상 절대 경로로 넘깁니다 — RAG 의 기본값은 상대 경로 `"index"` 라 cloud 에서는
`/project/workSpace/index` 를 찾게 됩니다.

**Rewrite 와 follow-ups 의 동작 계약.**

- 둘 다 agent runtime 에서만 호출합니다. Direct runtime 은 retrieval 이 없으므로
  둘 다 건너뛰고 `rewrite=None`, `follow_ups=[]` 을 저장합니다. Scope 거절 turn 도
  같습니다.
- Rewrite 대상은 runtime 이 실제로 답하는 질문입니다 — mixed 면 `supported_query`,
  아니면 사용자 문장. 결과가 원문과 같으면 `None` 으로 저장합니다.
- Rewrite 는 사용자 메시지를 **바꾸지 않습니다**. `RuntimeRequest.rewrite` 로
  넘어가 agent system prompt 의 `retrieval_query` 줄이 되고, 모델은 검색 tool 의
  query 로 그것을 우선 씁니다. 사용자의 말은 그대로 user message 로 남습니다.
- Rewrite 실패는 turn 실패입니다(`KnowledgeUnavailable` → 503, `KnowledgeTimeout` →
  504, `KnowledgeDenied` → 403). 원문으로 검색을 계속하면 recall 이 낮은 답이
  정상 답처럼 보이기 때문입니다 — rerank 를 건너뛰지 않는 것과 같은 이유입니다.
  User turn 은 같은 `request_id` retry 를 위해 남습니다.
- Follow-ups 실패는 답변을 깨뜨리지 않습니다. `skewnono.chat` logger 에 예외를
  남기고 `[]` 을 저장합니다 — 대화 기록(telemetry)과 같은 정책입니다.
- `RuntimeResult` 와 `Message` 가 `rewrite: str | None`, `follow_ups: list[str]` 을
  가집니다. SQLite mock 은 `messages.rewrite`, `messages.follow_ups_json` 열로
  additive migration 합니다. SPA 는 follow-up 을 chip 으로 그리고, 누르면 composer 에
  채웁니다(바로 전송하지 않습니다).

**Mock 과의 차이.** `knowledge/providers/mock.py` 의 `rewrite_query` 는 고정 약어·
번역 표이고 `generate_follow_ups` 는 인용 제목에서 만든 질문 3개입니다. 사무실은
둘 다 LLM 이며 자유 문장입니다. 모양(비어 있지 않은 문자열, 서로 다른 3~5개)만
같습니다.

## Office knowledge provider 구현 계약

`knowledge/providers/office_example.py` 는 **완성된 구현**입니다(2026-08-28). 사무실
에서는 `cp office_example.py office.py` 만 하고 아무것도 고치지 않습니다 — 네 seam
(`_config()`, `_build_request()`, `_execute()`, `_rerank()`)이 위 "RAG 동거" 절의
co-located RAG 를 호출하고, `rewrite_query()`/`generate_follow_ups()` 두 공개
함수가 더해져 있습니다. "do not edit below" 아래의 계약 절반(`_search` limit/오류
변환, `_rank_hits` 정렬·절단, `_to_evidence` 엄격 검증, 네 공개 함수)은 여전히
수정하지 않습니다. Seam 의 검증은 `tests/test_knowledge_office_template.py` 가
집에서 가짜 `src.retrieve` 패키지로 수행하고, 복사본이 있으면 같은 테스트를
복사본에도 돌립니다. 다음 네 공개 signature를 그대로 유지합니다.

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

위 signature의 `limit`은 공개 함수 호출자에게는 최종 행 수(최대 5)이지만,
`_build_request()`가 받는 `limit`은 그 값이 아니라 **후보 수**입니다. `_search()`가
`max(bounded, config.get_knowledge_candidate_pool())`로 후보 수를 계산해
`_build_request()`에 넘기므로, office adapter는 요청한 후보를 전부 가져와야 하며
스스로 줄이면 안 됩니다. 정렬(`_rank_hits()`)과 상한 5행 절단은 tracked 계약
절반이 소유합니다 — office copy는 `_rerank()`가 반환한 점수로 정렬된 뒤 이미
절단된 결과만 봅니다.

네 번째 seam `_rerank(source_type, query, hits) -> list[float]`은 후보 각각에
`hits`와 같은 순서로 점수 하나씩(높을수록 우수) 반환합니다. 이 seam은 순서를
바꾸거나 절단해서는 안 됩니다 — 정렬·절단은 `_rank_hits()`가 담당합니다. 리랭크가
실패하거나 미구현이면 원 순위를 그대로 쓰지 않고 `KnowledgeUnavailable`을
올립니다. C1(OpenSearch가 rerank까지 수행)으로 전환하면 `_rerank()`는 각 hit의
기존 `score`를 그대로 돌려주는 항등 함수가 됩니다.

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
| `figure_id` | 그림 chunk의 opaque token이며 text/table chunk는 `None`입니다. |
| `score` | 같은 source 검색 결과의 ranking 진단용 값이며 없으면 `None`입니다. |

사무실 manual 검색(`src/retrieve/serve.py:search_manuals()`)이 실제로 돌려주는 키는
`source_id`, `title`, `snippet`, `section`, `page`, `figure_id`, `score`,
`element_type` 여덟 개입니다(office 확인 2026-08-27). `_to_evidence()`는 optional 키를
`.get`으로 읽으므로 `revision`/`occurred_at`/`region`/`locator`가 없는 hit은 그대로
`None`으로 매핑되고, 알 수 없는 키 `element_type`은 seam에서 버려집니다 — office copy가
채우거나 지울 것이 없습니다. 파일시스템 `image_path`는 절대 seam을 넘지 않으며, 넘는
것은 `figure_id`뿐입니다.

`figure_id`는 애플리케이션이 저장소 접근으로 바꾸는 유일한 값이므로 `locator`와 다른
규칙을 따릅니다. Bucket, prefix, 경로 구분자, `.webp` 확장자를 포함하지 않는 맨 id만
반환합니다. 키 조립(`{client prefix}/hitachi_sem/manual_figures/{figure_id}.webp`)과
`^[A-Za-z0-9._-]{1,128}$` 검증은 serving 쪽이 전담하므로, 경로가 섞인 id는 오류가
아니라 렌더되지 않는 그림이 됩니다.

형식은 `{doc_id}_p{page}_i{idx}`이며 doc_id에 **점이 들어갑니다**
(`CG6300_1.HHTSEM_SYSTEM_p100_i0`, office 확인 2026-08-19). 검증 charset이 점을
허용하는 이유가 이것입니다 — 자세한 내용은 아래 "Figure serving" 절을 봅니다.

Retrieval query 한 번이 한국어와 영어를 **동시에** 만족시켜야 합니다. 사용자는 한 질문
안에서 두 언어를 섞고 코퍼스도 섞여 있으므로, 한 언어만 만족시키는 요청은 실패하지 않고
recall만 조용히 반토막 냅니다. 검색은 Nori BM25 ⊕ BGE-M3 dense의 2-leg hybrid이며(설계
`docs/superpowers/specs/2026-08-07-chat-rag-manuals-design.md`), BGE-M3가
multilingual이므로 k-NN leg에서 한/영 요건이 충족됩니다(user-confirmed 2026-08-06).
Lexical leg는 Nori analyzer로 확정했습니다(user-confirmed 2026-08-06) — OpenSearch
기본 `standard` analyzer는 한글을 한 글자씩 분해하므로 씁니다. 질의를 언어 판별로
분기하거나 번역해서 보내지 않습니다. 후보 20~30건을 `bge-reranker-v2-m3` 크로스인코더로
재점수화한 뒤 상한 5행으로 절단합니다 — 상세는 `docs/datatables/hitachi/chat_rag_contract.txt`의
"검색 방식" 절을 참고합니다. 모델 호출은 `office.py`가 사내 embedding/rerank API를
직접 호출하는 C2 경로입니다(user-confirmed 2026-08-07); C1(OpenSearch ML Commons remote
connector)은 사내 host가 `trusted_connector_endpoints_regex`에 없어 보류입니다(office
확인 2026-08-07).

Access filter는 retrieval query 단계에 적용합니다. 검색 후 Python filtering만으로 권한을
보완하지 않습니다. 권한이 없는 source의 존재, title, count 또는 score도 노출하지
않습니다. Empty result는 빈 list이며 다른 source나 mock 검색으로 대체하지 않습니다.

이 네 공개 함수는 provider가 준비된 모든 source에 대해 항상 호출 가능한 signature로
유지되지만, 실제로 tool로 노출되는지는 **source별 준비 상태**가 결정합니다.
`knowledge/data.py`의 `available_sources()`는 mock에서는 네 소스 전부를, office에서는
`get_knowledge_sources()`(`SKEWNONO_CHAT_KNOWLEDGE_SOURCES`, 기본 `manual`)가 반환하는
집합만 돌려줍니다 — office provider 모듈을 import하지 않고 판단합니다.
`runtime/providers/agent.py`의 `_build_tools()`가 그 목록에 있는 source에만 tool을
만들므로, 준비되지 않은 source는 tool 자체가 없습니다. 인덱스가 없는 source에 빈 list를
돌려주는 방식은 택하지 않습니다 — 모델이 "그 소스에는 관련 내용이 없다"로 잘못 읽기
때문입니다. 노출되는 tool이 하나도 없으면 `RuntimeUnavailable`을 올립니다.

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

## Figure serving — 디스크(2026-08-19)와 MinIO(2026-08-27) 모두 구현 완료

`GET /api/chat/figures/<figure_id>`는 구현되어 있고, 저장소 접근은 `chat/figures.py`의
`read_figure()` 한 곳입니다. 저장소는 **knowledge provider를 따라갑니다** — `figure_id`는
그것을 만든 인덱스에 대해서만 의미가 있으므로(사내 ingestion이 인덱스와 그림 객체를 함께
씁니다) 별도 selector를 두지 않았습니다.

| 항목 | 결정 |
| --- | --- |
| Route | `GET /api/chat/figures/<figure_id>` (`chat/routes.py`의 `chat_figure`) |
| 저장소 접근 | `chat/figures.py`의 `read_figure(figure_id) -> bytes \| None` |
| 인가 | 인증된 사용자면 통과합니다. `/api/*`가 이미 신원 gate 뒤이므로 추가 확인을 하지 않습니다. |
| `mock` 저장소 | 디스크. `{SKEWNONO_CHAT_FIGURES_DIR}/{figure_id}.webp` |
| `office` 저장소 | MinIO. `{client prefix}/{SKEWNONO_CHAT_FIGURE_PREFIX}{figure_id}.webp` |
| `office` 설정 | `SKEWNONO_CHAT_FIGURE_BUCKET`(보통 비움 = client 기본 `user`), `SKEWNONO_CHAT_FIGURE_PREFIX`(기본 `hitachi_sem/manual_figures/`) |
| 검증 | 저장소에 닿기 전에 `^[A-Za-z0-9._-]{1,128}$` 불일치, `..` 포함, 앞머리 점이면 `404` |
| 응답 | `image/webp` + `Cache-Control: public, max-age=3600` |

사무실의 실제 객체 키는 다음과 같습니다(office 확인 2026-08-27).

```text
user/2067928/hitachi_sem/manual_figures/CG6300_1.HHTSEM_SYSTEM_p100_i0.webp
^bucket ^client prefix ^SKEWNONO_CHAT_FIGURE_PREFIX (기본값)  ^figure_id
```

사용자 namespace `2067928/`는 MinIO client의 **자체 기본 prefix**(`minio_handler`의
`PREFIX` / `MINIO_PREFIX`)이고, 앱은 그 아래 키만 넘깁니다 —
`MinioObject().get("hitachi_sem/manual_figures/<id>.webp")`. 이것은 `msr_image`의
image cache와 **반대 규약**입니다. 그쪽은 client prefix를 비우고 `2067928/image_cache/`를
자기 prefix에 적습니다. 둘 다 동작하며 섞는 것이 함정입니다 —
`SKEWNONO_CHAT_FIGURE_PREFIX`에 `2067928/`를 적으면 키가 `2067928/2067928/...`으로
겹쳐 모든 그림이 404 납니다. `hitachi_sem/`은 tool family 축이므로 다른 family의 그림은
다른 prefix로 가지, 다른 bucket으로 가지 않습니다.

MinIO 오류 중 `NoSuchKey`/`NoSuchObject`/`NotFound`는 그냥 miss(404)입니다. 그 밖의
오류(scoped credential의 `AccessDenied` 등)도 404이지만 warning 로그를 남깁니다 —
남기지 않으면 bucket 설정 오류가 "그림을 추출하지 않은 매뉴얼"과 구분되지 않습니다.

`chat/tests/test_figures.py`의 디스크 테스트는 MinIO 구현 전후로 한 줄도 바뀌지
않았습니다 — 테스트를 HTTP 경계에만 걸어 둔 이유가 이것입니다. MinIO 쪽은 같은 파일
하단에서 fake client로 키 조립·miss·오류 로그·검증 선행을 고정합니다.

### 검증 charset이 점을 허용하는 이유

Office의 figure_id 형식은 `{doc_id}_p{page}_i{idx}`이고 doc_id가 점을 포함합니다
(`CG6300_1.HHTSEM_SYSTEM_p100_i0`, office 확인 2026-08-19). 원래 합의했던
`^[A-Za-z0-9_-]{1,128}$`는 이 값을 **거부합니다**.

이 조합이 위험한 이유는 실패가 조용하기 때문입니다. Mock fixture의 id에는 점이 없었으므로
집에서는 모든 테스트가 통과하고, 사무실에서만 모든 그림이 404가 나며, 그마저도 오류가 아니라
"썸네일이 안 보인다"로 나타납니다. 그래서 charset을 넓혔습니다.

점을 허용하면 `..`가 charset만으로는 걸러지지 않으므로 세 겹으로 막습니다.

1. `..`를 포함한 id는 이름으로 거부합니다.
2. Slash는 charset과 Flask routing 양쪽에서 막힙니다 — routing이 `../`를 정규화하므로
   view까지 도달하지도 않습니다.
3. 디스크 경로는 조립한 경로를 `resolve()`한 뒤 부모가 figures 디렉터리인지 확인합니다.
   저장소 밖으로 나가는 symlink도 여기서 걸립니다.
4. 앞머리 점(`.`, `.foo`)은 이름으로 거부합니다. 맨 `.` 하나는 charset을 통과하고 `..`도
   아니어서, MinIO 경로에서는 `.../..webp` 키로 저장소까지 갔습니다(2026-08-27에 MinIO
   테스트가 잡아냈고, 디스크 경로는 3번 검사로만 살아남고 있었습니다).

Mock fixture의 id도 같은 날 실제 형식으로 바꿨습니다(`SYN6300_1.EBEAM_ALARM_p12_i0`).
`test_knowledge.py`가 mock의 id를 route의 검증기에 직접 걸어 보므로, 한쪽만 바뀌면
테스트가 깨집니다.

### 실패는 전부 404입니다

형식 불일치, 저장되지 않은 그림, 저장소 미설정(`mock`에서 `SKEWNONO_CHAT_FIGURES_DIR`
없음)이 모두 같은 404입니다. 구분해서 알려주면 figure_id의 존재 여부를 확인하는 수단이 되므로 의도적으로
합쳤습니다.

저장소 미설정이 오류가 아닌 이유도 함께 적어 둡니다. 그림 추출 없이 색인한 매뉴얼은 정상
상태이고, 그때 SPA는 썸네일 없이 인용만 렌더합니다.

### 남는 위험 (인가)

Retrieval은 `AccessScope`로 걸러지지만 이 endpoint는 걸러지지 않으므로, group/FAB 제한
매뉴얼의 **그림**은 `figure_id`를 아는 사용자면 그룹 밖에서도 받을 수 있습니다. 그림 자체가
접근 제한 정보를 담는 것이 확인되면 이 결정을 다시 검토합니다.

Prefix를 환경 변수로 두는 이유는 `hitachi_sem/`이 tool family 축이기 때문입니다. 사용자
namespace 제한은 MinIO client의 기본 prefix가 이미 감당하므로, 이전에 적었던
`user/2067928/figures/` 같은 전체 경로를 prefix에 넣는 안은 폐기했습니다 — 넣으면
namespace가 두 번 붙습니다(위 표 아래 설명).

## Scope provider 구현 계약

`scope/providers/office_example.py` 는 **완성된 구현**입니다(2026-08-28) — RAG
handoff 가 정한 도메인 marker(`ebeam, metrology, measurement, tool, alarm, manual,
recipe, error, cd-sem, sem, calibration, optics, vacuum, stage, wafer, idp, amp,
hitachi, gt2000, cg6300`)에 한국어 대응어를 짝지은 keyword 정책이며, 엔진은 mock 과
같은 `scope/keyword_policy.py` 를 씁니다(어휘만 다릅니다). 사무실에서는
`cp office_example.py office.py` 만 합니다. 반환 `status`는 `in_scope`, `mixed`,
`out_of_scope`, `unsafe` 중 하나이며 `reason_code`와 `supported_query`를 함께
정규화합니다. `mixed`일 때만 지원되는 부분을 `supported_query`로 전달합니다.
Unavailable 상태는 `ScopeUnavailable`을 발생시키며 mock으로 fallback하지 않습니다.
어휘를 넓히려면 template 을 고치고 다시 복사합니다 — 복사본만 고치면
`sync_office_adapters` 가 `EDITED` 로 분류합니다.

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
  매뉴얼 범위에서는 해당 없음 (user-confirmed 2026-08-06) — 매뉴얼은 개정되지
  않으므로 이번 연결에서는 의미가 없습니다. 항목은 지우지 않습니다: 회의록·메일·
  리포트를 연결할 때 다시 필요해집니다. `source_id`의 결정적 유도(재색인 시에도
  안정)는 매뉴얼 불변과 무관하게 계속 유지합니다 — chunking을 튜닝하면 재색인하게
  됩니다.
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

## 대화 기록 인덱스 (skewnono_chat_logging)

완료된 대화 turn은 활동 로그와 분리된 전용 OpenSearch 인덱스에 1건씩 기록합니다.
활동 인덱스(`skewnono_logging`)는 본문을 절대 저장하지 않는다는 규약을 유지하고,
대화 본문은 보존·접근을 따로 통제할 수 있는 이 인덱스에만 둡니다.

| 항목 | 값 |
| --- | --- |
| Alias | `skewnono_chat_logging`(production, 보존 365일) / `skewnono_chat_logging_local`(local, 보존 30일) |
| Alias 선택 | `SKEWNONO_LOG_ENV` — `_logging/target.py`의 `resolve_chat_conversation_target()` |
| Provisioning | `.venv/bin/python ops_index_mgmt/skewnono_chat_logging.py` (idempotent, `--dry-run` 지원) |
| Emit 지점 | `orchestration.py`의 `_record_conversation` — assistant turn 저장 직후 |
| 전송 | `chat/conversation_log.py` — `OpenSearchBulkHandler` 파이프라인 재사용, `propagate=False` |
| 설치 gate | 활동 로그와 동일 — office mode + `OPENSEARCH_PASSWORD`, `OPENSEARCH_LOGGING_DISABLED`로 차단 |

동작 계약은 다음과 같습니다.

- Scope 거절 turn도 기록합니다(`runtime=scope_rejection`, `tool_call_count=0`).
- 같은 `request_id` replay는 완료된 turn을 조기 반환하므로 중복 기록되지 않습니다.
- Runtime 실패는 assistant turn이 저장되지 않으므로 기록하지 않습니다.
- 기록 실패는 응답을 깨뜨리지 않습니다 — 손실 허용 telemetry이며, 실패는
  `skewnono.chat` logger의 예외 로그로만 관측합니다.
- 본문은 각 8,000자에서 절단합니다. 문서 스키마의 진실 원천은
  `ops_index_mgmt/skewnono_chat_logging.py`의 `CHAT_MAPPING_PROPERTIES`이며,
  필드를 추가할 때는 `build_turn_document()`·mapping·
  `docs/datatables/hitachi/skewnono_chat_logging.txt` 세 곳을 함께 갱신한 뒤 사무실에서
  additive mapping update를 실행합니다.
- 이 인덱스는 thread storage가 아닙니다. Thread CRUD·replay·feedback은 계속
  thread storage provider가 담당하며, 이 인덱스는 append-only 기록입니다.
- 본문이 포함되므로 이 인덱스를 읽는 화면·export를 추가하려면 아래 evaluation
  제한(사람 검토, de-identification, 별도 승인)을 먼저 따릅니다.

## Feedback와 evaluation 제한

현재 feedback은 chat history와 같은 retention 정책을 따르며 mock 기본값은 30일입니다.
Office에서 더 길게 보존하려면 개인정보·보안 승인, 삭제 job, 목적과 접근자를 먼저
문서화한 후 정책을 분리합니다. Feedback은 자동 학습 label이 아니며 model fine-tuning에
직접 사용하지 않습니다.

Evaluation bundle에는 user query, assistant answer, scope decision, runtime/model,
tool trace, source reference/score, rating/reason/comment가 결합될 수 있으므로 민감
업무 데이터로 취급합니다. 이번 scaffold에는 export, dashboard, training dataset 생성이
포함되지 않습니다. Application log에는 query, answer, retrieval query/snippet, 원문,
page image, 내부 hostname/index, credential을 남기지 않습니다. 대화 본문의 유일한
승인된 적재처는 위의 전용 인덱스(`skewnono_chat_logging`)입니다.

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
Office 구현 시에는 파일 하단의 `OFFICE-TODO` skip test 네 건 — query-time access
filter 증명, raw row 정규화, client 오류 mapping, rerank가 hits와 같은 순서로
점수를 반환하는지 — 을 fake client/raw result 주입 방식으로 채웁니다. Live
service는 호출하지 않습니다.

```bash
.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge_office.py -q
```

`back_dev_home/chat/tests/test_knowledge_office_template.py`는 위 skip을 메웁니다.
`test_knowledge_office.py`가 gitignored office copy를 import하기 때문에 home에서
통째로 skip되는 사이, tracked `office_example.py`의 계약 절반 — 후보 over-fetch,
`_rerank()` 점수로 재정렬, tie는 backend 순서 유지, 5행 절단, 점수 개수 불일치·비수치
점수·미구현 rerank가 모두 `KnowledgeUnavailable`이 되는 것 — 은 이 파일이 home에서
매 회 검증합니다. `office.py`는 계약 절반을 byte-identical로 상속하므로 이 테스트가
office copy에도 그대로 적용됩니다.

```bash
.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge_office_template.py -q
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
