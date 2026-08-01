"""Lazy chat runtime selection."""

from importlib import import_module

from back_dev_home.chat import config
from back_dev_home.chat.runtime.contracts import RuntimeRequest, RuntimeResult


def invoke(request: RuntimeRequest) -> RuntimeResult:
    """Invoke only the runtime selected by server configuration."""
    provider = import_module(
        f"back_dev_home.chat.runtime.providers.{config.get_runtime_name()}"
    )
    return provider.invoke(request)
