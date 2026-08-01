"""Minimal in-memory stand-in for the Redis commands live_alarm uses.

Hand-rolled rather than pulled from a package: Phase 1 is fully offline,
so the test suite must not require a new dependency. Only the handful of
commands refresh.py issues are implemented.
"""

from __future__ import annotations


class FakePipeline:
    def __init__(self, store: "FakeRedis") -> None:
        self.store = store
        self.ops: list = []

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def zremrangebyscore(self, key, low, high):
        self.ops.append(("zremrangebyscore", key, low, high))
        return self

    def set(self, key, value, ex=None):
        self.ops.append(("set", key, value))
        return self

    def sadd(self, key, member):
        self.ops.append(("sadd", key, member))
        return self

    def expire(self, key, ttl):
        return self

    def execute(self):
        for op in self.ops:
            if op[0] == "zadd":
                self.store.zsets.setdefault(op[1], {}).update(op[2])
            elif op[0] == "zremrangebyscore":
                # Real Redis ZREMRANGEBYSCORE is a no-op on a missing key and
                # never creates it; a ZSET emptied by the removal is deleted.
                # Modelling both faithfully matters because job.py sizes its
                # poll window off client.exists(events_key): a fake that
                # fabricated the key on every prune would hide that a
                # perpetually-quiet fab keeps cold-starting, and would lie to
                # the reader (Task 9) about key presence.
                zset = self.store.zsets.get(op[1])
                if zset is None:
                    continue
                high = float(op[3])
                remaining = {m: s for m, s in zset.items() if float(s) > high}
                if remaining:
                    self.store.zsets[op[1]] = remaining
                else:
                    self.store.zsets.pop(op[1], None)
            elif op[0] == "set":
                self.store.strings[op[1]] = op[2].encode()
            elif op[0] == "sadd":
                self.store.sets.setdefault(op[1], set()).add(op[2])
        self.ops = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeRedis:
    def __init__(self, now: int = 1_000_000) -> None:
        self.zsets: dict[str, dict[str, float]] = {}
        self.strings: dict[str, bytes] = {}
        self.sets: dict[str, set] = {}
        # Expiry is modelled because the lock's TTL IS the feature's retry
        # backoff: a fake that ignored `ex` would make the backoff test pass
        # while the real lock never expired.
        self._expires: dict[str, int] = {}
        self._now = now

    def time(self):
        return (self._now, 0)

    def advance(self, seconds: int) -> None:
        self._now += seconds
        self._evict()

    def _evict(self) -> None:
        for key in [k for k, at in self._expires.items() if at <= self._now]:
            self._expires.pop(key, None)
            self.strings.pop(key, None)
            self.zsets.pop(key, None)
            self.sets.pop(key, None)

    def exists(self, key) -> int:
        self._evict()
        return int(key in self.zsets or key in self.strings)

    def get(self, key):
        self._evict()
        return self.strings.get(key)

    def set(self, key, value, nx: bool = False, ex: int | None = None):
        """redis-py returns True on a write and None when NX declined."""
        self._evict()
        if nx and key in self.strings:
            return None
        self.strings[key] = value.encode() if isinstance(value, str) else value
        if ex is None:
            self._expires.pop(key, None)
        else:
            self._expires[key] = self._now + int(ex)
        return True

    def delete(self, *keys) -> int:
        removed = 0
        for key in keys:
            self._expires.pop(key, None)
            if self.strings.pop(key, None) is not None:
                removed += 1
        return removed

    def eval(self, script, numkeys: int, *args) -> int:
        """The ONE script this feature uses: compare-and-delete.

        The script text is accepted and ignored — this fake implements the
        semantics of refresh._RELEASE_LUA, not a Lua interpreter. If a second
        script is ever added, this must branch on it rather than silently
        applying compare-and-delete to something else.
        """
        self._evict()
        keys, argv = list(args[:numkeys]), list(args[numkeys:])
        expected = argv[0].encode() if isinstance(argv[0], str) else argv[0]
        if self.strings.get(keys[0]) == expected:
            self.delete(keys[0])
            return 1
        return 0

    def sismember(self, key, member) -> bool:
        return member in self.sets.get(key, set())

    def zrangebyscore(self, key, low, high):
        zset = self.store_zset(key)
        low_f = float("-inf") if low == "-inf" else float(low)
        high_f = float("inf") if high == "+inf" else float(high)
        chosen = [(m, s) for m, s in zset.items() if low_f <= float(s) <= high_f]
        return [m.encode() for m, _ in sorted(chosen, key=lambda pair: pair[1])]

    def store_zset(self, key):
        return self.zsets.get(key, {})

    def pipeline(self):
        return FakePipeline(self)
