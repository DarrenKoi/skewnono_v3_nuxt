---
type: Integration Guide
title: Integration Points and Office Migration Boundaries
description: Live and planned SKEWNONO boundaries for identity, Nuxt proxying, OpenSearch, Redis, image delivery and TIFF previews, raw-recipe FTP, direct and agentic LLM execution, and office migration.
resource: docs/back-end/office-data-adapters.md
tags: [integrations, opensearch, minio, ftp, redis, sso, llm]
---

# Integration points and office migration boundaries

The [runtime architecture](../architecture/overview.md) deliberately keeps external systems behind provider modules. A library's presence in the repository does not prove that a product feature currently uses it.

## Nuxt-to-Flask API boundary

`front-dev-home/nuxt.config.ts` exposes `runtimeConfig.public.apiBase` (default `/api`) and proxies that prefix to `NUXT_API_TARGET` during development. Production Flask serves the SPA and API on one origin. Frontend code should not hardcode backend hosts or branch by deployment phase.

The current direct CORS allowlist is `http://localhost:3100`, while Nuxt defaults to `3000`. Normal development avoids this mismatch through the same-origin proxy; direct browser-to-Flask calls from port 3000 would need explicit configuration correction.

## Identity and access

Browser identity comes from `LASTUSER` or legacy `LAST_USER`, then a signed 30-day self-declaration; cloud falls back to `anonymous` and home to `local-dev`. `GET /api/me` enriches the effective identity from the Redis `members` hash, but missing rows or directory outages do not deny ordinary access: declarations are accepted as unverified unless a real row proves the entered name mismatches. Nuxt routes anonymous visitors to `/identify`; that gate is UX, while the server enforces that declared and anonymous identities are never admin. API clients may instead use `Authorization: Bearer skn_...`; token creation/revocation still requires a trusted human session. Admin identity can be configured by `SKEWNONO_ADMIN_USERS`.

Do not copy credential values into code or wiki pages. Cloud startup and preflight require a nonblank `SKEWNONO_SECRET_KEY` because declaration verification is carried in the signed session; the source fallback is explicitly development-only. Path-based cloud detection in `_runtime/env.py` decides the fallback identity and SPA serving, making deployment location part of the current integration contract. Operators must separately confirm that the hosting layer forwards `LASTUSER`; no internal SSO Python module is required.

## OpenSearch

`ops_store/` is a generic OpenSearch wrapper for search, document, and index operations. Product office providers own domain queries and normalization while reusing this transport layer. Canonical request logs are shipped asynchronously to the alias selected by `SKEWNONO_LOG_ENV`: `skewnono_logging_local` for `local` or `skewnono_logging` for `production`. The activity and admin-log office readers use the same selector, while their mock providers remain deterministic and network-free. Delivery is best-effort and observable through `/api/health/logging`; reader failures remain visible as endpoint-specific 503 responses instead of empty analytics.

`ops_index_mgmt/` contains one-shot templates, aliases, ISM policies, rollover setup, and reindex scripts. It is operational provisioning, not request-time application code. `ops_index_mgmt/skewnono_logging.py` provisions both explicit-mapping rollover families at 20 GB or seven days, with 30-day local and 365-day production retention. Measurement-history aliases now back Skewvoir search, complete distinct-recipe fallback, and recipe-open location lookup, although stable joins and mappings for every MSR artifact use remain unresolved.

## Measurement-image delivery and cache

Measurement images have a dedicated `back_dev_home/msr_image/` feature rather than an endpoint in `msr_file`. `GET /api/msr-images` lists JPEG/TIFF names and optionally filters `ext=jpg|tif`; `GET /api/msr-image` serves one cacheable response and optionally sends URL-encoded condition text in `X-Msr-Cond`; `POST /api/msr-images` validates locally, returns `202` before the slow FTP listing, and starts a background cache-warming job; `GET /api/msr-images/<job_id>` polls its snapshot. `msr_file` supplies the authoritative `(eqp_ip, class_name, msr)` tuple plus ordered `mp_image_names`; the frontend falls back to legacy `mp_image_name_01`, retains every HV-SEM variant, and uses the first only as the representative image. The [Skewvoir workflow](../workflows/key-workflows.md#skewvoir-search-and-analysis) consumes list/single-image endpoints and supports per-variant or all-variant display. The async job endpoints remain available for other clients, but Gallery no longer exposes a start/poll action.

A TIFF display request adds `preview=1`. After retrieving or caching the untouched original, `preview.py` content-sniffs TIFF bytes and converts the first page to WebP; 16-bit grayscale receives a percentile contrast stretch. Non-TIFF bytes pass through, and conversion failure logs then returns the original rather than failing the request. Explicit original-download links omit `preview=1`. Recipe-search images reuse the same conversion path, so preview semantics are content-driven rather than filename-driven.

Mock mode uses `DiskImageCache`; office mode chooses `MinioImageCache`, storing only original bytes plus content type and condition metadata. The [shared scheduler runtime](../architecture/overview.md#flask-composition) purges entries at `IMAGE_CACHE_PURGE_HOUR`:10 older than `IMAGE_CACHE_TTL_HOURS` (72 hours/three days by default). An external Airflow sweep is the office safety net for app downtime and must use the same cache prefix and retention. The tracked office adapter uses `ftp_handler` directly: Windows selects its HTTP-proxy transport, while Linux/cloud selects direct FTP under `/HITACHI/DEVICE/HD/<class>/images/<msr>`. Missing files map to 404 and transport failures to 503; condition sidecars are best-effort.

This cache is independent of processed MSR pickles. `dict_pkl` is read-only source data retained by an external 61-day partition policy; the application neither regenerates nor deletes it, and `raw_msr` is outside that purge. If a processed pickle is removed, the upstream post-processing pipeline must recreate it (`back_dev_home/msr_file/MIGRATION.md`, `docs/datatables/msr_file_pickle.txt`).

The boundary now validates IPv4 plus optional `SKEWNONO_TOOL_SUBNETS` and rejects unsafe class/MSR/name segments before source access. Job TTL and maximum-active settings are enforced. Office plus `REDIS_HOST` selects shared `RedisJobRegistry`; other runs use process memory, so Redis is required for reliable polling behind multi-worker uWSGI. Use a cache prefix distinct from measurement originals because application-level purge is the only available office lifecycle mechanism. Office rollout is still incomplete until the tracked adapter is copied to ignored `providers/office.py` and representative FTP/cache behavior passes on-site verification.

Cold single-image misses are additionally deduplicated per original cache key by the process-local `msr_image.single_flight` registry: the first request visits FTP and concurrent callers receive that result, including the original `ImageNotFound`/`SourceUnavailable` exception mapping. Failed attempts are removed before waiters wake and are not negative-cached, so later callers may retry; this is exact within one worker and only reduces duplication to the worker count under multi-worker uWSGI. Warm-job admission and polling use a separate client-side policy: only `429` with `too_many_jobs` retries the POST, while an existing job is never re-POSTed; poll failures retry unless the response is the specifically identified `404`/`unknown_job`. Each request receives the remaining `WARM_CEILING_MS` as its timeout, and retry backoff replaces—not follows—the normal poll interval, making the ceiling include unanswered requests and sleep time. These rules prevent a refused or transiently failed warm path from releasing the gallery into an unbudgeted cold-fetch burst.

## AFM office source

AFM sourcing remains a separate unresolved decision; do not infer its storage path from the measurement-image cache. Every function in `back_dev_home/afm/providers/office_example.py` is still an explicit `NotImplementedError`, so the integrated [AFM workflow](../workflows/key-workflows.md#afm-detail-and-comparison) has no connected office registry, file/detail/profile, artifact, activity, or analytics source.

## Live alarm cached pull

The [live alarm workflow](../workflows/key-workflows.md#live-alarm-board) uses Redis as a short-lived demand cache and bounded 20-minute board, not a durable event store. The single office swap surface, `providers/office.py`, calls `office_utils.live_alarm.get_ebeam_metrology_alarms(fac_id)` only when a request finds that facility's 20-second cache stale. A Redis lock prevents concurrent refreshes; failures do not advance `fetched_at` and leave the lock TTL to supply backoff. The office call must enforce its own timeout shorter than that TTL.

Current Hitachi normalization recognizes ALID `9006` as Align and `9007`/`9035` as Meas. Selected FABs resolve through SEM-list to distinct facilities, so sibling FABs sharing a facility cause one source call. Board assembly stamps equipment with current roster-derived `fab_name`; unknown equipment increments `unmatched_count`. Multi-fac freshness is worst-of, and partially unconfigured selections return configured data plus `not_configured_fabs`. Follow [operations](../operations/runbook.md#live-alarm-office-deployment); no external writer or scheduler deployment is required.

## FTP ingestion

`ftp_handler/` is an ingestion library, not a Flask Blueprint. It supports direct and HTTP-proxied fleet downloads, listing/size passes, background jobs, and injected archive/parse/index callbacks. The package intentionally does not import MinIO or OpenSearch; callers provide those side effects.

Recipe open now [uses this boundary from the recipe workflow](../workflows/key-workflows.md#recipe-and-hardware-operations): the office adapter resolves `.idp` location Redis-first from the recipe registry, falls back through eligible measured tools, applies the tool-IP/subnet guard, downloads from tool FTP, parses with office-only `office_utils.read_idp_info`, and normalizes the stable detail contract. The parsed `idp_image_info` contract treats `Addressing`, `Mother_Para`, and `dnumber_removed` as booleans; `Mother_Para=true` marks the row's own parameter as a mother, and `dnumber_removed=true` marks data suppressed from legacy delivery.

The `.idp` locator also addresses its adjacent raw-recipe directory. Bounded `POST .../param-detail` reads AMP (`PRMS`), translated addressing AF/PR (`PRMP` to `ENMP`), image slots, and hidden image-sidecar `cond.txt`; `GET .../align-detail` reads `IMAP`/`ENAP` pairs, where points 1 and 2 identify OM and SEM optics; and `GET .../recipe-image` streams immutable image bytes without storing them locally. All routes validate locator fields, subnet, path segments, and request fan-out; an unreachable tool is 503 while a truly missing image is 404. Office compare's base dataset remains mock-backed, but visible cells can lazily request real AMP detail. Only Redis-origin selections may open or compare, so OpenSearch fallback entries cannot enter those inconsistent paths.

## LLM gateway

`back_dev_home/chat/llm.py` sends stateless OpenAI-compatible chat-completion requests. Endpoint, API key, timeout, and model list are environment-driven through the chat config module. Before `httpx.post`, `chat/guard.py` applies an office-only egress blocklist: known public gateways and their subdomains are rejected, while mock mode is unchanged. `CHAT_BLOCKED_HOSTS` can add blocked hosts but cannot remove defaults. Office deployments must point `CHAT_BASE_URL` at an approved internal gateway; a blocked send returns `403` with error code `egress_blocked`, preserves the user turn, and appends no assistant reply.

This is a known-public-host blocklist, not a general internal-host allowlist. The [chat workflow](../workflows/key-workflows.md#chat) has active thread persistence and completion calls, but repository RAG/tool-calling documents describe future work only. Office chat persistence is also unresolved: home mode uses SQLite, while an OpenSearch-backed provider is planned but not connected. Before production, define thread privacy, retention, access, and deletion behavior alongside the datastore.

## Provider readiness

The active mock providers support home development. Tracked `providers/office_example.py` files are the reviewable implementation source; office environments copy them to ignored `providers/office.py` modules for source-specific verification without exposing local details. `docs/office-migration/STATUS.md` records whether real office data passed contract and screen verification; it does not drive runtime selection. SEM list and storage are recorded as office-verified, while health, measurement history, Recipe TAT, fail issue, lateral recipe, recipe search, and MSR file have implemented or partial adapters still awaiting full verification.

When no feature override is set, the [runtime architecture](../architecture/overview.md#provider-seam-and-contracts) selects office only when the process is in office mode and that machine has a direct `providers/office.py` for the feature. `SKEWNONO_DATA_PROVIDER=office` selects mode but does not force missing adapters; `SKEWNONO_DATA_PROVIDER=mock` returns all non-overridden features to mock. A feature-specific mock override isolates a broken adapter:

```bash
SKEWNONO_STORAGE_PROVIDER=mock python index.py
```

An explicit feature `=office` is a promise of real data: startup and direct provider resolution reject it when `office.py` is absent and include the required copy command. Startup also rejects a declared cross-feature mismatch such as `storage=office` with `sem_list=mock`, because storage joins its office rows to the SEM-list roster by equipment IP. After copying the required adapters, restart because the registry scan is process-cached, then confirm the actual resolution through the boot table or `GET /api/health/providers`.

### SEM-list Redis adapter

`back_dev_home/sem_list/providers/office_example.py` reads parquet-serialized DataFrames from `v3_df_sem_avail` and `v3_df_sem_version` using the shared `_runtime/office_redis.py` client. It de-duplicates the version table by `eqp_ip`, left-merges it onto the fleet so rows are not dropped or multiplied, then normalizes the result to `SemListRow`. The public `version` field is a free-form string such as `"1A"`; an unmatched fleet row returns `version: ""`. Parquet is the confirmed format (`pyarrow`); JSON and pickle remain compatibility fallbacks, and malformed data raises a diagnosable upstream-data failure.

The same adapter reads the full company roster from `v3_df_sem_list` and exposes roster-minus-available as `GET /api/sem-list/pending`, joined by equipment ID. Keeping this diff separate prevents unreachable tools from contaminating the connected-fleet identity used by other features. Missing values normalize to blanks, unknown vendors/models remain visible, and pending rows intentionally omit availability/version fields. This integration [surfaces as the Tool Roster workflow](../workflows/key-workflows.md#tool-roster-and-firewall-requests), where it becomes a fab/model matrix and an IT-ready IP export.

Storage shares that Redis plumbing. Its adapter reads per-tool storage DataFrames plus the combined `v3_hitachi_sem_ppid_not_avail` hash, then joins unavailable IPs through SEM list to recover equipment identity and split CD-SEM from HV-SEM. Storage therefore [depends on the SEM-list integration](#sem-list-redis-adapter), and both are office-verified in the migration ledger.

These adapters preserve the [provider seam](../architecture/overview.md#provider-seam-and-contracts): routes and frontend consumers do not know the Redis format. Copy the tracked examples to ignored `office.py` files, configure Redis without committing credentials, restart the process, confirm the provider row, and use the focused checks in [testing guidance](../testing/guidance.md#feature-contract-gates).

### Recipe TAT office analytics

`back_dev_home/ebeam/recipe_tat/providers/office_example.py` performs server-side ranking, summary, trend, and anchor aggregations over `meas_hist_cdsem` and `meas_hist_hvsem`. Because measurement documents do not carry `lot_cd`, it uses the `ebeam_tas_lot_hist` OpenSearch index as the `lot_id` bridge, then enriches active devices from Redis `device_desc` and `r3_device_grp` catalogs. Catalog and lot mappings use a 15-minute cache that serves the last good value after refresh failures; the first load still fails visibly. A ranking `limit=0` means all rows in range, implemented with paginated composite aggregations rather than an approximate fixed-size terms result.

The adapter is implemented, but the migration ledger has not yet recorded office-mode contract and screen verification. Treat it as a verification target, not as fully rolled out.

### Hardware OpenSearch adapters

Hardware's nested office adapters now pin several source contracts. FDC queries `network_fdc_cdsem` by exact `eqp_id.keyword`; its offset-less `timestamp` is interpreted as KST wall clock, and the exact discriminator is `TemperatureEChuck`. The query deliberately does not filter by fab so stale UI fab state cannot suppress a valid equipment result. `scripts/diagnose_fdc_standalone.py` reproduces field, timestamp, and clause diagnosis without repository imports for constrained office hosts.

BSM's implemented adapter queries `beam_shape_cdsem` and normalizes nested 16-point `Reso EB Focus` profiles plus scalar `Reso EB Focus Range`; malformed profiles are dropped and a result exactly at the 10,000-document cap fails rather than presenting a silently truncated trend. SCE's implemented adapter combines the current Redis `sce_info` snapshot with bidaily MinIO archives and treats unsupported fabs as valid empty states. MDC and Reso Center now have reconstructed tracked adapters and contract suites; Reso Center normalizes its flat 13-field source and derives `ResoDelta = ResoIScenter - BestReso`. Existing office-local copies may contain unique code, so merge these examples deliberately rather than overwriting them. These tabs remain CD-SEM-only, and tracked implementation does not equal local activation or office verification.

BM/PM combines `fab_inform_notes` past events (`down_dt`, 180-day lookback) with `tool_maintenance_plan` future work (`tool_start_tm`, 90-day horizon). Shared row logic classifies BM/PM by source text, preserves unclassified rows without chart overlays, formats chart timestamps as `YYYY-MM-DD HH:MM`, and keeps engineer-note fields available for tooltips. These mappings [surface through the hardware workflow](../workflows/key-workflows.md#recipe-and-hardware-operations), not through new public endpoints.

Lateral recipe now queries `cdsem_idp_ver`/`hvsem_idp_ver` and uses `meas_hist_cdsem`/`meas_hist_hvsem` as a 30-day readiness floor. This resolves the aliases and exact-keyword joins for that workflow, but does not establish measurement-history mappings for every Skewvoir or artifact use case.

Create a local adapter before explicitly enabling its override:

```bash
cp back_dev_home/ebeam/<feature>/providers/office_example.py \
  back_dev_home/ebeam/<feature>/providers/office.py
```

The measurement-image path keeps original bytes and TIFF-to-WebP previews under separate cache keys. A MinIO cache hit avoids the preliminary existence request; preview conversion is content-sniffed and cached only when actual WebP conversion succeeds. Before treating FTP tuning as a default, run `scripts/measure_msr_image_ftp.py` to measure login, per-image transfer, fan-out, and optional MinIO PUT cost; `_SECONDS_PER_IMAGE` and proxy-timeout assumptions remain `OFFICE-VERIFY` until measured.

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
- After first cloud deployment, does shared Redis remain stable for access-control, API-token, announcement, and rate-limit state, and does the host reliably forward `LASTUSER` so anonymous declarations remain an exception rather than the default? Office activity is derived from the shared canonical OpenSearch log stream.

Track startup and provider failures through the [operations runbook](../operations/runbook.md), and verify adapters using [testing guidance](../testing/guidance.md).
