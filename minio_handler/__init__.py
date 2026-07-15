"""Class-based MinIO / S3-compatible client wrappers."""

from .base import MinioBase, MinioConfig, create_client, load_config
from .object import DateFolder, DeleteOlderResult, GetManyResult, MinioObject

__all__ = [
    "DateFolder",
    "DeleteOlderResult",
    "GetManyResult",
    "MinioBase",
    "MinioConfig",
    "MinioObject",
    "create_client",
    "load_config",
]
