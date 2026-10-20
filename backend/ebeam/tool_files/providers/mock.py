"""Home adapter: a fake tool FTP server with ``core.FtpClient``'s surface.

Stands in for the server, not for the routes, so resolution, path checks and
error mapping run for real at home.

The folder layout is fabricated (OFFICE-VERIFY: no tool's real tree has been
listed from home). What it copies on purpose are the properties known to bite:

- filenames whose bytes are not UTF-8, as they arrive under
  ``SKEWNONO_TOOL_FTP_ENCODING=latin-1`` (office 확인 2026-10-14: tool
  filenames are corrupted bytes, not cp949) — one such name, plus a UTF-8
  Korean name the routes re-decode for display (``paths.readable_name``);
- an empty folder, a folder of thousands of files, a file over the download
  cap, a symlink entry;
- a login directory that is not ``/`` (HV-SEM here, OFFICE-VERIFY);
- tools that never answer: every sem_list row with ``available == "Off"``.

The mock never opens a socket. ``put`` and ``remove`` really change the tree
(module-level ``_TREE``, so a write is seen by the next request until the
process restarts); ``put`` onto an existing name raises ``TargetExists`` as
``core.FtpClient.put`` does. It never raises ``TransferUncertain``: that needs
a lost RNTO reply, which only a real server can lose.

It also carries the member directory, the other swap surface:
``_auth.directory.probe_member`` is ``unavailable`` at home by design, so the
team allowlist would be untestable here. ``_MEMBERS`` stands in: a member of
an allowed team, two members of other teams, a profile with no dept_nm, and a
directory outage; every other empno is absent. The allowed team's name is the
user's spelling (OFFICE-VERIFY against the directory, see ``access.py``); the
other two are placeholders.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ftplib import error_perm

from ftp_handler.core import FileInfo, ListingTooLarge, TargetExists, TransferTooLarge

from backend._auth.directory import Probe, bare_member
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
        # Valid in neither UTF-8 nor cp949: the office's corrupted kind, shown as read.
        b"\xff\xfe_scan.log".decode("latin-1"): _File(321, 7),
    }


_TREE = _tree()


def _unreachable(eqp_id: str) -> bool:
    return any(r["eqp_id"] == eqp_id and r["available"] == "Off" for r in get_sem_list())


class MockFtpClient:
    def __init__(self, tool: Tool) -> None:
        self._tool = tool
        self._home = _HOME.get(tool.tool_type, "/")
        # The shared tree hangs at the login directory; its ancestors hold only it.
        self._root = _TREE
        for part in reversed([p for p in self._home.split("/") if p]):
            self._root = {part: self._root}

    def __enter__(self) -> "MockFtpClient":
        if _unreachable(self._tool.eqp_id):
            raise TimeoutError(f"{self._tool.host}:21 timed out")
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def home(self) -> str:
        return self._home

    def _node(self, path: str):
        node = self._root
        for part in [p for p in path.split("/") if p]:
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
    return Probe({**bare_member(empno), "emp_nm": emp_nm, "dept_nm": dept_nm}, "found")


_MEMBERS: dict[str, Probe] = {
    "1000001": _profile("1000001", "김계측", "DRAM Metrology기술"),
    "1000002": _profile("1000002", "이계측", "계측기술팀"),
    "1000003": _profile("1000003", "박공정", "공정기술팀"),
    "1000004": _profile("1000004", "최무소속", None),
    "1000005": Probe(None, "unavailable"),
}


def probe(empno: str) -> Probe:
    return _MEMBERS.get(empno, Probe(None, "absent"))
