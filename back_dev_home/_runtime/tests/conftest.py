"""Shared fixtures for the provider-resolution tests.

Every one of these tests needs the same two things: an environment with no
real provider config leaking in from .env, and a fake package tree standing in
for the repo. office.py is gitignored, so which adapters exist is a property
of the machine running the tests — this Mac mini carries six written while
developing them, and the office has a different set. Only a fixed tree can
assert exact resolution.
"""

import os

import pytest

from back_dev_home._runtime import office_registry


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Neutralize any real provider/site config leaking in from .env.

    validate_env() scans EVERY SKEWNONO_*_PROVIDER variable, so a hardcoded
    delenv list would let one stray office line in .env fail unrelated tests.
    Strip them all instead; this also covers SKEWNONO_DATA_PROVIDER.
    """
    monkeypatch.delenv("SKEWNONO_SITE", raising=False)
    monkeypatch.delenv("SKEWNONO_OFFICE_HOSTNAMES", raising=False)
    for name in list(os.environ):
        if name.startswith("SKEWNONO_") and name.endswith("_PROVIDER"):
            monkeypatch.delenv(name)


@pytest.fixture
def fake_tree(tmp_path, monkeypatch):
    """Factory: build back_dev_home/<path>/{routes.py,providers/<files>} and aim _ROOT at it.

    Every entry gets a routes.py because every real feature has one — it is
    the blueprint the app factory registers, and since 2026-09-01 it is also
    what marks a directory as a feature for the sub-seam nesting guard.
    """
    root = tmp_path / "back_dev_home"

    def build(spec: dict[str, list[str]]):
        for rel, filenames in spec.items():
            providers = root / rel / "providers"
            providers.mkdir(parents=True, exist_ok=True)
            (root / rel / "routes.py").write_text("")
            for filename in filenames:
                (providers / filename).write_text("")
        monkeypatch.setattr(office_registry, "_ROOT", root)
        office_registry.reset_cache()
        return root

    yield build
    office_registry.reset_cache()


@pytest.fixture
def wired(fake_tree):
    """sem_list + storage have an office adapter; afm + tttm do not."""
    return fake_tree(
        {
            "sem_list": ["mock.py", "office.py"],
            "ebeam/storage": ["mock.py", "office.py"],
            "afm": ["mock.py", "office_example.py"],
            "ebeam/tttm": ["mock.py", "office_example.py"],
        }
    )
