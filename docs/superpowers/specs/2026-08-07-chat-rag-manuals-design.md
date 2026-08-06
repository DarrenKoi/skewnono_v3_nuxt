# Chat RAG — 매뉴얼 검색 연결 설계

- 작성일: 2026-08-07
- 상태: 설계 확정, 구현 전
- 범위: `/chat`의 근거 검색 중 **매뉴얼(manual) 1종**을 사무실 OpenSearch에 연결합니다.

## 1. 배경

Chat의 RAG 골격은 이미 저장소에 있습니다. `knowledge/` provider seam, `Evidence`
계약, 네 개의 read-only retrieval tool, scope classifier, agent runtime, 그리고
mock provider가 모두 동작합니다. 남은 것은 사무실 adapter가 **무엇을 호출하는지**를
확정하는 일입니다.

이 문서는 그 확정을 기록합니다. **`Evidence` 12필드, 네 개 함수 시그니처,
`AccessScope` 생성 위치, 오류 계약은 변경하지 않습니다.** 계약 변경이 아니라
`_execute()`가 무엇을 치느냐의 결정입니다.

관련 문서는 `back_dev_home/chat/MIGRATION.md`(전환 순서·selector·상한),
`docs/datatables/chat_rag_contract.txt`(인덱스 스키마의 진실 원천),
`docs/research/llm-rag-chatbot-feasibility.md`(최초 타당성 조사)입니다.

## 2. 결정 요약

| 항목 | 결정 | 근거 |
| --- | --- | --- |
| 검색 대상 | 매뉴얼 1종만. 회의록·메일·리포트는 뒤로 미룹니다. | 메일·회의록은 수신자/참석자 단위 권한이라 authoritative access resolver가 선행되어야 합니다. 현재 `AccessScope`는 `groups`/`fabs`가 빈 list입니다. |
| 실계측 데이터 | RAG 범위 밖입니다. skewnono가 직접 관장합니다. | 장비 상태·recipe·alarm은 이미 skewnono 소유이며, RAG에 넣으면 신원 위임 문제가 따라옵니다. |
| 저장소 | 기존 사무실 OpenSearch에 색인합니다. 별도 RAG 서버를 두지 않습니다. | 검색 경로가 같은 클러스터 안에 있으므로 중간 홉이 불필요합니다. |
| 검색 | 2-leg hybrid — Nori BM25 ⊕ BGE-M3 dense. | Nori 확보(user-confirmed 2026-08-06). BGE-M3는 multilingual이라 한/영 동시 요건이 k-NN leg에서 충족됩니다. BGE-M3 sparse는 쓰지 않습니다. |
| 리랭킹 | `bge-reranker-v2-m3` 크로스인코더. 후보 20~30 → 상한 5행. | 리랭커가 m3 계열이라 한/영 혼용 질의에 일관됩니다. |
| 모델 호출 | **C2** — `office.py`가 사내 embedding/rerank API를 직접 호출합니다. | 아래 3절. |
| Tool 노출 | provider 준비 상태가 결정합니다. 준비되지 않은 소스는 tool 자체를 노출하지 않습니다. | 빈 list를 주면 모델이 "회의록에는 없었습니다"라는 거짓 진술을 만듭니다. |
| `element_type` | 인덱스 내부 전용. `Evidence`에 올리지 않습니다. | 어휘가 아직 교정 중입니다. 인덱스 내부면 재색인 한 번, `Evidence`면 5곳 동시 변경입니다. |

## 3. 모델 호출 위치 — C2를 택한 이유

BGE-M3와 `bge-reranker-v2-m3`는 사내 API로 제공됩니다(user-confirmed 2026-08-07).
따라서 인코딩 주체는 OpenSearch도 Flask도 아닌 제3의 엔드포인트이며, 갈리는 지점은
**누가 그 API를 호출하는가**입니다.

| | 호출 주체 | Flask 왕복 | 전제 조건 |
| --- | --- | --- | --- |
| C1 | OpenSearch가 ML Commons remote connector로 호출 | 1회 | cluster settings 변경 권한, 클러스터 egress, 클러스터에 credential 보관 |
| **C2** | `office.py`가 직접 호출 | 3회 | 없음 |

C2를 택합니다. 사무실 확인 결과 `plugins.ml_commons.trusted_connector_endpoints_regex`에
사내 host가 **없습니다**(office 확인 2026-08-07). C1으로 가려면 공용 클러스터의
cluster-wide 설정을 바꿔야 하고, 이는 권한 확보와 운영 협의를 요구합니다. 또한 해당
설정은 배열을 **병합이 아니라 치환**하므로, 기존 기본 패턴을 함께 넣지 않으면 다른
사용자의 connector를 조용히 끊습니다.

C2의 대가는 왕복 3회와 `_rerank()` seam 하나이며, 둘 다 감당 가능합니다. 이 결정은
되돌릴 수 있습니다 — 클러스터 쪽이 정리되면 `_execute()`와 `_rerank()` 두 함수만
바꾸어 C1으로 옮기며, 추적되는 계약은 변경되지 않습니다. C1 전환 조건은 부록 A에
남깁니다.

`chat/guard.py`는 blocklist 방식(공개 게이트웨이만 차단)이므로 사내 API 호출을
막지 않습니다. Guard 변경은 필요하지 않습니다.

## 4. 구조

```text
Nuxt /chat
 └ Flask /api/chat/*            신원·ACL·rate·scope·AccessScope 생성
    └ chat/tools/*              모델에 노출되는 인자: query 하나
       └ knowledge/data.py      provider 선택 + available_sources()
          ├ mock.py             집: 픽스처 토큰 교집합, 4종 전부 노출
          └ office.py           사무실 (gitignored)
               ├ 사내 embedding API   질문 → BGE-M3 dense vector
               ├ OpenSearch          Nori BM25 ⊕ dense k-NN → 후보 20~30
               └ 사내 rerank API      bge-reranker-v2-m3 → 점수
                  ↳ 정렬·절단·검증은 tracked 계약 절반이 담당
```

## 5. 인덱스 계약 — offline ingestion이 지켜야 할 것

Runtime은 인덱스를 만들지 않습니다. Offline ingestion이 만든 immutable/versioned
artifact를 read-only로 읽습니다.

아래 항목은 **색인 후 변경이 곧 전체 재색인**이며, 어겼을 때 예외를 던지지 않고
조용히 품질만 떨어뜨립니다. 그것이 이 목록을 계약으로 못박는 이유입니다.

| 항목 | 규칙 | 어겼을 때 |
| --- | --- | --- |
| analyzer | 한국어 text 필드에 Nori를 지정합니다. | 기본 `standard` analyzer가 한글을 한 글자씩 분해하여 lexical leg가 무력화됩니다. 오류는 없고 recall만 반토막 납니다. |
| embedding | BGE-M3 dense. Ingestion과 질의가 같은 사내 API·같은 버전을 씁니다. | 색인 벡터와 질의 벡터가 다른 모델이면 검색이 무의미해집니다. |
| 권한 필드 | group/fab 등 접근 제한을 **filterable 필드**로 색인합니다. 지금 사용하지 않아도 색인은 해 둡니다. | 나중에 access resolver를 붙일 때 전체 재색인이 필요해집니다. |
| `source_type` 구분 | 소스별 인덱스든 필터 필드든, **질의 단계에서** 소스를 제한할 수 있어야 합니다. | hit 안의 값은 신뢰하지 않는다는 계약을 지킬 수 없습니다. |
| `source_id` | 결정적으로 유도합니다(예: `sha1(doc_id + revision + chunk_index)`). Ingestion 실행 단위 UUID를 쓰지 않습니다. | 재색인할 때마다 저장된 인용이 전부 끊깁니다. |
| `figure_id` | `^[A-Za-z0-9_-]{1,128}$`. Bucket·prefix·경로 구분자·`.webp`를 포함하지 않는 맨 id만 내보냅니다. | 서버 검증에 걸려 오류가 아니라 렌더되지 않는 그림이 됩니다. 색인 쪽이 유일한 방어선입니다. |
| `locator` | `manual:<doc_id>#page=<page>` 형태의 논리 참조입니다. URL·파일 경로·저장소 키가 아닙니다. | 화면에 내부 경로가 노출됩니다. |
| `snippet` | 승인된 최소 근거 text이며 원문 전체가 아닙니다. | 계약 위반입니다. |
| `element_type` | 인덱스 내부 전용입니다. `Evidence`로 내보내지 않습니다. | 어휘 교정이 backend·frontend·mock·테스트·datatables 동시 변경이 됩니다. |

매뉴얼은 개정되지 않으므로(user-confirmed 2026-08-06) revision 우선순위, superseded
문서 제외, `occurred_at` 정규화, retention 규칙은 이번 범위에서 제외합니다. 다만
`source_id`의 결정적 유도는 유지합니다 — 문서가 불변이어도 chunking을 튜닝하면
재색인하게 됩니다.

### 5.1 `element_type` 어휘 (권고, 강제 아님)

현재 어휘는 `paragraph`, `procedure`, `warning`, `caution`, `alarm`, `parameter`,
`table`, `parts_list`, `troubleshooting`, `figure_caption`, `figure_description`
입니다. 라벨링이 망설여지는 원인은 어휘가 아니라 **하나의 열거형에 축이 네 개
눌려 있는 것**입니다 — 형태, 기능, 안전 등급, 도메인 개체. 경고가 포함된 절차
단계, 파라미터 표, 알람 대처 표처럼 동시에 참인 chunk에서 거짓 선택을 강요합니다.

축을 분리한 형태를 권고합니다.

| 필드 | 값 | 비고 |
| --- | --- | --- |
| `block_type` | `paragraph`, `table`, `list`, `figure` | 형태, 단일값 |
| `intent` | `procedure`, `troubleshooting`, `reference` | 기능, 다중 가능 |
| `safety_level` | 원문 머리말 그대로 | OFFICE-VERIFY — 아래 참조 |
| `is_generated` | bool | 우선순위 최상 |
| `alarm_codes` | `["9006", ...]` | 라벨이 아니라 추출 필드 |

`is_generated`를 최우선으로 두는 이유는 나머지와 성격이 다르기 때문입니다. 나머지는
틀려도 검색 품질이 나빠질 뿐이지만, 이것은 **기계가 생성한 문장을 사람이 쓴 근거로
인용하는 문제**이며 나중에 소급해 판별할 수 없습니다. `figure_description`이
생성물이라면 `figure_caption`과의 차이는 형태가 아니라 출처입니다.

`alarm`과 `parameter`를 element type에서 빼고 추출 필드로 옮기기를 권합니다.
"이 chunk는 alarm 유형이다"보다 **"이 chunk는 알람 9006을 다룬다"** 가 검색에
유용합니다 — hybrid search가 하지 못하는 정확 일치 필터가 됩니다. 확정된 ALID
집합은 `9006`(align), `9007`·`9035`(meas)이며 Hitachi 한정입니다.

`safety_level`은 **미정**입니다. 실제 매뉴얼이 ANSI Z535.6 계열 머리말
(DANGER / WARNING / CAUTION / NOTICE)을 쓰는지 확인되지 않았습니다. 쓴다면 원문
단어를 그대로 보존하고 재해석하지 않습니다. 쓰지 않는다면 `warning`/`caution`
구분은 임의가 되어 일관된 라벨링이 불가능하므로, 축 자체를 두지 않는 편이 낫습니다.
RAG 담당이 확정한 뒤 이 문서를 갱신합니다.

## 6. 검색 경로

한 번의 `search_manuals(query, filters, scope, limit)` 호출이 다음을 수행합니다.

1. 사내 embedding API에 질문 텍스트를 보내 BGE-M3 dense vector를 받습니다.
2. OpenSearch에 hybrid 질의를 보냅니다 — Nori BM25 leg와 dense k-NN leg를
   normalization으로 결합하고, **접근 필터를 질의 단계에 포함**합니다.
   후보는 20~30건을 뽑습니다.
3. 사내 rerank API에 (질문, 후보 텍스트) 쌍을 보내 점수를 받습니다.
4. 점수순으로 정렬하고 `limit`(최대 5)로 절단한 뒤 `Evidence`로 정규화합니다.

제약과 근거는 다음과 같습니다.

- 질의를 언어 판별로 분기하거나 번역해서 보내지 않습니다. 섞인 질문을 더 나쁜
  단일 언어 질문으로 바꾸는 일입니다. BGE-M3와 Nori가 한 요청에서 두 언어를
  동시에 만족시킵니다.
- 접근 필터는 질의 단계에 적용합니다. 검색 후 Python 필터링으로 보완하는 것은
  계약 위반이며, 권한 없는 source의 존재·title·count·score도 노출하지 않습니다.
- 크로스인코더는 후보 수에 선형으로 비쌉니다. 20~30으로 시작하고 사무실에서
  측정합니다. 50은 체감될 수 있습니다.
- 임베딩 단위와 표시 단위를 분리해도 됩니다. BGE-M3는 컨텍스트가 길어 큰 chunk를
  견디지만 `snippet`은 최소 근거여야 하므로, 크게 색인하고 표시는 매칭 구간만
  잘라내는 선택지를 chunk 튜닝 때 함께 평가합니다.

### 6.1 왕복 3회가 지연에 미치는 영향

C2는 tool 호출 1회당 왕복 3회입니다. Agent runtime이 재질의하면 한 턴에 6~9회가
됩니다. 그중 리랭크가 가장 비쌉니다. 따라서 사무실 smoke 단계에서 실측한 뒤
`SKEWNONO_CHAT_*` deadline 값이 여전히 타당한지 확인합니다. 확인 전까지 기존
값을 바꾸지 않습니다.

## 7. `office_example.py` — `_rerank()` seam 추가

C2에서는 "후보 초과 조회 → 리랭크 → `limit`로 절단"이 `office.py` 안에서 벌어집니다.
그런데 **상한은 애플리케이션이 정하며 모델이나 어댑터가 늘릴 수 없다**가 계약입니다.
그 불변식을 집에서 테스트할 수 없는 gitignored 파일이 지키게 두면 계약을 형식적으로만
지키는 상태가 됩니다.

따라서 순서와 절단을 tracked 계약 절반으로 올리고, gitignored copy에는 호출 seam만
남깁니다.

```text
knowledge/providers/office_example.py   (tracked, "do not edit below" 아래)
  _search()
    → _execute()                후보 N건 조회            [OFFICE-TODO]
    → _rerank(query, cands)     점수 산출                [OFFICE-TODO, 신규]
    → 점수순 정렬 후 limit 절단   계약 절반이 소유
    → _to_evidence()            엄격 검증

knowledge/providers/office.py           (gitignored copy)
  _config()    사내 API endpoint, 인덱스/alias, timeout
  _execute()   embedding API 호출 + OpenSearch hybrid 질의
  _rerank()    rerank API 호출, 점수만 반환
  _translate_error()  client 오류 → typed exception
```

`_rerank()`가 실패하거나 미구현이면 리랭크 없이 원 순위를 유지하지 않고
`KnowledgeUnavailable`을 올립니다 — 조용한 품질 저하보다 명시적 실패를 택합니다.

C1으로 전환하면 리랭크가 클러스터 안에서 끝나므로 `_rerank()`는 항등 함수가 되며,
계약 절반은 그대로 둡니다.

## 8. Tool 노출 — `available_sources()`

`knowledge/data.py`에 `available_sources()`를 추가하고, `runtime/providers/agent.py`의
`_build_tools()`가 그 목록으로만 tool closure를 만듭니다.

| provider | 반환 | 모델에 보이는 tool |
| --- | --- | --- |
| mock | 4종 전부 | 4개 — 홈 개발 경로는 그대로입니다. |
| office | `SKEWNONO_CHAT_KNOWLEDGE_SOURCES`(기본 `manual`) | 현재 1개 |

이 설계는 이 저장소의 presence-based selection 원칙을 소스 단위로 내린 것입니다.
나중에 메일을 붙일 때 `runtime/providers/agent.py`를 고치지 않고 환경 변수와 실제
인덱스만 늘어납니다. 준비되지 않은 소스에 빈 list를 돌려주지 않는 이유는, 그것이 모델에게
"해당 소스에 관련 내용이 없다"로 읽히기 때문입니다 — 색인이 없는 것과 진짜 없는
것이 구분되지 않습니다. 부수적으로 tool 왕복이 줄어 지연도 함께 줄어듭니다.

## 9. 오류 계약 (변경 없음)

`KnowledgeDenied` → 403, `KnowledgeTimeout` → 504, `KnowledgeUnavailable` → 503.
자동 fallback을 구현하지 않습니다 — mock으로도, 다른 소스로도 전환하지 않습니다.
실패 시 user turn만 유지하고 assistant·source·tool trace는 저장하지 않으며,
이미 저장된 user turn은 같은 `request_id` retry를 위해 남깁니다.

## 10. 홈(mock) 경로

`knowledge/providers/mock.py`는 유지합니다. 사무실 인덱스는 집에서 닿지 않으므로,
mock을 버리면 홈 세션의 chat이 통째로 죽습니다. Mock은 4종을 모두 노출하여 tool
조립 경로 자체를 홈에서 검증합니다.

Mock이 사무실과 의도적으로 다른 지점을 docstring에 명시합니다 — 토큰 교집합 검색이라
semantic 매칭이 없고, `score`가 float 거리가 아닌 작은 정수이며, `figure_id`는 뒤에
실제 객체가 없는 불투명 토큰입니다. 픽스처는 한국어와 영어를 의도적으로 섞어 둡니다.

## 11. 문서 정정

이 설계가 확정되면 아래를 함께 갱신합니다. 사무실 DB 사실은 datatables와 mock 양쪽에
남긴다는 규칙을 따릅니다.

| 파일 | 정정 내용 |
| --- | --- |
| `docs/datatables/chat_rag_contract.txt` | multilingual OFFICE-VERIFY → BGE-M3 user-confirmed. Nori 확정. 2-leg hybrid + `bge-reranker-v2-m3` 명시. `element_type` 인덱스 내부 전용 명시. 매뉴얼 우선 범위. C2 호출 경로. |
| `back_dev_home/chat/MIGRATION.md` | 4소스 동시 전제 → 소스별 준비 상태. Revision/superseded 항목 축소. `available_sources()`와 `_rerank()` seam 추가. C1/C2 분기. |
| `knowledge/providers/mock.py` docstring | 무엇을 대신하는지, 어디서 의도적으로 다른지. |

## 12. 검증 순서

1. 홈 계약 — `pytest back_dev_home/chat/tests/test_knowledge.py test_runtime.py test_scope.py -q`
   에 `available_sources()`와 tool 노출 테스트를 추가합니다.
2. Fake-client 계약 — `test_knowledge_office.py`의 `OFFICE-TODO` skip test를 채웁니다.
   질의 단계 접근 필터 증명, raw row 정규화, client 오류 mapping, 그리고 **리랭크 후
   순서 보존과 5행 절단**을 fake seam으로 검증합니다. Live service는 호출하지 않습니다.
3. 사무실 smoke — `TEST_STAGE=local`과 필수 환경변수가 있을 때만 실행하며, 승인된
   비민감 query 한 건으로 source type·provenance·접근 거부를 확인합니다. Thread
   storage는 mock으로 고정하여 RAG smoke와 분리합니다. 이 단계에서 왕복 3회 지연을
   실측합니다.
4. 저장소 gate — `pytest tests back_dev_home -q`, `ruff check back_dev_home/chat`,
   `npm run lint:md`, 그리고 frontend의 `npm test / typecheck / lint / build`.

실제 source content, query 결과, 내부 경로, credential은 assertion·fixture·로그·commit
어디에도 남기지 않습니다.

## 13. 범위 밖

- Figure serving endpoint (`GET /api/chat/figures/<figure_id>`) — 설계는 확정되어
  있고 구현은 보류입니다. `figure_id`는 계약과 인덱스에 먼저 흘려 두므로 스키마
  변경 없이 나중에 켤 수 있습니다.
- 회의록·메일·리포트 — authoritative access resolver와 상시 ingestion 파이프라인이
  선행 조건입니다.
- MCP / A2A 전송 — 지금 결정하지 않습니다. `search_emails()`는 이미 provider로
  디스패치되는 함수라 seam이 서비스 경계 모양이며, 전송 방식은 `_execute()` 내부
  사정입니다. 다만 **반환 계약은 어떤 전송을 택하든 `Evidence`로 유지합니다** —
  한 답변이 매뉴얼 근거와 메일 근거를 같이 인용하는데 한쪽이 산문으로 오면 인용
  UI가 소스마다 갈라지고 되돌리기 어려워집니다.
- 실계측 데이터의 RAG 편입.
- Evaluation export, dashboard, training dataset 생성.

## 14. 미확인 (OFFICE-VERIFY)

- `safety_level` — 매뉴얼이 표준 머리말을 쓰는지. RAG 담당이 확정 후 통보합니다.
- Chunk 크기·중첩 — 사무실에서 측정합니다.
- 사내 embedding API의 버전 노출 여부. 노출하지 않으면 사내에서 모델을 조용히
  갱신했을 때 색인과 질의가 어긋나도 알아낼 방법이 없습니다. 확인이 필요합니다.
- 왕복 3회 실측 지연과 현재 deadline 값의 정합성.

## 부록 A — C1 전환 조건

아래가 모두 충족되면 C1이 더 낫습니다. 왕복이 1회로 줄고, ingestion과 질의가 같은
`model_id`를 쓰므로 모델 드리프트가 구조적으로 불가능해집니다.

- `plugins.ml_commons.trusted_connector_endpoints_regex`에 사내 API host가
  등록되어 있습니다. 이 설정은 배열을 치환하므로 기존 값을 반드시 병합합니다.
  기본 패턴이 모두 `^https://`로 시작하므로 사내 API가 http면 패턴을 직접 씁니다.
- `cluster:admin/settings/update` 권한이 있거나 클러스터 운영 담당의 협조를
  받습니다.
- 사내 API credential을 클러스터에 보관하는 것이 사내 정책상 허용됩니다.

확인 명령입니다.

```text
GET  _cluster/settings?include_defaults=true
GET  _plugins/_ml/connectors/_search?q=*
POST _plugins/_ml/models/_search      {"query": {"match_all": {}}}
```

전환 시 변경 범위는 gitignored `office.py`의 `_execute()`와 `_rerank()` 두 함수이며,
추적되는 계약과 테스트는 그대로 유지됩니다.
