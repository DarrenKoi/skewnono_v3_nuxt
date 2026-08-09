"""The fake's own contract.

A double that lied about NX or TTL would make every lock test above it green
for the wrong reason, so the double is tested before anything relies on it.
"""

from back_dev_home.ebeam.live_alarm.tests.fake_redis import FakeRedis


# The Lua text is irrelevant to the fake — redis.lock.Lock registers its own
# release script and the double reproduces that script's semantics.
RELEASE = "<redis.lock.Lock LUA_RELEASE_SCRIPT>"


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


def test_registered_release_script_deletes_only_when_the_token_matches():
    client = FakeRedis()
    release = client.register_script(RELEASE)
    client.set("k", "mine", nx=True, ex=20)
    assert release(keys=["k"], args=["theirs"], client=client) == 0
    assert client.get("k") == b"mine"
    assert release(keys=["k"], args=["mine"], client=client) == 1
    assert client.get("k") is None


def test_px_expiry_matches_ex_expiry():
    # redis.lock.Lock.acquire uses px (milliseconds), not ex.
    client = FakeRedis()
    client.set("k", "v", nx=True, px=20_000)
    client.advance(19)
    assert client.set("k", "other", nx=True, px=20_000) is None
    client.advance(1)
    assert client.set("k", "other", nx=True, px=20_000) is True


def test_set_without_nx_overwrites_and_clears_any_ttl():
    client = FakeRedis()
    client.set("k", "v", nx=True, ex=5)
    client.set("k", "w")
    client.advance(10)
    assert client.get("k") == b"w"
