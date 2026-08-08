# Open Jobs

_Updated: 2026-08-07 · branch: main_

## In progress

- [ ] **Chat RAG office adapter** — home side is done and merged (`60cbc7c`). **At the office:** `cp knowledge/providers/office_example.py knowledge/providers/office.py` → implement 4 seams (`_config` / `_build_request` / `_execute` / `_rerank`) + `_translate_error` → fill the 4 `OFFICE-TODO` skip stubs in `test_knowledge_office.py` (the `_rerank` one proves one score per hit **in hits order**) → set `SKEWNONO_CHAT_KNOWLEDGE_SOURCES=manual` → measure the 3-hop latency (embed→search→rerank, ×tool calls) and re-check `SKEWNONO_CHAT_AGENT_TIMEOUT`. Contract: `back_dev_home/chat/MIGRATION.md` + spec `docs/superpowers/specs/2026-08-07-chat-rag-manuals-design.md` · since 2026-08-07
- [ ] **Manual RAG ingestion (office parsing work)** — index must satisfy the 9-item contract in the spec §5 / `docs/datatables/chat_rag_contract.txt`. The irreversible ones: Nori on Korean text fields, access fields indexed *filterable* even though unused today, deterministic `source_id`, bare `figure_id` matching `^[A-Za-z0-9_-]{1,128}$`, `locator` as `manual:<doc_id>#page=<page>`. All fail silently, not loudly · since 2026-08-07
- [ ] Office verify recipe_tat + health — prepped at home 2026-07-24, only the on-site run is left. `cp office_example.py office.py` done; contract fixtures at a clean 28/28 baseline (`c7ce87a`). **At the office:** `detect_site()` should print `office` → start Flask → `.venv/bin/python scripts/check_contract.py` (any FAIL is now a genuine office-side shape difference) → eyeball recipe 현황 (`DEFAULT_LIMIT = 0`, uncapped — watch first-load latency) → bump STATUS.md · since 2026-07-21
- [ ] Recipe-open IDP chain — locate + FTP + .idp parse **proven live 2026-08-03** (tuple-wrap recovery `5be8101`; images and 측정 위치 render on the real app). What's left: **the three setting readers come back empty at the office** (AMP / Sequence·AF·PR / 빔 조건 all blank — the adapter degrades every settings failure to 파일 없음 silently). Next: get one of three office artifacts — param-detail response JSON (null blocks vs `rows: []`), server log grep `recipe_search:` (the log line names the case), or `scripts/probe_recipe_ftp` Stage D (prints each reader's actual return type). Then extend `_read_block`/`_to_rows` the same way `_normalize_frames` was · since 2026-07-29

## Blocked

- [ ] **`safety_level` in the manual `element_type` scheme** — blocked on: RAG owner confirming whether the manuals actually carry ANSI Z535.6 headwords (DANGER/WARNING/CAUTION/NOTICE). If they do, preserve the source word verbatim; if not, drop the axis rather than invent a distinction. Update spec §5.1 + `chat_rag_contract.txt` together · since 2026-08-07
- [ ] Confirm the cloud host forwards the `LASTUSER` cookie to `/project/workSpace` — a host that strips it fails silently: app works, every request logged `anonymous`. Check the activity log for a lone `anonymous` user · since 2026-07-31
- [ ] **How home stands in for `office_utils.read_idp_info`** — real parser output still unseen, but 2026-08-03 narrowed it: cloud's `combined_idp_info` returns a **tuple of two 3-key dicts** (values unknown). Probe command + update slot is `recipe_idp.txt` §2차 관측. Blocked on an office run of that probe · since 2026-07-27

## Backlog / soon

- [ ] `element_type` axis split (`block_type` / `intent` / `safety_level` / `is_generated` / `alarm_codes`) — spec §5.1 is a 권고, deliberately not confirmed. `is_generated` first: it's the only one that cannot be recovered retroactively · since 2026-08-07
- [ ] Chat agent-loop eyeball at home via OpenRouter — plan's manual verification step, never run. `SKEWNONO_CHAT_RUNTIME=agent` + mock knowledge + a `supports_tools` model; confirm citations and tool traces render · since 2026-08-07
- [ ] Chat review leftovers (deferred minors, ledger deleted so recorded here): duplicate `test_available_sources_does_not_import_the_office_module`; mid-file import `test_knowledge.py`; 2-row tie-stability test (3 rows in non-alphabetical order closes it); `get_knowledge_candidate_pool()` bare `ValueError` + call site outside `_search`'s try; `agent.py` `if source in _TOOL_BUILDERS` silent drop; `numpy.float32` rejected by the score `isinstance` check · since 2026-08-07
- [ ] 4 pre-existing ruff errors outside chat: `_auth/directory.py` B905, `_scheduler/tests/test_registry.py` B007, `device_statistics/providers/office_example.py` F401, +1 · since 2026-08-07
- [ ] `SKEWNONO_SECRET_KEY` — put a real value in the office/cloud `.env` before the next deploy (`a6613a6` refuses to boot without it; preflight checks it, `d5730e9`) · since 2026-07-24
- [ ] **Sync `identity_source` into upstream `flask_modules`** — local `ops_index_mgmt/skewnono_logging.py` is AHEAD (`7f42541`); an office-side template refresh would silently drop the field (index is `dynamic: "false"`). Office act: add the same keyword line upstream · office-only · since 2026-07-31
- [ ] **What fraction of declarations actually verify** — read `identity_source` off the activity log after the first real cloud usage; if most probe `absent`, the 미검증 badge stops distinguishing anyone · office-only · since 2026-07-31
- [ ] Close the OFFICE-VERIFY items in `docs/datatables/recipe_idp.txt` — now also: the tuple's actual contents (§2차 관측 probe), whether this parser version's readers really accept **bytes** (confirmed 07-29 on the office PC, not on cloud — version skew is proven for `read_idp_info`), plus the old trio: `img_meas2` dtype; what `img_*` hold; `Parameter` exact-match across tables · office-only · since 2026-07-27
- [ ] Spec 2 — skewvoir paired-scatter field-location pairing: spec written (`docs/superpowers/specs/2026-07-24-skewvoir-field-location-pairing-design.md`), no plan yet · since 2026-07-24
- [ ] storage↔sem_list hidden coupling: `ebeam/hitachi/storage/providers/office_example.py` imports `sem_list.data.get_sem_list()` (L53/L110/L240). STORAGE=office + SEM_LIST=mock silently empties rows. Add a provider-mismatch guard · since 2026-07-21
- [ ] Mock realism — one row left: the nameless-parameter dummy at `msr_file/providers/mock.py:577` (`uniform(10.0, 50.0)`), cosmetic. Fix only if it shows up in a view · since 2026-07-15
- [ ] Wire next office features — per `docs/office-migration/STATUS.md` (recount 07-31): 2 office-verified, 10 구현완료 awaiting an office run, 2 partial (`recipe_search`, `msr_file`), **5 bare mock**: `device_statistics`, `pm_planning`, `hardware`, `skew`, `afm`. Stale comment: `skew/tests/test_contract.py:113` still says `fac_id` · since 2026-07-21
- [ ] Settle whether main's hardware office-adapter tests lost coverage — evidence preserved as tag `archive/hardware-office-adapter-coverage` (`3966156`); diff against it, port gaps, only then delete the tag · since 2026-07-29
- [ ] B2 — Peer 비교 (`vs PEERS` card): auto same-recipe baseline + delta (spec §8.1) · since 2026-07-15
- [ ] B3 — FDC inline: connect orphan `Fdc*` components, CD↔`dynamic_fdc` on shared sequence axis (spec §12) · since 2026-07-15
- [ ] B3.2 — 하드웨어 timestamp popup: `useHardwareApi` eqp_id + start~end window → anchored slideover (spec §12) · since 2026-07-15
- [ ] §10.3 adaptive views (single-MSR variants of 위치/Time-Series/상관 panels) · since 2026-07-15
- [ ] B1 minors: keyboard/ARIA on clickable rows · since 2026-07-15
- [ ] Optional: skill-creator eval on `/leave-office`+`/back-to-office` · since 2026-06-30

## Closed 2026-08-07

- **Chat RAG manuals connection shipped** (`38bda12`..`60cbc7c`, merged + pushed). `available_sources()` drives tool exposure; `_rerank()` seam added with ordering + the 5-row cap owned by the tracked contract half; docs corrected across `chat_rag_contract.txt`, `MIGRATION.md`, `mock.py`. Decisions settled: manuals only, same OpenSearch (no separate RAG server), 2-leg hybrid Nori BM25 ⊕ BGE-M3 dense, `bge-reranker-v2-m3`, **C2** (office.py calls the in-house APIs directly — the ML Commons connector allowlist has no in-house host).

## Context to remember

- **`importorskip` hides broken office tests.** `test_knowledge_office.py` skips at home, so edits to the tracked `office_example.py` contract half can break it invisibly — 4 tests were broken while home stayed green. Run it for real by aliasing `office_example` into `sys.modules` as `...providers.office`. Same trap applies to every `test_*_office.py`.
- **`_runtime/data_provider.py` must import chat config lazily** — a module-level import creates a genuine cycle (`back_dev_home/__init__` → `_runtime.data_provider` → chat → back). Proven 2026-08-07, not cargo cult.
- **Settings blocks degrade silently by design.** `_read_block`/`_to_rows` render absent/unparseable/unrecognised as 파일 없음 or empty rows — an empty AMP/Sequence tab at the office is a server-log question (`grep recipe_search:`), never a frontend bug. Images coming from the *same* param-detail response proves the endpoint/FTP/import are fine.
- **Parser version skew is proven.** What was confirmed on the office PC (07-27/30) does not bind the cloud's `office_utils`. Any "confirmed" claim about a parser is per-environment.
- **`ms=-1` in a request log means the identity gate answered, not a route.** Read `_auth/middleware.py` before suspecting a route or the SPA mount.
- **Never answer a page request from the identity gate** — any response there blanks the SPA with no console error; self-id gating lives in Nuxt middleware.
- **Home `.env` sets `REDIS_HOST`** (unreachable office host) — gate on `get_mode() != "office"`, never `is_cloud()`.
- A bundle outside `/project/workSpace` makes `is_cloud()` False → home identity (`local-dev` admin), no SPA mount, mock data, all while serving 200s.
- **Column names are the office contract.** `office_utils` exists only at the office; a drifted name passes at home. `img_meas2` in `wafer_mp_info` is P_No's value, not a filename.
- **Recipe-open FTP chain:** `meas_hist_*` carries `eqp_ip` (no sem_list join); `idp_name`/`idw_name` are paths, FTP wants the stem; `/HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}.idp`, msr_image creds.
- **This session's loop:** Claude Code runs on the home Mac mini; the user pulls + runs at the office (Windows, `.venv\Scripts\python`). Office data unreachable from home (verified 07-24).
- **The test suite assumes NO office adapters present**; worktrees legitimately differ in skip counts.
- Error taxonomy: bare `LookupError` → 502, bare `RuntimeError` → 503; subclasses stay 500.
- **Two sessions interleave on `main`, and main gets rebased.** Explicit-path staging only; check `git merge-base --is-ancestor` before merging a worktree branch.
- Skewvoir seams unchanged: `overviewSites()`, `focusedSequence`, `Fdc*` staged WIP — don't prune.
