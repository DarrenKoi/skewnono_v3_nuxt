# 02. Ingest Raw — raw 자료를 wiki 로 합성

> raw/ 에 파일을 추가한 후 wiki 페이지로 합성하는 가장 흔한 작업. 한 번에 한 raw 파일만.

## 케이스 A: 학습 메모 (가장 흔함)

### 상황

LangGraph 의 state 관리를 처음 만져보고 막힌 지점을 5 줄 메모로 작성:

```bash
cat > docs/llm-wiki/raw/learning-logs/20260501-langgraph-state.md <<EOF
# LangGraph state 관리

- StateGraph 의 state 는 TypedDict 또는 Pydantic 모델
- 노드가 dict 를 반환하면 state 에 merge 됨 (replace 아님)
- list 필드는 add_messages reducer 로 append 가능
- channel 별로 다른 reducer 지정 가능
- 막힌 지점: dict-of-dict 인 경우 deep merge 가 안 됨, 직접 reducer 작성 필요
EOF
```

### 치환값

| 변수 | 값 |
| --- | --- |
| `<폴더>` | `learning-logs` |
| `<파일>` | `20260501-langgraph-state.md` |

### 실제 프롬프트

```text
docs/llm-wiki/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: 대영

Ingest 대상: docs/llm-wiki/raw/learning-logs/20260501-langgraph-state.md

작업 순서:
1. 대상 raw 파일을 읽고 핵심 정보 추출.
2. 영향받는 wiki/ 페이지 식별 — 신규 wiki/concepts/langgraph-state-management.md 예상.
   - _templates/concept.md 를 베이스로.
   - frontmatter 의 owner: 대영, last_updated: 2026-05-01.
3. 모든 비자명 주장에 raw 또는 코드 경로 인용.
4. 페이지 간 cross-link 는 상대경로로.
5. wiki/index.md 의 Concepts 섹션에 새 페이지 등록.
6. wiki/log.md 최상단에 ingest 항목 prepend:
   ## [2026-05-01] ingest | raw/learning-logs/20260501-langgraph-state.md (by 대영)
   - <변경 내역>
7. raw/ 는 절대 수정하지 말 것.
8. 검증 안 된 주장은 > Unverified: 블록.

마지막에 변경 파일 목록과 open question 요약.
```

### 예상 출력

- 신규: `wiki/concepts/langgraph-state-management.md` (Why → What → How → References 구조)
- 갱신: `wiki/index.md` (Concepts 섹션에 link 추가), `wiki/log.md` (ingest 항목 prepend)
- Open question 후보: "dict-of-dict deep merge reducer 의 표준 구현 패턴이 있는가?"

---

## 케이스 B: 외부 자료 (블로그·강의·논문)

### 상황

Karpathy 의 LLM Wiki gist 를 읽고 요약을 외부 자료 폴더에 저장:

```bash
# raw/references/articles/20260501-karpathy-llm-wiki.md 작성
# (raw/references/README.md 의 본문 형식 권장 사항 참조)
```

### 차이점

**프롬프트 본문은 케이스 A 와 100% 동일**, "Ingest 대상" 한 줄만 변경:

```text
Ingest 대상: docs/llm-wiki/raw/references/articles/20260501-karpathy-llm-wiki.md
```

### 예상 출력

- 신규 `wiki/concepts/llm-wiki-pattern.md` 생성 (`_templates/concept.md` 베이스).
- 기존 `wiki/concepts/rag-vs-wiki.md` 가 있으면 보강.
- References 섹션에 `raw/references/articles/20260501-karpathy-llm-wiki.md` + 원문 URL 인용.

---

## 케이스 C: 의사결정 (ADR)

### 상황

PostgreSQL vs SQLite 선택 ADR 초안을 `raw/decisions/20260501-db-choice.md` 에 작성.

### 차이점

"Ingest 대상" 한 줄만:

```text
Ingest 대상: docs/llm-wiki/raw/decisions/20260501-db-choice.md
```

### 예상 출력

- 신규 `wiki/decisions/20260501-db-choice.md` (`_templates/decision.md` 베이스).
- 영향받는 컴포넌트 페이지 (`wiki/components/<db-layer>.md` 등) 가 있으면 References 섹션 갱신.

---

## 케이스 D: 한국어 도메인 페이지 (한글 파일명)

### 상황

사내 "재고 관리 규칙" 정리 메모를 `raw/specs/재고-관리-규칙.md` 에 작성. 영어 원어가 없는 도메인 용어 → SCHEMA §2 의 hybrid 정책에 따라 한글 파일명 OK.

### 차이점

"Ingest 대상" 한 줄만:

```text
Ingest 대상: docs/llm-wiki/raw/specs/재고-관리-규칙.md
```

### 예상 출력

- 신규 `wiki/concepts/재고-관리-규칙.md` 또는 `wiki/components/재고-관리-시스템.md` (내용에 따라).
- frontmatter `owner: 대영`, `tags: [재고, 도메인-규칙]` 같이 한글 태그도 OK.
- cross-link 도 한글 경로: `[재고 관리 규칙](../concepts/재고-관리-규칙.md)`.

> 영어 기술 용어가 섞이면 영문이 default — 예: `재고-관리-api.md` (X), `inventory-management-api.md` (O). 경계 모호하면 영문으로.

---

## 패턴 요약

raw 폴더가 달라도 **프롬프트 본문은 동일**, "Ingest 대상" 한 줄만 변경. 폴더 → wiki 출력 매핑은 PROMPTS.md §2 의 표, 파일명 한글/영문 선택은 WIKI_SCHEMA.md §2 참조.

## 다음 단계

- [`04-query.md`](./04-query.md) — 방금 만든 페이지에 질문
- [`03-code-ingest.md`](./03-code-ingest.md) — 코드도 위키화
- [`../WIKI_SCHEMA.md`](../WIKI_SCHEMA.md) §2 — 파일명 hybrid 정책 (영문/한글 선택 기준)
