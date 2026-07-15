# Handoff — FTP fleet downloader + Flask proxy

Context for a fresh agent picking up the equipment-FTP collection work. Primary
reference doc (do not duplicate): [`ftp_fleet_downloader.md`](ftp_fleet_downloader.md).

## Goal

Pull the same files (FDC/recipe logs, timestamped measurement files) from 200+
equipment FTP servers every 30 min, archive raw to MinIO, parse, and index to
OpenSearch — running on the company Airflow (mostly LocalExecutor, 2–4 CPU).
A Flask **proxy** variant exists for a firewalled client PC that can't reach
FTP directly.

## Original bug that started this

User's `aioftp` + `PythonVirtualenvOperator` pipeline worked locally but failed
on the server ("some hosts fail, downloaded file not on disk"). Root cause:
unbounded concurrency (~200 simultaneous connections) hitting `ulimit -n` /
FTP connection caps, plus unpinned `aioftp` version drift in the runtime venv.
Fix direction chosen: `asyncio.to_thread + ftplib`, bounded concurrency,
per-host isolation, in-memory (no disk). See decision table in the reference doc.

## What was built

| Path | Role |
|------|------|
| `ftp_handler/ftp_fleet_downloader.py` | Core downloader. Sync API over async/thread fan-out. `FtpFleetDownloader`, `download_fleet`, `HostSpec`, `ListDir`, `DownloadReport` (+ `.grouped()`, `.failure_ratio`), `save_to_dir()` disk helper. |
| `ftp_handler/eqp_ftp_collect.py` | Airflow-free glue: `build_host_specs`, `collect_fleet` (archive→parse→index per file). Storage/index injected as callables (no minio/opensearch import). |
| `ftp_handler/ftp_flask_proxy.py` | Flask **Blueprint** `ftp_proxy_sknn_v3`; reuses the downloader, returns base64 bytes. Routes `/download_sknn_v3`, `/healthz_sknn_v3`. |
| `ftp_handler/ftp_flask_downloader.py` | Drop-in client for the proxy — same public names, HTTP transport. Re-exports the same dataclasses + `save_to_dir`. |
| `dags/eqp_ftp/eqp_ftp_collector_dag.py` | Thin `*/30` DAG: Variable `eqp_ftp_fleet`, Connection `eqp_ftp`, threshold failure, no-overlap. |
| `tests/test_ftp_fleet_downloader.py` | Downloader + glue + `save_to_dir` (mocked `ftplib.FTP`). |
| `tests/test_ftp_flask_proxy.py` | Client↔proxy end-to-end via Flask test client (only FTP faked). |

## Key decisions (resolved during a grilling session)

- In-memory `BytesIO`, not disk (files are KB–few MB). `save_to_dir` added later as an opt-in for the local-PC-to-disk case; handles Windows+Linux FTP separators, path-traversal, illegal-char sanitization.
- Bounded concurrency `max_concurrency=48` — I/O-bound threads, **not** CPU-bound, so fine on 2–4 cores.
- Timeouts: `connect_timeout=8` (the dead-host detector), `host_timeout=60` (whole-host backstop). Lowered from 15/120.
- Per-host error isolation; threshold-based task failure (`failure_ratio > 0.2` or zero successes), not fail-on-any.
- One connection per host, reused for both fixed-path `RETR` and `NLST`+filter discovery.
- Proxy is stateless, never writes disk; `on_file` runs on the client.

## State

- ✅ **30 tests pass** (`python -m pytest tests/test_ftp_fleet_downloader.py tests/test_ftp_flask_proxy.py -q`), all modules byte-compile. Tests are stdlib/mock — `flask`+`requests` present locally; `opensearchpy` present; `airflow`+`minio` are NOT installed locally.
- ❌ **Never run against a real FTP server** (local or company).
- ❌ **DAG integrity test not run** here (`airflow`/`minio` missing) — run `python -m pytest tests/test_dag_integrity.py -v` on a box with Airflow.
- ⚠️ Nothing committed to git yet.

## Open items for the next session

1. **Vendor `ops_store` under `airflow_mgmt/`** (like `minio_handler`) — the DAG's index step does `from ops_store import OSDoc`, which is unreachable from the `airflow_mgmt` root marker. Until then the index step fails at runtime. DAG parses fine (import is deferred into the task).
2. **Implement `parse_records(host, remote_path, data)`** in the DAG (currently `NotImplementedError`). Needs a deterministic `_id` per record for 30-min idempotency. File types vary; user deprioritized storage detail during design.
3. **OOM tuning for the shared uWSGI app** (`api/wsgi.ini`: `processes=4 threads=2 reload-on-rss=1500 harakiri=60`). Recommended but NOT yet applied: client `request_batch=10`, `host_timeout=45` (must stay under `harakiri=60`), optionally `max_concurrency=24`. User was offered baking these as defaults — not confirmed.
4. **Verify PASV** from the real worker/proxy (different subnet than the laptop) — `passive=False` fallback if `RETR` hangs only on the server.
5. **Live validation**: real local download → DAG parse → one manual company-Airflow run.

## Suggested skills for next session

- `tdd` — when implementing `parse_records` (test-first against real sample files).
- `verify` — to validate a real run / fix once Airflow + a reachable host are available.
- `commit` (commit-commands) — nothing is committed; create commits when the user is ready.
