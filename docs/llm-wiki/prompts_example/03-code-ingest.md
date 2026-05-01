# 03. Code Ingest — 코드를 wiki 로 합성

> 기존 코드베이스를 위키화. raw/ 거치지 않고 src/ 를 직접 입력. **agentic LLM (Claude Code, Codex CLI) 에서만 가능** — 웹 챗은 파일 직접 읽기 불가.

## 전체 흐름

```
3-A. 매핑 (1 회)        →  컴포넌트 후보 목록 받기
  ↓
3-B. 컴포넌트별 ingest  →  wiki/components/<name>.md 한 개씩 (반복)
  ↓
3-C. Runbooks (선택)    →  setup, deploy 절차 합성
```

10 컴포넌트 codebase 기준 첫 회 약 1 시간 + PR 리뷰.

---

## 3-A. Codebase 매핑

### 상황

방금 클론한 repo. 어떤 컴포넌트들이 있는지 LLM 에 한 번 훑어보게 한다.

### 실제 프롬프트

```text
docs/llm-wiki/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: 대영

src/ 전체를 훑어 주요 컴포넌트(모듈·서비스·패키지) 를 나열.
각 컴포넌트마다:
- 책임 한 줄
- 핵심 진입점 1~3 개 (src/<path>:<line>)
- 외부 의존성 (라이브러리·다른 컴포넌트)
- wiki/components/<제안 파일명>.md 후보

생성·수정은 하지 말고, 위 목록만 답변으로 출력.
이 결과를 보고 어느 컴포넌트부터 ingest 할지 결정한다.
```

### 예상 출력 (예시)

```markdown
주요 컴포넌트 8 개:

1. **auth-service**
   - 책임: JWT 발급·검증, 세션 관리
   - 진입점: src/auth/router.py:12, src/auth/service.py:45
   - 의존성: PyJWT@2.8, redis-py@5.0
   - 제안: wiki/components/auth-service.md

2. **rag-pipeline**
   - 책임: 질의 임베딩 → vector DB 검색 → LLM 응답 합성
   - 진입점: src/rag/pipeline.py:1, src/rag/retriever.py:30
   - 의존성: langchain@0.3, milvus-client@2.4, auth-service
   - 제안: wiki/components/rag-pipeline.md

... (이하 6 개)
```

→ 이 목록을 보고 우선순위 정해서 3-B 로 한 번에 하나씩 ingest.

---

## 3-B. 컴포넌트별 ingest (반복)

### 상황

위 목록에서 `auth-service` 를 첫 ingest 대상으로 선택.

### 치환값

| 변수 | 값 |
| --- | --- |
| 코드 경로 | `src/auth/` |
| 출력 페이지 | `wiki/components/auth-service.md` |

### 실제 프롬프트

```text
docs/llm-wiki/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: 대영

코드 ingest 대상: src/auth/
출력 대상: docs/llm-wiki/wiki/components/auth-service.md

작업:
1. 대상 코드를 읽고 책임·진입점·의존성·사용 패턴 추출.
2. wiki/components/auth-service.md 생성 또는 갱신.
   - docs/llm-wiki/_templates/component.md 를 베이스로.
   - 모든 비자명 주장에 src/<path>:<line> 인용.
   - 외부 라이브러리는 pyproject.toml 의 버전 명시.
   - frontmatter sources: [src/auth/, src/api/v2/auth.py] 처럼 코드 경로 나열.
   - frontmatter owner: 대영.
3. 페이지 간 cross-link 는 상대경로.
4. docs/llm-wiki/wiki/index.md 의 Components 섹션 갱신.
5. docs/llm-wiki/wiki/log.md 최상단에 prepend:
   ## [2026-05-01] ingest | src/auth/ (by 대영)
   - 생성: wiki/components/auth-service.md
   - <발견된 open question>
6. raw/ 와 src/ 모두 수정 금지.
7. 검증 안 된 추론은 > Unverified: 인용 블록.

마지막에 변경 파일 목록과 open question 요약.
```

### 예상 출력

- 신규: `wiki/components/auth-service.md` (책임/진입점/의존성/호출 예시 포함, 모든 주장에 `src/auth/...py:<line>` 인용).
- 갱신: `wiki/index.md` Components 섹션, `wiki/log.md` 최상단.
- Open question 예: "리프레시 토큰 만료 시 자동 재발급 로직이 router 에 없다 — 의도된 것인가?"

---

## 3-C. Runbooks 합성 (선택)

### 상황

코드 ingest 가 어느 정도 끝난 다음, README·Dockerfile 등에서 운영 절차를 합성.

### 실제 프롬프트

```text
docs/llm-wiki/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: 대영

코드 ingest 대상: README.md, pyproject.toml, Dockerfile, .github/workflows/ci.yml
출력 대상: docs/llm-wiki/wiki/runbooks/{setup, deploy}.md

docs/llm-wiki/_templates/runbook.md 를 베이스로.
각 단계: 실제 명령어 + 기대 출력 + 실패 시 대응 포함.

§3-B 와 동일한 인용·log·frontmatter 규칙 적용.
```

### 예상 출력

- 신규: `wiki/runbooks/setup.md` (로컬 개발 환경 띄우기), `wiki/runbooks/deploy.md` (CI/CD 흐름).
- 검증 가능한 명령어 (`uv sync`, `docker build`, `gh workflow run`) 포함.

---

## 코드 ingest 의 함정

| 함정 | 대응 |
| --- | --- |
| 한 번에 너무 큰 디렉토리 ingest → 페이지가 catch-all 됨 | 디렉토리 분할 후 각각 ingest |
| 테스트 코드를 별도 페이지로 만듦 | 테스트는 컴포넌트 페이지의 "사용 예시" 섹션에서만 인용 |
| lock file·build artifact ingest | 항상 제외 |
| 코드가 자주 바뀌어 위키가 stale | lint 가 last_updated vs source 변경 비교로 감지 → 재-ingest |

## 다음 단계

- [`04-query.md`](./04-query.md) — 만든 컴포넌트 페이지에 질문 던져보기
- [`05-lint.md`](./05-lint.md) — 첫 lint 로 누락·인용 오류 점검
