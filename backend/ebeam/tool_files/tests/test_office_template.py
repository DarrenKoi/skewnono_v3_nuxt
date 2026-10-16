"""The office template: a direct FtpClient, Redis grants, HSCAN team sizes.

Driven through a bytes-speaking fake; real WATCH/HSCAN semantics are office
verification items (ticket 09).
"""

import json

import pytest
import redis
from ftp_handler.core import FtpClient

from backend.ebeam.tool_files.errors import DirectoryUnavailable, StoreUnavailable
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

GRANTS_KEY = "skewnono:tool_files:grants"
_GRANT = {"granted_at": "2026-10-17T00:00:00Z", "granted_by": "2067928"}


class FakeRedis:
    """Bytes in, bytes out, like the shared office client
    (``decode_responses=False``). ``pages`` splits HSCAN into the given field
    lists, so a field Redis returns twice across pages can be staged."""

    def __init__(self):
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.fail_on: set[str] = set()
        self.pages: list[list[bytes]] | None = None
        self.calls: list[str] = []

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

    surface = ("open_client", "read_grants", "put_grant", "delete_grant", "probe", "teams")
    assert [name for name in surface if not callable(getattr(office, name, None))] == []
    assert [name for name in surface if not callable(getattr(mock, name, None))] == []
