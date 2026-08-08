// Request-shape limits shared by the two analytics features that send a
// multi-equipment selection (recipe-tat and fail-issue).
//
// This lives in one file because the backend keeps its counterpart in one file:
// `MAX_EQP_IDS` in `back_dev_home/ebeam/hitachi/_analytics_routes.py`, which the
// shared `resolve_analytics_scope` applies to every feature that reads `eqp_id`.
// Exporting the same name from two composables made Nuxt silently drop one of
// them, so a later change to either feature's cap would have handed the other
// feature's value to every auto-importing consumer.
//
// It is a UI convenience — it stops the user checking a sixth box. It is NOT a
// trust boundary: the server truncates the list regardless and echoes the
// truncated result in `eqp_ids`, so the frontend never has to be believed.
//
// Why this file exists at all, given that the fail-issue spec fenced the
// recipe-tat code as read-only: the collision above is a build-time WARN and a
// runtime failure, not a type error, so honoring the fence would have meant two
// names for one number — a place for the caps to drift apart. The exception is
// recorded in `docs/superpowers/specs/2026-08-08-fail-issue-by-equipment-design.md`
// §10.1. The cap's canonical home is `recipe_tat/contracts.py` (recipe-tat spec
// §4.2); this module is the frontend's reference to it.
export const MAX_COMPARE_EQPS = 5
