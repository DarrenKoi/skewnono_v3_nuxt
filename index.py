import os

# PyArrow 25's bundled mimalloc segfaults (SIGSEGV in mi_thread_init) on
# macOS/Python 3.14 when a fresh thread first allocates Arrow memory — and the
# werkzeug dev server runs every request on a fresh thread, while pandas 3
# routes string columns through pyarrow. Select Arrow's system allocator
# instead; must be set before libarrow loads.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

from back_dev_home import create_app
from back_dev_home._runtime.env import is_cloud

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
