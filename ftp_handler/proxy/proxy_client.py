"""Read-only single-server FTP client over the HTTP proxy — ``core.FtpClient``'s twin.

For a PC that cannot reach tool FTP (firewalled) but can reach the Flask proxy
(``flask_proxy.py``). ``home``, ``list_details`` and ``download`` have
``core.FtpClient``'s exact signatures and raise its exceptions, so a call site
swaps the import line and nothing else::

    from ftp_handler.core import FtpClient     # direct FTP
    from ftp_handler.proxy import FtpClient    # via the proxy

Every call is one HTTP request and one fresh FTP connection on the proxy; the
context manager holds no remote session, so paths are absolute strings that
stay valid across calls. Writes are not offered: the proxy has no auth, so
``put`` and ``remove`` raise ``WriteNotSupported`` and no write route exists.

Proxy location and auth are ``proxy_downloader.PROXY_URL`` / ``PROXY_TOKEN``,
read when the client is built, the same constants ``FtpFleetDownloader`` uses.

Wire (``POST``, JSON body = credentials envelope + operation fields):
    /list_details_sknn_v3  {remote_dir|null, pattern, tz_offset_s,
                            max_entries, max_raw_bytes, deadline_s}
        200 {home, entries:[{name, path, is_dir, size, modified, is_link, raw}]}
        ``remote_dir`` null lists the login directory (PWD).
    /fetch_sknn_v3         {remote_path, max_bytes, deadline_s}
        200 application/octet-stream, the raw file bytes
    Either route: 422 {code, error}, mapped back to an exception by ``_ERRORS``.
    Any other status, or a body that is not the expected JSON, is ``ProxyError``.

``deadline_s`` is the seconds remaining, never a clock reading: the two machines'
clocks are not compared. The proxy enforces every cap while it receives from
FTP, and this side enforces ``max_bytes`` and ``deadline`` again per chunk.
"""

import time
from datetime import datetime, tzinfo
from ftplib import error_perm

import requests

from ..core.client import (
    _DEFAULT_TZ,
    FileInfo,
    ListingTooLarge,
    TransferTimeout,
    TransferTooLarge,
    _check_deadline,
)
from ..direct_downloader.fleet_downloader import HostSpec
from . import proxy_downloader as _dl

URL_LIST_DETAILS = "/list_details_sknn_v3"
URL_FETCH = "/fetch_sknn_v3"
ERROR_STATUS = 422
_CHUNK = 64 * 1024


class WriteNotSupported(NotImplementedError):
    """The proxy transport is read-only; write directly or not at all."""


class ProxyError(ConnectionError):
    """The proxy itself failed: unreachable, 401, missing route, 5xx, bad body."""


class FileUnavailable(error_perm):
    """FTP 550 on the proxy side — an ``error_perm``, as the direct client raises."""


class ToolUnreachable(ConnectionError):
    """The proxy could not connect or log in to the tool."""


_ERRORS = {
    "too_large": TransferTooLarge,
    "listing_too_large": ListingTooLarge,
    "timeout": TransferTimeout,
    "unavailable": FileUnavailable,
    "unreachable": ToolUnreachable,
    "bad_request": ValueError,
}


def _field(read):
    """Decode a 200 body; a shape this client does not know is the proxy's fault."""
    try:
        return read()
    except (KeyError, TypeError, ValueError) as exc:
        raise ProxyError(f"proxy answered an unexpected body: {exc!r}") from exc


class FtpClient:
    """``core.FtpClient``'s read surface, one proxy request per call."""

    def __init__(
        self,
        *,
        host: str,
        user: str,
        password: str,
        port: int = 21,
        timeout: float = 8.0,
        passive: bool = True,
        encoding: str = "utf-8",
    ) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.timeout = timeout
        self.passive = passive
        self.encoding = encoding
        self.proxy_url = _dl.PROXY_URL.rstrip("/")
        self.token = _dl.PROXY_TOKEN

    def __enter__(self) -> "FtpClient":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def _envelope(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "timeout": self.timeout,
            "passive": self.passive,
            "encoding": self.encoding,
            **_dl._credentials_to_wire(HostSpec(self.host), self.user, self.password),
        }

    def _post(self, path: str, payload: dict, deadline: float | None):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        # The proxy answers only after its own FTP work, so a read may wait the
        # whole deadline; the socket timeout is added on top as slack.
        read = None if deadline is None else deadline + self.timeout
        try:
            resp = requests.post(
                f"{self.proxy_url}{path}",
                json={**self._envelope(), **payload},
                headers=headers,
                timeout=(self.timeout, read),
                stream=True,
            )
        except requests.RequestException as exc:
            raise ProxyError(f"proxy request failed: {exc}") from exc
        if resp.status_code == 200:
            return resp
        try:
            body = resp.json()
            code, error = body["code"], body["error"]
            exc_type = _ERRORS[code] if resp.status_code == ERROR_STATUS else None
        except (ValueError, KeyError, TypeError):
            exc_type = None
        finally:
            resp.close()
        if exc_type is None:
            raise ProxyError(f"proxy answered HTTP {resp.status_code} on {path}")
        raise exc_type(error)

    def _json(self, resp) -> dict:
        try:
            return resp.json()
        except ValueError as exc:
            raise ProxyError("proxy answered 200 with a non-JSON body") from exc
        finally:
            resp.close()

    def _list(self, remote_dir, pattern, tz, max_entries, max_raw_bytes, deadline) -> dict:
        payload = {
            "remote_dir": remote_dir,
            "pattern": pattern,
            # The parser stamps LIST wall-clock times with this offset.
            "tz_offset_s": datetime.now(tz).utcoffset().total_seconds(),
            "max_entries": max_entries,
            "max_raw_bytes": max_raw_bytes,
            "deadline_s": deadline,
        }
        return self._json(self._post(URL_LIST_DETAILS, payload, deadline))

    def home(self) -> str:
        """The login directory (PWD) — the root a relative path resolves from."""
        # ponytail: the proxy also LISTs the home dir here (no third route);
        # cache it per client if a tool's home listing ever proves heavy.
        body = self._list(None, None, _DEFAULT_TZ, None, None, None)
        return _field(lambda: str(body["home"]))

    def list_details(
        self,
        remote_dir: str,
        pattern: str | None = None,
        *,
        tz: tzinfo = _DEFAULT_TZ,
        max_entries: int | None = None,
        max_raw_bytes: int | None = None,
        deadline: float | None = None,
    ) -> list[FileInfo]:
        """``core.FtpClient.list_details``, run on the proxy."""
        body = self._list(remote_dir, pattern, tz, max_entries, max_raw_bytes, deadline)
        return _field(lambda: [
            FileInfo(
                name=e["name"],
                path=e["path"],
                is_dir=e["is_dir"],
                size=e["size"],
                modified=datetime.fromisoformat(e["modified"]) if e["modified"] else None,
                raw=e["raw"],
                is_link=e["is_link"],
            )
            for e in body["entries"]
        ])

    def download(
        self,
        remote_path: str,
        *,
        max_bytes: int | None = None,
        deadline: float | None = None,
    ) -> bytes:
        """``core.FtpClient.download``, run on the proxy and re-checked per chunk."""
        started = time.monotonic()
        payload = {"remote_path": remote_path, "max_bytes": max_bytes, "deadline_s": deadline}
        resp = self._post(URL_FETCH, payload, deadline)
        buf = bytearray()
        try:
            for chunk in resp.iter_content(_CHUNK):
                if max_bytes is not None and len(buf) + len(chunk) > max_bytes:
                    raise TransferTooLarge(f"{remote_path} exceeds {max_bytes} bytes")
                _check_deadline(started, deadline, remote_path)
                buf += chunk
        except requests.RequestException as exc:
            raise ProxyError(f"proxy stream broke: {exc}") from exc
        finally:
            resp.close()
        return bytes(buf)

    def put(self, remote_path: str, data: bytes, *, deadline: float | None = None) -> None:
        raise WriteNotSupported("the FTP proxy is read-only")

    def remove(self, remote_path: str) -> None:
        raise WriteNotSupported("the FTP proxy is read-only")


__all__ = [
    "FileUnavailable",
    "FtpClient",
    "ProxyError",
    "ToolUnreachable",
    "WriteNotSupported",
]
