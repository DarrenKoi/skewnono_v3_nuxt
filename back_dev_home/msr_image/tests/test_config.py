from back_dev_home.msr_image.config import load_config


def test_defaults_when_env_empty():
    cfg = load_config({})
    assert cfg.ftp_user == "hitachi"
    assert cfg.ftp_password == "hid"
    assert cfg.ftp_port == 21
    assert cfg.ftp_concurrency == 6
    assert cfg.ttl_hours == 72
    assert cfg.purge_hour == 3
    assert cfg.cache_prefix == "image_cache/"
    assert cfg.allowed_subnets == []


def test_env_overrides():
    cfg = load_config({
        "SKEWNONO_TOOL_FTP_USER": "svc",
        "SKEWNONO_TOOL_FTP_PASSWORD": "pw",
        "SKEWNONO_TOOL_FTP_CONCURRENCY": "10",
        "IMAGE_CACHE_TTL_HOURS": "48",
        "SKEWNONO_TOOL_SUBNETS": "10.0.0.0/8, 192.168.0.0/16",
    })
    assert cfg.ftp_user == "svc"
    assert cfg.ftp_password == "pw"
    assert cfg.ftp_concurrency == 10
    assert cfg.ttl_hours == 48
    assert cfg.allowed_subnets == ["10.0.0.0/8", "192.168.0.0/16"]


def test_blank_and_garbage_numeric_fall_back_to_defaults():
    cfg = load_config({
        "SKEWNONO_TOOL_FTP_TIMEOUT": "   ",
        "SKEWNONO_TOOL_FTP_CONCURRENCY": "--3",
        "IMAGE_CACHE_TTL_HOURS": "abc",
    })
    assert cfg.ftp_timeout == 8.0
    assert cfg.ftp_concurrency == 6
    assert cfg.ttl_hours == 72


def test_no_accounts_declared_means_one_account_serves_the_fleet():
    assert load_config({}).ftp_accounts == {}


def test_accounts_parse_by_fab_and_by_tool():
    cfg = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": "M16=svc:pw, MCD1234=other:pw2"})
    assert cfg.ftp_accounts == {"M16": ("svc", "pw"), "MCD1234": ("other", "pw2")}


def test_a_password_may_contain_a_colon():
    # Only the FIRST colon separates; a generated password containing one must
    # survive intact or the tool rejects a login that looks correct in the env.
    cfg = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": "M16=svc:a:b:c"})
    assert cfg.ftp_accounts["M16"] == ("svc", "a:b:c")


def test_a_malformed_entry_is_skipped_not_raised():
    # A typo in one tool's entry must not take the feature down at import: the
    # other tools' accounts are still correct and still worth serving.
    cfg = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": "broken,M16=svc:pw,=x:y,A=nopass"})
    assert cfg.ftp_accounts == {"M16": ("svc", "pw")}


def _lookup(monkeypatch, accounts, rows):
    from back_dev_home.msr_image import config as config_mod

    config_mod._roster.clear()  # the roster is TTL-cached across calls
    monkeypatch.setattr(
        "back_dev_home.sem_list.data.get_sem_list", lambda: rows, raising=True
    )
    cfg = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": accounts})
    return config_mod.ftp_account_lookup(cfg)


_ROWS = [
    {"eqp_ip": "10.0.0.1", "eqp_id": "MCD1234", "fab_name": "M16"},
    {"eqp_ip": "10.0.0.2", "eqp_id": "MCD9999", "fab_name": "M16"},
    {"eqp_ip": "10.0.0.3", "eqp_id": "VCD0001", "fab_name": "M14"},
]


def test_an_unconfigured_fleet_never_reads_the_roster(monkeypatch):
    # The roster read is two Redis keys and a parquet decode at the office, and
    # every deployment is unconfigured until the first AMAT tool arrives.
    def explode():
        raise AssertionError("get_sem_list must not be called")

    monkeypatch.setattr(
        "back_dev_home.sem_list.data.get_sem_list", explode, raising=True
    )
    from back_dev_home.msr_image.config import ftp_account_lookup

    assert ftp_account_lookup(load_config({}))("10.0.0.1") == {}


def test_a_fab_entry_covers_every_tool_in_that_fab(monkeypatch):
    account = _lookup(monkeypatch, "M16=svc:pw", _ROWS)
    assert account("10.0.0.1") == {"user": "svc", "password": "pw"}
    assert account("10.0.0.2") == {"user": "svc", "password": "pw"}
    # A fab with no entry keeps the downloader's own account.
    assert account("10.0.0.3") == {}


def test_a_tool_entry_beats_its_fabs(monkeypatch):
    account = _lookup(monkeypatch, "M16=svc:pw,MCD1234=tool:tp", _ROWS)
    assert account("10.0.0.1") == {"user": "tool", "password": "tp"}
    assert account("10.0.0.2") == {"user": "svc", "password": "pw"}


def test_the_key_match_ignores_case(monkeypatch):
    # A case slip would resolve to the fleet default silently -- a wrong-account
    # login rather than an error, which is what this mechanism exists to stop.
    account = _lookup(monkeypatch, "m16=svc:pw", _ROWS)
    assert account("10.0.0.1") == {"user": "svc", "password": "pw"}


def test_a_tool_missing_from_the_roster_falls_back_to_the_fleet(monkeypatch):
    account = _lookup(monkeypatch, "M16=svc:pw", _ROWS)
    assert account("10.9.9.9") == {}


def test_the_roster_is_read_once_across_lookups(monkeypatch):
    # fetch_image resolves an account per image; at the office each roster read
    # is two Redis keys plus a parquet decode, so a gallery would otherwise pay
    # one round-trip per thumbnail.
    from back_dev_home.msr_image import config as config_mod

    calls = []
    config_mod._roster.clear()
    monkeypatch.setattr(
        "back_dev_home.sem_list.data.get_sem_list",
        lambda: (calls.append(1), _ROWS)[1],
        raising=True,
    )
    cfg = load_config({"SKEWNONO_TOOL_FTP_ACCOUNTS": "M16=svc:pw"})
    for _ in range(3):
        assert config_mod.ftp_account_lookup(cfg)("10.0.0.1") == {
            "user": "svc",
            "password": "pw",
        }
    assert len(calls) == 1
