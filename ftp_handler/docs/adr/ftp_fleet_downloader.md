# FTP Fleet Downloader

Concurrent, in-memory FTP downloader for pulling the same files from many
equipment FTP servers (~200+) on a schedule. Lives in
`ftp_handler/ftp_fleet_downloader.py`; the storage/processing glue is in
`ftp_handler/eqp_ftp_collect.py`; the production DAG is
`dags/eqp_ftp/eqp_ftp_collector_dag.py`.

## Why this shape

- **`asyncio.to_thread` + `ftplib`, not `aioftp`.** Each host is one short FTP
  session that is almost all socket I/O, and Python releases the GIL during
  socket I/O — so blocking `ftplib` in a bounded thread pool fans out hundreds
  of hosts concurrently with **zero extra packages**. No `aioftp` to
  `pip install` into an Airflow venv, no `PythonVirtualenvOperator`, no version
  drift between your laptop and the worker. (Unpinned `aioftp` installed at
  task runtime, drifting from your local version, is a classic
  "works on my machine, breaks on the server" cause.)
- **Bounded concurrency.** ~200 *simultaneous* connections blow past the
  worker's open-file limit (`ulimit -n`) and the equipment's connection caps;
  some downloads then silently fail. `max_concurrency` caps how many run at
  once.
- **Per-host isolation.** One dead/black-holed host can't abort or stall the
  rest: tight timeouts bound each host, and failures are collected, not raised.

## Quick start

### Mode A — collect everything, then process

Returns one `DownloadReport` holding every file's bytes. Peak RAM = **sum of
all files**. Fine for small files / modest fleets.

```python
from ftp_handler.ftp_fleet_downloader import FtpFleetDownloader, HostSpec, ListDir

dl = FtpFleetDownloader(user="ftpuser", password="ftppass", max_concurrency=48)

report = dl.download([
    HostSpec("10.0.0.1", files=["/HITACHI/SYSFILE/LOG_RECIPE_EXE.log"]),
    HostSpec("10.0.0.2", listings=[ListDir("/MEAS", "*.dat")]),
    HostSpec("10.0.0.3",
             files=["/SYS/fdc.log"],
             listings=[ListDir("/MEAS", "*.dat")]),
])

print(f"ok={report.ok} ng={report.ng} fail_ratio={report.failure_ratio:.0%}")
for f in report.files:
    handle(f.host, f.remote_path, f.data)   # f.data is bytes
```

**The "single nested-dict variable" you asked about** — `report.grouped()`:

```python
data = report.grouped()
# {
#   "10.0.0.1": {"/HITACHI/SYSFILE/LOG_RECIPE_EXE.log": b"..."},
#   "10.0.0.2": {"/MEAS/20260522_1430_x.dat": b"...", ...},
# }
for host, files in data.items():
    for remote_path, raw in files.items():
        records = parse(host, remote_path, raw)   # <-- your processing here
        send_to_opensearch(records)
```

### Mode B — stream each file as it lands (memory-bounded)

Pass an `on_file` callback. Each file is handed to you the moment it downloads,
then dropped — peak RAM stays at **concurrency × file size**, regardless of
fleet size. This is the recommended mode at fleet scale.

```python
def on_file(host: str, remote_path: str, data: bytes) -> None:
    records = parse(host, remote_path, data)   # <-- your processing here
    storage.put(f"{host}/{remote_path.lstrip('/')}", data)   # archive raw
    OSDoc().bulk_index("eqp_meas", records)                  # index processed

report = dl.download(specs, on_file=on_file)   # report carries no bytes
```

> Where does my processing go? — There are exactly two seams: the body of your
> `on_file` callback (Mode B), or the loop over `report.grouped()` (Mode A).
> Either way, *you* own `parse(...)`; the downloader only fetches bytes.

### One-call helper

```python
from ftp_handler.ftp_fleet_downloader import download_fleet

report = download_fleet(specs, user="ftpuser", password="ftppass",
                        max_concurrency=48)
```

## API

### `HostSpec(host, files=[], listings=[])`
One equipment host and everything to pull from it over **one reused
connection**.
- `files: list[str]` — fixed remote paths fetched directly (`RETR`). Use for
  known append-only logs (FDC, recipe logs).
- `listings: list[ListDir]` — directories listed (`NLST`) then filtered, one
  `RETR` per match. Use for timestamped measurement files whose names you can't
  predict.

A host can mix both; they share the same connection.

### `ListDir(remote_dir, pattern=None)`
`pattern` is an fnmatch glob (`"*.dat"`); `None` fetches every entry. NLST
results are normalized whether the server returns bare names or full paths.

### `FtpFleetDownloader(*, user, password, port=21, max_concurrency=48, connect_timeout=15.0, host_timeout=120.0, passive=True)`
- `max_concurrency` (default 48) — simultaneous connections / threads. These
  are **I/O-bound** threads (blocked on sockets, GIL released), so this is
  **not** bounded by CPU count — 48 is fine on a 2–4 core box. The real limits
  are file descriptors (`ulimit -n`), peak RAM in Mode B (`concurrency × file
  size`), and the FTP servers'/network capacity. Lower it only if files are
  large or you hit those limits.
- `connect_timeout` (default 8 s) — **the connection-wait knob.** Bounds each
  blocking socket op (connect, login, `RETR`), so an offline/black-holed tool
  is abandoned in 8 s instead of hanging a slot. This is what makes hundreds of
  dead tools fail fast.
- `host_timeout` (default 60 s) — wall-clock backstop for a *whole host*
  (connect + listing + all its files). It does **not** govern dead-host
  detection (`connect_timeout` does); it only fires for a host that connects
  then stalls mid-transfer. Keep it above `connect_timeout × files-per-host`;
  don't set it as low as `connect_timeout` or healthy multi-file hosts get
  killed.
- `passive` — PASV mode (default `True`). See the firewall note below.
- `.download(specs, *, on_file=None) -> DownloadReport` — **synchronous**; runs
  its own event loop. Do **not** call from already-async code (`asyncio.run`
  can't nest).

### `DownloadReport`
- `.files: list[FileResult]` — `FileResult(host, remote_path, data)`. `data` is
  `b""` when an `on_file` callback consumed the bytes.
- `.failures: list[HostFailure]` — `HostFailure(host, error, remote_path)`.
  `remote_path is None` ⇒ failed before any file (connect/login/listing).
- `.ok` / `.ng` — success / failure counts.
- `.failure_ratio` — `ng / (ok + ng)`, for threshold alerting (`0.0` if empty).
- `.grouped() -> {host: {remote_path: bytes}}`.

### `ftp_handler.eqp_ftp_collect`
- `build_host_specs(fleet: list[dict]) -> list[HostSpec]` — turns the runtime
  config (Airflow Variable JSON) into specs.
- `collect_fleet(specs, *, user, password, archive, parse, index, **tuning)` —
  runs the downloader in Mode B with `archive → parse → index` per file
  (archive first, so you never index a record whose raw source wasn't stored).
  `archive`, `parse`, `index` are callables you supply, so this layer needs no
  `minio`/`opensearch` import and stays unit-testable.

## In-memory vs. disk — is in-memory safe under concurrency?

**Short answer: in-memory is safe here, and it is not inherently riskier than
disk.** The fear that "async mixes one host's data into another host's buffer"
comes from *shared mutable state*, not from memory itself.

Cross-host contamination happens only if concurrent units share a destination
or a stateful resource:
- **One FTP connection shared across concurrent downloads.** FTP is stateful
  (CWD, in-flight transfer); interleaving `RETR`s on one control connection
  corrupts data. → This downloader opens **one connection per host**, used
  sequentially inside that host's own thread (`_host_worker`).
- **A shared global/buffer/dict written without keying.** → Each download
  writes to a **local `BytesIO` created fresh per file** inside `_fetch_one`.
  Local variables are per-thread stack frames — never shared. Results are
  appended to a list (`list.append` is atomic under the GIL) and keyed by
  `(host, remote_path)`.

Note that **disk has the exact same risk**: if two hosts write to a path keyed
by *filename only*, they clobber each other — that *is* cross-host mixing, just
on disk. The repo's `recipe_log_collector` avoids it with a `uuid4` folder +
per-IP subdir. Correctness comes from **isolating the destination per host**
(unique buffer *or* unique path) and **not sharing a connection** — not from
the storage medium. asyncio never moves data between coroutines on its own;
each task has its own stack.

**When disk genuinely wins:** memory pressure, not correctness. Large files ×
high concurrency can exceed worker RAM; streaming to disk keeps RAM flat. That
was the grilling decision: small files (KB–few MB) → in-memory; if files were
large/variable → stream to scratch disk at low concurrency (the
`recipe_log_collector` pattern). For durability across retries we rely on
idempotency (deterministic `_id` + idempotent MinIO `put`), not on keeping
files on disk.

## Passive mode (the second "works locally, not on the server")

`ftplib` defaults to PASV, which is right behind NAT. But an Airflow worker on
a *different subnet* than your laptop can have its data connection firewalled
differently. If downloads connect+login fine but every `RETR` hangs/fails from
the worker only, try `passive=False`. Verify against one real host early.

## Airflow usage

The DAG `dags/eqp_ftp/eqp_ftp_collector_dag.py` wires it up:

- **Fleet config** from Airflow **Variable** `eqp_ftp_fleet` (JSON), re-read
  every run — edit the fleet without a code deploy:
  ```json
  [
    {"host": "10.0.0.1",
     "files": ["/HITACHI/SYSFILE/LOG_RECIPE_EXE.log"],
     "listings": [{"remote_dir": "/MEAS", "pattern": "*.dat"}]},
    {"host": "10.0.0.2", "files": ["/SYS/fdc.log"]}
  ]
  ```
- **Credentials** from a single Airflow **Connection** `eqp_ftp` (shared login).
- **Threshold failure**: the task is green on normal partial failures and only
  fails (alerts) when `failure_ratio > EQP_FTP_FAILURE_THRESHOLD` (default 0.2)
  or zero successes — distinguishing "one tool is off" from "the network/creds
  broke."
- **No overlap**: `schedule="*/30 * * * *"`, `max_active_runs=1`,
  `catchup=False`, `dagrun_timeout=25m`.
- Implement `parse_records(host, remote_path, data) -> list[dict]` in the DAG
  (the stub raises `NotImplementedError`). Give each doc a deterministic `_id`
  so 30-min re-runs are idempotent.

> **ops_store caveat:** the index step imports `ops_store`, which is **not**
> vendored under `airflow_mgmt/` (only `minio_handler` is). Vendor `ops_store`
> the same way, or make the repo root importable on the worker, before the
> index step runs. The DAG parses fine without it (the import is deferred into
> the task body).

Env overrides: `EQP_FTP_FLEET_VARIABLE`, `EQP_FTP_CONN_ID`, `EQP_FTP_BUCKET`,
`EQP_FTP_INDEX`, `EQP_FTP_MAX_CONCURRENCY`, `EQP_FTP_CONNECT_TIMEOUT`,
`EQP_FTP_HOST_TIMEOUT`, `EQP_FTP_FAILURE_THRESHOLD`.

## Proxy variant — when the client is firewalled off the FTP servers

If the machine that needs the data **cannot reach the equipment FTP servers**
(firewalled) but a **firewall-free host can**, run the downloader behind an
HTTP proxy:

```
local PC ──HTTP──> Flask proxy ──FTP──> equipment servers
(firewalled)       (firewall-free)
```

Two files implement this, and the client is a **drop-in** for the direct
downloader — swap one import, change nothing else:

| File | Runs on | Role |
|------|---------|------|
| `ftp_handler/ftp_flask_proxy.py` | firewall-free host | Flask **Blueprint** (`ftp_proxy_sknn_v3`); does the real FTP via `FtpFleetDownloader`, returns base64'd bytes over HTTP |
| `ftp_handler/ftp_flask_downloader.py` | firewalled client | same API (`FtpFleetDownloader`, `download_fleet`, `HostSpec`, …); POSTs batches to the proxy instead of doing FTP |

Routes carry a `_sknn_v3` suffix (`/download_sknn_v3`, `/healthz_sknn_v3`) so
they don't collide with paths already mounted on the host app.

```python
# direct (no firewall):
from ftp_fleet_downloader import FtpFleetDownloader, HostSpec, ListDir
# via proxy (firewalled client) — only this line changes:
from ftp_flask_downloader import FtpFleetDownloader, HostSpec, ListDir
```

The client **re-exports the same dataclasses**, so `DownloadReport`,
`grouped()`, `failure_ratio`, and your `on_file` handler are identical under
either transport. `on_file` still runs **on the client**, so your
parse/archive/index processing stays local — only the FTP bytes cross the
proxy.

**Mount the proxy** as a blueprint on your existing firewall-free Flask app:
```python
from ftp_flask_proxy import ftp_proxy_sknn_v3
app.register_blueprint(ftp_proxy_sknn_v3)   # adds /download_sknn_v3, /healthz_sknn_v3
```

**Or run it standalone** (on the firewall-free host):
```bash
pip install flask
# PowerShell:
# $env:FTP_PROXY_FTP_USER="ftpuser"
# $env:FTP_PROXY_FTP_PASSWORD="ftppass"
# $env:FTP_PROXY_TOKEN="secret"
python ftp_flask_proxy.py                  # serves 0.0.0.0:8080
```

**Use the client** (on the firewalled PC):
```bash
pip install requests
```
```python
dl = FtpFleetDownloader(user="ftpuser", password="ftppass", max_concurrency=48)
report = dl.download(specs)                 # same call as direct mode
```

Notes:
- **Security:** the equipment FTP credentials the client was constructed with
  travel in the POST body (2026-08-28 — between 2026-08-09 and that date they
  did not, and the proxy silently logged in as its own environment account
  instead of the caller's). `FTP_PROXY_FTP_USER` / `FTP_PROXY_FTP_PASSWORD` on
  the proxy host remain the fallback for a request that names no account. File
  bytes and credentials both cross the HTTP hop, so run the proxy behind
  **HTTPS** and set `FTP_PROXY_TOKEN` (the proxy enforces `Authorization:
  Bearer <token>`).
- **Per-host credentials:** one fleet is not always one account. `HostSpec` and
  `UploadSpec` carry optional `user`/`password` overriding the downloader's for
  that host alone, so a run spanning two vendors' tools spans two logins. Only
  an override is serialized — a host on the shared account sends no credential
  key at all, and an entry arriving without one falls back to the proxy's
  environment. That fallback is what lets the two halves deploy in either
  order.
- **Seam-clean config:** proxy location/auth are module constants in
  `proxy_downloader.py` (`PROXY_URL`, `PROXY_TOKEN`), **not** constructor args —
  that keeps the client constructor signature identical to the direct
  downloader, so a shared call site swaps the import line and passes nothing
  transport-specific. Edit the constants once for the deployment.
- **Batching:** the client splits hosts into `request_batch` (default 5) and
  POSTs `client_workers` (default 4) batches concurrently, bounding response
  size and mirroring the direct fan-out. A whole-batch transport failure marks
  every host in it failed — per-host isolation one level up. The defaults are
  small on purpose: the proxy collects a whole batch in memory (Mode A) and
  base64+jsonify roughly triples it, on a host app sharing an 8GiB /
  `reload-on-rss=1500` envelope with pandas tasks. `host_timeout` defaults to
  45s to stay under the host app's `harakiri=60`. See `0001-proxy-batch-sizing.md`.
- **Wire format:** JSON + base64. Simple and fine for small files; for very
  large payloads a binary/streaming transport would beat base64's ~33% bloat.

## Tests

`tests/test_ftp_fleet_downloader.py` patches `ftplib.FTP` with a `FakeFTP` —
no live server. Covers per-host error isolation, both discovery modes, NLST
path normalization, `on_file` streaming, threshold math, and the
`archive → parse → index` ordering.

`tests/test_ftp_flask_proxy.py` wires the real client to the real proxy through
Flask's test client (faking only FTP), proving the round trip, `on_file`
running client-side, failure propagation, batch isolation, auth enforcement,
and that the report types are literally shared between the two transports.

```bash
python -m pytest tests/test_ftp_fleet_downloader.py tests/test_ftp_flask_proxy.py -v
```
