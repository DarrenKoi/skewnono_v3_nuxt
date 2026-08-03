"""Skip-if-held job lock: a no-op at home, a Redis lock at the office.

Election already guarantees one scheduler process. This is the net for what
election cannot cover -- chiefly the ``max-requests = 1000`` recycle window,
where a dying worker 1 can overlap a booting one.

Built on ``redis.lock.Lock`` because its release/extend Lua scripts are the
owner-checked compare-and-swap this needs: we only DEL or re-EXPIRE the key
while we still hold it.
"""

import json
import logging
import os
import socket
import threading
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any

from back_dev_home._scheduler.runlog import kst_stamp

log = logging.getLogger("skewnono.scheduler")


def lock_owner_token() -> str:
    """This acquisition's lock value: identity plus a uniqueness nonce.

    redis-py compares it byte-for-byte, so any unique string works -- packing
    the holder's identity in means a contender that loses can report *who* beat
    it instead of a bare "lock held".
    """
    return json.dumps(
        {
            "token": uuid.uuid4().hex,
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "acquired": kst_stamp(),
        },
        sort_keys=True,
    )


def describe_lock_holder(client, key: str) -> dict[str, Any]:
    """Who holds ``key`` and how much TTL is left, so a skip is self-diagnosing.

    An orphan from a dead process shows a pid that is gone and a ``held_since``
    far in the past; genuine contention shows a live peer that acquired moments
    ago. Returns ``{}`` if Redis is unreachable -- a skip record must still be
    written.
    """
    try:
        with client.pipeline() as pipe:
            pipe.get(key)
            pipe.ttl(key)
            raw, ttl_remaining = pipe.execute()
    except Exception:
        log.exception("failed to read lock holder for %s", key)
        return {}
    info: dict[str, Any] = {"ttl_remaining": ttl_remaining}
    try:
        owner = json.loads(raw)
    except (ValueError, TypeError):
        owner = None
    if isinstance(owner, dict):
        info["holder"] = f"{owner.get('host')}:{owner.get('pid')}"
        info["held_since"] = owner.get("acquired")
    return info


def _renew_until_stopped(lock, ttl: int, stop: threading.Event) -> None:
    """Re-arm the TTL every ``ttl // 3`` seconds until ``stop`` is set.

    This is what decouples ``ttl`` from job runtime. Without it, ``ttl`` is a
    bet on how long the task takes: bet low and the key expires mid-run so the
    next fire acquires cleanly and runs CONCURRENTLY -- the lock silently stops
    protecting; bet high and one hard kill orphans the key for the full ``ttl``.

    ``replace_ttl=True`` is required: ``extend`` otherwise ADDS to the
    remaining TTL, so every tick pushes expiry further out.
    """
    from redis.exceptions import LockNotOwnedError

    interval = max(ttl // 3, 1)
    while not stop.wait(interval):
        try:
            lock.extend(ttl, replace_ttl=True)
        except LockNotOwnedError:
            # We lost ownership; the key expired and someone else took it. Stop
            # now so the release in the wrapper never deletes the new owner's.
            log.warning("lock %s no longer owned; stopping renewal", lock.name)
            return
        except Exception:
            log.exception("failed to renew lock %s", lock.name)


def _redis_lock(lock, *, ttl: int, on_skip: Callable[[dict], None] | None):
    """Decorator around an already-constructed lock. Split out so tests can
    pass a fake without a Redis server."""
    from redis.exceptions import RedisError

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not lock.acquire(blocking=False, token=lock_owner_token()):
                if on_skip is not None:
                    on_skip({})
                return None
            stop = threading.Event()
            threading.Thread(
                target=_renew_until_stopped,
                args=(lock, ttl, stop),
                name=f"lock-renew:{lock.name}",
                daemon=True,
            ).start()
            try:
                return fn(*args, **kwargs)
            finally:
                # Set first: the watchdog must not re-arm a key we are about to
                # delete.
                stop.set()
                try:
                    lock.release()
                except RedisError:
                    # An exception escaping this finally would REPLACE the job's
                    # own result or mask its real error, and the orphaned key
                    # expires on its own within ttl anyway.
                    log.exception("failed to release lock %s", lock.name)

        return wrapper

    return decorator


def _passthrough(fn: Callable) -> Callable:
    return fn


def make_job_lock(
    cfg,
    job: str,
    on_skip: Callable[[dict], None] | None = None,
    ttl: int | None = None,
):
    """Return the decorator for ``job``.

    Home is a pass-through: election already guarantees one process, and there
    is no reachable Redis to coordinate through anyway.

    ``ttl`` is the registry's per-job ``lock_ttl``; ``None`` or 0 falls back to
    ``cfg.lock_ttl``. Never let a None reach the lock -- redis-py would SET the
    key with no expiry and one killed process would block the job forever.
    """
    ttl = ttl or cfg.lock_ttl

    from back_dev_home._runtime.data_provider import get_mode

    if get_mode() == "mock":
        return _passthrough
    from back_dev_home._runtime.office_redis import redis_client_or_none

    client = redis_client_or_none()
    if client is None:
        log.warning("office mode but Redis is unconfigured; job %r runs unlocked", job)
        return _passthrough

    from redis.lock import Lock

    key = f"{cfg.lock_key_prefix}{job}"
    # thread_local=False: the renewal watchdog calls extend() from ANOTHER
    # thread, and redis-py's default stashes the acquisition token in
    # threading.local() where that thread would find none and raise.
    lock = Lock(client, key, timeout=ttl, thread_local=False)

    def skip_reporter(_info: dict) -> None:
        if on_skip is not None:
            on_skip(describe_lock_holder(client, key))

    return _redis_lock(lock, ttl=ttl, on_skip=skip_reporter)
