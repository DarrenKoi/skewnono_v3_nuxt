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
| requests (`read_requests`, `put_request`, `approve_request`, `reject_request`, `approve_team`) | sibling `requests.json` beside the grants file, same lock, atomic replace and unreadable = 503 | HASH `skewnono:tool_files:requests`, `<empno>` -> JSON `{request_id, reason, dept_nm, requested_at, status}`; approve/reject/team approve under `WATCH` -> compare `request_id` -> `MULTI` -> `EXEC` |
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
| `SKEWNONO_TOOL_FILES_MAX_UPLOAD_BYTES` | 100 MB per upload (Content-Length checked before parsing, bytes read counted again) |

Writes: `SKEWNONO_TOOL_FILES_WRITE` (default off; `1`/`true`/`yes`/`on` turn
it on). `can_write` in `GET .../tool-files/access` is
`flag ∧ is_admin_request() ∧ transport_supports_write()`. A write request is
refused in that order, before its body is read or FTP opens: 403
`write_disabled`, 403 `forbidden`, 501 `write_not_supported`. Upload uses
`FtpClient.put` (temp name, then RNFR/RNTO, never overwrites: 409
`file_exists`; a lost RNTO reply is 503 `transfer_uncertain`), delete uses
`FtpClient.remove`. Both log one `skewnono.tool_files` line with actor,
identity source, target, result and request_id.

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
  minutes late (the directory cache).
- **Access requests.** Only a cookie or local identity may ask; the body
  carries `reason` (1-200 characters) and nothing else, so the empno and the
  stored `dept_nm` are the server's. Each (re)request gets a new uuid4
  `request_id`, the token approve and reject compare: a different or missing
  one is 409 `request_changed`, except an approval retry whose grant already
  exists (no-op). A `WatchError` is caught before `STORE_ERRORS`; a change to
  that empno's request is 409, any other is retried up to three times, then
  503. Team approval clears only the pending requests whose *stored*
  `dept_nm` is the team. Request, approve, reject and team approve each log
  one `skewnono.tool_files` line carrying the access `request_id`.
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

## 플래그를 켜기 전 확인할 조건

`SKEWNONO_TOOL_FILES_WRITE`는 아래 항목을 계열마다 office에서 확인한 뒤에 켭니다.
모두 `OFFICE-VERIFY`입니다.

- [ ] **RNTO 동작.** 대상 이름에 파일이 이미 있을 때 서버가 RNTO를 거절하는지,
      덮어쓰는지 확인합니다. 같은 이름의 폴더가 있을 때의 동작도 봅니다. `put`의
      덮어쓰기 거부는 SIZE 확인에 기대는 best-effort이고, writer가 한 명이라는
      전제 위에서만 성립합니다.
- [ ] **SIZE 응답.** 없는 파일에 SIZE를 보내면 550이 오는지 확인합니다. 다른 코드가
      오면 `put`이 모든 업로드를 거절합니다.
- [ ] **서버 측 쓰기 범위 제한.** 장비 FTP 계정이 로그인 루트 밖에 쓸 수 없도록
      chroot나 계정 권한으로 제한되어 있는지 확인합니다. 경로 검사는 가드레일일
      뿐이고, 링크로 된 중간 폴더는 잡지 못합니다.
- [ ] **임시 파일.** 업로드가 끊기면 `<이름>.<난수>.part`가 남을 수 있습니다. 장비
      소프트웨어가 이런 파일을 레시피나 로그로 잘못 읽지 않는지 확인합니다.
- [ ] **파일 이름 인코딩.** `SKEWNONO_TOOL_FTP_ENCODING=latin-1`에서는 한글 이름을
      보낼 수 없어 400 `bad_path`로 거절합니다. 한글 이름 업로드가 필요한지 정합니다.
- [ ] **transport.** proxy(Windows office PC)에서는 `transport_supports_write()`가
      거짓이어야 합니다(ticket 06). 화면에 업로드·삭제가 보이지 않는지 확인합니다.
- [ ] **운영 확인.** 작은 파일 하나를 올리고, 목록에 보이는지, 같은 이름이 409인지,
      삭제하면 사라지는지 봅니다. 감사 로그 한 줄이 OpenSearch에 남는지도 확인합니다.

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
- [ ] **Real WATCH/MULTI races** (not runnable at home: the fake can only
      stage a `WatchError`). Open two Redis connections and replay each pair:
      approve ↔ re-request, reject ↔ re-request, team approve ↔ an empno
      approval or a re-request. Each must end in 409 or a clean retry, never a
      grant for a request the admin did not see.
- [ ] Request from a browser as a non-admin member, approve it on
      `/admin/access`, and the next page load opens the explorer. Check the
      request and approve lines reach OpenSearch.
