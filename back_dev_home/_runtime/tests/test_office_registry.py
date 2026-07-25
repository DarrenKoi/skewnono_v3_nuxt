"""Filesystem discovery of office adapters.

The fake_tree factory and env scrubbing live in conftest.py.
"""

import pytest

from back_dev_home._runtime import data_provider, office_registry


def test_feature_slug_is_the_directory_name_at_any_depth(fake_tree):
    fake_tree({
        "sem_list": ["mock.py"],
        "ebeam/hitachi/storage": ["mock.py"],
        "ebeam/cdsem/device_statistics": ["mock.py"],
    })
    assert set(office_registry.features()) == {
        "sem_list", "storage", "device_statistics",
    }


def test_office_ready_lists_only_features_with_an_office_adapter(fake_tree):
    fake_tree({
        "sem_list": ["mock.py", "office.py"],
        "chat": ["mock.py"],
    })
    assert set(office_registry.office_ready()) == {"sem_list"}


def test_per_tab_adapters_never_enter_the_global_registry(fake_tree):
    """The feature/tab boundary. hardware/providers/fdc/office.py must NOT
    register 'fdc' — that file is hardware's private business, resolved by
    its own _tab() fallback. The glob enforces this because 'fdc' is not
    literally named 'providers'."""
    root = fake_tree({"ebeam/hitachi/hardware": ["mock.py", "office.py"]})
    tab = root / "ebeam/hitachi/hardware/providers/fdc"
    tab.mkdir(parents=True)
    (tab / "office.py").write_text("")
    (tab / "mock.py").write_text("")
    office_registry.reset_cache()

    assert set(office_registry.office_ready()) == {"hardware"}
    assert "fdc" not in office_registry.features()


def test_underscore_prefixed_directories_are_skipped(fake_tree):
    fake_tree({"_internal/scratch": ["mock.py"], "sem_list": ["mock.py"]})
    assert set(office_registry.features()) == {"sem_list"}


def test_duplicate_slug_raises_with_both_paths(fake_tree):
    fake_tree({
        "ebeam/hitachi/hardware": ["mock.py"],
        "ebeam/cdsem/hardware": ["mock.py"],
    })
    with pytest.raises(RuntimeError) as exc:
        office_registry.features()
    message = str(exc.value)
    assert "hardware" in message
    assert "ebeam/hitachi/hardware" in message
    assert "ebeam/cdsem/hardware" in message


def test_a_duplicate_slug_reaches_the_boot_path_with_both_paths_named(
    fake_tree, monkeypatch
):
    """The guard above is only useful if boot walks into it.

    Before serving anything, create_app() calls validate_env() and then the
    resolve_all() behind the boot table — both reach this scan, and neither may
    reduce the diagnosis to something the reader cannot act on. Adding a second
    `hardware/` under another vendor is how this happens in practice, and the
    two directories are indistinguishable by slug, so the message has to name
    both paths; anything less leaves someone grepping for a directory name that
    matches twice. Refusing to start is the right outcome rather than a wrong
    guess: resolution has no correct answer here.
    """
    fake_tree({
        "ebeam/hitachi/hardware": ["mock.py"],
        "ebeam/cdsem/hardware": ["mock.py"],
    })
    # Set so the failure is essential to validate_env(), not incidental: this
    # variable can only mean one of the two directories, so the scan error is
    # what it must report however the readiness lookup is ordered.
    monkeypatch.setenv("SKEWNONO_HARDWARE_PROVIDER", "office")

    for boot_call in (data_provider.validate_env, data_provider.resolve_all):
        with pytest.raises(RuntimeError) as exc:
            boot_call()
        message = str(exc.value)
        assert "Duplicate feature slug 'hardware'" in message
        assert "back_dev_home/ebeam/hitachi/hardware" in message
        assert "back_dev_home/ebeam/cdsem/hardware" in message


def test_office_adapter_without_a_mock_sibling_raises(fake_tree):
    fake_tree({"orphan": ["office.py"], "sem_list": ["mock.py"]})
    with pytest.raises(RuntimeError) as exc:
        office_registry.office_ready()
    assert "orphan" in str(exc.value)


def test_repo_path_is_relative_to_the_repo_root(fake_tree):
    fake_tree({"ebeam/hitachi/storage": ["mock.py"]})
    directory = office_registry.features()["storage"]
    assert office_registry.repo_path(directory) == (
        "back_dev_home/ebeam/hitachi/storage"
    )


def test_real_repo_scan_is_self_consistent():
    """Sanity check against the actual tree, not a fixture.

    office_ready() is deliberately NOT asserted to be empty here. office.py is
    gitignored, so which adapters exist is a property of the machine running
    the tests — this Mac mini has six, written while developing them. That is
    harmless because home resolves to mock MODE; safety rests on the mode, not
    on the absence of adapters.
    """
    office_registry.reset_cache()
    real = office_registry.features()
    # Named features, not a count: adding a feature is routine and must not
    # fail an unrelated test. These four span the nesting depths that exist
    # (top level, ebeam/hitachi/, ebeam/cdsem/).
    assert {"sem_list", "storage", "hardware", "device_statistics"} <= set(real)
    # Whatever this machine has must at least be real features — an office.py
    # anywhere else would be a stray copy the orphan guard should have caught.
    assert set(office_registry.office_ready()) <= set(real)
