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

    skewnono:tool_files:grants    HASH  "team:<dept_nm>" | "emp:<empno>"
                                        -> JSON {granted_at, granted_by}
    skewnono:tool_files:requests  HASH  <empno> -> JSON {request_id, reason,
                                        dept_nm, requested_at, status}
    members                       HASH  <empno> -> JSON member document
                                        (read only; owned by the directory)

Every store failure raises ``StoreUnavailable`` (503), never an empty grant
list: an admin shown no grants during an outage would start re-granting. An
undecodable grant value is the same 503, not a missing grant. ``HSETNX`` makes
a repeat grant keep the first stamp without a read-before-write race.

Approve, reject and team approve run ``WATCH requests`` -> read and compare
``request_id`` -> ``MULTI`` -> writes -> ``EXEC``. A missing or different
request is ``RequestChanged`` (409), except an approval retry whose request
is gone and whose grant exists, which is a no-op. ``WatchError`` subclasses
``RedisError``, so it is caught *before* ``STORE_ERRORS`` or it would read as
an outage, and the whole attempt is retried up to three times. The retry
re-reads and re-compares, so it answers what mock answers: a second admin's
approval of the same request is a no-op, an approval after a rejection of
the same request still approves, and a replaced request is 409. The fake in
``tests/test_office_template.py`` can only stage a WatchError; real
two-connection races are an office verification item (MIGRATION.md).

Team sizes come from HSCAN over ``members``, deduplicated by field (HSCAN may
return a field twice across pages) and cached 600 s like ``probe_member``. A
member document that does not decode makes ``complete`` false, so the admin
page does not call a 0 proof; an outage is ``DirectoryUnavailable`` and is not
cached.
"""

import json
import platform
import time
from collections.abc import Callable
from functools import lru_cache

from redis.exceptions import WatchError

from ftp_handler.core import FtpClient
from ftp_handler.proxy import FtpClient as ProxyFtpClient

from backend._auth.directory import MEMBERS_KEY, probe_member
from backend._runtime.office_redis import STORE_ERRORS, redis_client, redis_text
from backend.ebeam.tool_files.config import load_limits
from backend.ebeam.tool_files.access import cleared_by_team, emp_key, team_counts, team_key
from backend.ebeam.tool_files.contracts import Grant, Request, Teams
from backend.ebeam.tool_files.errors import (
    DirectoryUnavailable,
    RequestChanged,
    StoreUnavailable,
)
from backend.ebeam.tool_files.resolve import Tool

_GRANTS_KEY = "skewnono:tool_files:grants"
_REQUESTS_KEY = "skewnono:tool_files:requests"
_WATCH_RETRIES = 3
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


def _decode(raw, key: str = _GRANTS_KEY) -> dict:
    try:
        record = json.loads(redis_text(raw))
    except (ValueError, UnicodeDecodeError) as exc:
        raise StoreUnavailable(f"undecodable value in {key}") from exc
    if not isinstance(record, dict):
        raise StoreUnavailable(f"non-object value in {key}")
    return record


def _json(record) -> str:
    return json.dumps(record, ensure_ascii=False)


def read_grants() -> dict[str, Grant]:
    try:
        raw = _client().hgetall(_GRANTS_KEY)
    except STORE_ERRORS as exc:
        raise StoreUnavailable("grant store unreachable") from exc
    return {redis_text(field): _decode(value) for field, value in raw.items()}


def put_grant(key: str, grant: Grant) -> Grant:
    try:
        client = _client()
        if client.hsetnx(_GRANTS_KEY, key, _json(grant)):
            return grant
        existing = client.hget(_GRANTS_KEY, key)
    except STORE_ERRORS as exc:
        raise StoreUnavailable("grant store unreachable; grant NOT saved") from exc
    return grant if existing is None else _decode(existing)


def delete_grant(key: str) -> bool:
    try:
        return bool(_client().hdel(_GRANTS_KEY, key))
    except STORE_ERRORS as exc:
        raise StoreUnavailable("grant store unreachable; revoke NOT saved") from exc


def read_requests() -> dict[str, Request]:
    try:
        raw = _client().hgetall(_REQUESTS_KEY)
    except STORE_ERRORS as exc:
        raise StoreUnavailable("request store unreachable") from exc
    return {redis_text(field): _decode(value, _REQUESTS_KEY) for field, value in raw.items()}


def put_request(empno: str, request: Request) -> None:
    try:
        _client().hset(_REQUESTS_KEY, empno, _json(request))
    except STORE_ERRORS as exc:
        raise StoreUnavailable("request store unreachable; request NOT confirmed") from exc


def _watched(attempt: Callable) -> object:
    """Run ``attempt(pipe)`` under WATCH requests. ``attempt`` reads and
    judges, then queues its writes after ``pipe.multi()`` and executes them;
    an aborted EXEC runs it again from the read."""
    try:
        client = _client()
        for _ in range(1 + _WATCH_RETRIES):
            try:
                with client.pipeline() as pipe:
                    pipe.watch(_REQUESTS_KEY)
                    return attempt(pipe)
            # Before STORE_ERRORS: WatchError is a RedisError, not an outage.
            except WatchError:
                pass
    except STORE_ERRORS as exc:
        raise StoreUnavailable("request store unreachable; result unknown, reload") from exc
    raise StoreUnavailable("requests kept changing under WATCH; nothing saved")


def _matching(pipe, empno: str, request_id: str) -> dict | None:
    raw = pipe.hget(_REQUESTS_KEY, empno)
    if raw is None:
        return None
    current = _decode(raw, _REQUESTS_KEY)
    if current.get("request_id") != request_id:
        raise RequestChanged(empno)
    return current


def approve_request(empno: str, request_id: str, grant: Grant) -> None:
    key = emp_key(empno)

    def attempt(pipe):
        if _matching(pipe, empno, request_id) is None:
            if pipe.hexists(_GRANTS_KEY, key):
                return None  # a retry of an approval that already landed
            raise RequestChanged(empno)
        pipe.multi()
        pipe.hsetnx(_GRANTS_KEY, key, _json(grant))
        pipe.hdel(_REQUESTS_KEY, empno)
        pipe.execute()
        return None

    _watched(attempt)


def reject_request(empno: str, request_id: str) -> None:
    def attempt(pipe):
        current = _matching(pipe, empno, request_id)
        if current is None:
            raise RequestChanged(empno)
        pipe.multi()
        pipe.hset(_REQUESTS_KEY, empno, _json({**current, "status": "rejected"}))
        pipe.execute()

    _watched(attempt)


def approve_team(dept_nm: str, grant: Grant) -> tuple[Grant, list[str]]:
    """The cleared set is read inside the transaction, so a request that
    lands meanwhile aborts EXEC and is judged on the retry."""
    key = team_key(dept_nm)

    def attempt(pipe):
        existing = pipe.hget(_GRANTS_KEY, key)
        cleared = sorted(
            redis_text(field)
            for field, raw in pipe.hgetall(_REQUESTS_KEY).items()
            if cleared_by_team(_decode(raw, _REQUESTS_KEY), dept_nm)
        )
        pipe.multi()
        pipe.hsetnx(_GRANTS_KEY, key, _json(grant))
        if cleared:
            pipe.hdel(_REQUESTS_KEY, *cleared)
        pipe.execute()
        return (grant if existing is None else _decode(existing)), cleared

    return _watched(attempt)


def _dept_of(raw) -> tuple[str | None, bool]:
    """(dept_nm, readable) for one member document."""
    try:
        document = _decode(raw, MEMBERS_KEY)
    except StoreUnavailable:
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
    return team_counts(depts.values(), complete)


def teams() -> Teams:
    return _team_counts(int(time.time() // _TEAMS_TTL_SECONDS))
