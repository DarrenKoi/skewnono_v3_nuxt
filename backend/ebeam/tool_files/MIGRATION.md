# tool_files — office migration

## Status: WRITTEN — activate by copying

The template opens a direct `ftp_handler.core.FtpClient` to the tool on
Linux (Phase 3) and the read-only `ftp_handler.proxy.FtpClient` on Windows
(Phase 2) and reads the real member directory. It holds no in-house value, so
the copy is verbatim:

```bash
cp providers/office_example.py providers/office.py
```

- `office.py` is gitignored and a **copy**. Refresh it after a `git pull` that
  moves the template, or the boot log reports `STALE office.py: tool_files`.
  A copy older than 2026-10-20 imports the removed grant/request types and
  stops the app from booting: refresh it in the same pull.
- It pairs with `sem_list`: every tool's IP and FTP account come from the
  live roster, so `validate_env()` refuses tool_files=office with
  sem_list=mock rather than send real credentials to fabricated addresses.
- `validate_env()` also refuses tool_files=office when the mode is not office
  (the member directory follows the mode, so every team verdict would be
  `directory_unavailable`) and when `REDIS_HOST` is unset (the directory).
- Never touch `routes.py`, `data.py`, `providers/mock.py`, `contracts.py`, or
  `tests/`.

## What swaps

Two surfaces, chosen together by one provider resolution:

| surface | mock | office |
| :-- | :-- | :-- |
| FTP (`open_client`, `transport_supports_write`) | fake tree, writable | direct `FtpClient` (writable) on Linux; proxy `FtpClient` (read-only) on Windows |
| directory (`probe`) | `_MEMBERS` table | `probe_member`, 600 s cache |

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
| `SKEWNONO_TOOL_FILES_MAX_BYTES` | 100 MB per download; a zip download spends it on all its files together |
| `SKEWNONO_TOOL_FILES_DEADLINE` | 120 s per transfer, and for a whole zip download (cloud harakiri is 720 s) |
| `SKEWNONO_TOOL_FILES_MAX_BATCH_FILES` | 200 files per zip download |
| `SKEWNONO_TOOL_FILES_MAX_CONCURRENT_FTP` | 2 FTP sessions (list, download, upload, delete) at a time per process; the next gets 503 `ftp_busy` at once |
| `SKEWNONO_TOOL_FILES_MAX_CONCURRENT_TRANSFERS` | 1 download at a time per process, held until the response is fully sent; the next gets 503 `transfers_busy` at once. With the FTP cap, at most 3 of a process's 4 uWSGI threads (12 of 16 on the cloud) are ever tool-files work |
| `SKEWNONO_TOOL_FILES_PROXY_DEADLINE` | 45 s per transfer through the proxy (each file of a zip is one) (proxy host harakiri 60 s, OFFICE-VERIFY on scheduler1) |
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
  then the listing). `home` is a PWD only (`home_only`), never a LIST of the
  home folder, and waits at most twice the tool timeout. Proxy failures
  (unreachable, 401, missing route, 5xx, a request the proxy cannot parse)
  answer `503 tool_unreachable`; names the tool encoding cannot decode answer
  `502 tool_encoding`, as on the direct path.
- **Access** is the admin, or a caller whose directory `dept_nm` is one of
  `access.ALLOWED_TEAMS` (DRAM MI개발, NAND MI개발, DRAM Metrology기술, NAND
  Metrology기술, 기반기술전략; user-confirmed 2026-10-20). There is no grant or request
  flow: changing who gets in is a code change. A team move reaches the
  verdict up to 10 minutes late (the directory cache). The Redis hashes
  `skewnono:tool_files:grants` and `skewnono:tool_files:requests` the earlier
  template wrote are no longer read; delete them once at the office.
- Listing and download reach any path under `/`; a listing with no `path`
  opens at the login directory (`PWD`, returned as `home`). Upload and delete
  stay confined to the login directory. Per-family allowed roots are not
  configurable yet; add them when a real tree shows the need.
- The path check is a guardrail. The FTP account's own permissions are the
  boundary: a symlinked middle folder can lead outside the root, and LIST
  cannot say where it points. Link entries are hidden from listings; a
  hand-written URL to a link is not separately refused.

## Phase 2 rollout order

The Windows PC needs proxy routes that only exist after the proxy host pulls,
so the order is fixed:

1. `flask_modules`: push (`ftp_handler/proxy`: `list_details_sknn_v3`,
   `fetch_sknn_v3`, and since 2026-10-17 the `home_only` mode and the
   `encoding` error code).
2. `skewnono-scheduler1-webapp`: `git pull` flask_modules, then restart the
   webapp. Check `POST /list_details_sknn_v3` no longer answers 404.
3. SKEWNONO on the Windows PC: `git pull`, then refresh the copy
   (`cp providers/office_example.py providers/office.py`).

Pulling SKEWNONO before step 2 is harmless but useless: every listing answers
`503 tool_unreachable` (the proxy's 404 is a `ProxyError`). A proxy host
pulled before 2026-10-17 ignores `home_only` and still LISTs the home folder
on every request, now cut off at twice the tool timeout (`503
tool_unreachable`), and answers an encoding error as `503` rather than `502
tool_encoding`: pull it again.

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
      보낼 수 없어 400 `name_unencodable`로 거절합니다. 한글 이름 업로드가 필요한지 정합니다.
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
- [ ] The directory's `dept_nm` for each allowed team is spelled exactly
      as `access.ALLOWED_TEAMS` (no `팀` suffix, same spacing and case). Fix
      the tuple and the mock `_MEMBERS` if not.
- [ ] Open the page as a member of one team (explorer opens) and as someone
      outside them (the team notice, and `list` answers 403).
