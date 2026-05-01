# 04. Query — 위키에서 자연어로 답 찾기

> 위키가 어느 정도 채워진 후, 폴더 뒤지지 말고 LLM 에 자연어로 질문.

## 상황

"우리 RAG 파이프라인에서 임베딩 모델은 뭐 쓰지?" 가 궁금. 위키에 답이 있는지 확인 + 없으면 코드에서 찾고 싶음.

## 실제 프롬프트

```text
docs/llm-wiki/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: 대영

질문: 우리 RAG 파이프라인에서 임베딩 모델은 뭐 쓰지?

답변 절차:
1. docs/llm-wiki/wiki/ 에서 먼저 답을 찾고, 참조 페이지 경로 인용.
2. 위키에 없거나 stale 의심이면 raw/ 또는 코드(src/) 보강.
3. 답변 끝에:
   - 답변 출처 (wiki/raw/코드/추측 중)
   - 인용 파일 경로 목록
4. 답이 wiki/ 에 새 페이지로 저장 가치 있으면 제안 경로 + 템플릿 + 근거 제시.
   파일 생성은 사용자 승인 후에만.
```

## 예상 답변 (위키에 있을 때)

```markdown
BGE-M3 (multilingual) 사용 중. 장점은 한국어/영어 모두 강함, 8K 토큰 컨텍스트 지원, sparse + dense + multi-vector 동시 출력.

검색 단계 구성:
1. 질의 임베딩 (BGE-M3)
2. Milvus hybrid search (dense + sparse)
3. RRF rerank
4. top-5 chunk → LLM context

---
**답변 출처**: wiki
**인용**:
- wiki/components/rag-pipeline.md:42 — 임베딩 모델 명시
- wiki/decisions/20260315-embedding-choice.md — BGE-M3 선택 ADR
```

## 예상 답변 (위키에 없고 코드에서 찾았을 때)

```markdown
BGE-M3 사용 중 (코드에서 확인).

src/rag/embedding.py:8 에서 `from FlagEmbedding import BGEM3FlagModel` 임포트하고 line 23 에서 인스턴스화.
설정 파일 config/rag.yaml:5 에 `embedding_model: bge-m3` 명시.

---
**답변 출처**: 코드
**인용**:
- src/rag/embedding.py:8, src/rag/embedding.py:23
- config/rag.yaml:5

⚠️ wiki/components/rag-pipeline.md 에 임베딩 모델 정보 누락.

**저장 제안**:
- 경로: wiki/components/rag-pipeline.md (기존 페이지 보강)
- 템플릿: _templates/component.md (이미 있는 페이지 갱신)
- 근거: 임베딩 선택은 RAG 파이프라인의 핵심 결정. 누락된 채로 두면 다음 사람이 같은 질문을 반복.

저장하라고 하면 PROMPTS.md §5 (Save Answer) 프롬프트로 진행.
```

## 답변 출처별 행동

| 답변 출처 | 의미 | 다음 행동 |
| --- | --- | --- |
| **wiki** | 위키가 잘 채워져 있다 | 그냥 사용 |
| **raw** | 위키 합성이 누락됐다 | ingest 부족 → §2 또는 §3 으로 보강 검토 |
| **코드** | 위키에 정보 없음 | 코드 ingest 또는 Save Answer 로 페이지 생성 |
| **추측** | 정보 없음, LLM 추론 | 위키 저장하지 말 것. 사람이 직접 검증 후 raw/ 에 메모 → ingest |

## 다음 단계

- 답이 만족스러우면 그대로 사용
- "코드" 또는 "추측" 출처면 → PROMPTS.md §5 (Save Answer) 또는 §3 (Code Ingest) 로 위키 보강
- 위키가 답을 못 주는 경우가 잦으면 → [`05-lint.md`](./05-lint.md) 로 canonical gap 점검
