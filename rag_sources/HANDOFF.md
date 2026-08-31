# Chat RAG 데이터 준비 체크포인트와 사내 LLM 프롬프트

작성일: 2026-08-02. **2026-08-31 갱신**: 답변 생성 경계가 RAG 쪽으로
넘어갔습니다 — chat 에는 agent loop 도, 검색 tool 도, LLM client 도 없고
`agent_query` 한 번의 호출이 turn 전체를 답합니다. provider 선택 환경 변수도
없어졌으며, `_rag` 체크아웃의 존재가 mock/office 를 정합니다. 아래 3~5절의
sadari 절차는 그 이전 구조를 전제하므로 `back_dev_home/chat/MIGRATION.md` 를
먼저 읽으십시오. 이 문서는 사내 RAG side project에서 로컬 LLM(GLM-5.2,
pi coding agent)으로 RAG 데이터를 생성할 때 사용할 목표 설명, 체크포인트,
복사-붙여넣기용 프롬프트를 제공합니다. 원문 배치 위치인 이 디렉터리
(`rag_sources/`, 계약은 같은 폴더의 `README.md`)에 함께 둡니다. Skewnono 저장소 쪽
계약의 원본은 `back_dev_home/chat/MIGRATION.md`이며, 이 문서는 그 계약을 "데이터를
만드는 쪽" 관점으로 재정리한 것입니다.

## 1. 우리의 목표

SKEWNONO chat 페이지가 mock 응답이 아니라 **사내 실제 업무 자료 — 장비 manual,
회의 요약, 이메일, 업무 보고서 — 에 근거한 답을 출처(provenance)와 함께 제공**하게
만드는 것이 목표입니다. 계측 엔지니어가 "이 alarm 복구 절차가 뭐였지", "지난 회의에서
그 장비 어떻게 하기로 했지" 같은 질문을 chat에 물으면, agent가 read-only retrieval
tool로 근거를 모아 답하고 각 답에 출처 chip이 붙습니다.

역할 분담은 다음과 같습니다.

- **RAG side project(이 문서의 독자)** — 원문을 ingestion해 versioned read-only
  index와 provenance manifest를 만들고, skewnono가 소비할 수 있는 계약 형태로
  배포합니다. 원문 배치 지점이 이 디렉터리이며, 운영 경로는
  `SKEWNONO_RAG_SOURCE_ROOT`로 지정합니다.
- **Skewnono chat(이미 준비됨)** — 그 index를 gitignored office adapter로 조회하고,
  agent runtime이 제한된 tool 호출로 근거를 모아 citation과 함께 답합니다.

품질 원칙은 하나입니다: **근거 없는 답을 근거 있는 답처럼 보이게 하지 않습니다.**
근거가 없으면 없다고 답하고, retrieval 실패는 typed 오류로 드러나며 mock이나 다른
source로 조용히 대체하지 않습니다. 향후 확장으로 MinIO에 저장된 이미지(stable
object key)를 출처에 연결하는 것을 계획하고 있으므로, 데이터를 만들 때부터 이미지
key를 manifest에 남겨 두면 재색인 없이 연결할 수 있습니다.

## 2. Feasibility 결론

Chat backend는 office 데이터를 받을 준비가 되어 있습니다. 2026-08-02 기준 확인
내용은 다음과 같습니다.

- `back_dev_home/chat` 전체 test 146건이 통과합니다 (agent runtime, 네 개의
  read-only retrieval tool, typed error 변환, no-fallback 규칙 포함).
- Knowledge/scope/thread-storage 세 swap surface 모두
  `providers/office_example.py` template이 존재하며, 구현 전에는 fail-closed로
  `KnowledgeUnavailable`(HTTP 503 계열)을 반환합니다. Mock으로 자동 전환하지
  않습니다.
- Frontend(`chat.vue`, `ChatMessage.vue`, `ChatSources.vue`)는 `request_id`
  idempotency 계약과 `sources` 표시를 이미 구현했습니다.

따라서 사내에서 남은 작업은 (1) RAG 데이터/index 생성(별도 side project),
(2) gitignored `office.py` adapter 구현, (3) access resolver·LLM gateway·retention
job 배정입니다. 이 문서는 (1)과 (2)를 위한 입력입니다.

## 3. RAG 데이터가 최종적으로 도달해야 하는 계약

Adapter가 반환하는 각 검색 결과는 `back_dev_home/chat/knowledge/contracts.py`의
`Evidence`와 정확히 일치해야 합니다. 즉 **RAG index의 record 하나가 아래 필드를
만들 수 있어야** 합니다.

| Field | 규칙 |
| --- | --- |
| `source_id` | 재색인 후에도 유지되는 stable ID입니다. Revision이 바뀔 때만 바뀝니다. |
| `source_type` | `manual`, `meeting`, `email`, `report` 네 가지뿐입니다. |
| `title` | 사용자 노출이 승인된 제목입니다. |
| `snippet` | 승인된 최소 근거 text입니다. 원문 전체를 넣지 않습니다. 앱이 1,200자(기본)로 자르므로 그 이하를 권장합니다. |
| `revision` | Manual/report revision, 없으면 `None`입니다. |
| `occurred_at` | 정규화된 기준일(ISO-8601, timezone 명시), 없으면 `None`입니다. |
| `section` | Section provenance, 없으면 `None`입니다. |
| `page` | 1-based page 번호, 없으면 `None`입니다. |
| `region` | 승인된 page region reference, 없으면 `None`입니다. |
| `locator` | 안정된 승인 locator입니다. 임의 URL·filesystem path·MinIO URL을 넣지 않습니다. |
| `score` | Ranking 진단용, 없으면 `None`입니다. |

Home mock fixture(`back_dev_home/chat/__fixtures__/knowledge/*.json`)가 이 형태의
살아 있는 예시입니다. Mock record는 Evidence 필드에 더해 `access`
(`users`/`groups`/`fabs`)와 `search_text`를 가지는데, 사내 index에도 **동일한
역할의 access metadata가 record 단위로** 있어야 합니다. Access filter는 검색
query 단계에 적용해야 하며, 검색 후 Python filtering으로 보완하는 방식은 계약
위반입니다.

## 4. RAG 데이터 생성 체크포인트

Ingestion/chunking/색인을 만드는 쪽에서 하나라도 빠지면 adapter를 아무리 잘
구현해도 계약을 만족할 수 없는 항목들입니다.

- [ ] **Provenance가 chunk까지 살아남습니다.** Chunk마다 document ID, revision,
  section, page(1-based), region을 유지하고, chunk/vector ID → (document,
  section, page, region) manifest를 함께 산출합니다.
- [ ] **`source_id`가 재색인에 안정적입니다.** ID를 embedding hash나 색인 순서로
  만들지 않습니다. 문서 identity + revision에서 유도합니다.
- [ ] **Revision 우선순위가 데이터에 반영됩니다.** Manual/report는 최신 revision
  우선, superseded 문서 제외 규칙을 색인 단계에서 적용하거나 metadata로 구분
  가능해야 합니다.
- [ ] **Access metadata가 record 단위로 붙습니다.** 허용 `users`/`groups`/`fabs`
  를 색인 시점에 기록해 query-time filter가 가능해야 합니다. 권한 없는 source는
  존재·title·count·score도 노출되지 않아야 합니다.
- [ ] **날짜가 정규화됩니다.** Meeting/email/report의 기준 date field와 timezone을
  하나의 규칙으로 통일해 `occurred_at`으로 변환 가능해야 합니다.
- [ ] **Snippet은 승인된 최소 근거입니다.** 원문 전문·개인정보·비승인 필드가
  snippet과 title에 들어가지 않도록 projection을 색인 단계에서 제한합니다.
- [ ] **Embedding 정합성이 기록됩니다.** Embedding model identity, dimension,
  index build version을 artifact에 함께 기록해 서로 불일치하면 배포가 거절되게
  합니다.
- [ ] **Artifact는 versioned/immutable입니다.** Skewnono runtime은
  `SKEWNONO_RAG_SOURCE_ROOT` 아래 offline ingestion이 만든 read-only artifact만
  열며 스스로 색인을 만들지 않습니다. Active version 전환은 atomic switch로
  설계합니다.
- [ ] **(선택, 향후 이미지 대비)** Source에 대응하는 이미지가 MinIO에 있다면
  manifest에 **stable object key**(승인된 prefix 아래)를 지금 기록해 둡니다.
  이후 `image_ref` 확장 시 재색인 없이 연결할 수 있습니다. Index나 Evidence에
  raw MinIO URL을 넣지 않습니다.
- [ ] **저장소·로그 위생.** 실제 hostname, credential, index alias, 원문, page
  image는 git 저장소·test fixture·log 어디에도 남기지 않습니다.

## 5. 사내 로컬 LLM용 프롬프트

아래 프롬프트는 그대로 복사해 사내 coding LLM(GLM-5.2, pi coding agent 하에서
동작)에 입력하는 용도입니다. `< >` 부분만 사내 값으로 치환합니다. 공통 전제: 사내
agent는 public skewnono 저장소 파일을 직접 읽을 수 있으므로 프롬프트는 경로만
가리키고, 실제 hostname/credential은 프롬프트에 넣지 않습니다.

### Prompt 1 — RAG ingestion 출력 schema 설계·검증

```text
너는 사내 RAG side project의 ingestion pipeline을 설계한다. 출력 데이터는 skewnono
chat이 소비하며, 최종 계약은 skewnono 저장소의
back_dev_home/chat/knowledge/contracts.py 의 Evidence TypedDict와
back_dev_home/chat/__fixtures__/knowledge/*.json 의 record 형태다.

요구사항:
1. source_type은 manual/meeting/email/report 네 가지로 정규화한다.
2. 각 chunk record는 Evidence의 모든 필드를 만들 수 있어야 한다: stable
   source_id(문서 identity+revision에서 유도, 재색인에 불변), title, snippet(승인된
   최소 근거, 1200자 이하), revision, occurred_at(ISO-8601+timezone), section,
   page(1-based), region, locator(안정된 승인 locator, URL/경로 금지).
3. 각 record에 access metadata(users/groups/fabs)를 붙여 query-time filter가
   가능하게 한다.
4. chunk/vector ID -> (document, section, page, region) manifest를 별도 산출한다.
5. embedding model identity/dimension/index build version을 artifact metadata로
   기록한다.
6. 산출물은 versioned immutable artifact이며 active version은 atomic하게 전환한다.
7. (있다면) source별 MinIO 이미지의 stable object key를 manifest에 기록한다. raw
   URL은 기록하지 않는다.

작업: <대상 source: 예. 장비 manual PDF 묶음>에 대해 (a) record JSON schema,
(b) chunking 규칙(경계·크기·provenance 유지 방식), (c) manifest schema,
(d) 위 7개 요구사항 각각의 검증 방법을 제시하라. 실제 hostname/credential/원문은
출력에 포함하지 마라.
```

### Prompt 2·3 — 철회 (2026-08-31)

`knowledge/providers/office.py` 구현과 그 fake-client contract test 를 지시하던
두 프롬프트는 삭제했습니다. 검색은 이제 RAG 안에서 일어나고 chat 쪽에는 그
seam 이 없습니다 — 검색 품질과 접근 필터는 `skewnono_rag` 의 책임이며, chat 은
`agent_query` 가 돌려준 Evidence 의 **모양만** 검증합니다
(`answer/providers/rag.py`, `tests/test_answer_rag.py`).

### Prompt 4 — 전환과 smoke 검증

```text
skewnono chat 의 office 전환을 확인하라. 선택할 환경 변수는 없다 — 체크아웃이
제자리에 있으면 office, 없으면 mock 이다.

1. `_rag/skewnono_rag/` 에 패키지와 빌드된 인덱스를 둔다.
2. `.venv/bin/python index.py` 로 띄우고 부팅 로그의 `chat/answer` 행이 `office` 이며
   체크아웃 경로를 가리키는지 확인한다. `mock` 이면 진입 모듈이나 인덱스가
   빠진 것이다.
3. 승인된 비민감 질문 한 건을 실제로 보내 source type, provenance, 접근 거부를
   확인한다.
4. repo root 에서 전체 suite 를 다시 실행해 계약이 변하지 않았음을 확인한다:
   .venv/bin/python -m pytest tests back_dev_home -q
```

## 6. Adapter 밖에서 별도 배정이 필요한 항목

RAG 데이터·adapter와 무관하게 사내 담당 배정이 필요한 잔여 항목입니다. 상세 계약은
`back_dev_home/chat/MIGRATION.md`에 있습니다.

| 항목 | 상태 |
| --- | --- |
| Access resolver (groups/fabs 계산) | 미구현. 현재 AccessScope는 user_id만 채웁니다. Resolver 전에는 전 사용자 공개 source만 연결합니다. |
| LLM gateway | RAG 소유로 이관되었습니다(`skewnono_rag/config.py` 내장 키). chat 쪽에는 배정할 항목이 없습니다. |
| Thread storage office provider | Stub. Write 가능한 사내 저장소 결정이 필요합니다. |
| Retention job | `_scheduler/` 에 구현할 수 있으나 owner/주기/alerting 값이 미정입니다. |
