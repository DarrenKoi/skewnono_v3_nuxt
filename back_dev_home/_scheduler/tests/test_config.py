from back_dev_home._scheduler.config import SchedulerConfig, load_scheduler_config


def test_defaults_when_env_is_empty():
    cfg = load_scheduler_config({})
    assert cfg.lock_ttl == 600
    assert cfg.log_list_max == 500
    assert cfg.timezone == "Asia/Seoul"
    assert cfg.lock_key_prefix == "skewnono:scheduler:lock:"
    assert cfg.log_list_key == "skewnono:scheduler:logs"


def test_env_overrides_are_read():
    cfg = load_scheduler_config(
        {"SKEWNONO_SCHEDULER_LOCK_TTL": "90", "SKEWNONO_SCHEDULER_LOG_MAX": "40"}
    )
    assert cfg.lock_ttl == 90
    assert cfg.log_list_max == 40


def test_garbage_env_falls_back_to_the_default():
    # A typo'd env var must not take the scheduler down at boot -- it is
    # plumbing, and refusing to start would cost more than one bad value.
    cfg = load_scheduler_config({"SKEWNONO_SCHEDULER_LOCK_TTL": "not-a-number"})
    assert cfg.lock_ttl == 600


def test_config_is_frozen():
    cfg = load_scheduler_config({})
    try:
        cfg.lock_ttl = 1  # type: ignore[misc]
    except Exception as exc:
        assert type(exc).__name__ == "FrozenInstanceError"
    else:
        raise AssertionError("SchedulerConfig must be frozen")


def test_is_a_schedulerconfig():
    assert isinstance(load_scheduler_config({}), SchedulerConfig)
