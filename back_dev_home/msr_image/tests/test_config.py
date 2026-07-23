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
