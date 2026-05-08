"""Base MinIO config, client factory, and shared service class."""

import importlib
import os
from dataclasses import dataclass, field, replace
from typing import Any, Self

_CONNECTION_ATTRS = {
    "endpoint": "ENDPOINT",
    "access_key": "ACCESS_KEY",
    "secret_key": "SECRET_KEY",
    "secure": "SECURE",
    "region": "REGION",
    "cert_check": "CERT_CHECK",
}

_OBJECT_ATTRS = {
    "bucket": "BUCKET",
    "prefix": "PREFIX",
}


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _module_values(attr_map: dict[str, str]) -> dict[str, Any]:
    """Return non-None constants defined in ``minio_handler.minio_config``.

    Missing module or missing attributes are silently ignored so the package
    works on a fresh clone where the gitignored config file is absent.
    """

    module_name = f"{__package__}.minio_config"
    try:
        mod = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise
        return {}

    values: dict[str, Any] = {}
    for key, attr in attr_map.items():
        if not hasattr(mod, attr):
            continue
        value = getattr(mod, attr)
        if value is None:
            continue
        values[key] = value
    return values


@dataclass(slots=True)
class MinioConfig:
    """Connection settings for a MinIO / S3-compatible endpoint."""

    endpoint: str = "localhost:9000"
    access_key: str | None = None
    secret_key: str | None = None
    secure: bool = False
    region: str | None = None
    cert_check: bool = True
    extra_client_kwargs: dict[str, Any] = field(default_factory=dict)

    def to_client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "secure": self.secure,
            "cert_check": self.cert_check,
        }

        if self.region:
            kwargs["region"] = self.region

        kwargs.update(self.extra_client_kwargs)
        return kwargs

    @classmethod
    def from_env(cls, **overrides: Any) -> Self:
        values: dict[str, Any] = _module_values(_CONNECTION_ATTRS)

        endpoint = os.getenv("MINIO_ENDPOINT")
        if endpoint:
            values["endpoint"] = endpoint

        access_key = os.getenv("MINIO_ACCESS_KEY")
        if access_key is not None:
            values["access_key"] = access_key or None

        secret_key = os.getenv("MINIO_SECRET_KEY")
        if secret_key is not None:
            values["secret_key"] = secret_key or None

        secure = os.getenv("MINIO_SECURE")
        if secure is not None:
            values["secure"] = _parse_bool(secure)

        region = os.getenv("MINIO_REGION")
        if region:
            values["region"] = region

        cert_check = os.getenv("MINIO_CERT_CHECK")
        if cert_check is not None:
            values["cert_check"] = _parse_bool(cert_check)

        values.update(overrides)
        return cls(**values)


def load_config(**overrides: Any) -> MinioConfig:
    """Load MinIO connection settings from the environment."""

    return MinioConfig.from_env(**overrides)


def _minio_class() -> type[Any]:
    from minio import Minio

    return Minio


def create_client(
    config: MinioConfig | None = None,
    **overrides: Any,
) -> Any:
    """Create and return a configured MinIO client."""

    if config is None:
        config = load_config(**overrides)
    elif overrides:
        config = replace(config, **overrides)

    return _minio_class()(**config.to_client_kwargs())


class MinioBase:
    """Base service that owns a MinIO client, default bucket, and key prefix."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        config: MinioConfig | None = None,
        bucket: str | None = None,
        prefix: str | None = None,
        **client_overrides: Any,
    ) -> None:
        module_defaults = _module_values(_OBJECT_ATTRS)
        resolved_bucket = bucket if bucket is not None else module_defaults.get("bucket")
        resolved_prefix = prefix if prefix is not None else module_defaults.get("prefix")

        self.default_bucket = resolved_bucket
        self.default_prefix = resolved_prefix.strip("/") if resolved_prefix else None

        if client is not None and client_overrides:
            raise ValueError(
                "Client overrides cannot be used when an existing client instance "
                "is supplied."
            )

        if client is None:
            if config is None:
                self.config = load_config(**client_overrides)
            elif client_overrides:
                self.config = replace(config, **client_overrides)
            else:
                self.config = config

            self.client = create_client(config=self.config)
        else:
            self.client = client
            self.config = config

    def use_bucket(self, bucket: str) -> Self:
        """Set the default bucket and return the service for chaining."""

        self.default_bucket = bucket
        return self

    def use_prefix(self, prefix: str | None) -> Self:
        """Set the default key prefix and return the service for chaining."""

        self.default_prefix = prefix.strip("/") if prefix else None
        return self

    def _resolve_bucket(self, bucket: str | None = None) -> str:
        resolved = bucket or self.default_bucket
        if resolved is None:
            raise ValueError("A bucket name is required for this operation.")
        return resolved

    def _resolve_key(self, key: str, *, prefix: str | None = None) -> str:
        active_prefix = prefix if prefix is not None else self.default_prefix
        cleaned_key = key.lstrip("/")
        if not active_prefix:
            return cleaned_key
        return f"{active_prefix.strip('/')}/{cleaned_key}"
