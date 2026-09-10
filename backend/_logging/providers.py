"""Logger for provider-resolution reporting.

Carries its own handler and level, mirroring ``skewnono.activity`` in
``activity.py``: ``app.logger`` inherits WARNING from the root logger, so INFO
records about which features are serving 사내 data would be invisible in
exactly the deployment that needs them.

Lives here rather than in ``_runtime.boot`` so a feature's office adapter can
log a fallback without importing a boot-reporting module — hardware's
per-tab dispatcher is the caller that made that dependency direction wrong.

Setup is a function, not an import-time side effect, so importing the logger
never mutates global logging state.
"""

import logging


logger = logging.getLogger("skewnono.providers")


def install_console_logger(target: logging.Logger) -> None:
    """Attach a console handler once. Idempotent. Shared with ``activity.py``."""
    if target.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    target.addHandler(handler)
    target.setLevel(logging.INFO)
    target.propagate = False


def install_provider_logging() -> None:
    """Attach the handler once. Idempotent, like install_activity_logging."""
    install_console_logger(logger)
