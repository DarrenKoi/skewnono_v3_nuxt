"""Resolve the one OpenSearch logging target selected for this process."""

from dataclasses import dataclass
from os import environ
from typing import Literal, Mapping

LoggingEnvironment = Literal["local", "production"]


class LoggingConfigurationError(RuntimeError):
    """Raised when OpenSearch logging has no valid environment target."""


@dataclass(frozen=True)
class LoggingTarget:
    environment: LoggingEnvironment
    alias: str
    deployment: str


_TARGETS = {
    "local": LoggingTarget("local", "skewnono_logging_local", "local"),
    "production": LoggingTarget("production", "skewnono_logging", "production"),
}


def resolve_logging_target(
    values: Mapping[str, str] | None = None,
) -> LoggingTarget:
    source = environ if values is None else values
    raw = source.get("SKEWNONO_LOG_ENV", "")
    try:
        return _TARGETS[raw]
    except KeyError as exc:
        raise LoggingConfigurationError(
            "SKEWNONO_LOG_ENV must be 'local' or 'production'"
        ) from exc
