"""The CLI layer of the two office-adapter provisioning scripts.

These are the scripts the office machine actually runs: setup_office_adapters
is the one-shot for a fresh clone, sync_office_adapters is how a stale copy
gets refreshed. Both decide whether a feature gets wired to office data at all
and whether gitignored office code — which exists nowhere else — survives.

Like ``_runtime/tests/test_office_template.py``, these build a real throwaway
git repo in tmp_path rather than mocking subprocess: STALE vs EDITED and the
"git does NOT ignore this" warning are both answers only git can give.

The classification itself is NOT retested here; it lives in
``office_template.classify()`` and is covered there. What is covered is
everything the CLI adds around it — stub detection, name resolution, the
backup/skip guards, and the --all / --dry-run / --include-stubs filters.
"""

import subprocess

import pytest

from scripts import setup_office_adapters as setup
from scripts import sync_office_adapters as sync
from scripts.sync_office_adapters import EDITED, MISSING, STALE, SYNCED


# --------------------------------------------------------------------------
# A throwaway checkout
# --------------------------------------------------------------------------

def _git(repo, *args):
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo),
        },
    )


IMPLEMENTED = 'def get_thing():\n    return {"rows": []}\n'
STUB_TEMPLATE = (
    'def get_thing():\n'
    '    raise NotImplementedError("not connected yet")\n'
)


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    """Factory: a git checkout whose back_dev_home holds the given templates.

    Aims both scripts at it. ``setup_office_adapters`` does a from-import of
    REPO_ROOT, so it holds its own binding and needs patching separately —
    the functions it imported read sync's globals at call time and do not.
    """
    root = tmp_path / "checkout"
    backend = root / "back_dev_home"
    backend.mkdir(parents=True)
    # Both rules from the real .gitignore, so git_ignores() has something to
    # say about a per-tab adapter as well as a feature-level one.
    (root / ".gitignore").write_text(
        "back_dev_home/**/providers/office.py\n"
        "back_dev_home/**/providers/**/office.py\n"
    )
    _git(root, "init", "-q", "-b", "main")
    monkeypatch.setattr(sync, "REPO_ROOT", root)
    monkeypatch.setattr(sync, "BACKEND_ROOT", backend)
    monkeypatch.setattr(setup, "REPO_ROOT", root)

    def build(templates: dict[str, str]):
        for key, source in templates.items():
            providers = _providers_dir(backend, key)
            providers.mkdir(parents=True, exist_ok=True)
            (providers / "office_example.py").write_text(source)
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", "templates")
        sync.reset_cache()
        return root

    yield build
    sync.reset_cache()


@pytest.fixture(autouse=True)
def _no_stale_statuses():
    sync.reset_cache()
    yield
    sync.reset_cache()


def _providers_dir(backend, key):
    """Where a template lives, from the key the checkout fixture was given.

    Normally ``<feature>/providers``. A key that already names a providers
    directory is used verbatim, because the real per-tab layout carries the
    segment in the MIDDLE — ``hardware/providers/fdc`` — and building
    ``hardware/providers/fdc/providers`` instead would let a narrowing of
    discover()'s slug rule pass unnoticed.
    """
    parts = key.split("/")
    if "providers" in parts:
        return backend.joinpath(*parts)
    return backend.joinpath(*parts, "providers")


def _target(root, key):
    return _providers_dir(root / "back_dev_home", key) / "office.py"


def _template(root, key):
    return _providers_dir(root / "back_dev_home", key) / "office_example.py"


def _make_synced(root, key):
    """A copy byte-identical to its template."""
    target = _target(root, key)
    target.write_bytes(_template(root, key).read_bytes())
    sync.reset_cache()
    return target


def _make_stale(root, key):
    """Copy, then move the template ahead and commit — the git pull scenario."""
    target = _make_synced(root, key)
    _template(root, key).write_text(IMPLEMENTED + "# template moved ahead\n")
    _git(root, "commit", "-qam", "template moves ahead")
    sync.reset_cache()
    return target


def _make_edited(root, key):
    """A copy holding local changes that match no committed template."""
    target = _target(root, key)
    target.write_text(IMPLEMENTED + "# 사내 schema detail\n")
    sync.reset_cache()
    return target


# --------------------------------------------------------------------------
# is_stub — whether copying a template would 500 a working mock page
# --------------------------------------------------------------------------

def _stub(tmp_path, source):
    path = tmp_path / "office_example.py"
    path.write_text(source)
    return sync.is_stub(path)


def test_a_template_whose_only_export_raises_is_a_stub(tmp_path):
    assert _stub(tmp_path, STUB_TEMPLATE)


def test_a_bare_raise_of_the_class_counts(tmp_path):
    assert _stub(tmp_path, "def get_thing():\n    raise NotImplementedError\n")


def test_a_docstring_does_not_hide_the_raise(tmp_path):
    assert _stub(
        tmp_path,
        'def get_thing():\n    """Office adapter."""\n    raise NotImplementedError()\n',
    )


def test_only_the_first_statement_counts(tmp_path):
    """A real adapter computes before it can fail, so a later raise is fine.

    This is the check that keeps working adapters copyable; without it any
    adapter with a defensive raise anywhere in its body would be skipped.
    """
    assert not _stub(
        tmp_path,
        "def get_thing(mode):\n"
        "    rows = fetch(mode)\n"
        "    if not rows:\n"
        '        raise NotImplementedError("mode not wired")\n'
        "    return rows\n",
    )


def test_a_raise_inside_a_conditional_is_not_a_stub(tmp_path):
    assert not _stub(
        tmp_path,
        "def get_thing(mode):\n"
        "    if mode == 'new':\n"
        "        raise NotImplementedError\n"
        "    return {}\n",
    )


def test_the_not_connected_helper_is_recognised(tmp_path):
    """`return _not_connected()` fails just as unconditionally as a raise."""
    assert _stub(
        tmp_path,
        "def _not_connected(*a, **k):\n"
        "    raise NotImplementedError\n"
        "\n"
        "def get_thing():\n"
        "    return _not_connected()\n",
    )


def test_a_bare_helper_call_statement_is_recognised(tmp_path):
    assert _stub(
        tmp_path,
        "def _not_connected(*a, **k):\n"
        "    raise NotImplementedError\n"
        "\n"
        "def get_thing():\n"
        "    _not_connected()\n",
    )


def test_module_level_aliasing_to_the_helper_counts(tmp_path):
    """chat's shape: the API is exported by assignment, not by `def`."""
    assert _stub(
        tmp_path,
        "def _not_connected(*a, **k):\n"
        "    raise NotImplementedError\n"
        "\n"
        "create_thread = _not_connected\n"
        "list_threads = _not_connected\n",
    )


def test_an_alias_to_something_real_is_not_a_stub(tmp_path):
    assert not _stub(
        tmp_path,
        "def _real():\n"
        "    return {}\n"
        "\n"
        "get_thing = _real\n",
    )


def test_a_call_to_an_unrelated_function_is_not_the_helper(tmp_path):
    """Only helpers that themselves just raise may stand in for a raise."""
    assert not _stub(
        tmp_path,
        "def _load():\n"
        "    return {}\n"
        "\n"
        "def get_thing():\n"
        "    return _load()\n",
    )


def test_one_implemented_export_is_enough_to_not_be_a_stub(tmp_path):
    """recipe_tat's shape: get_meas_hist raises, the rest are real."""
    assert not _stub(
        tmp_path,
        "def get_meas_hist():\n"
        '    raise NotImplementedError("not applicable at the office")\n'
        "\n"
        "def get_ranking():\n"
        "    return []\n",
    )


def test_an_async_export_that_raises_is_a_stub(tmp_path):
    assert _stub(tmp_path, "async def get_thing():\n    raise NotImplementedError\n")


def test_another_exception_type_is_not_a_stub_marker(tmp_path):
    assert not _stub(
        tmp_path, 'def get_thing():\n    raise RuntimeError("redis down")\n'
    )


def test_a_template_with_no_exports_is_not_a_stub(tmp_path):
    """Nothing to judge, so nothing is claimed — is_stub must not veto."""
    assert not _stub(tmp_path, "IMPORTS_ONLY = 1\n")
    assert not _stub(tmp_path, "def _private():\n    raise NotImplementedError\n")


def test_an_unparseable_template_is_not_a_stub(tmp_path):
    assert not _stub(tmp_path, "def get_thing(:\n")


def test_a_missing_template_is_not_a_stub(tmp_path):
    assert not sync.is_stub(tmp_path / "nope.py")


# --------------------------------------------------------------------------
# is_stub against the real tree
# --------------------------------------------------------------------------

@pytest.mark.parametrize("slug", [
    # A dispatcher, not a data adapter: it must be copied or the hardware page
    # stays on mock at the office with nothing saying so.
    "ebeam/hardware",
    # Live-verified at the office, so a stub verdict here is definitely wrong.
    "sem_list",
    "ebeam/storage",
    # Real, but deliberately leaves ONE export raising — the case the
    # every-export rule exists for.
    "ebeam/recipe_tat",
])
def test_the_implemented_adapters_in_the_tree_are_not_stubs(slug):
    """Live canary: a false positive here silently leaves a feature on mock."""
    template = sync.BACKEND_ROOT.joinpath(*slug.split("/"), "providers", "office_example.py")
    assert template.is_file()
    assert not sync.is_stub(template)


def test_no_real_template_is_called_a_stub_without_saying_so():
    """Cross-check every template in the tree against a crude text signal.

    A stub verdict blocks a copy, so a false positive silently leaves a
    feature on mock. Any template is_stub() rejects must at least mention
    NotImplementedError somewhere.
    """
    adapters = sync.discover()
    assert adapters, "the real tree must be scannable, or this asserts nothing"
    for adapter in adapters:
        if sync.is_stub(adapter.template):
            text = adapter.template.read_text(encoding="utf-8")
            assert "NotImplementedError" in text, adapter.slug


# --------------------------------------------------------------------------
# resolve — turning a typed name into exactly one adapter
# --------------------------------------------------------------------------

@pytest.fixture
def named(checkout):
    return checkout({
        "sem_list": IMPLEMENTED,
        "ebeam/storage": IMPLEMENTED,
        "ebeam/hardware/providers/fdc": IMPLEMENTED,
        "ebeam/fdc": IMPLEMENTED,
    })


def test_the_full_slug_resolves(named):
    assert [a.slug for a in sync.resolve(sync.discover(), "ebeam/storage")] == [
        "ebeam/storage"
    ]


@pytest.mark.parametrize("query", ["storage", "ebeam/storage", "/Storage/", " storage "])
def test_any_unique_suffix_resolves(named, query):
    assert [a.slug for a in sync.resolve(sync.discover(), query)] == [
        "ebeam/storage"
    ]


def test_a_partial_segment_matches_nothing(named):
    with pytest.raises(SystemExit, match="no adapter matches 'orage'"):
        sync.resolve(sync.discover(), "orage")


def test_an_unknown_name_names_the_status_listing(named):
    with pytest.raises(SystemExit, match="Run without arguments"):
        sync.resolve(sync.discover(), "nonesuch")


def test_an_ambiguous_suffix_refuses_to_guess(named):
    with pytest.raises(SystemExit) as exit_info:
        sync.resolve(sync.discover(), "fdc")

    message = str(exit_info.value)
    assert "ambiguous" in message
    assert "ebeam/fdc" in message
    assert "ebeam/hardware/fdc" in message


def test_a_longer_path_disambiguates(named):
    assert [a.slug for a in sync.resolve(sync.discover(), "hardware/fdc")] == [
        "ebeam/hardware/fdc"
    ]


def test_an_exact_slug_wins_over_its_own_suffix_matches(checkout):
    """A feature literally named `fdc` must not be reported as ambiguous."""
    checkout({"fdc": IMPLEMENTED, "ebeam/hardware/providers/fdc": IMPLEMENTED})

    assert [a.slug for a in sync.resolve(sync.discover(), "fdc")] == ["fdc"]


def test_a_blank_query_selects_nothing(named):
    assert sync.resolve(sync.discover(), "  ") == []


# --------------------------------------------------------------------------
# git_ignores — office.py must never become trackable
# --------------------------------------------------------------------------

def test_git_ignores_an_office_py(checkout):
    root = checkout({"sem_list": IMPLEMENTED})
    assert sync.git_ignores(_target(root, "sem_list"))


def test_git_ignores_a_per_tab_office_py(checkout):
    """The per-tab shape needs its own .gitignore rule to be covered."""
    root = checkout({"ebeam/hardware/providers/fdc": IMPLEMENTED})
    assert sync.git_ignores(_target(root, "ebeam/hardware/providers/fdc"))


def test_git_does_not_ignore_the_template(checkout):
    root = checkout({"sem_list": IMPLEMENTED})
    assert not sync.git_ignores(_template(root, "sem_list"))


@pytest.mark.parametrize("relative", [
    "back_dev_home/sem_list/providers/office.py",
    "back_dev_home/ebeam/hardware/providers/fdc/office.py",
])
def test_this_repo_ignores_every_shape_of_office_py(relative):
    """Against the REAL .gitignore, not the fixture's reduction of it.

    git check-ignore answers for paths that do not exist, so this holds
    wherever office.py happens to have been copied — and the copy warning is
    only as good as the rules it is checking.
    """
    assert sync.git_ignores(sync.REPO_ROOT / relative)


# --------------------------------------------------------------------------
# copy — the guards against unrecoverable loss of gitignored office code
# --------------------------------------------------------------------------

def test_a_missing_target_is_created(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})

    sync.copy(sync.discover(), force=False, dry_run=False)

    assert _target(root, "sem_list").read_text() == IMPLEMENTED
    assert "copied 1, skipped 0" in capsys.readouterr().out


def test_refreshing_a_stale_copy_backs_it_up_first(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})
    target = _make_stale(root, "sem_list")
    before = target.read_text()

    sync.copy(sync.discover(), force=False, dry_run=False)

    backup = target.with_suffix(".py.bak")
    assert backup.read_text() == before
    assert target.read_text() == _template(root, "sem_list").read_text()
    assert "backup" in capsys.readouterr().out


def test_an_edited_copy_is_skipped_without_force(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})
    target = _make_edited(root, "sem_list")
    before = target.read_text()

    sync.copy(sync.discover(), force=False, dry_run=False)

    out = capsys.readouterr().out
    assert target.read_text() == before
    assert not target.with_suffix(".py.bak").exists()
    assert "SKIP" in out
    assert "--force" in out
    assert "copied 0, skipped 1" in out


def test_force_overwrites_an_edited_copy_but_backs_it_up(checkout):
    root = checkout({"sem_list": IMPLEMENTED})
    target = _make_edited(root, "sem_list")
    local = target.read_text()

    sync.copy(sync.discover(), force=True, dry_run=False)

    # The .bak is the only remaining trace of the local changes; office.py is
    # gitignored, so without it the overwrite would be unrecoverable.
    assert target.with_suffix(".py.bak").read_text() == local
    assert target.read_text() == IMPLEMENTED


def test_a_synced_copy_is_skipped(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})
    _make_synced(root, "sem_list")

    sync.copy(sync.discover(), force=False, dry_run=False)

    out = capsys.readouterr().out
    assert "already synced" in out
    assert "copied 0, skipped 1" in out
    assert not _target(root, "sem_list").with_suffix(".py.bak").exists()


def test_dry_run_writes_nothing(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})

    sync.copy(sync.discover(), force=False, dry_run=True)

    out = capsys.readouterr().out
    assert not _target(root, "sem_list").exists()
    assert "would create" in out
    assert "would copy 1" in out


def test_dry_run_calls_a_stale_refresh_a_refresh(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})
    _make_stale(root, "sem_list")

    sync.copy(sync.discover(), force=False, dry_run=True)

    assert "would refresh" in capsys.readouterr().out


def test_a_target_git_does_not_ignore_is_shouted_about(checkout, capsys):
    """A tracked office.py risks committing 사내 schema, so it must be loud."""
    root = checkout({"sem_list": IMPLEMENTED})
    (root / ".gitignore").write_text("# nothing ignored\n")

    sync.copy(sync.discover(), force=False, dry_run=False)

    assert "git does NOT ignore this file" in capsys.readouterr().out
    assert _target(root, "sem_list").is_file()  # copied anyway, just noisily


def test_an_ignored_target_is_copied_quietly(checkout, capsys):
    checkout({"sem_list": IMPLEMENTED})

    sync.copy(sync.discover(), force=False, dry_run=False)

    assert "git does NOT ignore" not in capsys.readouterr().out


def test_copy_names_the_health_endpoint_to_verify_with(checkout, capsys):
    checkout({"sem_list": IMPLEMENTED})

    sync.copy(sync.discover(), force=False, dry_run=False)

    out = capsys.readouterr().out
    assert "Restart Flask" in out
    assert "/api/health/providers" in out


# --------------------------------------------------------------------------
# print_status — the default, safe action
# --------------------------------------------------------------------------

def test_print_status_counts_every_status(checkout, capsys):
    root = checkout({
        "missing_one": IMPLEMENTED,
        "synced_one": IMPLEMENTED,
        "stale_one": IMPLEMENTED,
        "edited_one": IMPLEMENTED,
    })
    _make_synced(root, "synced_one")
    _make_stale(root, "stale_one")
    _make_edited(root, "edited_one")

    sync.print_status(sync.discover())

    out = capsys.readouterr().out
    assert "4 adapters: 3 copied (1 synced, 1 stale, 1 edited), 1 missing." in out
    reported = {
        line.split()[0]: line.split()[1]
        for line in out.splitlines() if line.startswith(("missing", "synced", "stale", "edited"))
    }
    assert reported == {
        "missing_one": MISSING,
        "synced_one": SYNCED,
        "stale_one": STALE,
        "edited_one": EDITED,
    }
    # Each non-clean state gets its own call to action.
    assert "1 STALE" in out
    assert "Copy the missing ones" in out
    assert "exist nowhere else" in out


def test_print_status_is_quiet_when_everything_is_synced(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})
    _make_synced(root, "sem_list")

    sync.print_status(sync.discover())

    out = capsys.readouterr().out
    assert "1 adapters: 1 copied (1 synced, 0 stale, 0 edited), 0 missing." in out
    assert STALE not in out
    assert "Copy the missing ones" not in out


# --------------------------------------------------------------------------
# main — the --all filter is what a fresh office machine leans on
# --------------------------------------------------------------------------

def test_no_arguments_reports_and_copies_nothing(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})

    assert sync.main([]) == 0

    assert not _target(root, "sem_list").exists()
    assert "STATUS" in capsys.readouterr().out


def test_all_copies_missing_and_stale_but_not_edited(checkout):
    root = checkout({
        "missing_one": IMPLEMENTED,
        "stale_one": IMPLEMENTED,
        "edited_one": IMPLEMENTED,
    })
    _make_stale(root, "stale_one")
    edited = _make_edited(root, "edited_one")
    local = edited.read_text()

    assert sync.main(["--all"]) == 0

    assert _target(root, "missing_one").is_file()
    assert _target(root, "stale_one").read_text() == _template(root, "stale_one").read_text()
    assert edited.read_text() == local


def test_all_skips_stubs(checkout, capsys):
    root = checkout({"real_one": IMPLEMENTED, "stub_one": STUB_TEMPLATE})

    assert sync.main(["--all"]) == 0

    out = capsys.readouterr().out
    assert _target(root, "real_one").is_file()
    assert not _target(root, "stub_one").exists()
    assert "Skipping 1 not-yet-implemented template(s)" in out
    assert "--include-stubs" in out


def test_include_stubs_copies_them(checkout):
    root = checkout({"stub_one": STUB_TEMPLATE})

    assert sync.main(["--all", "--include-stubs"]) == 0

    assert _target(root, "stub_one").is_file()


def test_all_with_only_stubs_left_says_so(checkout, capsys):
    root = checkout({"stub_one": STUB_TEMPLATE})

    assert sync.main(["--all"]) == 0

    assert not _target(root, "stub_one").exists()
    assert "already up to date" in capsys.readouterr().out


def test_all_dry_run_writes_nothing(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})

    assert sync.main(["--all", "--dry-run"]) == 0

    assert not _target(root, "sem_list").exists()
    assert "would copy 1" in capsys.readouterr().out


def test_a_named_adapter_is_copied_even_when_it_is_a_stub(checkout):
    """Naming one is a deliberate act; the stub filter only guards --all."""
    root = checkout({"stub_one": STUB_TEMPLATE})

    assert sync.main(["stub_one"]) == 0

    assert _target(root, "stub_one").is_file()


def test_an_unknown_name_exits_nonzero(checkout):
    checkout({"sem_list": IMPLEMENTED})

    with pytest.raises(SystemExit):
        sync.main(["nonesuch"])


def test_a_tree_with_no_templates_exits(checkout):
    checkout({})

    with pytest.raises(SystemExit, match="no office_example.py"):
        sync.main([])


def test_diff_reports_nothing_when_every_copy_matches(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})
    _make_synced(root, "sem_list")

    assert sync.main(["--diff"]) == 0

    assert "Nothing to diff" in capsys.readouterr().out


def test_diff_headers_name_the_status_of_each_drifted_copy(checkout, capsys):
    root = checkout({"synced_one": IMPLEMENTED, "edited_one": IMPLEMENTED})
    _make_synced(root, "synced_one")
    _make_edited(root, "edited_one")

    assert sync.main(["--diff"]) == 0

    out = capsys.readouterr().out
    assert f"=== edited_one [{EDITED}] ===" in out
    assert "synced_one" not in out


# --------------------------------------------------------------------------
# -i — the menu, whose blank input is the easiest way to copy the wrong set
# --------------------------------------------------------------------------

def _answer(monkeypatch, text):
    monkeypatch.setattr("builtins.input", lambda *_: text)


@pytest.fixture
def menu(checkout):
    root = checkout({"missing_one": IMPLEMENTED, "edited_one": IMPLEMENTED})
    _make_edited(root, "edited_one")
    return root


def test_blank_input_selects_only_the_missing_ones(menu, monkeypatch, capsys):
    _answer(monkeypatch, "")

    assert sync.main(["-i"]) == 0

    out = capsys.readouterr().out
    assert _target(menu, "missing_one").is_file()
    assert EDITED in out  # listed in the menu, but not selected by a blank
    assert "copied 1, skipped 0" in out


def test_a_number_selects_that_adapter(menu, monkeypatch, capsys):
    _answer(monkeypatch, "2")  # adapters are listed sorted by slug

    assert sync.main(["-i", "--dry-run"]) == 0

    assert "missing_one" in capsys.readouterr().out.rsplit("[dry-run]", 1)[1]


def test_a_number_outside_the_menu_is_refused(menu, monkeypatch):
    _answer(monkeypatch, "9")

    with pytest.raises(SystemExit, match="between 1 and 2"):
        sync.main(["-i"])


def test_an_aborted_menu_copies_nothing(menu, monkeypatch, capsys):
    def _abort(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _abort)

    assert sync.main(["-i"]) == 0

    assert not _target(menu, "missing_one").exists()
    assert "Nothing selected." in capsys.readouterr().out


# --------------------------------------------------------------------------
# setup_office_adapters — the one-shot a fresh office clone runs
# --------------------------------------------------------------------------

def test_setup_creates_missing_and_refreshes_stale(checkout, capsys):
    root = checkout({"missing_one": IMPLEMENTED, "stale_one": IMPLEMENTED})
    _make_stale(root, "stale_one")

    assert setup.main([]) == 0

    out = capsys.readouterr().out
    assert _target(root, "missing_one").read_text() == IMPLEMENTED
    assert _target(root, "stale_one").read_text() == _template(root, "stale_one").read_text()
    assert "Created 1, refreshed 1." in out


def test_setup_backs_up_a_stale_copy_before_refreshing(checkout):
    root = checkout({"stale_one": IMPLEMENTED})
    target = _make_stale(root, "stale_one")
    before = target.read_text()

    assert setup.main([]) == 0

    assert target.with_suffix(".py.bak").read_text() == before


def test_setup_leaves_a_synced_copy_alone(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})
    _make_synced(root, "sem_list")

    assert setup.main([]) == 0

    out = capsys.readouterr().out
    assert "Created 0, refreshed 0." in out
    assert not _target(root, "sem_list").with_suffix(".py.bak").exists()


def test_setup_skips_stubs_and_names_them(checkout, capsys):
    root = checkout({"real_one": IMPLEMENTED, "stub_one": STUB_TEMPLATE})

    assert setup.main([]) == 0

    out = capsys.readouterr().out
    assert _target(root, "real_one").is_file()
    assert not _target(root, "stub_one").exists()
    assert "Skipped 1 not-yet-implemented template(s)" in out
    assert "stub_one" in out


def test_setup_include_stubs_copies_them(checkout):
    root = checkout({"stub_one": STUB_TEMPLATE})

    assert setup.main(["--include-stubs"]) == 0

    assert _target(root, "stub_one").is_file()


def test_setup_skips_edited_copies_and_names_them(checkout, capsys):
    root = checkout({"edited_one": IMPLEMENTED})
    target = _make_edited(root, "edited_one")
    local = target.read_text()

    assert setup.main([]) == 0

    out = capsys.readouterr().out
    assert target.read_text() == local
    assert not target.with_suffix(".py.bak").exists()
    assert "locally-edited" in out
    assert "edited_one" in out
    assert "--diff" in out


def test_setup_dry_run_copies_nothing(checkout, capsys):
    root = checkout({"missing_one": IMPLEMENTED, "stale_one": IMPLEMENTED})
    _make_stale(root, "stale_one")
    stale_before = _target(root, "stale_one").read_text()

    assert setup.main(["--dry-run"]) == 0

    out = capsys.readouterr().out
    assert not _target(root, "missing_one").exists()
    assert _target(root, "stale_one").read_text() == stale_before
    assert "would create" in out
    assert "would refresh" in out
    assert "Would create 1, would refresh 1." in out
    assert "Restart Flask" not in out


def test_setup_warns_when_git_does_not_ignore_the_target(checkout, capsys):
    root = checkout({"sem_list": IMPLEMENTED})
    (root / ".gitignore").write_text("# nothing ignored\n")

    assert setup.main([]) == 0

    assert "git does NOT ignore these" in capsys.readouterr().out


def test_setup_tells_the_office_to_restart_flask(checkout, capsys):
    checkout({"sem_list": IMPLEMENTED})

    assert setup.main([]) == 0

    out = capsys.readouterr().out
    assert "Restart Flask" in out
    assert "/api/health/providers" in out


# --------------------------------------------------------------------------
# The shared discover()/Adapter now has one home
# --------------------------------------------------------------------------

def test_the_cli_reuses_the_runtime_adapter_type():
    """One tested copy of the traversal, not two that can drift apart."""
    from back_dev_home._runtime import office_template

    assert sync.Adapter is office_template.Adapter


def test_discover_drops_the_providers_segment_from_the_slug(checkout):
    checkout({
        "sem_list": IMPLEMENTED,
        "ebeam/hardware/providers/fdc": IMPLEMENTED,
    })

    assert [a.slug for a in sync.discover()] == ["ebeam/hardware/fdc", "sem_list"]


def test_discover_pairs_each_template_with_its_office_py(checkout):
    root = checkout({"sem_list": IMPLEMENTED})

    adapter = sync.discover()[0]

    assert adapter.template == _template(root, "sem_list")
    assert adapter.target == _target(root, "sem_list")
    assert adapter.name == "sem_list"
