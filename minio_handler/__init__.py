"""Class-based MinIO / S3-compatible client wrappers."""

from .base import MinioBase, MinioConfig, create_client, load_config
from .object import MinioObject

__all__ = [
    "MinioBase",
    "MinioConfig",
    "MinioObject",
    "create_client",
    "load_config",
]
