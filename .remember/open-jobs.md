# Open Jobs

_Updated: 2026-07-29 · branch: main_

## In progress

- [ ] Office verify recipe_tat + health — prepped at home 2026-07-24, only the on-site run is left. `cp office_example.py office.py` done; contract fixtures at a clean 28/28 baseline (`c7ce87a`). **At the office:** `detect_site()` should print `office` → start Flask → `.venv/bin/python scripts/check_contract.py` (any FAIL is now a genuine office-side shape difference) → eyeball recipe 현황 (`DEFAULT_LIMIT = 0`, uncapped — watch first-load latency) → bump STATUS.md · since 2026-07-21
- [ ] Office verify the recipe-open IDP chain end to end — the adapter is written and green at home against stand-ins (Redis-first locate, FTP fetch, raw-recipe folder, align readers), but no part of it has met real office data. First office run should exercise: `_locate_via_redis` against real `rcp_loc`/`tools_in_rcp` hashes, the OpenSearch fallback, `_download_first` over the real FTP tree, and the align/AMP readers against a real `.idp` · since 2026-07-29

## Blocked

- [ ] **How home stands in for `office_utils.read_idp_info`** — I offered three routes (paste real `df.dtypes`+`head(3)` output / vendor the parser like ftp_handler / pure mock from column lists alone); user wanted to clarify the question and then signed off. Blocked on: that decision. Partially mitigated 2026-07-29 — `office_utils/read_idp_info.py` now has a stand-in with corrected slot values — but the real parser's output still has not been seen · since 2026-07-27
- [ ] First cloud feasibility deploy → `http://skewnono-v3-webapp.aipp01.skhynix.com` — packaging shipped, unblocked on our side. Remaining: pack from the office PC (`npm --prefix front-dev-home run build && .venv/bin/python -m scripts.deploy`), copy to `/project/workSpace/`, follow the bundle's `DEPLOY.md` · since 2026-07-24
- [ ] Confirm the `members` hash value encoding at the office — JSON object is an OFFICE-VERIFY assumption in `docs/datatables/members.txt`. If wrong, `/api/me` still works (names degrade to empno) and the warning log `member document for <empno> is not the expected JSON object` names it · since 2026-07-31
- [ ] Confirm the cloud host forwards the `LASTUSER` cookie to `/project/workSpace` — identity now depends on it alone; a host that strips it leaves everyone unidentified (pages load, `/api/*` 401s) · since 2026-07-31
- [x] ~~Register hostnames with SSO~~ — moot: identity is the `LASTUSER` cookie, no SSO callback registration needed (2026-07-31)
- [x] ~~Confirm which `hcputil` SSO spelling the cloud image provides~~ — moot: `hcputil` dependency removed entirely (2026-07-31)

## Backlog / soon

- [ ] Close the OFFICE-VERIFY items in `docs/datatables/recipe_idp.txt` — `img_meas2` dtype; what `img_*` in `idp_image_info` actually hold; whether `Parameter` matches exactly across the two parsed tables (a space/case difference makes the MP table render silently empty) · office-only · since 2026-07-27
- [ ] **Wafer map draws TWO disagreeing die grids** (confirmed on screen 2026-07-24, still present 2026-07-29). `waferAxis.ts:62` sets `cfg.interval = pitchMm`, so ECharts steps split-lines from the axis ORIGIN and can't be phase-shifted — they sit on the UNSHIFTED grid while `buildDieGridSegments` draws shifted boundaries, ~17–20 px apart at 1400 px. Labels stay correct. Needs a UX call: kill the axis splitLine when the overlay is on, or stop treating the axis as a die grid · since 2026-07-24
- [ ] Spec 2 — skewvoir paired-scatter field-location pairing: spec written (`docs/superpowers/specs/2026-07-24-skewvoir-field-location-pairing-design.md`), no plan yet · since 2026-07-24
- [ ] storage↔sem_list hidden coupling: `storage/providers/office.py` imports `sem_list.data.get_sem_list()` at three sites (L53/L110/L240) — STORAGE=office + SEM_LIST=mock silently empties rows. Now reachable at home, since both adapters exist locally. Add a provider-mismatch guard · since 2026-07-21
- [ ] Add `ProxyFix` — behind aipp01 ingress `request.remote_addr` is the proxy, so `_logging/activity.py` logs the proxy not the user. Confirmed absent 2026-07-29 · since 2026-07-24
- [ ] Rate limiter is `memory://` with `processes = 4` (`wsgi.ini`) — per-worker counters, effective limit ~4×; wants a Redis `storage_uri` (`back_dev_home/__init__.py:31`) · since 2026-07-24
- [ ] `SKEWNONO_SECRET_KEY` is absent from `back_dev_home/.env` entirely (checked 2026-07-29 — the old note claiming a `dev-only-not-for-prod` placeholder was wrong). Decide the default-vs-required behaviour, then set distinct test and prod values · since 2026-07-24
- [ ] Mock realism: `cd_value` is `uniform(10.0, 50.0)` at `back_dev_home/msr_file/providers/mock.py:577` (moved from `data.py`, and wider than the [15,45] the old note recorded), which flags most sites as outliers; tighten the spread · since 2026-07-15
- [ ] Wire next office features (16 pending mock-stub per STATUS.md; skew fab_name rename pending). Six adapters exist locally today: sem_list, health, storage, recipe_tat, recipe_search, lateral_recipe · since 2026-07-21
- [ ] Settle whether main's hardware office-adapter tests lost coverage — the deleted-branch rewrite renamed every test (`test_mdc_office`: 24 on main vs 13 on `test/hardware-office-adapter-coverage`, zero name overlap; fdc/sharpness have 18/22 branch-only names). Either confirm main covers the same ground or port the gaps, then drop the branch · since 2026-07-29
- [ ] B2 — Peer 비교 (`vs PEERS` card): auto same-recipe baseline + delta (spec §8.1) · since 2026-07-15
- [ ] B3 — FDC inline: connect orphan `Fdc*` components, CD↔`dynamic_fdc` on shared sequence axis (spec §12) · since 2026-07-15
- [ ] B3.2 — 하드웨어 timestamp popup: `useHardwareApi` eqp_id + start~end window → anchored slideover (spec §12) · since 2026-07-15
- [ ] §10.3 adaptive views (single-MSR variants of 위치/Time-Series/상관 panels) · since 2026-07-15
- [ ] B1 minors: keyboard/ARIA on clickable rows; stale comment `WaferMap.vue:26` · since 2026-07-15
- [ ] Optional: skill-creator eval on `/leave-office`+`/back-to-office` · since 2026-06-30

## Closed 2026-07-29

- **recipe_search office adapter IDP wiring** — `get_recipe_open_data` is a full implementation (`office_example.py:1319`), no longer the `TODO(office)` mock re-export. Redis-first locate (`_locate_via_redis`, `rcp_loc`/`tools_in_rcp`) with OpenSearch fallback + retry, merged to main.
- **Raw-recipe folder parsing** — `recipe_search/rawfiles.py` + `test_rawfiles.py`; slot planning and batched FTP live here.
- **`align_images` + `amp_info` source** — resolved and then *retired* from `contracts.py`/`mock.py`/`office_example.py`; align readers with P.No→optics mapping added, `test_align_readers.py` (16 regression + mock-parity tests).
- **Recipe-open modal close buttons** — `AlignPopup.vue` and `ImageLightbox.vue` were overriding `Modal.slots` and dropping the ✕; fixed and browser-verified across all three dismiss paths (`3c6aae1`).
- **Branch/worktree cleanup** — 5 pushed branches deleted locally after verifying `0 ahead / 0 behind` upstream; both sibling worktree directories confirmed to be build-artifact husks.
- Note: `.scratch/recipe-idp-redis-locate/plan.md` still shows unticked boxes. That is stale bookkeeping — the symbols and tests are all on main.

## Context to remember

- **The recipe-open FTP chain:** `meas_hist_{cdsem,hvsem}` carries `eqp_ip`, so no sem_list join is needed — the measurement row already names the tool that ran the recipe. `idp_name`/`idw_name` are *paths* (`/Recipe/ADI/X.idp`); the FTP tree wants the **stem**. Path is `/HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}.idp`, sibling of msr_image's `images/{msr}`, same creds (`SKEWNONO_TOOL_FTP_*`) and same Windows-proxy/direct split.
- **Column names are the office contract.** `office_utils` exists only at the office, so a drifted name passes at home and fails there. `img_meas2` in `wafer_mp_info` is **P_No's value, not a filename** — the mock faked `IMG_MEAS_0001.jpg` for months and taught the frontend to expect a string office never produces. Don't infer a column's content from its name here.
- **This session's loop:** Claude Code runs against the home Mac mini; the user is physically at the office and pulls + runs there. So: write → commit → push → they `git pull` and run → report stdout. Note the office PC is Windows (`.venv\Scripts\python`).
- **Office data cannot be reached from the Mac mini** (verified 2026-07-24): company Redis `10.156.133.126:10121` times out, and `.env` has no `OPENSEARCH_*` keys. Any office-verify job is genuinely office-only.
- **The test suite assumes you have NO office adapters.** `office.py` is gitignored, so tests asserting the "unconnected adapter" state only hold on a checkout without them (`tests/_office_state.py`). An adapter appearing + a Redis/OpenSearch timeout means the test needs a guard, not a fix.
- **Deploy's central gotcha:** `is_cloud()` is path-based (`/project/workSpace` prefix) and `spa_dir()` walks `parents[2]`. Unpack anywhere else → no SSO, no SPA mount, mock data, while still serving HTTP 200. Bundle depth is load-bearing.
- The SPA calls `/api` relative and Flask serves it same-origin, so **one bundle works on both the aipp01 test URL and `skewnono.skhynix.com`**. No CORS origins; no `SESSION_COOKIE_SECURE`/HSTS (both are http-only).
- Error taxonomy: bare `LookupError` → JSON 502 (upstream data), bare `RuntimeError` → 503 (unconfigured); subclasses stay 500.
- Two sessions are live on `main` and interleave commits. Re-read hunks before editing, stage explicit paths only, never `git add -A` / `commit -a` / `stash`.
- Skewvoir seams unchanged: `overviewSites()` single analytics source; `focusedSequence` shared selection; `Fdc*` cluster is staged WIP — don't prune.
- **A branch reading "not merged" often means "rebased, already landed."** `git branch --merged` walks ancestry; use `git cherry main <branch>` (patch-id) and then compare blobs before assuming a branch holds unlanded work. All 10 branches present on 2026-07-29 were superseded snapshots, not pending jobs.
