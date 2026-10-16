# tool_files — office migration

## Status: WRITTEN — activate by copying

The template opens a direct `ftp_handler.core.FtpClient` to the tool, so the
copy is verbatim:

```bash
cp providers/office_example.py providers/office.py
```

- `office.py` is gitignored and a **copy**. Refresh it after a `git pull` that
  moves the template, or the boot log reports `STALE office.py: tool_files`.
- It pairs with `sem_list`: every tool's IP and FTP account come from the
  live roster, so `validate_env()` refuses tool_files=office with
  sem_list=mock rather than send real credentials to fabricated addresses.
- Never touch `routes.py`, `data.py`, `providers/mock.py`, `contracts.py`, or
  `tests/`.

## What swaps

Only the FTP connection. `data.open_client(tool)` returns a context manager
with `FtpClient`'s surface (`home`, `list_details`, `download`); resolution,
path checks and the error mapping are shared code, so the mock exercises them
exactly as the office does.

## Configuration

Reused from msr_image, nothing new to set: `SKEWNONO_TOOL_FTP_USER`,
`SKEWNONO_TOOL_FTP_PASSWORD`, `SKEWNONO_TOOL_FTP_PORT`,
`SKEWNONO_TOOL_FTP_TIMEOUT`, `SKEWNONO_TOOL_FTP_ACCOUNTS` (per eqp_id /
fab_name / family) and `SKEWNONO_TOOL_FTP_ENCODING` (`latin-1` at the office).

Transfer limits, all OFFICE-VERIFY proposals:

| env | default |
|:--|:--|
| `SKEWNONO_TOOL_FILES_MAX_BYTES` | 100 MB per download |
| `SKEWNONO_TOOL_FILES_DEADLINE` | 120 s per transfer (cloud harakiri is 720 s) |
| `SKEWNONO_TOOL_FILES_MAX_ENTRIES` | 20000 raw LIST lines |
| `SKEWNONO_TOOL_FILES_MAX_LIST_BYTES` | 4 MB of raw LIST |

## Known limits

- **Phase 3 (Linux) only.** A Windows office PC cannot open FTP to tools; until
  the proxy transport lands (ticket 06) every request there answers
  `503 tool_unreachable`.
- **Access is admin-only** until the grant store lands (ticket 04).
- The root is the login directory (`PWD`). Per-family allowed roots are not
  configurable yet; add them when a real tree shows the need.
- The root check is a guardrail. The FTP account's own permissions are the
  boundary: a symlinked middle folder can lead outside the root, and LIST
  cannot say where it points. Link entries are hidden from listings; a
  hand-written URL to a link is not separately refused.

## Verify at the office

- [ ] One tool per family: list the login directory, open a subfolder,
      download a file, download a file whose name is corrupted bytes.
- [ ] Note each family's real login directory and folder layout, then update
      `providers/mock.py` to match.
- [ ] A file over 100 MB answers 413 and the worker stays healthy.
