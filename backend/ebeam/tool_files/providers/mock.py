"""Home adapter: a fake tool FTP server with ``core.FtpClient``'s surface.

Stands in for the server, not for the routes, so resolution, path checks and
error mapping run for real at home.

The folder layout is fabricated (OFFICE-VERIFY: no tool's real tree has been
listed from home). What it copies on purpose are the properties known to bite:

- filenames whose bytes are not UTF-8, as they arrive under
  ``SKEWNONO_TOOL_FTP_ENCODING=latin-1`` (office 확인 2026-10-14: tool
  filenames are corrupted bytes, not cp949);
- an empty folder, a folder of thousands of files, a file over the download
  cap, a symlink entry;
- a login directory that is not ``/`` (HV-SEM here, OFFICE-VERIFY);
- tools that never answer: every sem_list row with ``available == "Off"``.

The mock never opens a socket. ``put`` and ``remove`` really change the tree
(module-level ``_TREE``, so a write is seen by the next request until the
process restarts); ``put`` onto an existing name raises ``TargetExists`` as
``core.FtpClient.put`` does. It never raises ``TransferUncertain``: that needs
a lost RNTO reply, which only a real server can lose.

It also carries this feature's two other swap surfaces, so one provider choice
decides all three:

- **Grant store.** A JSON file (``SKEWNONO_TOOL_FILES_GRANTS_FILE``, default
  ``state/grants.json``), read on every call so a grant made in one worker is
  seen by the next request in any other, and written by atomic replace. Unlike
  access_control's mock, an unreadable file is 503, never an empty store.
- **Member directory.** ``_auth.directory.probe_member`` is ``unavailable`` at
  home by design, so team grants would be untestable here. ``_MEMBERS`` stands
  in: two teams, a profile with no dept_nm, and a directory outage; every
  other empno is absent. The names are placeholders (OFFICE-VERIFY: real
  dept_nm spellings are unknown from home).
"""

import json
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ftplib import error_perm
from pathlib import Path
from threading import Lock

from ftp_handler.core import FileInfo, ListingTooLarge, TargetExists, TransferTooLarge

from backend._auth.directory import Probe
from backend.ebeam.tool_files.contracts import Grant, Teams
from backend.ebeam.tool_files.errors import StoreUnavailable
from backend.ebeam.tool_files.resolve import Tool
from backend.sem_list.providers.mock import get_sem_list

_KST = timezone(timedelta(hours=9), "KST")
_NEWEST = datetime(2026, 10, 16, 18, 0, tzinfo=_KST)
_HOME = {"hv-sem": "/home/hitachi"}


@dataclass(frozen=True, slots=True)
class _File:
    size: int
    age_hours: int
    link: bool = False
    # Uploaded bytes; fabricated files have none and download as filler.
    data: bytes | None = None


def _korean_as_latin1(name: str) -> str:
    return name.encode("utf-8").decode("latin-1")


def _tree() -> dict:
    log = {"ARCHIVE": {}}
    for n in range(3000):
        log[f"EVENT_202610{n % 16 + 1:02d}_{n:04d}.log"] = _File(2_000 + n * 7 % 5_000, n)
    recipe = {"CURRENT": _File(16, 1, link=True)}
    for n in range(1, 13):
        recipe[f"RCP_{n:03d}.rcp"] = _File(4_096 * n, 24 * n)
    return {
        "DUMP": {
            "core_full.bin": _File(150 * 1024 * 1024, 30),
            "small.bin": _File(2_048, 30),
        },
        "LOG": log,
        "RECIPE": recipe,
        "README.TXT": _File(512, 2_000),
        _korean_as_latin1("측정결과.csv"): _File(1_234, 5),
    }


_TREE = _tree()


def _unreachable(eqp_id: str) -> bool:
    return any(r["eqp_id"] == eqp_id and r["available"] == "Off" for r in get_sem_list())


class MockFtpClient:
    def __init__(self, tool: Tool) -> None:
        self._tool = tool
        self._home = _HOME.get(tool.tool_type, "/")

    def __enter__(self) -> "MockFtpClient":
        if _unreachable(self._tool.eqp_id):
            raise TimeoutError(f"{self._tool.host}:21 timed out")
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def home(self) -> str:
        return self._home

    def _node(self, path: str):
        if path != self._home and not path.startswith(self._home.rstrip("/") + "/"):
            raise error_perm(f"550 {path}: No such file or directory")
        node = _TREE
        for part in [p for p in path[len(self._home):].split("/") if p]:
            if not isinstance(node, dict) or part not in node:
                raise error_perm(f"550 {path}: No such file or directory")
            node = node[part]
        return node

    def list_details(self, remote_dir, pattern=None, *, max_entries=None, **_limits):
        node = self._node(remote_dir)
        if not isinstance(node, dict):
            raise error_perm(f"550 {remote_dir}: Not a directory")
        if max_entries is not None and len(node) > max_entries:
            raise ListingTooLarge(f"{remote_dir} has over {max_entries} LIST lines")
        dirs = sorted(name for name, child in node.items() if isinstance(child, dict))
        files = sorted(name for name, child in node.items() if not isinstance(child, dict))
        base = remote_dir.rstrip("/")
        out = []
        for name in dirs + files:
            child = node[name]
            is_dir = isinstance(child, dict)
            out.append(
                FileInfo(
                    name=name,
                    path=f"{base}/{name}",
                    is_dir=is_dir,
                    size=None if is_dir else child.size,
                    modified=_NEWEST - timedelta(hours=0 if is_dir else child.age_hours),
                    raw="",
                    is_link=not is_dir and child.link,
                )
            )
        return out

    def download(self, remote_path, *, max_bytes=None, **_limits) -> bytes:
        node = self._node(remote_path)
        if isinstance(node, dict):
            raise error_perm(f"550 {remote_path}: Is a directory")
        if max_bytes is not None and node.size > max_bytes:
            raise TransferTooLarge(f"{remote_path} exceeds {max_bytes} bytes")
        if node.data is not None:
            return node.data
        line = f"mock {remote_path}\n".encode("utf-8")
        return (line * (node.size // len(line) + 1))[: node.size]

    def _folder_of(self, remote_path: str) -> tuple[dict, str]:
        folder, name = remote_path.rsplit("/", 1)
        node = self._node(folder or "/")
        if not isinstance(node, dict):
            raise error_perm(f"550 {folder}: Not a directory")
        return node, name

    def put(self, remote_path, data, *, deadline=None) -> None:
        node, name = self._folder_of(remote_path)
        if name in node:
            raise TargetExists(remote_path)
        node[name] = _File(len(data), 0, data=data)

    def remove(self, remote_path) -> None:
        node, name = self._folder_of(remote_path)
        if not isinstance(node.get(name), _File):
            raise error_perm(f"550 {remote_path}: No such file")
        del node[name]


def open_client(tool: Tool) -> MockFtpClient:
    return MockFtpClient(tool)


def transport_supports_write() -> bool:
    # The fake tree stands in for a direct connection.
    return True


def _profile(empno: str, emp_nm: str, dept_nm: str | None) -> Probe:
    member = {
        "empno": empno,
        "emp_nm": emp_nm,
        "dept_nm": dept_nm,
        "organ_cd": None,
        "upper_organ_nm": None,
    }
    return Probe(member, "found")


_MEMBERS: dict[str, Probe] = {
    "1000001": _profile("1000001", "김계측", "계측기술팀"),
    "1000002": _profile("1000002", "이계측", "계측기술팀"),
    "1000003": _profile("1000003", "박공정", "공정기술팀"),
    "1000004": _profile("1000004", "최무소속", None),
    "1000005": Probe(None, "unavailable"),
}


def probe(empno: str) -> Probe:
    return _MEMBERS.get(empno, Probe(None, "absent"))


def teams() -> Teams:
    counts = Counter(
        p.member["dept_nm"] for p in _MEMBERS.values() if p.member and p.member["dept_nm"]
    )
    return {
        "teams": [{"dept_nm": d, "members": n} for d, n in sorted(counts.items())],
        "complete": True,
    }


_lock = Lock()


def _grants_path() -> Path:
    override = os.environ.get("SKEWNONO_TOOL_FILES_GRANTS_FILE")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "state" / "grants.json"


def _read(path: Path) -> dict[str, Grant]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise StoreUnavailable(f"grant file unreadable: {path}") from exc
    if not isinstance(raw, dict) or not all(isinstance(v, dict) for v in raw.values()):
        raise StoreUnavailable(f"grant file is not a JSON object of grants: {path}")
    return raw


def _write(path: Path, grants: dict[str, Grant]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".grants.")
    except OSError as exc:
        raise StoreUnavailable(f"grant file not writable: {path}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(grants, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        Path(tmp).unlink(missing_ok=True)
        raise StoreUnavailable(f"grant file not writable: {path}") from exc


def read_grants() -> dict[str, Grant]:
    return _read(_grants_path())


def put_grant(key: str, grant: Grant) -> Grant:
    """Idempotent: a repeat grant keeps the first one's stamp."""
    path = _grants_path()
    with _lock:
        grants = _read(path)
        if key not in grants:
            grants[key] = grant
            _write(path, grants)
        return grants[key]


def delete_grant(key: str) -> bool:
    path = _grants_path()
    with _lock:
        grants = _read(path)
        if grants.pop(key, None) is None:
            return False
        _write(path, grants)
        return True
