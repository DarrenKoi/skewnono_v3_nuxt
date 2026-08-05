import os

import pytest

from back_dev_home._scheduler.tasks import uwsgi_reload
from back_dev_home._scheduler.tasks.uwsgi_reload import (
    ini_path,
    parse_touch_reload,
    resolve_targets,
    touch_reload,
)


@pytest.fixture
def inside_uwsgi(monkeypatch):
    """Pretend the process is a uWSGI worker.

    Every behavioural test needs this: outside uWSGI the job is a deliberate
    no-op, so without it they would all pass for the wrong reason.
    """
    monkeypatch.setattr(uwsgi_reload, "under_uwsgi", lambda: True)


def _ini(tmp_path, body: str):
    path = tmp_path / "wsgi.ini"
    path.write_text(body)
    return path


# ── parsing ────────────────────────────────────────────────────────────────


def test_an_absolute_target_is_read_verbatim(tmp_path):
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = /project/workSpace/reload.trigger\n")
    assert parse_touch_reload(ini) == [
        type(tmp_path)("/project/workSpace/reload.trigger")
    ]


def test_percent_d_resolves_to_the_ini_directory(tmp_path):
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = %dreload.trigger\n")
    assert parse_touch_reload(ini) == [tmp_path / "reload.trigger"]


def test_percent_p_resolves_to_the_ini_itself(tmp_path):
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = %p\n")
    assert parse_touch_reload(ini) == [ini]


def test_a_relative_target_resolves_against_the_ini_directory(tmp_path):
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = reload.trigger\n")
    assert parse_touch_reload(ini) == [tmp_path / "reload.trigger"]


def test_an_unresolvable_magic_variable_is_dropped_not_guessed(tmp_path):
    # %c is the directory's BASENAME. Treating it as the directory would build
    # /project/workSpace/workSpace/... and touch a file uWSGI never reads --
    # a job that then "succeeds" nightly while reloading nothing.
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = %c/reload.trigger\n")
    assert parse_touch_reload(ini) == []


def test_commented_out_lines_are_not_targets(tmp_path):
    ini = _ini(
        tmp_path,
        "[uwsgi]\n; touch-reload = /old/path\n# touch-reload = /older/path\n",
    )
    assert parse_touch_reload(ini) == []


def test_a_trailing_comment_is_stripped_from_the_value(tmp_path):
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = /tmp/t.trigger ; nightly\n")
    assert parse_touch_reload(ini) == [type(tmp_path)("/tmp/t.trigger")]


def test_every_touch_reload_line_is_returned(tmp_path):
    # uWSGI watches all of them, so touching only the first would leave a
    # configured trigger dead.
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = /a.trigger\ntouch-reload = /b.trigger\n")
    assert [str(p) for p in parse_touch_reload(ini)] == ["/a.trigger", "/b.trigger"]


def test_a_similarly_named_option_is_not_matched(tmp_path):
    ini = _ini(tmp_path, "[uwsgi]\nfs-reload = /a.trigger\ntouch-chain-reload = /b\n")
    assert parse_touch_reload(ini) == []


def test_an_unreadable_ini_yields_no_targets(tmp_path):
    assert parse_touch_reload(tmp_path / "absent.ini") == []


# ── target resolution ──────────────────────────────────────────────────────


def test_the_env_override_wins_over_the_ini(tmp_path):
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = /from-ini.trigger\n")
    env = {
        "SKEWNONO_UWSGI_INI": str(ini),
        "SKEWNONO_RELOAD_TOUCH_FILE": "/from-env.trigger",
    }
    assert [str(p) for p in resolve_targets(env)] == ["/from-env.trigger"]


def test_the_ini_path_defaults_next_to_the_project_root():
    assert ini_path({}).name == "wsgi.ini"


def test_the_ini_path_honours_its_env_override():
    assert str(ini_path({"SKEWNONO_UWSGI_INI": "/elsewhere/w.ini"})) == "/elsewhere/w.ini"


# ── touching ───────────────────────────────────────────────────────────────


def test_outside_uwsgi_nothing_is_touched(tmp_path, monkeypatch):
    # Home and Phase 2 do not run uWSGI at all; a touch there would only
    # litter a developer's checkout.
    monkeypatch.setattr(uwsgi_reload, "under_uwsgi", lambda: False)
    target = tmp_path / "reload.trigger"
    assert touch_reload({"SKEWNONO_RELOAD_TOUCH_FILE": str(target)}) == 0
    assert not target.exists()


def test_an_existing_trigger_gets_a_newer_mtime(tmp_path, inside_uwsgi):
    target = tmp_path / "reload.trigger"
    target.write_text("")
    os.utime(target, (0, 0))
    assert touch_reload({"SKEWNONO_RELOAD_TOUCH_FILE": str(target)}) == 1
    assert target.stat().st_mtime > 0


def test_a_missing_trigger_is_created(tmp_path, inside_uwsgi):
    # uWSGI records mtime 0 for an absent trigger at boot, so the file
    # appearing IS the reload signal.
    target = tmp_path / "reload.trigger"
    assert touch_reload({"SKEWNONO_RELOAD_TOUCH_FILE": str(target)}) == 1
    assert target.exists()


def test_with_no_touch_reload_configured_nothing_happens(tmp_path, inside_uwsgi):
    ini = _ini(tmp_path, "[uwsgi]\nmaster = true\n")
    assert touch_reload({"SKEWNONO_UWSGI_INI": str(ini)}) == 0


def test_an_untouchable_target_does_not_stop_the_others(tmp_path, inside_uwsgi):
    good = tmp_path / "good.trigger"
    env = {"SKEWNONO_RELOAD_TOUCH_FILE": f"/proc/nonexistent/bad.trigger,{good}"}
    assert touch_reload(env) == 1
    assert good.exists()


def test_the_ini_targets_are_touched_when_no_override_is_set(tmp_path, inside_uwsgi):
    ini = _ini(tmp_path, "[uwsgi]\ntouch-reload = %dreload.trigger\n")
    assert touch_reload({"SKEWNONO_UWSGI_INI": str(ini)}) == 1
    assert (tmp_path / "reload.trigger").exists()


def test_under_uwsgi_is_false_in_this_test_process():
    # The gate is "did the uWSGI server inject its module", not an env var --
    # pytest is not uWSGI, so this must be False here.
    assert uwsgi_reload.under_uwsgi() is False
