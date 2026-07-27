import pytest

from back_dev_home._logging.target import (
    LoggingConfigurationError,
    resolve_logging_target,
)


@pytest.mark.parametrize(
    ("value", "alias"),
    [
        ("local", "skewnono_logging_local"),
        ("production", "skewnono_logging"),
    ],
)
def test_target_resolves_one_alias(value, alias):
    target = resolve_logging_target({"SKEWNONO_LOG_ENV": value})
    assert target.environment == value
    assert target.deployment == value
    assert target.alias == alias


@pytest.mark.parametrize("value", ["", "cloud", "LOCAL"])
def test_missing_or_invalid_target_fails_closed(value):
    with pytest.raises(LoggingConfigurationError, match="SKEWNONO_LOG_ENV"):
        resolve_logging_target({"SKEWNONO_LOG_ENV": value})
