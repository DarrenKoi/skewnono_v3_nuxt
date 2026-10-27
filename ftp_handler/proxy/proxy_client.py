"""Single-server FTP client over the HTTP proxy — ``core.FtpClient``'s twin.

For a PC that cannot reach tool FTP (firewalled) but can reach the Flask proxy
(``flask_proxy.py``). ``home``, ``list_details``, ``download``, ``upload``,
``put``, ``remove``, ``mkdir`` and ``rmdir`` have ``core.FtpClient``'s exact
signatures and raise its exceptions, so a call site swaps the import line and
nothing else::

    from ftp_handler.core import FtpClient     # direct FTP
    from ftp_handler.proxy import FtpClient    # via the proxy

Every call is one HTTP request and one fresh FTP connection on the proxy; the
context manager holds no remote session, so paths are absolute strings that
stay valid across calls. Writes run ``core.FtpClient``'s own method on the
proxy, so ``put`` keeps its temp-then-rename no-clobber and ``mkdir`` its
existing-directory check. (Until 2026-10-28 this client was read-only and
raised ``WriteNotSupported``; the proxy's fleet routes already wrote, so the
policy changed to let the single-server client write too.)

A ``ProxyError`` from a write leaves its outcome unknown when the request
reached the proxy (a lost answer, a 5xx after the work): list before retrying.

Proxy location and auth are ``proxy_downloader.PROXY_URL`` / ``PROXY_TOKEN``,
read when the client is built, the same constants ``FtpFleetDownloader`` uses.

Wire (``POST``, JSON body = credentials envelope + operation fields):
    /list_details_sknn_v3  {remote_dir|null, pattern, tz_offset_s,
                            max_entries, max_raw_bytes, deadline_s, home_only}
        200 {home, entries:[{name, path, is_dir, size, modified, is_link, raw}]}
        ``remote_dir`` null lists the login directory (PWD); ``home_only`` true
        answers ``{home, entries: []}`` after the PWD with no LIST at all.
    /fetch_sknn_v3         {remote_path, max_bytes, deadline_s}
        200 application/octet-stream, the raw file bytes
    /write_sknn_v3         {op: upload|put|remove|mkdir|rmdir, remote_path,
                            data_b64 (upload, put), deadline_s (put)}
        200 {ok: true}
    Any route: 422 {code, error, temp_path?}, mapped back to an exception by
    ``_ERRORS``; ``temp_path`` names a put's leftover temp, as on the direct
    client;
    ``encoding`` (an undecodable name, banner or PWD) is ``UnicodeDecodeError``.
    Any other status, or a body that is not the expected JSON, is ``ProxyError``.

``deadline_s`` is the seconds remaining, never a clock reading: the two machines'
clocks are not compared. The proxy enforces every cap while it receives from
FTP, and this side enforces ``max_bytes`` and ``deadline`` again per chunk.
"""

import base64
import time
from datetime import datetime, tzinfo
from ftplib import error_perm

import requests

from ..core.client import (
    _DEFAULT_TZ,
    FileInfo,
    ListingTooLarge,
    TargetExists,
    TransferTimeout,
    TransferTooLarge,
    TransferUncertain,
    _check_deadline,
)
from ..direct_downloader.fleet_downloader import HostSpec
from . import proxy_downloader as _dl

URL_LIST_DETAILS = "/list_details_sknn_v3"
URL_FETCH = "/fetch_sknn_v3"
URL_WRITE = "/write_sknn_v3"
ERROR_STATUS = 422
_CHUNK = 64 * 1024


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
    "exists": TargetExists,
    "uncertain": TransferUncertain,
    # A request the proxy cannot parse is a version mismatch between the two
    # halves, not a value the caller passed.
    "bad_request": ProxyError,
    "encoding": "encoding",
}


def _field(read):
    """Decode a 200 body; a shape this client does not know is the proxy's fault."""
    try:
        return read()
    except (KeyError, TypeError, ValueError) as exc:
        raise ProxyError(f"proxy answered an unexpected body: {exc!r}") from exc


class FtpClient:
    """``core.FtpClient``'s surface, one proxy request per call."""

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
            temp = body.get("temp_path")
        except (ValueError, KeyError, TypeError, AttributeError):
            exc_type = None
        finally:
            resp.close()
        if exc_type is None:
            raise ProxyError(f"proxy answered HTTP {resp.status_code} on {path}")
        if exc_type == "encoding":
            # The direct client raises this from ftplib's decode; same type here.
            raise UnicodeDecodeError(self.encoding, b"", 0, 0, error)
        if exc_type is TransferUncertain:
            raise TransferUncertain(error, temp_path=temp)
        exc = exc_type(error)
        if temp:
            # As core.FtpClient._drop_temp marks a temp it could not delete.
            exc.temp_path = temp
            exc.add_note(f"temp file left on server: {temp}")
        raise exc

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
        # home_only: PWD with no LIST. The read waits ``timeout`` on top of a
        # ``timeout`` budget for the proxy's connect+login+PWD, never forever.
        # An older proxy ignores home_only and LISTs; the read timeout still
        # bounds that, as a ProxyError.
        payload = {"remote_dir": None, "home_only": True}
        body = self._json(self._post(URL_LIST_DETAILS, payload, self.timeout))
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

    def _write(self, op: str, remote_path: str, data: bytes | None = None,
               deadline: float | None = None) -> None:
        payload = {"op": op, "remote_path": remote_path, "deadline_s": deadline}
        if data is not None:
            payload["data_b64"] = base64.b64encode(data).decode("ascii")
        body = self._json(self._post(URL_WRITE, payload, deadline))
        # A 200 that is not this route's answer (a login page, an older proxy
        # without the route behind a catch-all) must never read as success.
        if _field(lambda: body["ok"]) is not True:
            raise ProxyError(f"proxy did not confirm {op} {remote_path}")

    def upload(self, remote_path: str, data: bytes) -> None:
        """``core.FtpClient.upload`` (STOR, overwriting), run on the proxy."""
        self._write("upload", remote_path, data)

    def put(self, remote_path: str, data: bytes, *, deadline: float | None = None) -> None:
        """``core.FtpClient.put`` (no-clobber temp + rename), run on the proxy."""
        self._write("put", remote_path, data, deadline)

    def remove(self, remote_path: str) -> None:
        """``core.FtpClient.remove`` (DELE), run on the proxy."""
        self._write("remove", remote_path)

    def mkdir(self, remote_dir: str) -> None:
        """``core.FtpClient.mkdir`` (MKD; an existing directory is success)."""
        self._write("mkdir", remote_dir)

    def rmdir(self, remote_dir: str) -> None:
        """``core.FtpClient.rmdir`` (RMD, empty directories only)."""
        self._write("rmdir", remote_dir)


__all__ = [
    "FileUnavailable",
    "FtpClient",
    "ProxyError",
    "ToolUnreachable",
]
