"""The office template: a direct FtpClient, Redis grants, HSCAN team sizes.

Driven through a bytes-speaking fake; real WATCH/HSCAN semantics are office
verification items (ticket 09).
"""

import json

import pytest
import redis
from ftp_handler.core import FtpClient
from ftp_handler.proxy import FtpClient as ProxyFtpClient

from backend.ebeam.tool_files.errors import DirectoryUnavailable, RequestChanged, StoreUnavailable
from backend.ebeam.tool_files.providers import mock
from backend.ebeam.tool_files.providers import office_example as office
from backend.ebeam.tool_files.resolve import Tool


def test_open_client_builds_a_direct_ftp_client_for_the_resolved_tool():
    tool = Tool(
        eqp_id="HCDX303",
        fab_name="M11A",
        tool_type="cd-sem",
        host="10.0.0.7",
        user="verity",
        password="pw",
        port=2121,
        timeout=8.0,
        encoding="latin-1",
    )

    client = office.open_client(tool)

    assert isinstance(client, FtpClient)
    assert (client.host, client.user, client.password, client.port, client.timeout, client.encoding) == (
        "10.0.0.7",
        "verity",
        "pw",
        2121,
        8.0,
        "latin-1",
    )


def test_windows_reaches_tools_through_the_read_only_proxy(monkeypatch):
    # A Windows office PC (Phase 2) cannot open FTP to tools; msr_image's rule.
    monkeypatch.setattr("platform.system", lambda: "Windows")

    client = office.open_client(_tool())

    assert isinstance(client, ProxyFtpClient)
    assert (client.host, client.user, client.port, client.encoding) == (
        "10.0.0.7",
        "verity",
        2121,
        "latin-1",
    )
    assert office.transport_supports_write() is False


def test_anything_but_windows_opens_ftp_directly_and_may_write(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")

    assert type(office.open_client(_tool())) is FtpClient
    assert office.transport_supports_write() is True


def test_the_proxy_holds_each_transfer_to_the_proxy_deadline(monkeypatch):
    # The route asks for the direct deadline (120 s); the proxy host's
    # harakiri would kill that request first.
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setenv("SKEWNONO_TOOL_FILES_PROXY_DEADLINE", "30")
    sent = []
    monkeypatch.setattr(
        "ftp_handler.proxy.proxy_client.FtpClient.download",
        lambda self, path, *, max_bytes=None, deadline=None: sent.append(deadline),
    )
    monkeypatch.setattr(
        "ftp_handler.proxy.proxy_client.FtpClient.list_details",
        lambda self, d, pattern=None, *, deadline=None, **kw: sent.append(deadline),
    )

    with office.open_client(_tool()) as ftp:
        ftp.download("/a", max_bytes=10, deadline=120.0)
        ftp.download("/a", deadline=5.0)
        ftp.list_details("/", max_entries=3, deadline=120.0)

    assert sent == [30.0, 5.0, 30.0]


def test_the_mock_transport_supports_write():
    assert mock.transport_supports_write() is True


def _tool() -> Tool:
    return Tool(
        eqp_id="HCDX303",
        fab_name="M11A",
        tool_type="cd-sem",
        host="10.0.0.7",
        user="verity",
        password="pw",
        port=2121,
        timeout=8.0,
        encoding="latin-1",
    )


GRANTS_KEY = "skewnono:tool_files:grants"
REQUESTS_KEY = "skewnono:tool_files:requests"
_GRANT = {"granted_at": "2026-10-17T00:00:00Z", "granted_by": "2067928"}


class FakePipeline:
    """redis-py's WATCH pipeline shape: commands run at once until
    ``multi()``, are queued after it, and ``execute()`` runs the queue. It
    cannot prove WATCH semantics; a staged race (``FakeRedis.races``) plays
    another client's write and then raises WatchError, as EXEC would."""

    def __init__(self, fake):
        self._fake = fake
        self._queue = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._queue = None

    def watch(self, *keys):
        self._fake._guard("watch")

    def multi(self):
        self._queue = []

    def execute(self):
        self._fake._guard("execute")
        if self._fake.races:
            self._fake.races.pop(0)(self._fake)
            raise redis.exceptions.WatchError("Watched variable changed.")
        queue, self._queue = self._queue or [], None
        return [command(*args) for command, args in queue]

    def __getattr__(self, name):
        command = getattr(self._fake, name)
        if self._queue is None:
            return command
        return lambda *args: self._queue.append((command, args))


class FakeRedis:
    """Bytes in, bytes out, like the shared office client
    (``decode_responses=False``). ``pages`` splits HSCAN into the given field
    lists, so a field Redis returns twice across pages can be staged."""

    def __init__(self):
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.fail_on: set[str] = set()
        self.pages: list[list[bytes]] | None = None
        self.calls: list[str] = []
        self.races: list = []

    def pipeline(self):
        return FakePipeline(self)

    def hset(self, key, field, value):
        self._guard("hset")
        self.hashes.setdefault(key, {})[self._b(field)] = self._b(value)
        return 1

    def hexists(self, key, field):
        self._guard("hexists")
        return self._b(field) in self.hashes.get(key, {})

    @staticmethod
    def _b(v) -> bytes:
        return v if isinstance(v, bytes) else str(v).encode()

    def _guard(self, name):
        self.calls.append(name)
        if name in self.fail_on:
            raise redis.exceptions.ConnectionError("fake outage")

    def hgetall(self, key):
        self._guard("hgetall")
        return dict(self.hashes.get(key, {}))

    def hget(self, key, field):
        self._guard("hget")
        return self.hashes.get(key, {}).get(self._b(field))

    def hsetnx(self, key, field, value):
        self._guard("hsetnx")
        h = self.hashes.setdefault(key, {})
        if self._b(field) in h:
            return 0
        h[self._b(field)] = self._b(value)
        return 1

    def hdel(self, key, *fields):
        self._guard("hdel")
        h = self.hashes.get(key, {})
        return sum(1 for f in fields if h.pop(self._b(f), None) is not None)

    def hscan(self, key, cursor=0, match=None, count=None):
        self._guard("hscan")
        h = self.hashes.get(key, {})
        pages = self.pages or [list(h)]
        page = {f: h[f] for f in pages[cursor]}
        nxt = cursor + 1 if cursor + 1 < len(pages) else 0
        return nxt, page


@pytest.fixture
def fake(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(office, "_client", lambda: fake)
    office._team_counts.cache_clear()
    yield fake
    office._team_counts.cache_clear()


def test_a_grant_is_one_hash_field_holding_json(fake):
    stored = office.put_grant("team:계측기술팀", _GRANT)

    assert stored == _GRANT
    raw = fake.hashes[GRANTS_KEY]["team:계측기술팀".encode()]
    assert json.loads(raw.decode("utf-8")) == _GRANT
    assert office.read_grants() == {"team:계측기술팀": _GRANT}


def test_a_repeat_grant_keeps_the_first_stamp(fake):
    office.put_grant("emp:1000001", _GRANT)
    again = office.put_grant("emp:1000001", {"granted_at": "2026-12-31T00:00:00Z", "granted_by": "x"})

    assert again == _GRANT


def test_revoke_reports_whether_a_field_was_there(fake):
    office.put_grant("emp:1000001", _GRANT)

    assert office.delete_grant("emp:1000001") is True
    assert office.delete_grant("emp:1000001") is False


@pytest.mark.parametrize(
    "command, call",
    [
        ("hgetall", lambda: office.read_grants()),
        ("hsetnx", lambda: office.put_grant("emp:1", _GRANT)),
        ("hdel", lambda: office.delete_grant("emp:1")),
    ],
)
def test_a_redis_outage_is_store_unavailable(fake, command, call):
    fake.fail_on.add(command)
    with pytest.raises(StoreUnavailable):
        call()


def test_an_undecodable_grant_value_is_store_unavailable_not_a_missing_grant(fake):
    fake.hashes[GRANTS_KEY] = {b"emp:1000001": b"\xff\xfe"}
    with pytest.raises(StoreUnavailable):
        office.read_grants()


def _doc(dept_nm):
    return json.dumps({"emp_nm": "x", "dept_nm": dept_nm}, ensure_ascii=False).encode("utf-8")


def test_teams_count_members_once_each_and_flag_unreadable_rows(fake):
    fake.hashes["members"] = {
        b"1000001": _doc("계측기술팀"),
        b"1000002": _doc("계측기술팀"),
        b"1000003": _doc("공정기술팀"),
        b"1000004": _doc(None),
        b"1000009": b"not json",
    }
    fake.pages = [[b"1000001", b"1000002"], [b"1000002", b"1000003", b"1000004", b"1000009"]]

    assert office.teams() == {
        "teams": [
            {"dept_nm": "계측기술팀", "members": 2},
            {"dept_nm": "공정기술팀", "members": 1},
        ],
        "complete": False,
    }


def test_teams_are_cached_between_calls(fake):
    fake.hashes["members"] = {b"1000001": _doc("계측기술팀")}
    office.teams()
    office.teams()

    assert fake.calls.count("hscan") == 1


def test_a_directory_outage_is_directory_unavailable_and_not_cached(fake):
    fake.fail_on.add("hscan")
    with pytest.raises(DirectoryUnavailable):
        office.teams()

    fake.fail_on.clear()
    fake.hashes["members"] = {b"1000001": _doc("계측기술팀")}
    assert office.teams()["complete"] is True


def test_the_template_offers_every_function_the_dispatcher_calls():
    from backend.ebeam.tool_files.providers import mock

    surface = (
        "open_client",
        "read_grants",
        "put_grant",
        "delete_grant",
        "read_requests",
        "put_request",
        "approve_request",
        "reject_request",
        "approve_team",
        "probe",
        "teams",
    )
    assert [name for name in surface if not callable(getattr(office, name, None))] == []
    assert [name for name in surface if not callable(getattr(mock, name, None))] == []


def _request(request_id, dept_nm="공정기술팀", status="pending"):
    return {
        "request_id": request_id,
        "reason": "백업",
        "dept_nm": dept_nm,
        "requested_at": "2026-10-17T00:00:00Z",
        "status": status,
    }


def _stored_grant(fake, key):
    raw = fake.hashes.get(GRANTS_KEY, {}).get(key.encode())
    return None if raw is None else json.loads(raw)


def _rerequest(empno, request_id):
    def play(fake):
        fake.hashes[REQUESTS_KEY][empno.encode()] = json.dumps(_request(request_id)).encode()

    return play


def test_a_request_is_one_hash_field_of_json_under_the_empno(fake):
    office.put_request("1000003", _request("a" * 32))

    raw = fake.hashes[REQUESTS_KEY][b"1000003"]
    assert json.loads(raw.decode("utf-8")) == _request("a" * 32)
    assert office.read_requests() == {"1000003": _request("a" * 32)}


def test_an_approval_grants_the_empno_and_drops_the_request(fake):
    office.put_request("1000003", _request("a" * 32))

    office.approve_request("1000003", "a" * 32, _GRANT)

    assert _stored_grant(fake, "emp:1000003") == _GRANT
    assert office.read_requests() == {}


def test_deciding_a_replaced_request_is_request_changed_and_writes_nothing(fake):
    office.put_request("1000003", _request("b" * 32))

    with pytest.raises(RequestChanged):
        office.approve_request("1000003", "a" * 32, _GRANT)
    with pytest.raises(RequestChanged):
        office.reject_request("1000003", "a" * 32)
    assert _stored_grant(fake, "emp:1000003") is None
    assert office.read_requests() == {"1000003": _request("b" * 32)}


def test_a_retried_approval_whose_request_is_gone_is_a_no_op(fake):
    office.put_grant("emp:1000003", _GRANT)

    office.approve_request("1000003", "a" * 32, {"granted_at": "later", "granted_by": "x"})

    assert _stored_grant(fake, "emp:1000003") == _GRANT


def test_a_rejection_keeps_the_request_marked_rejected(fake):
    office.put_request("1000003", _request("a" * 32))

    office.reject_request("1000003", "a" * 32)

    assert office.read_requests()["1000003"]["status"] == "rejected"


def test_an_unrelated_change_under_watch_is_retried(fake):
    office.put_request("1000003", _request("a" * 32))
    fake.races = [_rerequest("7777777", "c" * 32), _rerequest("7777778", "d" * 32), _rerequest("7777779", "e" * 32)]

    office.approve_request("1000003", "a" * 32, _GRANT)

    assert _stored_grant(fake, "emp:1000003") == _GRANT
    assert sorted(office.read_requests()) == ["7777777", "7777778", "7777779"]


def test_a_store_that_keeps_changing_gives_up_after_three_retries(fake):
    office.put_request("1000003", _request("a" * 32))
    fake.races = [_rerequest(f"777777{n}", "c" * 32) for n in range(4)]

    with pytest.raises(StoreUnavailable):
        office.approve_request("1000003", "a" * 32, _GRANT)
    assert _stored_grant(fake, "emp:1000003") is None


@pytest.mark.parametrize(
    "decide",
    [
        lambda: office.approve_request("1000003", "a" * 32, _GRANT),
        lambda: office.reject_request("1000003", "a" * 32),
    ],
)
def test_a_re_request_racing_the_decision_is_request_changed(fake, decide):
    office.put_request("1000003", _request("a" * 32))
    fake.races = [_rerequest("1000003", "b" * 32)]

    with pytest.raises(RequestChanged):
        decide()
    assert office.read_requests() == {"1000003": _request("b" * 32)}
    assert _stored_grant(fake, "emp:1000003") is None


def test_a_team_approval_grants_the_team_and_clears_its_pending_requests(fake):
    office.put_request("1000001", _request("a" * 32, dept_nm="계측기술팀"))
    office.put_request("1000002", _request("b" * 32, dept_nm="계측기술팀", status="rejected"))
    office.put_request("1000003", _request("c" * 32))
    fake.races = [_rerequest("7777777", "d" * 32)]

    grant, cleared = office.approve_team("계측기술팀", _GRANT)

    assert (grant, cleared) == (_GRANT, ["1000001"])
    assert _stored_grant(fake, "team:계측기술팀") == _GRANT
    assert sorted(office.read_requests()) == ["1000002", "1000003", "7777777"]


def test_a_repeat_team_approval_keeps_the_first_stamp(fake):
    office.put_grant("team:계측기술팀", _GRANT)

    grant, _cleared = office.approve_team("계측기술팀", {"granted_at": "later", "granted_by": "x"})

    assert grant == _GRANT


@pytest.mark.parametrize(
    "command, call",
    [
        ("hgetall", lambda: office.read_requests()),
        ("hset", lambda: office.put_request("1000003", _request("b" * 32))),
        ("watch", lambda: office.approve_request("1000003", "a" * 32, _GRANT)),
        ("watch", lambda: office.reject_request("1000003", "a" * 32)),
        ("watch", lambda: office.approve_team("공정기술팀", _GRANT)),
        ("execute", lambda: office.approve_request("1000003", "a" * 32, _GRANT)),
    ],
)
def test_a_redis_outage_in_the_request_store_is_store_unavailable(fake, command, call):
    office.put_request("1000003", _request("a" * 32))
    fake.fail_on.add(command)

    with pytest.raises(StoreUnavailable):
        call()


def test_an_undecodable_request_is_store_unavailable(fake):
    fake.hashes[REQUESTS_KEY] = {b"1000003": b"\xff"}

    with pytest.raises(StoreUnavailable):
        office.read_requests()
    with pytest.raises(StoreUnavailable):
        office.approve_request("1000003", "a" * 32, _GRANT)
