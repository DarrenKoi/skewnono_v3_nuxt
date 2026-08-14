# Recording an opencode run

**Every `oc-*` skill run that got a reply from an opencode model must leave a
summary in `docs/opencode/`.** This is not optional and not conditional on the
findings being interesting — a run that found nothing is itself a record that
the code was looked at, by which model, on which day.

## Where

```text
docs/opencode/YYYY-MM-DD-<short-kebab-title>.md
```

The date is the run date. The title names the subject, not the skill:
`2026-08-10-oc-skills-two-axis-review.md`, not `2026-08-10-oc-review.md`. If a
file with that name already exists from an earlier run the same day, append a
short distinguishing suffix rather than overwriting it — a superseded review is
still evidence of what was thought at the time.

## Language and lint

`docs/` is covered by `npm run lint:md`, so **run it from the repo root after
writing** the file. Per `CLAUDE.md`, prose in `docs/` is Korean with formal
endings (`~입니다.`, `~합니다.`), and tables use markdownlint `MD060` compact
style. The model's own findings are quoted **verbatim**, in whatever language
they came back in — do not translate them, because a translated finding is a
paraphrased finding.

## Format

```markdown
# <subject> — opencode <skill> 기록

- 실행일: YYYY-MM-DD
- 스킬: oc-review | oc-simplify | oc-discuss
- 모델: opencode-go/glm-5.3 (tier=heavy)
- 대상: <diff 범위, 파일, 또는 논의 주제>
- 소요: <초> · 세션: ses_...

## 모델이 지적한 것

<모델 응답을 그대로 인용합니다. 요약하지 않습니다.>

## 판단

<채택 / 반려 / 보류를 사유와 함께 적습니다.
 반려한 지적도 사유를 남깁니다 — 조용히 버린 지적은 기록이 아닙니다.>

## 후속

<적용한 커밋, 남긴 이슈, 또는 "없음">
```

## Why verbatim

The value of these records is that they are not filtered through the agent that
wrote the code. Summarising the model's findings before writing them down
re-introduces exactly the bias the delegation was meant to remove. Quote first,
judge second, and keep the two visibly separate.

## Failure runs

If the run failed — timeout, empty reply twice, both providers down — record
that too, briefly. Knowing that `glm-5.2` returned an empty final message on a
tool-using review is a fact about the setup worth keeping, and the pattern only
becomes visible across several records.
