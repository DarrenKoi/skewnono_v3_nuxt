"""Shared FTP primitives: the single-server client and the NLST normalizer.

``core`` is the foundation the two downloaders build on; it depends on nothing
else in ``ftp_handler``.

    from ftp_handler.core import FtpClient            # one server, ad-hoc ops
"""

from .client import DirEntries, FileInfo, FtpClient
from .listing import _normalize_listing

__all__ = [
    "FtpClient",
    "FileInfo",
    "DirEntries",
]
