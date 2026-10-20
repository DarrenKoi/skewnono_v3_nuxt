"""The office template's Redis person grants and requests, driven through a
bytes-speaking fake; real WATCH races are an office verification item."""

import json

import pytest
import redis

from backend.ebeam.tool_files.errors import RequestChanged, StoreUnavailable
from backend.ebeam.tool_files.providers import mock
from backend.ebeam.tool_files.providers import office_example as office

GRANTS_KEY = "skewnono:tool_files:emp_grants"
REQUESTS_KEY = "skewnono:tool_files:emp_requests"
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
    (``decode_responses=False``)."""

    def __init__(self):
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.fail_on: set[str] = set()
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


@pytest.fixture
def fake(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(office, "_client", lambda: fake)
    return fake


def test_a_grant_is_one_hash_field_holding_json_under_the_empno(fake):
    stored = office.put_grant("1000001", _GRANT)

    assert stored == _GRANT
    assert json.loads(fake.hashes[GRANTS_KEY][b"1000001"].decode("utf-8")) == _GRANT
    assert office.read_grants() == {"1000001": _GRANT}


def test_the_pre_2026_10_20_hashes_are_never_read(fake):
    fake.hashes["skewnono:tool_files:grants"] = {b"emp:1000001": json.dumps(_GRANT).encode()}

    assert office.read_grants() == {}


def test_a_repeat_grant_keeps_the_first_stamp(fake):
    office.put_grant("1000001", _GRANT)
    again = office.put_grant("1000001", {"granted_at": "2026-12-31T00:00:00Z", "granted_by": "x"})

    assert again == _GRANT


def test_revoke_reports_whether_a_field_was_there(fake):
    office.put_grant("1000001", _GRANT)

    assert office.delete_grant("1000001") is True
    assert office.delete_grant("1000001") is False


@pytest.mark.parametrize(
    "command, call",
    [
        ("hgetall", lambda: office.read_grants()),
        ("hsetnx", lambda: office.put_grant("1", _GRANT)),
        ("hdel", lambda: office.delete_grant("1")),
    ],
)
def test_a_redis_outage_is_store_unavailable(fake, command, call):
    fake.fail_on.add(command)
    with pytest.raises(StoreUnavailable):
        call()


def test_an_undecodable_grant_value_is_store_unavailable_not_a_missing_grant(fake):
    fake.hashes[GRANTS_KEY] = {b"1000001": b"\xff\xfe"}
    with pytest.raises(StoreUnavailable):
        office.read_grants()


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

    assert _stored_grant(fake, "1000003") == _GRANT
    assert office.read_requests() == {}


def test_deciding_a_replaced_request_is_request_changed_and_writes_nothing(fake):
    office.put_request("1000003", _request("b" * 32))

    with pytest.raises(RequestChanged):
        office.approve_request("1000003", "a" * 32, _GRANT)
    with pytest.raises(RequestChanged):
        office.reject_request("1000003", "a" * 32)
    assert _stored_grant(fake, "1000003") is None
    assert office.read_requests() == {"1000003": _request("b" * 32)}


def test_a_retried_approval_whose_request_is_gone_is_a_no_op(fake):
    office.put_grant("1000003", _GRANT)

    office.approve_request("1000003", "a" * 32, {"granted_at": "later", "granted_by": "x"})

    assert _stored_grant(fake, "1000003") == _GRANT


def test_a_rejection_keeps_the_request_marked_rejected(fake):
    office.put_request("1000003", _request("a" * 32))

    office.reject_request("1000003", "a" * 32)

    assert office.read_requests()["1000003"]["status"] == "rejected"


def test_an_unrelated_change_under_watch_is_retried(fake):
    office.put_request("1000003", _request("a" * 32))
    fake.races = [_rerequest("7777777", "c" * 32), _rerequest("7777778", "d" * 32), _rerequest("7777779", "e" * 32)]

    office.approve_request("1000003", "a" * 32, _GRANT)

    assert _stored_grant(fake, "1000003") == _GRANT
    assert sorted(office.read_requests()) == ["7777777", "7777778", "7777779"]


def test_a_store_that_keeps_changing_gives_up_after_three_retries(fake):
    office.put_request("1000003", _request("a" * 32))
    fake.races = [_rerequest(f"777777{n}", "c" * 32) for n in range(4)]

    with pytest.raises(StoreUnavailable):
        office.approve_request("1000003", "a" * 32, _GRANT)
    assert _stored_grant(fake, "1000003") is None


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
    assert _stored_grant(fake, "1000003") is None


def _approval_lands(empno):
    def play(fake):
        fake.hashes.setdefault(GRANTS_KEY, {})[empno.encode()] = json.dumps(_GRANT).encode()
        del fake.hashes[REQUESTS_KEY][empno.encode()]

    return play


def _rejection_lands(empno, request_id):
    def play(fake):
        fake.hashes[REQUESTS_KEY][empno.encode()] = json.dumps(
            _request(request_id, status="rejected")
        ).encode()

    return play


def test_two_admins_approving_at_once_leave_the_loser_a_no_op(fake):
    # Mock answers the second approval 200; the WATCH loser must too.
    office.put_request("1000003", _request("a" * 32))
    fake.races = [_approval_lands("1000003")]

    office.approve_request("1000003", "a" * 32, {"granted_at": "later", "granted_by": "x"})

    assert _stored_grant(fake, "1000003") == _GRANT
    assert office.read_requests() == {}


def test_an_approval_racing_a_rejection_of_the_same_request_still_approves(fake):
    # Same request_id, only the status moved: mock approves it, so does the retry.
    office.put_request("1000003", _request("a" * 32))
    fake.races = [_rejection_lands("1000003", "a" * 32)]

    office.approve_request("1000003", "a" * 32, _GRANT)

    assert _stored_grant(fake, "1000003") == _GRANT
    assert office.read_requests() == {}


def test_a_rejection_racing_an_approval_that_landed_is_request_changed(fake):
    # Mock's reject finds no request either: 409 on both.
    office.put_request("1000003", _request("a" * 32))
    fake.races = [_approval_lands("1000003")]

    with pytest.raises(RequestChanged):
        office.reject_request("1000003", "a" * 32)
    assert _stored_grant(fake, "1000003") == _GRANT


@pytest.mark.parametrize(
    "command, call",
    [
        ("hgetall", lambda: office.read_requests()),
        ("hset", lambda: office.put_request("1000003", _request("b" * 32))),
        ("watch", lambda: office.approve_request("1000003", "a" * 32, _GRANT)),
        ("watch", lambda: office.reject_request("1000003", "a" * 32)),
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


def test_both_adapters_offer_every_store_function_the_dispatcher_calls():
    surface = (
        "read_grants",
        "put_grant",
        "delete_grant",
        "read_requests",
        "put_request",
        "approve_request",
        "reject_request",
    )
    assert [name for name in surface if not callable(getattr(office, name, None))] == []
    assert [name for name in surface if not callable(getattr(mock, name, None))] == []
