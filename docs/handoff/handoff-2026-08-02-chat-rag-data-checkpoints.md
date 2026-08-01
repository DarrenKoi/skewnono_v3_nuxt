# Chat RAG 데이터 준비 체크포인트와 사내 LLM 프롬프트

작성일: 2026-08-02. 이 문서는 사내 RAG side project(별도 저장소)에서 로컬 LLM으로
RAG 데이터를 생성할 때 사용할 체크포인트와 복사-붙여넣기용 프롬프트를 제공합니다.
Skewnono 저장소 쪽 계약의 원본은 `back_dev_home/chat/MIGRATION.md`이며, 이 문서는
그 계약을 "데이터를 만드는 쪽" 관점으로 재정리한 것입니다.

## 1. Feasibility 결론

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

## 2. RAG 데이터가 최종적으로 도달해야 하는 계약

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

## 3. RAG 데이터 생성 체크포인트

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

## 4. 사내 로컬 LLM용 프롬프트

아래 프롬프트는 그대로 복사해 사내 coding LLM에 입력하는 용도입니다. `< >` 부분만
사내 값으로 치환합니다. 공통 전제: 사내 LLM은 public skewnono 저장소를 읽을 수
있고, 실제 hostname/credential은 프롬프트에 넣지 않습니다.

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

### Prompt 2 — `knowledge/providers/office.py` 구현

```text
skewnono 저장소의 back_dev_home/chat/MIGRATION.md 중 "Office knowledge provider
구현 계약" 절을 읽고, back_dev_home/chat/knowledge/providers/office_example.py 를
office.py 로 복사한 gitignored 파일에 다음을 구현하라.

1. search_manuals / search_meeting_summaries / search_emails / search_reports 네
   함수의 공개 signature를 그대로 유지한다: (query, filters, scope: AccessScope,
   limit) -> list[Evidence].
2. 검색 대상은 <사내 index/collection 설명>이며, access filter(scope의
   user_id/groups/fabs)는 검색 query 단계에 적용한다. 검색 후 Python filtering으로
   권한을 보완하지 않는다.
3. 반환 행은 contracts.py의 Evidence 필드를 전부 채운다. 없으면 None. snippet은
   승인된 최소 근거만 넣는다.
4. 오류 변환: 접근 거부 -> KnowledgeDenied, timeout -> KnowledgeTimeout, 설정
   누락·index 불일치·source unavailable -> KnowledgeUnavailable. 어떤 실패도
   mock/다른 source로 대체하지 않고, empty result는 빈 list로 반환한다.
5. host/credential/index 이름은 환경설정에서만 읽는다. model argument나 user
   입력에서 받지 않는다. 설정 self-load는 back_dev_home/_runtime 의 기존 패턴을
   따른다.
6. limit은 호출자가 준 값을 초과하지 않는다(응용단 상한 5).

구현 후, live service를 호출하지 않는
back_dev_home/chat/tests/test_knowledge_office.py 를 함께 작성하라(다음 프롬프트
참조).
```

### Prompt 3 — fake-client contract test 작성

```text
back_dev_home/chat/tests/test_knowledge_office.py 를 작성하라. Live 사내 service를
호출하지 않고 fake client/raw result를 주입해 office.py를 검증한다. 네 search 함수
각각에 대해 최소 다음을 검증한다.

1. raw result -> Evidence 변환: 모든 필드 정확성, None 처리, 1-based page.
2. access filter가 검색 query 단계에 반영되는지(fake client에 전달된 query/filter를
   검사한다).
3. limit 준수와 stable ordering.
4. empty result가 빈 list인지(대체 검색 없음).
5. 접근 거부/timeout/설정 누락이 각각 KnowledgeDenied/KnowledgeTimeout/
   KnowledgeUnavailable로 변환되는지.
6. 실제 source 내용·사내 경로·credential이 assertion과 fixture에 없는지.

실행:
.venv/bin/python -m pytest back_dev_home/chat/tests/test_knowledge_office.py -q
```

### Prompt 4 — 단계별 전환과 smoke 검증

```text
skewnono chat의 office 전환을 다음 사다리 순서로 진행하고 각 단계 결과를 기록하라.
자동 fallback은 없다. 문제가 생기면 환경변수를 명시적으로 되돌린다.

1. direct/mock/mock: SKEWNONO_CHAT_RUNTIME=direct 로 기존 대화 경로 확인.
2. agent/mock/mock: synthetic RAG로 tool 호출·citation 경로 확인.
3. agent/office/mock: SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office 로 실제 index 연결.
   TEST_STAGE=local SKEWNONO_CHAT_PROVIDER=mock SKEWNONO_CHAT_RUNTIME=agent \
   SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office SKEWNONO_CHAT_SCOPE_PROVIDER=office \
   .venv/bin/python -m pytest tests/test_chat_rag_local.py -q
   (승인된 비민감 query 한 건으로 source type/provenance/access denial 확인)
4. agent/office/office: scope classifier까지 전환.

Thread storage(SKEWNONO_CHAT_PROVIDER)는 RAG와 독립적으로 검증한다. 완료 후 repo
root에서 전체 suite를 다시 실행해 계약이 변하지 않았음을 확인한다:
.venv/bin/python -m pytest tests back_dev_home -q
```

## 5. Adapter 밖에서 별도 배정이 필요한 항목

RAG 데이터·adapter와 무관하게 사내 담당 배정이 필요한 잔여 항목입니다. 상세 계약은
`back_dev_home/chat/MIGRATION.md`에 있습니다.

| 항목 | 상태 |
| --- | --- |
| Access resolver (groups/fabs 계산) | 미구현. 현재 AccessScope는 user_id만 채웁니다. Resolver 전에는 전 사용자 공개 source만 연결합니다. |
| LLM gateway | 사내 tool-capable model endpoint와 `CHAT_MODELS` capability flag 배정이 필요합니다. |
| Thread storage office provider | Stub. Write 가능한 사내 저장소 결정이 필요합니다. |
| Retention job | `_scheduler/` 에 구현할 수 있으나 owner/주기/alerting 값이 미정입니다. |
