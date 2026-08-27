"""Manual figure store — turns an opaque ``figure_id`` into WebP bytes.

The RAG index emits ``figure_id`` for figure chunks (``None`` for text and
table chunks), and this module is the ONLY place that knows how that token
becomes a storage key. Two backends sit behind one function:

| knowledge provider | store | object                                              |
| ------------------ | ----- | --------------------------------------------------- |
| ``mock``           | disk  | ``{SKEWNONO_CHAT_FIGURES_DIR}/{figure_id}.webp``     |
| ``office``         | MinIO | ``{client prefix}/{figure prefix}{figure_id}.webp`` |

The store follows the knowledge provider rather than carrying a selector of
its own: a ``figure_id`` is only meaningful against the index that minted it
(the office ingestion writes the index and the figure objects together), so
"office index, disk figures" is not a configuration anyone can want.

Office layout (office 확인 2026-08-27)::

    user/2067928/hitachi_sem/manual_figures/CG6300_1.HHTSEM_SYSTEM_p100_i0.webp
    ^bucket ^client prefix ^SKEWNONO_CHAT_FIGURE_PREFIX (default) ^figure_id

The user namespace (``2067928/``) is the MinIO client's own default prefix —
``minio_handler``'s ``PREFIX`` / ``MINIO_PREFIX`` — and this module passes the
key BELOW it: ``MinioObject().get("hitachi_sem/manual_figures/<id>.webp")``.
That is the opposite of ``msr_image/minio_cache.py``, which clears the client
prefix and spells the namespace into its own prefix. Both work; the trap is
mixing them — spelling ``2067928/`` into ``SKEWNONO_CHAT_FIGURE_PREFIX`` here
would double it to ``2067928/2067928/...`` and every figure 404s. The
``hitachi_sem/`` segment is a tool-family axis, so another family's figures
land under another prefix, never another bucket.

Every failure is a miss (``None`` → 404), by design: distinguishing "bad id"
from "not stored" from "no store configured" would make the endpoint an
oracle for which figure_ids exist. Storage errors that are NOT a plain miss
are logged so a scoped-credential ``AccessDenied`` does not masquerade as an
unextracted figure.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

from back_dev_home.chat import config

log = logging.getLogger(__name__)

# The office derives a figure id as ``{doc_id}_p{page}_i{idx}``, and real
# doc_ids carry dots — ``CG6300_1.HHTSEM_SYSTEM_p100_i0`` (office 확인
# 2026-08-19). The charset therefore admits ``.``, which the original design
# did not; without it every office figure 404s while every mock fixture keeps
# passing, so the failure would only ever show up at the office.
_FIGURE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# minio raises S3Error with one of these in ``.code`` when the object is gone.
# Matched on the attribute rather than ``isinstance(exc, S3Error)`` because
# ``minio`` is an office-only dependency (same reason as msr_image's cache).
_NOT_FOUND_CODES = frozenset({"NoSuchKey", "NoSuchObject", "NotFound"})


def is_valid_figure_id(figure_id: str) -> bool:
    """Charset + length + no ``..`` — checked before any storage call.

    Validation happens before storage, not after: on the MinIO path a
    malformed id would otherwise cost a network round trip to learn what the
    charset already knows. Admitting ``.`` means ``..`` is no longer excluded
    by the charset alone, so it is refused by name, and so is a LEADING dot:
    a bare ``.`` matches the charset, and on the MinIO path it was reaching
    storage as ``.../..webp`` (the disk path only survived it through the
    containment check). Real ids start with the doc_id's model prefix
    (``CG6300_…``), never a dot. Slashes never arrive — Flask routing refuses
    them before the view runs.
    """
    return (
        bool(_FIGURE_ID.match(figure_id))
        and ".." not in figure_id
        and not figure_id.startswith(".")
    )


def figure_key(figure_id: str) -> str:
    """The object key below the client's namespace prefix (MinIO store)."""
    return f"{config.get_figure_prefix()}{figure_id}.webp"


def read_figure(figure_id: str) -> bytes | None:
    """WebP bytes for ``figure_id``, or ``None`` when it must not be served."""
    if not is_valid_figure_id(figure_id):
        return None
    if config.get_knowledge_provider_name() == "office":
        return _read_minio(figure_id)
    return _read_disk(figure_id)


def _read_disk(figure_id: str) -> bytes | None:
    figures_dir = config.get_figures_dir()
    if figures_dir is None:
        return None
    # Containment is the backstop for the charset check above — it also
    # catches a figure symlinked out of the store.
    root = Path(figures_dir).resolve()
    path = (root / f"{figure_id}.webp").resolve()
    if path.parent != root:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _default_client():
    # Lazy: office-only dependency, keeps home boot free of minio_handler.
    from minio_handler import MinioObject

    client = MinioObject()
    bucket = config.get_figure_bucket()
    if bucket:
        client = client.use_bucket(bucket)
    # Deliberately NOT ``use_prefix(None)``: the client's default prefix is the
    # user namespace and the whole point (see the module docstring).
    return client


# Swapped by tests; the office never touches this.
_client_factory: Callable[[], object] = _default_client
_client: object | None = None


def _get_client():
    global _client
    if _client is None:
        _client = _client_factory()
    return _client


def reset_client() -> None:
    """Drop the cached MinIO client (tests, and any future config reload)."""
    global _client
    _client = None


def _read_minio(figure_id: str) -> bytes | None:
    key = figure_key(figure_id)
    try:
        return _get_client().get(key)
    except Exception as error:  # noqa: BLE001 — every failure is a miss
        code = getattr(error, "code", None)
        if code in _NOT_FOUND_CODES:
            return None
        log.warning(
            "chat figure store read failed for %s: %s%s",
            figure_id,
            type(error).__name__,
            f" ({code})" if code else "",
        )
        return None
