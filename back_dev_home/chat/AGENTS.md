# AGENTS.md — chat 폴더에서 일하는 두 agent 의 공동 규약

이 폴더는 두 agent 가 함께 씁니다. 여기 없는 규칙은 각자의 본진 문서를
따릅니다(chat 측: 저장소 루트 `CLAUDE.md`, RAG 측: `_rag/skewnono_rag/` 안의
자체 문서).

| agent | 실행 위치 | 소유 영역 |
| --- | --- | --- |
| chat 측 (Claude, 저장소 전체) | 저장소 루트 | 이 폴더의 모든 코드·테스트·`MIGRATION.md`·`docs/` |
| RAG 측 (사무실 LLM) | 이 폴더 (`back_dev_home/chat/`) | `_rag/skewnono_rag/` 전체 |

## 역할 분담 (runtime)

RAG 측이 지식·검색·답변 생성을 전담하고, chat 측은 front 를 전담합니다.
어느 쪽이 답하는지는 설정이 아니라 **`_rag/skewnono_rag/` 의 존재**로
정해집니다 — 진입 모듈과 빌드된 인덱스가 있으면 RAG, 없으면 mock 입니다
(`rag.py` 의 `rag_ready()`; 부팅 로그가 어느 쪽인지 한 줄로 찍습니다).

| 역할 | 담당 |
| --- | --- |
| 문서 ingestion, 인덱스 빌드, MinIO figure 적재 | RAG 측 |
| 검색·질의 rewrite·follow-ups | RAG 측 — 셋 다 `agent_query` **안에서** 일어납니다. chat 이 따로 부르는 함수는 없습니다(구 primitive 3함수는 2026-08-31 계약에서 폐기) |
| LLM gateway 키 관리 (`skewnono_rag/config.py` 내장) | RAG 측 |
| HTTP routes, 스레드 저장(SQLite), rate limit, 신원 | chat 측 |
| scope 사전 게이트 | chat 측 — 2026-09-01 부터 **deny-list** 입니다. 명시적 off-topic·unsafe 마커가 있는 질의만 막히고, 나머지는 마커가 없어도 RAG 에 도달합니다(`scope/policy.py`) |
| figure 서빙 (`figure_id` → MinIO webp), SPA 화면 | chat 측 |
| agent loop (검색 반복·답변 생성) | RAG 측 (`agent_query`) — chat 측 구 경로는 2026-08-31 삭제되었습니다 |
| 모델 선택·system prompt | RAG 측 — chat 은 자체 LLM 호출이 없습니다 |

집(mock) 환경에서는 RAG 측 역할 전부를 chat 의 mock provider 가 대역합니다.

## 소유 경계

- **RAG 측 agent 가 만지는 곳은 `_rag/skewnono_rag/` 하나뿐입니다** — 그
  밖의 어느 파일도 쓰지 않습니다(편지 파일 포함). 갱신은 **통째 교체**로만
  하며(인덱스 `index/` 4파일과 gateway 키 내장 `config.py` 포함), chat 측은
  읽기만 합니다.
- 그 밖의 chat 코드·문서는 전부 chat 측이 고칩니다. RAG 측이 chat 코드에서
  고칠 것을 발견하면 회신(아래 서신 절)으로 요청합니다.
- `_rag/` 는 `.gitignore` 대상이므로 그 안에 둔 파일은 git 으로 전달되지
  않습니다. 저장소를 타야 하는 문서는 `docs/` 에 둡니다.

## 서신 — `docs/`

채널은 비대칭입니다: **chat → RAG 는 `docs/` 의 편지**(RAG 측은 읽기만),
**RAG → chat 회신은 사용자가 chat 세션에 직접 타이핑해 전달**합니다 — RAG
측은 파일을 쓰지 않으므로 회신을 편지 파일로 남기는 쪽은 chat 측입니다
(받은 회신을 해당 편지의 후기 절로 기록). 지금까지의 왕복이 모두 `docs/` 에
있으니 새 편지를 쓰기 전에 최근 것부터 읽습니다.

- 파일명: `YYYY-MM-DD-<보낸쪽>-to-<받는쪽>-<주제>.md` (예:
  `2026-08-31-chat-to-rag-answer-contract.md`).
- 본문은 한국어 정중체, 표는 markdownlint MD060 compact 스타일.
- 질문은 표로 모으고, 답이 예측대로면 회신을 생략할 수 있게 "회신 불요"
  조건을 함께 적습니다.
- 사실에는 출처 표기를 답니다: `RAG 측 확인 YYYY-MM-DD`,
  `office 확인 YYYY-MM-DD`, `user-confirmed`, 미확인 가정은 `OFFICE-VERIFY`.

**완료된 안건**: 답변 전체를 RAG 의 `agent_query(question, messages,
scope, timeout)` 하나로 옮기는 경계 변경이 끝났습니다
(`docs/2026-08-31-chat-to-rag-answer-contract-agreed.md` 가 최종 계약).

구 경로(chat 측 agent loop, `llm.py`, egress guard, tool 6종, knowledge
검색 seam)는 **사무실 full-path 검증 전에** 사용자 결정으로 삭제했습니다
(2026-08-31). 이유는 두 경로를 함께 두는 비용이 검증 대기 기간보다 컸기
때문입니다. 검증에서 문제가 나오면 되살릴 곳은 git 이며, 삭제 커밋 하나만
되돌리면 구 경로가 그대로 복원됩니다.

**사무실 full-path 검증 완료 (2026-09-01).** `answer/contract.py` 의
`--live` 러너가 사무실 런타임에서 전부 `ok` 를 냈습니다 — import·서명·반환값.
동거 배치가 처음으로 실증되었고(사내 의존성이 skewnono 의 `numpy>=2` 옆에서
로드됨), 계약 검증이 편지 왕복에서 명령 한 번으로 바뀌었습니다.

**화면 경로도 확인 완료 (2026-09-01).** 사무실에서 `/chat` 을 열어 그림이
보이는 것까지 확인했습니다(user-confirmed). `figure_id` → MinIO webp 는
`--live` 가 전혀 건드리지 않는 유일한 경로였고, 이로써 chat 은 집에서
검증할 수 없던 경로가 하나도 남지 않았습니다. 실제 매뉴얼 파일 이름이
serving charset(`^[\w .-]{1,128}$`)을 통과한다는 것도 같이 실증되었습니다 —
RAG 측에 sanitization 이 없으므로 이 charset 을 좁히면 그때 깨집니다.

## 계약의 원본 (여기 요약하지 않습니다)

| 내용 | 원본 |
| --- | --- |
| **반환값 필드 규칙, 호출 서명, 예외 대응 (실행 가능)** | **`answer/contract.py`** |
| RAG 동거 배치, 공개 API(`agent_query` 1함수), 오류 계약, 의존성 | `MIGRATION.md` 의 "RAG 동거" 절 |
| Evidence 필드 규칙, figure 저장소(MinIO 키), index 위치 | `../../docs/datatables/hitachi/chat_rag_contract.txt` |
| import 경로와 index 기본값의 코드 구현 | `rag.py` (`import_rag`, `index_dir`) |
| Evidence / AccessScope 타입 | `contracts.py` |
| mock / office 판정 (검출 조건) | `rag.py` 의 `rag_ready()` |
| 답변 범위 사전 게이트 어휘 | `scope/policy.py` |

세 곳이 조용히 경쟁하지 않도록 축을 나눕니다.

| 무엇 | 이기는 곳 |
| --- | --- |
| **실행 가능한** 사실 — 필수 키, 값 모양, 호출 서명, 예외 대응 | `answer/contract.py` |
| **실행 불가능한** 의미 — `source_id` 안정성, `snippet` 승인 범위, AccessScope 가 5행 절단 전에 적용될 것 | `docs/datatables/…/chat_rag_contract.txt` |
| 협상 경과 | `docs/` 의 편지 |

즉 코드로 검사할 수 있는 것은 코드가 이기고, 검사할 수 없는 것은 datatables
문서가 이깁니다. 새로 확인된 office 사실은 datatables 문서와 mock provider
양쪽에 같은 변경으로 적습니다(chat 측 담당).

계약 파일은 **두 환경이 함께 실행합니다** — chat 은 사무실 turn 마다
`validate_answer()` 를 부르고, RAG 측은 사무실 런타임에서
`python -m scripts.verify.check_answer_contract --live` 로 자기 `agent_query`
를 검사합니다. 규칙을 바꾸려면 `CONTRACT_VERSION` 을 올리고 편지 한 통을
보냅니다.
