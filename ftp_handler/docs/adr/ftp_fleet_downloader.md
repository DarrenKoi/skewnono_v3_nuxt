# FTP Fleet Downloader — design rationale

Why `direct_downloader.FtpFleetDownloader` and its proxy twin are shaped the way
they are. How to call them is in `../guides/usage.md`; the module map and the
per-operation table are in `../guides/summary.md`; terms are in `CONTEXT.md`.

## Threads + `ftplib`, no event loop

Each host is one short FTP session that is almost all socket I/O, and Python
releases the GIL during socket I/O — so blocking `ftplib` in a bounded
`ThreadPoolExecutor` fans out hundreds of hosts concurrently with **zero extra
packages**. No `aioftp` to install into an Airflow venv, no version drift
between a laptop and the worker (unpinned `aioftp` installed at task runtime
was the original "works locally, fails on the server" bug).

There is no asyncio anywhere: every fleet operation is a plain synchronous
call, safe from a script, an Airflow task, a Flask handler, or code already
running its own event loop.

## Bounded concurrency and the two timeouts

- `max_concurrency` (default 48) caps simultaneous connections. ~200 at once
  blows past `ulimit -n` and the equipment's connection caps, and downloads
  then fail silently. The threads are I/O-bound, so the cap is not tied to CPU
  count; the real limits are file descriptors, peak RAM (streaming mode:
  `concurrency × file size`), and the servers.
- `connect_timeout` (default 8 s) is the dead-host detector: it bounds every
  blocking socket op, so an offline tool is abandoned in seconds.
- `host_timeout` (default 60 s; the proxy client defaults to 45 s) is the
  whole-host backstop for a host that connects and then stalls. It is measured
  from when that host's worker starts, not from submit. Keep it above
  `connect_timeout × files-per-host`.

A timed-out host's thread cannot be killed; `_FileGate` makes sure its
`on_file` callback stops reaching caller state once `download` has reported it
failed.

## Failure isolation is the normal case

One dead host never aborts its siblings, and inside a host one bad file (or
directory, for `mkdir` / `delete`) never aborts the rest. Failures are collected into the
report, never raised. Callers gate on `failure_ratio` (e.g. `> 0.2`, or zero
successes) — tools go offline routinely.

## In-memory, not disk

Cross-host contamination comes from **shared mutable state**, not from memory:
each host gets its own connection used sequentially in its own thread, and each
file lands in a fresh local `BytesIO`. Disk has the same risk (two hosts
writing the same filename clobber each other); correctness comes from isolating
the destination per host, not from the medium.

Disk wins only on memory pressure. Files here are KB–few MB, so the default is
in-memory; at fleet scale use `on_file` streaming so peak RAM stays at
`concurrency × file size`. Durability across retries comes from idempotency
(deterministic OpenSearch `_id`, idempotent MinIO `put`).

## Passive mode

`ftplib` defaults to PASV, which is right behind NAT. A worker on a different
subnet than your laptop can have its data connection firewalled differently:
if login works but every `RETR` hangs only from the server, try
`passive=False`.

## `mkdir` is `mkdir -p` and idempotent

`mkdir` exists so an `upload` to a new path has a destination — STOR cannot
create folders. Each entry of `MkdirSpec.dirs` creates its missing parents, and
an existing directory counts as success, so callers run it before an upload
without looking first. FTP answers MKD with the same 550 for "already exists"
and for "permission denied", so a refused MKD is settled by CWD into that path
(enter it → it exists; then CWD back to the login PWD so relative paths keep
resolving there). If that CWD back fails, the session sits in an unknown
directory, so the host's remaining dirs are all reported failed rather than
created in the wrong place.

## `delete` is DELE + RMD of empty dirs, and idempotent

`DeleteSpec.files` are DELE'd, then `dirs` RMD'd — files first, so a directory
emptied by the same spec can go too. There is no recursive delete: RMD refuses
a non-empty directory, and walking a tree would lean on LIST/MLSD parsing that
differs per server, for a destructive operation. A path already gone is a
success, so a retried run is harmless.

That needs the 550 settled again: after a refused DELE/RMD the path counts as
gone only if `SIZE` answers 550 (not a file) **and** `CWD` answers 550 (not a
directory). Either check finding something re-raises the original refusal —
which is how a non-empty directory, a directory named as a file, and a file
named as a directory all stay failures. A probe refused with anything but 550
(502 "SIZE not implemented", 530, …) proves nothing about the path, so it keeps
the failure too. The known ceiling: a server that refuses SIZE on an existing
file with 550 makes that file read as gone.

Two rules keep a delete from landing on the wrong path or the wrong time:

- **The CWD probe must be undoable.** It returns to the login PWD exactly as
  `mkdir` does, and stops the host if that fails. Only a clean refusal
  (`error_perm`) proves the probe did not move the session; any other error
  from the probe itself (an undecodable or lost reply — the server may have
  changed directory anyway) stops the host too, for `mkdir` and `delete`
  alike. `core.FtpClient.mkdir` drops its connection in the same cases. An empty login PWD (ftplib's
  answer to a PWD reply it cannot parse) counts as a failed return, because
  `cwd("")` sends `CWD .` and would "succeed" in place — leaving the next
  relative DELE inside the probed directory.
- **An abandoned host stops deleting.** A host given up on at `host_timeout`
  keeps its thread, and `delete` sets that host's stop flag, so it sends no
  further DELE/RMD after the caller has been told it failed. The command
  already in flight cannot be recalled; its outcome is unknown.

## Proxy pair

For a client that cannot reach the FTP servers but can reach a firewall-free
host: `proxy/flask_proxy.py` does the real FTP there, `proxy/proxy_downloader.py`
exposes the same `FtpFleetDownloader` surface over HTTP.

- **One seam.** `FleetTransport` lists every fleet operation; a conformance
  test asserts both adapters match it method by method, so a call site swaps
  one import line. Proxy location/auth are module constants (`PROXY_URL`,
  `PROXY_TOKEN`), not constructor args, so the constructor stays identical.
- **Credentials travel with the spec.** `user` and `password` resolve
  **independently**, each as spec value → client constructor value → the proxy
  host's `FTP_PROXY_FTP_USER` / `FTP_PROXY_FTP_PASSWORD`; a field missing from
  the wire falls back alone. That fallback also lets the two halves deploy in
  either order. Bytes and
  credentials both cross the HTTP hop: serve it behind HTTPS and set
  `FTP_PROXY_TOKEN`.
- **Small batches.** The proxy holds a whole batch in memory and
  base64 + jsonify roughly triples it, on a host app sharing an 8 GiB /
  `reload-on-rss=1500` envelope. Hence `request_batch=5`, `client_workers=4`,
  and `host_timeout=45` under the host's `harakiri=60` — see
  `0001-proxy-batch-sizing.md`. A whole-batch transport failure marks every
  host in it failed.
- **Wire format** is JSON + base64: simple, ~33% bloat, fine for small files.

## Airflow

The scheduled collector is `airflow_mgmt/dags/eqp_ftp/eqp_ftp_collector_dag.py`;
its module docstring is the source of truth for its Variable, Connection,
schedule, venv and threshold settings.
