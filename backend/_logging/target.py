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

# Chat conversations carry message content, which the activity index must
# never hold, so they get their own alias family selected by the same
# SKEWNONO_LOG_ENV switch — one env answer, two content-isolated indices.
_CHAT_CONVERSATION_TARGETS = {
    "local": LoggingTarget("local", "skewnono_chat_logging_local", "local"),
    "production": LoggingTarget("production", "skewnono_chat_logging", "production"),
}


def _resolve(
    targets: Mapping[str, LoggingTarget],
    values: Mapping[str, str] | None,
) -> LoggingTarget:
    source = environ if values is None else values
    raw = source.get("SKEWNONO_LOG_ENV", "")
    try:
        return targets[raw]
    except KeyError as exc:
        raise LoggingConfigurationError(
            "SKEWNONO_LOG_ENV must be 'local' or 'production'"
        ) from exc


def resolve_logging_target(
    values: Mapping[str, str] | None = None,
) -> LoggingTarget:
    return _resolve(_TARGETS, values)


def resolve_chat_conversation_target(
    values: Mapping[str, str] | None = None,
) -> LoggingTarget:
    return _resolve(_CHAT_CONVERSATION_TARGETS, values)
