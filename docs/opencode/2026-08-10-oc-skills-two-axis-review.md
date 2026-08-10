# oc-* 스킬 자체에 대한 2축 리뷰 — opencode oc-review 기록

- 실행일: 2026-08-10
- 스킬: oc-review
- 모델: `opencode-go/kimi-k3` (tier=heavy)
- 대상: `git diff main...HEAD` — oc-* 스킬 3종 도입 커밋 2개 (7 files, +920)
- 소요: Standards 252초 · 세션 `ses_014b32040ffeQTE06p04YT2V5a`
- 결과: Standards 성공 · **Spec 축은 빈 최종 메시지로 실패**

## 모델이 지적한 것 (Standards, 원문 인용)

> ### (a) Documented-standard violations
>
> **HARD — CLAUDE.md "Project skills" table left stale.** CLAUDE.md §Agent skills enumerates the skills in `.claude/skills/` (verify, home-to-office, generate-mock, add-vendor). The diff adds three new skill directories (`oc-review`, `oc-simplify`, `oc-discuss`) and touches neither CLAUDE.md nor AGENTS.md — the documented index no longer matches the tree it claims to list.
>
> ### (b) Baseline smells
>
> **JUDGEMENT — internal inconsistency (smells.md rationale is false).** `smells.md` says "Paste this file into the opencode prompt verbatim — the delegated model has no access to this repo's skill files and cannot read it otherwise." But `oc-review`'s own prompt in the same diff instructs the model to "Read these for the repo's documented standards: CLAUDE.md, DESIGN.md, and any MIGRATION.md" — i.e., it *can* read repo files (read-only under `--agent plan`, per `oc.sh`'s header). Pasting is harmless; the stated reason contradicts the change itself.
>
> **JUDGEMENT — Shotgun Surgery (reliability rationale restated 4×).** The "default `heavy` because `glm-5.2` failed tool-using review" reasoning lives in `models.md` ("Consequence"), `oc-review` §2, `oc-simplify` §2, and `spec.md`. The fix commit `5f038d79` already had to edit all four for one logical change — the smell the baseline names. `models.md` is the designated home; the skills should reference, not restate.
>
> **JUDGEMENT — inconsistent application of the same measurement (oc-discuss).** `oc-discuss` recommends "`medium` is fine for a scoped implementation choice," yet its round-1 prompt says "Inspect the repo yourself as needed" — the tool-using shape `models.md` records `glm-5.2` failing 2/2 on. The "Consequence" in `models.md` names only `oc-review`/`oc-simplify`; either extend it to `oc-discuss` or say why discussion is exempt.
>
> **JUDGEMENT — lint:md coverage gap (pre-existing, widened here).** CLAUDE.md says `lint:md` covers "every tree whose Markdown we author" and lists deliberate exclusions; `.claude/skills/` is in neither list, and this diff adds ~460 lines of authored Markdown there. Predates the diff (verify etc. already unlinted) — widen the glob or record the exclusion in CLAUDE.md.
>
> **JUDGEMENT (minor) — Duplicated Code in oc.sh.** The `is_timeout` handler block ("timed out after ${OC_TIMEOUT}s on $USED … exit 124") appears twice with diverging advice text.
>
> **Suppressed:** Fowler-list duplication into prompts and tier boilerplate per skill — deliberate self-containment; repo-specific smells — no provider/mock hunks in this diff.
>
> **Clean:** `oc.sh` header matches behavior (exit codes, stdin prompt, per-attempt tags); MD060 compact tables throughout; spec correctly placed under `.scratch/` per `docs/agents/issue-tracker.md`.

## 판단

| 지적 | 처리 | 사유 |
| --- | --- | --- |
| CLAUDE.md 스킬 표 미갱신 (HARD) | 채택 | 정확합니다. 세 스킬과 `_opencode/` 설명을 추가했습니다 |
| `smells.md` 근거가 사실과 다름 | 채택 | 모델은 파일을 읽을 수 있습니다. 붙여넣는 진짜 이유(재현성)로 문구를 고쳤습니다 |
| 신뢰도 근거 4중 중복 (Shotgun Surgery) | 채택 | `models.md` 를 단일 출처로 두고 스킬들은 참조만 하도록 줄였습니다 |
| `oc-discuss` 티어 권고 불일치 | 채택 | 토론도 저장소를 읽는 작업이므로 기본을 `heavy` 로 맞췄습니다 |
| `lint:md` 커버리지 공백 | 채택(기록 쪽) | 글롭을 넓히는 대신 `.claude/skills/**` 를 의도적 제외로 CLAUDE.md 에 명시했습니다. 이 트리는 영어로 쓰는 에이전트용 지시문이라 `docs/` 의 한국어 규칙과 충돌합니다 |
| `oc.sh` timeout 블록 중복 | 채택 | `fail_timeout()` 하나로 합쳤습니다 |

반려한 지적은 없습니다.

## Spec 축 실패에 대하여

Spec 축은 `kimi-k3` 에서도 빈 최종 메시지로 끝났습니다. 같은 실패를 앞서
`glm-5.2` 에서 두 번 봤으므로 이는 모델 고유 문제가 아니라 **간헐적**
현상으로 판단합니다. 도구 호출은 모두 성공하고 최종 step 만 0 토큰으로
끝나는 형태입니다.

그래서 `oc.sh` 에 **빈 응답 1회 재시도** 를 넣었습니다. 두 번 모두 비면
그때 실패로 종료합니다. 빈 응답을 "지적 없음" 으로 보고하는 경로는 계속
막혀 있습니다.

## 후속

- 위 6건을 반영한 커밋으로 이어집니다.
- `models.md` 의 신뢰도 표는 재측정 대상입니다. `medium` 이 안정화되면
  기본 티어를 되돌릴 수 있습니다.
