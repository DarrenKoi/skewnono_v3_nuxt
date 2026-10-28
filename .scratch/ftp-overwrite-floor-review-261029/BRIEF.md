# Review brief: put(overwrite=) and mkdir -p with floor=

Repo: `/Users/daeyoung/Codes/flask_modules` (upstream of a vendored `ftp_handler/`).
Commit under review: `8dc1009`. Read it with
`git -C /Users/daeyoung/Codes/flask_modules show 8dc1009`.

## What the change claims

`ftp_handler/core/client.py` `FtpClient`:

- `put(remote_path, data, *, deadline=None, overwrite=False)`. Default unchanged
  (no-clobber: temp `.part` STOR, then RNTO; `TargetExists` if the target exists).
  `overwrite=True`: temp STOR, then DELE the old target if present, then RNTO.
  Once the DELE has run, a failed rename must KEEP the temp (it is the only copy)
  and name it as `exc.temp_path` + a `__notes__` entry; a lost reply (OSError /
  EOFError) is `TransferUncertain(temp_path=...)`. A refused DELE keeps the old
  target and drops the temp.
- `mkdir(remote_dir, *, floor=None)` is now `mkdir -p` (was: one MKD, 550 only).
  One MKD per level; any `error_perm` is settled by `_is_dir` (CWD in, CWD back to
  PWD; discards the connection if a CWD fails other than by refusal). `floor` and
  every level above it are never MKD'd.
- The proxy client (`ftp_handler/proxy/proxy_client.py`) and route
  (`ftp_handler/proxy/flask_proxy.py` `_write`) pass `overwrite` and `floor`
  through; the client's HTTP wait for mkdir scales with path depth.

Context: the only real caller is a separate app (`/Users/daeyoung/Codes/bulk_recipe_copy`,
`backend/transfer.py` ~line 220) that calls
`ftp.mkdir(parent, floor=None if may_create_class else data_dir)` then
`ftp.put(path, data, overwrite=overwrite, deadline=...)`. The floor exists so a
class folder the user did not allow to be created is never recreated.

## What to look for (correctness only)

1. Data loss or a wrong outcome in `put(overwrite=True)`: any failure point where
   neither the old nor the new content survives, or the temp is deleted / leaked
   wrongly, or the exception does not say where the data is.
2. `mkdir` + `floor`: any input that MKDs the floor or above it (relative paths,
   trailing slashes, `floor="/"`, floor not a prefix of `remote_dir`, `..`), or
   reports success for a level that is not a directory; session-directory safety
   after probes.
3. Parity between direct and proxy for the new options; what an older proxy does
   with them (claimed: fails closed).
4. Tests that pass by construction or would not fail if the logic broke.

Out of scope: style, naming, docs wording, unrelated pre-existing code.

## Rules

- Read-only. Do not edit, stage or commit anything in any repo.
- You may run: `cd /Users/daeyoung/Codes/flask_modules && /Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m unittest tests.test_ftp_client tests.test_ftp_client_put tests.test_ftp_proxy_client -v`
- Read only what you need.

## Output

Write the review to
`/private/tmp/claude-501/-Users-daeyoung-Codes-skewnono-v3-nuxt/def2b18b-fdf4-4115-b069-8862d3550838/scratchpad/codex-review-overwrite-floor.md`,
at most ~100 lines. One entry per finding:

```
### [blocker|should|nit] <one-line claim>
- where: file:line
- failing input: <concrete call/state -> wrong result>
- fix: <one or two lines>
```

End with a one-line verdict. If there is nothing real, say so — do not pad.
