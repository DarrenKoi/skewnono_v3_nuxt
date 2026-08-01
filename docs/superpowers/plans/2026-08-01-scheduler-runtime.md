# Scheduler Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Flask backend one shared scheduler that runs exactly one copy of each periodic job across all uWSGI workers, records every run, and carries three jobs — image_cache purge, device-statistics weekly snapshot, and snapshot retention sweep.

**Architecture:** A new `back_dev_home/_scheduler/` package (underscore-prefixed, so blueprint autodiscovery skips it). Election decides which process owns the scheduler; each job is wrapped `job_lock(run_log.wrap(fn))` so a blocked run emits exactly one `skip` record. Home and office differ only in two swappable pieces — the run log (memory ring buffer vs Redis list) and the lock (no-op vs `redis.lock.Lock` with TTL renewal). Both use APScheduler's default memory jobstore.

**Tech Stack:** Python 3.14, Flask 3, APScheduler 3.10+ (`BackgroundScheduler`), redis-py 5+, pytest. No new dependencies — `apscheduler` is already in `back_dev_home/requirements.txt:16`.

**Spec:** `docs/superpowers/specs/2026-08-01-scheduler-runtime-design.md`

## Global Constraints

- **Never edit `providers/office.py`.** It is gitignored. The tracked template is `providers/office_example.py`; edit that.
- **Commit only files you edited.** Always pass explicit pathspecs. `git add -A`, `git add .`, `git commit -a` are banned — several agent sessions share this working tree.
- **Run pytest as `python -m pytest` from the repo root.** The `-m` is what puts the root on `sys.path`. Full suite: `.venv/bin/python -m pytest -q`.
- **Mode gating uses `get_mode()`, never `is_cloud()`.** Phase 2 runs on office localhost, where the filesystem looks like home.
- **Every office fact gets a provenance marker:** `office 확인 YYYY-MM-DD`, `user-confirmed`, or `OFFICE-VERIFY`.
- **`npm run lint:md` from the repo root after any Markdown edit.** Tables use markdownlint `MD060` `compact` style.
- **Korean for `docs/` and `MIGRATION.md` prose**, with formal endings (`~입니다.`, `~합니다.`). Python docstrings follow whatever the file already uses.
- **Retention and paths are env vars, not constants** — `SKEWNONO_WEEKLY_TREND_KEEP_WEEKS` (default 12), `SKEWNONO_WEEKLY_TREND_DIR` (default `var/weekly_trend`). Tuning must not require a deploy.

---

### Task 1: Scheduler config

**Files:**
- Create: `back_dev_home/_scheduler/__init__.py`
- Create: `back_dev_home/_scheduler/config.py`
- Create: `back_dev_home/_scheduler/tests/__init__.py`
- Test: `back_dev_home/_scheduler/tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SchedulerConfig` (frozen dataclass) with fields `lock_ttl: int`, `lock_key_prefix: str`, `log_list_key: str`, `log_list_max: int`, `timezone: str`; and `load_scheduler_config(env: Mapping[str, str] | None = None) -> SchedulerConfig`.

This mirrors `back_dev_home/msr_image/config.py` exactly — same `_int` helper shape, same "env is a parameter with an `os.environ` default" signature, so it is testable without monkeypatching.

- [ ] **Step 1: Create the package directories**

```bash
mkdir -p back_dev_home/_scheduler/tasks back_dev_home/_scheduler/tests
touch back_dev_home/_scheduler/tasks/__init__.py back_dev_home/_scheduler/tests/__init__.py
```

Leave `back_dev_home/_scheduler/__init__.py` empty for now; Task 9 fills it in.

```bash
touch back_dev_home/_scheduler/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `back_dev_home/_scheduler/tests/test_config.py`:

```python
from back_dev_home._scheduler.config import SchedulerConfig, load_scheduler_config


def test_defaults_when_env_is_empty():
    cfg = load_scheduler_config({})
    assert cfg.lock_ttl == 600
    assert cfg.log_list_max == 500
    assert cfg.timezone == "Asia/Seoul"
    assert cfg.lock_key_prefix == "skewnono:scheduler:lock:"
    assert cfg.log_list_key == "skewnono:scheduler:logs"


def test_env_overrides_are_read():
    cfg = load_scheduler_config(
        {"SKEWNONO_SCHEDULER_LOCK_TTL": "90", "SKEWNONO_SCHEDULER_LOG_MAX": "40"}
    )
    assert cfg.lock_ttl == 90
    assert cfg.log_list_max == 40


def test_garbage_env_falls_back_to_the_default():
    # A typo'd env var must not take the scheduler down at boot -- it is
    # plumbing, and refusing to start would cost more than one bad value.
    cfg = load_scheduler_config({"SKEWNONO_SCHEDULER_LOCK_TTL": "not-a-number"})
    assert cfg.lock_ttl == 600


def test_config_is_frozen():
    cfg = load_scheduler_config({})
    try:
        cfg.lock_ttl = 1  # type: ignore[misc]
    except Exception as exc:
        assert type(exc).__name__ == "FrozenInstanceError"
    else:
        raise AssertionError("SchedulerConfig must be frozen")


def test_is_a_schedulerconfig():
    assert isinstance(load_scheduler_config({}), SchedulerConfig)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_config.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._scheduler.config'`

- [ ] **Step 4: Write the implementation**

Create `back_dev_home/_scheduler/config.py`:

```python
"""Environment-driven config for the shared scheduler.

Same shape as ``msr_image/config.py``: ``env`` is a parameter with an
``os.environ`` default, so tests pass a dict instead of monkeypatching, and a
malformed value falls back to the default rather than raising. The scheduler is
plumbing -- refusing to boot over one typo'd env var would cost more than the
bad value does.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(env.get(key, "").strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class SchedulerConfig:
    # Orphan-clear window, NOT a runtime budget. A live run re-arms its own TTL
    # (see locks.py), so this only bounds how long a lock survives a process
    # that died without releasing it. All three jobs are daily or weekly, so
    # any value under a day skips zero runs -- keep it small so an orphan from
    # an OOM-killed worker clears in minutes instead of blocking tomorrow too.
    lock_ttl: int = 600
    lock_key_prefix: str = "skewnono:scheduler:lock:"
    log_list_key: str = "skewnono:scheduler:logs"
    log_list_max: int = 500
    timezone: str = "Asia/Seoul"


def load_scheduler_config(env: Mapping[str, str] | None = None) -> SchedulerConfig:
    env = os.environ if env is None else env
    return SchedulerConfig(
        lock_ttl=_int(env, "SKEWNONO_SCHEDULER_LOCK_TTL", 600),
        log_list_max=_int(env, "SKEWNONO_SCHEDULER_LOG_MAX", 500),
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_config.py -q`

Expected: PASS — 5 passed

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/_scheduler/__init__.py back_dev_home/_scheduler/config.py \
        back_dev_home/_scheduler/tasks/__init__.py \
        back_dev_home/_scheduler/tests/__init__.py \
        back_dev_home/_scheduler/tests/test_config.py
git commit -m "feat(scheduler): add SchedulerConfig with env overrides"
```

---

### Task 2: Election

**Files:**
- Create: `back_dev_home/_scheduler/election.py`
- Test: `back_dev_home/_scheduler/tests/test_election.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `is_scheduler_worker(app) -> bool`.

Three cases in order: uWSGI (worker 1 only), Werkzeug reloader (app child only, not the watcher parent), otherwise this process. The reloader case is the one that is broken today — see the spec § 3.3.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_scheduler/tests/test_election.py`:

```python
import sys
import types

import pytest
from flask import Flask

from back_dev_home._scheduler.election import is_scheduler_worker


def _app(debug: bool) -> Flask:
    app = Flask(__name__)
    app.debug = debug
    return app


@pytest.fixture
def fake_uwsgi(monkeypatch):
    """Install a stub `uwsgi` module; the real one only exists under uWSGI."""

    def install(worker_id: int):
        module = types.ModuleType("uwsgi")
        module.worker_id = lambda: worker_id  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "uwsgi", module)

    return install


def test_uwsgi_worker_one_is_elected(fake_uwsgi, monkeypatch):
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    fake_uwsgi(1)
    assert is_scheduler_worker(_app(debug=False)) is True


def test_uwsgi_other_workers_are_not_elected(fake_uwsgi, monkeypatch):
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    for worker_id in (2, 3, 4):
        fake_uwsgi(worker_id)
        assert is_scheduler_worker(_app(debug=False)) is False


def test_reloader_parent_is_not_elected(monkeypatch):
    # The Werkzeug reloader runs the module in TWO processes. The watcher
    # parent has debug=True and no WERKZEUG_RUN_MAIN; electing it too would
    # put two schedulers on one dev machine.
    monkeypatch.delitem(sys.modules, "uwsgi", raising=False)
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    assert is_scheduler_worker(_app(debug=True)) is False


def test_reloader_child_is_elected(monkeypatch):
    monkeypatch.delitem(sys.modules, "uwsgi", raising=False)
    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    assert is_scheduler_worker(_app(debug=True)) is True


def test_single_process_without_debug_is_elected(monkeypatch):
    monkeypatch.delitem(sys.modules, "uwsgi", raising=False)
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    assert is_scheduler_worker(_app(debug=False)) is True
```

Note: `monkeypatch.delitem(sys.modules, "uwsgi", raising=False)` is required because `fake_uwsgi` from an earlier test leaves a stub behind in the same session.

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_election.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._scheduler.election'`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/_scheduler/election.py`:

```python
"""Which process owns the scheduler thread.

Exactly one process must run each job. This module answers "is that me?" in
three cases, checked in order.

1. **uWSGI** (Phase 3, and Phase 2 if run that way). ``wsgi.ini`` sets
   ``lazy-apps = true``, so every worker calls ``create_app()`` itself and
   would naively get its own scheduler thread. APScheduler does NOT coordinate
   across schedulers, so we elect worker 1 and let the others serve requests
   only. ``lazy-apps`` is load-bearing here: under preforking the app is built
   once in the master and threads do not survive ``fork()``, so the scheduler
   would exist in no process at all.

2. **Werkzeug reloader** (Phase 1/2 dev server -- ``index.py`` sets
   ``debug=not cloud``). The reloader runs the module in TWO processes: a
   watcher parent and the app child. Both call ``create_app()`` and neither is
   uWSGI, so without this case a single dev machine gets two schedulers. Only
   the child carries ``WERKZEUG_RUN_MAIN``, so "debug and no WERKZEUG_RUN_MAIN"
   identifies the parent exactly. uWSGI and cloud never reach here -- debug is
   False there.

3. **Anything else** -- a single-process run, pytest. Elected.

This is deliberately NOT gated on ``get_mode()`` or ``is_cloud()``: it answers
"which process", a different question from "which data source". The mode gate
lives in ``runlog.py`` and ``locks.py``, which pick their backends.
"""

import os


def _reloader_parent(app) -> bool:
    return bool(app.debug) and os.environ.get("WERKZEUG_RUN_MAIN") != "true"


def is_scheduler_worker(app) -> bool:
    try:
        import uwsgi  # type: ignore[import-not-found]
    except ImportError:
        pass
    else:
        return uwsgi.worker_id() == 1
    if _reloader_parent(app):
        return False
    return True
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_election.py -q`

Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_scheduler/election.py back_dev_home/_scheduler/tests/test_election.py
git commit -m "feat(scheduler): elect one scheduler process

Handles uWSGI worker-1 election and the Werkzeug reloader's two-process
split. The reloader case is not theoretical: index.py sets debug=not cloud,
so the home dev server has been running two msr_image purge schedulers
(its guard is per-app-object and cannot see across processes)."
```

---

### Task 3: Run log

**Files:**
- Create: `back_dev_home/_scheduler/runlog.py`
- Test: `back_dev_home/_scheduler/tests/test_runlog.py`

**Interfaces:**
- Consumes: `SchedulerConfig` (Task 1).
- Produces:
  - `RunLog` Protocol with `record(job: str, event: str, **extra) -> None`, `read(limit: int) -> list[dict]`, `wrap(fn: Callable, name: str) -> Callable`.
  - `MemoryRunLog(max_records: int)`, `RedisRunLog(client, key: str, max_records: int)`.
  - `make_run_log(cfg: SchedulerConfig) -> RunLog` — picks by `get_mode()`.
  - `utc_stamp() -> str`.

`wrap` lives on the run log (as in `flask_modules`' `TaskLogger.wrap`) so start/end/error bracketing is defined once for both backends.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_scheduler/tests/test_runlog.py`:

```python
import pytest

from back_dev_home._scheduler.runlog import MemoryRunLog, utc_stamp


def test_records_are_newest_first():
    log = MemoryRunLog(max_records=10)
    log.record("job_a", "start")
    log.record("job_b", "start")
    rows = log.read(limit=10)
    assert [r["job"] for r in rows] == ["job_b", "job_a"]


def test_ring_buffer_drops_the_oldest():
    log = MemoryRunLog(max_records=2)
    for name in ("a", "b", "c"):
        log.record(name, "start")
    rows = log.read(limit=10)
    assert [r["job"] for r in rows] == ["c", "b"]


def test_every_record_has_ts_job_event():
    log = MemoryRunLog(max_records=5)
    log.record("job_a", "skip", holder="host:123")
    row = log.read(limit=1)[0]
    assert row["job"] == "job_a"
    assert row["event"] == "skip"
    assert row["holder"] == "host:123"
    assert row["ts"].endswith("+00:00")


def test_wrap_brackets_a_successful_call_with_start_and_end():
    log = MemoryRunLog(max_records=10)
    wrapped = log.wrap(lambda: 7, "job_a")
    assert wrapped() == 7
    events = [r["event"] for r in log.read(limit=10)]
    assert events == ["end", "start"]
    assert log.read(limit=10)[0]["duration_ms"] >= 0


def test_wrap_records_error_and_reraises():
    log = MemoryRunLog(max_records=10)

    def boom():
        raise ValueError("nope")

    wrapped = log.wrap(boom, "job_a")
    with pytest.raises(ValueError):
        wrapped()
    rows = log.read(limit=10)
    assert [r["event"] for r in rows] == ["error", "start"]
    assert "nope" in rows[0]["error"]


def test_wrap_uses_the_registry_name_not_the_function_name():
    # The registry key is the job's identity everywhere -- lock key, scheduler
    # job id, and log records. Deriving it from fn.__name__ splits that the
    # moment an entry is named differently from its function.
    log = MemoryRunLog(max_records=10)
    log.wrap(lambda: None, "registry_name")()
    assert log.read(limit=1)[0]["job"] == "registry_name"


def test_utc_stamp_is_second_precision_aware_utc():
    stamp = utc_stamp()
    assert stamp.endswith("+00:00")
    assert "." not in stamp
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_runlog.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._scheduler.runlog'`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/_scheduler/runlog.py`:

```python
"""Job-run records, in memory at home and in a Redis list at the office.

Both backends satisfy :class:`RunLog`. ``wrap`` lives here rather than in the
registry so the start/end/error bracketing is defined once and both backends
get it.

Every write failure is swallowed-and-logged. Observability must never break the
task it observes -- a Redis blip should not turn a working purge into a failed
one.
"""

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Protocol

log = logging.getLogger("skewnono.scheduler")


def utc_stamp() -> str:
    """Second-precision aware-UTC ISO timestamp -- the one format records use.

    Stored in UTC and rendered locally by the caller, so records stay
    comparable across hosts while operators still read Seoul time.
    """
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunLog(Protocol):
    def record(self, job: str, event: str, **extra: Any) -> None: ...
    def read(self, limit: int) -> list[dict[str, Any]]: ...
    def wrap(self, fn: Callable, name: str) -> Callable: ...


class _WrapMixin:
    def wrap(self, fn: Callable, name: str) -> Callable:
        """Emit start / end / error around each call.

        ``name`` is the registry key, never ``fn.__name__``: the key is the
        job's identity for the lock, the scheduler job id and these records,
        and deriving one of them differently splits that identity.
        """

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.record(name, "start")  # type: ignore[attr-defined]
            started = time.monotonic()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                self.record(  # type: ignore[attr-defined]
                    name,
                    "error",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error=repr(exc),
                )
                raise
            self.record(  # type: ignore[attr-defined]
                name,
                "end",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            return result

        return wrapper


def _build(job: str, event: str, extra: dict[str, Any]) -> dict[str, Any]:
    record = {"ts": utc_stamp(), "job": job, "event": event}
    record.update(extra)
    return record


class MemoryRunLog(_WrapMixin):
    """Home backend. A bounded deque, newest first.

    Per-process, which is correct at home: election guarantees one scheduler
    process, and that same process answers /api/health/jobs.
    """

    def __init__(self, max_records: int = 500) -> None:
        self._records: deque[dict[str, Any]] = deque(maxlen=max_records)

    def record(self, job: str, event: str, **extra: Any) -> None:
        record = _build(job, event, extra)
        log.info("task-run %s", record)
        self._records.appendleft(record)

    def read(self, limit: int) -> list[dict[str, Any]]:
        return list(self._records)[:limit]


class RedisRunLog(_WrapMixin):
    """Office backend. LPUSH + LTRIM in one round-trip.

    Shared across workers on purpose: the elected worker writes, and any worker
    can answer /api/health/jobs.
    """

    def __init__(self, client, key: str, max_records: int = 500) -> None:
        self.client = client
        self.key = key
        self.max_records = max_records

    def record(self, job: str, event: str, **extra: Any) -> None:
        record = _build(job, event, extra)
        log.info("task-run %s", record)
        try:
            with self.client.pipeline() as pipe:
                pipe.lpush(self.key, json.dumps(record))
                pipe.ltrim(self.key, 0, self.max_records - 1)
                pipe.execute()
        except Exception:
            log.exception("failed to push task-run record")

    def read(self, limit: int) -> list[dict[str, Any]]:
        try:
            raw = self.client.lrange(self.key, 0, limit - 1)
        except Exception:
            log.exception("failed to read task-run records")
            return []
        out: list[dict[str, Any]] = []
        for item in raw:
            try:
                out.append(json.loads(item))
            except (ValueError, TypeError):
                # Lenient, like the rest of this module: one malformed entry
                # must not hide the records around it.
                log.warning("dropping malformed task-log entry: %r", item)
        return out


def make_run_log(cfg) -> RunLog:
    """Pick the backend by mode. Office falls back to memory if Redis is not
    configured -- a scheduler with no run log is far better than no scheduler."""
    from back_dev_home._runtime.data_provider import get_mode

    if get_mode() == "mock":
        return MemoryRunLog(cfg.log_list_max)
    from back_dev_home._runtime.office_redis import redis_client_or_none

    client = redis_client_or_none()
    if client is None:
        log.warning("office mode but Redis is unconfigured; run log is memory-only")
        return MemoryRunLog(cfg.log_list_max)
    return RedisRunLog(client, cfg.log_list_key, cfg.log_list_max)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_runlog.py -q`

Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_scheduler/runlog.py back_dev_home/_scheduler/tests/test_runlog.py
git commit -m "feat(scheduler): add run log with memory and Redis backends"
```

---

### Task 4: Job lock

**Files:**
- Create: `back_dev_home/_scheduler/locks.py`
- Test: `back_dev_home/_scheduler/tests/test_locks.py`

**Interfaces:**
- Consumes: `SchedulerConfig` (Task 1), `RunLog` (Task 3).
- Produces: `make_job_lock(cfg, job: str, on_skip: Callable[[dict], None] | None = None) -> Callable[[Callable], Callable]` — a decorator factory. Home returns a pass-through; office returns the Redis lock.
- Produces: `lock_owner_token() -> str`, `describe_lock_holder(client, key) -> dict`.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_scheduler/tests/test_locks.py`:

```python
import json
import time

from back_dev_home._scheduler.config import load_scheduler_config
from back_dev_home._scheduler.locks import (
    _redis_lock,
    lock_owner_token,
    make_job_lock,
)


class FakeLock:
    """Enough of redis.lock.Lock for the wrapper's contract."""

    def __init__(self, *, acquirable: bool = True):
        self.acquirable = acquirable
        self.released = False
        self.extends: list[tuple[int, bool]] = []
        self.name = "fake"

    def acquire(self, blocking=False, token=None):
        self.token = token
        return self.acquirable

    def extend(self, ttl, replace_ttl=False):
        self.extends.append((ttl, replace_ttl))

    def release(self):
        self.released = True


def test_home_lock_is_a_passthrough(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    cfg = load_scheduler_config({})
    calls = []
    wrapped = make_job_lock(cfg, "job_a")(lambda: calls.append(1))
    wrapped()
    wrapped()
    assert len(calls) == 2


def test_lock_runs_the_function_and_releases():
    lock = FakeLock(acquirable=True)
    calls = []
    wrapped = _redis_lock(lock, ttl=600, on_skip=None)(lambda: calls.append(1))
    assert wrapped() is None or True
    assert len(calls) == 1
    assert lock.released is True


def test_lock_skips_when_held_and_does_not_call_the_function():
    lock = FakeLock(acquirable=False)
    calls = []
    skips = []
    wrapped = _redis_lock(lock, ttl=600, on_skip=skips.append)(lambda: calls.append(1))
    wrapped()
    assert calls == []
    assert len(skips) == 1


def test_release_still_happens_when_the_function_raises():
    lock = FakeLock(acquirable=True)

    def boom():
        raise ValueError("nope")

    wrapped = _redis_lock(lock, ttl=600, on_skip=None)(boom)
    try:
        wrapped()
    except ValueError:
        pass
    assert lock.released is True


def test_release_error_does_not_replace_the_functions_exception():
    from redis.exceptions import RedisError

    class ExplodingRelease(FakeLock):
        def release(self):
            raise RedisError("connection lost")

    lock = ExplodingRelease(acquirable=True)

    def boom():
        raise ValueError("the real error")

    wrapped = _redis_lock(lock, ttl=600, on_skip=None)(boom)
    try:
        wrapped()
    except Exception as exc:
        # The job's own error must survive; a failed release must not mask it.
        assert isinstance(exc, ValueError)
        assert str(exc) == "the real error"
    else:
        raise AssertionError("expected the function's ValueError")


def test_owner_token_carries_host_and_pid():
    payload = json.loads(lock_owner_token())
    assert set(payload) == {"token", "host", "pid", "acquired"}
    assert isinstance(payload["pid"], int)


def test_renewal_re_arms_the_ttl_with_replace_ttl():
    # Without replace_ttl=True, extend ADDS to the remaining TTL, so every tick
    # pushes expiry further out and a killed process orphans the lock far
    # beyond ttl -- inverting the property the TTL exists to provide.
    #
    # ttl=3 makes the watchdog tick every ttl//3 = 1s, so a job that runs ~1.3s
    # sees at least one renewal. Asserting `extends` is non-empty is the point:
    # without it this test passes vacuously on an empty list, proving nothing.
    lock = FakeLock(acquirable=True)

    wrapped = _redis_lock(lock, ttl=3, on_skip=None)(lambda: time.sleep(1.3))
    wrapped()

    assert lock.extends, "the watchdog never renewed the lock"
    assert all(replace is True for _ttl, replace in lock.extends)
    assert all(ttl == 3 for ttl, _replace in lock.extends)


def test_renewal_stops_when_the_job_finishes():
    # The watchdog must not re-arm a key the wrapper is about to delete.
    lock = FakeLock(acquirable=True)
    wrapped = _redis_lock(lock, ttl=3, on_skip=None)(lambda: None)
    wrapped()
    ticks_at_exit = len(lock.extends)
    time.sleep(1.5)
    assert len(lock.extends) == ticks_at_exit
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_locks.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._scheduler.locks'`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/_scheduler/locks.py`:

```python
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

from back_dev_home._scheduler.runlog import utc_stamp

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
            "acquired": utc_stamp(),
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


def make_job_lock(cfg, job: str, on_skip: Callable[[dict], None] | None = None):
    """Return the decorator for ``job``.

    Home is a pass-through: election already guarantees one process, and there
    is no reachable Redis to coordinate through anyway.
    """
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
    lock = Lock(client, key, timeout=cfg.lock_ttl, thread_local=False)

    def skip_reporter(_info: dict) -> None:
        if on_skip is not None:
            on_skip(describe_lock_holder(client, key))

    return _redis_lock(lock, ttl=cfg.lock_ttl, on_skip=skip_reporter)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_locks.py -q`

Expected: PASS — 8 passed

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_scheduler/locks.py back_dev_home/_scheduler/tests/test_locks.py
git commit -m "feat(scheduler): add skip-if-held job lock with TTL renewal"
```

---

### Task 5: Relocate the image_cache purge job

**Files:**
- Create: `back_dev_home/_scheduler/tasks/image_cache.py`
- Delete: `back_dev_home/msr_image/scheduler.py`
- Modify: `back_dev_home/msr_image/tests/test_scheduler.py` (retarget the import)
- Modify: `back_dev_home/__init__.py:287-288` (drop the old start call)

**Interfaces:**
- Consumes: `msr_image.cache.make_cache`, `msr_image.config.load_config`, `msr_image.data.provider_name`.
- Produces: `purge_image_cache(cfg: ImageConfig | None = None) -> int`.

The old module mixed a task body (`purge_now`) with scheduling policy (`start_purge_scheduler`). The body moves here; the policy is replaced by the registry in Task 9. The factory temporarily starts no scheduler at all between this task and Task 9 — that is intentional and the suite must stay green throughout.

- [ ] **Step 1: Write the failing test**

Replace `back_dev_home/msr_image/tests/test_scheduler.py` entirely:

```python
import os
import time

from back_dev_home._scheduler.tasks.image_cache import purge_image_cache
from back_dev_home.msr_image.cache import DiskImageCache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator


def test_purge_image_cache_removes_expired(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    cfg = load_config({"IMAGE_CACHE_DIR": str(tmp_path), "IMAGE_CACHE_TTL_HOURS": "72"})
    cache = DiskImageCache(str(tmp_path))
    loc = ImageLocator("10.0.0.1", "ADI", "MSR_1", "a.jpeg")
    cache.put(loc, FetchedImage(b"x", "image/jpeg", None))
    aged = tmp_path / "10.0.0.1" / "ADI" / "MSR_1" / "a.jpeg"
    old = time.time() - 100 * 3600
    os.utime(aged, (old, old))

    assert purge_image_cache(cfg) == 1
    assert cache.get(loc) is None


def test_purge_image_cache_keeps_fresh_objects(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    cfg = load_config({"IMAGE_CACHE_DIR": str(tmp_path), "IMAGE_CACHE_TTL_HOURS": "72"})
    cache = DiskImageCache(str(tmp_path))
    loc = ImageLocator("10.0.0.1", "ADI", "MSR_1", "fresh.jpeg")
    cache.put(loc, FetchedImage(b"x", "image/jpeg", None))

    assert purge_image_cache(cfg) == 0
    assert cache.get(loc) is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/msr_image/tests/test_scheduler.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._scheduler.tasks.image_cache'`

- [ ] **Step 3: Create the task module**

Create `back_dev_home/_scheduler/tasks/image_cache.py`:

```python
"""Nightly image-cache purge.

A thin call-through: home deletes disk files, office sweeps the MinIO cache
prefix by ``last_modified`` (``MinioImageCache.purge``). The deletion logic
itself stays in ``msr_image`` -- this module only names the job. Duplicate runs
are idempotent.

Relocated from ``msr_image/scheduler.py``, which mixed this body with its own
BackgroundScheduler. Scheduling policy now lives in ``_scheduler/registry.py``.
"""

import logging

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import ImageConfig, load_config

logger = logging.getLogger("skewnono.scheduler")


def purge_image_cache(cfg: ImageConfig | None = None) -> int:
    cfg = cfg or load_config()
    cache = make_cache(cfg, data.provider_name())
    removed = cache.purge(cfg.ttl_hours)
    logger.info("image_cache purge removed %d objects", removed)
    return removed
```

- [ ] **Step 4: Delete the old module and unwire the factory**

```bash
git rm back_dev_home/msr_image/scheduler.py
```

In `back_dev_home/__init__.py`, delete these two lines (currently at 287-288, just before `return app`):

```python
    from back_dev_home.msr_image.scheduler import start_purge_scheduler
    start_purge_scheduler(app)
```

Task 9 puts `start_scheduler(app)` in their place. Between now and then the app starts no scheduler, which is fine — no test asserts one exists yet.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/msr_image -q`

Expected: PASS — the whole msr_image suite, with no import errors from the deleted module.

- [ ] **Step 6: Confirm nothing else referenced the old module**

Run: `grep -rn "msr_image.scheduler\|start_purge_scheduler\|purge_now" back_dev_home docs --include='*.py' --include='*.md' | grep -v docs/superpowers/plans`

Expected: no output. (Plans under `docs/superpowers/plans/` are historical records of past work and are not updated.)

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/_scheduler/tasks/image_cache.py \
        back_dev_home/msr_image/tests/test_scheduler.py \
        back_dev_home/__init__.py
git rm --cached back_dev_home/msr_image/scheduler.py 2>/dev/null || true
git commit -m "refactor(scheduler): move the image-cache purge into _scheduler/tasks

Splits the task body from the scheduling policy. msr_image/scheduler.py
started its own BackgroundScheduler inside create_app(), which under
wsgi.ini's processes=4 + lazy-apps=true meant all four workers fired the
purge nightly. The body moves here; the registry takes over scheduling."
```

---

### Task 6: Home snapshot store

**Files:**
- Create: `back_dev_home/ebeam/cdsem/device_statistics/providers/snapshot_store.py`
- Modify: `back_dev_home/ebeam/cdsem/device_statistics/providers/mock.py` (re-export)
- Test: `back_dev_home/ebeam/cdsem/device_statistics/tests/test_snapshot_store.py`

**Interfaces:**
- Consumes: `providers/statistics.py`'s `get_weekly_trend_data`, `RCP_BUCKETS`, `_trend_dates`.
- Produces: `build_weekly_snapshot(date_key: str | None = None) -> dict`, `write_weekly_snapshot(date_key: str | None = None) -> str` (returns the file path), `sweep_weekly_snapshots(keep_weeks: int = 12) -> int`, `snapshot_dir() -> Path`.

A separate module rather than growing `mock.py`, which is already the interlocking-fixtures surface other features import from.

**Two things that are easy to get wrong here:**

1. The mock's weeks are anchored on `BASE_TIME` (a fixed mock instant), not on today — see `statistics.py:_trend_dates`. `build_weekly_snapshot(None)` must use the same anchor, or the file it writes is named for a week the trend never returns.
2. `get_weekly_trend_data` must stay live for all weeks. Do **not** give the mock the office's "omit past weeks with no snapshot" rule — a fresh checkout has no snapshots, so that would return 1 date instead of 8 and blank the trend chart. Task 6 Step 1 has a regression test pinning this.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/ebeam/cdsem/device_statistics/tests/test_snapshot_store.py`:

```python
import json

from back_dev_home.ebeam.cdsem.device_statistics.data import get_weekly_trend_data
from back_dev_home.ebeam.cdsem.device_statistics.providers.snapshot_store import (
    build_weekly_snapshot,
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)

BUCKETS = ("all", "only_normal", "mother_normal", "only_sample")


def test_payload_has_the_documented_shape():
    payload = build_weekly_snapshot()
    assert set(payload) == {"date", "generated_at", "summaries"}
    assert set(payload["summaries"]) == set(BUCKETS)
    assert payload["generated_at"].endswith("+09:00")


def test_payload_carries_summaries_but_not_recipe_info():
    # Snapshots are summary-only by design: device x bucket x recipe would be
    # GB-scale weekly, and no screen reads it (docs/datatables/
    # device_statistics_weekly_trend.txt).
    payload = build_weekly_snapshot()
    assert payload["summaries"]["all"], "expected at least one summary row"
    assert "all_rcp_info" not in payload["summaries"]


def test_default_date_is_a_monday():
    from datetime import date

    payload = build_weekly_snapshot()
    assert date.fromisoformat(payload["date"]).weekday() == 0


def test_default_date_matches_a_week_the_trend_returns():
    # The mock anchors weeks on BASE_TIME, not today. A snapshot named for a
    # week the trend never returns would be unreadable by construction.
    payload = build_weekly_snapshot()
    assert payload["date"] in get_weekly_trend_data(points=8)


def test_write_then_read_back_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    path = write_weekly_snapshot("2026-06-01")
    written = json.loads((tmp_path / "2026-06-01.json").read_text(encoding="utf-8"))
    assert written["date"] == "2026-06-01"
    assert set(written["summaries"]) == set(BUCKETS)
    assert path.endswith("2026-06-01.json")


def test_rewriting_the_same_week_overwrites(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    write_weekly_snapshot("2026-06-01")
    write_weekly_snapshot("2026-06-01")
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_sweep_keeps_the_newest_and_deletes_by_key_date(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    for week in ("2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25"):
        write_weekly_snapshot(week)

    assert sweep_weekly_snapshots(keep_weeks=2) == 2
    remaining = sorted(p.stem for p in tmp_path.glob("*.json"))
    assert remaining == ["2026-05-18", "2026-05-25"]


def test_sweep_ignores_files_that_are_not_dated_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    write_weekly_snapshot("2026-05-04")
    (tmp_path / "notes.json").write_text("{}", encoding="utf-8")

    sweep_weekly_snapshots(keep_weeks=0)
    assert (tmp_path / "notes.json").exists()


def test_sweep_on_a_missing_directory_is_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path / "nope"))
    assert sweep_weekly_snapshots(keep_weeks=12) == 0


def test_trend_still_returns_every_week_with_no_snapshots(tmp_path, monkeypatch):
    # REGRESSION GUARD. The office adapter omits past weeks that have no
    # snapshot. If that rule ever leaks into the mock, a fresh checkout returns
    # 1 date instead of 8 and the trend chart goes blank until eight Mondays
    # have physically passed. The mock computes every week live, on purpose.
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    assert len(get_weekly_trend_data(points=8)) == 8
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/cdsem/device_statistics/tests/test_snapshot_store.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named '...providers.snapshot_store'`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/ebeam/cdsem/device_statistics/providers/snapshot_store.py`:

```python
"""주차 스냅샷의 집(home) 구현 — 디스크에 JSON 을 씁니다.

사무실은 같은 payload 를 MinIO 에 올립니다(``office_example.py`` 의
``write_weekly_snapshot``). ``msr_image`` 의 ``DiskImageCache`` /
``MinioImageCache`` 분기와 같은 형태입니다.

**읽기 경로는 의도적으로 갈라집니다 — 이 모듈이 쓴 파일을 화면이 읽지
않습니다.** 사무실 어댑터는 과거 주차를 스냅샷에서 읽고 스냅샷이 없는 주차는
응답에서 빼지만(datatable 문서 읽기 규칙 3), mock 의
``get_weekly_trend_data`` 는 지금처럼 **모든 주차를 라이브로 계산**합니다.
새 체크아웃에는 스냅샷이 하나도 없으므로 그 규칙을 집에 옮기면 트렌드가 8개
대신 1개 날짜만 돌려주고, 월요일이 여덟 번 지날 때까지 차트가 비어 있게
됩니다. 결정론적 seed 덕분에 라이브 계산은 같은 날짜에 늘 같은 값을 줍니다.

따라서 집에서 이 모듈이 검증하는 것은 **payload 를 만들어 남기는 데까지**이며,
그것이 사무실에서 MinIO 에 올라갈 바로 그 payload 입니다.
"""

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from back_dev_home.ebeam.cdsem.device_statistics.providers.statistics import (
    RCP_BUCKETS,
    _trend_dates,
    get_weekly_trend_data,
)

logger = logging.getLogger("skewnono.scheduler")

KST = timezone(timedelta(hours=9))

# YYYY-MM-DD.json 인 파일만 스냅샷으로 취급합니다. sweep 이 같은 폴더의 다른
# 파일을 지우지 않도록 하는 유일한 방어선입니다.
_SNAPSHOT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def snapshot_dir() -> Path:
    """``SKEWNONO_WEEKLY_TREND_DIR`` 또는 기본 ``var/weekly_trend``.

    환경변수를 매번 읽습니다 — 모듈 로드 시점에 고정하면 테스트가
    monkeypatch 로 경로를 바꿀 수 없습니다.
    """
    raw = os.environ.get("SKEWNONO_WEEKLY_TREND_DIR", "").strip()
    return Path(raw) if raw else Path("var/weekly_trend")


def _current_week() -> str:
    """mock 이 '이번 주차'로 부르는 날짜.

    ``_trend_dates`` 와 같은 앵커(BASE_TIME)를 씁니다. 오늘 날짜로 계산하면
    트렌드가 절대 돌려주지 않는 주차 이름으로 파일이 생깁니다.
    """
    return _trend_dates(points=1, interval_days=7)[-1]


def build_weekly_snapshot(date_key: str | None = None) -> dict[str, Any]:
    """한 주차 payload — **모든 device 의 summary 만**.

    ``*_rcp_info`` 는 일부러 담지 않습니다. recipe 단위 상세는 device 4000개 ×
    버킷 4개 × recipe 100~200개가 되어 매주 GB 급이 되는데, 그것을 읽는 화면이
    없습니다(docs/datatables/device_statistics_weekly_trend.txt).
    """
    anchor = date_key or _current_week()
    trend = get_weekly_trend_data(None, points=8, interval_days=7, include_recipes=False)
    bucket = trend.get(anchor)
    if bucket is None:
        # 요청된 주차가 mock 의 창 밖입니다. 가장 최근 주차로 payload 를 만들되
        # 이름은 요청된 주차로 둡니다 — 재적재(backfill)를 흉내 내는 경로입니다.
        bucket = trend[next(reversed(trend))]
    return {
        "date": anchor,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "summaries": {name: list(bucket[f"{name}_summary"]) for name in RCP_BUCKETS},
    }


def write_weekly_snapshot(date_key: str | None = None) -> str:
    """payload 를 파일로 남기고 그 경로를 돌려줍니다. 같은 주차를 다시 불러도
    덮어쓰므로 재실행에 안전합니다."""
    payload = build_weekly_snapshot(date_key)
    directory = snapshot_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{payload['date']}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "device_statistics: wrote weekly snapshot %s (%d lots)",
        path, len(payload["summaries"].get("all", [])),
    )
    return str(path)


def _snapshot_dates(directory: Path) -> list[str]:
    return sorted(
        p.stem for p in directory.glob("*.json") if _SNAPSHOT_NAME.match(p.stem)
    )


def sweep_weekly_snapshots(keep_weeks: int = 12) -> int:
    """가장 최근 ``keep_weeks`` 주차만 남기고 지웁니다. 지운 개수를 돌려줍니다.

    **key 의 날짜로 판단하며 파일의 mtime 으로 하지 않습니다.** 놓친 주를 메우려
    ``write_weekly_snapshot("2026-06-01")`` 을 다시 부르면 그 파일의 mtime 은
    오늘이 됩니다. mtime 기준이면 그 오래된 백필을 남기고 정상적인 최근 것을
    지웁니다.
    """
    directory = snapshot_dir()
    if not directory.is_dir():
        return 0
    dates = _snapshot_dates(directory)
    doomed = dates[:-keep_weeks] if keep_weeks > 0 else dates
    removed = 0
    for stem in doomed:
        try:
            (directory / f"{stem}.json").unlink()
            removed += 1
        except OSError:
            logger.exception("failed to delete weekly snapshot %s", stem)
    logger.info("device_statistics: swept %d weekly snapshots", removed)
    return removed


__all__ = [
    "build_weekly_snapshot",
    "snapshot_dir",
    "sweep_weekly_snapshots",
    "write_weekly_snapshot",
]
```

- [ ] **Step 4: Re-export from mock.py**

In `back_dev_home/ebeam/cdsem/device_statistics/providers/mock.py`, next to the existing trailing imports (`from .recipe_params import ...`, `from .rules import ...` around line 210), add:

```python
from .snapshot_store import (  # noqa: E402  (의도된 후위 import)
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)
```

And add both names to `mock.py`'s `__all__`:

```python
    "write_weekly_snapshot",
    "sweep_weekly_snapshots",
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/cdsem/device_statistics -q`

Expected: PASS — the new file's 10 tests plus the existing device_statistics suite.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/ebeam/cdsem/device_statistics/providers/snapshot_store.py \
        back_dev_home/ebeam/cdsem/device_statistics/providers/mock.py \
        back_dev_home/ebeam/cdsem/device_statistics/tests/test_snapshot_store.py
git commit -m "feat(device-statistics): write weekly snapshots to disk at home

Mirrors the office adapter's payload so home exercises the shape before the
office trip. The mock's read path deliberately stays live for every week:
applying the office's omit-missing-weeks rule at home would return 1 date
instead of 8 and blank the trend chart. Pinned by a regression test."
```

---

### Task 7: Dispatch the snapshot functions

**Files:**
- Modify: `back_dev_home/ebeam/cdsem/device_statistics/data.py`
- Modify: `back_dev_home/ebeam/cdsem/device_statistics/providers/office_example.py`
- Modify: `back_dev_home/ebeam/cdsem/device_statistics/MIGRATION.md`
- Test: `back_dev_home/ebeam/cdsem/device_statistics/tests/test_snapshot_dispatch.py`

**Interfaces:**
- Consumes: Task 6's mock functions.
- Produces: `data.write_weekly_snapshot(date_key=None) -> str`, `data.sweep_weekly_snapshots(keep_weeks=12) -> int`.

The office adapter already has `write_weekly_snapshot` (`office_example.py:966`). It needs `sweep_weekly_snapshots` added, and the existing office-template contract test must be checked for a signature-parity assertion.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/ebeam/cdsem/device_statistics/tests/test_snapshot_dispatch.py`:

```python
import inspect

from back_dev_home.ebeam.cdsem.device_statistics import data
from back_dev_home.ebeam.cdsem.device_statistics.providers import (
    mock,
    office_example,
)


def test_dispatcher_exports_both_snapshot_functions():
    assert "write_weekly_snapshot" in data.__all__
    assert "sweep_weekly_snapshots" in data.__all__


def test_dispatcher_reaches_the_mock_at_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    path = data.write_weekly_snapshot("2026-06-08")
    assert path.endswith("2026-06-08.json")
    assert data.sweep_weekly_snapshots(keep_weeks=0) == 1


def test_office_template_offers_the_same_two_functions():
    # The adapter is swapped in by copying office_example.py to office.py, so a
    # signature that drifts from the mock breaks only at the office.
    for name in ("write_weekly_snapshot", "sweep_weekly_snapshots"):
        assert hasattr(office_example, name), f"office_example is missing {name}"
        assert list(inspect.signature(getattr(mock, name)).parameters) == list(
            inspect.signature(getattr(office_example, name)).parameters
        ), f"{name} signature differs between mock and office"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/cdsem/device_statistics/tests/test_snapshot_dispatch.py -q`

Expected: FAIL — `AssertionError` on `data.__all__`

- [ ] **Step 3: Extend the dispatcher**

In `back_dev_home/ebeam/cdsem/device_statistics/data.py`, add both names to `__all__`:

```python
__all__ = [
    "get_r3_device_grp",
    "get_device_desc",
    "get_recipe_params",
    "get_weekly_trend_data",
    "get_rules",
    "write_weekly_snapshot",
    "sweep_weekly_snapshots",
]
```

And append at the end of the file:

```python
# ── 스케줄러 진입점 ──────────────────────────────────────────────
# 읽기가 아니라 쓰기입니다. 스케줄러가 provider 를 직접 import 하지 않도록
# 여기를 통과시킵니다 — 직접 import 하면 이 dispatcher 가 존재하는 이유인
# home/office swap 을 하드코딩하게 됩니다.


def write_weekly_snapshot(date_key: str | None = None) -> str:
    """이번(또는 지정된) 주차 스냅샷을 적재하고 그 위치를 돌려줍니다."""
    return _provider().write_weekly_snapshot(date_key)


def sweep_weekly_snapshots(keep_weeks: int = 12) -> int:
    """가장 최근 ``keep_weeks`` 주차만 남기고 지웁니다. 지운 개수를 돌려줍니다."""
    return _provider().sweep_weekly_snapshots(keep_weeks)
```

- [ ] **Step 4: Add the office sweep**

In `back_dev_home/ebeam/cdsem/device_statistics/providers/office_example.py`, add `"sweep_weekly_snapshots"` to `__all__` (near the existing `"write_weekly_snapshot"` at line 151), and append after `write_weekly_snapshot`:

```python
def sweep_weekly_snapshots(keep_weeks: int = 12) -> int:
    """가장 최근 ``keep_weeks`` 주차만 남기고 MinIO 객체를 지웁니다.

    **key 의 날짜로 판단하며 ``last_modified`` 로 하지 않습니다.** 이미지 캐시는
    객체가 연속적으로 도착하므로 쓰기 시각이 곧 나이지만, 스냅샷은 key 가 곧
    주차입니다. 놓친 주를 메우려 재적재하면 그 객체의 ``last_modified`` 는
    오늘이 되므로, ``last_modified`` 기준 sweep 은 그 오래된 백필을 남기고
    정상적인 최근 것을 지웁니다.

    MinIO 자격증명이 prefix 로 제한되어 native lifecycle 을 걸 수 없기 때문에
    애플리케이션 쪽에서 지웁니다(docs/datatables/device_statistics_weekly_trend.txt
    의 OFFICE-VERIFY 항목).

    **``AccessDenied`` 를 "지울 것 없음"으로 삼키지 않습니다.** 사무실 자격증명은
    허용된 prefix 밖에서 NotFound 가 아니라 AccessDenied 를 돌려주므로, 삼키면
    경로 오타가 "성공"을 보고하면서 영원히 아무것도 하지 않습니다.

    OFFICE-VERIFY: 첫 실행에서 실제로 지워지는 개수와 남는 개수.
    """
    from minio_handler import MinioObject  # office 전용 의존성 — 지연 import

    store = MinioObject()
    prefix = f"{MINIO_BASE}/"
    dated: list[str] = []
    for obj in store.list(prefix=prefix, recursive=True):
        stem = str(obj.object_name).rsplit("/", 1)[-1].removesuffix(".json")
        if _SNAPSHOT_NAME.match(stem):
            dated.append(str(obj.object_name))
    if not dated:
        return 0
    dated.sort()
    doomed = dated[:-keep_weeks] if keep_weeks > 0 else dated
    if not doomed:
        return 0
    errors = store.delete_many(doomed) or []
    removed = len(doomed) - len(errors)
    _LOG.info("device_statistics: swept %d weekly snapshots", removed)
    return removed
```

Add the shared name pattern near `MINIO_BASE` (line 170):

```python
# YYYY-MM-DD.json 인 객체만 스냅샷으로 취급합니다 — sweep 이 같은 prefix 의 다른
# 객체를 지우지 않도록 하는 방어선입니다.
_SNAPSHOT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}$")
```

Add `import re` to the module's imports if it is not already there.

- [ ] **Step 5: Update MIGRATION.md**

In `back_dev_home/ebeam/cdsem/device_statistics/MIGRATION.md`:

Replace the "weekly-snapshot scheduler does not exist yet" paragraph in `## Status` with:

```markdown
주차 스냅샷 스케줄러는 이제 존재합니다(`back_dev_home/_scheduler/`). 월요일
01:00 에 `write_weekly_snapshot()`, 02:30 에 `sweep_weekly_snapshots()` 가
돕니다. 사무실에서는 `cp office_example.py office.py` 만 하면 켜집니다.
```

In the `## Rules` section, replace `Never touch ... data.py ...` with:

```markdown
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `providers/snapshot_store.py`, `providers/statistics.py`,
  `providers/recipe_params.py`, `providers/rules.py`, `contracts.py`, or
  `tests/`. (`data.py` 는 2026-08-01 에 스케줄러 진입점 두 개가 추가되면서 한 번
  바뀌었습니다 — dispatcher 에 함수를 더한 것이며 `_provider()` 선택 로직은
  그대로입니다. 사무실 방문에서는 여전히 건드리지 않습니다.)
```

And add to the list of functions to implement:

```markdown
- **일곱 개**를 구현합니다: 기존 다섯 개에 더해 `write_weekly_snapshot`,
  `sweep_weekly_snapshots`. 뒤의 두 개는 스케줄러가 부르며 화면이 부르지
  않습니다.
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/cdsem/device_statistics -q`

Expected: PASS. If `tests/test_office_template.py` fails on a function-set assertion, extend its expected set with the two new names — that test exists to catch exactly this drift.

- [ ] **Step 7: Lint the Markdown**

Run: `npm run lint:md`

Expected: `Summary: 0 error(s)`

- [ ] **Step 8: Commit**

```bash
git add back_dev_home/ebeam/cdsem/device_statistics/data.py \
        back_dev_home/ebeam/cdsem/device_statistics/providers/office_example.py \
        back_dev_home/ebeam/cdsem/device_statistics/MIGRATION.md \
        back_dev_home/ebeam/cdsem/device_statistics/tests/test_snapshot_dispatch.py
git commit -m "feat(device-statistics): dispatch snapshot write and sweep

Adds both scheduler entry points to the dispatcher so the scheduler never
imports providers.office directly, and gives the office template the sweep
it was missing. The sweep deletes by the ISO date in the key, not by
last_modified, so a backfilled old week is still collected."
```

---

### Task 8: Snapshot task module

**Files:**
- Create: `back_dev_home/_scheduler/tasks/device_statistics.py`
- Test: `back_dev_home/_scheduler/tests/test_tasks_device_statistics.py`

**Interfaces:**
- Consumes: `device_statistics.data` (Task 7).
- Produces: `write_weekly_snapshot() -> str`, `sweep_weekly_snapshots() -> int` — zero-argument, because the registry calls them with none. Retention is read from the environment here, not passed in.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_scheduler/tests/test_tasks_device_statistics.py`:

```python
from back_dev_home._scheduler.tasks.device_statistics import (
    keep_weeks,
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)


def test_both_tasks_take_no_arguments():
    import inspect

    assert list(inspect.signature(write_weekly_snapshot).parameters) == []
    assert list(inspect.signature(sweep_weekly_snapshots).parameters) == []


def test_keep_weeks_defaults_to_twelve(monkeypatch):
    monkeypatch.delenv("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", raising=False)
    assert keep_weeks() == 12


def test_keep_weeks_reads_the_env(monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "4")
    assert keep_weeks() == 4


def test_keep_weeks_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "soon")
    assert keep_weeks() == 12


def test_write_then_sweep_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_DIR", str(tmp_path))
    monkeypatch.setenv("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "1")

    write_weekly_snapshot()
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert sweep_weekly_snapshots() == 0  # only one, and we keep one
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_tasks_device_statistics.py -q`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/_scheduler/tasks/device_statistics.py`:

```python
"""Weekly device-statistics snapshot: write, then sweep.

Thin call-throughs into ``device_statistics.data``, which dispatches to the
mock (disk) or office (MinIO) adapter. Both take no arguments because the
registry calls them with none -- retention is read from the environment here so
tuning it never requires a deploy.

Why the snapshot exists at all: the process-step source is a CURRENT-STATE
index, so "how many steps did this device have three weeks ago" cannot be
recovered by query. Filtering on chg_tm is not equivalent either -- any step
changed since the cutoff drops out entirely, so the further back you go the
more it under-counts. See docs/datatables/device_statistics_weekly_trend.txt.
"""

import logging
import os

from back_dev_home.ebeam.cdsem.device_statistics import data

logger = logging.getLogger("skewnono.scheduler")


def keep_weeks() -> int:
    """Retention, in weeks. The screen shows 8 (default ``points``); 12 leaves
    headroom if that is raised. Expected to change once the first snapshot's
    real size is known, so it is an env var rather than a constant."""
    try:
        return int(os.environ.get("SKEWNONO_WEEKLY_TREND_KEEP_WEEKS", "").strip())
    except ValueError:
        return 12


def write_weekly_snapshot() -> str:
    location = data.write_weekly_snapshot()
    logger.info("weekly snapshot written to %s", location)
    return location


def sweep_weekly_snapshots() -> int:
    removed = data.sweep_weekly_snapshots(keep_weeks())
    logger.info("weekly snapshot sweep removed %d objects", removed)
    return removed
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_tasks_device_statistics.py -q`

Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_scheduler/tasks/device_statistics.py \
        back_dev_home/_scheduler/tests/test_tasks_device_statistics.py
git commit -m "feat(scheduler): add the weekly snapshot write and sweep tasks"
```

---

### Task 9: Registry and startup

**Files:**
- Create: `back_dev_home/_scheduler/registry.py`
- Modify: `back_dev_home/_scheduler/__init__.py`
- Modify: `back_dev_home/__init__.py` (start the scheduler where the old call was)
- Test: `back_dev_home/_scheduler/tests/test_registry.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4, 5, 8.
- Produces: `JOB_REGISTRY: dict[str, dict]`, `build_jobs(cfg, run_log) -> dict[str, Callable]`, and `start_scheduler(app) -> BackgroundScheduler | None` exported from `_scheduler/__init__.py`.
- Produces: `app.extensions["scheduler_run_log"]` — the `RunLog`, read by Task 10's endpoint.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/_scheduler/tests/test_registry.py`:

```python
import pytest
from flask import Flask

from back_dev_home._scheduler import start_scheduler
from back_dev_home._scheduler.config import load_scheduler_config
from back_dev_home._scheduler.registry import JOB_REGISTRY, build_jobs
from back_dev_home._scheduler.runlog import MemoryRunLog


def test_every_entry_has_a_function_and_a_trigger():
    for name, spec in JOB_REGISTRY.items():
        assert callable(spec["fn"]), f"{name} has no callable fn"
        assert "trigger" in spec, f"{name} has no trigger"
        assert isinstance(spec.get("lock_ttl"), int), f"{name} has no lock_ttl"


def test_all_three_jobs_are_registered():
    assert set(JOB_REGISTRY) == {
        "image_cache_purge",
        "weekly_snapshot_write",
        "weekly_snapshot_sweep",
    }


def test_no_two_jobs_share_a_fire_instant():
    # Cron fires at an exact instant, so two jobs written minute=0 start
    # TOGETHER, not "around" the hour.
    slots = []
    for name, spec in JOB_REGISTRY.items():
        fields = {f.name: str(f) for f in spec["trigger"].fields}
        slots.append(
            (fields.get("day_of_week"), fields.get("hour"), fields.get("minute"))
        )
    assert len(set(slots)) == len(slots), f"two jobs share a fire instant: {slots}"


def test_every_job_fires_inside_the_quiet_window():
    # 01:00-08:00 is the confirmed quiet window (user-confirmed 2026-08-01).
    for name, spec in JOB_REGISTRY.items():
        hour = int(str(next(f for f in spec["trigger"].fields if f.name == "hour")))
        assert 1 <= hour < 8, f"{name} fires at {hour}, outside the quiet window"


def test_the_sweep_runs_after_the_write():
    # Sweeping first would race the write and could delete the oldest kept
    # snapshot in the same hour the newest arrives.
    def hour(name):
        spec = JOB_REGISTRY[name]
        return int(str(next(f for f in spec["trigger"].fields if f.name == "hour")))

    assert hour("weekly_snapshot_sweep") > hour("weekly_snapshot_write")


def test_build_jobs_returns_one_callable_per_entry(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    jobs = build_jobs(load_scheduler_config({}), MemoryRunLog(10))
    assert set(jobs) == set(JOB_REGISTRY)
    assert all(callable(fn) for fn in jobs.values())


def test_wrapped_job_records_start_and_end(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    run_log = MemoryRunLog(10)
    cfg = load_scheduler_config({})
    registry = {"noop": {"fn": lambda: 1, "trigger": None, "lock_ttl": 60}}
    jobs = build_jobs(cfg, run_log, registry=registry)
    jobs["noop"]()
    assert [r["event"] for r in run_log.read(10)] == ["end", "start"]


def test_testing_app_starts_no_scheduler():
    app = Flask(__name__)
    app.testing = True
    assert start_scheduler(app) is None


def test_starting_twice_returns_the_same_scheduler(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    app = Flask(__name__)
    app.debug = False
    first = start_scheduler(app)
    try:
        assert first is not None
        assert start_scheduler(app) is first
        assert len(first.get_jobs()) == len(JOB_REGISTRY)
    finally:
        if first is not None:
            first.shutdown(wait=False)


def test_start_exposes_the_run_log_on_the_app(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    app = Flask(__name__)
    app.debug = False
    scheduler = start_scheduler(app)
    try:
        assert app.extensions["scheduler_run_log"] is not None
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler/tests/test_registry.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._scheduler.registry'`

- [ ] **Step 3: Write the registry**

Create `back_dev_home/_scheduler/registry.py`:

```python
"""What runs, when, and with which knobs.

Four knobs matter, and for jobs measured in minutes the last two matter most.

``minute=``  Cron fires at an exact instant, so two jobs written ``minute=0``
             start TOGETHER, not "around" the hour. Every job gets its own
             slot; a test asserts no two share one.

``lock_ttl`` Orphan-clear window only -- a live run re-arms its own TTL, so it
             may overrun this freely. Smaller is better: it bounds how long a
             lock left by a killed process blocks the job. All three jobs are
             daily or weekly, so any value under a day skips zero runs. Do NOT
             reason "weekly job, weekly TTL" -- that is this knob's most common
             mistake.

``misfire_grace_time``  How late a start may be and still happen. Checked when
             the job reaches a worker thread, so it covers queue wait. The 60s
             APScheduler default is far too tight for a WEEKLY job: a missed
             snapshot write does not retry until next Monday, so six hours of
             grace costs nothing and saves a week.

Hours all sit inside 01:00-08:00, the confirmed quiet window (user-confirmed
2026-08-01), and the sweep deliberately follows the write.
"""

from collections.abc import Callable

from apscheduler.triggers.cron import CronTrigger

from back_dev_home._scheduler.locks import make_job_lock
from back_dev_home._scheduler.tasks.device_statistics import (
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)
from back_dev_home._scheduler.tasks.image_cache import purge_image_cache

JOB_REGISTRY: dict[str, dict] = {
    "image_cache_purge": {
        "fn": purge_image_cache,
        # Nightly. :10 keeps it clear of the two weekly slots below.
        "trigger": CronTrigger(hour=3, minute=10),
        "lock_ttl": 600,
        "misfire_grace_time": 3600,
    },
    "weekly_snapshot_write": {
        "fn": write_weekly_snapshot,
        # Monday, because the snapshot key IS that week's Monday.
        "trigger": CronTrigger(day_of_week="mon", hour=1, minute=0),
        "lock_ttl": 600,
        # Six hours: the next retry would otherwise be next Monday.
        "misfire_grace_time": 21600,
    },
    "weekly_snapshot_sweep": {
        "fn": sweep_weekly_snapshots,
        # 90 minutes after the write, never before: sweeping first could delete
        # the oldest kept snapshot in the same hour the newest arrives, and a
        # failed write would still trigger deletions.
        "trigger": CronTrigger(day_of_week="mon", hour=2, minute=30),
        "lock_ttl": 600,
        "misfire_grace_time": 3600,
    },
}


def _skip_recorder(run_log, job: str) -> Callable[[dict], None]:
    """Build the on_skip callback for ``job``.

    A factory, not a closure written inline in the loop below: an inline
    closure captures the loop VARIABLE, so by the time any job ran, every
    callback would report the last-registered name.
    """

    def record_skip(info: dict) -> None:
        run_log.record(job, "skip", **info)

    return record_skip


def build_jobs(cfg, run_log, registry: dict[str, dict] | None = None) -> dict[str, Callable]:
    """Wrap every entry as ``job_lock(run_log.wrap(fn))``.

    That order matters: reversed, a run blocked by a peer would emit
    start/skip/end instead of a single skip.
    """
    registry = JOB_REGISTRY if registry is None else registry
    jobs: dict[str, Callable] = {}
    for name, spec in registry.items():
        # The registry key is the job's identity everywhere -- lock key,
        # scheduler job id and log records. Deriving any of them from
        # fn.__name__ splits that identity, and two entries sharing one
        # function would silently share one lock.
        lock = make_job_lock(cfg, name, on_skip=_skip_recorder(run_log, name))
        jobs[name] = lock(run_log.wrap(spec["fn"], name))
    return jobs
```

- [ ] **Step 4: Write the package entry point**

Replace `back_dev_home/_scheduler/__init__.py`:

```python
"""One scheduler for the whole backend.

``start_scheduler(app)`` is the only thing the app factory calls. It is
idempotent and safe to call from every worker: workers that lose the election
return None without creating a thread.

APScheduler's DEFAULT memory jobstore is used on purpose, in both phases. Jobs
here are declared in code and rebuilt every boot, and all three triggers are
cron -- absolute wall-clock -- so a fresh scheduler after a restart computes
exactly the right next fire. A RedisJobStore would pickle each job, and
pickling a functools.wraps-decorated closure follows __qualname__ back to the
BARE task, so a restored job would bypass the lock and the run log entirely.
The accepted loss: a run missed while the process is down is skipped rather
than detected as missed.
"""

import atexit
import logging

from back_dev_home._scheduler.config import load_scheduler_config
from back_dev_home._scheduler.election import is_scheduler_worker
from back_dev_home._scheduler.registry import JOB_REGISTRY, build_jobs
from back_dev_home._scheduler.runlog import make_run_log

logger = logging.getLogger("skewnono.scheduler")

__all__ = ["start_scheduler"]

_EXTENSION_KEY = "scheduler"


def start_scheduler(app):
    """Start the scheduler if this process owns it. Returns it, or None."""
    if app.testing:
        # A test suite creates many apps; each would otherwise leave a live
        # thread firing real jobs.
        return None
    if _EXTENSION_KEY in app.extensions:
        return app.extensions[_EXTENSION_KEY]

    cfg = load_scheduler_config()
    run_log = make_run_log(cfg)
    # Set even on workers that lose the election: any worker may serve
    # /api/health/jobs, and at the office they all read the same Redis list.
    app.extensions["scheduler_run_log"] = run_log

    if not is_scheduler_worker(app):
        logger.info("not the scheduler process; serving requests only")
        return None

    from apscheduler.schedulers.background import BackgroundScheduler

    jobs = build_jobs(cfg, run_log)
    scheduler = BackgroundScheduler(daemon=True, timezone=cfg.timezone)
    for name, spec in JOB_REGISTRY.items():
        scheduler.add_job(
            jobs[name],
            trigger=spec["trigger"],
            id=name,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=spec.get("misfire_grace_time"),
        )
    _install_missed_listener(scheduler, run_log)
    scheduler.start()
    app.extensions[_EXTENSION_KEY] = scheduler
    atexit.register(_shutdown, scheduler)
    logger.info("scheduler started with %d jobs", len(JOB_REGISTRY))
    return scheduler


def _install_missed_listener(scheduler, run_log) -> None:
    """Record dropped and refused fires.

    Without this they leave NO record at all -- their only trace is a line in
    the uWSGI log, which at the office nobody may be reading.
    """
    from apscheduler.events import EVENT_JOB_MAX_INSTANCES, EVENT_JOB_MISSED

    def record(event) -> None:
        if event.code == EVENT_JOB_MISSED:
            reason = "start missed by more than misfire_grace_time"
            scheduled = getattr(event, "scheduled_run_time", None)
        else:
            reason = "previous run still executing (max_instances)"
            times = getattr(event, "scheduled_run_times", None) or []
            scheduled = times[0] if times else None
        run_log.record(
            event.job_id,
            "missed",
            reason=reason,
            scheduled=scheduled.isoformat() if scheduled else None,
        )

    scheduler.add_listener(record, EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES)


def _shutdown(scheduler) -> None:
    """Pause BEFORE shutdown.

    Without the pause, a trigger tick mid-flight can call submit_job() after
    the ThreadPoolExecutor has been torn down, producing sporadic "cannot
    schedule new futures after shutdown" errors. With max-requests = 1000 in
    wsgi.ini, worker recycles are routine here, not rare.
    """
    try:
        if scheduler.running:
            scheduler.pause()
            scheduler.shutdown(wait=False)
    except Exception:
        pass
```

- [ ] **Step 5: Wire the app factory**

In `back_dev_home/__init__.py`, where the old `start_purge_scheduler` call was (just before `return app`), add:

```python
    from back_dev_home._scheduler import start_scheduler
    start_scheduler(app)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/_scheduler -q`

Expected: PASS — 10 passed in test_registry.py plus the earlier modules.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS. Compare `passed + skipped` against the pre-change total, not `passed` alone — a worktree without gitignored `office.py` files legitimately skips a different number.

- [ ] **Step 8: Commit**

```bash
git add back_dev_home/_scheduler/registry.py back_dev_home/_scheduler/__init__.py \
        back_dev_home/_scheduler/tests/test_registry.py back_dev_home/__init__.py
git commit -m "feat(scheduler): add the job registry and start the scheduler

Replaces msr_image's per-feature BackgroundScheduler with one elected
scheduler carrying all three jobs. Memory jobstore on purpose -- see the
package docstring. Shutdown pauses before shutting down, which matters
because max-requests=1000 makes worker recycles routine."
```

---

### Task 10: The run-log endpoint

**Files:**
- Modify: `back_dev_home/health/routes.py`
- Modify: `back_dev_home/health/contracts.py`
- Test: `back_dev_home/health/tests/test_jobs_endpoint.py`

**Interfaces:**
- Consumes: `app.extensions["scheduler_run_log"]` (Task 9).
- Produces: `GET /api/health/jobs`.

Admin-gated, like `/health/providers` and `/health/logging`: it names internal job ids and deployment shape, which is an operator's signal rather than a user's.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/health/tests/test_jobs_endpoint.py`:

```python
import pytest

from back_dev_home import create_app
from back_dev_home._scheduler.runlog import MemoryRunLog


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    app = create_app()
    app.testing = True
    run_log = MemoryRunLog(max_records=10)
    run_log.record("image_cache_purge", "start")
    run_log.record("image_cache_purge", "end", duration_ms=12)
    app.extensions["scheduler_run_log"] = run_log
    return app.test_client()


def _admin(client, path):
    # local-dev is the admin identity at home; digits are a normal user.
    return client.get(path, headers={"Cookie": "LASTUSER=local-dev"})


def test_returns_records_newest_first(client):
    response = _admin(client, "/api/health/jobs")
    assert response.status_code == 200
    records = response.get_json()["records"]
    assert [r["event"] for r in records] == ["end", "start"]
    assert records[0]["job"] == "image_cache_purge"


def test_limit_is_honoured(client):
    records = _admin(client, "/api/health/jobs?limit=1").get_json()["records"]
    assert len(records) == 1


def test_limit_is_capped_at_the_retention_maximum(client):
    # The cap is defined by the storage layer, not mirrored in the query.
    body = _admin(client, "/api/health/jobs?limit=99999").get_json()
    assert body["limit"] <= 500


def test_garbage_limit_falls_back_to_the_default(client):
    body = _admin(client, "/api/health/jobs?limit=soon").get_json()
    assert body["limit"] == 200


def test_missing_run_log_answers_an_empty_list(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    app = create_app()
    app.testing = True
    app.extensions.pop("scheduler_run_log", None)
    response = app.test_client().get(
        "/api/health/jobs", headers={"Cookie": "LASTUSER=local-dev"}
    )
    assert response.status_code == 200
    assert response.get_json()["records"] == []


def test_normal_user_is_refused(client):
    response = client.get("/api/health/jobs", headers={"Cookie": "LASTUSER=1234567"})
    assert response.status_code in (401, 403)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/health/tests/test_jobs_endpoint.py -q`

Expected: FAIL — 404 on `/api/health/jobs`

- [ ] **Step 3: Add the contract**

In `back_dev_home/health/contracts.py`, extend `__all__` and append:

```python
__all__ = [
    "ServiceHealth",
    "ServicesHealthResponse",
    "JobRunRecord",
    "JobsHealthResponse",
]


class JobRunRecord(TypedDict, total=False):
    ts: str
    job: str
    event: Literal["start", "end", "error", "skip", "missed"]
    duration_ms: int
    error: str


class JobsHealthResponse(TypedDict):
    limit: int
    records: list[JobRunRecord]
```

- [ ] **Step 4: Add the route**

In `back_dev_home/health/routes.py`, add `current_app` and `request` to the Flask import, then append:

```python
_DEFAULT_JOB_LIMIT = 200


@bp.get("/health/jobs")
@require_admin
def jobs_health():
    """Recent scheduler run records — start, end, error, skip, missed.

    Same introspection carve-out as /health/providers: reads the run log off
    the app rather than going through a provider. Admin-only because it names
    internal job ids and their timings.

    The retention cap lives in the storage layer (memory ring buffer at home, a
    Redis LTRIM at the office), so the ceiling below is read from the config
    rather than duplicated here. A worker that never elected still answers:
    at the office every worker reads the same Redis list.
    """
    from back_dev_home._scheduler.config import load_scheduler_config

    ceiling = load_scheduler_config().log_list_max
    raw_limit = request.args.get("limit", "")
    try:
        limit = int(raw_limit) if raw_limit else _DEFAULT_JOB_LIMIT
    except ValueError:
        limit = _DEFAULT_JOB_LIMIT
    limit = max(1, min(limit, ceiling))

    run_log = current_app.extensions.get("scheduler_run_log")
    records = run_log.read(limit) if run_log is not None else []
    return jsonify({"limit": limit, "records": records})
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/health -q`

Expected: PASS — 6 new tests plus the existing health suite.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/health/routes.py back_dev_home/health/contracts.py \
        back_dev_home/health/tests/test_jobs_endpoint.py
git commit -m "feat(health): add GET /api/health/jobs for scheduler run records"
```

---

### Task 11: Documentation

**Files:**
- Modify: `docs/deployment.md`
- Modify: `docs/datatables/device_statistics_weekly_trend.txt`
- Modify: `back_dev_home/.env.example`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Record the load-bearing uWSGI settings**

A comment in the local `wsgi.ini` never reaches the cloud host's permanent copy, so this goes in `docs/deployment.md`. Add a subsection after the section that describes what the bundle contains:

```markdown
### `wsgi.ini` 의 두 설정은 스케줄러가 의존합니다

`wsgi.ini` 는 번들에 들어가지 않고 클라우드 호스트에 영구 보관되므로, 아래 두
줄은 **여기에만 기록됩니다.** 지우면 스케줄러가 조용히 멈춥니다.

| 설정 | 지웠을 때 |
| --- | --- |
| `enable-threads = true` | `BackgroundScheduler` 가 요청 스레드 밖에서 돌지 못해 tick 하지 않습니다. 오류는 나지 않고 작업만 영영 실행되지 않습니다. |
| `lazy-apps = true` | 앱이 마스터에서 한 번 만들어지는데 스레드는 `fork()` 를 넘어가지 못하므로, 스케줄러가 **어느 워커에도 존재하지 않게** 됩니다. `uwsgi.worker_id()` 기반 선출도 무의미해집니다. |

`harakiri = 60` 은 스케줄러 작업을 죽이지 않습니다 — harakiri 타이머는 **요청**
단위로 걸립니다. `max-requests = 1000` 은 워커 1 을 주기적으로 재생성하며,
그때마다 스케줄러가 앱 부팅 시간만큼 끊겼다 복구됩니다.

돌고 있는지 확인하려면 `GET /api/health/jobs` (관리자)를 봅니다. 작업 하나가
하루에 여러 줄로 보이면 선출이 실패한 것입니다.
```

- [ ] **Step 2: Mark the retention item as implemented**

In `docs/datatables/device_statistics_weekly_trend.txt`, replace the "적재 (스케줄러)" section's closing line `스케줄러 자체는 아직 없습니다 — 사무실에서 붙일 작업입니다.` with:

```text
스케줄러는 2026-08-01 에 붙었습니다 — back_dev_home/_scheduler/ 의
weekly_snapshot_write 작업이 월요일 01:00 에 이 함수를 부릅니다.
사무실에서는 cp office_example.py office.py 만 하면 켜집니다.
```

And in the `OFFICE-VERIFY` section, replace the retention bullet with:

```text
- 보존 기간은 구현되었습니다. weekly_snapshot_sweep 이 월요일 02:30 에 돌며
  가장 최근 SKEWNONO_WEEKLY_TREND_KEEP_WEEKS(기본 12) 주차만 남깁니다.
  **key 의 날짜로 지우며 last_modified 로 하지 않습니다** — 재적재한 과거
  주차는 last_modified 가 오늘이므로, 그 기준이면 오래된 백필을 남기고
  정상적인 최근 것을 지웁니다.
  OFFICE-VERIFY: 첫 sweep 이 지운 개수와 남긴 개수, 그리고 잘못된 prefix 로
  실행했을 때 AccessDenied 가 삼켜지지 않고 예외로 올라오는지.
```

- [ ] **Step 3: Document the new environment variables**

In `back_dev_home/.env.example`, add:

```bash
# ── Scheduler ────────────────────────────────────────────────────
# Orphan-clear window for the job lock, in seconds. NOT a runtime budget --
# a live run re-arms its own TTL.
# SKEWNONO_SCHEDULER_LOCK_TTL=600
# How many job-run records to retain.
# SKEWNONO_SCHEDULER_LOG_MAX=500
# Weekly device-statistics snapshots: where home writes them, and how many
# weeks to keep. The screen shows 8; 12 leaves headroom.
# SKEWNONO_WEEKLY_TREND_DIR=var/weekly_trend
# SKEWNONO_WEEKLY_TREND_KEEP_WEEKS=12
```

- [ ] **Step 4: Note the scheduler in CLAUDE.md**

In the "Feature-sliced Backend Layout" section, the sentence listing underscore folders currently reads `Underscore-prefixed folders (_runtime/, _auth/, _core/, _logging/, _spa/)`. Add `_scheduler/`:

```markdown
- Underscore-prefixed folders (`_runtime/`, `_auth/`, `_core/`, `_logging/`,
  `_scheduler/`, `_spa/`) are shared plumbing, **not** features — the app
  factory skips them.
```

And add to "Runtime gotchas":

```markdown
- Periodic jobs live in `back_dev_home/_scheduler/`, not in feature folders.
  Exactly one process runs them (uWSGI worker 1; the Werkzeug reloader's app
  child at home). `wsgi.ini`'s `lazy-apps` and `enable-threads` are
  load-bearing for this — see `docs/deployment.md`. Check runs with
  `GET /api/health/jobs`.
```

- [ ] **Step 5: Lint the Markdown**

Run: `npm run lint:md`

Expected: `Summary: 0 error(s)`

- [ ] **Step 6: Run the full suite one more time**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add docs/deployment.md docs/datatables/device_statistics_weekly_trend.txt \
        back_dev_home/.env.example CLAUDE.md
git commit -m "docs(scheduler): record the load-bearing uWSGI flags and new env vars

wsgi.ini is excluded from the deploy bundle and lives permanently on the
cloud host, so a comment in the local copy never reaches it -- lazy-apps
and enable-threads are documented in deployment.md instead."
```

---

## Verification

After Task 11, confirm the scheduler is real rather than merely importable.

- [ ] **Start the backend and check the endpoint**

```bash
.venv/bin/python index.py     # Flask on :5050
```

In another shell:

```bash
curl -s -H 'Cookie: LASTUSER=local-dev' localhost:5050/api/health/jobs | head -20
```

Expected: `{"limit": 200, "records": []}` — empty because no job has fired yet.

- [ ] **Confirm exactly one scheduler process at home**

Check the startup log for `scheduler started with 3 jobs`. It must appear **once**, not twice. Twice means the reloader-parent case in `election.py` is not working, which is the bug this plan fixes.

- [ ] **Fire a job by hand and see it recorded**

```bash
.venv/bin/python -c "
from back_dev_home._scheduler.config import load_scheduler_config
from back_dev_home._scheduler.registry import build_jobs
from back_dev_home._scheduler.runlog import MemoryRunLog
log = MemoryRunLog(10)
build_jobs(load_scheduler_config(), log)['weekly_snapshot_write']()
for record in log.read(10): print(record)
"
```

Expected: an `end` record and a `start` record, and a new file under `var/weekly_trend/`.

- [ ] **Confirm the trend screen is unaffected**

```bash
curl -s 'localhost:5050/api/cdsem/device-statistics/recipe-trend?lot_cds=' \
  -H 'Cookie: LASTUSER=local-dev' | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
```

Expected: `8`. Anything less means the office read rule leaked into the mock and the trend chart is blank.

## Notes for the implementer

**Skip counts differ legitimately.** A worktree has no gitignored `office.py` files, so provider-contract tests skip differently than in the main checkout. Compare `passed + skipped`, not `passed`.

**`import uwsgi` needs nothing installed.** It is not a PyPI package and not
from `flask_modules` — the uWSGI server injects it into the interpreter it
embeds, so it exists purely by virtue of the process having been started by
`uwsgi --ini wsgi.ini`. No `pip install`, no server rebuild, no `systemctl`,
and nothing outside `wsgi.ini` to change. Outside uWSGI it raises
`ModuleNotFoundError` (verified at home 2026-08-01), which is exactly the
signal `election.py` uses to fall through to the reloader check. The same
`import uwsgi` / `worker_id()` pair is already running at the office in
`flask_modules/api/__init__.py:42` (user-confirmed 2026-08-01), so this is a
proven pattern in this environment rather than a new dependency on it.

**Do not add `flask_apscheduler`.** This plan uses plain `BackgroundScheduler`, already a dependency. `flask_modules` uses the Flask extension, but it needs the app-context plumbing that comes with it; here, the only job touching Flask state is none of them.

**`office.py` may exist on the machine you are working on.** It is gitignored and is a copy of `office_example.py`. If the app fails to boot with an import error from it, the copy is stale relative to the template — refresh with `python -m scripts.sync_office_adapters device_statistics`.
