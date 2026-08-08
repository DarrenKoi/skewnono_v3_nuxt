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
export const MAX_COMPARE_EQPS = 5
