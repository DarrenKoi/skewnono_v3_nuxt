# 01. Bootstrap — 프로젝트 셋업 (1 회)

> 새 프로젝트에 starter 폴더 (`docs/llm-wiki/`) 를 복사한 직후 1 회 실행. 일반 팀원은 이 단계 건너뛰고 [`02-ingest-raw.md`](./02-ingest-raw.md) 부터.

## 상황

- starter 를 `docs/llm-wiki/` 로 복사 완료.
- `WIKI_SCHEMA.md`, `wiki/index.md`, `wiki/log.md`, `wiki/overview.md` 에 placeholder 가 남아있는 상태.

## 치환값

| 변수 | 값 |
| --- | --- |
| `<WIKI_ROOT>` | `docs/llm-wiki` |
| `<프로젝트명>` | `SKEWNONO` |
| 오늘 날짜 | `2026-05-01` |

## 실제 프롬프트

```text
docs/llm-wiki/ 의 LLM Wiki 부트스트랩을 마무리해줘.

작업:
1. docs/llm-wiki/WIKI_SCHEMA.md 와 docs/llm-wiki/wiki/{index.md, log.md, overview.md} 안의:
   - <프로젝트명> → SKEWNONO
   - YYYY-MM-DD → 2026-05-01
   를 일괄 치환.
2. raw/ 와 wiki/ 컴포넌트 폴더는 빈 상태 유지 (첫 ingest 전).
3. raw/, wiki/ 하위 README.md 는 폴더 설명용이므로 손대지 말 것.

작성자(owner) 정보는 부트스트랩 시점에 정하지 않는다.
각 페이지가 ingest/save 시점에 그 작업의 작성자로 채워진다.

치환된 파일 목록을 마지막에 보고.
```

## 예상 LLM 출력

```text
✅ 치환 완료:
- docs/llm-wiki/WIKI_SCHEMA.md (Last updated, 본문 4 곳)
- docs/llm-wiki/wiki/index.md (frontmatter 1 곳)
- docs/llm-wiki/wiki/log.md (frontmatter 1 곳, 부트스트랩 항목 1 곳)
- docs/llm-wiki/wiki/overview.md (frontmatter 1 곳, 본문 1 곳)

raw/, wiki/ 하위 README.md 는 손대지 않음.
```

## 다음 단계

→ [`02-ingest-raw.md`](./02-ingest-raw.md) 또는 [`03-code-ingest.md`](./03-code-ingest.md)
