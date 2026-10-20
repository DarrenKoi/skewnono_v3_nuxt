"""SWAP SURFACE for tool-files provider selection.

Two surfaces swap together:

- the FTP connection: a context manager with ``core.FtpClient``'s surface
  (``home``, ``list_details``, ``download``, ``put``, ``remove``),
  plus ``transport_supports_write()``. Resolution, path checks and
  error mapping stay in shared code, so the mock exercises them as the office
  does;
- the member directory (``probe``), whose ``dept_nm`` the team allowlist in
  ``access.py`` is matched against.
"""

from backend._runtime.data_provider import get_data_provider
from backend._auth.directory import Probe
from backend.ebeam.tool_files.resolve import Tool


def _provider():
    if get_data_provider("tool_files") == "office":
        from backend.ebeam.tool_files.providers import office as provider
    else:
        from backend.ebeam.tool_files.providers import mock as provider
    return provider


def open_client(tool: Tool):
    return _provider().open_client(tool)


def transport_supports_write() -> bool:
    """False for a read-only transport (the office proxy): writes answer 501."""
    return _provider().transport_supports_write()


def probe(empno: str) -> Probe:
    return _provider().probe(empno)
