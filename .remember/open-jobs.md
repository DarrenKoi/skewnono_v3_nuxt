# Open Jobs

_Updated: 2026-07-31 · branch: main_

## In progress

- [ ] **Anonymous self-identification** — spec committed (`6c45d6f`, `docs/superpowers/specs/2026-07-31-anonymous-self-identification-design.md`). Next: user reviews the spec, then invoke `writing-plans`. No code written yet. Scope: `_auth/self_id.py` + `verify.py` + `probe_member()` in `directory.py`, `is_admin_request()`, `POST/DELETE /api/identify`, Nuxt `identify.global.ts` + `pages/identify.vue` · since 2026-07-31
- [ ] Office verify recipe_tat + health — prepped at home 2026-07-24, only the on-site run is left. `cp office_example.py office.py` done; contract fixtures at a clean 28/28 baseline (`c7ce87a`). **At the office:** `detect_site()` should print `office` → start Flask → `.venv/bin/python scripts/check_contract.py` (any FAIL is now a genuine office-side shape difference) → eyeball recipe 현황 (`DEFAULT_LIMIT = 0`, uncapped — watch first-load latency) → bump STATUS.md · since 2026-07-21
- [ ] Office verify the recipe-open IDP chain end to end — adapter written and green at home against stand-ins (Redis-first locate, FTP fetch, raw-recipe folder, align readers), but no part has met real office data. First office run should exercise: `_locate_via_redis` against real `rcp_loc`/`tools_in_rcp` hashes, the OpenSearch fallback, `_download_first` over the real FTP tree, and the align/AMP readers against a real `.idp` · since 2026-07-29

## Blocked

- [ ] **`members` coverage rate** — the self-id spec rejects an empno with no directory row, and the gate is hard, so anyone missing from `members` is fully locked out. Need the real miss rate (contractors, service accounts) before shipping. If it is high, relax the `absent` row only · since 2026-07-31
- [ ] Confirm the cloud host forwards the `LASTUSER` cookie to `/project/workSpace` — identity depends on it alone, and a host that strips it now **fails silently**: the app works with every request logged as `anonymous`. Check the activity log for a lone `anonymous` user rather than waiting for an error · since 2026-07-31
- [ ] **How home stands in for `office_utils.read_idp_info`** — three routes offered (paste real `df.dtypes`+`head(3)` / vendor the parser like ftp_handler / pure mock from column lists); user wanted to clarify then signed off. Blocked on that decision. Partially mitigated 2026-07-29 (`office_utils/read_idp_info.py` stand-in with corrected slot values) but the real parser's output is still unseen · since 2026-07-27
- [ ] First cloud feasibility deploy → `http://skewnono-v3-webapp.aipp01.skhynix.com` — packaging shipped, unblocked on our side. Remaining: pack from the office PC (`npm --prefix front-dev-home run build && .venv/bin/python -m scripts.deploy`), copy to `/project/workSpace/`, follow the bundle's `DEPLOY.md` · since 2026-07-24

## Backlog / soon

- [ ] `SKEWNONO_SECRET_KEY` — decided: **required on cloud** (`a6613a6` refuses to boot without it) and preflight now checks the bundle's `.env` for a chosen value (`d5730e9`). Remaining act: put a real value in the office/cloud `.env` before the next deploy · since 2026-07-24
- [ ] **Sync `identity_source` into upstream `flask_modules`** — `ops_index_mgmt/skewnono_logging.py` here is AHEAD of its office upstream (the mapping line landed in `7f42541`; do NOT delete/recreate the local copy). An office-side template refresh from `flask_modules` would silently drop the field (index is `dynamic: "false"`). Office act: add the same `identity_source` keyword line to the `flask_modules` copy · office-only · since 2026-07-31
- [ ] **/identify sign-out + unverified badge UI** — `DELETE /api/identify` and `useIdentity.signOut` exist with no caller; a mistaken declaration on a shared browser has no in-app undo for 30 days, and `declared`-unverified identities show no badge. Wire a header pill/footer link to `signOut` + the 미검증 badge (review finding, 2026-07-31) · since 2026-07-31
- [ ] Close the OFFICE-VERIFY items in `docs/datatables/recipe_idp.txt` — `img_meas2` dtype; what `img_*` in `idp_image_info` hold; whether `Parameter` matches exactly across the two parsed tables (a space/case difference renders the MP table silently empty) · office-only · since 2026-07-27
- [ ] Spec 2 — skewvoir paired-scatter field-location pairing: spec written (`docs/superpowers/specs/2026-07-24-skewvoir-field-location-pairing-design.md`), no plan yet · since 2026-07-24
- [ ] storage↔sem_list hidden coupling: `storage/providers/office.py` imports `sem_list.data.get_sem_list()` at L53/L110/L240 — STORAGE=office + SEM_LIST=mock silently empties rows. Add a provider-mismatch guard · since 2026-07-21
- [ ] Mock realism: `cd_value` is `uniform(10.0, 50.0)` at `msr_file/providers/mock.py:577`, which flags most sites as outliers; tighten the spread · since 2026-07-15
- [ ] Wire next office features (16 pending mock-stub per STATUS.md; skew fab_name rename pending). Six adapters exist locally: sem_list, health, storage, recipe_tat, recipe_search, lateral_recipe · since 2026-07-21
- [ ] Settle whether main's hardware office-adapter tests lost coverage — deleted-branch rewrite renamed every test (`test_mdc_office`: 24 on main vs 13 on the branch, zero name overlap; fdc/sharpness have 18/22 branch-only names). Confirm main covers the same ground or port the gaps · since 2026-07-29
- [ ] B2 — Peer 비교 (`vs PEERS` card): auto same-recipe baseline + delta (spec §8.1) · since 2026-07-15
- [ ] B3 — FDC inline: connect orphan `Fdc*` components, CD↔`dynamic_fdc` on shared sequence axis (spec §12) · since 2026-07-15
- [ ] B3.2 — 하드웨어 timestamp popup: `useHardwareApi` eqp_id + start~end window → anchored slideover (spec §12) · since 2026-07-15
- [ ] §10.3 adaptive views (single-MSR variants of 위치/Time-Series/상관 panels) · since 2026-07-15
- [ ] B1 minors: keyboard/ARIA on clickable rows; stale comment `WaferMap.vue:26` · since 2026-07-15
- [ ] Optional: skill-creator eval on `/leave-office`+`/back-to-office` · since 2026-06-30

## Closed 2026-07-31

- **Rate limiter rebuilt** (`1f2ee4a`): the 20/5s budget is now genuinely app-wide (`application_limits`; `default_limits` was per-route so the documented contract never held), anonymous callers get per-address buckets instead of one shared bucket, and office mode points storage at the shared Redis with in-memory fallback — closing the per-worker `memory://` item below.
- **ProxyFix** — shipped in the self-id batch behind `SKEWNONO_TRUST_PROXY` (opt-in, `x_for=1` only); the two-sided trap is documented in `docs/deployment.md`.
- **Plumbing hardening** (`b474362`, `4dca3b5`): OpenSearch log install now gates on `get_mode()` (a home `.env` growing office `OPENSEARCH_*` lines can no longer fail boot or spin a retry thread), `record_request` can no longer 500 a served response, the log pipeline filters its own transport noise, and the health mock stops dialing the office Redis from home (was a 2s block per `/api/health/services` call).
- **Self-id review gaps 1–2** (`6066109`, `d5730e9`): `/identify` requires `emp_nm` server-side; preflight checks `SKEWNONO_SECRET_KEY`.

- **Wafer map drew TWO disagreeing die grids** — fixed (`dbbd719`). The UX call resolved itself: the axis lattice was not merely misaligned but *unalignable*. ECharts drops its nice-extent when an `interval` arrives with min/max and steps ticks from the extent START (−radius·1.03), so no interval can phase-shift split-lines onto `map_offset + k·pitch`. The boundary overlay now owns the lines and the axis owns only the numbers, placed on die centres via `axisLabel/axisTick.customValues`; both lattices come from one `lattice()` helper differing in phase. 79 lines per axis → 39 on the mock's 39×55 recipe. The old note's "labels stay correct" was wrong — each number sat 0.328 pitches (4 px) off its die.
- **The two IDP cross-table invariants** (`Region == P_No`, `D_No == -1` ⟺ `dnumber_removed`) — office-confirmed 2026-07-28, documented, then left unbuilt; now enforced in `providers/mock.py`, the `office_utils` stand-in, and `tests/test_mock_cross_table.py` (`0b316c6`). `D_No == -1` previously occurred at no seed, so the suppressed-data path had never run at home. The adapter still joins on `Parameter`; moving it to the integer key is now testable here.

- **Phase 3 redirect loop** — root cause was `CloudIdentityProvider` probing five attribute names `hcputil.auth.sso.SSO` never had; `identify()` always None while `login_redirect_url()` worked = infinite app↔SSO loop. Identity is now the `LASTUSER` cookie alone; `hcputil` removed from app, preflight and docs (`20f1492`).
- **Member directory** — `HGET members <empno>` → `GET /api/me`, schema in `docs/datatables/members.txt`, home mock + 30-day-equivalent TTL cache (`20f1492`, gating fixed in `984b1bf`).
- **`anonymous` fallback** — no cookie on cloud = `anonymous`, never admin, guarded against both phase allowlists (`7adaaef`).
- Closed as moot: SSO hostname registration, `hcputil` spelling confirmation, `members` value encoding (all user-confirmed or removed).

## Context to remember

- **`ms=-1` in a request log means the identity gate answered, not a route.** The activity timer is a `before_request` registered *after* the identity hook, so `-1` is the fingerprint of a short-circuit. Read `_auth/middleware.py` before suspecting a route or the SPA mount.
- **Never answer a page request from the identity gate.** It is the app's first `before_request`, so any response there blocks `index.html` and every bundle with it — a blank window, no console error. This is why the self-id gate is Nuxt middleware, not Flask.
- **Home `.env` sets `REDIS_HOST`** (to an unreachable office host), so "is Redis configured" is a false home/office signal costing 10s per cold call. Gate on `get_mode() != "office"`, never `is_cloud()` — `is_cloud()` cannot tell home from office-localhost.
- A bundle outside `/project/workSpace` makes `is_cloud()` False → **home identity provider → `local-dev` (admin) for anonymous callers**, plus no SPA mount and mock data, while still serving 200s. Bundle depth is load-bearing.
- **Column names are the office contract.** `office_utils` exists only at the office, so a drifted name passes at home and fails there. `img_meas2` in `wafer_mp_info` is P_No's value, not a filename.
- **The recipe-open FTP chain:** `meas_hist_{cdsem,hvsem}` carries `eqp_ip`, so no sem_list join is needed. `idp_name`/`idw_name` are *paths*; the FTP tree wants the **stem**. Path `/HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}.idp`, same creds as msr_image.
- **This session's loop:** Claude Code runs on the home Mac mini; the user is at the office and pulls + runs there. Office PC is Windows (`.venv\Scripts\python`). Office data is unreachable from the Mac mini (verified 2026-07-24).
- **The test suite assumes you have NO office adapters** (`office.py` is gitignored, `tests/_office_state.py`). An adapter present + a Redis timeout means the test needs a guard, not a fix. Worktrees legitimately differ in skip counts.
- Error taxonomy: bare `LookupError` → 502, bare `RuntimeError` → 503; subclasses stay 500.
- **Two sessions are live on `main` and interleave commits — and main gets *rebased*.** Stage explicit paths only; never `git add -A` / `commit -a` / `stash`. Before merging a worktree branch, check `git merge-base --is-ancestor` — a "fast-forward failed" today meant main had been rewritten under me, not that I had conflicts.
- Skewvoir seams unchanged: `overviewSites()` single analytics source; `focusedSequence` shared selection; `Fdc*` cluster is staged WIP — don't prune.
