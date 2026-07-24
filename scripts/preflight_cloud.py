"""Will this bundle boot? Run this on the cloud host BEFORE starting uwsgi.

`wsgi.ini` sets `need-app = true`, so every boot problem surfaces as a uwsgi
crash log — a poor diagnostic on a host with a slow iteration loop. This
script turns each of those failures into one line naming the remedy.

Run it TWICE:

    cd /project/workSpace
    python preflight.py                                  # before pip install
    pip install -r back_dev_home/requirements.txt
    python preflight.py                                  # after

The first pass proves the transfer landed at the right path with the right
layout — the failure with the most confusing symptoms, because the app still
returns HTTP 200 while silently running with auth off, no SPA, and mock data.
The second proves the dependency install completed.

STDLIB ONLY. This must run before `pip install` succeeds, or it cannot report
which packages are missing.
"""

import argparse
import importlib
import sys
from pathlib import Path

CLOUD_PREFIX = Path("/project/workSpace")
DEFAULT_SECRET_KEY = "dev-only-not-for-prod"

# (import name, pip name) — the two differ often enough to be worth pairing,
# because the remedy the operator needs is the pip name.
RUNTIME_PACKAGES = (
    ("flask", "Flask"),
    ("flask_cors", "flask-cors"),
    ("flask_limiter", "flask-limiter"),
    ("pandas", "pandas"),
    ("pyarrow", "pyarrow"),
    ("redis", "redis"),
    ("minio", "minio"),
    ("opensearchpy", "opensearch-py"),
    ("apscheduler", "apscheduler"),
    ("dotenv", "python-dotenv"),
)

# The cloud image supplies these; requirements.txt deliberately does not.
HCPUTIL_PATHS = ("hcputil.auth.sso", "hcputil.auto.sso")


def check_layout(root: Path) -> list[str]:
    """Structural checks. Depth matters as much as presence."""
    failures = []

    env_py = root / "back_dev_home" / "_runtime" / "env.py"
    if not env_py.is_file():
        failures.append(
            f"MISSING {env_py} — back_dev_home/ did not survive the transfer."
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
            f"MISSING {index_html} — the SPA is absent; every page returns 404."
        )

    for name in ("index.py", "wsgi.ini"):
        if not (root / name).is_file():
            failures.append(f"MISSING {root / name}")

    if not root.resolve().is_relative_to(CLOUD_PREFIX):
        failures.append(
            f"PATH bundle is at {root.resolve()}, not under {CLOUD_PREFIX}. "
            "is_cloud() will be False: no SSO auth, no SPA mount, mock data. "
            f"Move the bundle so it sits under {CLOUD_PREFIX}."
        )

    return failures


def check_imports() -> tuple[list[str], list[str]]:
    """Returns (failures, notes). Notes record which hcputil spelling worked."""
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

    for module_path in HCPUTIL_PATHS:
        try:
            importlib.import_module(module_path)
        except ImportError:
            continue
        notes.append(f"hcputil resolved as {module_path}")
        break
    else:
        failures.append(
            "IMPORT hcputil SSO unavailable; tried "
            + " and ".join(HCPUTIL_PATHS)
            + ". This is supplied by the cloud image, NOT by requirements.txt. "
            "Without it create_app() raises and uwsgi refuses to start."
        )

    return failures, notes


def _parse_env(text: str) -> dict[str, str]:
    """Minimal .env reader — python-dotenv may not be installed yet."""
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def check_config(root: Path) -> tuple[list[str], list[str]]:
    """Returns (failures, warnings)."""
    failures = []
    warnings = []

    env_path = root / "back_dev_home" / ".env"
    if not env_path.is_file():
        failures.append(
            f"MISSING {env_path} — create_app() calls load_dotenv on this path; "
            "without it the app boots unconfigured."
        )
        return failures, warnings

    try:
        values = _parse_env(env_path.read_text(encoding="utf-8"))
    except OSError as exc:
        failures.append(f"UNREADABLE {env_path}: {exc}")
        return failures, warnings

    secret = values.get("SKEWNONO_SECRET_KEY", "")
    if not secret or secret == DEFAULT_SECRET_KEY:
        warnings.append(
            "SKEWNONO_SECRET_KEY is unset or still the default "
            f"({DEFAULT_SECRET_KEY!r}); sessions are signed with a known key. "
            "Acceptable for a feasibility deploy, not for skewnono.skhynix.com."
        )

    return failures, warnings


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

    print(f"SKEWNONO cloud preflight — {root}\n")

    failures = check_layout(root)
    import_failures, notes = check_imports()
    failures += import_failures
    config_failures, warnings = check_config(root)
    failures += config_failures

    for note in notes:
        print(f"  ok   {note}")

    roster = _adapter_roster(root)
    if roster:
        print(f"  ok   {len(roster)} office adapter(s): {', '.join(roster)}")
    else:
        warnings.append(
            "No providers/office.py found — every feature will serve mock data."
        )

    for warning in warnings:
        print(f"  WARN {warning}")

    if not failures:
        print("\nPASS — uwsgi should start. Next: uwsgi --ini wsgi.ini")
        return 0

    print("")
    for failure in failures:
        print(f"  FAIL {failure}")
    print(f"\nFAIL — {len(failures)} blocking problem(s). Do not start uwsgi yet.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
