import importlib.util
import sys
import types
from pathlib import Path

import pytest
from flask import Flask

from back_dev_home._scheduler.election import is_scheduler_worker

REPO_ROOT = Path(__file__).resolve().parents[3]


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


# ── the real entry point ────────────────────────────────────────────────────
# Every test above hands is_scheduler_worker an app it built itself with
# debug=True -- a state no production code path was actually producing. The
# guard was dead for months because `index.py` only passed debug to app.run(),
# long after create_app() had already elected. So these two exercise the real
# module: load index.py exactly as `python index.py` does and look at what it
# built.


def _load_index(name: str):
    """Execute the repo's real ``index.py`` under a throwaway module name."""
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def entry_point_env(monkeypatch):
    """Home-like env for loading index.py, with FLASK_DEBUG guaranteed unset.

    setenv-then-delenv rather than a bare delenv: index.py SETS FLASK_DEBUG, so
    monkeypatch has to have recorded an undo for it or the flag leaks into the
    rest of the session.
    """
    monkeypatch.setenv("FLASK_DEBUG", "1")
    monkeypatch.delenv("FLASK_DEBUG")
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    monkeypatch.delenv("SKEWNONO_SCHEDULER_ENABLED", raising=False)
    monkeypatch.delitem(sys.modules, "uwsgi", raising=False)
    return monkeypatch


def _shutdown(module) -> None:
    scheduler = module.app.extensions.get("scheduler")
    if scheduler is not None:
        scheduler.shutdown(wait=False)


def test_index_py_reloader_parent_starts_no_scheduler(entry_point_env):
    # The watcher parent: no WERKZEUG_RUN_MAIN. It must lose the election, or
    # `python index.py` runs two schedulers firing the same three jobs.
    entry_point_env.delenv("WERKZEUG_RUN_MAIN", raising=False)
    module = _load_index("index_reloader_parent")
    try:
        assert module.app.debug is True, (
            "index.py must make debug true BEFORE create_app(); "
            "app.run(debug=...) is too late for the scheduler election"
        )
        assert "scheduler" not in module.app.extensions
    finally:
        _shutdown(module)


def test_index_py_reloader_child_starts_the_scheduler(entry_point_env):
    entry_point_env.setenv("WERKZEUG_RUN_MAIN", "true")
    module = _load_index("index_reloader_child")
    try:
        assert "scheduler" in module.app.extensions
    finally:
        _shutdown(module)
