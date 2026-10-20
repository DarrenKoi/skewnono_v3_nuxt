"""Office adapter: a direct FTP connection and the real member directory.

Copy to ``office.py`` to activate. It holds no in-house address or secret;
the directory reads Redis from ``backend/.env`` via ``_runtime/office_redis.py``.

Transport follows msr_image's rule, decided per call: Linux (Phase 3 cloud)
opens FTP directly; Windows (Phase 2 office PC, which cannot reach tool FTP)
goes through the read-only ``ftp_handler.proxy.FtpClient``, which holds every
transfer to ``SKEWNONO_TOOL_FILES_PROXY_DEADLINE`` (45 s) so the proxy host's
harakiri never kills it first. ``transport_supports_write()`` is False there:
the proxy has no write route.

``probe`` is ``_auth.directory.probe_member``: its ``dept_nm`` is what the
team allowlist in ``access.py`` is matched against.
"""

import platform

from ftp_handler.core import FtpClient
from ftp_handler.proxy import FtpClient as ProxyFtpClient

from backend._auth.directory import probe_member
from backend.ebeam.tool_files.config import load_limits
from backend.ebeam.tool_files.resolve import Tool

probe = probe_member


def _via_proxy() -> bool:
    return platform.system() == "Windows"


def transport_supports_write() -> bool:
    return not _via_proxy()


def _proxy_deadline(asked: float | None) -> float:
    limit = load_limits().proxy_deadline
    return limit if asked is None else min(asked, limit)


class _ProxyClient(ProxyFtpClient):
    """The proxy client, with each transfer held to the proxy deadline: the
    routes ask for the direct one, which the proxy host would not survive."""

    def list_details(self, remote_dir, pattern=None, *, deadline=None, **kwargs):
        return super().list_details(
            remote_dir, pattern, deadline=_proxy_deadline(deadline), **kwargs
        )

    def download(self, remote_path, *, deadline=None, **kwargs):
        return super().download(remote_path, deadline=_proxy_deadline(deadline), **kwargs)


def open_client(tool: Tool) -> FtpClient | ProxyFtpClient:
    client = _ProxyClient if _via_proxy() else FtpClient
    return client(
        host=tool.host,
        user=tool.user,
        password=tool.password,
        port=tool.port,
        timeout=tool.timeout,
        encoding=tool.encoding,
    )
