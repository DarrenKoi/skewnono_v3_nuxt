"""Office adapter: a direct FTP connection, Redis grants, the real directory.

Copy to ``office.py`` to activate. It holds no in-house address or secret;
Redis comes from ``backend/.env`` via ``_runtime/office_redis.py``.

Transport follows msr_image's rule, decided per call: Linux (Phase 3 cloud)
opens FTP directly; Windows (Phase 2 office PC, which cannot reach tool FTP)
goes through the read-only ``ftp_handler.proxy.FtpClient``, which holds every
transfer to ``SKEWNONO_TOOL_FILES_PROXY_DEADLINE`` (45 s) so the proxy host's
harakiri never kills it first. ``transport_supports_write()`` is False there:
the proxy has no write route.

Layout:

    skewnono:tool_files:grants  HASH  "team:<dept_nm>" | "emp:<empno>"
                                      -> JSON {granted_at, granted_by}
    members                     HASH  <empno> -> JSON member document
                                      (read only; owned by the directory)

Every store failure raises ``StoreUnavailable`` (503), never an empty grant
list: an admin shown no grants during an outage would start re-granting. An
undecodable grant value is the same 503, not a missing grant. ``HSETNX`` makes
a repeat grant keep the first stamp without a read-before-write race.

Team sizes come from HSCAN over ``members``, deduplicated by field (HSCAN may
return a field twice across pages) and cached 600 s like ``probe_member``. A
member document that does not decode makes ``complete`` false, so the admin
page does not call a 0 proof; an outage is ``DirectoryUnavailable`` and is not
cached.
"""

import json
import platform
import time
from collections import Counter
from functools import lru_cache

from ftp_handler.core import FtpClient
from ftp_handler.proxy import FtpClient as ProxyFtpClient

from backend._auth.directory import MEMBERS_KEY, probe_member
from backend._runtime.office_redis import STORE_ERRORS, redis_client, redis_text
from backend.ebeam.tool_files.config import load_limits
from backend.ebeam.tool_files.contracts import Grant, Teams
from backend.ebeam.tool_files.errors import DirectoryUnavailable, StoreUnavailable
from backend.ebeam.tool_files.resolve import Tool

_GRANTS_KEY = "skewnono:tool_files:grants"
_TEAMS_TTL_SECONDS = 600
_SCAN_COUNT = 1000

probe = probe_member


def _client():
    # The seam tests patch to inject a fake.
    return redis_client()


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


def _decode_grant(raw) -> Grant:
    try:
        grant = json.loads(redis_text(raw))
    except (ValueError, UnicodeDecodeError) as exc:
        raise StoreUnavailable(f"undecodable value in {_GRANTS_KEY}") from exc
    if not isinstance(grant, dict):
        raise StoreUnavailable(f"non-object value in {_GRANTS_KEY}")
    return grant


def read_grants() -> dict[str, Grant]:
    try:
        raw = _client().hgetall(_GRANTS_KEY)
    except STORE_ERRORS as exc:
        raise StoreUnavailable("grant store unreachable") from exc
    return {redis_text(field): _decode_grant(value) for field, value in raw.items()}


def put_grant(key: str, grant: Grant) -> Grant:
    try:
        client = _client()
        if client.hsetnx(_GRANTS_KEY, key, json.dumps(grant, ensure_ascii=False)):
            return grant
        existing = client.hget(_GRANTS_KEY, key)
    except STORE_ERRORS as exc:
        raise StoreUnavailable("grant store unreachable; grant NOT saved") from exc
    return grant if existing is None else _decode_grant(existing)


def delete_grant(key: str) -> bool:
    try:
        return bool(_client().hdel(_GRANTS_KEY, key))
    except STORE_ERRORS as exc:
        raise StoreUnavailable("grant store unreachable; revoke NOT saved") from exc


def _dept_of(raw) -> tuple[str | None, bool]:
    """(dept_nm, readable) for one member document."""
    try:
        document = json.loads(redis_text(raw))
    except (ValueError, UnicodeDecodeError):
        return None, False
    if not isinstance(document, dict):
        return None, False
    dept_nm = str(document.get("dept_nm") or "").strip()
    return dept_nm or None, True


@lru_cache(maxsize=1)
def _team_counts(_bucket: int) -> Teams:
    depts: dict[bytes, str | None] = {}
    complete = True
    cursor = 0
    try:
        client = _client()
        while True:
            cursor, page = client.hscan(MEMBERS_KEY, cursor, count=_SCAN_COUNT)
            for field, raw in page.items():
                dept_nm, readable = _dept_of(raw)
                complete = complete and readable
                depts[field] = dept_nm
            if cursor == 0:
                break
    except STORE_ERRORS as exc:
        raise DirectoryUnavailable("member directory unreachable") from exc
    counts = Counter(d for d in depts.values() if d)
    return {
        "teams": [{"dept_nm": d, "members": n} for d, n in sorted(counts.items())],
        "complete": complete,
    }


def teams() -> Teams:
    return _team_counts(int(time.time() // _TEAMS_TTL_SECONDS))
