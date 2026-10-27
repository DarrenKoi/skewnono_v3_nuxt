# Review brief: proxy single-server FtpClient writes

Repo: `/Users/daeyoung/Codes/flask_modules` (upstream of a vendored `ftp_handler/`).
Commit under review: `be54128` ("let the proxy single-server FtpClient write").
Read it with `git -C /Users/daeyoung/Codes/flask_modules show be54128`.

## What the change claims

- `ftp_handler/proxy/proxy_client.py` `FtpClient` gains `upload`, `put`, `remove`,
  `mkdir`, `rmdir` with `ftp_handler/core/client.py` `FtpClient`'s exact signatures
  and exceptions — a call site swaps one import line and nothing else.
- `ftp_handler/proxy/flask_proxy.py` gains `POST /write_sknn_v3`, which runs
  `core.FtpClient`'s own method on a fresh connection (`_write`, via the renamed
  `_single_op`). `TargetExists` -> `"exists"`, `TransferUncertain` -> `"uncertain"`,
  and a put's leftover `temp_path` rides on the 422 body.
- `WriteNotSupported` was deleted (policy change: the client used to be read-only).
- Tests: `tests/test_ftp_proxy_client.py` runs each write direct and through the proxy
  (Flask test client) against one fake FTP and compares outcome + resulting tree.

## What to look for (correctness only)

1. Parity gaps: any input where direct and proxy differ in return value, exception
   type, exception attributes (`temp_path`, `__notes__`, the 550 prefix), or what is
   left on the server.
2. Error mapping in `_post` / `_single_op`: an exception that maps to the wrong code,
   a 422 body shape the client mis-reads, a write that can report success when it did
   not happen (e.g. a 200 that is not this route's answer).
3. Timeouts / deadlines for writes (`_post` read timeout when `deadline` is None,
   `put`'s `deadline_s`), and whether a write can hang or report a false failure.
4. Input validation on the route (`op`, `remote_path`, `data_b64`), and anything a
   malformed request can make the proxy do.
5. Tests that pass by construction or would not fail if the logic broke.

Out of scope: style, naming, docs wording, the pre-existing fleet routes.

## Rules

- Read-only. Do not edit, stage or commit anything in any repo.
- You may run: `cd /Users/daeyoung/Codes/flask_modules && /Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m unittest tests.test_ftp_proxy_client tests.test_ftp_flask_proxy tests.test_ftp_client_put -v`
- Read only what you need; do not survey the rest of the repo.

## Output

Write the review to
`/private/tmp/claude-501/-Users-daeyoung-Codes-skewnono-v3-nuxt/def2b18b-fdf4-4115-b069-8862d3550838/scratchpad/codex-review-proxy-write.md`,
at most ~100 lines. One entry per finding:

```
### [blocker|should|nit] <one-line claim>
- where: file:line
- failing input: <concrete request/state -> wrong result>
- fix: <one or two lines>
```

End with a one-line verdict. If there is nothing real, say so — do not pad.
