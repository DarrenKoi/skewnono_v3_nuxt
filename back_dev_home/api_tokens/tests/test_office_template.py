"""The office api_tokens adapter — Redis-backed token store.

Verified against an injected fake rather than a live server: home has no Redis,
and the point under test is our key layout, the ``None``/``""`` round-trip, the
touch debounce and revoke idempotency — not redis-py.

Same approach (and the same byte-oriented FakeRedis dialect) as
``msr_image/tests/test_redis_jobs.py``, which is the only other module in the
backend that writes to the office Redis.
"""

from datetime import datetime, timedelta, timezone

import pytest

from back_dev_home.api_tokens.providers import office_example as office

OWNER = "2067928"
OTHER_OWNER = "1234567"


class FakeRedis:
    """In-memory stand-in speaking the byte-oriented dialect of the shared
    office client, which is built with ``decode_responses=False`` (its usual
    values are parquet DataFrames). Returning str here instead of bytes would
    let a decoding bug pass at home and fail at the office."""

    def __init__(self):
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.strings: dict[str, bytes] = {}
        self.sets: dict[str, set[bytes]] = {}
        self.ttls: dict[str, int] = {}

    @staticmethod
    def _b(v) -> bytes:
        return v if isinstance(v, bytes) else str(v).encode()

    def hset(self, key, field=None, value=None, mapping=None):
        h = self.hashes.setdefault(key, {})
        for k, v in (mapping or {}).items():
            h[self._b(k)] = self._b(v)
        if field is not None:
            h[self._b(field)] = self._b(value)

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(self._b(field))

    def set(self, key, value):
        self.strings[key] = self._b(value)

    def get(self, key):
        return self.strings.get(key)

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(self._b(v) for v in values)

    def srem(self, key, *values):
        s = self.sets.get(key, set())
        s.difference_update(self._b(v) for v in values)
        # Redis drops a collection key once it is empty. Modelling that matters
        # here: without it an owner who revokes their last token leaves an empty
        # SET behind forever, and this fake would call that clean.
        if not s:
            self.sets.pop(key, None)

    def smembers(self, key):
        return set(self.sets.get(key, set()))

    def delete(self, *keys):
        removed = 0
        for key in keys:
            for store in (self.hashes, self.strings, self.sets):
                if key in store:
                    del store[key]
                    removed += 1
            self.ttls.pop(key, None)
        return removed

    def expire(self, key, seconds):
        self.ttls[key] = seconds
        return True

    # -- test helpers -------------------------------------------------
    def all_keys(self) -> set[str]:
        return set(self.hashes) | set(self.strings) | set(self.sets)

    def raw_blob(self) -> str:
        """Everything stored, flattened — used to prove no plaintext leaks."""
        parts = [k for k in self.all_keys()]
        for h in self.hashes.values():
            parts += [k.decode() for k in h] + [v.decode() for v in h.values()]
        parts += [v.decode() for v in self.strings.values()]
        for s in self.sets.values():
            parts += [v.decode() for v in s]
        return "\n".join(parts)


@pytest.fixture
def fake(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(office, "_client", lambda: client)
    return client


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


# ── key layout ──────────────────────────────────────────────────────────


def test_create_token_writes_row_owner_index_and_hash_index(fake):
    view, _plaintext = office.create_token(OWNER, "laptop")

    token_id = view["id"]
    assert fake.hashes[f"skewnono:api_tokens:token:{token_id}"]
    assert fake.smembers(f"skewnono:api_tokens:owner:{OWNER}") == {
        token_id.encode()
    }
    # The reverse index is what keeps find_by_plaintext off a full scan.
    hash_keys = [k for k in fake.strings if ":hash:" in k]
    assert len(hash_keys) == 1
    assert fake.get(hash_keys[0]).decode() == token_id


def test_create_token_returns_public_view_and_one_time_plaintext(fake):
    view, plaintext = office.create_token(OWNER, "laptop")

    assert set(view) == {"id", "label", "created_at", "last_used_at"}
    assert view["label"] == "laptop"
    assert view["last_used_at"] is None
    assert plaintext.startswith("skn_")


def test_create_token_coerces_blank_label_to_untitled(fake):
    view, _ = office.create_token(OWNER, "   ")
    assert view["label"] == "untitled"


def test_plaintext_is_never_persisted(fake):
    _view, plaintext = office.create_token(OWNER, "laptop")
    assert plaintext not in fake.raw_blob()


def test_token_rows_carry_no_ttl(fake):
    """Unlike msr_image's job keys, tokens are durable credentials.

    A TTL here would silently log users out when it lapsed.
    """
    office.create_token(OWNER, "laptop")
    assert fake.ttls == {}


# ── list_tokens ─────────────────────────────────────────────────────────


def test_list_tokens_returns_only_this_owners_rows(fake):
    mine, _ = office.create_token(OWNER, "mine")
    office.create_token(OTHER_OWNER, "theirs")

    rows = office.list_tokens(OWNER)

    assert [r["id"] for r in rows] == [mine["id"]]
    assert rows[0]["label"] == "mine"


def test_list_tokens_with_no_tokens_returns_empty_list(fake):
    assert office.list_tokens(OWNER) == []


def test_list_tokens_skips_a_row_whose_hash_expired_out(fake):
    """A stale id in the owner index must not fabricate a half-empty row."""
    view, _ = office.create_token(OWNER, "mine")
    fake.delete(f"skewnono:api_tokens:token:{view['id']}")

    assert office.list_tokens(OWNER) == []


def test_absent_last_used_at_round_trips_as_none_not_the_string_none(fake):
    """Redis hashes hold strings, so ``None`` needs an explicit encoding."""
    office.create_token(OWNER, "laptop")

    assert office.list_tokens(OWNER)[0]["last_used_at"] is None


# ── find_by_plaintext (bearer-auth path) ────────────────────────────────


def test_find_by_plaintext_resolves_a_freshly_created_secret(fake):
    view, plaintext = office.create_token(OWNER, "laptop")

    row = office.find_by_plaintext(plaintext)

    # middleware.py reads ATTRIBUTES off this row, not dict keys.
    assert row.id == view["id"]
    assert row.owner_user_id == OWNER


def test_find_by_plaintext_rejects_a_wrong_prefix_without_reading_redis(
    fake, monkeypatch
):
    office.create_token(OWNER, "laptop")

    def explode():
        raise AssertionError("must short-circuit before touching Redis")

    monkeypatch.setattr(office, "_client", explode)
    assert office.find_by_plaintext("nope_not-a-real-token") is None


def test_find_by_plaintext_misses_a_correct_prefix_with_unknown_hash(fake):
    office.create_token(OWNER, "laptop")
    assert office.find_by_plaintext("skn_not-a-real-token") is None


def test_find_by_plaintext_misses_when_the_index_outlives_the_row(fake):
    _view, plaintext = office.create_token(OWNER, "laptop")
    for key in [k for k in fake.hashes if ":token:" in k]:
        fake.delete(key)

    assert office.find_by_plaintext(plaintext) is None


# ── revoke_token ────────────────────────────────────────────────────────


def test_revoke_token_removes_row_owner_index_and_hash_index(fake):
    view, _ = office.create_token(OWNER, "laptop")

    assert office.revoke_token(OWNER, view["id"]) is True

    assert fake.all_keys() == set()


def test_revoke_token_is_idempotent(fake):
    view, _ = office.create_token(OWNER, "laptop")

    assert office.revoke_token(OWNER, view["id"]) is True
    # Real clients retry; a DEL on a gone key must read as False, not raise.
    assert office.revoke_token(OWNER, view["id"]) is False


def test_revoke_token_refuses_another_owners_token(fake):
    view, _ = office.create_token(OWNER, "laptop")

    assert office.revoke_token(OTHER_OWNER, view["id"]) is False
    # And the refusal must not have deleted anything.
    assert office.list_tokens(OWNER)[0]["id"] == view["id"]


def test_revoked_token_no_longer_authenticates(fake):
    view, plaintext = office.create_token(OWNER, "laptop")
    office.revoke_token(OWNER, view["id"])

    assert office.find_by_plaintext(plaintext) is None


# ── touch_last_used ─────────────────────────────────────────────────────


def test_touch_last_used_writes_on_first_use(fake):
    view, _ = office.create_token(OWNER, "laptop")

    office.touch_last_used(view["id"])

    assert office.list_tokens(OWNER)[0]["last_used_at"] is not None


def test_touch_last_used_debounces_a_second_call_inside_the_window(fake):
    view, _ = office.create_token(OWNER, "laptop")
    recent = _iso(datetime.now(timezone.utc) - timedelta(seconds=5))
    fake.hset(f"skewnono:api_tokens:token:{view['id']}", "last_used_at", recent)

    office.touch_last_used(view["id"])

    assert office.list_tokens(OWNER)[0]["last_used_at"] == recent


def test_touch_last_used_writes_again_once_the_window_has_passed(fake):
    view, _ = office.create_token(OWNER, "laptop")
    stale = _iso(datetime.now(timezone.utc) - timedelta(minutes=2))
    fake.hset(f"skewnono:api_tokens:token:{view['id']}", "last_used_at", stale)

    office.touch_last_used(view["id"])

    assert office.list_tokens(OWNER)[0]["last_used_at"] != stale


def test_touch_last_used_on_an_unknown_token_is_a_noop(fake):
    office.touch_last_used("deadbeefcafe")
    assert fake.all_keys() == set()
