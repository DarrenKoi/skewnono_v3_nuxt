"""The short-link store, exercised through data.py — the swap surface.

Tests go through ``data.py`` rather than a provider module so the same file
proves the contract for whichever adapter is active: at home that is the
in-memory mock, at the office the Redis adapter. What a provider owes the
caller is exactly what is pinned here — mint, resolve, and the behaviour of a
code nobody minted.

Determinism is part of the contract, not an optimisation: minting the same
screen twice must return the SAME code, so re-sharing a link a colleague
already has does not fork it into a second entry that expires on its own
schedule.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.short_links.contracts import ShortLink
from back_dev_home.short_links.data import create_short_link, resolve_short_link

TARGET = "/ebeam/cd-sem/skewvoir/analysis?lot=KPB266344&view=time-series"

mock_only = pytest.mark.skipif(
    get_data_provider("short_links") != "mock",
    reason="drives the mock's process-local dict; office answers from Redis",
)


@pytest.fixture(autouse=True)
def _clean_store():
    """Each test starts from an empty store. Mock-only — the office adapter's
    store is Redis and is never reset by a test run."""
    if get_data_provider("short_links") == "mock":
        from back_dev_home.short_links.providers import mock

        mock.reset_for_tests()
    yield


# ── mint ────────────────────────────────────────────────────────────────


def test_minting_returns_the_contract_shape():
    assert_matches(create_short_link(TARGET), ShortLink)


def test_a_minted_code_resolves_back_to_its_target():
    link = create_short_link(TARGET)
    assert resolve_short_link(link["code"])["target"] == TARGET


def test_minting_the_same_target_twice_returns_the_same_code():
    """Idempotence. Sharing the same screen again must not fork the store into
    a second entry with its own expiry — the colleague's existing link and the
    one just copied have to be the same link."""
    assert create_short_link(TARGET)["code"] == create_short_link(TARGET)["code"]


def test_different_targets_get_different_codes():
    a = create_short_link(TARGET)["code"]
    b = create_short_link(TARGET + "&mp=CD_TOP")["code"]
    assert a != b


def test_a_code_is_short_lowercase_and_unambiguous():
    """The point of the feature. Base32 also omits 0/1/8/9, so there is no
    O/0 or l/1 pair to misread when a code is retyped off a screenshot."""
    code = create_short_link(TARGET)["code"]
    assert 6 <= len(code) <= 16
    assert code.isalnum()
    assert code == code.lower()
    assert not set(code) & set("0189")


def test_a_minted_link_is_much_shorter_than_the_target_it_replaces():
    """The user-visible reason this feature exists: a six-MSR comparison link
    is ~500 chars of mostly repeated recipe/date text."""
    msrs = ",".join(
        f"20260509_ADI_CD_BIAS_MEAS_STD_KPB2663{n:02d}_ECDX2{n:02d}"
        for n in range(10, 16)
    )
    long_target = (
        "/ebeam/cd-sem/skewvoir/analysis"
        "?lot=KPB266310&recipe=ADI_CD_BIAS_MEAS_STD&eq=ECDX210"
        "&cap=2026-05-09T11%3A02%3A44&mp=CD_TOP&scope=set&view=time-series"
        f"&msr={msrs.split(',')[0]}&msrs={msrs}"
    )
    assert len(long_target) > 400

    code = create_short_link(long_target)["code"]
    assert len(f"/s/{code}") < 20


# ── resolve ─────────────────────────────────────────────────────────────


def test_an_unminted_code_resolves_to_none():
    """Not an exception: a stale or mistyped link is an expected, routine
    outcome that the route turns into a 404 page, not a 500."""
    assert resolve_short_link("zzzzzzzzzz") is None


def test_an_empty_code_resolves_to_none():
    assert resolve_short_link("") is None


def test_resolving_does_not_consume_the_link():
    """A shared link is read by many people, and by the same person twice."""
    code = create_short_link(TARGET)["code"]
    assert resolve_short_link(code) is not None
    assert resolve_short_link(code) is not None


# ── collision ───────────────────────────────────────────────────────────


@mock_only
def test_a_code_collision_lengthens_rather_than_overwriting(monkeypatch):
    """Two different targets hashing to the same prefix must NOT share a code —
    that would silently land one engineer on another's screen, which is worse
    than any error. Forced here by stubbing the digest, because a natural
    collision at this width is not reachable in a test.
    """
    from back_dev_home.short_links.providers import mock

    monkeypatch.setattr(mock, "_digest", lambda target: "aaaaaaaaaaaaaaaaaaaa")

    first = create_short_link("/a")["code"]
    second = create_short_link("/b")["code"]

    assert first != second
    assert resolve_short_link(first)["target"] == "/a"
    assert resolve_short_link(second)["target"] == "/b"
