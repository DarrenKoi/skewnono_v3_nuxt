# 02 — fail-issue.yaml `eqp_ids` field description still states the backwards order

**What to build:** commit 466bf775 fixed the truncation/de-dup order in the `eqp_id` *query-param* description ("truncates it to the first MAX_EQP_IDS (5) entries FIRST … WITHOUT de-duplicating; de-duplication happens afterwards"), but the `eqp_ids` *response-field* description ~20 lines below still reads "The eqp_id list actually used, after de-duplication and the MAX_EQP_IDS (5) cap." Rewrite the field description to state truncate-first-dedupe-after, matching the param text and the actual pipeline (`_analytics_routes.py` truncates the raw list; `fail_issue/providers/_shape.py` de-dupes during assembly). Bonus: the same sentence says "Echoed so a silent truncation is never silent" — fold the redundancy away while editing.

**Why:** review Spec axis, implemented-but-wrong documentation. The contract document now asserts both orders within one endpoint section. An office implementer who reads the field description writes dedupe-first — which silently admits a sixth *distinct* id that the real parser would have truncated away (`eqp_id=X,X,X,X,X,Y` yields `["X"]`, never `["X","Y"]` — the param text's own example). A contract that contradicts itself on ordering is worse than no contract for exactly the swap it exists to guard.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-09) — 5b2cb5da

- [ ] `eqp_ids` field description states truncation first, de-duplication after — agreeing with the `eqp_id` param description
- [ ] No other yaml content changed; the recipe-tat contract's wording stays as-is
