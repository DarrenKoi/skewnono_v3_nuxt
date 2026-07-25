"""Office-adapter state helpers for the home-safe backend tests.

`providers/office.py` is gitignored — it exists only where someone ran
`cp office_example.py office.py` while wiring a feature at the office. So
"does this feature serve office data" is a property of the checkout, not of
the code under test: absent on CI and on a fresh clone, present on a wired
office machine and on the developer's Mac.

Two ways to cope, and this module offers both:

* **Control the state.** `fake_office_adapter` / `without_office_adapter`
  override readiness for the duration of a test, so the office dispatch branch
  and the missing-adapter refusal can both be asserted on ANY checkout. Use
  these — they make the assertion say what it means instead of depending on
  which machine ran it.
* **Skip on the state.** `has_office_adapter` / `skip_reason` opt a test out
  when the real adapter is present and would dial the company network (which
  is unreachable from home and times out). Use these only when the test truly
  needs the real module.

Mind the two key spaces, which name the same feature differently because they
answer different questions. `has_office_adapter` takes a **repo path** under
back_dev_home ("ebeam/hitachi/storage") because it stats a file. The state
helpers take the dispatcher **slug** ("storage") — the `providers/` parent
directory name, which is what `SKEWNONO_<FEATURE>_PROVIDER` and the registry
key on, and is globally unique by construction (`office_registry._discover`).

The now-deleted "unconnected office adapter" tests were written when every
`providers/office.py` was a stub raising
`NotImplementedError("... has not been connected")`. Adapters are real code
now, so that assertion is gone; the behaviour worth pinning is the
dispatcher's refusal, spelled `MISSING_ADAPTER_MESSAGE` below.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

_BACKEND = Path(__file__).resolve().parents[1] / "back_dev_home"

# The dispatcher's message when SKEWNONO_<FEATURE>_PROVIDER=office but no
# adapter is present. This is the documented contract (see CLAUDE.md):
# naming office with no adapter refuses to boot rather than falling back.
MISSING_ADAPTER_MESSAGE = "does not exist on this machine"


def has_office_adapter(feature_path: str) -> bool:
    """True when `back_dev_home/<feature_path>/providers/office.py` exists.

    `feature_path` is the slug-ish path under back_dev_home, e.g. "sem_list"
    or "ebeam/hitachi/storage".
    """
    return (_BACKEND / feature_path / "providers" / "office.py").is_file()


def skip_reason(feature_path: str) -> str:
    return (
        f"{feature_path} has a real providers/office.py on this machine, so the "
        "'unconnected adapter' state under test does not exist here — the "
        "adapter would dial the company network instead."
    )


def _providers_package(slug: str) -> str:
    """Dotted path of `<feature>/providers` for a dispatcher slug.

    Derived from the registry's own directory rather than passed in by the
    caller: a hand-written module path could drift from the slug, and on a
    wired office machine the drift would silently import the REAL adapter and
    dial the company Redis — the one failure neither CI nor home can catch.
    """
    from back_dev_home._runtime.office_registry import backend_root, features

    known = features()
    if slug not in known:
        raise AssertionError(
            f"unknown feature slug {slug!r}; known: {', '.join(sorted(known))}"
        )
    relative = known[slug].relative_to(backend_root().parent)
    return ".".join((*relative.parts, "providers"))


def _patched_readiness(ready: dict[str, Path]):
    """Override which features the registry reports as office-ready.

    Patches the memoized `_scan` rather than `data_provider.office_ready`, so
    every consumer of the registry agrees for the duration of the test. Note
    `features()` is read BEFORE the patch takes effect — it goes through the
    same `_scan`.
    """
    from back_dev_home._runtime import office_registry

    return patch.object(
        office_registry,
        "_scan",
        return_value=(office_registry.features(), ready),
    )


def _shadowed(package: str, module: ModuleType) -> list:
    """Make `<package>.office` resolve to `module`, for both import forms.

    The 22 dispatchers are split: 4 do `from <pkg>.office import <fn>`, which
    reads `sys.modules`; the other 18 do `from <pkg> import office`, which
    reads the attribute off the package — and on a wired machine that
    attribute already points at the real adapter. Cover both, or the helper
    would work at home and quietly dial the company network at the office.
    """
    return [
        patch.dict(sys.modules, {f"{package}.office": module}),
        patch.object(
            importlib.import_module(package), "office", module, create=True
        ),
    ]


def _checked_against_template(package: str, names: Iterator[str]) -> None:
    """Refuse to fake a function the tracked office template does not export.

    Replaces the guard lost when these tests stopped importing the real
    `providers/office.py`: `patch.object` used to raise AttributeError when a
    fake named a function the adapter no longer had. `office_example.py` is
    tracked, so this works on every checkout — and it pins the test to the
    template all office copies are made from, not to one machine's copy.
    """
    template = importlib.import_module(f"{package}.office_example")
    unknown = sorted(name for name in names if not hasattr(template, name))
    if unknown:
        raise AssertionError(
            f"{package}.office_example exports no {', '.join(unknown)} — "
            f"the office adapter contract moved and this test did not."
        )


@contextmanager
def fake_office_adapter(slug: str, **functions: object) -> Iterator[None]:
    """Stand a fake `providers/office.py` up for the body of a test.

    `slug` is the dispatcher slug ("sem_list", "storage"); `functions` are the
    adapter functions to expose, normally `unittest.mock` objects the caller
    then asserts on.

    Two fictions are needed because readiness and import are independent
    questions. Readiness is a FILESYSTEM fact, so the registry scan is
    patched — otherwise `SKEWNONO_<FEATURE>_PROVIDER=office` would raise the
    missing-adapter refusal before any adapter code ran. Import is resolved
    from `sys.modules` and the package attribute, neither of which needs a
    file on disk or the company network.

    Together they let the office dispatch branch be asserted on a clean
    checkout, and keep the assertion off the real adapter on a wired one.
    """
    from back_dev_home._runtime.office_registry import features, office_ready

    package = _providers_package(slug)
    _checked_against_template(package, iter(functions))

    module = ModuleType(f"{package}.office")
    for name, value in functions.items():
        setattr(module, name, value)

    ready = {**office_ready(), slug: features()[slug]}
    with ExitStack() as stack:
        for context in (*_shadowed(package, module), _patched_readiness(ready)):
            stack.enter_context(context)
        yield


@contextmanager
def without_office_adapter(slug: str) -> Iterator[None]:
    """Make `slug` look unwired, whatever this checkout actually has.

    The mirror of `fake_office_adapter`: it pins what happens when
    `SKEWNONO_<FEATURE>_PROVIDER=office` names a feature with no adapter —
    a refusal, never a silent fall back to fabricated mock numbers.
    """
    from back_dev_home._runtime.office_registry import office_ready

    _providers_package(slug)  # reject a typo instead of vacuously "unwired"
    ready = {
        slug_: path for slug_, path in office_ready().items() if slug_ != slug
    }
    with _patched_readiness(ready):
        yield
