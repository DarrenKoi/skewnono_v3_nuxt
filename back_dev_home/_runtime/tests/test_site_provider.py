"""Site detection + provider resolution precedence.

The invariant under test: explicit env vars always win; the hostname-based
site default only ever flips OFFICE_READY features, and only on a recognized
office machine; everything else stays mock.
"""

import pytest

from back_dev_home._runtime import data_provider, site


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Neutralize any real provider/site config leaking in from .env."""
    monkeypatch.delenv("SKEWNONO_SITE", raising=False)
    monkeypatch.delenv("SKEWNONO_DATA_PROVIDER", raising=False)
    monkeypatch.delenv("SKEWNONO_OFFICE_HOSTNAMES", raising=False)
    monkeypatch.delenv("SKEWNONO_STORAGE_PROVIDER", raising=False)
    monkeypatch.delenv("SKEWNONO_CHAT_PROVIDER", raising=False)


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
    assert data_provider.get_data_provider("sem_list") == "office"
    assert data_provider.get_data_provider("chat") == "mock"  # not office-ready


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
    assert data_provider.get_data_provider("sem_list") == "office"


def test_site_env_overrides_hostname(monkeypatch):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini.local")  # a home machine...
    monkeypatch.setenv("SKEWNONO_SITE", "office")       # ...forced to office
    assert site.detect_site() == "office"


def test_invalid_site_env_raises(monkeypatch):
    monkeypatch.setenv("SKEWNONO_SITE", "moon-base")
    with pytest.raises(RuntimeError):
        site.detect_site()


# --------------------------------------------------------- get_data_provider

def test_home_defaults_to_mock(monkeypatch):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    assert data_provider.get_data_provider("storage") == "mock"


def test_office_default_flips_only_ready_features(monkeypatch):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    assert "storage" in site.OFFICE_READY
    assert data_provider.get_data_provider("storage") == "office"
    # chat has no working office adapter — a blanket default would 500 it.
    assert "chat" not in site.OFFICE_READY
    assert data_provider.get_data_provider("chat") == "mock"


def test_explicit_feature_var_beats_office_site(monkeypatch):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    monkeypatch.setenv("SKEWNONO_STORAGE_PROVIDER", "mock")
    assert data_provider.get_data_provider("storage") == "mock"


def test_global_var_beats_site_default(monkeypatch):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    assert data_provider.get_data_provider("sem_list") == "mock"


def test_unknown_host_defaults_to_mock_even_for_ready_features(monkeypatch):
    _set_host(monkeypatch, "some-random-box")
    assert data_provider.get_data_provider("sem_list") == "mock"
