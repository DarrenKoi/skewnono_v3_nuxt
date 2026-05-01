# raw/decisions/

ADR (Architecture Decision Record) 초안.

- 파일명: `YYYYMMDD-<title>.md` (예: `20260501-postgres-vs-sqlite.md`)
- 형식: 문제 → 옵션 → 선택 → 결과 → 트레이드오프
- 한 결정에 한 파일.
- 결정이 번복되어도 원본 파일은 수정 금지. 새 ADR 로 supersede.
- 템플릿: [`../../_templates/decision.md`](../../_templates/decision.md)

ingest 시 LLM 이 `wiki/decisions/<같은이름>.md` 로 합성·cross-link 한다.
