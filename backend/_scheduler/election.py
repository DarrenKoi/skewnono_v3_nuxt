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
   ``FLASK_DEBUG=1`` off-cloud). The reloader runs the module in TWO processes:
   a watcher parent and the app child. Both call ``create_app()`` and neither
   is uWSGI, so without this case a single dev machine gets two schedulers.
   Only the child carries ``WERKZEUG_RUN_MAIN``, so "debug and no
   WERKZEUG_RUN_MAIN" identifies the parent exactly. uWSGI and cloud never
   reach here -- debug is False there.

   ``index.py`` must set the debug flag through the ENVIRONMENT, before
   ``create_app()``: passing ``app.run(debug=...)`` sets it long after this
   election has already run, leaving ``app.debug`` False in both processes and
   this guard permanently dead.

3. **Anything else** -- a single-process run, pytest. Elected.

This is deliberately NOT gated on ``get_mode()`` or ``is_cloud()``: it answers
"which process", a different question from "which data source". The mode gate
lives in ``runlog.py`` and ``locks.py``, which pick their backends.
"""

import os


def _reloader_child() -> bool:
    """Werkzeug sets this only in the child it re-executes.

    Checked FIRST and independently of ``app.debug``: its presence is a
    positive fact about this process, whereas ``app.debug`` is a flag someone
    has to remember to set early enough (``index.py`` sets ``FLASK_DEBUG``
    before ``create_app()`` for exactly that reason). Trusting the env var on
    its own means the child is elected even if the debug flag never lands.
    """
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def _reloader_parent(app) -> bool:
    if _reloader_child():
        return False
    return bool(app.debug)


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
