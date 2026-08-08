# 02 — 400 tests for the two equipment endpoints

**What to build:** spec §7's test list includes "잘못된 `tool_slug` → 400", but the only 400 assertion today hits `/recipe-tat/summary`. Add the bad-`tool_slug` → 400 coverage for `GET /<slug>/recipe-tat/equipments` and `GET /<slug>/recipe-tat/equipment-compare`, colocated per repo convention.

**Why:** review Spec axis, missing requirement. §7's test list names the bad-`tool_slug` → 400 case, and the two new endpoints shipped without it — the only 400 assertion still covers the pre-existing `/summary` route. Risk is low because scope resolution is shared, but the contract tests are the mock→office swap guard: the office adapter must reproduce the same 400, and an untested path is where the two adapters quietly diverge.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 65ce7bd4 — 4개 경로(fail-issue 쌍둥이 포함)

- [ ] Both equipment endpoints assert 400 on an unknown `tool_slug`
- [ ] Tests live in `back_dev_home/ebeam/hitachi/recipe_tat/tests/` or the cross-feature `tests/` suite, matching where the existing 400 assertion lives
