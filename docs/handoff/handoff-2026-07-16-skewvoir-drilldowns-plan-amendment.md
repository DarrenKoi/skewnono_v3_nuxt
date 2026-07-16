# Handoff: Skewvoir analysis-drilldowns plan — amended with 측정 개요 focus switcher

Repo: `/Users/daeyoung/Codes/skewnono_v3_nuxt` (branch `main`, work directly on main per CLAUDE.md)

## What this session did

1. Reviewed the analysis-drilldowns implementation plan at the user's request and confirmed a real gap: with multiple MSRs selected, 측정 개요 (Measurement Overview / Dashboard view) had no set awareness and there was **no way to switch the focus MSR inside the workspace at all** (`useSkewvoirRoute.ts` has `setView`/`setMsrs`/`setParam` but no `setMsr`; focus only changed via fresh navigation from search).
2. User approved a **focus switcher chip strip** UX for the overview (chips = comparison set; click switches focus; one MSR rendered at a time, never a set fan-out). Set add/remove stays in the shared context bar (Task 3).
3. Amended BOTH plan docs (Korean is source of truth, English mirrored 1:1). **Docs only — no code was written. The feature is NOT implemented.**
4. Verified: `npx markdownlint-cli2` on both docs = 0 errors; `git diff --check` clean. **Changes are uncommitted.**

## Artifacts (read these, don't re-derive)

- Amended plan (KO, source of truth): `docs/superpowers/plans/2026-07-16-skewvoir-analysis-drilldowns.md`
- Amended plan (EN mirror): `docs/superpowers/plans/2026-07-16-skewvoir-analysis-drilldowns.en.md`
- Design spec (intentionally NOT edited this session): `docs/superpowers/specs/2026-07-16-skewvoir-analysis-drilldowns-design.md`
- Planning-session plan file (edit rationale + review verdict): `/Users/daeyoung/.claude/plans/docs-superpowers-plans-2026-07-16-skewv-mutable-cosmos.md`

Amendment summary (details live in the plan docs): principle 0.1 now allows focus switching (ban is set fan-out only); §2 Phase-1 table includes 3b; Task 1 flags the "focus changes only via search re-entry" fixture as superseded; Task 3 pins `setFocusedMsr` semantics; **new Task 3b** "측정 개요 focus 전환 chip strip"; Task 13 and the Self-Review risk table got matching clarifications.

## Key code facts discovered (verified, shape the implementation)

- `front-dev-home/app/composables/useMsrFileApi.ts:124-173` — `fetchMsrFile` dedupes only in-flight requests; **no completed-response cache** (A→B→A refetches). Retries 429 with backoff; mock backend rate-limits msr_file at 20 req/5s.
- `front-dev-home/app/composables/useSkewvoirAnalysis.ts:61-79` — focus-file watcher has **no stale-response guard**; rapid focus switches can race (older response clobbers newer).
- `front-dev-home/app/components/ebeam/skewvoir/LeftRail.vue:150-160` — renders Lot/Recipe/EQ/MP/Captured **from URL query fields**, so `setFocusedMsr` must rewrite `lot`/`eq`/`cap` from the new focus's `meas_hist` row (`rowByMsr`), not just `msr`.
- `useSkewvoirAnalysis.ts:159` — `setFiles` already holds full `MsrFileResponse` objects for set members if Time-Series/Position-Stack was visited → chip switches can resolve with zero network (cache chain: session cache → `setFiles` → `fetchMsrFile`).
- `useSkewvoirAnalysis.ts:12,152-157` — `TREND_LIMIT = 30` caps the set; bound the session cache at this.
- `useSkewvoirAnalysis.ts:113-115, 129-133` — `focusedSequence` reset and `mp` normalization already handled by existing watchers; don't re-implement.
- `wantSet` (`useSkewvoirAnalysis.ts:138-140`) gates batch fetch to `time-series|position-stack`; the Dashboard must never call `fetchMsrFiles` (Task 1 characterization invariant).

## Next session: what to do

Execute the amended plan starting from **Task 0** (land/commit the in-flight wafer-map changes currently dirty in the worktree — see `git status`; Task 0 is a gate for Tasks 5/6/13) then Task 1 onward. If the user wants the quick win first, Task 3b (chip strip) requires Task 3's `setFocusedMsr` — respect that dependency. Follow each task's Steps/Acceptance/Verify/Commit blocks verbatim from the Korean plan.

Pending decisions for the user:
- Commit the two amended plan docs (uncommitted; only commit when asked).
- Whether to start at Task 0/1 or negotiate scope.

## Conventions that bit us / must follow

- Korean docs: formal endings (`~입니다/~합니다`), markdownlint MD060 compact tables; run `npm run lint:md` (or `npx markdownlint-cli2`) after editing Markdown.
- Keep KO and EN plan docs in sync section-by-section; displayed UI strings stay in Korean even in the EN doc.
- Work on `main`; commit/push only when the user asks.
- App verification: Flask mock on :5050, Nuxt with `NUXT_API_TARGET=http://localhost:5050`; browser screenshots via Tailscale IP `http://100.103.116.55:3000` (Claude-in-Chrome is remote), Playwright screenshots under `.playwright-mcp/screenshots/`.

## Suggested skills

- `superpowers:executing-plans` — the plan doc is the execution artifact; use this to run it with review checkpoints.
- `superpowers:subagent-driven-development` — the plan was written for per-task subagent execution (prior tasks in this repo shipped that way).
- `superpowers:test-driven-development` (or `tdd`) — every task closes framework-free computation test → component wiring → live evidence.
- `verify` (project skill) — build/launch recipe for live-verifying in the running app.
- `superpowers:requesting-code-review` / `codex:rescue` — the user habitually runs a Codex consensus review before landing skewvoir work.
- `leave-office` / `remember:remember` — if the session ends mid-plan, write the carryover.

No secrets or PII encountered this session; nothing redacted.
