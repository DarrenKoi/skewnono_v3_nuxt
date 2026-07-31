"""The mock exception store's failure paths, which the contract gate and the
route tests both run past rather than into.

The store is the mock's whole reason to be trusted at the office: it is an
mtime-keyed JSON file precisely so grants propagate across `gunicorn -w N`
workers (see MIGRATION.md — this is why the office switch is discretionary
here and mandatory for `api_tokens`). Two rules make that safe, and neither is
exercised by a happy-path test:

* **reads fail safe** — an unreadable file is an empty store for that one call,
  nothing cached, so the next call retries. A read failure must not 500 every
  request from an X-member.
* **writes fail closed and atomic** — a mutation against an unreadable store is
  refused rather than persisting a half-loaded view over the real file, and a
  failed write leaves NOTHING changed, in memory or on disk.

These call `providers.mock` directly: `_store_path` / `reset_for_tests` are
mock-only helpers and the failure modes are the mock's own (a corrupt local
file), not the office adapter's (a Redis that is not answering).
"""

import json

import pytest

from back_dev_home.access_control.providers import mock

BLOCKED = "X9999999"


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A throwaway store file, isolated from the gitignored real one."""
    path = tmp_path / "access_exceptions.json"
    monkeypatch.setenv("SKEWNONO_ACCESS_EXCEPTIONS_FILE", str(path))
    mock.reset_for_tests()
    yield path
    mock.reset_for_tests()


def _grant(user_id: str = BLOCKED) -> dict:
    return mock.add_exception(user_id)


def test_missing_file_is_a_normal_empty_store(store):
    assert not store.exists()
    assert mock.list_exceptions() == []
    assert mock.is_blocked(BLOCKED) is True


def test_corrupt_file_reads_fail_safe_but_mutations_are_refused(store):
    store.write_text("{not json", encoding="utf-8")

    # Reads: this call sees an empty store instead of raising...
    assert mock.list_exceptions() == []
    assert mock.is_blocked(BLOCKED) is True

    # ...but a mutation must not persist that empty view over the real file.
    with pytest.raises(mock.StoreUnavailableError):
        _grant()
    with pytest.raises(mock.StoreUnavailableError):
        mock.remove_exception(BLOCKED)
    assert store.read_text(encoding="utf-8") == "{not json"


def test_a_read_failure_is_not_cached_so_the_next_call_retries(store):
    store.write_text("{not json", encoding="utf-8")
    assert mock.list_exceptions() == []  # fail-safe, nothing cached

    store.write_text(
        json.dumps({"exceptions": [{"user_id": BLOCKED, "granted_at": "2026-07-14T00:00:00Z"}]}),
        encoding="utf-8",
    )
    # No reset_for_tests(): a repaired file must be picked up on the very next
    # call, or one corrupt write would wedge the store until a restart.
    assert [row["user_id"] for row in mock.list_exceptions()] == [BLOCKED]
    assert mock.is_blocked(BLOCKED) is False


def test_an_unstatable_path_fails_safe_to_read_and_closed_to_write(tmp_path, monkeypatch):
    # A regular file where a parent directory is expected: stat() raises
    # NotADirectoryError — an OSError that is NOT FileNotFoundError, so it is
    # a real fault rather than "no store yet".
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("SKEWNONO_ACCESS_EXCEPTIONS_FILE", str(blocker / "store.json"))
    mock.reset_for_tests()
    try:
        assert mock.list_exceptions() == []
        assert mock.is_blocked(BLOCKED) is True
        with pytest.raises(mock.StoreUnavailableError):
            _grant()
    finally:
        mock.reset_for_tests()


@pytest.mark.parametrize("mutate", ["add", "remove"])
def test_a_failed_write_changes_nothing_in_memory_or_on_disk(store, monkeypatch, mutate):
    """The property that replaced the hand-rolled rollback: both mutators write
    the candidate row set FIRST and commit to the cache only once the file has
    it, so a write failure cannot leave the two disagreeing."""
    _grant()  # one committed grant to mutate against
    before_file = store.read_text(encoding="utf-8")
    before_rows = mock.list_exceptions()

    def _explode(rows):
        raise OSError("disk full")

    monkeypatch.setattr(mock, "_save_locked", _explode)

    with pytest.raises(OSError):
        if mutate == "add":
            _grant("X7777777")
        else:
            mock.remove_exception(BLOCKED)

    # No monkeypatch.undo() — it would revert this test's store-path env var
    # too, and the reads below never touch _save_locked anyway.
    assert mock.list_exceptions() == before_rows
    assert store.read_text(encoding="utf-8") == before_file
    # And the enforcement path agrees with both.
    assert mock.is_blocked(BLOCKED) is False


def test_a_repeat_grant_is_idempotent_and_writes_nothing(store, monkeypatch):
    first = _grant()

    def _explode(rows):
        raise AssertionError("a repeat grant must not rewrite the file")

    monkeypatch.setattr(mock, "_save_locked", _explode)
    assert _grant() == first  # same row, original granted_at
