# raw/references/

외부에서 가져온 학습 자료. 본인이 작성한 메모(`learning-logs/`, `journals/`) 와 분리.

- **무엇이 들어가나**: 블로그 글 요약, 강의·튜토리얼 노트, 논문 요약, 책 챕터 노트.
- **무엇이 들어가지 않나**: 본인의 학습 reaction (→ `learning-logs/`), 작업 일지 (→ `journals/`).

## 하위 분류

| 폴더 | 용도 | 예시 파일명 |
| --- | --- | --- |
| `articles/` | 블로그·아티클·뉴스레터 | `20260501-karpathy-llm-wiki.md` |
| `courses/` | 강의·튜토리얼·온라인 코스 노트 | `fastapi-official-tutorial.md` |
| `papers/` | 논문 요약 (필요 시) | `2024-rag-survey.md` |
| `books/` | 책 챕터 노트 (필요 시) | `designing-data-intensive-apps-ch3.md` |

쓰지 않는 하위 폴더는 `git rm -r` 로 삭제해도 무방.

## 저작권 주의 (중요)

- **전문 복사 금지.** 외부 콘텐츠를 그대로 붙여넣지 말 것.
- **요약·발췌·자기 노트만.** 인용 시 출처 URL·저자·발행일 명시.
- 회사 내부 자료를 references/ 에 넣을 땐 NDA·기밀 등급 확인.

## ingest 결과

ingest 시 LLM 이 합성하는 곳:

- `articles/`, `courses/`, `papers/`, `books/` → 주로 `wiki/concepts/<topic>.md` (Why → What → How → References 구조)
- 절차 위주 튜토리얼 → `wiki/runbooks/<task>.md` 로 갈 수 있음

각 wiki 페이지의 References 섹션에 `raw/references/<폴더>/<파일>.md` 로 출처 인용된다.

## 파일 작성 규칙

- 파일명: 소문자-하이픈 (SCHEMA §2). 날짜 prefix 는 자료 캡처 시점이 회상에 도움될 때만 — 정적인 주제 (책·코스·논문) 는 자유.
- 본문 권장 구조:
  ```markdown
  # <자료 제목>

  - 출처: <URL>
  - 저자: <이름>
  - 발행: YYYY-MM-DD
  - 캡처: YYYY-MM-DD (이 파일 작성 일자)

  ## 요약
  - 핵심 주장 3~5개

  ## 인용할 만한 부분
  > "원문 인용" — 페이지/타임스탬프

  ## 내 메모 / 비판 / 적용 아이디어
  - (선택) 본인 코멘트
  ```
