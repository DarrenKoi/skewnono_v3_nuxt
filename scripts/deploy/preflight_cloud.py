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
            "is_cloud() will be False: no SPA mount, mock data, and — worst — "
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


def check_config(root: Path) -> tuple[list[str], list[str]]:
    """Check that Flask's environment file exists and chooses a secret key.

    The file's other contents stay uninspected — preflight has no standing to
    judge them — but SKEWNONO_SECRET_KEY decides whether create_app() raises
    on the cloud, and a preflight that passes while uwsgi boot-loops (reason
    visible only in uwsgi logs) is the silent-blank-window failure this script
    exists to prevent. Same rule as create_app(): blank counts as absent.
    """
    env_path = root / "back_dev_home" / ".env"
    if not env_path.is_file():
        return (
            [
                f"MISSING {env_path} — create_app() calls load_dotenv on this path; "
                "without it the app boots unconfigured."
            ],
            [],
        )
    if not _env_file_chooses_secret_key(env_path):
        return (
            [
                f"SKEWNONO_SECRET_KEY not set in {env_path} — create_app() refuses "
                "to start on the cloud without it (it signs the "
                "self-identification session). Set any non-empty value."
            ],
            [],
        )
    return [], []


def _env_file_chooses_secret_key(env_path: Path) -> bool:
    """Whether the .env assigns SKEWNONO_SECRET_KEY a non-blank value.

    A hand-rolled scan rather than python-dotenv: this script may only import
    what the cloud image alone supplies, and it must degrade to a report on a
    broken host — an unreadable file is a different failure that load_dotenv
    will surface at boot, so it is not this check's call to guess at.
    """
    try:
        text = env_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return True
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        if name.strip() != "SKEWNONO_SECRET_KEY" or not sep:
            continue
        value = value.strip()
        if value[:1] in {"'", '"'} and len(value) >= 2 and value[-1:] == value[:1]:
            value = value[1:-1]  # quoted: keep content verbatim, as dotenv does
        else:
            value = value.split("#", 1)[0]  # unquoted: drop an inline comment
        if value.strip():
            return True
    return False


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
