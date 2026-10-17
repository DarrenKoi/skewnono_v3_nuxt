# tool_files — office migration

## Status: WRITTEN — activate by copying

The template opens a direct `ftp_handler.core.FtpClient` to the tool on
Linux (Phase 3) and the read-only `ftp_handler.proxy.FtpClient` on Windows
(Phase 2), keeps grants in Redis and reads the real member directory. It holds no in-house
value, so the copy is verbatim:

```bash
cp providers/office_example.py providers/office.py
```

- `office.py` is gitignored and a **copy**. Refresh it after a `git pull` that
  moves the template, or the boot log reports `STALE office.py: tool_files`.
- It pairs with `sem_list`: every tool's IP and FTP account come from the
  live roster, so `validate_env()` refuses tool_files=office with
  sem_list=mock rather than send real credentials to fabricated addresses.
- `validate_env()` also refuses tool_files=office when the mode is not office
  (the member directory follows the mode, so every team verdict would be
  `directory_unavailable`) and when `REDIS_HOST` is unset (the grant store).
- Never touch `routes.py`, `data.py`, `providers/mock.py`, `contracts.py`, or
  `tests/`.

## What swaps

Three surfaces, chosen together by one provider resolution, so "real FTP +
mock grants" cannot happen:

| surface | mock | office |
| :-- | :-- | :-- |
| FTP (`open_client`, `transport_supports_write`) | fake tree, writable | direct `FtpClient` (writable) on Linux; proxy `FtpClient` (read-only) on Windows |
| grants (`read_grants`, `put_grant`, `delete_grant`) | `state/grants.json` (`SKEWNONO_TOOL_FILES_GRANTS_FILE`), unreadable = 503 | HASH `skewnono:tool_files:grants`, `"team:<dept_nm>"` / `"emp:<empno>"` -> JSON `{granted_at, granted_by}` |
| directory (`probe`, `teams`) | `_MEMBERS` table | `probe_member` + HSCAN of `members`, 600 s cache |

Resolution, path checks, the verdict (`access.decide`) and the error mapping
are shared code, so the mock exercises them exactly as the office does.

## Configuration

Reused from msr_image, nothing new to set: `SKEWNONO_TOOL_FTP_USER`,
`SKEWNONO_TOOL_FTP_PASSWORD`, `SKEWNONO_TOOL_FTP_PORT`,
`SKEWNONO_TOOL_FTP_TIMEOUT`, `SKEWNONO_TOOL_FTP_ACCOUNTS` (per eqp_id /
fab_name / family) and `SKEWNONO_TOOL_FTP_ENCODING` (`latin-1` at the office).

Transfer limits, all OFFICE-VERIFY proposals:

| env | default |
| :-- | :-- |
| `SKEWNONO_TOOL_FILES_MAX_BYTES` | 100 MB per download |
| `SKEWNONO_TOOL_FILES_DEADLINE` | 120 s per transfer (cloud harakiri is 720 s) |
| `SKEWNONO_TOOL_FILES_PROXY_DEADLINE` | 45 s per transfer through the proxy (proxy host harakiri 60 s, OFFICE-VERIFY on scheduler1) |
| `SKEWNONO_TOOL_FILES_MAX_ENTRIES` | 20000 raw LIST lines |
| `SKEWNONO_TOOL_FILES_MAX_LIST_BYTES` | 4 MB of raw LIST |

## Known limits

- **Phase 2 (Windows) is read-only.** A Windows office PC cannot open FTP to
  tools, so it lists and downloads through the shared FTP proxy
  (`skewnono-scheduler1-webapp`) and `transport_supports_write()` is false.
  The proxy has no auth and no write route by design. Each call is one HTTP
  request and one fresh FTP connection, so a page view costs two (`home`,
  then the listing). Proxy failures (unreachable, 401, missing route, 5xx)
  answer `503 tool_unreachable`.
- **Access** is the admin, an `emp:` grant, or a `team:` grant matching the
  caller's directory `dept_nm`. A team move reaches the verdict up to 10
  minutes late (the directory cache). Access requests arrive in ticket 05.
- The root is the login directory (`PWD`). Per-family allowed roots are not
  configurable yet; add them when a real tree shows the need.
- The root check is a guardrail. The FTP account's own permissions are the
  boundary: a symlinked middle folder can lead outside the root, and LIST
  cannot say where it points. Link entries are hidden from listings; a
  hand-written URL to a link is not separately refused.

## Phase 2 rollout order

The Windows PC needs proxy routes that only exist after the proxy host pulls,
so the order is fixed:

1. `flask_modules`: push (`ftp_handler/proxy`: `list_details_sknn_v3`,
   `fetch_sknn_v3`).
2. `skewnono-scheduler1-webapp`: `git pull` flask_modules, then restart the
   webapp. Check `POST /list_details_sknn_v3` no longer answers 404.
3. SKEWNONO on the Windows PC: `git pull`, then refresh the copy
   (`cp providers/office_example.py providers/office.py`).

Pulling SKEWNONO before step 2 is harmless but useless: every listing answers
`503 tool_unreachable` (the proxy's 404 is a `ProxyError`).

## Verify at the office

- [ ] One tool per family: list the login directory, open a subfolder,
      download a file, download a file whose name is corrupted bytes.
- [ ] Note each family's real login directory and folder layout, then update
      `providers/mock.py` to match.
- [ ] A file over 100 MB answers 413 and the worker stays healthy.
- [ ] Phase 2 (Windows PC, after the rollout above): list and download from
      one tool per family through the proxy; a slow transfer stops at 45 s
      with `503 tool_timeout`, not a proxy 502; msr_image images and
      recipe_search raw files still load through the proxy.
- [ ] `/admin/access` team list: counts look right, `complete` is true, and
      the real `dept_nm` spellings match what grants will be keyed on. Update
      the mock `_MEMBERS` names to the real shape.
- [ ] Grant a team, open the browser as one of its members; revoke, and the
      next request is 403.
