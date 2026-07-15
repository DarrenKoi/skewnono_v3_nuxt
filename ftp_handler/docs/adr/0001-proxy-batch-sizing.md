# 0001 — FTP proxy batch sizing for ~10MB files

- Status: accepted
- Date: 2026-05-22

## Context

The Flask proxy (`ftp_handler/ftp_flask_proxy.py`) mounts as a blueprint on the
existing company API uWSGI app. That app's envelope (`api/wsgi.ini`):
`processes=4`, `reload-on-rss=1500` (MB), `harakiri=60` (s), on an **8 GiB**
host, and it already runs memory-heavy pandas/Arrow tasks (600–800 MB per
request per the wsgi comments). The proxy borrows from that same per-worker
budget — it does not get a fresh one.

Two structural facts of the proxy make large files expensive:

1. **Mode-A collection.** The proxy calls `downloader.download(specs)` with no
   `on_file`, so it holds an entire request batch's bytes in memory before
   responding. It cannot stream per-file the way the direct path does.
2. **base64 + jsonify.** The response is JSON with base64'd bytes — roughly a
   3× transient over the batch's raw bytes (raw buffer + base64 string +
   serialized JSON copy, briefly co-resident).

File profile (resolved in the grilling session): ~300 hosts, of which only
20–30 carry large files, at 1–2 × ~10MB each. The rest are KB–few MB.

At the original defaults (`request_batch=20`, `host_timeout=60`,
`client_workers=8`) a batch landing several large hosts reaches ~1.4 GB
transient — at the `reload-on-rss=1500` cliff — and can recycle the worker
**mid-request**, failing the whole batch and potentially disrupting an
in-flight pandas task in that worker. Separately, `host_timeout=60 ≥
harakiri=60` lets one stalled host consume the entire request budget so uWSGI
kills the request before the downloader's own graceful backstop fires.

## Decision

Keep the proxy's Mode-A-collect transport (no streaming rewrite) but **size the
defaults against the shared 8 GiB envelope**:

- `request_batch = 5` — worst-case transient ≈ 5 × 2 × 10MB × 3 ≈ 370 MB, well
  under `reload-on-rss=1500` even stacked on an 800 MB pandas task.
- `host_timeout = 45` — under `harakiri=60`, so the downloader's per-host
  backstop fires first and the batch returns partial results instead of being
  killed.
- `client_workers = 4` — match `processes=4`: one batch per worker process, no
  two batches stacking in a single worker's address space.

These are baked in as defaults in `ftp_flask_downloader.py` (and the proxy's
`host_timeout` fallback in `ftp_flask_proxy.py`), not left to the call site,
because the defaults exist to give a caller who hasn't done this math a safe
result on the shared host.

The direct Airflow path is unaffected: it streams (Mode B), peak RAM ≈
`concurrency × file size` ≈ 300 MB, on its own worker.

## Consequences

- Roughly 4× more HTTP round trips for the same fleet (60 batches vs 15 at 300
  hosts). Acceptable — the proxy path is the firewalled fallback, not the hot
  path, and the trips run `client_workers=4` concurrent.
- If the file profile changes materially — many hosts each dumping several
  10MB+ files — small batches stop being enough and the proxy should move to a
  **streaming transport** (chunked / multipart per file, dropping base64's 33%
  bloat). That is the rewrite this ADR deliberately defers.
- Do **not** "optimize" `request_batch` back up without re-checking the
  `reload-on-rss` / pandas-stacking math above; the small value is load-bearing.
