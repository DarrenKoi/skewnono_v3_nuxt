# Open Jobs

_Updated: 2026-07-27 · branch: main_

## In progress

- [ ] **Wire recipe_search office adapter to the real IDP source** — source is now known and the .idp downloads. Next: implement `get_recipe_open_data` in `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py:44` (currently a `TODO(office)` re-export of mock): meas_hist_* doc → `eqp_ip`+`class_name`+`idw_name`+`idp_name` → FTP RETR → `office_utils.read_idp_info.combined_idp_info()` → `RecipeDetailResponse`. Import `office_utils` *inside* the function, not at module scope · since 2026-07-27
- [ ] Office verify recipe_tat + health — prepped at home 2026-07-24, only the on-site run is left. `cp office_example.py office.py` done (6 adapters); contract fixtures at a clean 28/28 baseline (`c7ce87a`). **At the office:** `detect_site()` should print `office` → start Flask → `.venv/bin/python scripts/check_contract.py` (any FAIL is now a genuine office-side shape difference) → eyeball recipe 현황 (`DEFAULT_LIMIT = 0`, uncapped — watch first-load latency) → bump STATUS.md · since 2026-07-21

## Blocked

- [ ] **How home stands in for `office_utils.read_idp_info`** — I offered three routes (paste real `df.dtypes`+`head(3)` output / vendor the parser like ftp_handler / pure mock from column lists alone); user wanted to clarify the question and then signed off. Blocked on: that decision. It gates whether the adapter mapping can be verified at home or only at the office · since 2026-07-27
- [ ] First cloud feasibility deploy → `http://skewnono-v3-webapp.aipp01.skhynix.com` — packaging shipped, unblocked on our side. Remaining: pack from the office PC (`npm --prefix front-dev-home run build && .venv/bin/python -m scripts.deploy`), copy to `/project/workSpace/`, follow the bundle's `DEPLOY.md` · since 2026-07-24
- [ ] Register `skewnono-v3-webapp.aipp01.skhynix.com` with SSO as a valid service/callback URL — blocked on infra/SSO team; repeat for `skewnono.skhynix.com` at cutover · since 2026-07-24
- [ ] Confirm which `hcputil` SSO spelling the cloud image provides (`auth` vs `auto`) — not urgent, `_load_sso_class()` tries both (`374432a`); bundled `preflight.py` reports which resolved · since 2026-07-24

## Backlog / soon

- [ ] Parse the `{idp_name}/` raw-recipe folder — probe lists it but downloads nothing; user called parsing it "the next step" · since 2026-07-27
- [ ] Find a source for `align_images` + `amp_info` — absent from the parser's three keys, so still fabricated *at the office*. Candidate: the raw-recipe folder above · since 2026-07-27
- [ ] Close the OFFICE-VERIFY items in `docs/datatables/recipe_idp.txt` — `img_meas2` dtype; what `img_*` in `idp_image_info` actually hold; whether `Parameter` matches exactly across the two parsed tables (a space/case difference makes the MP table render silently empty) · since 2026-07-27
- [ ] Spec 2 — skewvoir paired-scatter field-location pairing: spec written (`docs/superpowers/specs/2026-07-24-skewvoir-field-location-pairing-design.md`), no plan yet · since 2026-07-24
- [ ] **Wafer map draws TWO disagreeing die grids** (confirmed on screen 2026-07-24). `waferAxis.ts` sets `cfg.interval = pitchMm`, so ECharts steps split-lines from the axis ORIGIN and can't be phase-shifted — they sit on the UNSHIFTED grid while `buildDieGridSegments` draws shifted boundaries, ~17–20 px apart at 1400 px. Labels stay correct. Needs a UX call: kill the axis splitLine when the overlay is on, or stop treating the axis as a die grid · since 2026-07-24
- [ ] Set a real `SKEWNONO_SECRET_KEY` in `back_dev_home/.env` (still `dev-only-not-for-prod`); distinct test vs prod · since 2026-07-24
- [ ] Add `ProxyFix` — behind aipp01 ingress `request.remote_addr` is the proxy, so `_logging/activity.py` logs the proxy not the user · since 2026-07-24
- [ ] Rate limiter is `memory://` with `processes = 4` (`wsgi.ini`) — per-worker counters, effective limit ~4×; wants a Redis `storage_uri` · since 2026-07-24
- [ ] storage↔sem_list hidden coupling: `get_ppid_unavailable` joins via `sem_list.data.get_sem_list()` — STORAGE=office + SEM_LIST=mock silently empties rows; add a provider-mismatch guard · since 2026-07-21
- [ ] Wire next office features (16 pending mock-stub per STATUS.md; skew fab_name rename pending) · since 2026-07-21
- [ ] B2 — Peer 비교 (`vs PEERS` card): auto same-recipe baseline + delta (spec §8.1) · since 2026-07-15
- [ ] B3 — FDC inline: connect orphan `Fdc*` components, CD↔`dynamic_fdc` on shared sequence axis (spec §12) · since 2026-07-15
- [ ] B3.2 — 하드웨어 timestamp popup: `useHardwareApi` eqp_id + start~end window → anchored slideover (spec §12) · since 2026-07-15
- [ ] §10.3 adaptive views (single-MSR variants of 위치/Time-Series/상관 panels) · since 2026-07-15
- [ ] B1 minors: keyboard/ARIA on clickable rows; stale comment `WaferMap.vue:26` · since 2026-07-15
- [ ] Mock realism: `cd_value` uniform [15,45] flags ~80% sites; tighten spread (`back_dev_home/msr_file/data.py`) · since 2026-07-15
- [ ] Optional: skill-creator eval on `/leave-office`+`/back-to-office` · since 2026-06-30

## Closed today

- Recipe-open IDP source identified end to end: `scripts/probe_recipe_ftp.py` (`bc53600`) downloads the .idp off tool FTP; schema corrected from the real parser (`f567096`); MP table shows the full column set (`e7ec6d6`). All pushed.

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
