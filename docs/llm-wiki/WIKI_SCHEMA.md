# WIKI_SCHEMA — <프로젝트명> LLM Wiki 운영 규칙

> 이 파일은 LLM 이 ingest/query/lint 를 수행할 때 매번 읽는 운영 규칙이다.
> 변경은 팀 합의 + PR 리뷰로만.

Last updated: YYYY-MM-DD
Maintainers: 팀 전체 (각 페이지의 작성자는 frontmatter 의 `owner` 필드 참조)

---

## 1. 불변 규칙

- `raw/` 하위 파일은 **절대 수정 금지**. 새 정보가 생기면 새 파일 추가.
- 모든 비자명 주장은 raw 경로(`raw/...`) 또는 코드 경로(`src/...:line`) 인용.
- 비밀·자격증명·고객 PII·내부 장비 데이터 ingest 금지.
- 미팅 raw transcript ingest 금지. 사람이 요약한 후 `raw/meetings/` 에 저장.
- **외부 콘텐츠 전문 복사 금지**. `raw/references/` 에 들어가는 자료는 요약·발췌·본인 메모만. 출처 URL·저자·발행일 명시.

## 2. 페이지 작성 규칙

- **언어**: 한국어, 기술용어는 영어 병기 (예: "임베딩(Embedding)").
- **구조**: 모든 합성 페이지는 `Why → What → How → References` 4 섹션을 포함.
- **파일명**: 소문자, 하이픈(`-`) 구분, 검색 가능한 이름. 예: `embedding-basics.md`.
  - **영어 원어가 있는 기술 용어는 영문** (예: `fastapi-deps.md`, `langgraph-state.md`, `embedding-basics.md`). 검색·인용 시 영어 원본과 매칭.
  - **한국어 도메인 용어·내부 프로세스는 한글 OK** (예: `재고-관리-규칙.md`, `업무-흐름-개요.md`).
  - 경계가 모호하면 영문이 default (URL 공유·tab completion·CLI 친화).
  - **폴더명은 모두 영문** (`raw/`, `wiki/`, `components/` 등). 변경 금지.
- **메타데이터**: 모든 wiki/ 페이지 상단에 frontmatter:
  ```yaml
  ---
  tags: [<tag1>, <tag2>]
  level: beginner | intermediate | advanced
  last_updated: YYYY-MM-DD
  status: in-progress | complete | needs-review
  owner: <작성자 이름>      # 페이지를 만들거나 마지막으로 크게 수정한 사람
  sources: [<raw/path>, <src/path>]
  ---
  ```
  - `owner` 는 GitHub 핸들이 아닌 본인이 식별 가능한 이름 (예: `대영`, `daeyoung`, `DK`).
  - 매 ingest/save 시 그 작업의 작성자(PROMPTS.md 의 `<MY_NAME>`) 가 들어간다.
  - 기존 페이지를 단순 갱신할 때는 owner 를 바꾸지 말고 `last_updated` 만 갱신.
- **단일 주제 원칙**: 한 페이지에 한 주제. catch-all 문서 지양.
- **불확실 표기**: 검증 안 된 주장은 `> Unverified:` 인용 블록.
- **충돌 표기**: 페이지 간 모순은 `> Conflict:` 인용 블록 + 양쪽 source 인용.

## 3. 폴더별 용도

### raw/ (불변 입력)
- `journals/` — 개발 저널 (`YYYYMMDD-<topic>.md`)
- `meetings/` — 미팅 요약 (raw transcript 금지)
- `decisions/` — ADR 초안
- `specs/` — 요구사항·설계 문서
- `incidents/` — 장애·이슈 회고
- `learning-logs/` — "이거 처음 봤다" 본인 학습 reaction
- `references/` — 외부 학습 자료 (블로그·강의·논문·책). 하위에 `articles/`, `courses/`, `papers/`, `books/`

### wiki/ (LLM 합성, 인간 리뷰)
- `index.md` — 전체 목차. 매 ingest 후 갱신.
- `log.md` — ingest/lint 이력. 매 작업 후 1 행 추가.
- `overview.md` — 신규 합류자용 한 페이지 요약.
- `components/` — 코드 컴포넌트 (모듈·서비스).
- `runbooks/` — 사용법·운영 절차.
- `concepts/` — 학습 개념 정리.
- `decisions/` — ADR 합성 페이지.
- `sources/` — 원본 자료 인덱스.

## 4. Ingest 규칙

LLM 이 한 번의 ingest 에서 수행해야 할 것:

1. 지정된 raw 파일을 읽고 핵심 정보 추출.
2. 영향받는 wiki 페이지 식별 (기존 갱신 + 신규 생성).
3. 각 주장에 raw 경로 또는 코드 경로 인용 추가.
4. 페이지 간 cross-link 생성 (절대경로가 아닌 상대경로).
5. `wiki/index.md` 갱신.
6. `wiki/log.md` 에 1 행 추가.
7. 발견된 open question·contradiction 별도 보고.
8. **raw/ 는 절대 건드리지 않음**.

## 5. Query 규칙

- 위키 페이지에서 먼저 답을 찾는다.
- 위키에 정보가 없거나 stale 의심이면 raw/ 에서 보강.
- 답변 가치가 있다고 판단되면 wiki/ 에 새 페이지로 저장 제안.

## 6. Lint 규칙 (주 1 회 권장)

다음 항목을 점검해 `wiki/log.md` 에 리포트:

- **Stale**: `last_updated` 가 90 일 이상 지났고 source 가 변경된 페이지.
- **Contradiction**: 두 페이지가 같은 사실에 대해 다르게 기술.
- **Missing citation**: 비자명 주장에 raw·코드 인용이 없음.
- **Broken link**: 깨진 cross-link.
- **Orphan**: 어디에서도 link 되지 않은 페이지.
- **Canonical gap**: raw 에 자주 등장하지만 canonical wiki 페이지가 없는 개념.

## 7. log.md 형식

```markdown
## [YYYY-MM-DD] <action> | <target>

- <변경 1>
- <변경 2>
- <발견된 open question / conflict>
```

action: `ingest` | `query-saved` | `lint` | `manual-edit`

예시:
```markdown
## [2026-04-29] ingest | raw/learning-logs/20260428-langgraph-state.md

- Added wiki/concepts/langgraph-state-management.md
- Updated wiki/components/rag-pipeline.md (state 흐름 섹션)
- Open question: checkpoint 저장소 선택은 raw/decisions/ 에 ADR 필요
```

## 8. PR 워크플로우

- 위키 변경은 PR 로만. main 직접 push 금지.
- PR 제목: `[wiki] <action>: <summary>` 예: `[wiki] ingest: langgraph state notes`.
- 리뷰어 1 인 이상 승인 필요.
- LLM 자동 ingest PR 도 동일 규칙 적용.
