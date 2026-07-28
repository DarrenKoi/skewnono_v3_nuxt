---
type: Integration Guide
title: Integration Points and Office Migration Boundaries
description: Live and planned SKEWNONO boundaries for Nuxt proxying, identity, OpenSearch, MinIO, FTP ingestion, LLM completion, Redis-backed SEM-list data, and provider-by-provider office migration.
resource: docs/back-end/office-data-adapters.md
tags: [integrations, opensearch, minio, ftp, redis, sso, llm]
---

# Integration points and office migration boundaries

The [runtime architecture](../architecture/overview.md) deliberately keeps external systems behind provider modules. A library's presence in the repository does not prove that a product feature currently uses it.

## Nuxt-to-Flask API boundary

`front-dev-home/nuxt.config.ts` exposes `runtimeConfig.public.apiBase` (default `/api`) and proxies that prefix to `NUXT_API_TARGET` during development. Production Flask serves the SPA and API on one origin. Frontend code should not hardcode backend hosts or branch by deployment phase.

The current direct CORS allowlist is `http://localhost:3100`, while Nuxt defaults to `3000`. Normal development avoids this mismatch through the same-origin proxy; direct browser-to-Flask calls from port 3000 would need explicit configuration correction.

## Identity and access

Local identity is development-oriented; cloud identity lazily imports internal SSO. API clients may use `Authorization: Bearer skn_...`; token creation/revocation still requires a human session. Admin identity can be configured by `SKEWNONO_ADMIN_USERS`.

Do not copy credential values into code or wiki pages. Production must set `SKEWNONO_SECRET_KEY`; the source fallback is explicitly development-only. Path-based cloud detection in `_runtime/env.py` decides whether SSO and SPA serving activate, making deployment location part of the current integration contract.

## OpenSearch

`ops_store/` is a generic OpenSearch wrapper for search, document, and index operations. Product office providers own domain queries and normalization while reusing this transport layer. Canonical request logs are shipped asynchronously to the alias selected by `SKEWNONO_LOG_ENV`: `skewnono_logging_local` for `local` or `skewnono_logging` for `production`. The activity and admin-log office readers use the same selector, while their mock providers remain deterministic and network-free. Delivery is best-effort and observable through `/api/health/logging`; reader failures remain visible as endpoint-specific 503 responses instead of empty analytics.

`ops_index_mgmt/` contains one-shot templates, aliases, ISM policies, rollover setup, and reindex scripts. It is operational provisioning, not request-time application code. `ops_index_mgmt/skewnono_logging.py` provisions both explicit-mapping rollover families at 20 GB or seven days, with 30-day local and 365-day production retention. Measurement-history aliases now back Skewvoir search, complete distinct-recipe fallback, and recipe-open location lookup, although stable joins and mappings for every MSR artifact use remain unresolved.

## Measurement-image delivery and cache

Measurement images have a dedicated `back_dev_home/msr_image/` feature rather than an endpoint in `msr_file`. `GET /api/msr-images` lists JPEG/TIFF names; `GET /api/msr-image` serves one cacheable response and optionally sends URL-encoded condition text in `X-Msr-Cond`; `POST /api/msr-images` validates locally, returns `202` before the slow FTP listing, and starts a background download-all job; `GET /api/msr-images/<job_id>` polls its snapshot. `msr_file` supplies the authoritative `(eqp_ip, class_name, msr)` tuple from the MSR's parent measurement document; a loaded measurement-history row is only a frontend fallback. The [Skewvoir gallery](../workflows/key-workflows.md#skewvoir-search-and-analysis) consumes these endpoints, reports whole-job and per-file failures, and offers TIFF originals as downloads when the browser cannot render them.

Mock mode uses `DiskImageCache`; office mode chooses `MinioImageCache`, storing content type and condition as object metadata. `create_app()` starts an APScheduler purge at `IMAGE_CACHE_PURGE_HOUR` and removes entries older than `IMAGE_CACHE_TTL_HOURS` (168 hours/seven days by default). An external Airflow sweep is the office safety net for periods when the app is down; it must use the same cache prefix and retention window. The tracked office adapter uses `ftp_handler` directly: Windows selects its HTTP-proxy transport, while Linux/cloud selects direct FTP under `/HITACHI/DEVICE/HD/<class>/images/<msr>`. Missing files map to 404 and transport failures to 503; condition sidecars are best-effort.

This cache is independent of processed MSR pickles. `dict_pkl` is read-only source data retained by an external 61-day partition policy; the application neither regenerates nor deletes it, and `raw_msr` is outside that purge. If a processed pickle is removed, the upstream post-processing pipeline must recreate it (`back_dev_home/msr_file/MIGRATION.md`, `docs/datatables/msr_file_pickle.txt`).

The boundary now validates IPv4 plus optional `SKEWNONO_TOOL_SUBNETS` and rejects unsafe class/MSR/name segments before source access. Job TTL and maximum-active settings are enforced. Office plus `REDIS_HOST` selects shared `RedisJobRegistry`; other runs use process memory, so Redis is required for reliable polling behind multi-worker uWSGI. Use a cache prefix distinct from measurement originals because application-level purge is the only available office lifecycle mechanism. Office rollout is still incomplete until the tracked adapter is copied to ignored `providers/office.py` and representative FTP/cache behavior passes on-site verification.

## AFM office source

AFM sourcing remains a separate unresolved decision; do not infer its storage path from the measurement-image cache. Every function in `back_dev_home/afm/providers/office_example.py` is still an explicit `NotImplementedError`, so the integrated [AFM workflow](../workflows/key-workflows.md#afm-detail-and-comparison) has no connected office registry, file/detail/profile, artifact, activity, or analytics source.

## Live alarm writer and reader

The [live alarm workflow](../workflows/key-workflows.md#live-alarm-board) uses Redis as a bounded broadcast board, not a durable event store. A portable writer intended for the existing scheduler polls configured fab alarm APIs, normalizes ALID `9006` and `9100`, and updates per-tool/fab event ZSET and heartbeat metadata every 15 seconds. Flask's office reader uses Redis server time, returns only the last 600 seconds, tolerates malformed members, and reports `live`, `stale`, or `not_configured`.

There are two machine-local swap surfaces: `writer/office.py` configures source addresses and scheduler-side Redis, while `providers/office.py` lets Flask read the board. Neither tracked example is itself the active local file, and the writer is not started by this Flask app. Follow [operations](../operations/runbook.md#live-alarm-office-deployment) so writer deployment precedes reader activation.

## FTP ingestion

`ftp_handler/` is an ingestion library, not a Flask Blueprint. It supports direct and HTTP-proxied fleet downloads, listing/size passes, background jobs, and injected archive/parse/index callbacks. The package intentionally does not import MinIO or OpenSearch; callers provide those side effects.

Recipe open now [uses this boundary from the recipe workflow](../workflows/key-workflows.md#recipe-and-hardware-operations): the office adapter locates the newest valid recipe path in `meas_hist_{cdsem,hvsem}`, applies the tool-IP/subnet guard, downloads the `.idp` from tool FTP, parses it with office-only `office_utils.read_idp_info`, and normalizes the stable detail contract. The parsed `idp_image_info` contract treats `Addressing`, `Mother_Para`, and `dnumber_removed` as booleans; `Mother_Para=true` marks the row's own parameter as a mother, and `dnumber_removed=true` marks data suppressed from legacy delivery. `align_images` and `amp_info` remain synthetic because the parser has no source for them, and office compare remains mock-backed; only Redis-origin selections may open or compare, so OpenSearch fallback entries cannot enter those inconsistent paths.

## LLM gateway

`back_dev_home/chat/llm.py` sends stateless OpenAI-compatible chat-completion requests. Endpoint, API key, timeout, and model list are environment-driven through the chat config module. Before `httpx.post`, `chat/guard.py` applies an office-only egress blocklist: known public gateways and their subdomains are rejected, while mock mode is unchanged. `CHAT_BLOCKED_HOSTS` can add blocked hosts but cannot remove defaults. Office deployments must point `CHAT_BASE_URL` at an approved internal gateway; a blocked send returns `403` with error code `egress_blocked`, preserves the user turn, and appends no assistant reply.

This is a known-public-host blocklist, not a general internal-host allowlist. The [chat workflow](../workflows/key-workflows.md#chat) has active thread persistence and completion calls, but repository RAG/tool-calling documents describe future work only. Office chat persistence is also unresolved: home mode uses SQLite, while an OpenSearch-backed provider is planned but not connected. Before production, define thread privacy, retention, access, and deletion behavior alongside the datastore.

## Provider readiness

The active mock providers support home development. Tracked `providers/office_example.py` files are the reviewable implementation source; office environments copy them to ignored `providers/office.py` modules for source-specific verification without exposing local details. `docs/office-migration/STATUS.md` records whether real office data passed contract and screen verification; it does not drive runtime selection. SEM list and storage are recorded as office-verified, while health, measurement history, Recipe TAT, fail issue, lateral recipe, recipe search, and MSR file have implemented or partial adapters still awaiting full verification.

When no feature override is set, the [runtime architecture](../architecture/overview.md#provider-seam-and-contracts) selects office only when the process is in office mode and that machine has a direct `providers/office.py` for the feature. `SKEWNONO_DATA_PROVIDER=office` selects mode but does not force missing adapters; `SKEWNONO_DATA_PROVIDER=mock` returns all non-overridden features to mock. A feature-specific mock override isolates a broken adapter:

```bash
SKEWNONO_STORAGE_PROVIDER=mock python index.py
```

An explicit feature `=office` is a promise of real data: startup and direct provider resolution reject it when `office.py` is absent and include the required copy command. After copying an adapter, restart because the registry scan is process-cached, then confirm the actual resolution through the boot table or `GET /api/health/providers`.

### SEM-list Redis adapter

`back_dev_home/sem_list/providers/office_example.py` reads parquet-serialized DataFrames from `v3_df_sem_avail` and `v3_df_sem_version` using the shared `_runtime/office_redis.py` client. It de-duplicates the version table by `eqp_ip`, left-merges it onto the fleet so rows are not dropped or multiplied, then normalizes the result to `SemListRow`. The public `version` field is a free-form string such as `"1A"`; an unmatched fleet row returns `version: ""`. Parquet is the confirmed format (`pyarrow`); JSON and pickle remain compatibility fallbacks, and malformed data raises a diagnosable upstream-data failure.

Storage shares that Redis plumbing. Its adapter reads per-tool storage DataFrames plus the combined `v3_hitachi_sem_ppid_not_avail` hash, then joins unavailable IPs through SEM list to recover equipment identity and split CD-SEM from HV-SEM. Storage therefore [depends on the SEM-list integration](#sem-list-redis-adapter), and both are office-verified in the migration ledger.

These adapters preserve the [provider seam](../architecture/overview.md#provider-seam-and-contracts): routes and frontend consumers do not know the Redis format. Copy the tracked examples to ignored `office.py` files, configure Redis without committing credentials, restart the process, confirm the provider row, and use the focused checks in [testing guidance](../testing/guidance.md#feature-contract-gates).

### Recipe TAT office analytics

`back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py` performs server-side ranking, summary, trend, and anchor aggregations over `meas_hist_cdsem` and `meas_hist_hvsem`. Because measurement documents do not carry `lot_cd`, it uses the `ebeam_tas_lot_hist` OpenSearch index as the `lot_id` bridge, then enriches active devices from Redis `device_desc` and `r3_device_grp` catalogs. Catalog and lot mappings use a 15-minute cache that serves the last good value after refresh failures; the first load still fails visibly. A ranking `limit=0` means all rows in range, implemented with paginated composite aggregations rather than an approximate fixed-size terms result.

The adapter is implemented, but the migration ledger has not yet recorded office-mode contract and screen verification. Treat it as a verification target, not as fully rolled out.

### Hardware OpenSearch adapters

Hardware's nested office adapters now pin several source contracts. FDC queries `network_fdc_cdsem` by exact `eqp_id.keyword`; its offset-less `timestamp` is interpreted as KST wall clock, and the exact discriminator is `TemperatureEChuck`. The query deliberately does not filter by fab so stale UI fab state cannot suppress a valid equipment result. `scripts/diagnose_fdc_standalone.py` reproduces field, timestamp, and clause diagnosis without repository imports for constrained office hosts.

BSM's implemented adapter queries `beam_shape_cdsem` and normalizes nested 16-point `Reso EB Focus` profiles plus scalar `Reso EB Focus Range`; malformed profiles are dropped and a result exactly at the 10,000-document cap fails rather than presenting a silently truncated trend. SCE's implemented adapter combines the current Redis `sce_info` snapshot with bidaily MinIO archives and treats unsupported fabs as valid empty states. MDC and Reso Center now have reconstructed tracked adapters and contract suites; Reso Center normalizes its flat 13-field source and derives `ResoDelta = ResoIScenter - BestReso`. Existing office-local copies may contain unique code, so merge these examples deliberately rather than overwriting them. These tabs remain CD-SEM-only, and tracked implementation does not equal local activation or office verification.

BM/PM combines `fab_inform_notes` past events (`down_dt`, 180-day lookback) with `tool_maintenance_plan` future work (`tool_start_tm`, 90-day horizon). Shared row logic classifies BM/PM by source text, preserves unclassified rows without chart overlays, formats chart timestamps as `YYYY-MM-DD HH:MM`, and keeps engineer-note fields available for tooltips. These mappings [surface through the hardware workflow](../workflows/key-workflows.md#recipe-and-hardware-operations), not through new public endpoints.

Lateral recipe now queries `cdsem_idp_ver`/`hvsem_idp_ver` and uses `meas_hist_cdsem`/`meas_hist_hvsem` as a 30-day readiness floor. This resolves the aliases and exact-keyword joins for that workflow, but does not establish measurement-history mappings for every Skewvoir or artifact use case.

Create a local adapter before explicitly enabling its override:

```bash
cp back_dev_home/<feature>/providers/office_example.py \
  back_dev_home/<feature>/providers/office.py
```

Never commit the resulting `office.py`; update the tracked example at home when contracts change. Hardware is a deliberate nested exception: the feature-level `hardware/providers/office.py` participates in global resolution, while `hardware/providers/<tab>/office.py` is private to the hardware dispatcher. A missing tab adapter falls back to that tab's mock and logs the fallback; an existing tab adapter that fails to import does not silently fall back.

A provider is ready only when it:

1. queries a confirmed production source;
2. normalizes source fields into the existing contract;
3. passes its active-provider contract gate;
4. preserves route filtering, pagination, error, and empty-state behavior;
5. has operational health/failure semantics;
6. is exercised through the relevant [key workflow](../workflows/key-workflows.md), not only a transport unit test.

## Migration questions

- What are the authoritative joins for Skewvoir `meas_hist` and `msr_file` beyond the aliases now confirmed for lateral-recipe readiness?
- Where do stable site-layout, recipe-revision, coordinate-transform, and sequence fields originate?
- When will the implemented measurement-image FTP/gallery path complete on-site activation and representative verification, and what authoritative office sources will serve AFM registry, detail/profile bodies, images/artifacts, activity, and analytics?
- What store backs editable measurement-rule versions and rollback?
- Should Redis or another shared system replace process-local access, token, and limiter state in production? Office activity is now derived from the shared canonical OpenSearch log stream.

Track startup and provider failures through the [operations runbook](../operations/runbook.md), and verify adapters using [testing guidance](../testing/guidance.md).
