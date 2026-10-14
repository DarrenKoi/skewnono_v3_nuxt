"""Purpose-specific OpenSearch service classes built on top of opensearch-py."""

from .base import ConnectionStatus, OSConfig, create_client, load_config
from .document import BulkCreateResult, OSDoc, normalize_document
from .index import OSIndex
from .search import OSSearch

__all__ = [
    "BulkCreateResult",
    "ConnectionStatus",
    "OSConfig",
    "OSDoc",
    "OSIndex",
    "OSSearch",
    "create_client",
    "load_config",
    "normalize_document",
]
