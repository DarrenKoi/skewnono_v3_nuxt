"""Shared FTP listing primitive used at both scales.

``_normalize_listing`` lives in ``core`` (not in either downloader) so the
single-server ``FtpClient`` and the fleet ``FtpFleetDownloader`` normalize NLST
output identically, and so neither downloader depends on the other. Stdlib only
(``fnmatch``), so it travels with the copy-out proxy bundle by bare name.
"""

import fnmatch


def _normalize_listing(
    names: list[str],
    remote_dir: str,
    pattern: str | None = None,
) -> list[str]:
    """Filter and normalize raw NLST output into usable remote paths.

    NLST returns either bare basenames or full paths depending on the server;
    this normalizes both to a path that RETR/DELE will accept, and keeps only
    entries whose basename matches ``pattern`` (an fnmatch glob). ``pattern=None``
    keeps everything.
    """
    out: list[str] = []
    for name in names:
        base = name.rsplit("/", 1)[-1]
        if pattern is None or fnmatch.fnmatch(base, pattern):
            full = name if name.startswith("/") else f"{remote_dir.rstrip('/')}/{base}"
            out.append(full)
    return out
