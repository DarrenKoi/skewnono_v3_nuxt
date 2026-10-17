"""Path keys: which ones a request may name, and the breadcrumb around them.

A guardrail, not the security boundary. The tool's FTP account permissions are
what actually confine a session; LIST cannot tell where a symlinked middle
folder points, so a path inside the root by these rules can still resolve
outside it on the server.
"""

import re

from backend.ebeam.tool_files.contracts import Crumb
from backend.ebeam.tool_files.errors import ToolFilesError

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_DRIVE = re.compile(r"^[A-Za-z]:$")


def _parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def _bad(path: str, why: str) -> ToolFilesError:
    return ToolFilesError(400, "bad_path", f"{path!r} {why}")


def check_path(root: str, path: str | None) -> str:
    """``path`` if it is an absolute key at or under ``root``; ``root`` for None.

    Compared component by component, so ``/rcp2`` is not under ``/rcp``. The
    key is returned as given — never stripped, re-encoded or normalized, since
    any of those would change the bytes a latin-1 filename round-trips on.
    """
    if path is None or path == "":
        return root
    if not path.startswith("/"):
        raise _bad(path, "is not an absolute path key")
    if "\\" in path or _CONTROL.search(path):
        raise _bad(path, "contains a backslash or control character")
    parts = path.split("/")[1:] if path != "/" else []
    if any(part in ("", ".", "..") for part in parts):
        raise _bad(path, "has an empty, '.' or '..' segment")
    root_parts = _parts(root)
    if parts[: len(root_parts)] != root_parts:
        raise _bad(path, f"is outside {root!r}")
    if any(_DRIVE.match(part) for part in parts[len(root_parts):]):
        raise _bad(path, "names a drive")
    return path


def readable_name(name: str) -> str:
    """What to show for a name read under latin-1: its bytes as UTF-8, else
    cp949 (Korean Windows), else as read. Display only — a path key keeps the
    latin-1 string, since that is what round-trips to the server's bytes.

    A name a utf-8 session already decoded has characters past U+00FF, so it
    cannot be latin-1 bytes and comes back unchanged.
    """
    try:
        raw = name.encode("latin-1")
    except UnicodeEncodeError:
        return name
    for codec in ("utf-8", "cp949"):
        try:
            return raw.decode(codec)
        except UnicodeDecodeError:
            pass
    return name


def parent_of(root: str, path: str) -> str | None:
    parts, root_parts = _parts(path), _parts(root)
    if len(parts) <= len(root_parts):
        return None
    return "/" + "/".join(parts[:-1])


def crumbs(root: str, path: str) -> list[Crumb]:
    root_parts, parts = _parts(root), _parts(path)
    out: list[Crumb] = [{"name": root, "path": root}]
    for depth in range(len(root_parts) + 1, len(parts) + 1):
        out.append({"name": readable_name(parts[depth - 1]), "path": "/" + "/".join(parts[:depth])})
    return out
