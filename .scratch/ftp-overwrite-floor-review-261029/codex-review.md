Reviewed commit `8dc1009eeae47816b998b6ea44a5728991380248`, including the direct client, proxy transport/route, changed tests, and the named bulk-copy caller.

### [blocker] An undecodable DELE reply can cause both copies to be deleted
- where: ftp_handler/core/client.py:470-484
- failing input: `put("/rcp/a.rcp", b"new", overwrite=True)` with an existing target. The server executes DELE, but reading its reply raises `UnicodeDecodeError`. `deleted` is still false, so the generic handler calls `_drop_temp`; if that DELE succeeds, both the original and replacement are gone, and the exception has no `temp_path`. This affects direct and proxy calls. The new tests cover a refused DELE and a lost rename reply, but not an executed DELE whose reply cannot be decoded.
- fix: Treat an undecodable DELE reply as an uncertain outcome: discard the connection, keep/name the temp, and raise `TransferUncertain`. Add a test that removes the target before raising the decode error and asserts the replacement survives.

### [blocker] An older proxy can recreate the protected floor
- where: ftp_handler/proxy/proxy_client.py:326-328, ftp_handler/proxy/proxy_client.py:301-305
- failing input: Against the parent commit's proxy, call `mkdir("/CLS/data", floor="/CLS/data")` with `/CLS` present and `/CLS/data` missing. The old route ignores `floor`, its single MKD creates `/CLS/data`, and `{ok: true}` is accepted. This is a real caller shape: `bulk_recipe_copy/backend/transfer.py:221` passes `parent == data_dir` for a `.idw` directly under `data/`; the directory can disappear after the caller's existence check. The claimed mixed-version behavior therefore fails open.
- fix: Verify support for `floor` before sending a mutating request with that option, and reject unsupported proxies. Add a mixed-version test with a missing floor and `remote_dir == floor`.

### [blocker] Counting floor components does not enforce the protected path boundary
- where: ftp_handler/core/client.py:528-534
- failing input: With `/CLS/data` present, `mkdir("/CLS/data/../../NEW", floor="/CLS/data")` issues MKD for `/CLS/data/..` and `/CLS/data/../..`, which name ancestors of the floor, then creates `/NEW`. The floor depth merely skips the first two textual components. Likewise, an unrelated floor is never checked for ancestry, and mixed absolute/relative paths are compared only by depth. The proxy forwards these inputs unchanged.
- fix: Reject `..` components and require the floor to be the same path or an actual component prefix under the same absolute/relative base before any MKD. Add boundary tests for traversal, unrelated floors, and mixed path bases.

### [should] A target equal to the floor succeeds without proving it is a directory
- where: ftp_handler/core/client.py:530-531
- failing input: `mkdir("/CLS/data/", floor="/CLS/data")` returns normally when `/CLS/data` is absent or is a regular file: `start == len(parts)`, so no command runs. This violates mkdir's directory-success contract on both transports. An unrelated floor with at least as many components also silently skips all work.
- fix: After validating the floor relationship, use the existing CWD-and-restore probe when no creation levels remain; raise if the target is not a directory, while never MKD-ing the floor. Add missing-target and regular-file tests for this no-iteration case.

Validation: the permitted unittest command passed all 89 tests, with bytecode writes disabled. Findings above are source traces; no additional fault-injection cases or live FTP/proxy deployments were run. No repository files were changed.

Verdict: Fix the data-loss path and floor enforcement before shipping.

## 2차 확인

Reviewed `52efc28b063ca398de01bb7d168947c6a0a8e052` against the four findings.

- 1. RESOLVED — `ftp_handler/core/client.py:494-508` preserves the temp, discards the connection, and raises `TransferUncertain` for an undecodable DELE reply; the added test applies DELE before raising.
- 2. RESOLVED — `ftp_handler/proxy/proxy_client.py:334` sends `makedirs`; the pre-mkdir-p route rejects that unknown operation before any mutation, and its `bad_request` becomes `ProxyError`. Capability negotiation is unnecessary for this fix.
- 3. OPEN — `ftp_handler/core/client.py:73-82` still accepts `mkdir("/CLS/data/./child", floor="/CLS/data")`, whose first MKD is `/CLS/data/.`, the protected floor itself; remove `.` components from both paths before prefix comparison and level construction. The original `..`, unrelated-floor, and mixed-base cases are fixed.
- 4. RESOLVED — `ftp_handler/core/client.py:568-572` now probes equal-floor targets and raises 550 for a missing target or regular file without issuing MKD.

### [should] Root mkdir's new directory probe exceeds the proxy's reply budget
- where: ftp_handler/core/client.py:568-570; ftp_handler/proxy/proxy_client.py:302-305
- failing input: Proxied `mkdir("/", floor="/")` with `timeout=1` and an FTP server taking 0.9 seconds per reply, including normal USER/PASS login. The new zero-level branch needs six replies: banner, USER, PASS, PWD, CWD /, CWD back. Each FTP wait is valid, but the HTTP read budget is only `(3 + max(1, 4 * 0) + 1) * timeout = 5` seconds, so the proxy client raises `ProxyError` before the 5.4-second operation finishes. Direct mode succeeds; before this commit the zero-level branch did not probe.
- fix: Budget at least three operation replies for a zero-level `makedirs` probe, in addition to login and existing slack. Add a root-path timeout-budget assertion.

Validation: all 94 tests passed using the same permitted unittest command with bytecode writes disabled. Remaining cases are source traces; no live FTP/proxy or additional fault-injection runs. No repository files changed.

Verdict: Findings 1, 2, and 4 are resolved; finish the `.` floor case and root-probe timeout budget.

## 3차 확인

Reviewed `1ea1b6fb80ffdb8c5420e7b8f2b8f5aec15ed2de`.

- Finding 3: RESOLVED — `ftp_handler/core/client.py:74-78` removes `.` components from both paths before level construction and prefix comparison; `/CLS/data/./child` now attempts only `/CLS/data/child` below the floor, with a regression assertion on the actual MKD arguments.
- Root-budget finding: RESOLVED — `ftp_handler/proxy/proxy_client.py:303-305` budgets at least one level for `makedirs`, giving the root probe eight timeout units including slack, sufficient for its six replies; the added test checks the HTTP read budget.

No new correctness issue found in this commit. All 96 tests passed using the same permitted unittest command with bytecode writes disabled. No repository files changed; live FTP/proxy behavior was not checked.

Verdict: Both remaining findings are resolved; no further changes requested within this review scope.
