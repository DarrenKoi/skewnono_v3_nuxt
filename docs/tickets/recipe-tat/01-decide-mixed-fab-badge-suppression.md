# 01 — Decide: mixed-fab badge suppression vs spec §3.2

**What to build:** a decision, then alignment. The equipment badge signal is suppressed when the query scope mixes fabs (`isPeerGroupComparable`, plus the mixed-fab TAT-index tooltip wording). The recipe-tat by-equipment spec §3.2 defines the peer group as the query scope itself — "또래 집단(peer group)은 **조회 범위 그 자체**입니다… 모델별·fab별로 더 잘게 나누지 않습니다" — so the implementation narrows a shipped signal's behavior without spec sanction; the amended §3.5 only defers the *office* procedure for mixed fabs. Either amend the spec to sanction mixed-fab suppression (with the reasoning recorded), or revert the gating so badges judge across the full query scope. Deliverable is the recorded decision plus code and spec agreeing.

**Why:** review Spec axis, worst finding of the recipe-tat group. The spec is this repo's source of truth for behavior decisions, and §3.2 explicitly forbids subdividing the peer group by fab — yet the implementation does exactly that, changing what a shipped signal means for users who mix fabs in one query. This is not a mechanical fix: suppressing may well be the *right* product call (cross-fab percentiles can mislead), but that call belongs in the spec, recorded with its reasoning — not smuggled in by implementation fiat.

**Blocked by:** None — can start immediately. Gates any future badge-behavior work.

**Status:** done (2026-08-09) — ba99784b — 억제 유지, spec §3.2 개정

- [ ] Decision recorded in `docs/superpowers/specs/2026-08-07-recipe-tat-by-equipment-design.md`
- [ ] Code and spec agree on what happens to badges when the query scope mixes fabs
- [ ] If suppression stays: the spec names the mixed-fab rule; if reverted: `isPeerGroupComparable` gating and the tooltip wording come out
