"""`hcputil` lives only on the cloud image, so these tests inject stub
modules into sys.modules rather than importing the real library.

The module path is genuinely uncertain: the in-house requirements doc
(afm_data_platform/개발요구.txt:31) spells it `auto`, the library spells it
`auth`. The loader accepts either, and these tests pin that behaviour.
"""

import sys
import types

import pytest

from back_dev_home._auth.provider import _load_sso_class


class _FakeSSO:
    pass


@pytest.fixture
def stub_hcputil(monkeypatch):
    """Install hcputil.<variant>.sso stubs; yields an installer function."""

    def install(*variants):
        for variant in variants:
            pkg = types.ModuleType("hcputil")
            pkg.__path__ = []
            sub = types.ModuleType(f"hcputil.{variant}")
            sub.__path__ = []
            sso_mod = types.ModuleType(f"hcputil.{variant}.sso")
            sso_mod.SSO = _FakeSSO
            monkeypatch.setitem(sys.modules, "hcputil", pkg)
            monkeypatch.setitem(sys.modules, f"hcputil.{variant}", sub)
            monkeypatch.setitem(sys.modules, f"hcputil.{variant}.sso", sso_mod)

    return install


def test_prefers_auth_spelling(stub_hcputil):
    stub_hcputil("auth")
    assert _load_sso_class() is _FakeSSO


def test_falls_back_to_auto_spelling(stub_hcputil):
    stub_hcputil("auto")
    assert _load_sso_class() is _FakeSSO


def test_raises_naming_both_paths_when_neither_exists(monkeypatch):
    for name in list(sys.modules):
        if name == "hcputil" or name.startswith("hcputil."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "path", [])

    with pytest.raises(ImportError) as excinfo:
        _load_sso_class()

    message = str(excinfo.value)
    assert "hcputil.auth.sso" in message
    assert "hcputil.auto.sso" in message
