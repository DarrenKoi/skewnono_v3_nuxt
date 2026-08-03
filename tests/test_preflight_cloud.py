"""The cloud preflight checker must degrade to a report, never an exception.

Its whole job is to run on a host where things are broken, so any check that
raises instead of returning a failure string is a bug.
"""

import re
from pathlib import Path

import pytest

from scripts.deploy import preflight_cloud

REPO_ROOT = Path(__file__).resolve().parents[1]


# Everything check_config() insists on, so a test that varies one setting can
# write only that setting's line and still describe a deployable host.
LOGGING_ENV_LINES = "SKEWNONO_LOG_ENV=production\nOPENSEARCH_PASSWORD=real-password\n"
HEALTHY_ENV = "SKEWNONO_SECRET_KEY=real-key\n" + LOGGING_ENV_LINES


def _make_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    (root / "back_dev_home" / "_runtime").mkdir(parents=True)
    (root / "back_dev_home" / "_runtime" / "env.py").write_text("")
    (root / "front-dev-home" / ".output" / "public").mkdir(parents=True)
    (root / "front-dev-home" / ".output" / "public" / "index.html").write_text("<!doctype html>")
    (root / "back_dev_home" / ".env").write_text(HEALTHY_ENV)
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


def test_config_treats_an_unreadable_env_as_not_its_call(bundle):
    """Degrade to a report, and do not guess: an undecodable .env is a
    different failure that load_dotenv surfaces at boot. The checker must
    neither crash on it nor manufacture a SKEWNONO_SECRET_KEY verdict from a
    file it could not read."""
    env_path = bundle / "back_dev_home" / ".env"
    env_path.write_bytes(b"\xff")

    assert preflight_cloud.check_config(bundle) == ([], [])


def test_config_fails_when_env_missing(bundle):
    root = bundle
    (root / "back_dev_home" / ".env").unlink()

    failures, _warnings = preflight_cloud.check_config(root)

    assert any(".env" in f for f in failures)


def test_config_passes_when_a_secret_key_is_chosen(bundle):
    """The bundle fixture's .env carries a real key — the deploy happy path."""
    assert preflight_cloud.check_config(bundle) == ([], [])


@pytest.mark.parametrize(
    "env_body",
    [
        "REDIS_HOST=redis.example\n",
        "SKEWNONO_SECRET_KEY=\n",
        "SKEWNONO_SECRET_KEY=   \n",
        'SKEWNONO_SECRET_KEY=""\n',
        "SKEWNONO_SECRET_KEY= # choose one\n",
    ],
)
def test_config_fails_when_the_secret_key_is_missing_or_blank(bundle, env_body):
    """create_app() treats a blank as absent and refuses to start on the
    cloud; a preflight that disagrees passes a bundle uwsgi will boot-loop on,
    with the reason visible only in uwsgi logs."""
    (bundle / "back_dev_home" / ".env").write_text(LOGGING_ENV_LINES + env_body)

    failures, _warnings = preflight_cloud.check_config(bundle)

    assert any("SKEWNONO_SECRET_KEY" in f for f in failures)


@pytest.mark.parametrize(
    "env_body",
    [
        "export SKEWNONO_SECRET_KEY=chosen\n",
        "SKEWNONO_SECRET_KEY='chosen'\n",
        "OTHER=1\nSKEWNONO_SECRET_KEY=chosen\n",
    ],
)
def test_config_accepts_the_dotenv_spellings_load_dotenv_accepts(bundle, env_body):
    """False FAILs erode trust in the checker: every spelling python-dotenv
    would load as a non-blank key must pass here too."""
    (bundle / "back_dev_home" / ".env").write_text(LOGGING_ENV_LINES + env_body)

    assert preflight_cloud.check_config(bundle) == ([], [])


def test_config_fails_when_the_logging_target_is_the_office_local_alias(bundle):
    """The 2026-08-03 cloud deploy: a valid value pointed at the wrong alias.

    Nothing downstream can catch this -- the shipper installs, indexes happily
    into `skewnono_logging_local`, and /admin-logs reads that same alias back,
    so the app looks healthy while the production index stays empty.
    """
    (bundle / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=real-key\n"
        "SKEWNONO_LOG_ENV=local\n"
        "OPENSEARCH_PASSWORD=real-password\n"
    )

    failures, _warnings = preflight_cloud.check_config(bundle)

    assert any("SKEWNONO_LOG_ENV" in f and "production" in f for f in failures)


def test_config_fails_when_the_logging_target_is_unset_but_reachable(bundle):
    """OPENSEARCH_PASSWORD set + SKEWNONO_LOG_ENV unset is the boot-loop combo:
    install_opensearch_logging() clears its own guards and then
    resolve_logging_target() raises inside create_app()."""
    (bundle / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=real-key\nOPENSEARCH_PASSWORD=real-password\n"
    )

    failures, _warnings = preflight_cloud.check_config(bundle)

    assert any("SKEWNONO_LOG_ENV" in f for f in failures)


def test_config_fails_when_the_logging_target_is_not_a_known_environment(bundle):
    (bundle / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=real-key\nSKEWNONO_LOG_ENV=prod\n"
    )

    failures, _warnings = preflight_cloud.check_config(bundle)

    assert any("SKEWNONO_LOG_ENV" in f for f in failures)


def test_config_only_warns_about_a_deploy_that_ships_no_logs(bundle):
    """No target and no credentials is a coherent choice -- logging off. It
    still deserves a line, because the alternative reading is that someone
    forgot, and /admin-logs will be empty either way."""
    (bundle / "back_dev_home" / ".env").write_text("SKEWNONO_SECRET_KEY=real-key\n")

    failures, warnings = preflight_cloud.check_config(bundle)

    assert failures == []
    assert any("SKEWNONO_LOG_ENV" in w for w in warnings)


def test_config_warns_when_the_named_target_has_no_credentials(bundle):
    """SKEWNONO_LOG_ENV=production alone reads as "logging is configured", but
    the handler is skipped without a password and the alias stays empty."""
    (bundle / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=real-key\nSKEWNONO_LOG_ENV=production\n"
    )

    failures, warnings = preflight_cloud.check_config(bundle)

    assert failures == []
    assert any("OPENSEARCH_PASSWORD" in w for w in warnings)


@pytest.mark.parametrize("raw", ["true", "TRUE", "1", "yes"])
def test_config_warns_while_the_write_kill_switch_is_on(bundle, raw):
    """An emergency switch that outlives the emergency is a silent outage."""
    (bundle / "back_dev_home" / ".env").write_text(
        HEALTHY_ENV + f"OPENSEARCH_LOGGING_DISABLED={raw}\n"
    )

    failures, warnings = preflight_cloud.check_config(bundle)

    assert failures == []
    assert any("OPENSEARCH_LOGGING_DISABLED" in w for w in warnings)


def test_config_accepts_the_logging_target_values_the_app_accepts():
    """Preflight's notion of a valid target must not drift from the app's."""
    from back_dev_home._logging.target import _TARGETS

    source = Path(preflight_cloud.__file__).read_text(encoding="utf-8")

    assert set(_TARGETS) == {"local", "production"}
    for environment in _TARGETS:
        assert f'"{environment}"' in source or f"'{environment}'" in source


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


def test_versions_pass_when_the_installed_release_clears_the_floor(bundle):
    (bundle / "back_dev_home" / "requirements.txt").write_text("pytest>=1\n")

    failures, notes = preflight_cloud.check_versions(bundle)

    assert failures == []
    assert notes == []


def test_versions_report_a_preinstalled_package_below_the_floor(bundle):
    """The cloud image ships its own copies, and `pip install -r` upgrades one
    only when a specifier we wrote down excludes it. This check is what turns
    'the install quietly did nothing' into a line the operator can act on."""
    (bundle / "back_dev_home" / "requirements.txt").write_text("pytest>=9999\n")

    failures, _notes = preflight_cloud.check_versions(bundle)

    assert len(failures) == 1
    assert "pytest" in failures[0]
    assert ">=9999" in failures[0]
    assert "pip install -r" in failures[0]


def test_versions_name_the_numpy_symptom_not_just_the_number(bundle):
    """A bare '2.5.0 does not satisfy >=9999' tells an operator nothing about
    why they should care. numpy's violation surfaces as a MinIO traceback hours
    later, so the remedy line has to carry the symptom."""
    (bundle / "back_dev_home" / "requirements.txt").write_text("numpy>=9999\n")

    failures, _notes = preflight_cloud.check_versions(bundle)

    assert len(failures) == 1
    assert "numpy._core" in failures[0]
    assert "get_pickle" in failures[0]


def test_versions_stay_silent_about_a_package_that_is_not_installed(bundle):
    """check_imports() owns absence. Reporting it twice, under two different
    remedies, sends the operator looking for a version problem that is really a
    missing install."""
    (bundle / "back_dev_home" / "requirements.txt").write_text("definitely-not-installed>=5\n")

    failures, _notes = preflight_cloud.check_versions(bundle)

    assert failures == []


def test_versions_degrade_to_a_note_when_requirements_are_unreadable(bundle):
    (bundle / "back_dev_home" / "requirements.txt").write_bytes(b"\xff")

    failures, notes = preflight_cloud.check_versions(bundle)

    assert failures == []
    assert any("unverified" in note for note in notes)


@pytest.mark.parametrize(
    ("installed", "op", "required", "expected"),
    [
        ("2.5.0", ">=", "2", True),
        ("1.26.4", ">=", "2", False),
        ("2.2.2", ">=", "2.2.2", True),
        ("2.2.0", ">=", "2.2.2", False),
        ("2.10.0", ">=", "2.9", True),  # not a string comparison
        ("3.0.0", "<", "3", False),
        ("2.9.9", "<", "3", True),
        ("2.0.0rc1", ">=", "2", True),  # pre-release reads as its base version
    ],
)
def test_version_comparison_handles_the_forms_requirements_txt_uses(
    installed, op, required, expected
):
    assert preflight_cloud._satisfies(installed, (op, required)) is expected


def test_requirements_parser_keeps_both_halves_of_a_bounded_range():
    parsed = dict(preflight_cloud._parse_requirements("opensearch-py>=2,<3\n# comment\n\n"))

    assert parsed["opensearch-py"] == [(">=", "2"), ("<", "3")]


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
