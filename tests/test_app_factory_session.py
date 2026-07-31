"""Boot-time configuration for the declared-identity session.

The signature on that session is the only thing making its `verified` flag mean
anything, so on the cloud a missing key is not a weak setting — it is an
unsigned session that still looks signed. This module pins that the app refuses
to start in that state, and that home, where there is nothing to forge, keeps
its convenience fallback.

`load_dotenv` is neutralized throughout. `create_app` loads
`back_dev_home/.env`, which exists on a developer's checkout and not in a fresh
worktree, and `load_dotenv` sets a variable a test just deleted — so without
this the results would depend on which tree the suite is run from.
"""

from datetime import timedelta

import pytest

import back_dev_home
from back_dev_home import create_app


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(back_dev_home, "load_dotenv", lambda *a, **k: None)


@pytest.fixture
def cloud(monkeypatch):
    """`is_cloud` is imported into the factory's namespace, so patching it at
    its source module would leave the factory's reference untouched."""
    monkeypatch.setattr(back_dev_home, "is_cloud", lambda: True)


@pytest.fixture
def home(monkeypatch):
    monkeypatch.setattr(back_dev_home, "is_cloud", lambda: False)


def _has_proxyfix(app) -> bool:
    from werkzeug.middleware.proxy_fix import ProxyFix

    return isinstance(app.wsgi_app, ProxyFix)


def test_the_cloud_refuses_to_boot_without_a_secret_key(monkeypatch, cloud):
    """Silent forgeability becomes a startup error — surfaced once, at deploy,
    rather than never."""
    monkeypatch.delenv("SKEWNONO_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SKEWNONO_SECRET_KEY"):
        create_app()


def test_a_blank_secret_key_is_treated_as_absent(monkeypatch, cloud):
    """`SKEWNONO_SECRET_KEY=` in a .env reads as "" — not None, so a plain
    presence check would sail past it into an effectively unsigned session.
    The same trap is documented for MINIO_SECRET_KEY in .env.example."""
    monkeypatch.setenv("SKEWNONO_SECRET_KEY", "   ")

    with pytest.raises(RuntimeError, match="SKEWNONO_SECRET_KEY"):
        create_app()


def test_the_cloud_boots_with_any_non_empty_key(monkeypatch, cloud):
    """The gate asks whether a value was CHOSEN, not whether it is strong.
    Judging strength here would block a deploy over a policy this code has no
    standing to set."""
    monkeypatch.setenv("SKEWNONO_SECRET_KEY", "any-non-empty-value")

    assert create_app().secret_key == "any-non-empty-value"


def test_home_boots_without_one(monkeypatch, home):
    """There is nothing to forge at home, and requiring setup here would put a
    stop sign in front of every fresh checkout."""
    monkeypatch.delenv("SKEWNONO_SECRET_KEY", raising=False)

    assert create_app().secret_key


def test_home_still_prefers_a_real_key_when_given_one(monkeypatch, home):
    monkeypatch.setenv("SKEWNONO_SECRET_KEY", "a-home-key")

    assert create_app().secret_key == "a-home-key"


def test_the_session_lasts_thirty_days(home):
    """Only sessions marked permanent get a lifetime, and self_id.write_declared
    marks them — this is the other half of that pair."""
    assert create_app().permanent_session_lifetime == timedelta(days=30)


def test_proxyfix_is_off_by_default(monkeypatch, home):
    """Trusting X-Forwarded-For while the app is directly exposed lets anyone
    forge their own IP with a header, so it is opt-in rather than detected."""
    monkeypatch.delenv("SKEWNONO_TRUST_PROXY", raising=False)

    assert not _has_proxyfix(create_app())


@pytest.mark.parametrize("flag", ["1", "true", "TRUE", "yes"])
def test_proxyfix_is_applied_when_the_flag_is_set(monkeypatch, home, flag):
    monkeypatch.setenv("SKEWNONO_TRUST_PROXY", flag)

    assert _has_proxyfix(create_app())


@pytest.mark.parametrize("flag", ["0", "false", "no", ""])
def test_an_unset_looking_flag_does_not_enable_it(monkeypatch, home, flag):
    """`SKEWNONO_TRUST_PROXY=false` must mean false. Treating any non-empty
    string as true is the classic way an opt-in becomes an always-on."""
    monkeypatch.setenv("SKEWNONO_TRUST_PROXY", flag)

    assert not _has_proxyfix(create_app())


@pytest.fixture
def seeded(monkeypatch):
    """The factory imports `seed_demo_users` inside the branch, so the module
    attribute is what it resolves at call time."""
    from back_dev_home.activity import data as activity_data

    calls: list[int] = []
    monkeypatch.setattr(activity_data, "seed_demo_users", lambda: calls.append(1))
    return calls


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setattr(back_dev_home, "get_mode", lambda: "mock")


@pytest.fixture
def office_mode(monkeypatch):
    monkeypatch.setattr(back_dev_home, "get_mode", lambda: "office")
    # Office mode points the rate limiter at Redis; without this the boot
    # spends its connect timeout on a host that is not there.
    monkeypatch.delenv("REDIS_HOST", raising=False)


def test_home_seeds_the_demo_users(home, mock_mode, seeded):
    assert create_app() and seeded


def test_office_localhost_does_not_seed(home, office_mode, seeded):
    """Phase 2 runs on office localhost, where /project/workSpace/ is absent —
    so is_cloud() reads false and the old gate seeded there. Any feature
    falling back to the mock adapter then served five invented employees as
    real ones."""
    assert create_app() and not seeded


def test_the_cloud_does_not_seed_even_with_the_kill_switch(
    monkeypatch, cloud, mock_mode, seeded
):
    """SKEWNONO_DATA_PROVIDER=mock makes get_mode() report "mock" on the cloud
    host, so mode alone would reopen the hole is_cloud() was closing."""
    monkeypatch.setenv("SKEWNONO_SECRET_KEY", "a-cloud-key")

    assert create_app() and not seeded


def test_the_session_cookie_is_samesite_lax(home):
    """Explicit, not inherited from browser defaults: without the attribute a
    pre-Lax-by-default browser sends the session cookie on a cross-site form
    POST, and /api/identify's response plants an attacker-chosen declared
    identity (login-CSRF, 30 days of mis-attribution)."""
    app = create_app()

    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
