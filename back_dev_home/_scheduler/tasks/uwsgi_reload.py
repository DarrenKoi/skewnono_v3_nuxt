"""Nightly uWSGI reload, by touching whatever ``touch-reload`` watches.

A long-lived worker accumulates state we do not manage: cached provider
modules, a warmed `lru_cache`, FTP/MinIO clients, and whatever the office
adapters hold open. Restarting once a night, in the quiet hour, keeps the
instance fresh without an operator logging in.

**The target is read out of wsgi.ini, never guessed.** A job that touches a
file uWSGI is not watching succeeds every night and reloads nothing -- there is
no error to notice, and the only symptom is uptime that keeps climbing. So this
parses the deploy's own ``touch-reload`` lines and touches exactly those. If the
operator changes the path, the job follows it with no code change; if the
option is absent, the job says so and does nothing.

**It is a hard no-op outside uWSGI.** ``import uwsgi`` succeeds only inside a
uWSGI worker -- the module is injected by the server, not installed by pip --
which makes it the one reliable "is this reload even meaningful" signal. Home
(Werkzeug) and Phase 2 (Flask dev server) therefore skip before touching
anything, so no stray trigger file appears in a developer's checkout.

The alternative, calling ``uwsgi.reload()`` directly, needs no config at all,
but it is also unconditional: a bad path here fails visibly in the run log,
while a bad ``uwsgi.reload()`` would restart an instance whose operator had
deliberately turned reloading off. Following the config is the more honest of
the two.

Note the reload lands on the process running this job, so the run log's ``end``
record for ``uwsgi_touch_reload`` is written microseconds before the worker is
told to go away, and may be lost if the master is quick. The ``INFO`` line below
is emitted *before* the touch for exactly that reason -- the uWSGI log is the
durable record here.
"""

import logging
import os
import re
from collections.abc import Mapping
from pathlib import Path

from back_dev_home._runtime.env import project_root

logger = logging.getLogger("skewnono.scheduler")

# `;` and `#` both start a comment in a uWSGI ini. Stripping them inline too is
# the deliberate reading: a log-trigger path containing `;` or `#` is far less
# likely than a trailing note, and if uWSGI did take such a character
# literally the config was already watching a file nobody creates.
_TOUCH_RELOAD_RE = re.compile(r"^\s*touch-reload\s*=\s*([^;#]+?)\s*(?:[;#].*)?$")


def under_uwsgi() -> bool:
    """True only inside a uWSGI worker."""
    try:
        import uwsgi  # noqa: F401
    except ImportError:
        return False
    return True


def ini_path(env: Mapping[str, str] | None = None) -> Path:
    """The wsgi.ini this deploy actually booted from.

    Overridable because the cloud's ``/project/workSpace/wsgi.ini`` is
    deliberately outside the deploy bundle (docs/deployment.md) -- it can be
    edited to live somewhere else without this job noticing.
    """
    env = os.environ if env is None else env
    raw = (env.get("SKEWNONO_UWSGI_INI") or "").strip()
    return Path(raw) if raw else project_root() / "wsgi.ini"


def resolve_targets(env: Mapping[str, str] | None = None) -> list[Path]:
    """The files to touch: the env override, else every ``touch-reload`` line.

    uWSGI allows the option more than once and watches all of them, so this
    returns a list rather than picking the first.
    """
    env = os.environ if env is None else env
    override = (env.get("SKEWNONO_RELOAD_TOUCH_FILE") or "").strip()
    if override:
        return [Path(p.strip()) for p in override.split(",") if p.strip()]
    return parse_touch_reload(ini_path(env))


def parse_touch_reload(ini: Path) -> list[Path]:
    """Read ``touch-reload`` values out of a uWSGI ini, magic vars resolved.

    Only ``%p`` (this file) and ``%d`` (its directory, trailing slash) are
    substituted -- they are the two that name a path. Anything else left as
    ``%x`` is reported and dropped rather than guessed: ``%c`` in particular is
    the directory's *basename*, so resolving it as a directory would silently
    produce ``/project/workSpace/workSpace/...`` and touch a file no one reads.

    A relative value is resolved against the ini's directory, which is what
    uWSGI's own ``chdir`` makes it mean here.
    """
    try:
        text = ini.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.warning("uwsgi_reload could not read %s: %s", ini, exc)
        return []

    targets: list[Path] = []
    for line in text.splitlines():
        if line.lstrip().startswith((";", "#")):
            continue
        match = _TOUCH_RELOAD_RE.match(line)
        if not match:
            continue
        value = (
            match.group(1)
            .replace("%p", str(ini))
            .replace("%d", f"{ini.parent}{os.sep}")
        )
        if "%" in value:
            logger.warning(
                "uwsgi_reload skipping touch-reload = %s: unresolved uWSGI "
                "magic variable",
                match.group(1),
            )
            continue
        path = Path(value)
        targets.append(path if path.is_absolute() else ini.parent / path)
    return targets


def touch_reload(env: Mapping[str, str] | None = None) -> int:
    """Touch every configured trigger file. Returns how many were touched.

    ``Path.touch()`` creates the file when missing, which is correct rather
    than merely convenient: uWSGI records mtime 0 for an absent trigger at
    boot, so the file appearing is itself a reload signal, and the first run
    after a fresh deploy would otherwise have nothing to bump.
    """
    if not under_uwsgi():
        logger.info("uwsgi_reload: not running under uWSGI; nothing to reload")
        return 0

    targets = resolve_targets(env)
    if not targets:
        logger.warning(
            "uwsgi_reload: no touch-reload configured in %s and no "
            "SKEWNONO_RELOAD_TOUCH_FILE set; the nightly reload is a no-op",
            ini_path(env),
        )
        return 0

    touched = 0
    for path in targets:
        # Logged BEFORE the touch: the reload it triggers may end this process
        # before any later line is flushed.
        logger.info("uwsgi_reload touching %s; workers will reload", path)
        try:
            path.touch()
        except OSError as exc:
            logger.warning("uwsgi_reload could not touch %s: %s", path, exc)
            continue
        touched += 1
    return touched
