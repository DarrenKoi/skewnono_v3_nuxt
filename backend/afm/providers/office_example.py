# TEMPLATE — copy to office.py at the office: `cp office_example.py office.py`.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 AFM adapter: a Redis index over MinIO objects. Read-only.

Schema of record: docs/datatables/afm/afm_redis.txt (user-confirmed 2026-10-06).

Redis — two hashes, every value a ``DataFrame.to_parquet()`` blob:

* ``afm_d1_tools``, field ``all`` — the tool list: ``id, name, fab, alias``
  (``fab`` is still empty).
* ``afm_d2_measurements``, field = tool name (``MAP608``, ``MAPC01``,
  ``5EAP1501``) — that tool's whole measurement history as ONE DataFrame. There
  is no per-row key and no TTL; the loader rewrites a tool's field wholesale.

A measurement row carries seven ``*_dir_list`` columns (data, profile, tiff,
align, tip, capture, raw) holding full MinIO object keys,
``2067928/afm/<TOOL>/<unique_key>/<file name>``. An empty list means no files.

MinIO — the bodies those keys name:

* detail: ``detail_information.parquet``, ``detail_summary.parquet``,
  ``detail_points.parquet``
* profile: ``profile_<raw name>.parquet`` — X/Y/Z, units in the metadata
* images: ``<file name>.webp``

**This adapter never writes to MinIO or Redis.** The loader owns both.

What the contract gets is not what Redis holds, in two places: the lists are cut
down to **basenames** (the page never learns the storage layout, and a name is
unique inside one measurement's folder), and an empty cell — NaN in the frame,
``NA`` in ``time`` — becomes ``None`` / ``""``.

Still assumptions (OFFICE-VERIFY) — run this file once and compare:
  - the columns of the three detail parquets (see ``_information`` and
    ``_position``); ``Point No`` / ``Site ID`` are the raw CSV's names;
  - whether a profile's units sit in the parquet metadata or in the MinIO
    object's user metadata (both are read);
  - how a point's image is named — matched here on ``_<position>_Height``;
  - where the original TIFF lives. ``raw_dir_list`` is documented as csv/txt, so
    no image offers a TIFF download until a ``.tif``/``.tiff`` shows up there;
  - ``measured_info`` and ``tool_id`` are not among the documented columns.

Standalone check, from the repo root (reads only):

    python -m backend.afm.providers.office
"""

from __future__ import annotations

import io
import json
import re
import time
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from backend._runtime.office_redis import (
    read_dataframe as _deserialize_dataframe,
    redis_client as _redis_client,
)
from backend.afm.contracts import AfmMeasurementRow, AfmOriginalFile, AfmProfileMeta

_TOOLS_KEY = "afm_d1_tools"
_TOOLS_FIELD = "all"
_MEASUREMENTS_KEY = "afm_d2_measurements"

_LIST_KINDS = ("data", "profile", "tiff", "align", "tip", "capture", "raw")
_IMAGE_KINDS = ("align", "tip", "capture", "tiff")
_INFORMATION, _SUMMARY, _POINTS = (
    "detail_information.parquet",
    "detail_summary.parquet",
    "detail_points.parquet",
)
_TIFF_SUFFIXES = (".tif", ".tiff")
_GONE_CODES = {"NoSuchKey", "NoSuchObject", "NotFound"}
# `_0001_Height`, or `_0004_X000_Y-002_0002_Height` on a recipe that records Site ID.
_POSITION_IN_NAME = re.compile(r"_((?:\d{4}_X-?\d+_Y-?\d+_)?\d{4})_Height")

# One tool's history is a single blob, and a detail page asks for it a dozen
# times (detail, profile, every image). Re-read it at most this often.
_CACHE_SECONDS = 60


# -- reading -----------------------------------------------------------------


def _records(df) -> list[dict[str, Any]]:
    """A DataFrame as JSON-ready rows.

    ``to_json`` is what turns NaN / NaT into null, numpy scalars into Python
    ones and a list column (a numpy array after ``read_parquet``) into a list —
    the three things ``to_dict`` leaves for ``jsonify`` to choke on.
    """
    return json.loads(df.to_json(orient="records", date_format="iso", double_precision=15))


@lru_cache(maxsize=8)
def _hash_rows(key: str, field: str, _tick: int) -> tuple[dict[str, Any], ...]:
    raw = _redis_client().hget(key, field)
    if raw is None:
        return ()
    return tuple(_records(_deserialize_dataframe(raw, f"{key}[{field}]")))


def _rows_of(key: str, field: str) -> tuple[dict[str, Any], ...]:
    # Shared between requests for a minute: read these dicts, never change them.
    return _hash_rows(key, field, int(time.time() // _CACHE_SECONDS))


@lru_cache(maxsize=1)
def _store():
    # Lazy: office-only dependency, keeps home boot free of minio_handler.
    from minio_handler import MinioObject

    # prefix="" (NOT None, which means "use the default"): the keys in Redis
    # already start with the user namespace, and the client's default prefix is
    # that same `2067928/` — left on, every key would double and 404.
    return MinioObject(prefix="")


def _object(key: str | None) -> bytes | None:
    """One stored object, or None when it is not there (never listed, or purged)."""
    if not key:
        return None
    try:
        return _store().get(key)
    except Exception as exc:  # noqa: BLE001 — re-raised unless it is a plain miss
        if getattr(exc, "code", None) in _GONE_CODES:
            return None
        raise


def _frame(key: str | None):
    raw = _object(key)
    if raw is None:
        return None
    import pandas as pd

    return pd.read_parquet(io.BytesIO(raw))


# -- cells and names ---------------------------------------------------------


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _basename(key: str) -> str:
    return key.rsplit("/", 1)[-1]


def _stem(filename: str) -> str:
    return filename[:-4] if filename.endswith((".csv", ".pkl")) else filename


def _keys(record: dict[str, Any], kind: str) -> list[str]:
    return record.get(f"{kind}_dir_list") or []


def _key_named(record: dict[str, Any], kind: str, name: str) -> str | None:
    return next((key for key in _keys(record, kind) if _basename(key) == name), None)


def _key_at(record: dict[str, Any], kind: str, point: str) -> str | None:
    """The file of one position: its name ends `_<position>_Height.<ext>`."""
    keys = _keys(record, kind)
    return next(
        (key for key in keys if f"_{point}_Height" in _basename(key)),
        _key_named(record, kind, point),
    )


def _original_key(record: dict[str, Any], name: str) -> str | None:
    # OFFICE-VERIFY: an original is looked for beside the raw files, under the
    # webp's own name with a TIFF extension.
    stem = name.rsplit(".", 1)[0]
    for key in _keys(record, "raw"):
        base = _basename(key)
        if base.lower().endswith(_TIFF_SUFFIXES) and base.rsplit(".", 1)[0] == stem:
            return key
    return None


def _find(filename: str, tool_name: str | None) -> dict[str, Any] | None:
    wanted = _stem(filename)
    for record in _rows_of(_MEASUREMENTS_KEY, normalize_tool(tool_name)):
        if wanted in (_stem(_text(record.get("filename"))), _text(record.get("unique_key"))):
            return record
    return None


# -- tools and the list ------------------------------------------------------


def normalize_tool(tool_name: str | None) -> str:
    return (tool_name or "").strip().upper() or "MAP608"


def get_tools() -> list[dict[str, str]]:
    return [
        {
            "id": _text(record.get("id")),
            "name": _text(record.get("name")),
            "label": _text(record.get("alias")) or _text(record.get("name")),
            # Empty for now: the office has not decided where fab comes from.
            "fab": _text(record.get("fab")),
        }
        for record in _rows_of(_TOOLS_KEY, _TOOLS_FIELD)
    ]


def _row(record: dict[str, Any], tool: str) -> AfmMeasurementRow:
    names = {kind: [_basename(key) for key in _keys(record, kind)] for kind in _LIST_KINDS}
    time_code = _text(record.get("time"))
    point_count = record.get("point_count")
    return {
        "unique_key": _text(record.get("unique_key")),
        "filename": _text(record.get("filename")),
        "date": _text(record.get("date")),
        "formatted_date": _text(record.get("formatted_date")) or None,
        "recipe_name": _text(record.get("recipe_name")),
        "lot_id": _text(record.get("lot_id")),
        "slot_number": _text(record.get("slot_number")),
        # The loader writes a missing time as null, and the raw name spells it NA.
        "time": None if time_code in ("", "NA") else time_code,
        # OFFICE-VERIFY: neither column is in the documented schema.
        "measured_info": _text(record.get("measured_info")),
        "tool_name": _text(record.get("tool_name")) or tool,
        "tool_id": _text(record.get("tool_id")) or tool.lower(),
        "fab": _text(record.get("fab")),
        "profile_dir_list": names["profile"],
        "data_dir_list": names["data"],
        "tiff_dir_list": names["tiff"],
        "align_dir_list": names["align"],
        "tip_dir_list": names["tip"],
        "capture_dir_list": names["capture"],
        "raw_dir_list": names["raw"],
        "has_profile": bool(names["profile"]),
        "has_data": bool(names["data"]),
        "has_image": bool(names["tiff"]),
        "has_align": bool(names["align"]),
        "has_tip": bool(names["tip"]),
        "point_count": None if point_count is None else int(point_count),
    }


def list_afm_files(tool_name: str | None = None) -> list[AfmMeasurementRow]:
    tool = normalize_tool(tool_name)
    rows = [_row(record, tool) for record in _rows_of(_MEASUREMENTS_KEY, tool)]
    # Newest first; the frame's own order is whatever the loader appended in.
    return sorted(rows, key=lambda row: (row["date"], row["time"] or ""), reverse=True)


# -- detail ------------------------------------------------------------------


def _information(df) -> dict[str, str]:
    # OFFICE-VERIFY: read as key/value rows when the frame has two columns (the
    # raw Info section's shape), otherwise as one wide row.
    if df is None or df.empty:
        return {}
    records = _records(df)
    if df.shape[1] == 2:
        return {_text(key): _text(value) for key, value in (r.values() for r in records)}
    return {_text(key): _text(value) for key, value in records[0].items()}


def _position(record: dict[str, Any]) -> str:
    """A point's position key — the text its profile and image are named after.

    The 4-digit point number, behind the Site ID on a recipe that records one
    (`0004_X000_Y-002_0002`).
    """
    number = record.get("Point No")
    point = "" if number is None else f"{int(number):04d}"
    site = _text(record.get("Site ID"))
    return f"{site}_{point}" if site and point else site or point


def get_afm_file_detail(
    filename: str,
    tool_name: str | None = None,
) -> dict[str, Any] | None:
    record = _find(filename, tool_name)
    if record is None:
        return None

    summary = _frame(_key_named(record, "data", _SUMMARY))
    points = _frame(_key_named(record, "data", _POINTS))
    # The page's point picker filters on `measurement_point`; a frame that
    # already carries the column keeps its own.
    data = [] if points is None else [
        {"measurement_point": _position(row), **row} for row in _records(points)
    ]
    positions = [row["measurement_point"] for row in data if row["measurement_point"]]
    if not positions:
        # No data CSV is a normal state, and its profiles and images still need
        # a picker: read the positions off their names.
        positions = [
            match.group(1)
            for kind in ("profile", "tiff")
            for key in _keys(record, kind)
            if (match := _POSITION_IN_NAME.search(_basename(key)))
        ]

    stored_name = _text(record.get("filename"))
    return {
        "filename": stored_name,
        "tool": normalize_tool(tool_name),
        "pickle_filename": f"{_stem(stored_name)}.pkl",
        "information": _information(_frame(_key_named(record, "data", _INFORMATION))),
        "summary": [] if summary is None else _records(summary),
        "data": data,
        "available_points": list(dict.fromkeys(positions)),
    }


# -- profile -----------------------------------------------------------------

# ponytail: the profile route asks for the points and then the metadata, so one
# view downloads the same object twice. Cache `_profile` by key (hits only — a
# cached miss would hide an object loaded a moment later) if that ever shows.


def _profile(filename: str, point: str, tool_name: str | None):
    """(X/Y/Z table, declared metadata) of one position's profile, or None."""
    record = _find(filename, tool_name)
    key = None if record is None else _key_at(record, "profile", point)
    raw = _object(key)
    if raw is None:
        return None

    import pyarrow.parquet as pq

    table = pq.read_table(io.BytesIO(raw))
    declared = {
        name.decode(errors="replace").lower(): value.decode(errors="replace")
        for name, value in (table.schema.metadata or {}).items()
    }
    if "xunit" not in declared:
        # OFFICE-VERIFY: "객체 metadata" may mean the MinIO object's user
        # metadata rather than the parquet file's.
        declared = {
            name.lower().removeprefix("x-amz-meta-"): value
            for name, value in (_store().stat(key).metadata or {}).items()
        }
    return table, declared


def get_profile_points(
    filename: str,
    point: str,
    tool_name: str | None = None,
    site_info: dict[str, str | int | None] | None = None,
) -> list[dict[str, float]] | None:
    profile = _profile(filename, point, tool_name)
    if profile is None:
        return None
    df = profile[0].to_pandas()
    df.columns = [str(column).lower() for column in df.columns]
    return _records(df[["x", "y", "z"]])


def get_profile_meta(
    filename: str,
    point: str,
    tool_name: str | None = None,
) -> AfmProfileMeta | None:
    profile = _profile(filename, point, tool_name)
    if profile is None:
        return None
    declared = profile[1]
    # Units travel as declared: never converted, never defaulted per tool.
    return {
        "x_unit": declared.get("xunit", ""),
        "y_unit": declared.get("yunit", ""),
        "z_unit": declared.get("zunit", ""),
        "data_size": declared.get("datasize", ""),
        "surface_size": declared.get("surfacesize", ""),
    }


# -- images ------------------------------------------------------------------
# The two `*_svg` names are the contract's, kept from the mock's placeholder.
# Here both return the stored webp bytes, which routes.py serves as image/webp.


def get_profile_image_svg(
    filename: str,
    point: str,
    tool_name: str | None = None,
) -> bytes | None:
    record = _find(filename, tool_name)
    return None if record is None else _object(_key_at(record, "tiff", point))


def list_analysis_images(
    filename: str,
    image_type: str,
    tool_name: str | None = None,
) -> list[dict[str, str]]:
    record = _find(filename, tool_name) if image_type in _IMAGE_KINDS else None
    if record is None:
        return []

    base = f"/api/afm/files/{quote(_text(record.get('filename')), safe='')}"
    tool = f"?tool={quote(normalize_tool(tool_name), safe='')}"
    images: list[dict[str, str]] = []
    for key in _keys(record, image_type):
        name = _basename(key)
        encoded = quote(name, safe="")
        image = {"name": name, "url": f"{base}/images/{image_type}/{encoded}{tool}"}
        # The page shows 원본 TIFF 다운로드 only where this key is present.
        if image_type == "tiff" and _original_key(record, name):
            image["original_url"] = f"{base}/tiff/{encoded}{tool}"
        images.append(image)
    return images


def get_analysis_image_svg(
    filename: str,
    image_type: str,
    name: str,
    tool_name: str | None = None,
) -> bytes | None:
    record = _find(filename, tool_name) if image_type in _IMAGE_KINDS else None
    return None if record is None else _object(_key_named(record, image_type, name))


def get_tiff_original(
    filename: str,
    name: str,
    tool_name: str | None = None,
) -> AfmOriginalFile | None:
    record = _find(filename, tool_name)
    key = None if record is None else _original_key(record, name)
    data = _object(key)
    if data is None:
        return None
    # The stored name, not one composed here: a download keeps its identity.
    return {"filename": _basename(key), "content_type": "image/tiff", "data": data}


if __name__ == "__main__":
    # Prints what the OFFICE-VERIFY items above need: the real column names.
    for _tool in get_tools():
        _rows = list_afm_files(_tool["name"])
        print(f"{_tool} — {len(_rows)} measurements")
        if not _rows:
            continue
        _first = _rows[0]
        print("  row    :", {k: v for k, v in _first.items() if not k.endswith("_dir_list")})
        print("  files  :", {k: v[:2] for k, v in _first.items() if k.endswith("_dir_list")})
        _detail = get_afm_file_detail(_first["filename"], _tool["name"])
        print("  info   :", _detail["information"])
        print("  summary:", _detail["summary"][:1])
        print("  points :", _detail["data"][:1])
        print("  picker :", _detail["available_points"][:5])
        if _first["has_profile"] and _detail["available_points"]:
            _point = _detail["available_points"][0]
            print("  profile:", get_profile_meta(_first["filename"], _point, _tool["name"]))
