"""Minimal in-memory stand-in for the Redis commands the writer uses.

Hand-rolled rather than pulled from a package: Phase 1 is fully offline,
so the test suite must not require a new dependency. Only the handful of
commands job.py issues are implemented.
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
                zset = self.store.zsets.get(op[1], {})
                high = float(op[3])
                self.store.zsets[op[1]] = {
                    m: s for m, s in zset.items() if float(s) > high
                }
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
        self._now = now

    def time(self):
        return (self._now, 0)

    def advance(self, seconds: int) -> None:
        self._now += seconds

    def exists(self, key) -> int:
        return int(key in self.zsets or key in self.strings)

    def get(self, key):
        return self.strings.get(key)

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
