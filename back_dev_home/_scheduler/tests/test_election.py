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
