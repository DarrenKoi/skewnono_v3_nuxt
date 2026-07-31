"""The mock store's own invariants — mock-only, never run against office.

The contract gate (test_contract.py) drives whichever provider is active and so
cannot assert anything about `_tokens`/`_by_hash`. What needs asserting here is
the reason those two dicts are locked at all: the home dev server answers every
request on a FRESH thread, each create touches both dicts, and touch_last_used
is a read-modify-write.

`test_listing_while_others_create_never_raises` is the one that genuinely
fails if the lock is removed, and only because of
`hair_trigger_thread_switching` below: at the default 5 ms switch interval an
unlocked `list_tokens` almost always finishes its comprehension inside one GIL
slice, so the race passed 40/40 runs and proved nothing. Preempting every
microsecond makes it `RuntimeError: dictionary changed size during iteration`
on the first attempt, every time (verified by re-running this module against a
stubbed no-op lock). The other two assert end-state invariants that CPython's
GIL happens to preserve even unlocked — they are cheap guards against a future
change that makes the store genuinely reorderable, not lock detectors.
"""

import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from back_dev_home.api_tokens.providers import mock

OWNER = "concurrency-user"
WRITERS = 200


@pytest.fixture(autouse=True)
def clean_store():
    mock.reset_for_tests()
    yield
    mock.reset_for_tests()


@pytest.fixture(autouse=True)
def hair_trigger_thread_switching():
    """Preempt threads every microsecond so interleavings actually happen.

    Restored afterwards — leaving it set would slow every later test in the
    session down for no benefit.
    """
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(previous)


def test_concurrent_creates_leave_both_indexes_consistent():
    """`create_token` writes `_tokens` then `_by_hash`. Every secret it handed
    out must resolve, and the two indexes must agree on the population."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda i: mock.create_token(OWNER, f"t{i}"), range(WRITERS))
        )

    assert len(results) == WRITERS
    for view, plaintext in results:
        row = mock.find_by_plaintext(plaintext)
        assert row is not None, view["id"]
        assert row.id == view["id"]

    listed = mock.list_tokens(OWNER)
    assert len({row["id"] for row in listed}) == WRITERS


def test_listing_while_others_create_never_raises():
    """The regression this lock was added for: `list_tokens` iterates `_tokens`,
    and an unguarded insert mid-iteration raises — a 500 on a plain GET."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        writers = [
            pool.submit(mock.create_token, OWNER, f"w{i}") for i in range(WRITERS)
        ]
        readers = [pool.submit(mock.list_tokens, OWNER) for _ in range(WRITERS)]
        for future in writers + readers:
            future.result()  # re-raises whatever a worker hit

    assert len(mock.list_tokens(OWNER)) == WRITERS


def test_concurrent_touch_and_revoke_do_not_corrupt_the_store():
    """touch_last_used is a read-modify-write on a row a revoke may be deleting.
    Neither may raise, and the revoked token must leave both indexes."""
    view, plaintext = mock.create_token(OWNER, "hot")
    token_id = view["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(mock.touch_last_used, token_id) for _ in range(WRITERS)]
        futures.append(pool.submit(mock.revoke_token, OWNER, token_id))
        for future in futures:
            future.result()

    assert mock.list_tokens(OWNER) == []
    assert mock.find_by_plaintext(plaintext) is None
