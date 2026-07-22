import pytest

from back_dev_home.chat import guard


@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch):
    # Isolate every test from an ambient global provider setting.
    monkeypatch.delenv("SKEWNONO_DATA_PROVIDER", raising=False)
    monkeypatch.delenv("SKEWNONO_CHAT_PROVIDER", raising=False)
    monkeypatch.delenv("CHAT_BLOCKED_HOSTS", raising=False)


def _office(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")


def _mock(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")


def test_guard_is_active_on_an_office_host_with_no_chat_config(monkeypatch):
    """Regression: the guard must key on the MODE, not on chat's adapter.

    chat is parked, so it never had an office adapter. While this function
    checked get_data_provider("chat"), that returned "mock" on a real office
    host — and the guard that exists to keep chat data on the company network
    returned early and blocked nothing, in exactly the deployment it was
    written for. Nothing sets SKEWNONO_CHAT_PROVIDER at the office, so this is
    the default configuration, not an edge case.
    """
    monkeypatch.setattr(guard, "get_mode", lambda: "office")
    with pytest.raises(guard.ChatEgressBlocked):
        guard.enforce_egress_policy("https://openrouter.ai/api/v1")


# --- pure helpers -----------------------------------------------------------

def test_default_blocked_hosts_include_openrouter():
    assert "openrouter.ai" in guard.get_blocked_hosts()
    assert "api.openai.com" in guard.get_blocked_hosts()


def test_host_is_blocked_exact_match():
    assert guard.host_is_blocked("openrouter.ai", {"openrouter.ai"})


def test_host_is_blocked_subdomain_suffix():
    assert guard.host_is_blocked("x.openrouter.ai", {"openrouter.ai"})


def test_host_is_blocked_is_case_insensitive():
    assert guard.host_is_blocked("OpenRouter.AI", {"openrouter.ai"})


def test_host_is_blocked_rejects_unrelated_host():
    assert not guard.host_is_blocked("llm.sknn.local", {"openrouter.ai"})


def test_host_is_blocked_no_false_suffix_match():
    # "notopenrouter.ai" must NOT match "openrouter.ai".
    assert not guard.host_is_blocked("notopenrouter.ai", {"openrouter.ai"})


def test_blocked_hosts_env_extends_defaults(monkeypatch):
    monkeypatch.setenv("CHAT_BLOCKED_HOSTS", "extra.example.com, another.example.com")
    hosts = guard.get_blocked_hosts()
    assert "extra.example.com" in hosts
    assert "another.example.com" in hosts
    assert "openrouter.ai" in hosts  # still keeps the defaults


# --- enforce_egress_policy --------------------------------------------------

def test_mock_mode_allows_openrouter(monkeypatch):
    _mock(monkeypatch)
    guard.enforce_egress_policy("https://openrouter.ai/api/v1")  # no raise


def test_office_mode_blocks_default_openrouter(monkeypatch):
    _office(monkeypatch)
    with pytest.raises(guard.ChatEgressBlocked):
        guard.enforce_egress_policy("https://openrouter.ai/api/v1")


def test_office_mode_blocks_openrouter_subdomain(monkeypatch):
    _office(monkeypatch)
    with pytest.raises(guard.ChatEgressBlocked):
        guard.enforce_egress_policy("https://x.openrouter.ai/api/v1")


def test_office_mode_blocks_openai(monkeypatch):
    _office(monkeypatch)
    with pytest.raises(guard.ChatEgressBlocked):
        guard.enforce_egress_policy("https://api.openai.com/v1")


def test_office_mode_allows_internal_host(monkeypatch):
    _office(monkeypatch)
    guard.enforce_egress_policy("http://llm.sknn.local/v1")  # no raise


def test_office_mode_blocks_host_added_via_env(monkeypatch):
    _office(monkeypatch)
    monkeypatch.setenv("CHAT_BLOCKED_HOSTS", "gateway.public.example")
    with pytest.raises(guard.ChatEgressBlocked):
        guard.enforce_egress_policy("https://gateway.public.example/v1")


def test_blocked_exception_carries_message(monkeypatch):
    _office(monkeypatch)
    with pytest.raises(guard.ChatEgressBlocked) as exc:
        guard.enforce_egress_policy("https://openrouter.ai/api/v1")
    assert exc.value.message
