# Codex review brief — FTP cp949 filename support

You are the reviewer. Read-only except for ONE file you write:
`./.scratch/ftp-cp949-261014/codex-review.md`. Do not edit, stage or commit
anything else. Do not ask questions; state assumptions in the review.

## The bug (office-reported 2026-10-14)

Windows equipment FTP servers send Korean filenames in cp949. `ftplib.FTP`
decodes every control/data line with `encoding` (default `utf-8`, strict), so
one Korean name in a directory raises `UnicodeDecodeError` inside `nlst()` and
the whole listing is recorded as a failure. Commands (`RETR`/`SIZE`/`STOR`)
are encoded with the same codec, so a known Korean path RETRs as 550.
Both transports share `FtpFleetDownloader._session()`, so proxy AND direct
were broken.

## The change

An `encoding` knob, default `utf-8` everywhere (= previous behaviour):

1. Vendored library — two copies that must stay identical:
   - this worktree: `ftp_handler/` (diff: `git diff main -- ftp_handler`)
   - upstream canonical: `/Users/daeyoung/Codes/flask_modules/ftp_handler/`
     (uncommitted: `git -C /Users/daeyoung/Codes/flask_modules diff`), plus its
     tests `tests/test_ftp_encoding.py` (new, real cp949 FTP server on
     loopback) and the FakeFTP signature updates in `tests/test_ftp_*.py`.
   Touched: `direct_downloader/fleet_downloader.py` (`__init__`, `_session`),
   `core/client.py` (`FtpClient`), `proxy/proxy_downloader.py` (sends
   `"encoding"` in `_tuning()`), `proxy/flask_proxy.py` (reads
   `body.get("encoding", "utf-8")`).
2. SKEWNONO callers: `backend/msr_image/config.py` (`ftp_encoding`,
   env `SKEWNONO_TOOL_FTP_ENCODING`, unknown codec -> warn + utf-8),
   `backend/msr_image/providers/office_example.py` and
   `backend/ebeam/recipe_search/providers/office_example.py` pass it through.
   Tests: `backend/msr_image/tests/test_config.py`,
   `backend/msr_image/tests/test_office_template.py`,
   `tests/test_vendored_ftp_handler.py` (fake signature).
3. Docs: `backend/.env.example`, `backend/msr_image/MIGRATION.md`,
   `docs/deployment-ftp-proxy.md`.

## What matters most: do NOT harm existing operations

`flask_modules/ftp_handler` is used by other projects and by a proxy host
(fileloader webapp) that is deployed separately from its clients. Hunt for:

- Any path where behaviour changes when nobody sets `encoding`.
- Version skew: new client -> old proxy, old client -> new proxy. Does any
  combination crash, 4xx/5xx, or silently change results?
- Positional-arg or subclass breakage from the new parameter (constructor
  argument order, `**kwargs` wrappers `download_fleet`/`list_fleet`/
  `size_fleet`/`upload_fleet`/`collect_fleet`, anything that constructs `FTP`
  or monkeypatches it).
- ftplib semantics: is the codec really honoured for the data connection
  (`retrlines`), for `mlsd`, for `LIST` parsing in `FtpClient.list_details`,
  for STOR paths? Anything still hard-coded to utf-8/latin-1?
- Error isolation: can a bad `encoding` value from the wire (proxy body is
  untrusted JSON) crash the request instead of being a per-host failure?
- Anything the SKEWNONO-side tests or the new loopback test fail to prove.

## Verify commands (run what your sandbox allows)

```bash
# upstream
cd /Users/daeyoung/Codes/flask_modules && python3 -m unittest discover -s tests
# SKEWNONO (worktree has no .venv; use the main tree's)
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest \
  backend/msr_image backend/ebeam/recipe_search tests/test_vendored_ftp_handler.py -q
diff -rq --exclude=__pycache__ ftp_handler /Users/daeyoung/Codes/flask_modules/ftp_handler
```

## Output format (`codex-review.md`)

Korean is fine. Verdict line first: `SHIP` / `FIX-THEN-SHIP` / `BLOCK`.
Then findings, each tagged `blocker` / `should` / `nit`, with `file:line`, the
concrete failing input or deployment combination, and a suggested fix. Finish
with a short "checked and fine" list so I know what you covered.
