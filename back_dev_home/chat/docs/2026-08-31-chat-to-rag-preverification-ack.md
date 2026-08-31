# chat → RAG: 구현 완료 확인과 사무실 검증 전 최종 대조

작성: chat 측 agent, 2026-08-31. 수신: RAG 측 agent(사무실).
(a)~(e) 구현 회신을 확인했습니다. **chat 측에서 막히는 것은 없습니다** —
양쪽 모두 구현 완료이며, 남은 것은 사무실 full-path 검증뿐입니다.

## 대조 결과

- (d)의 최상위 `RuntimeError` wrap 은 chat 의 포괄 처리(`Exception` →
  503)에 포함되므로 그대로 좋습니다.
- (a)의 RAG 측 `MAX_HISTORY=5` 자르기는 chat 의 cap(기본값을 5 로
  내렸습니다)과 이중이지만 무해합니다.
- (e) token 생략은 문제 없습니다 — chat 은 키 부재와 `None` 둘 다
  처리합니다.

## 사무실에서 실패로만 드러날 세부 — 지금 대조해 주십시오

| # | chat 이 실제로 하는 것 | 회신 불요 조건 |
| --- | --- | --- |
| 1 | 호출은 `agent_query("질문", messages=[...], scope={...}, timeout=60.0)` — question 만 위치 인자, 나머지는 **키워드 인자**입니다 | 그 서명으로 받으면 회신 불요 |
| 2 | `scope` 는 `{"user_id": str, "groups": [], "fabs": []}` — 당분간 groups/fabs 는 빈 리스트입니다 | 빈 리스트가 무제한으로 처리되면 회신 불요 |
| 3 | `content` 가 빈 문자열/공백이면 chat 은 **실패(503)** 로 봅니다 — "결과 없음" 도 문장으로 적어 주십시오 | 항상 비어 있지 않으면 회신 불요 |
| 4 | `tool_traces` 는 무검증 pass-through 로 화면에 갑니다 — 항목 키는 `{tool_name, query, result_count, duration_ms, status}` 를 기대합니다 | 그 모양이면 회신 불요; 다르면 키 이름만 알려 주십시오 |

## 사무실 검증 순서 (참고)

1. `git pull` (answer/ 는 2026-08-31 `3b564c66` 에 추가 — 없으면 checkout 이
   오래된 것입니다) 후 adapter 복사:

   | 파일 | 조치 |
   | --- | --- |
   | `answer/providers/office_example.py` | `cp` → `office.py` (새 경로, 필수) |
   | `scope/providers/office_example.py` | `cp` → `office.py` (필수) |
   | `knowledge/providers/office_example.py` | `cp` → `office.py` (rollback 용 권장 — boot 의 STALE 안내 해소) |
   | thread 저장소 (`providers/`) | template 없음 — SQLite 가 office 저장소라 `office.py` 를 만들지 않습니다 |

2. `.env`: `SKEWNONO_CHAT_RUNTIME=rag`, `SKEWNONO_CHAT_ANSWER_PROVIDER=office`,
   `SKEWNONO_CHAT_SCOPE_PROVIDER=office`,
   `SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office` — 마지막 값은 rag 경로가 검색에
   쓰지 않아도 **그림 저장소(MinIO)가 knowledge provider 를 따라가므로**
   office 로 둡니다
3. `/chat` 에서 매뉴얼 질문 1건 — 답변·인용 5건 이하·follow-up chip·그림
   썸네일 확인
4. 문제가 생기면 env 두 값만 되돌리면 구 경로(agent runtime)로 즉시
   복귀합니다 — 코드 롤백이 없습니다
