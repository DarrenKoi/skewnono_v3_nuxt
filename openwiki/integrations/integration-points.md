---
type: Integration Guide
title: Integration Points and Office Migration Boundaries
description: Live and planned SKEWNONO boundaries for Nuxt proxying, identity, OpenSearch, MinIO, FTP ingestion, LLM completion, and provider-by-provider office migration.
resource: docs/back-end/office-data-adapters.md
tags: [integrations, opensearch, minio, ftp, sso, llm]
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

`back_dev_home/chat/llm.py` sends stateless OpenAI-compatible chat-completion requests. Endpoint, API key, timeout, and model list are environment-driven through the chat config module. The [chat workflow](../workflows/key-workflows.md#chat) has active thread persistence and completion calls, but repository RAG/tool-calling documents describe future work only.

Office chat persistence is also unresolved: home mode uses SQLite, while an OpenSearch-backed provider is planned but not connected. Before production, define thread privacy, retention, access, and deletion behavior alongside the datastore.

## Provider readiness

The active mock providers support home development. Representative unconnected office adapters include health, SEM list, measurement history, MSR file, storage, hardware, Device Statistics, AFM, chat, activity, and access control. Use feature-specific overrides during incremental rollout:

```bash
SKEWNONO_DATA_PROVIDER=office \
SKEWNONO_HEALTH_PROVIDER=mock \
SKEWNONO_STORAGE_PROVIDER=mock \
python index.py
```

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
