---
tags: [llm-wiki, prompts]
level: beginner
last_updated: 2026-05-01
status: complete
---

# LLM Wiki — 공통 프롬프트 모음

> 팀원이 어떤 LLM (Claude Code, Codex CLI, Cursor, ChatGPT 웹, Gemini, Claude.ai 등) 을 쓰든 동일하게 동작하도록 만든 프롬프트. 복사 → 변수 치환 → 사용.

---

## 사용 환경별 차이

| 환경 | 파일 직접 읽기/쓰기 | 사용법 |
| --- | --- | --- |
| Claude Code · Codex CLI · Cursor · Aider | ✅ 자동 | 프롬프트 그대로 붙여넣기 |
| ChatGPT · Gemini · Claude.ai (웹) | ❌ 불가 | 관련 파일을 첨부 또는 본문에 붙여넣기. 결과는 전문/diff 로 받아 수동 적용 |

**웹 챗 환경에서는** 모든 프롬프트 마지막 줄에 다음을 추가:

> 파일을 직접 수정할 수 없다면, 변경/생성할 각 파일의 **전체 내용** 을 파일 경로를 헤더로 한 별도 코드블록으로 출력해줘. diff 보다 전문이 적용에 안전하다.

## 변수 표기

- `<WIKI_ROOT>` — 위키 루트 경로 (대상 프로젝트의 `docs/llm-wiki/` 또는 `doc/llm-wiki/`). 한 프로젝트 안에서는 항상 동일.
- `<MY_NAME>` — **본인 이름 또는 사내 핸들** (예: `대영`, `daeyoung`, `DK`). 페이지를 새로 만들거나 수정할 때 frontmatter 의 `owner` 필드에 들어간다. 팀원마다 다르므로 매 프롬프트마다 본인 값으로 치환.
- `<...>` — 그 외 placeholder. 사용 시 실제 값으로 치환.

## 공통 헤더 (모든 프롬프트의 첫 두 줄)

```text
<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: <MY_NAME>
```

- 1 행이 빠지면 LLM 이 자체 컨벤션을 만들어 위키가 일관성을 잃는다.
- 2 행은 새로 만들거나 수정하는 페이지의 frontmatter `owner` 필드에 들어가는 값이다. 팀원이 누가 작업했는지 추적되도록 매번 본인 이름을 기입한다.

---

## 1. Bootstrap — 최초 1 회 (프로젝트 셋업 담당자만)

새 프로젝트에 starter 폴더를 복사한 직후 1 회 실행. 일반 팀원은 건너뛰고 §2 부터.

```text
<WIKI_ROOT>/ 의 LLM Wiki 부트스트랩을 마무리해줘.

작업:
1. <WIKI_ROOT>/WIKI_SCHEMA.md 와 <WIKI_ROOT>/wiki/{index.md, log.md, overview.md} 안의:
   - <프로젝트명> → <실제 프로젝트 이름>
   - YYYY-MM-DD → <오늘 날짜>
   를 일괄 치환.
2. raw/ 와 wiki/ 컴포넌트 폴더는 빈 상태 유지 (첫 ingest 전).
3. raw/, wiki/ 하위 README.md 는 폴더 설명용이므로 손대지 말 것.

작성자(owner) 정보는 부트스트랩 시점에 정하지 않는다.
각 페이지가 ingest/save 시점에 그 작업의 작성자(<MY_NAME>) 로 채워진다.

치환된 파일 목록을 마지막에 보고.
```

---

## 2. Ingest — raw 자료를 wiki 로 합성 (주력 작업)

가장 자주 쓰는 프롬프트. **한 번에 한 raw 파일만** 처리.

```text
<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: <MY_NAME>

Ingest 대상: <WIKI_ROOT>/raw/<폴더>/<파일>.md

작업 순서:
1. 대상 raw 파일을 읽고 핵심 정보 추출.
2. 영향받는 wiki/ 페이지 식별 — 기존 갱신 + 신규 생성.
   - 새 페이지는 <WIKI_ROOT>/_templates/ 의 해당 템플릿을 베이스로.
     (components/ → component.md, concepts/ → concept.md, decisions/ → decision.md,
      runbooks/ → runbook.md)
   - raw 폴더별 기본 ingest 대상:
     · raw/journals/, raw/learning-logs/  → wiki/concepts/ 또는 wiki/components/
     · raw/decisions/, raw/meetings/      → wiki/decisions/
     · raw/specs/                         → wiki/components/, wiki/overview.md
     · raw/incidents/                     → wiki/runbooks/, wiki/decisions/
     · raw/references/articles/           → wiki/concepts/
     · raw/references/courses/            → wiki/concepts/ 또는 wiki/runbooks/
     · raw/references/papers/             → wiki/concepts/ (강한 인용)
     · raw/references/books/              → wiki/concepts/
   - 파일명: SCHEMA §2 규칙 적용 (영어 기술 용어는 영문, 한글 도메인 용어는 한글 OK).
   - frontmatter 필수 (SCHEMA §2). owner 는 위 "작성자" 값(<MY_NAME>) 사용.
   - 기존 페이지를 수정하는 경우, 그 페이지의 owner 는 그대로 두되
     last_updated 만 오늘 날짜로 갱신.
3. 모든 비자명 주장에 raw 또는 코드 경로 인용 추가
   (형식: `raw/<...>` 또는 `src/<...>:<line>`).
4. 페이지 간 cross-link 는 상대경로로.
5. <WIKI_ROOT>/wiki/index.md 의 해당 섹션에 새 페이지 등록.
6. <WIKI_ROOT>/wiki/log.md 최상단에 ingest 항목 prepend:
   ## [<오늘 날짜>] ingest | raw/<폴더>/<파일>.md (by <MY_NAME>)
   - <변경 1>
   - <변경 2>
   - <발견된 open question 또는 conflict>
7. raw/ 는 절대 수정하지 말 것.
8. 검증 안 된 주장은 `> Unverified:` 인용 블록으로 표기.
9. 페이지 간 모순 발견 시 `> Conflict:` 블록 + 양쪽 source 인용.

마지막에 변경된 파일 목록과 open question 을 요약.
```

---

## 3. Code Ingest — 코드를 wiki 로 합성

기존 코드베이스를 위키화할 때. **`raw/` 거치지 않고 `src/` 를 직접 입력**으로 사용. 두 단계로 나뉨.

### 3-A. Codebase 매핑 (1 회 — 어떤 컴포넌트가 있는지 파악)

```text
<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: <MY_NAME>

src/ 전체를 훑어 주요 컴포넌트(모듈·서비스·패키지) 를 나열.
각 컴포넌트마다:
- 책임 한 줄
- 핵심 진입점 1~3 개 (src/<path>:<line>)
- 외부 의존성 (라이브러리·다른 컴포넌트)
- wiki/components/<제안 파일명>.md 후보

생성·수정은 하지 말고, 위 목록만 답변으로 출력.
이 결과를 보고 어느 컴포넌트부터 ingest 할지 결정한다.
```

### 3-B. 컴포넌트별 ingest (반복)

```text
<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: <MY_NAME>

코드 ingest 대상: <코드 경로> (예: src/auth/, src/api/v2/router.py)
출력 대상: <WIKI_ROOT>/wiki/components/<component-name>.md

작업:
1. 대상 코드를 읽고 책임·진입점·의존성·사용 패턴 추출.
2. wiki/components/<component-name>.md 생성 또는 갱신.
   - <WIKI_ROOT>/_templates/component.md 를 베이스로.
   - 모든 비자명 주장에 src/<path>:<line> 인용.
   - 외부 라이브러리는 package.json / pyproject.toml / requirements.txt 의 버전 명시.
   - frontmatter sources 에 코드 경로 나열.
   - frontmatter owner: <MY_NAME>.
3. 페이지 간 cross-link 는 상대경로.
4. <WIKI_ROOT>/wiki/index.md 의 Components 섹션 갱신.
5. <WIKI_ROOT>/wiki/log.md 최상단에 prepend:
   ## [<오늘 날짜>] ingest | <코드 경로> (by <MY_NAME>)
6. raw/ 와 src/ 모두 수정 금지.
7. 검증 안 된 추론은 > Unverified: 인용 블록.

마지막에 변경 파일 목록과 open question 요약.
```

### 3-C. Runbooks 합성 (선택 — setup/deploy 절차)

코드와 함께 운영 절차도 위키화:

```text
<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: <MY_NAME>

코드 ingest 대상: README.md, package.json (또는 pyproject.toml), Dockerfile, .github/workflows/
출력 대상: <WIKI_ROOT>/wiki/runbooks/{setup, deploy}.md

<WIKI_ROOT>/_templates/runbook.md 를 베이스로.
각 단계: 실제 명령어 + 기대 출력 + 실패 시 대응 포함.

§3-B 와 동일한 인용·log·frontmatter 규칙 적용.
```

### 코드 ingest 만의 주의점

- **한 디렉토리 = 한 컴포넌트 페이지** 원칙. 너무 큰 디렉토리는 분할 (예: `src/api/` → `api-router.md` + `api-middleware.md`).
- 테스트 코드는 input 으로만 사용. 별도 wiki 페이지 X. 컴포넌트 페이지의 "사용 예시" 섹션 인용으로만.
- 자동 생성 파일 (lock files, build artifacts) 은 ingest 금지.
- 컴포넌트 코드 큰 변경 시 해당 위키 페이지 재-ingest. lint 가 `last_updated` vs source 변경 비교로 stale 감지.

---

## 4. Query — 위키에서 먼저 답하기

질문할 때 사용. 위키가 우선, 부족하면 raw/ 보강.

```text
<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: <MY_NAME>

질문: <질문 내용>

답변 절차:
1. <WIKI_ROOT>/wiki/ 에서 먼저 답을 찾고, 참조한 페이지 경로를 인용.
2. 위키에 없거나 stale 의심이면 <WIKI_ROOT>/raw/ 또는 코드(src/) 를 보강.
3. 답변 본문 끝에 다음 메타정보 명시:
   - 답변 출처: wiki / raw / 코드 / 추측 중 어느 것인지
   - 인용된 파일 경로 목록
4. 답이 wiki/ 에 새 페이지로 저장할 가치가 있다고 판단되면, 답변 마지막에:
   - 제안 경로 (예: wiki/concepts/<name>.md)
   - 어떤 템플릿을 베이스로 (_templates/ 중)
   - 1~2 문장 근거
   를 제시. **실제 파일 생성은 사용자 승인 후에만.**
```

---

## 5. Save Answer — Q&A 를 wiki 페이지로 저장

§4 답변 후 "그래, 저장해줘" 라고 할 때 사용.

```text
<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: <MY_NAME>

방금 답변을 <WIKI_ROOT>/wiki/<제안된 경로> 로 저장:

1. <WIKI_ROOT>/_templates/<해당 템플릿>.md 를 베이스로 새 페이지 생성.
2. 답변 내용을 Why → What → How → References 구조로 재구성.
3. frontmatter 채움:
   - owner 는 위 "작성자" 값(<MY_NAME>).
   - tags, level, last_updated, status, sources 는 답변 내용에 맞게.
4. 인용된 raw/, src/ 경로를 References 섹션에 명시.
5. <WIKI_ROOT>/wiki/index.md 의 해당 섹션에 link 추가.
6. <WIKI_ROOT>/wiki/log.md 최상단에 query-saved 항목 prepend:
   ## [<오늘 날짜>] query-saved | <새 페이지 경로> (by <MY_NAME>)
```

---

## 6. Lint — 월 1 회 위생 점검

```text
<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: <MY_NAME>

<WIKI_ROOT>/wiki/ 전체에 lint 패스 실행.

점검 항목 (SCHEMA §6):
- Stale: last_updated 가 90 일 이상이고 source 가 그 이후 변경됨
- Contradiction: 두 페이지가 같은 사실을 다르게 기술
- Missing citation: 비자명 주장에 raw/ 또는 src/ 인용 누락
- Broken link: 깨진 cross-link
- Orphan: index.md 와 다른 페이지 어디에서도 link 되지 않은 페이지
- Canonical gap: raw/ 에 자주 나오지만 canonical wiki 페이지가 없는 개념

산출:
- <WIKI_ROOT>/wiki/log.md 최상단에 lint 항목 prepend:
  ## [<오늘 날짜>] lint | wiki-wide (by <MY_NAME>)
- 각 발견 사항을 카테고리별 bullet 으로 나열, 영향받는 페이지 경로 포함.
- **자동 수정 금지.** 사람이 PR 에서 결정.
- 발견 0 건이면 "all clean" 으로 명시 (lint 가 부실한 게 아니라면 OK 신호).
```

---

## 7. PR Description — 위키 변경 PR 본문 생성

ingest/lint 결과를 PR 로 올릴 때 사용.

```text
방금 작업한 위키 변경사항으로 PR description 을 작성해줘.

형식:
- 제목: [wiki] <action>: <한 줄 요약>
  (action: ingest | query-saved | lint | manual-edit)
- 본문:
  ## Summary
  - 어떤 raw 파일을 ingest 했는지 (또는 어떤 lint 였는지)
  - 생성/수정된 wiki 페이지 목록 (경로)

  ## Citations
  - 새로 추가된 인용 경로 목록

  ## Open questions
  - 발견된 미해결 사항 (없으면 "없음")

  ## Reviewer checklist
  - [ ] raw/ 가 수정되지 않았는가
  - [ ] 비밀·자격증명·PII 가 포함되지 않았는가
  - [ ] 모든 비자명 주장에 인용이 있는가
  - [ ] index.md 에 새 페이지 link 가 추가되었는가
  - [ ] log.md 에 항목이 prepend 되었는가
```

---

## 일반 원칙

- **한 번에 한 raw 파일만 ingest.** 여러 개 묶으면 LLM 이 합성을 뭉갠다.
- **LLM 이 raw/ 를 수정하려 하면 거부.** SCHEMA §1 위반.
- **결과는 항상 PR 로.** main 직접 push 금지.
- **한 페이지 = 한 주제.** catch-all 문서 지양.
- **불확실하면 `> Unverified:` 표기.** 잘못된 확신보다 명시적 의문이 낫다.

## 트러블슈팅

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| LLM 이 SCHEMA 무시하고 자기 컨벤션으로 씀 | 공통 헤더 누락 | 첫 줄에 `<WIKI_ROOT>/WIKI_SCHEMA.md 를 운영 규칙으로...` 추가 |
| 페이지가 매번 다른 frontmatter 형식 | 템플릿을 안 읽음 | 프롬프트에 `_templates/<해당>.md 를 베이스로` 명시 |
| index.md, log.md 갱신을 빼먹음 | 작업 단계 불명확 | Ingest 프롬프트의 §5, §6 처럼 번호로 명시 |
| 웹 챗에서 파일 못 읽는다고 함 | 환경 차이 | 관련 파일을 본문에 붙여넣고, 끝에 "전체 내용 코드블록 출력" fallback 추가 |
| 한 ingest 가 너무 많은 페이지를 건드림 | raw 파일이 너무 큼 | raw 파일을 주제별로 분할 후 각각 ingest |

## 예시 사용 시나리오

각 프롬프트의 채워진 실제 사용 예시는 [`prompts_example/`](./prompts_example/) 폴더 참조 — 한 시나리오 = 한 파일이라 빠르게 복사·수정 후 바로 사용 가능.

| 파일 | 시나리오 | 해당 §|
| --- | --- | --- |
| [`01-bootstrap.md`](./prompts_example/01-bootstrap.md) | 프로젝트 셋업 1 회 | §1 |
| [`02-ingest-raw.md`](./prompts_example/02-ingest-raw.md) | raw 자료 합성 (학습 메모, 외부 자료) | §2 |
| [`03-code-ingest.md`](./prompts_example/03-code-ingest.md) | 코드베이스 위키화 (매핑 → 컴포넌트 → runbooks) | §3 |
| [`04-query.md`](./prompts_example/04-query.md) | 위키에서 답 찾기 + 예상 답변 형식 | §4 |
| [`05-lint.md`](./prompts_example/05-lint.md) | 월 1 회 위생 점검 + 예상 log.md 출력 | §6 |

## 참고 자료 (References)

- [WIKI_SCHEMA.md](./WIKI_SCHEMA.md) — 운영 규칙 (LLM 이 매번 읽음)
- [USAGE.md](./USAGE.md) — 폴더 복사·부트스트랩 가이드
- [README.md](./README.md) — LLM Wiki 패턴 일반론
- [_templates/](./_templates/) — 페이지 템플릿
- [`prompts_example/`](./prompts_example/) — 채워진 실제 프롬프트 예시
