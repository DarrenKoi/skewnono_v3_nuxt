# 실험실 페이지 프로덕션 숨김 — opencode oc-review 기록

- 실행일: 2026-08-19
- 스킬: oc-review (2축 — Standards / Spec)
- 모델: `opencode-go/glm-5.3` variant=high (tier=heavy)
- 대상: `git diff 7169eb99...HEAD` — 6개 파일, 223 insertions
- 소요: standards 63s (`ses_fe9765cb2ffe7fNTldjvS9p7Sd`) · spec 52s (`ses_fe9765cc7ffeLkQ8zu22vm2Rxc`)
- Standards 기준 문서: `CLAUDE.md`, `DESIGN.md`, `docs/back-end/provider-selection.md`, `back_dev_home/health/MIGRATION.md`
- Spec: `.scratch/lab-cloud-hide/spec.md` (대화에서 확정된 요구사항을 그대로 옮긴 문서. diff 에서 유추한 항목 없음)

Tier 선정 근거: 6개 파일로 규모는 작으나, 변경 전체가 `is_cloud()` 뒤에 놓여
있어 홈 테스트 스위트가 어느 쪽으로든 통과합니다. `models.md` 의 escalation
조건("테스트 스위트가 실행되지 않는 환경에 게이트된 코드")에 해당하여 `heavy`
를 썼습니다.

## 모델이 말한 것 — Standards (exit 0)

**Findings**

**1. HARD — `back_dev_home/health/MIGRATION.md` not updated (stale endpoint table).**
The MIGRATION.md opens "This feature has three endpoints, and only one of them swaps" and lists `/health/services`, `/health/providers`, `/health/logging`. The diff adds a fourth endpoint, `GET /api/health/deployment` (back_dev_home/health/routes.py:65), open-auth and reading `_runtime` directly — i.e., a second runtime carve-out in this very feature — without touching the doc. AGENTS.md points readers to `<feature>/MIGRATION.md` as the per-feature authority; it now misstates the feature.

**2. HARD — `docs/back-end/provider-selection.md` §4 "single exception" claim now false.**
§4 states routes use `from .data import ...` exclusively and "단 하나의 예외는 `/health/providers`" (the one endpoint reading `_runtime` directly). The new route imports `from back_dev_home._runtime.env import is_cloud` inside `routes.py` (back_dev_home/health/routes.py:9), becoming a second exception the authoritative doc doesn't acknowledge. The route's docstring justifies itself well, but the doc of record contradicts the code. Both docs and code must change together per CLAUDE.md's two-places rule in spirit and AGENTS.md's doc conventions.

**3. JUDGEMENT — Duplicated Code (comment shape).** The "ssr:false bakes `runtimeConfig.public` at build time / pack.py ships the same artifact / is_cloud() is a filesystem-path check" rationale appears nearly verbatim in both back_dev_home/health/routes.py:67-78 and front-dev-home/app/composables/useDeployment.ts:3-17. Comments, not logic — acceptable for cross-boundary rationale, but the next editor updates one and not the other.

**4. JUDGEMENT — weak assertion, `test_deployment_is_open_to_a_normal_user`** (back_dev_home/health/tests/test_deployment_route.py:41): `assert response.get_json()["is_cloud"] in (True, False)` is tautological — any boolean passes. The test's real claim (200 for a non-admin) is carried by the status assert alone; the second line adds false confidence.

**Clean:** `hiddenOnCloud` as a row property, the `visibleHeaderLinksIn` / `headerLinksIn` split, tab-derivation test guarding hidden rows, single `useAsyncData` cache key, `payloadCache` reuse, and the default-false cloud guess are all consistent with CLAUDE.md's fetching/state patterns. No overlay smells (no mock/office pair touched, no localStorage plumbing, no raw colors).

## 모델이 말한 것 — Spec (exit 0)

## Review: lab-cloud-hide vs spec

### (a) Missing / partly done

1. **Partly done — req 1 "프로덕션(클라우드 배포)에서 두 페이지를 숨긴다"** (spec.md:14). Hiding is not instantaneous or guaranteed: `useDeployment.ts` defaults `isCloud` to `false` while the fetch is pending *or if it fails* (older backend, network error). On the cloud deploy the TTTM/PM-Tune rows can flash visible — or stay visible indefinitely on fetch failure. The code's own comment concedes this: "`isCloud` reads false until it does, which at worst shows a BETA row for a moment to a production user." A failure mode that silently un-hides on production is a partial implementation of "숨긴다".

That is the only gap; reqs 2–6 are all satisfied (no `office.py` change; `is_cloud()` gate; no admin gate; routes untouched — `visibleHeaderLinksIn` filters the menu only while `HEADER_INFO_PATHS` still derives from every row; and `hiddenOnCloud` is a per-row axis, not TTTM/PM-Tune hardcoding — "실험실의 각 페이지가 켜고 끌 수 있는 축이어야 합니다", spec.md:34-37).

### (b) Scope creep

1. **LabMenu trigger-inking behavior change** (LabMenu.vue:77-84). On cloud, when a user is on a hidden page, the 실험실 trigger no longer inks: "Someone who reached a hidden page by URL on the cloud sees a plain trigger." Nothing in the spec asks for this — it's an unrequested secondary UI behavior, though small and reasoned.

The new `/api/health/deployment` endpoint is *not* creep: the spec's 제약 section (spec.md:48-52) rules out build-time flags and the admin-only `/health/providers`, leaving a runtime backend answer as the only path.

### (c) Implemented but looks wrong

1. **Permanent-unhide on endpoint failure** — same root as (a.1). `isCloud = data.value?.is_cloud === true` with no error handling means any 404/timeout on `/api/health/deployment` makes the cloud deploy behave like Phase 2, defeating req 1 ("프로덕션 배포본에서 일반 사용자에게 노출되는 것을 원하지 않습니다", spec.md:9-10). The comment argues false is "the safer of the two" defaults, but that tradeoff was the author's, not the spec's.

2. Nothing else — tests, route shape `{"is_cloud": bool}`, and the open-access endpoint all match the spec's constraints.

## 판정

인용은 모두 원문을 열어 확인했습니다. 이번 회차에서 모델이 인용한 문서 두 건은
실제로 존재하고 실제로 그렇게 적혀 있었습니다 — `models.md` 가 기록한 "읽지 않은
문서를 인용하는" 실패는 없었습니다.

| # | 축 | 등급 | 판정 | 근거 |
| --- | --- | --- | --- | --- |
| 1 | Standards | HARD | 채택 | `health/MIGRATION.md:19` 이 실제로 "three endpoints" 이고 표가 3행입니다 |
| 2 | Standards | HARD | 채택 | `provider-selection.md:52` 이 실제로 "단 하나의 예외가 `/api/health/providers`" 입니다 |
| 3 | Standards | JUDGEMENT | 채택 | 근거 주석이 route docstring 과 composable 에 거의 동일하게 중복 |
| 4 | Standards | JUDGEMENT | 채택 | bool 에 대한 `in (True, False)` 는 공허한 단언이 맞습니다 |
| 5 | Spec (a.1)(c.1) | — | 보류(설명) | 판단은 옳으나 결론은 유지. 아래 참조 |
| 6 | Spec (b.1) | — | 반려 | scope creep 이 아니라 구조상 강제되는 선택입니다 |

### 1·2번에 붙는 중요한 단서 — 문서 노후는 이 변경 이전부터입니다

모델은 두 문서가 틀렸다는 점에서 옳지만, 그것을 이 diff 의 책임으로 돌린 부분은
사실과 다릅니다. `health/MIGRATION.md` 의 마지막 수정은 2026-08-01 이고
`/health/data-mode` 는 2026-08-16 에 들어왔습니다. `/health/jobs` 도 표에
없었습니다. 즉 표는 이미 두 개가 모자란 상태였고, 이번 변경은 그 노후를 **만든**
것이 아니라 **세 번째로 지나친** 것입니다. `provider-selection.md` §4 의
"단 하나의 예외" 역시 `/health/data-mode` 가 들어온 시점에 이미 거짓이 되었습니다.

수정하면서 옛 문장이 암묵적으로만 담고 있던 규칙 두 개를 명시했습니다.

- carve-out 이라는 사실이 admin 전용을 뜻하지 않습니다. gate 는 **답이 무엇을
  드러내는가**를 따릅니다.
- 이 예외는 `health/` 에 한정됩니다. 다른 feature 의 `routes.py` 가 `_runtime` 을
  직접 import 하면 그것은 예외가 아니라 위반입니다.

### 5번 — fetch 실패 시 행이 계속 보이는 문제

모델의 지적은 정확합니다. `isCloud` 는 미해결·실패 시 `false` 이므로, 클라우드에서
`/api/health/deployment` 가 실패하면 숨김이 풀립니다. 그리고 "그 트레이드오프는
스펙이 아니라 작성자가 정한 것"이라는 지적도 맞습니다.

그럼에도 기본값을 유지합니다. 근거는 두 가지입니다.

1. **사용자가 명시적으로 노출을 허용했습니다.** "url을 아는 사람들은 들어와서 봐도
   돼", "no problem some users can visit" (spec 요구사항 5). 이 기능이 막는 것은
   접근이 아니라 **초대**입니다. 잠깐 보이거나 백엔드가 상한 동안 보이는 것은
   사용자가 수용한다고 말한 범위 안에 있습니다.
2. **반대 방향의 실패가 더 비쌉니다.** 기본값을 `true` 로 두면, 사무실 백엔드가
   낡아 이 엔드포인트가 404 를 주는 동안 두 페이지가 메뉴에서 사라집니다. 사무실은
   이 페이지들을 실제 데이터로 검증해야 하는 유일한 장소이므로(요구사항 3),
   그쪽 실패가 목적을 더 직접적으로 해칩니다.

덧붙여, 이 엔드포인트가 실패하는 상황이면 `/api/tttm/*` 도 같이 실패합니다. 즉
사용자가 행을 눌러 들어가도 조작된 숫자가 아니라 에러를 봅니다 — 실제로 우려되는
피해는 이 실패 모드에서 발생하지 않습니다.

사용자에게 열린 결정으로 보고했습니다.

### 6번 — trigger inking 은 scope creep 이 아닙니다

`links` 가 필터링된 이상 `hasActiveLink` 는 필터 전후 중 하나를 골라야 하며,
"고르지 않음" 이라는 선택지가 없습니다. 스펙이 말하지 않았다는 점은 맞지만
그것은 창발적 범위가 아니라 구현이 강제하는 분기입니다. 숨겨진 행이 없는데
trigger 만 활성으로 칠해지면, 열었을 때 대응하는 행이 없어 헤더가 거짓말을 합니다.

## 양 축이 모두 놓친 것

- **`office.py` 삭제 방식이 왜 실패하는지**를 두 축 모두 다루지 않았습니다.
  이것이 이 작업의 출발점이었고, `_runtime/data_provider.py:180` 의 mock 폴백
  때문에 "숨김"이 "가짜 데이터 노출"이 된다는 점이 채택된 설계의 근거 전부입니다.
  Spec 축은 요구사항 2 를 "만족"으로만 표시했습니다.
- **`front-dev-home/app/data/apiCatalog.ts`** 에 새 엔드포인트를 넣지 않았습니다.
  의도적입니다 — 이 목록은 health 엔드포인트를 모두 담지 않고 `/health/services`
  만 담고 있어, `/health/data-mode` 의 선례를 따랐습니다.

## 후속

- 리뷰 대상 커밋: `e13d71e8`
- 수정 반영 커밋: `123ad700` (1·2·3·4번)
- 5번은 사용자 결정 대기. 뒤집으려면 `useDeployment.ts` 의 기본값 한 줄입니다.
