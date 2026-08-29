# 자체 감사 정리 커밋 4건 — opencode oc-simplify 기록 (ponytail 렌즈 첫 실행)

- 실행일: 2026-08-30
- 스킬: oc-simplify
- 모델: `opencode-go/glm-5.3` variant=high (tier=heavy)
- 대상: `git diff eb74b5fc...201dacb4` — `ponytail-audit` 자체 감사로 만든
  정리 커밋 4건 (`0bd7bce5`, `a510f850`, `437dbfa6`, `201dacb4`; 66 files,
  +366 / −2,892)
- 소요: 260초 · 세션 `ses_fb099ab16ffeKit1j1phrKA2aY`
- 티어 근거: `437dbfa6` 가 `ebeam/**/providers/` (escalation surface) 를
  건드립니다

## 이 실행이 다른 점

`oc-simplify` 의 2번 렌즈가 이날부터 `ponytail-review` 의 다섯 태그
(`delete:` / `stdlib:` / `native:` / `yagni:` / `shrink:`) 와 한 줄 형식,
`net: -N lines` 집계를 씁니다. `stdlib:` 과 `native:` 는 저장소 안만 grep
하는 Reuse 렌즈가 못 보던 축입니다. 차가운 모델이 `yagni:` / `delete:` 로
잘못 찍을 의도된 구조 7건은 `.claude/oc-project.md` 의 새
"Deliberate structure" 절에 적어 프롬프트에 그대로 붙였습니다.

대상이 Claude 자신의 `ponytail-audit` 결과물이라는 점도 의도한 것입니다.
같은 눈으로 다시 보면 같은 가정을 그대로 지나치므로, 놓친 것을 찾는 데는
바깥 모델이 맞습니다.

## 모델이 말한 것 (원문 인용)

> **Findings, ordered by value.** The cleanup itself is sound (the hoists into `_core/timefmt.py`, `_shared.py`, `para_buckets._str_digest`, `fleet_too_small_payload` all landed correctly, mock and office_example both call the shared forms). What it missed:
>
> **1. Contract drift — the backend half of three payloads was deleted, the frontend types weren't.** Verified by grep: no runtime reads of any of these, so removal is type-only, no behaviour change.
>
> - `front-dev-home/app/composables/usePmPlanningApi.ts:38-40,52`: **delete** `FleetDefaults` interface and `defaults: FleetDefaults` field — backend stopped shipping `defaults` in this very diff. (−3)
> - `front-dev-home/app/utils/pmPlanning.ts:7-9`: this comment now *lies* — "The backend still ships `defaults.focus_n` and `defaults.advisory_threshold`" was the documented reason to leave the contract alone, and the same change-series removed it. Rewrite or delete; leaving it invites someone to "restore" the field. (−2)
> - `front-dev-home/app/composables/useFailIssueApi.ts:142-143`: **delete** `min_expected_fails` / `confidence_z` from `FailIssueFleetReference` — `fail_issue/providers/_shape.py` stopped sending them. (−2)
> - `front-dev-home/app/composables/useChatApi.ts:7`: **delete** `supports_vision: boolean` — dropped from `chat/config.py`, `contracts.py`, fixtures, and `.env.example` in this diff. (−1)
>
> **2. REUSE — `_core/timefmt.iso_z` was built but not applied in files this diff touched:**
>
> - `back_dev_home/ebeam/pm_planning/providers/mock.py:84`: `FETCHED_AT` hand-rolls it (`NOW` is tz-aware UTC — safe swap).
> - `back_dev_home/ebeam/device_statistics/providers/mock.py:241`: `chg_tm` same (`BASE_TIME` is aware UTC).
> - Not swap-safe: `recipe_tat/providers/mock.py:361` `_format_iso` — its inputs are KST-aware, so the existing `.replace("+00:00","Z")` is a no-op and `iso_z` would silently convert to UTC. BEHAVIOUR-CHANGE — leave it, but it deserves a comment.
> - Tail for a follow-up (untouched files): `sem_list`, `access_control` ×2, `storage`, `meas_hist` mocks still hand-roll ~8 more.
>
> **3. shrink:** `back_dev_home/chat/tools/_shared.py:36` — `trace["result_count"] = len(rows)` is unconditionally overwritten at line 41; the first assignment is dead. (−1)
>
> **4. shrink:** `back_dev_home/ebeam/recipe_tat/tests/test_contract.py:100,120,134,149` — four identical function-local `_generate_meas_hist` imports; one module-level import. (−3)
>
> **5.** `front-dev-home/app/utils/stats.ts:150` — comment says CorrelationScatter *and FdcAnalysis* "both now call here"; FdcAnalysis.vue was deleted here, so "both" is stale. Comment fix.
>
> Efficiency and altitude: nothing real — the hoists all moved logic to the right layer. Net: −12 lines possible.
>
> File read but not in the diff: `front-dev-home/app/utils/pmPlanning.ts`.

## 판단

지적마다 코드를 열어 확인한 뒤 나눴습니다.

| 지적 | 처리 | 사유 |
| --- | --- | --- |
| 1a `FleetDefaults` + `defaults` 필드 | 채택 | 이 diff 가 `contracts.py` / `mock.py` / `office_example.py` 에서 `defaults` 를 지웠고 프론트 읽는 곳은 없습니다 |
| 1b `pmPlanning.ts` 주석 | 채택 | "백엔드가 아직 보낸다" 는 문장이 거짓이 됐습니다. 지운 날짜를 적는 문장으로 바꿨습니다 |
| 1c `min_expected_fails` / `confidence_z` | 채택 | `fail_issue/` 전체에 참조가 없습니다 |
| 1d `supports_vision` | 채택 | 백엔드 참조 0건. `docs/superpowers/` 의 옛 계획서만 남는데 그것은 이력이라 둡니다 |
| 2 `pm_planning` `FETCHED_AT` → `iso_z(NOW)` | 채택 | `NOW` 는 aware UTC, 마이크로초 없음 → 출력 동일 |
| 2 `device_statistics` `chg_tm` → `iso_z(timestamp)` | 채택 | `timestamp = BASE_TIME - timedelta(hours=…)` 라 마이크로초 없음 → `timespec="seconds"` 와 `isoformat()` 이 같은 문자열 |
| 2 `recipe_tat` `_format_iso` | 보류 | 모델 스스로 BEHAVIOUR-CHANGE 로 표시했고, 파일 자체가 diff 에 없습니다. 후속에서 주석 한 줄 |
| 2 미접촉 mock 8곳 | 보류 | diff 밖 파일. `storage/providers/mock.py:53` 의 사설 `_iso_z` 도 같은 후속입니다 |
| 3 `_shared.py` 죽은 대입 | 채택 | `test_runtime.py:494` 는 최종값만 읽습니다 |
| 4 `test_contract.py` 지역 import 4건 | **반려** | 네 import 모두 `if get_data_provider("recipe_tat") != "mock": return` 가드 **뒤**에 있습니다. mock 헬퍼를 mock 으로 돌 때만 import 하려는 의도이고, 옆의 `_generate_rows` / `_lot_index` 지역 import 는 그대로 남으니 하나만 올리면 섞인 꼴이 됩니다. −3줄 값어치가 아닙니다 |
| 5 `stats.ts` 주석 | 채택 | `FdcAnalysis.vue` 는 이 diff 에서 삭제됐습니다 |

모델이 놓친 것 하나를 더 고쳤습니다: `pm_planning/contracts.py:5` 의
docstring 도 "raw values plus defaults" 라고 말하고 있었습니다.

결과 9 files, +8 / −17. 채택 8건 · 반려 1건 · 보류 2건.

## 검증

worktree 에서 본 checkout 의 도구로 실행했습니다.

| 검사 | 결과 |
| --- | --- |
| `ruff check .` | clean |
| `pytest back_dev_home/ebeam/pm_planning back_dev_home/ebeam/device_statistics back_dev_home/chat -q` | 469 passed, 1 skipped (office 게이트, worktree 에 `office.py` 없음) |
| `nuxt typecheck` | exit 0 |
| `node --test` | 1718 / 1718 |
| `eslint .` | 0 errors (경고 2건은 미접촉 `ImageViewer.vue` 의 기존 것) |

## 이번 실행이 렌즈에 대해 말해 준 것

- 가장 값진 지적(1번)은 ponytail 태그가 아니라 **계약 표류**였습니다. 백엔드
  필드를 지워도 프론트의 `use*Api.ts` 인터페이스는 typecheck 를 통과합니다 —
  JSON 경계에서 타입을 검사하는 것이 없기 때문입니다. 자체 감사가 이것을
  못 본 이유는 백엔드와 프론트를 따로 훑었기 때문입니다.
- "Deliberate structure" 절은 제 역할을 했습니다. `data.py`, `office_example.py`,
  `__fixtures__/`, provider env 노브 중 어느 것도 `yagni:` / `delete:` 로
  찍히지 않았습니다.
- `stdlib:` / `native:` 지적은 0건이었습니다. 이 diff 는 삭제 위주라 그 축에
  걸릴 것이 적었을 뿐이고, 렌즈 자체의 무용함을 뜻하지는 않습니다. 다음
  기능 diff 에서 다시 봅니다.
- 모델은 한 줄 형식을 3·4·5번에만 지켰고 1·2번은 절 형태로 썼습니다. 내용이
  정확했으므로 형식은 따지지 않았습니다.

## 후속

- 채택분은 이 기록과 같은 커밋으로 `main` 에 들어갑니다.
- 후속 1건: 나머지 mock 의 손으로 만든 ISO-Z 8곳을 `iso_z` 로 모으고,
  `recipe_tat` 의 `_format_iso` 에는 KST 입력이라 바꾸면 안 된다는 주석을
  답니다.
