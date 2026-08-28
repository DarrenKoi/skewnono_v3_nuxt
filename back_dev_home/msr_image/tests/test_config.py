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
