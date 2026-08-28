"""Which account each tool is reached with, and that the specs actually carry it.

The wiring half matters as much as the resolution half: a dropped
``**account(...)`` at a spec site is not an error, it is a successful login as
the wrong account, so it has to be asserted rather than assumed.
"""

from types import SimpleNamespace

import pytest

from back_dev_home.msr_image import ftp_accounts
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.ftp_accounts import account_for, ftp_account_lookup
from back_dev_home.msr_image.providers import office_example as office
from back_dev_home.msr_image.tests.test_office_template import FakeFleet


_ROWS = [
    {"eqp_ip": "10.0.0.1", "eqp_id": "MCD1234", "fab_name": "M16"},
    {"eqp_ip": "10.0.0.2", "eqp_id": "MCD9999", "fab_name": "M16"},
    {"eqp_ip": "10.0.0.3", "eqp_id": "VCD0001", "fab_name": "M14"},
]


# ── resolution (pure over rows, no roster source) ────────────────────────────


def test_a_fab_entry_covers_every_tool_in_that_fab():
    accounts = {"M16": ("svc", "pw")}
    assert account_for(_ROWS, accounts, "10.0.0.1") == {"user": "svc", "password": "pw"}
    assert account_for(_ROWS, accounts, "10.0.0.2") == {"user": "svc", "password": "pw"}
    # A fab with no entry keeps the downloader's own account.
    assert account_for(_ROWS, accounts, "10.0.0.3") == {}


def test_a_tool_entry_beats_its_fabs():
    accounts = {"M16": ("svc", "pw"), "MCD1234": ("tool", "tp")}
    assert account_for(_ROWS, accounts, "10.0.0.1") == {"user": "tool", "password": "tp"}
    assert account_for(_ROWS, accounts, "10.0.0.2") == {"user": "svc", "password": "pw"}


def test_the_key_match_ignores_case():
    # Tested through load_config because that is where normalisation happens:
    # _accounts() upper-cases the declared keys, account_for upper-cases the
    # row's. A case slip surviving to a lookup would resolve to the fleet
    # default silently -- a wrong-account login rather than an error.
    accounts = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": "m16=svc:pw"}).ftp_accounts
    assert account_for(_ROWS, accounts, "10.0.0.1") == {"user": "svc", "password": "pw"}


def test_a_tool_missing_from_the_roster_falls_back_to_the_fleet():
    assert account_for(_ROWS, {"M16": ("svc", "pw")}, "10.9.9.9") == {}


# ── the office-side loader ───────────────────────────────────────────────────


@pytest.fixture
def roster(monkeypatch):
    """Serve ``_ROWS`` as the sem_list roster, counting the reads."""
    calls = []
    ftp_accounts._ROSTER.clear()
    monkeypatch.setattr(
        "back_dev_home.sem_list.data.get_sem_list",
        lambda: (calls.append(1), _ROWS)[1],
        raising=True,
    )
    yield calls
    ftp_accounts._ROSTER.clear()


def test_an_unconfigured_fleet_never_reads_the_roster(roster):
    # Two Redis keys and a parquet decode at the office, and every deployment
    # is unconfigured until the first AMAT tool arrives.
    assert ftp_account_lookup(load_config({}))("10.0.0.1") == {}
    assert roster == []


def test_the_roster_is_read_once_across_lookups(roster):
    cfg = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": "M16=svc:pw"})
    for _ in range(3):
        assert ftp_account_lookup(cfg)("10.0.0.1") == {"user": "svc", "password": "pw"}
    assert len(roster) == 1


def test_a_refresh_failure_serves_the_previous_roster(monkeypatch):
    ftp_accounts._ROSTER.clear()
    state = {"ok": True}

    def get_sem_list():
        if not state["ok"]:
            raise RuntimeError("redis down")
        return _ROWS

    monkeypatch.setattr(
        "back_dev_home.sem_list.data.get_sem_list", get_sem_list, raising=True
    )
    cfg = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": "M16=svc:pw"})
    assert ftp_account_lookup(cfg)("10.0.0.1") == {"user": "svc", "password": "pw"}

    state["ok"] = False
    monkeypatch.setattr(ftp_accounts, "_ROSTER_TTL_SECONDS", -1.0)
    # Blanking a tool's account on an upstream hiccup would log it in as the
    # fleet account -- worse than serving a roster a few minutes old.
    assert ftp_account_lookup(cfg)("10.0.0.1") == {"user": "svc", "password": "pw"}
    ftp_accounts._ROSTER.clear()


def test_the_first_load_failure_raises_rather_than_guessing(monkeypatch):
    ftp_accounts._ROSTER.clear()

    def boom():
        raise RuntimeError("redis down")

    monkeypatch.setattr(
        "back_dev_home.sem_list.data.get_sem_list", boom, raising=True
    )
    cfg = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": "M16=svc:pw"})
    with pytest.raises(RuntimeError):
        ftp_account_lookup(cfg)("10.0.0.1")


# ── wiring: the specs the adapters actually build ────────────────────────────


class RecordingFleet(FakeFleet):
    """FakeFleet that keeps every spec it was handed."""

    specs = []

    def list_dirs(self, specs):
        RecordingFleet.specs += specs
        return super().list_dirs(specs)

    def download(self, specs, *, on_file=None):
        RecordingFleet.specs += specs
        return super().download(specs, on_file=on_file)


@pytest.fixture
def recording(monkeypatch, roster):
    RecordingFleet.specs = []
    monkeypatch.setattr(office, "FtpFleetDownloader", RecordingFleet)
    return RecordingFleet


def _configured():
    from dataclasses import replace

    return replace(office._test_config(), ftp_accounts={"M16": ("svc", "pw")})


def test_every_msr_image_spec_carries_the_tools_account(recording):
    cfg = _configured()
    office.list_images("10.0.0.1", "ADI", "MSR_1", _config=cfg)
    office.fetch_image(ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg"), _config=cfg)
    office.download_all(
        "10.0.0.1", "ADI", "MSR_1", ["shot01.jpeg", "shot02.jpeg"],
        on_file=lambda *_: None, concurrency=1, _config=cfg,
    )
    assert recording.specs, "no spec reached the downloader"
    assert all((s.user, s.password) == ("svc", "pw") for s in recording.specs)


def test_a_tool_the_fleet_account_covers_sends_no_override(recording):
    office.list_images("10.0.0.3", "ADI", "MSR_1", _config=_configured())
    assert [(s.user, s.password) for s in recording.specs] == [(None, None)]


def test_every_recipe_search_spec_carries_the_tools_account(monkeypatch, roster):
    """The other adapter on the same mechanism, and the one whose office.py is
    a stale copy in most checkouts -- so the wiring is asserted, not assumed."""
    from back_dev_home.ebeam.recipe_search.providers import office_example as rs

    seen = []

    class Fleet:
        def __init__(self, **kw):
            pass

        def download(self, specs, *, on_file=None):
            seen.extend(specs)
            return SimpleNamespace(files=[], failures=[], grouped=dict)

        def list_dirs(self, specs):
            seen.extend(specs)
            return SimpleNamespace(listings=[], failures=[], grouped=dict)

    monkeypatch.setattr(rs, "_transport", lambda: rs._Transport(
        Fleet, office.HostSpec, office.ListDir, "test"
    ))
    monkeypatch.setattr(
        "back_dev_home.msr_image.config.load_config", _configured, raising=True
    )
    key = ("10.0.0.1", "ADI", "IDW1", "IDP1")
    rs._fetch_many({key: ["a.jpeg"]})
    rs._list_raw_dirs([key])
    assert seen, "no spec reached the downloader"
    assert all((s.user, s.password) == ("svc", "pw") for s in seen)
