"""Purpose-specific OpenSearch service classes built on top of opensearch-py."""

from .base import OSConfig, create_client, load_config
from .document import OSDoc, normalize_document
from .index import OSIndex
from .search import OSSearch

__all__ = [
    "OSConfig",
    "OSDoc",
    "OSIndex",
    "OSSearch",
    "create_client",
    "load_config",
    "normalize_document",
]
