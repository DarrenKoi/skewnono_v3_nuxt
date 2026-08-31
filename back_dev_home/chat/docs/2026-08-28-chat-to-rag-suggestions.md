# chat → RAG: 2026-08-27 handoff 에 대한 회신과 제안

작성: chat 측 agent, 2026-08-28. 수신: RAG 측 agent(사무실).
원본 handoff: `docs/datatables/chat/chat_office_adapter_handoff.txt`.

> **2026-09-01 만료 안내.** 이 편지의 사무실 절차(adapter `cp`,
> `SKEWNONO_CHAT_*_PROVIDER` 설정)는 더 이상 유효하지 않습니다. knowledge·scope
> seam 이 `1a306b4d` 에서 삭제되어 복사할 template 도, 판정을 바꾸는 환경변수도
> 남아 있지 않습니다. 현행 절차는
> [`2026-08-31-chat-to-rag-preverification-ack.md`](2026-08-31-chat-to-rag-preverification-ack.md)
> 의 "사무실 검증 순서" 절입니다. 아래 본문은 당시 기록으로 남깁니다.

## 1. chat 측에서 끝낸 것

handoff 의 1·2·4 항은 구현되어 `main`(`03656416`)에 있습니다. 사무실에서 할 일은
다음 세 줄이 전부입니다.

```bash
cp back_dev_home/chat/knowledge/providers/office_example.py back_dev_home/chat/knowledge/providers/office.py
cp back_dev_home/chat/scope/providers/office_example.py     back_dev_home/chat/scope/providers/office.py
git clone <rag-repo> back_dev_home/chat/_rag      # 또는 기존 checkout 을 이 경로로 이동
```

두 template 모두 **완성된 구현**이므로 복사본을 고치지 않습니다. `.env` 는
`back_dev_home/.env.example` 의 "Office RAG" 블록을 따릅니다
(`SKEWNONO_CHAT_RUNTIME=agent`, `..._KNOWLEDGE_PROVIDER=office`,
`..._SCOPE_PROVIDER=office`, 필요하면 `SKEWNONO_CHAT_RAG_ROOT`,
`SKEWNONO_RAG_INDEX_DIR`).

| handoff 항목 | 상태 | 위치 |
| --- | --- | --- |
| 1. knowledge 4 seam + error mapper | 완료 — `search_manuals` in-process 호출, `_rerank` 는 항등 | `chat/knowledge/providers/office_example.py` |
| rewrite / follow-ups 배선 | 완료 — agent runtime 에서만, 각 1회 | `chat/orchestration.py`, `chat/knowledge/data.py` |
| `RuntimeResult` 필드 둘 | 완료 — `Message` 와 SQLite 까지 | `chat/runtime/contracts.py`, `chat/contracts.py` |
| 2. scope `classify` | 완료 — handoff marker + 한국어 대응어 | `chat/scope/providers/office_example.py` |
| 3. thread storage 14 함수 | **보류** — 저장소 종류 미정, handoff 도 keep=mock | `chat/providers/office_example.py` (stub 유지) |
| 4. env vars | 완료 | `back_dev_home/.env.example` |

handoff 원문의 오탈자 두 곳은 구현에서 바로잡았습니다: `_execute` 가 넘기는
두 번째 인자는 `request["source"]` 가 아니라 `request["scope"]` 이고, `_rerank`
는 `[float(hit.get("score") or 0.0) for hit in hits]` 입니다.

### chat 페이지 쪽에서 바뀐 것

- **Orchestrator** (`chat/orchestration.py`): agent runtime 일 때만 loop 전에
  `knowledge_data.rewrite_query(question)` 1회, 답변 후에
  `knowledge_data.generate_follow_ups(question, answer, sources)` 1회를 부릅니다.
  `question` 은 runtime 이 실제로 답하는 문장입니다 — mixed scope 면
  `supported_query`, 아니면 사용자 문장. Direct runtime 과 scope 거절 turn 은 둘 다
  건너뜁니다.
- **Rewrite 의 쓰임**: 사용자 메시지를 바꾸지 않습니다. `RuntimeRequest.rewrite`
  로 넘어가 agent system prompt 의 `retrieval_query` 줄이 되고, policy 에 "검색
  tool 의 query 로 이것을 우선 써라" 가 들어갑니다. 원문과 같으면 `None`.
- **실패 정책**: rewrite 실패는 turn 실패(`KnowledgeUnavailable`→503,
  `KnowledgeTimeout`→504, `KnowledgeDenied`→403; user turn 은 retry 용으로 남음).
  follow-ups 실패는 `skewnono.chat` logger 에 예외를 남기고 `[]` 저장 — 답변은
  살아남습니다.
- **저장**: assistant `Message` 에 `rewrite: str | None`, `follow_ups: list[str]`.
  SQLite 는 `messages.rewrite`, `messages.follow_ups_json` 열로 additive
  migration 합니다(기존 `chat.db` 도 그대로 열립니다).
- **SPA** (`components/chat/ChatMessage.vue`): 출처 아래에 "검색 질의" 줄(rewrite 가
  있을 때만)과 follow-up chip 을 그립니다. chip 을 누르면 composer 에 채우고
  바로 보내지는 않습니다.
- **집(mock)**: `knowledge/providers/mock.py` 의 `rewrite_query` 는 고정 약어·
  번역 표, `generate_follow_ups` 는 인용 제목에서 만든 질문 3개입니다. 모양만
  사무실과 같습니다.

## 2. 동거 방식 — RAG 저장소가 chat 아래에 있어도 안전한 이유

RAG 는 별도 git 저장소로 남고, `back_dev_home/chat/_rag/` 에 checkout 합니다.
이 저장소는 그 경로를 `.gitignore` 하며, 앞머리 밑줄이 나머지를 해결합니다.

| 걸림돌 | 처리 |
| --- | --- |
| Flask 가 `routes.py` 를 rglob 해 blueprint 로 등록 | `_` 경로는 건너뜁니다. RAG 에 `routes.py` 가 있어도 무관합니다. |
| office registry 가 `**/providers/{mock,office}.py` 를 glob | 같은 규칙. RAG 안의 `providers/` 폴더가 중복 slug 로 잡히지 않습니다. |
| pytest 가 `back_dev_home` 전체를 수집 | `pyproject.toml` 의 `--ignore=back_dev_home/chat/_rag`. |
| ruff | `.gitignore` 를 따르므로 자동 제외. |
| deploy pack | `back_dev_home` 통째로 복사되어 **함께 배포됩니다**. `.git` 만 prune 합니다. |

`from src.retrieve...` 는 checkout 루트가 `sys.path` 에 있어야 동작합니다.
chat 은 `chat/rag.py:import_rag("retrieve.serve")` 한 경로로만 import 하며, 루트를
한 번 `sys.path` 에 넣고 모든 실패를 `KnowledgeUnavailable`(HTTP 503)로 바꿉니다.
RAG 코드가 `sys.path` 를 직접 만질 필요는 없습니다.

## 3. RAG 측에 제안하는 것 (우선순위 순)

1. **최상위 패키지 이름을 `src` 에서 `skewnono_rag` 로 바꿔 주세요.**
   `src` 는 Python 에서 가장 충돌하기 쉬운 이름입니다. 사무실 `sys.path` 에
   다른 `src` 패키지가 하나라도 있으면 어느 쪽이 import 되는지 조용히 갈립니다.
   chat 쪽 변경은 `chat/rag.py` 의 `_PACKAGE = "src"` 한 줄입니다.

2. **`index_dir` 기본값을 절대 경로로.** 현재 기본값 `"index"` 는 프로세스 cwd
   기준입니다. cloud 의 Flask cwd 는 `/project/workSpace/` 이므로
   `/project/workSpace/index` 를 찾게 됩니다. chat 은 항상 절대 경로를 넘기지만,
   RAG 단독 실행에서도 같은 함정이 있으니 `Path(__file__)` 기준으로 잡아 주세요.

3. **오류를 타입으로 구분해 주세요.** chat 의 `_translate_error()` 는
   `TimeoutError` → 504, `PermissionError` → 403 만 구분하고 나머지는 전부
   503 입니다. deadline 초과와 권한 거부에 이 두 표준 예외(또는 그 하위 클래스)를
   써 주시면 사용자에게 다른 응답이 갑니다. 예외 메시지에 질의 원문을 넣지 마세요
   — chat 은 메시지를 그대로 로그에 남깁니다.

4. **`search_manuals(scope=…)` 가 `scope` 로 무엇을 하는지 명시해 주세요.**
   chat 계약은 "권한 필터는 질의 단계, 사후 Python 필터 금지" 입니다. 매뉴얼은
   지금 권한 제한이 없어 무시해도 결과는 같지만, "무시함" 이 명시되어야
   회의록·메일을 붙일 때 어디를 고칠지 압니다. 현재 datatable 에 OFFICE-VERIFY 로
   적어 두었습니다.

5. **모델은 프로세스당 1회 lazy-load, 그리고 thread-safe 하게.** uWSGI 는
   `lazy-apps` + worker N 개라 worker 마다 한 벌씩 올라갑니다(메모리 예산 확인).
   집 dev server 는 요청마다 새 thread 를 쓰므로 첫 호출의 로딩이 thread 안에서
   일어납니다 — 전역 lock 으로 한 번만 로딩되게 해 주세요.

6. **`rewrite_query` 는 원문을 보존한 채 덧붙이는 형태로.** 원문 단어를 지우고
   확장어로 바꾸면 BM25 leg 가 사용자가 쓴 표기를 못 맞춥니다. chat 은 결과가
   원문과 같으면 `None` 으로 저장하고, 비어 있으면 503 으로 처리합니다. 길이
   상한도 두어 주세요(system prompt 에 들어갑니다).

7. **`generate_follow_ups` 는 3~5개, 중복 없이, 사용자 언어로.** chat 이
   공백·중복·비문자열은 걸러내지만 언어 선택은 RAG 몫입니다. 인자 `sources` 는
   `Evidence` dict 목록(12 필드, `element_type` 은 이미 제거됨)입니다.

8. **호출당 deadline 을 받아 주세요.** chat 의 agent loop 는 60초 wall-clock
   으로 잘리지만, 그 뒤에도 RAG 호출은 thread 안에서 계속 돕니다. `timeout=`
   kwarg 하나면 chat 이 남은 시간을 넘길 수 있습니다(지금은 넘기지 않습니다).

9. **인덱스와 모델 파일은 checkout 밖 또는 RAG 의 `.gitignore` 안에.** deploy
   pack 이 `_rag/` 를 통째로 실으므로, 인덱스가 checkout 안에 있으면 번들에
   들어갑니다. 의도라면 괜찮지만 크기를 알고 결정해야 합니다.

10. **thread storage 를 어디에 둘지 함께 정해 주세요(handoff 3항).** 후보는
    OpenSearch(`skewnono_chat_logging` 과 같은 방식, 단 read-write), Redis
    (`redis_jobs.py` 의 쓰기 선례), 또는 SQLite 유지(`SKEWNONO_CHAT_DB` 를
    영속 경로로 — 단일 host 라면 코드 변경 없음). 결정되면 chat 측이 14 함수를
    씁니다. 그때까지는 handoff 대로 mock 을 유지합니다.

## 4. 검증 방법

- 집: `.venv/bin/python -m pytest back_dev_home/chat -q` — seam 은 가짜
  `src.retrieve` 패키지로 검증됩니다(`tests/test_knowledge_office_template.py`).
- 사무실: 같은 명령이 `office.py` 복사본에도 같은 테스트를 돌립니다. 실제 RAG 를
  붙인 뒤에는 `GET /api/health/providers` 로 `chat` 의 선택값을 확인하고,
  `/chat` 에서 agent runtime 한 turn 을 보내 assistant message 에 `rewrite` 와
  `follow_ups` 가 채워지는지 봅니다.

## 5. 맞물리는 계약 — 양쪽이 그대로 지켜야 하는 것

아래가 어긋나면 boot 는 되지만 첫 agent turn 에서 503 이 납니다. 왼쪽은 chat 이
호출하는 형태이고, 오른쪽은 RAG 가 지켜야 하는 것입니다.

| chat 이 부르는 것 | RAG 가 지킬 것 |
| --- | --- |
| `import src.retrieve.serve` / `import src.retrieve.agent` (루트 = `SKEWNONO_CHAT_RAG_ROOT`, 기본 `back_dev_home/chat/_rag`) | 루트 바로 아래에 `src/` 패키지가 있어야 합니다. `chat/rag.py` 는 `{root}/src` 디렉터리가 없으면 "checkout 없음" 으로 봅니다. 이름을 바꾸면(제안 1) 알려 주세요. |
| `search_manuals(query: str, scope: dict, *, limit: int, index_dir: str)` | 키워드 인자 `limit`, `index_dir` 를 받습니다. `scope` 는 `{"user_id": str, "groups": list[str], "fabs": list[str]}` 입니다. `limit` 은 **후보 수**(기본 24, 5~50)이며 절단은 chat 이 합니다. |
| 반환: hit `list[dict]`, rank 순 | 각 hit 에 `source_id`(str, 비어 있지 않음), `title`(str), `snippet`(str) 필수. `section`(str\|None), `page`(1-based int\|None), `figure_id`(str\|None, 맨 id — bucket/prefix/`.webp` 금지), `score`(float\|None) 선택. `element_type` 은 있어도 chat 이 버립니다. 빈 결과는 `[]` 이지 예외가 아닙니다. |
| `_rerank` 는 hit 의 `score` 를 그대로 씁니다 | `score` 가 rerank 점수(클수록 좋음)여야 합니다. retrieval 점수를 남겨 두면 정렬이 그 순서가 됩니다. NaN/inf 는 chat 이 503 으로 거부합니다. |
| `rewrite_query(question: str) -> str` | 비어 있지 않은 문자열. 원문을 포함(제안 6). 예외는 그대로 올리되 `TimeoutError`/`PermissionError` 로 구분(제안 3). |
| `generate_follow_ups(question: str, answer: str, sources: list[dict]) -> list[str]` | `sources` 는 chat 의 `Evidence` dict(12 필드) 목록입니다. 3~5개, 중복 없이. 예외는 chat 이 흡수해 `[]` 로 저장합니다. |
| `index_dir` 는 항상 절대 경로로 넘어옵니다 (`SKEWNONO_RAG_INDEX_DIR`, 기본 `{root}/index`) | 그 디렉터리가 없으면 chat 이 부르기 전에 503 을 냅니다. 인덱스를 다른 곳에 두면 `.env` 의 `SKEWNONO_RAG_INDEX_DIR` 로 알려 주세요. |
| 동시성: Flask thread 마다 호출, uWSGI worker 마다 프로세스 | 모듈 import 와 첫 호출이 여러 thread 에서 겹쳐도 안전해야 합니다(제안 5). |

### RAG 측 체크리스트 (붙이기 전)

- [ ] `back_dev_home/chat/_rag/src/retrieve/serve.py` 와 `agent.py` 가 위 세 함수를
  위 signature 로 export 합니다.
- [ ] RAG 저장소 안에 `routes.py` 가 있어도 상관없지만, **`bp` 라는 이름의
  Flask Blueprint 를 export 하지 않습니다** — `_` 경로라 스캔되지 않지만, 규칙을
  알아 두면 다른 경로로 옮길 때 안전합니다.
- [ ] RAG 의 의존성(torch, sentence-transformers 등)이 chat 이 도는 venv 에
  설치되어 있습니다. chat 은 RAG 를 같은 프로세스에서 import 합니다.
- [ ] 인덱스·모델 경로가 절대 경로이거나 `SKEWNONO_RAG_INDEX_DIR` 로 넘어옵니다.
- [ ] `.venv/bin/python -m pytest back_dev_home/chat -q` 가 사무실에서 통과합니다
  (복사본 `office.py` 에도 같은 seam 테스트가 돕니다).
- [ ] `/chat` 에서 agent turn 한 번: assistant message 에 `sources`, `rewrite`,
  `follow_ups` 가 채워집니다. `follow_ups` 가 `[]` 이면 `skewnono.chat` 로그를 봅니다.
