"""SWAP SURFACE for tool-files provider selection.

Three surfaces swap together, so "real FTP + mock grants" cannot exist:

- the FTP connection: a context manager with ``core.FtpClient``'s surface
  (``home``, ``list_details``, ``download``). Resolution, path checks and
  error mapping stay in shared code, so the mock exercises them as the office
  does;
- the grant store (``read_grants``, ``put_grant``, ``delete_grant``), keyed
  ``team:<dept_nm>`` / ``emp:<empno>``, raising ``StoreUnavailable``;
- the member directory (``probe``, ``teams``).
"""

from backend._runtime.data_provider import get_data_provider
from backend._auth.directory import Probe
from backend.ebeam.tool_files.contracts import Grant, Teams
from backend.ebeam.tool_files.resolve import Tool


def _provider():
    if get_data_provider("tool_files") == "office":
        from backend.ebeam.tool_files.providers import office as provider
    else:
        from backend.ebeam.tool_files.providers import mock as provider
    return provider


def open_client(tool: Tool):
    return _provider().open_client(tool)


def read_grants() -> dict[str, Grant]:
    return _provider().read_grants()


def put_grant(key: str, grant: Grant) -> Grant:
    return _provider().put_grant(key, grant)


def delete_grant(key: str) -> bool:
    return _provider().delete_grant(key)


def probe(empno: str) -> Probe:
    return _provider().probe(empno)


def teams() -> Teams:
    return _provider().teams()
