"""The office short-link adapter — one expiring Redis string per link.

Verified against an injected fake rather than a live server. Two things carry
the weight here.

First, the collision probe. It is the only reason a code cannot silently point
at somebody else's screen, and a natural collision is unreachable in a test, so
it is forced by stubbing the digest.

Second, outage behaviour. Unlike the read-only adapters, a failed WRITE that
looks like a success hands the user a link that 404s forever — and they will
have pasted it into a report before finding out. So both functions must raise
rather than degrade, and the resolver in particular must not answer "not found"
for what is really an outage.

`importorskip` is deliberately NOT used: at home this file must actually run, or
the collision and outage rules go unproven until someone is at the office. The
adapter imports only stdlib plus `_runtime.office_redis`, so it imports fine.
"""

import json

import pytest
import redis

from back_dev_home.short_links.providers import mock
from back_dev_home.short_links.providers import office_example as office

TARGET = "/ebeam/cd-sem/skewvoir/analysis?lot=KPB266344&view=time-series"


class FakeRedis:
    """Byte-oriented stand-in for the shared office client, which runs
    ``decode_responses=False``. Implements only the four calls the adapter
    makes, including SET's ``nx`` and ``ex``."""

    def __init__(self):
        self.strings: dict[str, bytes] = {}
        self.ttl: dict[str, int] = {}
        self.fail = False

    def _guard(self):
        if self.fail:
            raise redis.exceptions.ConnectionError("fake outage")

    def get(self, key):
        self._guard()
        return self.strings.get(key)

    def set(self, key, value, ex=None, nx=False):
        self._guard()
        if nx and key in self.strings:
            return None
        self.strings[key] = value.encode() if isinstance(value, str) else value
        if ex is not None:
            self.ttl[key] = ex
        return True

    def expire(self, key, seconds):
        self._guard()
        if key not in self.strings:
            return False
        self.ttl[key] = seconds
        return True


@pytest.fixture
def fake(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(office, "_client", lambda: client)
    return client


# ── parity with the mock ────────────────────────────────────────────────


def test_the_code_derivation_matches_the_mock_exactly():
    """A code minted at home and one minted at the office must be the same
    string for the same screen. ``_digest`` is duplicated in both adapters
    (no import edge between them), so this is the pin that keeps them equal —
    the drift it guards against would be invisible until someone compared two
    links side by side."""
    for target in (TARGET, "/", "/a?b=c#d", "/한글/경로"):
        assert office._digest(target) == mock._digest(target)


def test_the_code_length_constant_matches_the_mock():
    assert office.CODE_LEN == mock.CODE_LEN


# ── mint ────────────────────────────────────────────────────────────────


def test_minting_stores_the_link_under_its_code(fake):
    link = office.create_short_link(TARGET)

    stored = json.loads(fake.strings[f"{office.KEY_PREFIX}{link['code']}"])
    assert stored["target"] == TARGET


def test_a_minted_link_carries_a_ttl(fake):
    """Unbounded keys would grow the keyspace with links nobody opens again."""
    link = office.create_short_link(TARGET)

    assert fake.ttl[f"{office.KEY_PREFIX}{link['code']}"] == office.TTL_SECONDS


def test_minting_the_same_target_twice_returns_the_same_code(fake):
    assert office.create_short_link(TARGET)["code"] == (
        office.create_short_link(TARGET)["code"]
    )


def test_re_sharing_preserves_created_at_rather_than_minting_a_second_entry(fake):
    """Matches the mock: the second call hands back the entry that already
    exists, so a colleague's link and the one just copied are one link."""
    first = office.create_short_link(TARGET)
    second = office.create_short_link(TARGET)

    assert second["created_at"] == first["created_at"]
    assert len(fake.strings) == 1


def test_re_sharing_refreshes_the_expiry(fake):
    """A link still in circulation should not age out on the schedule of the
    first time anyone shared it."""
    code = office.create_short_link(TARGET)["code"]
    fake.ttl[f"{office.KEY_PREFIX}{code}"] = 5

    office.create_short_link(TARGET)

    assert fake.ttl[f"{office.KEY_PREFIX}{code}"] == office.TTL_SECONDS


# ── collision ───────────────────────────────────────────────────────────


def test_a_collision_widens_the_code_rather_than_overwriting(fake, monkeypatch):
    """The failure this prevents is the worst one available to a redirector:
    following your own link and landing on a colleague's screen, with nothing
    on the page saying anything went wrong."""
    monkeypatch.setattr(office, "_digest", lambda target: "a" * 20)

    first = office.create_short_link("/a")
    second = office.create_short_link("/b")

    assert first["code"] != second["code"]
    assert office.resolve_short_link(first["code"])["target"] == "/a"
    assert office.resolve_short_link(second["code"])["target"] == "/b"


def test_an_exhausted_code_space_raises_rather_than_returning_a_wrong_code(
    fake, monkeypatch
):
    monkeypatch.setattr(office, "_digest", lambda target: "a" * 10)
    office.create_short_link("/a")

    with pytest.raises(RuntimeError):
        office.create_short_link("/b")


# ── resolve ─────────────────────────────────────────────────────────────


def test_a_minted_code_resolves_back(fake):
    code = office.create_short_link(TARGET)["code"]
    assert office.resolve_short_link(code)["target"] == TARGET


def test_an_unminted_code_resolves_to_none(fake):
    assert office.resolve_short_link("zzzzzzzzzz") is None


def test_an_empty_code_resolves_to_none_without_touching_the_store(fake):
    fake.fail = True
    assert office.resolve_short_link("") is None


def test_an_unreadable_value_reads_as_absent_rather_than_500(fake):
    """A truncated or hand-edited value degrades to "link not found"; the
    resolver has no try/except of its own."""
    fake.strings[f"{office.KEY_PREFIX}abcdefghij"] = b'{"target": '

    assert office.resolve_short_link("abcdefghij") is None


def test_a_value_missing_its_target_reads_as_absent(fake):
    fake.strings[f"{office.KEY_PREFIX}abcdefghij"] = b'{"created_at": "x"}'

    assert office.resolve_short_link("abcdefghij") is None


def test_an_unreadable_value_lets_its_slot_be_reclaimed_on_mint(fake, monkeypatch):
    """Otherwise one corrupt value would block that code forever, and the code
    is derived — nobody could mint that screen again."""
    monkeypatch.setattr(office, "_digest", lambda target: "a" * 20)
    fake.strings[f"{office.KEY_PREFIX}aaaaaaaaaa"] = b"not json"

    link = office.create_short_link("/a")

    assert link["code"] == "aaaaaaaaaa"
    assert office.resolve_short_link(link["code"])["target"] == "/a"


# ── outage: never report infrastructure failure as a data decision ──────


def test_a_failed_mint_raises_rather_than_returning_an_unpersisted_code(fake):
    """Returning a code we did not persist would hand the user a link that
    404s forever — and the frontend's long-URL fallback only runs if the error
    actually arrives."""
    fake.fail = True

    with pytest.raises(RuntimeError):
        office.create_short_link(TARGET)


def test_a_failed_resolve_raises_rather_than_answering_not_found(fake):
    """`None` means "this link does not exist", which during an outage tells
    someone their good link is dead and sends them to re-mint it."""
    fake.fail = True

    with pytest.raises(RuntimeError):
        office.resolve_short_link("abcdefghij")


@pytest.mark.parametrize("call", ["create", "resolve"])
def test_outages_raise_exactly_runtimeerror_so_the_factory_answers_503(fake, call):
    """``back_dev_home/__init__.py`` checks ``type(err) is not RuntimeError``
    and sends subclasses to a 500. A ConnectionError reaching the client
    unwrapped would answer 503 by luck; an OSError would answer 500."""
    fake.fail = True

    with pytest.raises(RuntimeError) as caught:
        if call == "create":
            office.create_short_link(TARGET)
        else:
            office.resolve_short_link("abcdefghij")

    assert type(caught.value) is RuntimeError


def test_an_os_level_failure_is_also_converted(fake):
    """redis-py lets socket-level OSErrors through unwrapped; uncaught they
    would answer 500 ("we have a bug") instead of 503 ("retry")."""

    def boom(*args, **kwargs):
        raise OSError("socket went away")

    fake.set = boom

    with pytest.raises(RuntimeError) as caught:
        office.create_short_link(TARGET)

    assert type(caught.value) is RuntimeError
