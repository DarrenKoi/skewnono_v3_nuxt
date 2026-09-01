# Chat office RAG 전환 가이드

이 문서는 사내 coding LLM이 현재 Flask/Nuxt 계약을 변경하지 않고 chat RAG 연결점을
구현하기 위한 handoff 계약입니다. 실제 hostname, credential, index alias, raw mapping,
사내 sample 문서 및 원문은 저장소에 commit하지 않습니다.

## 페이지 공개 여부

Chat은 2026-09-01 부터 production cloud를 포함한 모든 phase에서 정상 공개됩니다.
"준비 중" 안내는 이제 opt-in 이며, flag는 내려야 할 때를 위해 남겨 둡니다.

| 항목 | 값 |
| --- | --- |
| 환경 변수 | `SKEWNONO_CHAT_UNDER_DEVELOPMENT` (1/0) |
| 기본값 | `False` — 어디서나 정상 공개 (2026-09-01 이전에는 `is_cloud()`) |
| Endpoint | `GET /api/chat/availability` → `{"data": {"available": bool}}` |
| SPA | `pages/chat.vue`가 mount 시 1회 조회합니다. |

**페이지를 다시 내리려면 cloud host의 `.env`에 `SKEWNONO_CHAT_UNDER_DEVELOPMENT=1`을
넣고 재기동합니다.** RAG 장애처럼 급히 가려야 할 때 재배포 없이 처리하기 위한
장치이며, 코드 변경은 필요하지 않습니다.

이것은 **페이지 gate이며 authorization gate가 아닙니다.** `/api/chat/*`는 cloud에서도
계속 응답하므로 페이지가 가려진 상태에서도 API를 그대로 시험할 수 있습니다. 접근을
막아야 하는 상황이 오면 이 flag를 확장하지 말고 별도의 인증 장치를 씁니다.

SPA는 하나의 bundle이 세 phase에 모두 배포되므로 phase를 스스로 알 수 없습니다.
따라서 backend가 데이터로 알려주는 형태여야 하며, 프론트가 phase로 분기하지
않습니다. Availability 조회가 실패하면 안내가 아니라 정상 UI로 falls through
합니다 — backend 장애를 "서비스 시작 안 함"으로 잘못 표시하지 않기 위해서입니다.

## 유일한 선택점 — `_rag` 가 있는가

Chat 에는 provider selector 가 없습니다. 사내 RAG 가 model, prompt, gateway
키를 모두 소유하므로 chat 은 자체 LLM 호출을 하지 않고, 남은 질문은 하나뿐
입니다 — **이 기계에 답할 수 있는 RAG 가 있는가.**

| 판정 | 조건 | 결과 |
| --- | --- | --- |
| office | `{root}/skewnono_rag/retrieve/agent.py` 가 있고 `{root}/skewnono_rag/index/` 가 비어 있지 않음 | `answer/providers/rag.py` 가 `agent_query` 로 답합니다. Figure 도 MinIO 에서 읽습니다. |
| mock | 그 밖의 모든 경우 | `answer/providers/mock.py` 가 fixture 로 답합니다. Figure 는 디스크에서 읽습니다. |

`root` 는 `SKEWNONO_CHAT_RAG_ROOT`, 미설정이면 `back_dev_home/chat/_rag` 입니다
(`rag.py` 의 `rag_ready()`). 판정은 **import 이 아니라 파일 존재 확인**입니다 —
부팅 시점에 faiss·torch 를 끌어와 앱을 죽이지 않기 위해서입니다. 따라서 체크아웃은
있는데 import 이 깨진 경우는 `office` 로 판정된 뒤 요청마다 `503` 이 됩니다. 그것이
맞는 자리입니다: 조용히 mock 으로 내려가 가짜 답을 내놓는 것보다 낫습니다.

부팅 로그가 어느 쪽으로 판정했는지 한 줄로 찍습니다.

```text
  chat/answer  office  RAG checkout at /project/workSpace/back_dev_home/chat/_rag
  chat/answer  mock    no RAG checkout
```

되돌리는 방법은 체크아웃을 치우거나 `SKEWNONO_CHAT_RAG_ROOT` 를 빈 디렉터리로
돌리는 것입니다. 요청 도중 자동 fallback 은 없습니다.

Thread 저장소는 이 축과 무관합니다 — 사무실에서도 SQLite(`chat/store.py`)
이며 `SKEWNONO_CHAT_DB` 만 영속 경로로 둡니다(아래 "Thread storage 동기화").

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

Assistant message는 `status`, `runtime`, `scope_status`, `sources`, `feedback`을
포함합니다. Frontend와 backend의 해당 타입도 같은 release 단위로 유지합니다.

### Turn 은 요청이 아니라 리소스입니다 (2026-09-01)

`POST` 는 답변을 기다리지 않습니다. assistant 행을 `pending` 으로 예약하고
**202** 로 즉시 돌려주며, 답변은 백그라운드 worker 가 만들어 SQLite 에 씁니다.
SPA 는 `GET /api/chat/threads/<id>` 를 2초 간격으로 폴링해 그 행이
`done` 또는 `failed` 로 정착하는 것을 봅니다. 전용 폴링 엔드포인트는 없습니다 —
스레드 조회가 이미 그 행을 내려주고, 그래서 새로고침이 진행 중인 turn 을 그대로
이어받습니다.

| 응답 | 언제 |
| --- | --- |
| `202` + `status: "pending"` | worker 가 답변을 만드는 중 |
| `200` + `status: "done"` | scope 거절(0ms)이거나 이미 끝난 turn 의 재생 |
| `503` | scope 게이트 자체가 사용 불가(`ScopeUnavailable`). 유일하게 인라인으로 남은 실패 |

**답변 실패는 HTTP 오류가 아닙니다.** 답변이 요청 스레드에서 일어나지 않으므로,
403/503/504 로 나가던 것이 이제 그 turn 의 행에 `status='failed'` 와
`error_code` 로 남습니다. `error_code` 는 이 모듈이 오류 본문에 쓰는 문자열과
같은 어휘(`runtime_denied` / `runtime_unavailable` / `gateway_timeout`)이므로
SPA 는 한 벌만 알면 됩니다.

**같은 `request_id` 의 재요청**은 진행 중인 turn 에 합류하고(RAG 에 두 번 묻지
않습니다), 실패한 turn 은 같은 행에서 다시 시작합니다. 행은 turn 당 하나이며
시도마다 늘지 않습니다.

**고아 `pending`** 은 청소 작업이 아니라 읽을 때 나이로 판정합니다 —
`created_at` 이 예산 + 30초를 넘긴 pending 은 `gateway_timeout` 실패로 보입니다.
부팅 훅으로 일괄 처리하지 않는 이유는 `lazy-apps` 때문입니다: 워커가 각자
부팅하므로 4번 워커가 뜨면서 1번 워커의 진행 중인 turn 을 죽이게 됩니다.

`GET /api/chat/availability` 는 `answer_timeout_seconds` 도 함께 돌려줍니다.
SPA 가 "42초 경과 / 최대 240초" 를 그리는 데 쓰며, 그 숫자는 서버의 것입니다.

혼합 배포는 여기서도 허용하지 않습니다 — 구형 SPA 는 202 를 완성된 답변으로
읽습니다.

## RAG 동거(co-location) — 사내 RAG 저장소를 chat 아래에 두는 방법 (2026-08-28)

사내 RAG는 별도의 git 저장소이며(공개 저장소인 이곳에 절대 push 하지 않습니다),
chat 은 그것을 **같은 프로세스 안에서 import** 합니다 — Flask 와 인덱스 사이에
서비스가 없습니다. RAG 측 handoff 는 `docs/datatables/chat/chat_office_adapter_handoff.txt`
(2026-08-27)이고, 공개 API 는 다음 셋입니다(office 확인 2026-08-27).

| 단계 | RAG 함수 | chat 쪽 호출 지점 |
| --- | --- | --- |
| turn 마다 1회 | `skewnono_rag.retrieve.agent.agent_query(question, messages, scope, timeout=)` | `answer/providers/rag.py` |

최상위 패키지는 `skewnono_rag` 입니다(2026-08-28 에 `src` 에서 개명, RAG 측
확인). `timeout=` 초를 넘기면 `TimeoutError` 를, 권한 거부는 `PermissionError`
를 올립니다(RAG 측 확인 2026-08-28) — chat 은
`SKEWNONO_CHAT_ANSWER_TIMEOUT`(기본 240)을 넘기고 adapter 가 각각 504/403 으로
바꿉니다.

반환값의 필드 규칙·호출 서명·예외 대응은 산문이 아니라 코드입니다 —
`answer/contract.py` 하나이며, chat 이 turn 마다 `validate_answer()` 로
검사하고 RAG 측은 사무실에서 같은 모듈을 직접 돌립니다.

```bash
python -m scripts.verify.check_answer_contract          # 계약 출력 + 자체 검사
python -m scripts.verify.check_answer_contract --live   # 실제 agent_query 1회
```

필수 키(`content`, `sources`, `follow_ups`, `rewrite`, `tool_traces`)는
**present 여야 하고 값은 비어 있어도 됩니다**. token 수 두 개만 합의된
선택 항목입니다. 5건 상한을 넘긴 인용은 거절이 아니라 절삭입니다.

검색 반복과 답변 생성은 **전부 RAG 안**입니다. chat 쪽에는 agent loop 도,
검색 tool 도, LLM client 도 없습니다(2026-08-31 삭제).

**배치.** Co-location 루트는 `back_dev_home/chat/_rag/` 입니다(RAG 측 확인
2026-08-31). `_rag/` 자체는 우리 것이고, 그 안의 `skewnono_rag/` 가 RAG 측이
통째로 전달·교체하는 read-only 패키지입니다 — 여기서 절대 수정하지 않습니다.
빌드된 인덱스는 패키지 **안** `skewnono_rag/index/` 에 함께 옵니다(db, vectors,
faiss, bm25 네 파일). 패키지는 완전히 self-contained 입니다 — common LLM
gateway 키(`LLM_BASE_URL_HCP`, `API_KEY_FREE_HCP` — 초기의
`LLM_BASE_URL_COMMON`/`API_KEY_RPO` 에서 RAG 측이 개명, RAG 측 확인 2026-09-01)는
`skewnono_rag/config.py` 에 내장되어 있으므로 `.env` 를 어디에도 만들지
않습니다(RAG 측 확인 2026-08-31; 초기의 `_rag/.env` 안은 철회됨). skewnono 의
`back_dev_home/.env` 에도 넣지 않습니다. 앞머리 밑줄이 이 배치를 안전하게
만드는 전부입니다.

RAG 가 office 에서 요구하는 의존성(RAG 측 확인 2026-08-31): `faiss-cpu`,
`rank_bm25`, `numpy`, `langchain`, `langgraph`, `langchain-openai`,
`langchain-core`, `python-dotenv`, `requests`. skewnono 의 venv 에 함께
설치합니다(같은 프로세스 import 이므로). faiss-cpu 는 skewnono 가 pin 한
`numpy>=2` 와 호환됩니다(RAG 측 확인 2026-08-31).

| 걸림돌 | 왜 `_rag/` 가 걸리지 않는가 |
| --- | --- |
| Blueprint 자동 탐색(`routes.py` rglob) | `_` 로 시작하는 경로를 건너뜁니다. RAG 에 `routes.py` 가 있어도 boot 가 깨지지 않습니다. |
| Office registry(`**/providers/{mock,office}.py` glob) | 같은 규칙. RAG 안의 `providers/` 폴더가 중복 slug 로 잡히지 않습니다. |
| Deploy pack | `_` 경로를 걷지 않는 규칙은 없지만 `back_dev_home` 통째로 복사하므로 **함께 실립니다**(의도). 대신 `.git` 은 `PRUNE_DIRS` 로 버립니다. |
| ruff | `.gitignore` 를 따르므로 무시합니다. |
| pytest | `.gitignore` 를 따르지 **않으므로** `pyproject.toml` 의 `--ignore=back_dev_home/chat/_rag` 가 막습니다. |
| git | `.gitignore` 의 `back_dev_home/chat/_rag/`. `skewnono_rag/` 갱신은 RAG 측 전달로 통째 교체합니다(사내 저장소라면 `git -C back_dev_home/chat/_rag/skewnono_rag pull`). Submodule 은 쓰지 않습니다 — 사무실은 GitHub 에 로그인할 수 없고 RAG 저장소는 사내 전용입니다. |

`from skewnono_rag.retrieve...` 가 동작하려면 checkout 루트가 `sys.path` 에 있어야 하는데,
Flask 는 저장소 루트에서 뜨므로 저절로 되지 않습니다. `chat/rag.py` 의
`import_rag("retrieve.serve")` 가 유일한 import 경로입니다 — 루트를
`SKEWNONO_CHAT_RAG_ROOT`(미설정이면 `_rag/`)에서 찾아 한 번만 `sys.path` 에 넣고,
checkout 이 없거나 사내 의존성이 빠진 모든 실패를 `KnowledgeUnavailable`(503)로
바꿉니다. 인덱스 경로는 `SKEWNONO_RAG_INDEX_DIR`(미설정이면 패키지 안
`{root}/skewnono_rag/index`, RAG 측 확인 2026-08-31)이며
항상 절대 경로로 넘깁니다 — RAG 의 기본값은 상대 경로 `"index"` 라 cloud 에서는
`/project/workSpace/index` 를 찾게 됩니다.

**Rewrite 와 follow-ups 의 동작 계약.**

- 둘 다 agent runtime 에서만 호출합니다. Direct runtime 은 retrieval 이 없으므로
  둘 다 건너뛰고 `rewrite=None`, `follow_ups=[]` 을 저장합니다. Scope 거절 turn 도
  같습니다.
- Rewrite 대상은 사용자 문장 그대로입니다. 결과가 원문과 같으면 `None` 으로
  저장합니다.
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

## Answer seam — turn 전체를 한 번의 호출로

계약 원본은 `docs/2026-08-31-chat-to-rag-answer-contract-agreed.md` 이며, 여기
요약하지 않습니다.

| 조각 | 위치 |
| --- | --- |
| Provider 선택 | `answer/data.py` — `rag.rag_ready()` 하나. env 없음, `cp` 없음 |
| Office adapter | `answer/providers/rag.py` — `agent_query(question, messages, scope, timeout)` 호출 + 3종 오류 변환 + Evidence 모양 검증(5건 cap) + 바깥 hard guard(+5초). **추적되는 파일**이므로 사무실에서 복사할 것이 없습니다 |
| Mock answerer | `answer/providers/mock.py` — knowledge fixture 로 만든 고정 템플릿 답변. 네 개 retrieval tool(manual·meeting·email·report)을 모두 부르고 점수로 합쳐 5건까지 냅니다 — manual fixture 만 `figure_id` 를 가지므로 manuals 만 뒤지면 사무실의 흔한 상태인 *그림 없는 인용*이 집에서 재현되지 않습니다(2026-09-01) |
| History cap | dispatcher 가 `SKEWNONO_CHAT_ANSWER_MAX_HISTORY`(기본 5 = RAG 의 MAX_HISTORY, RAG 측 확인 2026-08-31)로 자름 |
| Turn 예산 | `SKEWNONO_CHAT_ANSWER_TIMEOUT`(기본 240초, 1~360). cap 360 + adapter grace 5초 = 365초가 앱이 스스로 504 를 내는 시점이므로 `wsgi.ini` 의 harakiri(380)는 항상 그 위에 있어야 합니다 |
| Orchestrator | scope 판정 → answer 호출 1회 → 저장 → 로깅. rewrite·follow-ups 는 결과 안에 실려 오므로 자체 호출이 없습니다 |

구 경로(chat 측 agent loop, `llm.py`, egress guard, tool 6종, knowledge 검색
seam)는 **사무실 full-path 검증 전에** 사용자 결정으로 삭제했습니다
(2026-08-31). 되살릴 곳은 git 이며 삭제 커밋 하나를 되돌리면 됩니다.

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
| `office` 설정 | `SKEWNONO_CHAT_FIGURE_BUCKET`(보통 비움 = client 기본 `user`), `SKEWNONO_CHAT_FIGURE_PREFIX`(기본 `skewnono_rag/hitachi_manuals/figures/`) |
| 검증 | 저장소에 닿기 전에 `^[\w .-]{1,128}$` 불일치, `..` 포함, 앞머리 점이면 `404` |
| 응답 | `image/webp` + `Cache-Control: public, max-age=3600` |

사무실의 실제 객체 키는 다음과 같습니다(RAG 측 확인 2026-08-31; 2026-08-27 의
`hitachi_sem/manual_figures/` 배치를 대체합니다).

```text
user/2067928/skewnono_rag/hitachi_manuals/figures/CG6300_1.HHTSEM_SYSTEM_p100_i0.webp
^bucket ^client prefix ^SKEWNONO_CHAT_FIGURE_PREFIX (기본값)  ^figure_id
```

사용자 namespace `2067928/`는 MinIO client의 **자체 기본 prefix**(`minio_handler`의
`PREFIX` / `MINIO_PREFIX`)이고, 앱은 그 아래 키만 넘깁니다 —
`MinioObject().get("skewnono_rag/hitachi_manuals/figures/<id>.webp")`. 이것은 `msr_image`의
image cache와 **반대 규약**입니다. 그쪽은 client prefix를 비우고 `2067928/image_cache/`를
자기 prefix에 적습니다. 둘 다 동작하며 섞는 것이 함정입니다 —
`SKEWNONO_CHAT_FIGURE_PREFIX`에 `2067928/`를 적으면 키가 `2067928/2067928/...`으로
겹쳐 모든 그림이 404 납니다. Prefix 는 RAG ingestion 의 namespace(`skewnono_rag/`
+ 매뉴얼 family 구간)이므로 다른 family의 그림은 다른 prefix로 가지, 다른 bucket으로
가지 않습니다.

MinIO 오류 중 `NoSuchKey`/`NoSuchObject`/`NotFound`는 그냥 miss(404)입니다. 그 밖의
오류(scoped credential의 `AccessDenied` 등)도 404이지만 warning 로그를 남깁니다 —
남기지 않으면 bucket 설정 오류가 "그림을 추출하지 않은 매뉴얼"과 구분되지 않습니다.

`chat/tests/test_figures.py`의 디스크 테스트는 MinIO 구현 전후로 한 줄도 바뀌지
않았습니다 — 테스트를 HTTP 경계에만 걸어 둔 이유가 이것입니다. MinIO 쪽은 같은 파일
하단에서 fake client로 키 조립·miss·오류 로그·검증 선행을 고정합니다.

### 검증 charset이 공백과 한글까지 허용하는 이유

Office의 figure_id 형식은 `{stem}_p{page}_i{idx}`이고, stem은 매뉴얼 **파일 이름**입니다.
파일 이름은 담당자가 붙인 임의의 텍스트이므로 점(`CG6300_1.HHTSEM_SYSTEM_p100_i0`,
office 확인 2026-08-19)뿐 아니라 공백과 한글(`CD-SEM 사용 설명서 v1.2_p12_i0`)이
정상입니다. ASCII만 받는 charset은 이런 매뉴얼의 그림을 전부 **거부합니다**.

이 조합이 위험한 이유는 실패가 조용하기 때문입니다. Mock fixture의 id가 실제보다 단정하면
집에서는 모든 테스트가 통과하고, 사무실에서만 그림이 404가 나며, 그마저도 오류가 아니라
"썸네일이 안 보인다"로 나타납니다. 그래서 charset을 파일 이름이 담는 범위까지 넓혔습니다 —
`\w`(str 패턴이므로 이미 유니코드 인식) + `.` + `-` + 공백. Mock fixture 쪽도 같은 이유로
점을 가진 id 하나와 공백·한글을 가진 id 하나를 함께 둡니다.

Charset을 넓히면 `..`가 charset만으로는 걸러지지 않으므로 세 겹으로 막습니다.

1. `..`를 포함한 id는 이름으로 거부합니다.
2. Slash와 backslash는 charset(`\w`에 경로 구분자가 없습니다)과 Flask routing 양쪽에서
   막힙니다 — routing이 `../`를 정규화하므로 view까지 도달하지도 않습니다.
3. 디스크 경로는 조립한 경로를 `resolve()`한 뒤 부모가 figures 디렉터리인지 확인합니다.
   저장소 밖으로 나가는 symlink도 여기서 걸립니다.
4. 앞머리 점(`.`, `.foo`)은 이름으로 거부합니다. 맨 `.` 하나는 charset을 통과하고 `..`도
   아니어서, MinIO 경로에서는 `.../..webp` 키로 저장소까지 갔습니다(2026-08-27에 MinIO
   테스트가 잡아냈고, 디스크 경로는 3번 검사로만 살아남고 있었습니다).

Mock fixture의 id는 실제 형식을 따릅니다 — `SYN6300_1.EBEAM_ALARM_p12_i0`(점)과
`SYN 전자광학 조정 안내서 v2.1_p21_i0`(공백·한글)이 한 파일에 함께 있습니다
(`__fixtures__/knowledge/manuals.json`).

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

Prefix를 환경 변수로 두는 이유는 배치가 RAG ingestion 소관이라 또 옮겨질 수 있기
때문입니다(실제로 2026-08-31 에 `hitachi_sem/manual_figures/` 에서 옮겨졌습니다). 사용자
namespace 제한은 MinIO client의 기본 prefix가 이미 감당하므로, 이전에 적었던
`user/2067928/figures/` 같은 전체 경로를 prefix에 넣는 안은 폐기했습니다 — 넣으면
namespace가 두 번 붙습니다(위 표 아래 설명).

## Scope 사전 게이트

`scope/policy.py` 하나이며 집과 사무실이 같은 어휘를 씁니다 — 무엇을 답하는
서비스인가는 제품 결정이지 어느 기계에서 도는지의 문제가 아니기 때문입니다.
(mock/office 로 갈라져 있던 것을 2026-08-31 합쳤습니다. 그 분기가 실제로 뜻한
바는 "집에서는 한국어 질문을 거절한다" 였고, 그것을 원한 테스트는 없었습니다.)

**2026-09-01 부터 deny-list 입니다.** 명시적으로 도메인 밖인 marker(영화, 주식,
날씨 …)가 없으면 통과시킵니다. 그전에는 반대로 도메인 marker 를 **요구**했고,
그 결과 어휘에 없는 용어로 물으면 거절했습니다 — "MDC에 대해서 알려줘" 가
`mdc` 가 목록에 없다는 이유로 막혔습니다. 우리가 미리 떠올린 단어만 담긴
allow-list 는 하필 사용자가 모르는 용어에서 가장 크게 실패하며, 목록에 있는 말로
바꿔 물으려면 이미 답을 알아야 합니다. 진짜 필터는 retrieval 입니다: 도메인 밖
질문은 근거를 못 찾아 "근거 없음" 으로 정직하게 답하고, 검색 한 번을 씁니다.
잘못된 거절의 대가는 답 그 자체입니다.

어휘는 RAG handoff 가 정한 도메인 marker(`ebeam, metrology, measurement, tool,
alarm, manual, recipe, error, cd-sem, sem, calibration, optics, vacuum, stage,
wafer, idp, amp, hitachi, gt2000, cg6300`)에 한국어 대응어를 짝지은 것입니다.
이제 이 목록이 결정하는 것은 하나입니다 — off-topic marker 가 걸린 질의에
**업무 부분이 조금이라도 있는가**. 반환 `status` 는 `in_scope`,
`out_of_scope`, `unsafe` **셋**이며 `reason_code` 를 함께 냅니다.

**`mixed` 는 2026-09-01 에 없앴습니다.** 업무 주제와 off-topic 이 한 질의에
같이 있으면 예전에는 정규식으로 절을 잘라 지원되는 부분만 RAG 에 보냈고,
자를 경계가 없으면 **매칭된 marker 단어만 이어 붙여** 보냈습니다 —
`"계측 알람"` 같은, 아무도 하지 않은 질문이었고 그것을 "답변했습니다" 라는
고지와 함께 내보냈습니다. 지금은 그런 질의를 **사용자가 쓴 그대로** 묻습니다:
업무 부분은 근거를 찾고 나머지는 못 찾으므로, 잘라낸 질문보다 정직합니다.
`supported_query` 필드와 `ScopeUnavailable` 도 함께 사라졌습니다.

`reason_code` 는 셋을 가릅니다 — marker 로 통과한 `supported_domain`,
marker 없이 기본 허용으로 통과한 `no_marker_default_allow`, off-topic 절을
끼고 통과한 `off_topic_clause_ignored`. 셋 다 messages 테이블에서 세어 볼 수
있으므로 "허용 기본값이 얼마나 자주 turn 을 나르는가" 가 추측이 아니라
질의입니다.

## Thread storage 동기화

**2026-08-28 결정(RAG 측 확인): office thread storage 는 SQLite 입니다.**
`providers/office.py` 를 만들지 않고 `SKEWNONO_CHAT_DB` 만 영속 경로로 둡니다.
단일 host 이므로 코드 변경이 없고, uWSGI worker 여럿이 한 파일을 여는 것은
SQLite 의 파일 잠금이 처리합니다. deploy pack 은 `*.db` 를 prune 하므로 번들이
cloud 의 thread 를 덮어쓰지 않습니다. 아래 절은 저장소를 multi-host 로 옮길
때만 유효합니다.

이 결정 때문에 thread storage 에는 seam 자체가 **없습니다**(2026-09-01).
`providers/` 폴더도 `data.py` dispatcher 도 지우고 구현을 `chat/store.py` 하나로
두었습니다 — adapter 가 하나뿐인 swap surface 는 영영 swap 되지 않고, 그 자리에
남아 있는 동안 부팅 표에 `chat  mock  no office adapter planned` 라는, 없는
결정을 기다리는 것처럼 보이는 행을 찍습니다. 이제 `chat` 은 provider 표에
나오지 않고(registry 는 `providers/mock.py` 로 feature 를 셉니다), 답변 축만
`chat/answer` 행으로 남습니다. Office thread storage 를 언젠가 따로 쓴다면 그때
`providers/{mock,office}.py` 를 만들어 seam 을 되살리고 `contracts.py` 의 의미를
유지합니다. 특히 다음을 보장합니다.

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

`office.py` 는 구현과 fake-client 검증이 끝나기 전에는 만들지 않습니다 —
존재 자체가 스위치입니다.

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

### Home

집에서는 체크아웃이 없으므로 mock 경로가 돌고, RAG 경로는 `skewnono_rag` 를
가짜로 끼워 `test_answer_rag.py` 가 검증합니다 — office adapter 가 추적되는
파일이라 사무실 복사본을 기다리지 않고 집에서 그대로 실행됩니다.

```bash
.venv/bin/python -m pytest back_dev_home/chat -q
```

### Office-local smoke

집 test 가 통과한 뒤, 사무실에서 체크아웃을 제자리에 두고 부팅 로그가
`chat/answer  office` 를 찍는지 먼저 확인합니다. 그 다음 승인된 비민감 질문 한 건을
실제로 보내 source type, provenance, 접근 거부를 확인합니다.

```bash
.venv/bin/python index.py            # 부팅 로그의 chat 행을 읽습니다
curl -s -b LASTUSER=<사번> -X POST localhost:5000/api/chat/threads
curl -s -b LASTUSER=<사번> -X POST localhost:5000/api/chat/threads/<id>/messages \
  -H 'Content-Type: application/json' \
  -d '{"content":"<승인된 질문>","request_id":"<uuid>"}'
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
