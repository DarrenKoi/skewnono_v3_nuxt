"""SWAP SURFACE for tool-files provider selection.

Three surfaces swap together, so "real FTP + mock grants" cannot exist:

- the FTP connection: a context manager with ``core.FtpClient``'s surface
  (``home``, ``list_details``, ``download``, ``put``, ``remove``),
  plus ``transport_supports_write()``. Resolution, path checks and
  error mapping stay in shared code, so the mock exercises them as the office
  does;
- the grant store (``read_grants``, ``put_grant``, ``delete_grant``), keyed
  ``team:<dept_nm>`` / ``emp:<empno>``, raising ``StoreUnavailable``;
- the access requests (``read_requests``, ``put_request``,
  ``approve_request``, ``reject_request``, ``approve_team``), keyed by the
  normalised empno; the three admin writes compare a ``request_id`` and raise
  ``RequestChanged`` when it moved;
- the member directory (``probe``, ``teams``).
"""

from backend._runtime.data_provider import get_data_provider
from backend._auth.directory import Probe
from backend.ebeam.tool_files.contracts import Grant, Request, Teams
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


def read_grants() -> dict[str, Grant]:
    return _provider().read_grants()


def put_grant(key: str, grant: Grant) -> Grant:
    return _provider().put_grant(key, grant)


def delete_grant(key: str) -> bool:
    return _provider().delete_grant(key)


def read_requests() -> dict[str, Request]:
    return _provider().read_requests()


def put_request(empno: str, request: Request) -> None:
    _provider().put_request(empno, request)


def approve_request(empno: str, request_id: str, grant: Grant) -> None:
    _provider().approve_request(empno, request_id, grant)


def reject_request(empno: str, request_id: str) -> None:
    _provider().reject_request(empno, request_id)


def approve_team(dept_nm: str, grant: Grant) -> tuple[Grant, list[str]]:
    return _provider().approve_team(dept_nm, grant)


def probe(empno: str) -> Probe:
    return _provider().probe(empno)


def teams() -> Teams:
    return _provider().teams()
