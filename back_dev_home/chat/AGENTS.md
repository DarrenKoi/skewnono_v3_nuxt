# AGENTS.md — chat 폴더에서 일하는 두 agent 의 공동 규약

이 폴더는 두 agent 가 함께 씁니다. 여기 없는 규칙은 각자의 본진 문서를
따릅니다(chat 측: 저장소 루트 `CLAUDE.md`, RAG 측: `_rag/skewnono_rag/` 안의
자체 문서).

| agent | 실행 위치 | 소유 영역 |
| --- | --- | --- |
| chat 측 (Claude, 저장소 전체) | 저장소 루트 | 이 폴더의 모든 코드·테스트·`MIGRATION.md`·`docs/` |
| RAG 측 (사무실 LLM) | 이 폴더 (`back_dev_home/chat/`) | `_rag/skewnono_rag/` 전체 |

## 역할 분담 (runtime)

RAG 측이 지식·검색을 전담하고, chat 측은 front 를 전담합니다.

| 역할 | 담당 |
| --- | --- |
| 문서 ingestion, 인덱스 빌드, MinIO figure 적재 | RAG 측 |
| 검색·질의 rewrite·follow-ups (`search_manuals`, `rewrite_query`, `generate_follow_ups`) | RAG 측 |
| LLM gateway 키 관리 (`skewnono_rag/config.py` 내장) | RAG 측 |
| HTTP routes, 스레드 저장(SQLite), rate limit, 신원 | chat 측 |
| scope 사전 게이트 (범위 밖 질문은 RAG 에 도달하지 않음) | chat 측 |
| figure 서빙 (`figure_id` → MinIO webp), SPA 화면 | chat 측 |
| agent loop (검색 반복·답변 생성) | **현행** chat 측 — RAG 측으로 이동 합의됨(2026-08-31), `agent_query` 구현·검증 완료 시 교체 |

집(mock) 환경에서는 RAG 측 역할 전부를 chat 의 mock provider 가 대역합니다.

## 소유 경계

- `_rag/skewnono_rag/` 는 RAG 측 전달물입니다. 갱신은 **통째 교체**로만
  하며(인덱스 `index/` 4파일과 gateway 키 내장 `config.py` 포함), chat 측은
  읽기만 합니다.
- 그 밖의 chat 코드는 chat 측이 고칩니다. RAG 측이 chat 코드에서 고칠 것을
  발견하면 편지로 요청합니다 (아래 서신 절).
- `_rag/` 는 `.gitignore` 대상이므로 그 안에 둔 파일은 git 으로 전달되지
  않습니다. 저장소를 타야 하는 문서는 `docs/` 에 둡니다.

## 서신 — `docs/`

두 agent 의 공식 채널은 `docs/` 의 편지입니다. 지금까지의 왕복이 모두 거기
있으니 새 편지를 쓰기 전에 최근 것부터 읽습니다.

- 파일명: `YYYY-MM-DD-<보낸쪽>-to-<받는쪽>-<주제>.md` (예:
  `2026-08-31-chat-to-rag-answer-contract.md`).
- 본문은 한국어 정중체, 표는 markdownlint MD060 compact 스타일.
- 질문은 표로 모으고, 답이 예측대로면 회신을 생략할 수 있게 "회신 불요"
  조건을 함께 적습니다.
- 사실에는 출처 표기를 답니다: `RAG 측 확인 YYYY-MM-DD`,
  `office 확인 YYYY-MM-DD`, `user-confirmed`, 미확인 가정은 `OFFICE-VERIFY`.

**진행 중 안건**: 답변 전체를 RAG 의 `agent_query(question, messages,
scope, timeout)` 하나로 옮기는 경계 변경이 **합의되었습니다**
(`docs/2026-08-31-chat-to-rag-answer-contract-agreed.md` 가 최종 계약).
RAG 측은 (a)~(e) 구현 후 `skewnono_rag/` 재전달. chat 측 절반은 **완료**
(`answer/providers/` swap surface + `SKEWNONO_CHAT_RUNTIME=rag`) — 사무실
에서 `cp answer/providers/office_example.py answer/providers/office.py` 후
env 전환으로 검증합니다. 구 경로 삭제는 사무실 검증 후입니다.

## 계약의 원본 (여기 요약하지 않습니다)

| 내용 | 원본 |
| --- | --- |
| RAG 동거 배치, 공개 API 3함수, 오류 계약, 의존성 | `MIGRATION.md` 의 "RAG 동거" 절 |
| Evidence 필드 규칙, figure 저장소(MinIO 키), index 위치 | `../../docs/datatables/hitachi/chat_rag_contract.txt` |
| import 경로와 index 기본값의 코드 구현 | `rag.py` (`import_rag`, `index_dir`) |
| Evidence / AccessScope 타입 | `knowledge/contracts.py` |

같은 사실이 두 곳에서 어긋나면 datatables 문서가 이깁니다. 새로 확인된
office 사실은 datatables 문서와 mock provider 양쪽에 같은 변경으로 적습니다
(chat 측 담당).
