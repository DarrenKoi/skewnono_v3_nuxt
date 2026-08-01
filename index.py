import os

# PyArrow 25's bundled mimalloc segfaults (SIGSEGV in mi_thread_init) on
# macOS/Python 3.14 when a fresh thread first allocates Arrow memory — and the
# werkzeug dev server runs every request on a fresh thread, while pandas 3
# routes string columns through pyarrow. Select Arrow's system allocator
# instead; must be set before libarrow loads.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

from back_dev_home import create_app
from back_dev_home._runtime.env import is_cloud

# FLASK_DEBUG must be set BEFORE create_app(), not left to app.run(debug=...)
# below. The scheduler elects its owner process during create_app() (see
# back_dev_home/_scheduler/election.py), and the Werkzeug reloader runs this
# module in TWO processes -- a watcher parent and the app child. The parent is
# identified by "debug and no WERKZEUG_RUN_MAIN", so if app.debug is still
# False at election time BOTH processes elect themselves and one dev machine
# runs two schedulers firing the same jobs. app.run's debug flag arrives long
# after that decision. Flask reads FLASK_DEBUG when the app is constructed,
# which is why this is an env var rather than an argument.
#
# index.py is NOT part of the deploy bundle (scripts/deploy/pack.py), so this
# reaches home and any host where index.py is re-copied. The cloud path is
# unaffected either way: uWSGI election returns before the reloader check ever
# runs, and is_cloud() keeps the flag off there regardless.
if not is_cloud():
    os.environ.setdefault("FLASK_DEBUG", "1")

app = create_app()
application = app

if __name__ == "__main__":
    cloud = is_cloud()
    host = "0.0.0.0" if cloud else "127.0.0.1"
    # use_debugger=False: the Werkzeug in-browser debugger allocates a
    # multiprocessing semaphore that leaks a resource_tracker warning on
    # every abrupt exit (reloader restarts, SIGTERM). Tracebacks still
    # print to the terminal; the reloader stays on via debug=True.
    app.run(
        host=host,
        port=int(os.environ.get("PORT", 5050)),
        debug=not cloud,
        use_debugger=False,
    )
