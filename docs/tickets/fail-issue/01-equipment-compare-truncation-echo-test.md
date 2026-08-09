# 01 — Truncation-echo test for the fail-issue compare endpoint

**What to build:** spec §7's contract-test row assigns fail_issue this check: "`eqp_id` 6개를내면 5개로 잘리고 `eqp_ids` 가 그 사실을 에코하는가." No fail_issue test sends six ids — the parser cap is exercised only by recipe_tat's suite (`recipe_tat/tests/test_contract.py`), but the response-side `eqp_ids` echo is assembled per-feature in `fail_issue/providers/_shape.py`. Add the six-ids → five-plus-echo assertion to `back_dev_home/ebeam/fail_issue/tests/test_contract.py`, mirroring the recipe_tat test's shape.

**Why:** review Spec axis, missing requirement. The parser is shared so the truncation itself is low-risk, but the echo is feature-owned payload assembly — and the contract suite is the mock→office swap guard: an untested echo is exactly where the two adapters quietly diverge. The spec placed this check in fail_issue's additions deliberately; recipe_tat's green run says nothing about fail_issue's payload.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 65ce7bd4 — HTTP 경유 절단·에코 + dedupe 순서 고정

- [ ] `GET /<slug>/fail-issue/equipment-compare` with six `eqp_id` values returns five, and the response's `eqp_ids` echoes the truncation
- [ ] Test lives in `back_dev_home/ebeam/fail_issue/tests/test_contract.py`, gated with `_is_mock()` if it relies on mock-only facts (same convention as the fleet-sum test added in 7d68e2a2)
- [ ] `fail_issue` provider suite stays green
