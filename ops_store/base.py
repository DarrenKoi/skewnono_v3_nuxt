"""Base OpenSearch config, client factory, and shared service class."""

import os
from dataclasses import dataclass, field, replace
from typing import Any, Self


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


@dataclass(slots=True)
class OSConfig:
    """Connection settings for an OpenSearch cluster."""

    host: str = "localhost"
    port: int = 443
    user: str | None = "admin"
    password: str | None = "admin"
    use_ssl: bool = True
    verify_certs: bool = False
    ssl_show_warn: bool = False
    ca_certs: str | None = None
    bulk_chunk: int = 500
    timeout: int = 30
    max_retries: int = 3
    retry_on_timeout: bool = True
    http_compress: bool = True
    extra_client_kwargs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if bool(self.user) != bool(self.password):
            raise ValueError(
                "OSConfig requires both user and password when basic "
                "authentication is enabled."
            )

    @property
    def http_auth(self) -> tuple[str, str] | None:
        if self.user and self.password:
            return (self.user, self.password)
        return None

    @property
    def hosts(self) -> list[dict[str, Any]]:
        scheme = "https" if self.use_ssl else "http"
        return [{"host": self.host, "port": self.port, "scheme": scheme}]

    def to_client_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "hosts": self.hosts,
            "use_ssl": self.use_ssl,
            "verify_certs": self.verify_certs,
            "ssl_show_warn": self.ssl_show_warn,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_on_timeout": self.retry_on_timeout,
            "http_compress": self.http_compress,
        }

        if self.http_auth:
            kwargs["http_auth"] = self.http_auth

        if self.ca_certs:
            kwargs["ca_certs"] = self.ca_certs

        kwargs.update(self.extra_client_kwargs)
        return kwargs

    @classmethod
    def from_env(cls, **overrides: Any) -> Self:
        values: dict[str, Any] = {}

        host = os.getenv("OPENSEARCH_HOST")
        if host:
            values["host"] = host

        port = os.getenv("OPENSEARCH_PORT")
        if port:
            values["port"] = int(port)

        user = os.getenv("OPENSEARCH_USER")
        if user is not None:
            values["user"] = user or None

        password = os.getenv("OPENSEARCH_PASSWORD")
        if password is not None:
            values["password"] = password or None

        use_ssl = os.getenv("OPENSEARCH_USE_SSL")
        if use_ssl is not None:
            values["use_ssl"] = _parse_bool(use_ssl)

        verify_certs = os.getenv("OPENSEARCH_VERIFY_CERTS")
        if verify_certs is not None:
            values["verify_certs"] = _parse_bool(verify_certs)

        ssl_show_warn = os.getenv("OPENSEARCH_SSL_SHOW_WARN")
        if ssl_show_warn is not None:
            values["ssl_show_warn"] = _parse_bool(ssl_show_warn)

        ca_certs = os.getenv("OPENSEARCH_CA_CERTS")
        if ca_certs:
            values["ca_certs"] = ca_certs

        bulk_chunk = os.getenv("OPENSEARCH_BULK_CHUNK")
        if bulk_chunk:
            values["bulk_chunk"] = int(bulk_chunk)

        timeout = os.getenv("OPENSEARCH_TIMEOUT")
        if timeout:
            values["timeout"] = int(timeout)

        max_retries = os.getenv("OPENSEARCH_MAX_RETRIES")
        if max_retries:
            values["max_retries"] = int(max_retries)

        retry_on_timeout = os.getenv("OPENSEARCH_RETRY_ON_TIMEOUT")
        if retry_on_timeout is not None:
            values["retry_on_timeout"] = _parse_bool(retry_on_timeout)

        http_compress = os.getenv("OPENSEARCH_HTTP_COMPRESS")
        if http_compress is not None:
            values["http_compress"] = _parse_bool(http_compress)

        values.update(overrides)
        return cls(**values)


def load_config(**overrides: Any) -> OSConfig:
    """Load connection settings from the environment."""

    return OSConfig.from_env(**overrides)


def _opensearch_class() -> type[Any]:
    from opensearchpy import OpenSearch

    return OpenSearch


def create_client(
    config: OSConfig | None = None,
    **overrides: Any,
) -> Any:
    """Create and return a configured OpenSearch client."""

    if config is None:
        config = load_config(**overrides)
    elif overrides:
        config = replace(config, **overrides)

    return _opensearch_class()(**config.to_client_kwargs())


class OSBase:
    """Base service that owns an OpenSearch client and an optional default index."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        config: OSConfig | None = None,
        index: str | None = None,
        **client_overrides: Any,
    ) -> None:
        self.default_index = index

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

    def use_index(self, index: str) -> Self:
        """Set the default index and return the service for chaining."""

        self.default_index = index
        return self

    def _resolve_index(self, index: str | None = None) -> str:
        resolved_index = index or self.default_index
        if resolved_index is None:
            raise ValueError("An index name is required for this operation.")
        return resolved_index
