"""Diagnose chat manual figures that 404 while the chat answer itself works.

`GET /api/chat/figures/<figure_id>` deliberately turns EVERY failure into a
404, so the browser cannot tell these four apart:

    no credentials | no bucket resolved | key outside the credential's
    prefix (AccessDenied) | the object genuinely is not stored

This script separates them by printing what the real code path resolves --
the same `figures.read_figure()` the endpoint calls -- and then listing what
actually exists under the figures prefix.

The suspect it exists for: `minio_handler/minio_config.py` is GITIGNORED, and
the client's BUCKET / PREFIX are read from that module and nowhere else
(`minio_handler/base.py` `_module_values`; the connection settings do have
MINIO_* env fallbacks, these two do not). On a checkout without that file the
prefix resolves to None, chat's key loses the `2067928/` user namespace, and
credentials scoped to that namespace answer AccessDenied.

That file is also SHARED with the co-located RAG, which imports the same
`minio_handler` from the same repo root. Two callers, one global: chat spells
its key BELOW the client prefix while `msr_image` clears the prefix and owns
the whole key, so whichever convention the RAG needs is a value both sides
must live with. Section 4 prints what each convention would ask for.

Run FROM THE REPO ROOT at the office:

    .venv/bin/python -m scripts.diagnose.diagnose_chat_figures
    .venv/bin/python -m scripts.diagnose.diagnose_chat_figures <figure_id>

Read-only: stat, get and list only. It never writes or deletes an object.
"""

from __future__ import annotations

import sys
from pathlib import Path
# Make `back_dev_home` importable however this file was started. `-m` puts the
# working directory on sys.path and works from the repo root; running the file
# by path puts scripts/ there instead and fails on the first import below. Both
# forms get typed -- a file manager, an IDE "run this file" button and tab
# completion all produce the by-path one -- so support both.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Importing the package applies its stdout UTF-8 fix. `-m` gets it for free
# because -m imports the package first; running this file by path does not,
# and would then die on the ANSI code page. One line covers both.
import scripts  # noqa: E402,F401

from back_dev_home.chat import config, figures, rag  # noqa: E402

# A real office id, dots and all (office 확인 2026-08-19). Only a default: the
# answer that matters is about YOUR figure, so pass one from a live citation.
_SAMPLE_ID = "CG6300_1.HHTSEM_SYSTEM_p100_i0"
_LIST_LIMIT = 5


def _rule(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 60 - len(title)))


def _report_switch() -> bool:
    _rule("1. which store answers")
    root = rag.rag_root()
    ready = rag.rag_ready()
    print(f"  rag_root()   : {root}")
    print(f"  rag_ready()  : {ready}")
    if not ready:
        print("  -> DISK store. Figures come from SKEWNONO_CHAT_FIGURES_DIR")
        print(f"     SKEWNONO_CHAT_FIGURES_DIR = {config.get_figures_dir()}")
        print("     Unset = every figure 404s, and that is the whole story.")
    else:
        print("  -> MinIO store.")
    return ready


def _report_client_config() -> None:
    _rule("2. what the shared minio_handler resolved")
    try:
        from minio_handler import minio_config  # type: ignore[attr-defined]
    except ModuleNotFoundError:
        print("  minio_config.py: ABSENT (it is gitignored)")
        print("    -> BUCKET and PREFIX have NO env fallback, so both are None")
        print("       unless SKEWNONO_CHAT_FIGURE_BUCKET supplies the bucket.")
        print("       A None prefix drops the 2067928/ namespace -> AccessDenied.")
    else:
        print(f"  minio_config.py: present at {minio_config.__file__}")
        print(f"    BUCKET = {getattr(minio_config, 'BUCKET', None)!r}")
        print(f"    PREFIX = {getattr(minio_config, 'PREFIX', None)!r}")
        # Never print a secret; presence is the whole question.
        for name in ("ACCESS_KEY", "SECRET_KEY"):
            value = getattr(minio_config, name, None)
            print(f"    {name} = {'set' if value else 'None (falls back to env)'}")

    print(f"  SKEWNONO_CHAT_FIGURE_BUCKET = {config.get_figure_bucket()!r}")
    print(f"  SKEWNONO_CHAT_FIGURE_PREFIX = {config.get_figure_prefix()!r}")


def _report_key(figure_id: str):
    _rule("3. the key chat builds for this figure")
    print(f"  figure_id     : {figure_id}")
    print(f"  valid charset : {figures.is_valid_figure_id(figure_id)}")
    key = figures.figure_key(figure_id)
    print(f"  key below the client prefix: {key}")

    try:
        client = figures._get_client()
    except Exception as error:  # noqa: BLE001 — the diagnosis, not a crash
        print(f"  CLIENT CONSTRUCTION FAILED: {type(error).__name__}: {error}")
        print("  -> credentials or endpoint. Nothing below can run.")
        return None, key

    bucket = getattr(client, "default_bucket", None)
    prefix = getattr(client, "default_prefix", None)
    resolved = f"{prefix + '/' if prefix else ''}{key}"
    print(f"  resolved bucket : {bucket!r}")
    print(f"  resolved prefix : {prefix!r}")
    print(f"  FULL OBJECT     : {bucket}/{resolved}")
    if prefix is None:
        print("  !! no client prefix: this key has no user namespace. If the")
        print("     credentials are scoped to one, MinIO answers AccessDenied,")
        print("     which this endpoint reports as a 404.")
    return client, key


def _report_read(figure_id: str, client, key: str) -> None:
    _rule("4. what the store actually says")
    if client is None:
        return
    try:
        client.get(key)
    except Exception as error:  # noqa: BLE001 — the whole point is the error
        code = getattr(error, "code", None)
        print(f"  get() raised {type(error).__name__}{f' ({code})' if code else ''}: {error}")
        if code == "AccessDenied":
            print("  -> the key is outside the credential's prefix. Compare the")
            print("     FULL OBJECT above with the layout in chat/figures.py.")
        elif code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
            print("  -> reachable and permitted, the object is simply not there.")
            print("     That is an ingestion question for the RAG side.")
    else:
        print("  get() SUCCEEDED — the store is fine and the 404 is elsewhere")
        print("  (check is_valid_figure_id above, and the browser's actual URL).")

    print(f"\n  listing up to {_LIST_LIMIT} objects under the figures prefix:")
    shown = 0
    try:
        for obj in client.list(config.get_figure_prefix()):
            if shown >= _LIST_LIMIT:
                print("    ... (truncated)")
                break
            print(f"    {obj.object_name}")
            shown += 1
        if shown == 0:
            print("    (nothing under that prefix)")
    except Exception as error:  # noqa: BLE001
        print(f"    list() raised {type(error).__name__}: {error}")


def _report_conventions() -> None:
    _rule("5. the two conventions, since the RAG shares this client")
    prefix = config.get_figure_prefix()
    print("  chat  (inherits the client prefix, minio_config.py owns 2067928/):")
    print("      minio_config.py: BUCKET = \"user\"   PREFIX = \"2067928/\"")
    print(f"      SKEWNONO_CHAT_FIGURE_PREFIX = {prefix}")
    print("  chat  (no minio_config.py — chat supplies everything itself):")
    print("      SKEWNONO_CHAT_FIGURE_BUCKET=user")
    print(f"      SKEWNONO_CHAT_FIGURE_PREFIX=2067928/{prefix}")
    print("  Pick ONE. Doing both writes 2067928/2067928/... and every figure")
    print("  404s, which is the same symptom as doing neither.")


def main() -> int:
    if len(sys.argv) > 2:
        print(__doc__)
        return 2
    figure_id = sys.argv[1] if len(sys.argv) == 2 else _SAMPLE_ID

    if not _report_switch():
        return 0
    _report_client_config()
    client, key = _report_key(figure_id)
    _report_read(figure_id, client, key)
    _report_conventions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
