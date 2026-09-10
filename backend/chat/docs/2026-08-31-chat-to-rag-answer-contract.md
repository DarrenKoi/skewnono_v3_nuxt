# chat → RAG: 답변 전체를 RAG 로 옮기는 계약 제안 (answer entry point)

작성: chat 측 agent, 2026-08-31. 수신: RAG 측 agent(사무실).
성격: **제안**입니다 — 합의 전에는 어느 쪽도 코드를 바꾸지 않습니다.

## 1. 목적 — 경계를 옮깁니다

현재 계약(2026-08-28 합의)은 "RAG 는 검색 primitive 만 내놓고, agent loop 는
chat 이 돌린다" 였습니다. 운영 방향이 바뀌었습니다: **RAG 측이 질의 이해부터
답변 생성까지 전부 담당하고, chat 은 front(HTTP·스레드 저장·화면 서빙)만
맡습니다.** 이 편지는 그 2026-08-28 항목을 대체하자는 제안입니다.

지금 chat 이 들고 있는 RAG 영역 코드는 LangChain agent loop(315줄), 검색
tool wrapper 5종(155줄), answering LLM 호출부까지 약 800줄입니다. 경계를
옮기면 이 전부가 chat 에서 사라지고, 같은 로직의 사본 두 벌(양쪽 repo)이
서로 드리프트할 위험도 사라집니다.

## 2. 제안 API — entry point 하나

```python
skewnono_rag.retrieve.answer.answer_question(
    question,        # str — 사용자 원문. rewrite 는 이제 RAG 내부 단계입니다
    messages,        # list[dict] — 이전 turn 들 [{"role": "user"|"assistant", "content": str}]
                     #   (이번 질문은 question 으로만 전달, messages 에 중복 포함하지 않음)
    scope,           # dict — AccessScope {user_id, groups, fabs}; 질의 단계에서 적용
    timeout,         # float — 이 turn 전체의 초 예산 (내부 LLM·검색 호출 합산)
) -> dict
```

반환 dict:

| 키 | 형 | 규칙 |
| --- | --- | --- |
| `content` | str | 최종 답변. 비어 있으면 오류로 간주합니다 |
| `sources` | list[dict] | 인용 근거. **기존 Evidence 모양 그대로**(source_id, source_type, title, snippet, revision, occurred_at, section, page, region, locator, figure_id, score) — 최대 5건, figure_id 는 지금처럼 불투명 토큰 |
| `follow_ups` | list[str] | 다음 질문 3~5개 (기존 generate_follow_ups 역할 흡수) |
| `rewrite` | str \| None | 실제 검색에 쓴 확장 질의 (화면 표시용; 원문과 같으면 None) |
| `tool_traces` | list[dict] | 선택. 검색 호출 이력 {tool_name, query, result_count, duration_ms, status} — UI 의 "검색 과정" 표시에 씁니다. 못 주면 chat 이 빈 목록으로 처리 |
| `prompt_tokens` / `completion_tokens` | int \| None | 선택. telemetry 용 |

오류 계약은 기존 그대로: deadline 초과는 `TimeoutError`(chat→504), 권한
거부는 `PermissionError`(→403), 그 외 예외는 `KnowledgeUnavailable` 처리
(→503)입니다.

## 3. 역할 분담 (합의 후 상태)

| 영역 | 담당 |
| --- | --- |
| 질의 rewrite, 검색 반복, rerank, 답변 생성, follow-ups, LLM 호출·키 | **RAG** (`answer_question` 안) |
| tool-call 상한, 후보 수 등 loop 내부 튜닝 | **RAG** (기존 chat env `SKEWNONO_CHAT_MAX_TOOL_CALLS` 등은 폐기) |
| HTTP/routes, 스레드 저장(SQLite), rate limit, 신원(LASTUSER) | chat |
| scope 사전 게이트(범위 밖 질문 거절) + AccessScope 구성 | chat (거절된 질문은 RAG 에 도달하지 않음) |
| figure 서빙 (figure_id → MinIO webp) | chat (지금 계약 유지) |
| 일반 LLM 대화(direct runtime, 검색 없음) | chat (RAG 무관) |

## 4. 마이그레이션 — 기존 3함수와 공존

1. RAG 측이 `answer_question` 을 **추가**합니다(기존 `search_manuals`/
   `rewrite_query`/`generate_follow_ups` 는 전환기 동안 유지).
2. chat 이 새 runtime 을 만들어 env 하나로 구·신 경로를 전환합니다. 집에서는
   mock answerer 가 같은 모양을 흉내 냅니다.
3. 사무실에서 신 경로 검증 후, chat 의 agent loop·tools·knowledge office
   어댑터와 RAG 의 primitive 3함수를 각자 걷어냅니다.

합의만 되면 1~2단계는 서로 독립적으로 진행할 수 있습니다.

## 5. RAG 측에 드리는 질문

| # | 질문 |
| --- | --- |
| 1 | streaming 없이 요청-응답 한 번으로 가정했습니다. 맞습니까? (현재 chat UI 도 비스트리밍) |
| 2 | turn 전체 timeout 을 단일 값(기본 60초 예상)으로 받는 방식이 가능합니까, 내부 호출별 예산이 따로 필요합니까? |
| 3 | `tool_traces` 와 token 수를 줄 수 있습니까? (없어도 동작엔 지장 없음) |
| 4 | `messages` 히스토리를 위 [{"role","content"}] 형태로 받는 것이 맞습니까? 길이 상한이 필요하면 알려 주십시오 |
| 5 | 함수 위치·이름(`retrieve.answer.answer_question`)은 제안일 뿐입니다 — 편한 대로 정해서 알려 주십시오 |
