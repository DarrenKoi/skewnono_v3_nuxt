"""Site detection + two-step provider resolution.

The invariant: an explicit per-feature env var always wins; otherwise a
feature serves office data only when the process is in office MODE *and* that
feature has a providers/office.py.

The `wired` fake tree and env scrubbing live in conftest.py.
"""

import pytest

from back_dev_home._runtime import data_provider, office_registry, site


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
    assert data_provider.get_data_provider("tttm") == "mock"


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


def test_office_without_an_adapter_raises_off_the_app_factory_path(
    monkeypatch, wired
):
    """The refusal must hold wherever resolution happens, not only in
    create_app().

    Every MIGRATION.md tells you to verify an adapter with
    `SKEWNONO_<F>_PROVIDER=office .venv/bin/pytest back_dev_home/<f>`, which
    never builds an app and so never calls validate_env(). Without this check
    that command dies on a bare ModuleNotFoundError from data.py instead of
    the cp command — on precisely the path the docs send people down.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "office")
    with pytest.raises(RuntimeError) as exc:
        data_provider.get_data_provider("chat")
    message = str(exc.value)
    assert "cp back_dev_home/chat/providers/office_example.py" in message


def test_the_two_paths_give_the_identical_message(monkeypatch, wired):
    """validate_env() and get_data_provider() must not drift on diagnosis."""
    monkeypatch.setenv("SKEWNONO_TTTM_PROVIDER", "office")

    with pytest.raises(RuntimeError) as boot_exc:
        data_provider.validate_env()
    with pytest.raises(RuntimeError) as request_exc:
        data_provider.get_data_provider("tttm")

    assert str(boot_exc.value) == str(request_exc.value)


def test_hyphenated_and_cased_slugs_resolve_to_the_same_feature(
    monkeypatch, wired
):
    """get_data_provider() normalizes its argument; resolve_all() feeds it raw
    slugs. Both must land on the same env var and the same adapter."""
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    assert data_provider.get_data_provider("SEM-List") == "office"
    monkeypatch.setenv("SKEWNONO_SEM_LIST_PROVIDER", "mock")
    assert data_provider.get_data_provider("SEM-List") == "mock"


def test_a_new_office_py_only_takes_effect_after_a_restart(monkeypatch, wired):
    """Readiness is scanned once per process, deliberately.

    `cp office_example.py office.py` is done by hand at the office, sometimes
    while Flask is running. The env vars above are re-read on every call, but
    this one is not: a feature that flipped mid-process would make the boot
    table and /api/health/providers describe a state that no longer holds, and
    two requests seconds apart would read from different backends — with only
    one of them exercised by whatever verification followed the cp.

    So the scan is memoized and a restart is the way in (Flask's dev reloader
    and every cloud deploy restart anyway). Anyone who "fixes" the cache to
    pick up new files must break this test first.
    """
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    assert data_provider.get_data_provider("chat") == "mock"

    (wired / "chat" / "providers" / "office.py").write_text("")
    assert data_provider.get_data_provider("chat") == "mock"  # not until restart

    office_registry.reset_cache()  # what a restart amounts to
    assert data_provider.get_data_provider("chat") == "office"


# --------------------------------------------------------------- resolve_all

def test_resolve_all_reports_provider_and_reason(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    monkeypatch.setenv("SKEWNONO_STORAGE_PROVIDER", "mock")
    by_feature = {r.feature: r for r in data_provider.resolve_all()}

    assert set(by_feature) == {"sem_list", "storage", "chat", "tttm"}
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


def test_validate_env_leaves_chat_sub_provider_selectors_to_chat(monkeypatch, wired):
    """Knowledge/scope adapters are lazy chat seams, not feature providers."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_SCOPE_PROVIDER", "office")

    data_provider.validate_env()  # must not require chat/providers/office.py


@pytest.mark.parametrize(
    "env_name",
    [
        "SKEWNONO_CHAT_KNOWLEDGE_PROVIDER",
        "SKEWNONO_CHAT_SCOPE_PROVIDER",
    ],
)
def test_validate_env_rejects_invalid_lazy_chat_selector(
    monkeypatch, wired, env_name
):
    """Lazy adapter resolution must not make invalid selector values lazy."""
    monkeypatch.setenv(env_name, "typo")

    with pytest.raises(RuntimeError, match=env_name):
        data_provider.validate_env()


# ------------------------------------------- cross-feature office dependencies
#
# storage's office adapter joins every row against the live sem_list by
# eqp_ip. Pairing it with a mock sem_list is the one misconfiguration that
# produces no error at all: the join matches nothing, and the table renders
# empty behind a 200.

def _storage_only_tree(fake_tree):
    """storage has an office adapter; sem_list does not — the cp-one-of-two slip."""
    return fake_tree(
        {
            "sem_list": ["mock.py", "office_example.py"],
            "ebeam/storage": ["mock.py", "office.py"],
        }
    )


def test_validate_env_refuses_office_storage_against_a_mock_sem_list(
    monkeypatch, fake_tree
):
    _storage_only_tree(fake_tree)
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")

    with pytest.raises(RuntimeError) as exc:
        data_provider.validate_env()

    message = str(exc.value)
    # Both sides named, so the message says which pairing is wrong...
    assert "storage" in message
    assert "sem_list" in message
    # ...and carries the fix, the same shape as the missing-adapter error.
    assert "cp back_dev_home/sem_list/providers/office_example.py" in message


def test_forcing_sem_list_to_mock_is_refused_too(monkeypatch, wired):
    """Both adapters present, but sem_list explicitly demoted — same hazard."""
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_SEM_LIST_PROVIDER", "mock")

    with pytest.raises(RuntimeError, match="sem_list"):
        data_provider.validate_env()


def test_storage_on_mock_needs_no_office_sem_list(monkeypatch, fake_tree):
    """The dependency is a property of the OFFICE adapter only.

    A home instance runs storage's mock, which builds its own fleet — nothing
    joins, so nothing can silently empty.
    """
    _storage_only_tree(fake_tree)
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")

    data_provider.validate_env()  # must not raise


def test_both_on_office_is_the_supported_pairing(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")

    data_provider.validate_env()  # must not raise
