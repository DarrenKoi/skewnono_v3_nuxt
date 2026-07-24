"""The cloud preflight checker must degrade to a report, never an exception.

Its whole job is to run on a host where things are broken, so any check that
raises instead of returning a failure string is a bug.
"""

import sys
import types
from pathlib import Path

import pytest

from scripts import preflight_cloud


def _make_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    (root / "back_dev_home" / "_runtime").mkdir(parents=True)
    (root / "back_dev_home" / "_runtime" / "env.py").write_text("")
    (root / "front-dev-home" / ".output" / "public").mkdir(parents=True)
    (root / "front-dev-home" / ".output" / "public" / "index.html").write_text("<!doctype html>")
    (root / "back_dev_home" / ".env").write_text("SKEWNONO_SECRET_KEY=real-key\n")
    (root / "back_dev_home" / "requirements.txt").write_text("Flask>=3.0\n")
    (root / "index.py").write_text("")
    (root / "wsgi.ini").write_text("[uwsgi]\n")
    return root


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    """A well-formed bundle that also *looks* like it sits under the cloud
    prefix. CLOUD_PREFIX is repointed at tmp_path because the real prefix is an
    absolute host path no test can create -- without this every layout check
    would drag along a PATH failure and mask what it is actually asserting."""
    root = _make_bundle(tmp_path)
    monkeypatch.setattr(preflight_cloud, "CLOUD_PREFIX", tmp_path)
    return root


def test_layout_passes_on_a_well_formed_bundle(bundle):
    assert preflight_cloud.check_layout(bundle) == []


def test_layout_reports_a_bundle_outside_the_cloud_prefix(tmp_path):
    """The deploy's central gotcha: is_cloud() is path-based, so a bundle
    unpacked anywhere else still serves HTTP 200 -- with auth off, no SPA and
    mock data. Nothing else in the checker catches this."""
    root = _make_bundle(tmp_path)

    failures = preflight_cloud.check_layout(root)

    assert any(str(preflight_cloud.CLOUD_PREFIX) in f for f in failures)


def test_layout_reports_missing_spa(bundle):
    (bundle / "front-dev-home" / ".output" / "public" / "index.html").unlink()

    failures = preflight_cloud.check_layout(bundle)

    assert any("index.html" in f for f in failures)


def test_layout_reports_broken_depth_invariant(bundle):
    """env.py must sit exactly 2 levels below the root or spa_dir() misses."""
    root = bundle
    nested = root / "extra" / "back_dev_home" / "_runtime"
    nested.mkdir(parents=True)
    nested.joinpath("env.py").write_text("")
    (root / "back_dev_home" / "_runtime" / "env.py").unlink()

    failures = preflight_cloud.check_layout(root)

    assert any("env.py" in f for f in failures)


def test_imports_report_missing_package_by_pip_name(monkeypatch):
    monkeypatch.setattr(
        preflight_cloud, "RUNTIME_PACKAGES", (("definitely_not_installed", "some-pip-name"),)
    )

    failures, _notes = preflight_cloud.check_imports()

    assert any("some-pip-name" in f for f in failures)


def test_imports_accept_either_hcputil_spelling(monkeypatch):
    monkeypatch.setattr(preflight_cloud, "RUNTIME_PACKAGES", ())
    pkg = types.ModuleType("hcputil")
    pkg.__path__ = []
    sub = types.ModuleType("hcputil.auto")
    sub.__path__ = []
    sso = types.ModuleType("hcputil.auto.sso")
    sso.SSO = object
    monkeypatch.setitem(sys.modules, "hcputil", pkg)
    monkeypatch.setitem(sys.modules, "hcputil.auto", sub)
    monkeypatch.setitem(sys.modules, "hcputil.auto.sso", sso)

    failures, notes = preflight_cloud.check_imports()

    assert failures == []
    assert any("hcputil.auto.sso" in n for n in notes)


def test_config_warns_on_default_secret_key(bundle):
    root = bundle
    (root / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=dev-only-not-for-prod\n"
    )

    failures, warnings = preflight_cloud.check_config(root)

    assert failures == []
    assert any("SKEWNONO_SECRET_KEY" in w for w in warnings)


def test_config_fails_when_env_missing(bundle):
    root = bundle
    (root / "back_dev_home" / ".env").unlink()

    failures, _warnings = preflight_cloud.check_config(root)

    assert any(".env" in f for f in failures)
