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

`ops_store/` is a generic OpenSearch wrapper for search, document, and index operations. Product office providers should own domain queries and normalization while reusing this transport layer. Current integrated uses include cloud request logging, optional admin-log querying, and health probes.

`ops_index_mgmt/` contains one-shot templates, aliases, ISM policies, rollover setup, and reindex scripts. It is operational provisioning, not request-time application code. Measurement-history aliases are likely Skewvoir office sources, but exact joins, mappings, and retention configuration remain unresolved.

The admin-logs feature currently performs configured OpenSearch querying inside its nominal mock provider while its office provider is a stub. Treat that as migration debt rather than a pattern to copy.

## MinIO and large objects

`minio_handler/` wraps bucket/prefix CRUD, listing, presigned URLs, DataFrames, and images. It is an approved office-adapter dependency, but current feature integrations mostly stop at health probing. MSR and AFM office designs still need a firm choice among MinIO, live source access, or another artifact service.

A likely clean split is searchable metadata in OpenSearch and large images/files in object storage, but this remains an architectural direction rather than confirmed runtime behavior.

## FTP ingestion

`ftp_handler/` is an ingestion library, not a Flask Blueprint. It supports direct and HTTP-proxied fleet downloads, listing/size passes, background jobs, and injected archive/parse/index callbacks. The package intentionally does not import MinIO or OpenSearch; callers provide those side effects.

`back_dev_home/msr_file/MIGRATION.md` identifies tool FTP as a possible office image source. The operational decision still needs caching, timeouts, failure behavior, and a choice between serving live FTP content and archived objects.

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

- What are the authoritative aliases and joins for `meas_hist` and `msr_file`?
- Where do stable site-layout, recipe-revision, coordinate-transform, and sequence fields originate?
- Will measurement and AFM images be served from FTP, MinIO, or presigned object URLs?
- What store backs editable measurement-rule versions and rollback?
- Should Redis or another shared system replace process-local access, activity, token, and limiter state in production?
- When can AFM compatibility aliases and `afm_data_platform/` be retired?

Track startup and provider failures through the [operations runbook](../operations/runbook.md), and verify adapters using [testing guidance](../testing/guidance.md).
