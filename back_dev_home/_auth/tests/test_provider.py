"""The cloud image supplies `hcputil.auth.sso`; tests inject a local stub."""

import sys
import types

import pytest

from back_dev_home._auth.provider import _load_sso_class


class _FakeSSO:
    pass


@pytest.fixture
def stub_hcputil_auth(monkeypatch):
    pkg = types.ModuleType("hcputil")
    pkg.__path__ = []
    sub = types.ModuleType("hcputil.auth")
    sub.__path__ = []
    sso_mod = types.ModuleType("hcputil.auth.sso")
    sso_mod.SSO = _FakeSSO
    monkeypatch.setitem(sys.modules, "hcputil", pkg)
    monkeypatch.setitem(sys.modules, "hcputil.auth", sub)
    monkeypatch.setitem(sys.modules, "hcputil.auth.sso", sso_mod)


def test_loads_auth_sso(stub_hcputil_auth):
    assert _load_sso_class() is _FakeSSO


def test_does_not_fall_back_to_auto_typo(monkeypatch):
    attempted = []

    def missing(name):
        attempted.append(name)
        raise ImportError(name)

    monkeypatch.setattr(
        "back_dev_home._auth.provider.importlib.import_module",
        missing,
    )

    with pytest.raises(ImportError, match=r"hcputil\.auth\.sso"):
        _load_sso_class()

    assert attempted == ["hcputil.auth.sso"]
