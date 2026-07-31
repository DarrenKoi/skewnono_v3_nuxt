"""The cloud preflight checker must degrade to a report, never an exception.

Its whole job is to run on a host where things are broken, so any check that
raises instead of returning a failure string is a bug.
"""

import re
from pathlib import Path

import pytest

from scripts.deploy import preflight_cloud

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_imports_need_nothing_the_cloud_image_alone_supplies(monkeypatch):
    """Preflight used to fail the deploy unless `hcputil.auth.sso` imported.

    Identity is now the LASTUSER cookie, so every runtime import comes from
    requirements.txt and a host that installed them passes. Keeping the old
    gate would block a deploy that is in fact complete.
    """
    monkeypatch.setattr(preflight_cloud, "RUNTIME_PACKAGES", ())

    failures, notes = preflight_cloud.check_imports()

    assert failures == []
    assert any("LASTUSER" in note for note in notes)


def test_no_check_reaches_for_a_cloud_image_module():
    """The bundle must be verifiable from its own contents. An import probe for
    a module only the cloud image provides cannot be reproduced anywhere the
    deploy is prepared, so a failure there is undiagnosable before transfer."""
    source = Path(preflight_cloud.__file__).read_text(encoding="utf-8")

    assert "hcputil" not in source


def test_config_does_not_read_env_contents(bundle):
    env_path = bundle / "back_dev_home" / ".env"
    env_path.write_bytes(b"\xff")

    assert preflight_cloud.check_config(bundle) == ([], [])


def test_config_fails_when_env_missing(bundle):
    root = bundle
    (root / "back_dev_home" / ".env").unlink()

    failures, _warnings = preflight_cloud.check_config(root)

    assert any(".env" in f for f in failures)


def _requirement_names(text: str) -> set[str]:
    """PEP 503-normalized distribution names from a requirements.txt body."""
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~;\[]", line, maxsplit=1)[0].strip()
        if name:
            names.add(re.sub(r"[-_.]+", "-", name).lower())
    return names


def test_every_declared_dependency_is_preflight_checked():
    """The whole point of check_imports() is to catch a missing dependency on
    the cloud host BEFORE uwsgi crashes on it. A package that requirements.txt
    installs but RUNTIME_PACKAGES omits is invisible to that check: preflight
    reports PASS and the app then dies at request time on the one code path
    that imports it.

    Pinning the containment here rather than adding literals to the tuple
    means a future requirements.txt entry cannot silently reopen the gap.
    """
    reqs = REPO_ROOT / "back_dev_home" / "requirements.txt"
    declared = _requirement_names(reqs.read_text(encoding="utf-8"))
    checked = {
        re.sub(r"[-_.]+", "-", pip_name).lower()
        for _import_name, pip_name in preflight_cloud.RUNTIME_PACKAGES
    }

    assert declared <= checked, (
        "declared in requirements.txt but not checked by preflight: "
        f"{sorted(declared - checked)}"
    )


def test_preflight_checked_packages_are_all_declared():
    """The converse: a RUNTIME_PACKAGES entry with no requirements.txt line
    tells the operator to `pip install -r requirements.txt` to fix an import
    that command will never fix."""
    reqs = REPO_ROOT / "back_dev_home" / "requirements.txt"
    declared = _requirement_names(reqs.read_text(encoding="utf-8"))
    checked = {
        re.sub(r"[-_.]+", "-", pip_name).lower()
        for _import_name, pip_name in preflight_cloud.RUNTIME_PACKAGES
    }

    assert checked <= declared, (
        "checked by preflight but absent from requirements.txt: "
        f"{sorted(checked - declared)}"
    )
