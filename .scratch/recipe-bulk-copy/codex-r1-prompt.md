# Review request: recipe bulk copy design (handoff.md)

Read `.scratch/recipe-bulk-copy/handoff.md` and critique the design. Read-only; do not edit files.
Write your findings to `.scratch/recipe-bulk-copy/codex-r1.md` (Korean, formal `~입니다` endings, markdown).

## New constraints from the user (not yet in handoff.md)

- Target scale: copy a recipe bundle (hundreds of files) from one tool to **10+ tools** at once, reliably.
- SKEWNONO production runs on **2 CPU / 8 GiB**, uWSGI `processes=4 threads=4 lazy-apps harakiri=720 max-requests=1000`, nightly `touch-reload` at 00:05. It already runs pandas/Arrow requests of 600–800 MB.
- The user can get a **separate web app** on the company private cloud (same network as SKEWNONO), or scale SKEWNONO's CPU/RAM. Either is allowed.
- Hard requirement: **the copy feature must not affect the running SKEWNONO service.**
- Office Redis is reachable from the cloud and already holds app-owned state (api_tokens, access_control, announcements). MinIO is also available. No SQL DB exists.

## Context you should check in the repo

- `ftp_handler/core/client.py` — `FtpClient.put` (no-clobber temp+rename, `TargetExists`, `TransferUncertain`).
- `ftp_handler/direct_downloader/fleet_downloader.py` — `FtpFleetDownloader`, `UploadSpec` (note: `UploadFile` overwrites).
- `ftp_handler/web_app/jobs.py` — `BackgroundJobs` (in-memory, single-process).
- `ftp_handler/proxy/flask_proxy.py` — fleet `upload()` route exists (overwriting); single-client explorer routes have no write.
- `ftp_handler/docs/adr/0001-proxy-batch-sizing.md` — RAM math on the shared 8 GiB host.
- `backend/_scheduler/election.py` — how exactly one uWSGI worker is elected.
- `backend/chat/orchestration.py` `_spawn_daemon` — precedent of a background daemon thread inside a uWSGI worker (dies on reload/recycle).
- `docs/deployment.md` lines 120–200 — uWSGI envelope and why.
- `.scratch/tool-files/spec.md` — the sibling explorer feature whose auth/eqp/path/safe-write helpers the copy job reuses.

## Questions I want your independent view on

1. Where should the dedicated worker live: (a) thread inside SKEWNONO uWSGI, (b) separate process on the same host via `attach-daemon`, (c) the separate web app? Give the decisive reason, and what must be true of the cloud platform for (c) to work (OFFICE-VERIFY items).
2. What is the minimal durable job/task state model so a worker restart mid-job resumes correctly (which states, who writes, how idempotent re-verification works)? Redis is the only shared store.
3. Does bundle-level atomic swap (upload to `<bundle>.tmp/` dir then rename dir) beat per-file no-clobber `put`? What breaks if the tool FTP does not support directory rename?
4. Concurrency plan for 10+ targets × hundreds of small files: per-tool connection count, cross-tool parallelism, where the ceiling is (FTP server session limits vs our CPU), and how to keep the source snapshot consistent.
5. Verification: re-download + hash on every file for every target — acceptable, or propose cheaper that is still trustworthy.
6. The handoff admits the "currently running recipe" race is unresolved. Propose the best achievable mitigation without a lock and state the residual risk plainly.
7. Anything in handoff.md that is wrong, contradictory, over-engineered, or missing. Be specific with line references.

Keep it tight: numbered findings, each with a one-line recommendation. No restating the handoff.
