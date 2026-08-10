"""Will this bundle boot? Run this on the cloud host BEFORE starting uwsgi.

`wsgi.ini` sets `need-app = true`, so every boot problem surfaces as a uwsgi
crash log - a poor diagnostic on a host with a slow iteration loop. This
script turns each of those failures into one line naming the remedy.

Run it TWICE:

    cd /project/workSpace
    python preflight.py                                  # before pip install
    pip install -r back_dev_home/requirements.txt
    python preflight.py                                  # after

The first pass proves the transfer landed at the right path with the right
layout - the failure with the most confusing symptoms, because the app still
returns HTTP 200 while silently running with auth off, no SPA, and mock data.
The second proves the dependency install completed.

STDLIB ONLY. This must run before `pip install` succeeds, or it cannot report
which packages are missing.
"""

import argparse
import importlib
import re
import sys
from importlib import metadata
from pathlib import Path

CLOUD_PREFIX = Path("/project/workSpace")

# (import name, pip name) - the two differ often enough to be worth pairing,
# because the remedy the operator needs is the pip name.
RUNTIME_PACKAGES = (
    ("flask", "Flask"),
    ("flask_cors", "flask-cors"),
    ("flask_limiter", "flask-limiter"),
    ("pandas", "pandas"),
    ("pyarrow", "pyarrow"),
    ("numpy", "numpy"),
    ("redis", "redis"),
    ("minio", "minio"),
    ("PIL", "Pillow"),
    ("opensearchpy", "opensearch-py"),
    ("apscheduler", "apscheduler"),
    ("dotenv", "python-dotenv"),
    ("httpx", "httpx"),
    ("requests", "requests"),
    ("langchain", "langchain"),
    ("langgraph", "langgraph"),
    ("langchain_openai", "langchain-openai"),
)

def check_layout(root: Path) -> list[str]:
    """Structural checks. Depth matters as much as presence."""
    failures = []

    env_py = root / "back_dev_home" / "_runtime" / "env.py"
    if not env_py.is_file():
        failures.append(
            f"MISSING {env_py} - back_dev_home/ did not survive the transfer."
        )
    elif env_py.resolve().parents[2] != root.resolve():
        # spa_dir() is parents[2] / front-dev-home / .output / public.
        failures.append(
            f"DEPTH {env_py} is not exactly 2 levels below {root}; "
            "spa_dir() will resolve to the wrong place and the UI will 404."
        )

    index_html = root / "front-dev-home" / ".output" / "public" / "index.html"
    if not index_html.is_file():
        failures.append(
            f"MISSING {index_html} - the SPA is absent; every page returns 404."
        )

    for name in ("index.py", "wsgi.ini"):
        if not (root / name).is_file():
            failures.append(f"MISSING {root / name}")

    if not root.resolve().is_relative_to(CLOUD_PREFIX):
        failures.append(
            f"PATH bundle is at {root.resolve()}, not under {CLOUD_PREFIX}. "
            "is_cloud() will be False: no SPA mount, mock data, and - worst - "
            "the LOCAL identity provider, which falls back to the admin id "
            "'local-dev' for any caller with no LASTUSER cookie. "
            f"Move the bundle so it sits under {CLOUD_PREFIX}."
        )

    return failures


def check_imports() -> tuple[list[str], list[str]]:
    """Returns (failures, notes)."""
    failures = []
    notes = []

    for import_name, pip_name in RUNTIME_PACKAGES:
        try:
            importlib.import_module(import_name)
        except ImportError as exc:
            failures.append(
                f"IMPORT {import_name} unavailable ({exc}); "
                f"run: pip install -r back_dev_home/requirements.txt  [{pip_name}]"
            )

    notes.append("identity: LASTUSER cookie (no cloud-image SSO module needed)")

    return failures, notes


# Symptom hints for floors whose violation is undiagnosable from the version
# number alone. Keyed by pip name; only worth an entry when the package imports
# fine at the wrong version and fails much later, somewhere unrelated-looking.
VERSION_SYMPTOMS = {
    "numpy": (
        "MinIO pickles are written upstream on numpy 2 and name `numpy._core`, "
        "absent in numpy 1: msr_file's get_pickle() raises ModuleNotFoundError "
        "at the first /api/msr-file request, in a traceback that reads as a "
        "MinIO fault."
    ),
}


def check_versions(root: Path) -> tuple[list[str], list[str]]:
    """Do the INSTALLED versions satisfy requirements.txt? Returns (failures, notes).

    The cloud image preinstalls part of our dependency set, and `pip install -r`
    upgrades a preinstalled package only when its version violates a specifier
    we actually wrote down. So every floor that matters has to be declared -
    and then verified here, because the install can still be defeated: an
    offline mirror without the release, a permission error on a root-owned
    site-packages, or a system copy shadowing the venv on sys.path. All three
    leave `import` working and the version wrong, which check_imports() passes.

    Deliberately no `packaging` dependency: this runs before pip install.
    """
    failures: list[str] = []
    notes: list[str] = []

    requirements = root / "back_dev_home" / "requirements.txt"
    try:
        body = requirements.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # The import loop still covers presence; the bundle-layout check owns
        # the verdict on a requirements.txt that did not survive transfer.
        return [], [f"could not read {requirements}; version floors unverified"]

    for pip_name, constraints in _parse_requirements(body):
        installed = _installed_version(pip_name)
        if installed is None:
            continue  # absent - check_imports() already names it

        unmet = [c for c in constraints if not _satisfies(installed, c)]
        if not unmet:
            continue

        detail = f"{pip_name} {installed}"
        location = _installed_location(pip_name)
        if location:
            detail += f" at {location}"
        message = (
            f"VERSION {detail} does not satisfy "
            f"{','.join(op + ver for op, ver in unmet)}; "
            "run: pip install -r back_dev_home/requirements.txt"
        )
        symptom = VERSION_SYMPTOMS.get(pip_name)
        if symptom:
            message += f" - {symptom}"
        failures.append(message)

    return failures, notes


def _parse_requirements(body: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """`name>=1,<2` -> ("name", [(">=", "1"), ("<", "2")]). Comments dropped.

    Handles only what our requirements.txt uses. An unrecognized line yields no
    constraints rather than a parse error: preflight reporting a bogus version
    failure would be worse than it reporting none.
    """
    parsed = []
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z0-9._-]+)\s*(.*)$", line)
        if not match:
            continue
        name, tail = match.group(1), match.group(2)
        constraints = [
            (op, ver.strip())
            for op, ver in re.findall(r"(>=|<=|==|>|<|!=)\s*([^,\s]+)", tail)
        ]
        parsed.append((name, constraints))
    return parsed


def _installed_version(pip_name: str) -> str | None:
    try:
        return metadata.version(pip_name)
    except metadata.PackageNotFoundError:
        return None


def _installed_location(pip_name: str) -> str | None:
    """Where the distribution actually lives - the tell for a shadowing copy."""
    try:
        return str(metadata.distribution(pip_name).locate_file(""))
    except Exception:
        return None


def _version_tuple(version: str) -> tuple[int, ...]:
    """`2.5.0` -> (2, 5, 0). Trailing non-digits are dropped per component, so
    a pre-release like `2.0.0rc1` reads as (2, 0, 0) - close enough to compare
    against an integer floor, and never the reason a deploy is blocked."""
    parts = []
    for component in re.split(r"[.\-_+]", version):
        digits = re.match(r"\d+", component)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts)


def _satisfies(installed: str, constraint: tuple[str, str]) -> bool:
    op, required = constraint
    left = _version_tuple(installed)
    right = _version_tuple(required)
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))

    if op == ">=":
        return left >= right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == "<":
        return left < right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    return True  # unknown operator: not preflight's call


def check_config(root: Path) -> tuple[list[str], list[str]]:
    """Check the .env settings that decide the deploy. Returns (failures, warnings).

    Most of the file stays uninspected - preflight has no standing to judge it
    - but two settings are checkable here and undiagnosable later:

    * SKEWNONO_SECRET_KEY decides whether create_app() raises on the cloud, and
      a preflight that passes while uwsgi boot-loops (reason visible only in
      uwsgi logs) is the silent-blank-window failure this script exists to
      prevent. Same rule as create_app(): blank counts as absent.
    * SKEWNONO_LOG_ENV decides WHICH logging alias this host writes - see
      _check_logging_target for why a valid value can still be a deploy bug.
    """
    env_path = root / "back_dev_home" / ".env"
    if not env_path.is_file():
        return (
            [
                f"MISSING {env_path} - create_app() calls load_dotenv on this path; "
                "without it the app boots unconfigured."
            ],
            [],
        )

    values = env_file_values(env_path)
    if values is None:
        return [], []

    failures = []
    if not values.get("SKEWNONO_SECRET_KEY", ""):
        failures.append(
            f"SKEWNONO_SECRET_KEY not set in {env_path} - create_app() refuses "
            "to start on the cloud without it (it signs the "
            "self-identification session). Set any non-empty value."
        )

    log_failures, warnings = _check_logging_target(values, env_path)
    return failures + log_failures, warnings


def _check_logging_target(
    values: dict[str, str],
    env_path: Path,
) -> tuple[list[str], list[str]]:
    """Does this host ship activity to the PRODUCTION logging alias?

    The failure this exists for is not a crash. `SKEWNONO_LOG_ENV=local` is a
    perfectly valid value, so resolve_logging_target() accepts it, the shipper
    installs, and every request is indexed - into `skewnono_logging_local`.
    The production alias just stays empty, /admin-logs reads the local one
    back, and nothing anywhere reports a problem. That cost a cloud deploy's
    activity history on 2026-08-03, and no amount of documentation would have
    caught it, because a correct-looking .env is exactly the symptom.

    `local` is only ever right on an office PC, and this script only ever runs
    on the cloud host, so here it is unambiguously wrong. The two aliases also
    carry different ISM retention (office-local diagnostics vs. 365-day
    production activity), so misfiled documents are deleted early too.
    """
    failures: list[str] = []
    warnings: list[str] = []

    log_env = values.get("SKEWNONO_LOG_ENV", "")
    password = values.get("OPENSEARCH_PASSWORD", "")
    disabled = values.get("OPENSEARCH_LOGGING_DISABLED", "").lower() in {
        "1",
        "true",
        "yes",
    }

    if log_env == "local":
        failures.append(
            f"SKEWNONO_LOG_ENV=local in {env_path} - that is the office-PC "
            "target. Activity would land in the `skewnono_logging_local` alias "
            "(shorter ISM retention), production `skewnono_logging` would stay "
            "empty, and /admin-logs would read the local alias back, so nothing "
            "surfaces the mistake. Set SKEWNONO_LOG_ENV=production."
        )
    elif log_env and log_env != "production":
        failures.append(
            f"SKEWNONO_LOG_ENV={log_env!r} in {env_path} is neither 'local' nor "
            "'production' - resolve_logging_target() raises "
            "LoggingConfigurationError inside create_app() and uwsgi boot-loops. "
            "Set SKEWNONO_LOG_ENV=production."
        )
    elif not log_env and password:
        failures.append(
            f"SKEWNONO_LOG_ENV not set in {env_path} while OPENSEARCH_PASSWORD is "
            "- install_opensearch_logging() gets that far and then raises "
            "LoggingConfigurationError, so create_app() dies at boot. "
            "Set SKEWNONO_LOG_ENV=production."
        )
    elif not log_env:
        warnings.append(
            f"SKEWNONO_LOG_ENV not set in {env_path}: no OpenSearch logging, and "
            "nothing for /admin-logs to read. Correct only if this deploy is "
            "meant to run without activity logging."
        )

    if log_env == "production" and not password:
        warnings.append(
            f"OPENSEARCH_PASSWORD not set in {env_path}: install_opensearch_logging() "
            "skips the handler with one stderr line, so `skewnono_logging` stays "
            "empty even though SKEWNONO_LOG_ENV names it."
        )

    if disabled:
        warnings.append(
            f"OPENSEARCH_LOGGING_DISABLED is on in {env_path} - the write kill "
            "switch. Activity is dropped for as long as it stays set."
        )

    return failures, warnings


def env_file_values(env_path: Path) -> dict[str, str] | None:
    """The .env's assignments, or None when the file could not be read.

    A hand-rolled scan rather than python-dotenv: this script may only import
    what the cloud image alone supplies, and it must degrade to a report on a
    broken host - an unreadable file is a different failure that load_dotenv
    will surface at boot, so it is not this check's call to guess at. Hence
    None rather than an empty dict, which would read as "nothing is set" and
    manufacture verdicts about a file nobody managed to read.

    Values come back stripped, so "blank counts as absent" is a falsy check at
    every call site. Later assignments win, as they do in dotenv.

    Public because pack.py reads the same file at the office, one step before
    this script sees it on the cloud. A second copy of this parser would be a
    second thing to keep in step with dotenv's spellings.
    """
    try:
        text = env_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        name = name.strip()
        if not sep or not name or name.startswith("#"):
            continue
        value = value.strip()
        if value[:1] in {"'", '"'} and len(value) >= 2 and value[-1:] == value[:1]:
            value = value[1:-1]  # quoted: keep content verbatim, as dotenv does
        else:
            value = value.split("#", 1)[0]  # unquoted: drop an inline comment
        values[name] = value.strip()
    return values


def _adapter_roster(root: Path) -> list[str]:
    backend = root / "back_dev_home"
    if not backend.is_dir():
        return []
    return sorted(
        str(p.relative_to(backend).parent.parent)
        for p in backend.rglob("providers/office.py")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether this bundle will boot on the cloud host."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Bundle root (default: this file's directory).",
    )
    args = parser.parse_args(argv)
    root = args.root

    print(f"SKEWNONO cloud preflight - {root}\n")

    failures = check_layout(root)
    import_failures, notes = check_imports()
    failures += import_failures
    version_failures, version_notes = check_versions(root)
    failures += version_failures
    config_failures, warnings = check_config(root)
    failures += config_failures
    warnings += version_notes

    for note in notes:
        print(f"  ok   {note}")

    roster = _adapter_roster(root)
    if roster:
        print(f"  ok   {len(roster)} office adapter(s): {', '.join(roster)}")
    else:
        warnings.append(
            "No providers/office.py found - every feature will serve mock data."
        )

    # recipe open imports the 사내 IDP parser lazily, so its absence never
    # fails boot or preflight imports - it surfaces as a 500 on the first
    # recipe-open request. Warn rather than fail: only that feature needs it.
    if not (root / "office_utils" / "read_idp_info.py").is_file():
        warnings.append(
            f"{root / 'office_utils' / 'read_idp_info.py'} missing - recipe "
            "open will fail at the parse step (the FTP fetch succeeds, then "
            "combined_idp_info is unimportable). Re-pack with an office_utils/ "
            "at the repo root, or copy the folder onto the host."
        )

    for warning in warnings:
        print(f"  WARN {warning}")

    if not failures:
        print("\nPASS - uwsgi should start. Next: uwsgi --ini wsgi.ini")
        return 0

    print("")
    for failure in failures:
        print(f"  FAIL {failure}")
    print(f"\nFAIL - {len(failures)} blocking problem(s). Do not start uwsgi yet.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
