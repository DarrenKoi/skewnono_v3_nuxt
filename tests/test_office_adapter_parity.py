"""Sweep: every office adapter template imports, and matches its mock sibling.

`providers/office.py` is a gitignored copy of the tracked
`providers/office_example.py`, and `data.py` resolves the adapter at call time
(`_provider().get_storage(...)`). Nothing in between type-checks that seam: a
function the dispatcher reaches for but the office template never defined is an
`AttributeError` on the first office request, and a parameter the office
template dropped is a `TypeError` on the same request. Both are invisible at
home, because home never selects the office branch. This module closes that gap
for every adapter at once instead of one test per feature — 13 of the 22
features had no office-adapter test at all when it was written.

WHAT "PUBLIC API" MEANS HERE — and why it is not "module-level callables".

The obvious definition (every non-underscore callable defined in the module)
is wrong for this repo, and confidently wrong: re-exporting the mock is a
*documented office pattern* for a not-yet-sourced function. recipe_search's
template does exactly that for `get_recipe_open_data` /
`get_recipe_compare_data` ("NO office source yet ... re-exported from the mock
below so the UI stays usable"), and device_statistics' mock re-exports
`get_recipe_params` / `get_rules` / `get_weekly_trend_data` from submodules. A
`__module__`-based "defined here" filter flags all of those as drift, and a
sweep that starts red gets an exclusion list bolted on and then ignored.
`__all__` is no better: only 13 of the 30 templates declare one, and the 19
mocks that do also export their contract TypedDicts, which the office side has
no reason to re-export.

So the surface asserted here is the one that can actually break a request: the
names THIS REPO'S OWN DISPATCH CODE looks up on the swapped module, read out of
the caller's AST (see `_switched_names` / `_tab_names`). Internal helpers are
excluded for free — nobody looks them up across the seam — so the assertion
needs no exclusions and is not weakened by the ones it would otherwise need.

The surface is tracked PER SIDE rather than as one shared set, because a couple
of dispatchers deliberately reach for different names on each provider.
fail_issue and recipe_tat both do::

    def get_anchor_time():
        provider = _provider()
        if provider is mock_provider:
            return mock_provider.ANCHOR_TIME   # a constant at home ...
        return provider.get_anchor_time()      # ... a live query at the office

Demanding `get_anchor_time` from the mock there would invent a requirement the
design rejects, so office-only lookups are asserted against the office template
only. That is also where the risk actually lives: the mock is exercised by every
home request, while the office branch runs nowhere until it runs in production.

Signatures are compared by ARITY ONLY, not by parameter names. An office
adapter that has not been connected yet is deliberately a `(*args, **kwargs)`
stub raising NotImplementedError (see pm_planning, device_statistics — the only
two left),
so name-by-name signature equality would fail for every unwired feature —
exactly the features least worth failing on. Arity binding still catches the
fatal case (the dispatcher passes more positionals than the adapter accepts)
and passes cleanly against a `*args` stub.

Nothing here CALLS an adapter. Import and introspection only: the real office
adapters dial the company Redis/OpenSearch, unreachable from home, and a
sweep that hangs for 30 seconds off-network would be deleted rather than fixed.

Everything is read from the TRACKED `office_example.py`, never from the
gitignored `office.py`, so the sweep asserts the same thing in a fresh checkout
as on an office machine that has copies — and needs no `tests/_office_state.py`
guard to collect.

Run from repo root:  .venv/bin/python -m pytest tests/test_office_adapter_parity.py
"""

from __future__ import annotations

import ast
import importlib
from functools import lru_cache
from inspect import Parameter, signature
from pathlib import Path

import pytest

from back_dev_home._runtime.office_registry import backend_root, features
from back_dev_home._runtime.office_template import Adapter, discover


# chat is PARKED — not an established page, and its office store is a stub with
# a second (env-driven LLM) swap surface this sweep does not model. Excluded
# deliberately; do not "fix" the omission by deleting this set.
#
# Full slugs, not bare directory names, so a future nested adapter that happens
# to sit in a directory called "chat" is not silently dropped from the sweep.
PARKED = {"chat"}

# The writer directory is copied wholesale onto a scheduler service and has no
# providers/ layout and no mock.py at all — its caller is its own job.py, not a
# data.py. Importability is still asserted; parity has no second side to check.
NO_MOCK_SIBLING = {"ebeam/hitachi/live_alarm/writer"}


def _adapters() -> list[Adapter]:
    return [a for a in discover() if a.slug not in PARKED]


def _module_name(path: Path) -> str:
    """back_dev_home/sem_list/providers/mock.py -> back_dev_home.sem_list...mock."""
    return ".".join(path.relative_to(backend_root().parent).with_suffix("").parts)


def _import(path: Path):
    return importlib.import_module(_module_name(path))


# --------------------------------------------------------------------------
# Reading the dispatch surface out of the caller's AST.
#
# Parsed, never executed: `from ...providers.office import get_sem_list` is a
# string here, so a checkout with no gitignored office.py reads the same
# surface as an office machine that has one.
# --------------------------------------------------------------------------


def _lookups(tree: ast.AST, is_source) -> tuple[set[str], set[str]]:
    """Attribute names read off whatever `is_source` recognizes as the module.

    Returns (inline, via_local) — kept apart because the two callers weigh them
    differently: a tab's builders are symmetric by contract, while a local bound
    to `_provider()` is the one place a dispatcher branches on which provider it
    got. Both spellings occur:

        _tab("fdc").build_fdc_docs(...)          # inline
        mdc = _tab("mdc"); mdc.build_mdc_settings(...)   # via a local

    Missing the second form silently reduced this sweep to zero assertions for
    hardware's mdc and sce tabs while it was being written, which is why
    `test_every_adapter_with_a_caller_has_a_non_empty_switched_surface` exists.
    """
    def _attr_on(node: ast.AST, matches) -> str | None:
        if isinstance(node, ast.Attribute) and matches(node.value):
            return node.attr
        return None

    bound = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and is_source(node.value)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    inline: set[str] = set()
    via_local: set[str] = set()
    for node in ast.walk(tree):
        found = _attr_on(node, is_source)
        if found:
            inline.add(found)
        found = _attr_on(node, lambda base: isinstance(base, ast.Name) and base.id in bound)
        if found:
            via_local.add(found)
    return inline, via_local


def _calls_named(name: str, *args_match):
    """Predicate: a call to `name(...)`, optionally pinned to a first argument."""
    def matches(node: ast.AST) -> bool:
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        ):
            return False
        if not args_match:
            return True
        return (
            bool(node.args)
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == args_match[0]
        )

    return matches


def _switched_names(data_py: Path) -> tuple[set[str], set[str]]:
    """(office_required, mock_required) for one feature's data.py.

    Three idioms are live in the tree today:

      * `_provider().get_device_desc(...)` — one `_provider()` helper picking
        the module, then an inline call. The majority of features; required on
        BOTH sides, since either module can be what `_provider()` returned.
      * `provider = _provider()` … `provider.get_anchor_time()` — the module
        bound to a local first (fail_issue, recipe_tat). Counted as OFFICE-only:
        both occurrences exist precisely because the dispatcher branches on
        provider identity and takes a different name at home (see the module
        docstring), so symmetry cannot be assumed here.
      * `from <feature>.providers.{office,mock} import get_storage as ...` — the
        per-call-site import (sem_list, storage, skew). Each side's import
        counts for that side.

    Two kinds of reference are deliberately NOT collected:

      * MODULE-LEVEL imports. access_control's data.py re-exports
        `BLOCKED_PREFIX` and `StoreUnavailableError` from the mock at module
        scope on purpose ("re-exported unswitched — provider-independent
        policy/error type"), so demanding them from the office side would
        invent a requirement the design rejects.
      * `mock_provider.<name>` — a module-scope alias pinned to the mock
        (fail_issue's `ANCHOR_TIME`, msr_file's cache handles). Those never
        resolve against the office module, so they are not seam lookups at all;
        home exercises them on every request.
    """
    tree = ast.parse(data_py.read_text(encoding="utf-8"))
    is_provider = _calls_named("_provider")
    inline, via_local = _lookups(tree, is_provider)

    # Inline `_provider().x` may land on either module; a local bound to
    # `_provider()` is where a dispatcher branches, so it counts office-only.
    office = inline | via_local
    mock = set(inline)

    # Imports inside a function body ARE the switch; module-scope ones are not.
    # Collected by walking function bodies rather than by excluding tree.body, so
    # a module-scope `if TYPE_CHECKING:` block cannot be mistaken for a switch.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.ImportFrom):
                continue
            imported = {alias.name for alias in child.names}
            if (child.module or "").endswith(".providers.office"):
                office |= imported
            elif (child.module or "").endswith(".providers.mock"):
                mock |= imported
    return office, mock


def _tab_names(providers_dir: Path, tab: str) -> set[str]:
    """Builder names hardware's dispatcher calls on one per-tab adapter.

    Read from `providers/office_example.py` only — that dispatcher is the sole
    `_tab()` caller (`providers/mock.py` imports the per-tab builders at module
    scope instead). One source is enough because `_tab()` resolves to EITHER a
    tab's office.py or its mock.py, which is exactly the contract the dispatcher
    states: "a tab's office.py and mock.py expose the SAME builder names
    returning the SAME raw shapes". So every name found here is required of both
    sides of that tab's swap.
    """
    source = providers_dir / "office_example.py"
    if not source.exists():
        return set()
    tree = ast.parse(source.read_text(encoding="utf-8"))
    inline, via_local = _lookups(tree, _calls_named("_tab", tab))
    return inline | via_local


def _is_feature_level(adapter: Adapter) -> bool:
    """True for providers/office_example.py, False for providers/<tab>/…"""
    return adapter.template.parent.name == "providers"


@lru_cache(maxsize=None)
def _required(adapter: Adapter) -> tuple[set[str], set[str]]:
    """(office_required, mock_required) for this adapter, read from its caller.

    Memoized: four tests and two guards ask for the same surface, and Adapter is
    a frozen dataclass, so one parse per adapter covers the whole module.
    """
    providers_dir = adapter.template.parent
    if not _is_feature_level(adapter):
        # providers/<tab>/office_example.py — the caller is the parent dispatcher,
        # which states that a tab's two modules expose the SAME builder names, so
        # the per-tab surface is symmetric by contract.
        names = _tab_names(providers_dir.parent, providers_dir.name)
        return names, names
    data_py = providers_dir.parent / "data.py"
    if not data_py.exists():
        return set(), set()
    return _switched_names(data_py)


def _positional_arity(func) -> int | None:
    """How many positionals this function declares, or None if it takes *args."""
    try:
        params = signature(func).parameters.values()
    except (TypeError, ValueError):
        return None
    if any(p.kind is Parameter.VAR_POSITIONAL for p in params):
        return None
    return sum(
        1
        for p in params
        if p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
    )


def _ids(adapters: list[Adapter]) -> list[str]:
    return [a.slug for a in adapters]


_ALL = _adapters()
_WITH_MOCK = [a for a in _ALL if a.slug not in NO_MOCK_SIBLING]


# --------------------------------------------------------------------------
# The assertions
# --------------------------------------------------------------------------


@pytest.mark.parametrize("adapter", _ALL, ids=_ids(_ALL))
def test_office_template_imports(adapter: Adapter):
    """A template that cannot be imported cannot be copied into service.

    Hard failure, not importorskip: all 30 templates in the tree import in this
    venv today (29 are swept — chat is parked), so skipping on ImportError would
    only hide the day one stops. A genuinely optional third-party dependency
    going missing is a finding about the venv, which is what the surfaced
    exception says.
    """
    try:
        _import(adapter.template)
    except Exception as exc:  # noqa: BLE001 — the type is the diagnosis
        pytest.fail(
            f"{adapter.slug}: {adapter.template.name} failed to import — "
            f"{type(exc).__name__}: {exc}"
        )


@pytest.mark.parametrize("adapter", _WITH_MOCK, ids=_ids(_WITH_MOCK))
def test_mock_has_a_template_sibling(adapter: Adapter):
    """Both halves of the swap exist. office_registry raises for a missing mock
    under providers/, but says nothing about a per-tab adapter."""
    assert adapter.template.with_name("mock.py").exists(), (
        f"{adapter.slug}: office_example.py with no sibling mock.py — home "
        f"development and the contract tests both run against the mock"
    )


@pytest.mark.parametrize("adapter", _WITH_MOCK, ids=_ids(_WITH_MOCK))
def test_switched_names_resolve_on_both_adapters(adapter: Adapter):
    """Every name the dispatcher looks up is callable on mock AND office.

    A name present only on the mock breaks the office (AttributeError on the
    first office request); a name present only on the office template breaks
    home the same way. Neither side is the reference — the dispatcher is.
    """
    office_required, mock_required = _required(adapter)
    office = _import(adapter.template)
    mock = _import(adapter.template.with_name("mock.py"))

    missing_office = sorted(
        n for n in office_required if not callable(getattr(office, n, None))
    )
    missing_mock = sorted(
        n for n in mock_required if not callable(getattr(mock, n, None))
    )
    assert not (missing_office or missing_mock), (
        f"{adapter.slug}: dispatched name(s) missing across the swap seam — "
        f"absent from office_example.py: {missing_office or 'none'}; "
        f"absent from mock.py: {missing_mock or 'none'}"
    )


@pytest.mark.parametrize("adapter", _WITH_MOCK, ids=_ids(_WITH_MOCK))
def test_office_accepts_the_positional_arity_mock_declares(adapter: Adapter):
    """The office side must not take fewer positionals than the mock.

    The mock is the reference arity because home exercises it on every request,
    so `_provider().get_storage(tool_slug, fab_names)` is known to fit it. An
    office adapter that fits the same call cannot raise TypeError on dispatch.

    Extra office-only parameters are fine as long as they default — msr_image's
    template adds `_config=None` for test injection. A `*args` stub on either
    side yields None arity and is skipped: it accepts everything, so there is
    nothing to catch.
    """
    office = _import(adapter.template)
    mock = _import(adapter.template.with_name("mock.py"))

    office_required, mock_required = _required(adapter)
    too_narrow = []
    # Only names dispatched to BOTH sides have a mock arity to measure against.
    for name in sorted(office_required & mock_required):
        office_func = getattr(office, name, None)
        mock_func = getattr(mock, name, None)
        if not (callable(office_func) and callable(mock_func)):
            continue  # already reported by the resolution test
        arity = _positional_arity(mock_func)
        if arity is None:
            continue
        try:
            signature(office_func).bind(*[None] * arity)
        except TypeError as exc:
            too_narrow.append(
                f"{name}: mock takes {arity} positional(s) but office "
                f"{signature(office_func)} rejects that call — {exc}"
            )
    assert not too_narrow, f"{adapter.slug}: " + "; ".join(too_narrow)


# --------------------------------------------------------------------------
# Guards on the sweep itself
# --------------------------------------------------------------------------


def test_every_adapter_with_a_caller_has_a_non_empty_switched_surface():
    """The sweep must not quietly become a no-op.

    Every assertion above iterates a set read out of a caller's AST, so a
    dispatch idiom this module does not recognize does not fail — it yields an
    empty set and passes vacuously. Refactoring data.py to, say, `getattr` is
    a legitimate change that must break HERE, loudly, rather than silently
    retiring the parity check for that feature.
    """
    empty = sorted(
        a.slug
        for a in _ALL
        if a.slug not in NO_MOCK_SIBLING and not any(_required(a))
    )
    assert not empty, (
        "no switched names extracted for: " + ", ".join(empty) + ". Either the "
        "feature's data.py uses a dispatch idiom _switched_names/_tab_names "
        "does not recognize, or its caller moved — extend the extractor"
    )


def test_sweep_covers_every_registered_feature():
    """Every feature the app can switch to office has a template in this sweep.

    A feature with providers/mock.py but no providers/office_example.py cannot
    be wired at the office at all (there is nothing to `cp`), so it belongs on
    this list or it belongs in PARKED — not silently outside both.
    """
    # features() is keyed by feature directory name. Only FEATURE-LEVEL adapters
    # may satisfy it: counting per-tab names too would let a future feature
    # directory called e.g. "fdc" pass this guard with no template of its own.
    swept = {a.name for a in _ALL if _is_feature_level(a)}
    swept |= {slug.rsplit("/", 1)[-1] for slug in PARKED}
    uncovered = sorted(set(features()) - swept)
    assert not uncovered, (
        "feature(s) with providers/mock.py but no providers/office_example.py: "
        + ", ".join(uncovered)
        + " — add the template (see the feature's MIGRATION.md) so the office "
        "has something to copy"
    )
