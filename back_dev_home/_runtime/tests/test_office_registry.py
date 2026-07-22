"""Filesystem discovery of office adapters.

Every test builds a fake package tree under tmp_path rather than reading the
real repo: at home NO providers/office.py exists anywhere (it is gitignored
and only ever created at the office), so the real tree cannot exercise the
office-ready paths at all.
"""

import pytest

from back_dev_home._runtime import office_registry


@pytest.fixture
def fake_tree(tmp_path, monkeypatch):
    """Build back_dev_home/<path>/providers/<files> trees and point _ROOT at it."""
    root = tmp_path / "back_dev_home"

    def build(spec: dict[str, list[str]]):
        for rel, filenames in spec.items():
            providers = root / rel / "providers"
            providers.mkdir(parents=True, exist_ok=True)
            for filename in filenames:
                (providers / filename).write_text("")
        monkeypatch.setattr(office_registry, "_ROOT", root)
        office_registry.reset_cache()
        return root

    yield build
    office_registry.reset_cache()


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
    assert {"sem_list", "storage", "hardware", "device_statistics"} <= set(real)
    assert len(real) == 20
    # Whatever this machine has must at least be real features — an office.py
    # anywhere else would be a stray copy the orphan guard should have caught.
    assert set(office_registry.office_ready()) <= set(real)
