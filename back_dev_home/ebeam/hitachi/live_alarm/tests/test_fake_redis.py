"""The fake's own contract.

A double that lied about NX or TTL would make every lock test above it green
for the wrong reason, so the double is tested before anything relies on it.
"""

from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis


RELEASE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) end return 0"
)


def test_set_nx_succeeds_once_then_fails():
    client = FakeRedis()
    assert client.set("k", "first", nx=True, ex=20) is True
    assert client.set("k", "second", nx=True, ex=20) is None
    assert client.get("k") == b"first"


def test_expiry_releases_the_key_when_the_clock_advances():
    client = FakeRedis()
    client.set("k", "v", nx=True, ex=20)
    client.advance(19)
    assert client.set("k", "other", nx=True, ex=20) is None
    client.advance(1)
    assert client.set("k", "other", nx=True, ex=20) is True


def test_eval_deletes_only_when_the_token_matches():
    client = FakeRedis()
    client.set("k", "mine", nx=True, ex=20)
    assert client.eval(RELEASE, 1, "k", "theirs") == 0
    assert client.get("k") == b"mine"
    assert client.eval(RELEASE, 1, "k", "mine") == 1
    assert client.get("k") is None


def test_set_without_nx_overwrites_and_clears_any_ttl():
    client = FakeRedis()
    client.set("k", "v", nx=True, ex=5)
    client.set("k", "w")
    client.advance(10)
    assert client.get("k") == b"w"
