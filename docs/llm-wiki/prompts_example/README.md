# prompts_example/

[`../PROMPTS.md`](../PROMPTS.md) 의 각 프롬프트를 실제 값으로 채운 사용 예시 모음.

> **사용법**: 본인 상황과 가까운 파일을 골라 → 복사 → `<MY_NAME>`, 경로, 날짜만 본인 값으로 수정 → 그대로 LLM 에 붙여넣기.

## 공통 가정

모든 예시는 다음 값을 사용:

- `<WIKI_ROOT>` = `docs/llm-wiki`
- `<MY_NAME>` = `대영`
- 오늘 날짜 = `2026-05-01`

본인 환경에서는 위 값을 자기 것으로 일괄 치환하면 된다.

## 시나리오 인덱스

| 파일 | 언제 사용 | 해당 PROMPTS.md § |
| --- | --- | --- |
| [`01-bootstrap.md`](./01-bootstrap.md) | 새 프로젝트에 starter 복사한 직후 1 회 | §1 |
| [`02-ingest-raw.md`](./02-ingest-raw.md) | raw/ 에 파일 추가한 후 (가장 흔함) | §2 |
| [`03-code-ingest.md`](./03-code-ingest.md) | 기존 코드베이스를 위키화할 때 | §3 |
| [`04-query.md`](./04-query.md) | 위키에 자연어로 질문할 때 | §4 |
| [`05-lint.md`](./05-lint.md) | 월 1 회 위키 위생 점검 | §6 |

§5 (Save Answer) 와 §7 (PR Description) 은 §4·§2 의 자연스러운 후속이라 별도 예시 생략 — PROMPTS.md 의 템플릿을 그대로 따르면 된다.

## 워크플로우 추천

처음 사용하는 팀원은 다음 순서로 한 번씩 따라해보면 전체 그림이 잡힌다:

1. `01-bootstrap.md` — 프로젝트 셋업 (한 번)
2. `02-ingest-raw.md` — 학습 메모 한 건 ingest
3. `04-query.md` — 방금 만든 페이지에 질문
4. `03-code-ingest.md` — 컴포넌트 하나 위키화
5. `05-lint.md` — 첫 lint 패스 (대부분 all clean)
