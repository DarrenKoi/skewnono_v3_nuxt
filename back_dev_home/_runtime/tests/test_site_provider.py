"""Site detection + two-step provider resolution.

The invariant: an explicit per-feature env var always wins; otherwise a
feature serves office data only when the process is in office MODE *and* that
feature has a providers/office.py.

Resolution tests point office_registry at a fake tree rather than the real
repo. office.py is gitignored, so which adapters exist is a property of the
machine running the tests — this Mac mini happens to have six, written while
developing them, and the office has a different set. A fixed tree is the only
way to assert exact resolution.
"""

import os

import pytest

from back_dev_home._runtime import data_provider, office_registry, site


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Neutralize any real provider/site config leaking in from .env.

    validate_env() scans EVERY SKEWNONO_*_PROVIDER variable, so a hardcoded
    delenv list would let one stray office line in .env fail unrelated tests
    here. Strip them all instead. This also covers SKEWNONO_DATA_PROVIDER.
    """
    monkeypatch.delenv("SKEWNONO_SITE", raising=False)
    monkeypatch.delenv("SKEWNONO_OFFICE_HOSTNAMES", raising=False)
    for name in list(os.environ):
        if name.startswith("SKEWNONO_") and name.endswith("_PROVIDER"):
            monkeypatch.delenv(name)


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """A fake tree where sem_list + storage have office.py and chat/skew do not."""
    root = tmp_path / "back_dev_home"
    for rel, filenames in {
        "sem_list": ["mock.py", "office.py"],
        "ebeam/hitachi/storage": ["mock.py", "office.py"],
        "chat": ["mock.py", "office_example.py"],
        "ebeam/hitachi/skew": ["mock.py", "office_example.py"],
    }.items():
        providers = root / rel / "providers"
        providers.mkdir(parents=True)
        for filename in filenames:
            (providers / filename).write_text("")
    monkeypatch.setattr(office_registry, "_ROOT", root)
    office_registry.reset_cache()
    yield root
    office_registry.reset_cache()


def _set_host(monkeypatch, name: str) -> None:
    monkeypatch.setattr(site.socket, "gethostname", lambda: name)
    # These tests run outside /project/workSpace, so is_cloud() is already
    # False — no stub needed; the cloud test overrides it explicitly.


# ---------------------------------------------------------------- detect_site

def test_home_hostname_detected_with_suffix_and_case(monkeypatch):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini.local")
    assert site.detect_site() == "home"


def test_unknown_hostname_is_none(monkeypatch):
    _set_host(monkeypatch, "some-random-box")
    assert site.detect_site() is None


def test_pc_prefix_is_office(monkeypatch):
    # Company-issued office PCs are named "PC<...>" — prefix alone suffices.
    _set_host(monkeypatch, "PC0123456.corp.example")
    assert site.detect_site() == "office"


def test_office_hostnames_env_list(monkeypatch):
    _set_host(monkeypatch, "OFFICE-MAC-01.corp.example")
    monkeypatch.setenv("SKEWNONO_OFFICE_HOSTNAMES", "office-mac-01, spare-box")
    assert site.detect_site() == "office"


def test_cloud_deploy_is_office_site(monkeypatch):
    # Phase 3: production must NEVER silently fall back to mock just because
    # the cloud VM hostname isn't in any registry — the deploy path decides.
    _set_host(monkeypatch, "ephemeral-vm-8f3a2")  # unknown hostname
    monkeypatch.setattr(site, "is_cloud", lambda: True)
    assert site.detect_site() == "office"


def test_site_env_overrides_hostname(monkeypatch):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini.local")  # a home machine...
    monkeypatch.setenv("SKEWNONO_SITE", "office")       # ...forced to office
    assert site.detect_site() == "office"


def test_invalid_site_env_raises(monkeypatch):
    monkeypatch.setenv("SKEWNONO_SITE", "moon-base")
    with pytest.raises(RuntimeError):
        site.detect_site()


# ---------------------------------------------------------------------- mode

def test_mode_follows_site_when_global_var_unset(monkeypatch):
    _set_host(monkeypatch, "PC0123456")
    assert data_provider.get_mode() == "office"
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    assert data_provider.get_mode() == "mock"


def test_unknown_host_is_mock_mode(monkeypatch):
    _set_host(monkeypatch, "some-random-box")
    assert data_provider.get_mode() == "mock"


def test_global_var_overrides_site_in_both_directions(monkeypatch):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    assert data_provider.get_mode() == "office"
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    _set_host(monkeypatch, "PC0123456")
    assert data_provider.get_mode() == "mock"


def test_invalid_global_var_raises(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "opensearch")
    with pytest.raises(RuntimeError) as exc:
        data_provider.get_mode()
    assert "SKEWNONO_DATA_PROVIDER" in str(exc.value)


# --------------------------------------------------------- get_data_provider

def test_office_mode_flips_only_features_with_an_adapter(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    assert data_provider.get_data_provider("sem_list") == "office"
    assert data_provider.get_data_provider("storage") == "office"
    # No office.py -> mock, silently. A blanket office default would 500 these.
    assert data_provider.get_data_provider("chat") == "mock"
    assert data_provider.get_data_provider("skew") == "mock"


def test_mock_mode_ignores_present_adapters(monkeypatch, wired):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    assert data_provider.get_data_provider("sem_list") == "mock"


def test_kill_switch_returns_the_whole_instance_to_mock(monkeypatch, wired):
    """One line takes an office machine back to a known-good state without
    deleting any adapter."""
    _set_host(monkeypatch, "PC0123456")
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    assert data_provider.get_data_provider("sem_list") == "mock"
    assert data_provider.get_data_provider("storage") == "mock"


def test_feature_var_mock_beats_a_present_adapter(monkeypatch, wired):
    """The escape hatch when an office adapter breaks mid-shift."""
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    monkeypatch.setenv("SKEWNONO_STORAGE_PROVIDER", "mock")
    assert data_provider.get_data_provider("storage") == "mock"
    assert data_provider.get_data_provider("sem_list") == "office"


def test_feature_var_office_wins_at_home(monkeypatch, wired):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    monkeypatch.setenv("SKEWNONO_SEM_LIST_PROVIDER", "office")
    assert data_provider.get_data_provider("sem_list") == "office"


def test_invalid_feature_var_raises_naming_that_var(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SEM_LIST_PROVIDER", "redis")
    with pytest.raises(RuntimeError) as exc:
        data_provider.get_data_provider("sem_list")
    assert "SKEWNONO_SEM_LIST_PROVIDER" in str(exc.value)


# --------------------------------------------------------------- resolve_all

def test_resolve_all_reports_provider_and_reason(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    monkeypatch.setenv("SKEWNONO_STORAGE_PROVIDER", "mock")
    by_feature = {r.feature: r for r in data_provider.resolve_all()}

    assert set(by_feature) == {"sem_list", "storage", "chat", "skew"}
    assert by_feature["sem_list"].provider == "office"
    assert by_feature["sem_list"].reason == "providers/office.py found"
    assert by_feature["chat"].provider == "mock"
    assert by_feature["chat"].reason == "no providers/office.py"
    assert by_feature["storage"].provider == "mock"
    assert "SKEWNONO_STORAGE_PROVIDER" in by_feature["storage"].reason


def test_resolve_all_reports_mode_when_not_at_the_office(monkeypatch, wired):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    by_feature = {r.feature: r for r in data_provider.resolve_all()}
    assert by_feature["sem_list"].provider == "mock"
    assert by_feature["sem_list"].reason == "mode=mock"


# -------------------------------------------------------------- validate_env

def test_validate_env_passes_when_config_matches_the_filesystem(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SEM_LIST_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "mock")
    data_provider.validate_env()  # must not raise


def test_validate_env_refuses_office_without_an_adapter(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "office")
    with pytest.raises(RuntimeError) as exc:
        data_provider.validate_env()
    message = str(exc.value)
    assert "SKEWNONO_CHAT_PROVIDER" in message
    assert "cp back_dev_home/chat/providers/office_example.py" in message
    assert "back_dev_home/chat/providers/office.py" in message


def test_validate_env_flags_an_unknown_feature_as_a_typo(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_STORAGES_PROVIDER", "office")
    with pytest.raises(RuntimeError) as exc:
        data_provider.validate_env()
    assert "unknown feature" in str(exc.value)


def test_validate_env_ignores_the_global_mode_var(monkeypatch, wired):
    """SKEWNONO_DATA_PROVIDER selects the mode; it names no feature, so it can
    never be 'unhonorable'."""
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    data_provider.validate_env()  # must not raise
