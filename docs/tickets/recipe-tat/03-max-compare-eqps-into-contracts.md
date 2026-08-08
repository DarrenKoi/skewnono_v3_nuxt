# 03 — `MAX_COMPARE_EQPS` lands in contracts.py; reuse the summary empty state

**What to build:** two spec-alignment items. First, spec §4.2 names `recipe_tat/contracts.py` as the home of the compare cap `MAX_COMPARE_EQPS = 5`; today it lives as `MAX_EQP_IDS` in `_analytics_routes.py` (parser-owned) and separately as `MAX_COMPARE_EQPS` in the frontend composable. Give the cap one documented home in `contracts.py`, have the parser reference it, and align the twin constant names so they stop drifting. Second, spec §3.3 says the equipment view reuses the existing 전체 요약 "측정 없음" empty state; `RecipeTatEquipmentView` shipped its own markup instead — swap to the shared empty state.

**Why:** review Spec axis, two placement deviations. §4.2 puts the cap in `contracts.py` because that module is the shared return-type contract both adapters normalize to — a cap living in the route parser is invisible to anyone implementing against the contract, and the twin frontend/backend constants under different names can drift apart silently (backend truncates at one value, frontend allows another). §3.3's empty-state reuse matters for the same reason as every reuse rule here: two empty-state designs for the same condition drift on the next copy edit.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 65ce7bd4 — 이탈 있음: cap 은 _analytics_routes.py 에 남겼습니다(계약에 두면 공유 파서가 기능 계약을 임포트하는 레이어 역전. 이 결정은 구현 플랜에 이미 기록돼 있었고 spec §4.2 만 옛 문장을 들고 있었습니다). 이름은 MAX_COMPARE_EQPS 로 정렬, 빈 상태는 AppEmptyState 로 추출

- [ ] The cap of 5 has a single documented home in `recipe_tat/contracts.py`; backend parser and frontend constant reference/align with it
- [ ] `RecipeTatEquipmentView` renders the shared 전체 요약 empty state rather than its own markup
- [ ] Contract tests still pass with the constant's new home
