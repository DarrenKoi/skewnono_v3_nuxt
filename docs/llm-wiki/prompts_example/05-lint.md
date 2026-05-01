# 05. Lint — 월 1 회 위키 위생 점검

> 위키가 자라면 stale·중복·누락이 쌓인다. 월 1 회 lint 가 catch-all.

## 상황

매월 첫째 주 월요일에 한 번 실행. 자동 수정은 안 하고 발견 사항만 log.md 에 기록.

## 실제 프롬프트

```text
docs/llm-wiki/WIKI_SCHEMA.md 를 운영 규칙으로 읽고 그대로 따라줘.
작성자: 대영

docs/llm-wiki/wiki/ 전체에 lint 패스 실행.

점검 항목 (SCHEMA §6):
- Stale: last_updated 가 90 일 이상이고 source 가 그 이후 변경됨
- Contradiction: 두 페이지가 같은 사실을 다르게 기술
- Missing citation: 비자명 주장에 raw/ 또는 src/ 인용 누락
- Broken link: 깨진 cross-link
- Orphan: index.md 와 다른 페이지 어디에서도 link 되지 않은 페이지
- Canonical gap: raw/ 에 자주 나오지만 canonical wiki 페이지가 없는 개념

산출:
- wiki/log.md 최상단에 prepend:
  ## [2026-05-01] lint | wiki-wide (by 대영)
- 카테고리별 bullet, 영향받는 페이지 경로 포함.
- 자동 수정 금지.
- 발견 0 건이면 "all clean" 명시.
```

## 예상 log.md 항목 (발견 있는 경우)

```markdown
## [2026-05-01] lint | wiki-wide (by 대영)

### Stale (2)
- wiki/components/auth-service.md — last_updated 2026-01-10, src/auth/*.py 가 2026-03-15 변경됨
- wiki/runbooks/deploy.md — last_updated 2025-11-30, 90 일 초과

### Missing citation (1)
- wiki/concepts/embedding-basics.md §3 의 "BGE-M3 가 multilingual 에 강하다" 주장에 출처 없음

### Contradiction (1)
- wiki/components/rag-pipeline.md 는 "top-5 chunk 사용" 으로 기술
- wiki/decisions/20260315-rag-tuning.md 는 "top-3 으로 변경" 으로 기술
- src/rag/config.py:12 확인 필요

### Orphan (1)
- wiki/concepts/jwt-internals.md — index.md 와 다른 페이지 어디에서도 link 없음

### Broken link (0)
### Canonical gap (1)
- raw/learning-logs/ 에 langgraph 관련 메모 4 건 있으나 canonical wiki/concepts/langgraph-*.md 페이지는 1 개뿐
- 후보: wiki/concepts/langgraph-checkpoint.md, langgraph-streaming.md
```

## 예상 log.md 항목 (all clean)

```markdown
## [2026-05-01] lint | wiki-wide (by 대영)

all clean — Stale 0, Contradiction 0, Missing citation 0, Broken link 0, Orphan 0, Canonical gap 0.
```

> ⚠️ all clean 이 너무 자주 나오면 lint 가 부실할 가능성. 위키가 30 페이지 이상인데 매번 0 건이면, 점검 항목 prompt 를 더 까다롭게 만들거나 LLM 모델을 더 강한 것으로 교체 검토.

## 발견 사항 처리

| 카테고리 | 처리 |
| --- | --- |
| **Stale** | 해당 컴포넌트 재-ingest (§2 또는 §3-B) |
| **Contradiction** | 사람이 코드·raw 로 진실 확인 후 한쪽 페이지 수정 |
| **Missing citation** | 페이지 작성자가 인용 추가, 못 찾으면 `> Unverified:` 로 강등 |
| **Broken link** | 링크 수정 또는 페이지가 이동/삭제됐다면 cross-link 갱신 |
| **Orphan** | index.md 또는 관련 페이지에 link 추가, 정말 가치 없으면 삭제 |
| **Canonical gap** | raw 메모를 ingest 해서 canonical 페이지 생성 (§2) |

전부 PR 로 처리 — lint 결과를 보고 한 명이 일괄 수정 PR 을 올리거나, 각 owner 에게 핑.

## 자동화 옵션

매월 1 일 cron 으로 GitHub Actions 가 lint 프롬프트를 LLM API 에 보내고 결과를 issue 또는 PR 로 자동 생성하는 패턴이 가능 — 단, 리뷰는 반드시 사람이.

## 다음 단계

발견 사항이 있으면 카테고리별로 위 표대로 처리. 다 끝나면 다시 lint 한 번 돌려 0 건 확인.
