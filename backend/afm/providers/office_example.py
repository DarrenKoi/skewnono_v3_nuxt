# TEMPLATE — copy to office.py at the office: `cp office_example.py office.py`.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 AFM adapter: a Redis index over MinIO objects. Read-only.

Schema of record: docs/datatables/afm/afm_redis.txt (spec user-confirmed
2026-10-06; column layouts and value conventions office 확인 2026-10-06, the
tip columns, ``measured_time`` and ``point_count`` office 확인 2026-10-07).

Redis — two hashes, every value a ``DataFrame.to_parquet()`` blob:

* ``afm_d1_tools``, field ``all`` — the tool list: ``id, name, fab, alias``.
  ``fab`` is an empty string and ``alias`` is the pipeline's code name for the
  tool (``R3``, ``M15``; null for MAP608), so the fab is a fixed table here:
  MAP608=PKG, MAPC01=R3, 5EAP1501=M15 (user-confirmed 2026-10-07).
* ``afm_d2_measurements``, field = tool name (``MAP608``, ``MAPC01``,
  ``5EAP1501``) — that tool's whole measurement history as ONE DataFrame. There
  is no per-row key and no TTL; the loader rewrites a tool's field wholesale,
  every 30 minutes.

A measurement row carries seven ``*_dir_list`` columns (data, profile, tiff,
align, tip, capture, raw) holding full MinIO object keys,
``2067928/afm/<TOOL>/<unique_key>/<file name>``. An empty list means no files.

MinIO — the bodies those keys name:

* detail: ``detail_information.parquet`` (columns ``name``, ``value``),
  ``detail_summary.parquet`` (``Site``, ``ITEM``, measurement columns; a
  measurement with no Summary has a 0-row, 0-column object) and
  ``detail_points.parquet`` (one row per reading; ``Site`` is the row's block).
  A measurement with no data CSV has ``detail_information.parquet`` alone.
* profile: ``profile_<raw name>.parquet`` — X/Y/Z; the units are the object's
  user metadata (``x-amz-meta-xunit`` …), not parquet metadata.
* images: ``<file name>.webp``; ``tiff_dir_list`` also holds the original TIFFs.

**This adapter never writes to MinIO or Redis.** The loader owns both. Objects
past the 3-month retention are deleted from MinIO first and from Redis after, so
a listed key can be gone: that is a miss (``None``), never an error.

What the contract gets is not what the stores hold, in three places:

* the lists are cut down to **basenames** (the page never learns the storage
  layout, and a name is unique inside one measurement's folder);
* an empty cell — NaN in the frame, ``NA`` in ``time`` — becomes ``None`` / ``""``;
* **every detail value is loaded as text** (``"79.24"``, ``Point No`` ``"1"``,
  an unmeasured cell ``" "``, an unset ``_Valid`` ``""``). ``_cell`` turns
  unit-bearing columns, ``Point No`` and ``Site X`` / ``Site Y`` into numbers and
  the ``Valid`` columns into booleans; everything else stays text.

Still assumptions (OFFICE-VERIFY) — run this file once and compare:
  - how a FALSE ``Valid`` is spelled (none has been seen); ``true`` / ``false``
    in any case are read, anything else is ``None``;

Standalone check, from the repo root (reads only):

    python -m backend.afm.providers.office
"""

from __future__ import annotations

import io
import json
import mimetypes
import re
import threading
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
# user-confirmed 2026-10-07. Nothing the office loads says which fab a tool is in.
_FAB_OF = {"MAP608": "PKG", "MAPC01": "R3", "5EAP1501": "M15"}
_GONE_CODES = {"NoSuchKey", "NoSuchObject", "NotFound"}
_INTEGER_COLUMNS = ("Point No", "Site X", "Site Y")
# `Left_H (nm)`, `X (um)`: a column that names its unit holds a number.
_HAS_UNIT = re.compile(r"\(.+\)\s*$")
_BOOLEANS = {"true": True, "false": False}
_LEADING_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
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


# One snapshot per (hash, field), replaced in place when its minute is over —
# so a worker holds one history per tool however many tools or minutes pass.
_snapshots: dict[tuple[str, str], tuple[int, tuple[dict[str, Any], ...]]] = {}
# ponytail: one lock for every tool, so a refresh of one waits behind another's
# decode (once a minute each). Per-key locks if that wait ever shows.
_refresh = threading.Lock()


def _rows_of(key: str, field: str) -> tuple[dict[str, Any], ...]:
    # Shared between requests for a minute: read these dicts, never change them.
    tick = int(time.time() // _CACHE_SECONDS)
    held = _snapshots.get((key, field))
    if held is not None and held[0] == tick:
        return held[1]
    # A gallery's 133 requests cross the minute together: one of them decodes
    # the blob, the rest wait here and find it done.
    with _refresh:
        held = _snapshots.get((key, field))
        if held is not None and held[0] == tick:
            return held[1]
        raw = _redis_client().hget(key, field)
        if raw is None:
            # Never kept: the field is `?tool=`, the caller's own text, and an
            # entry per spelling would grow without end.
            _snapshots.pop((key, field), None)
            return ()
        rows = tuple(_records(_deserialize_dataframe(raw, f"{key}[{field}]")))
        _snapshots[(key, field)] = (tick, rows)
        return rows


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


def _user_metadata(key: str | None) -> dict[str, str] | None:
    """An object's user metadata with the `x-amz-meta-` prefix dropped, or None."""
    if not key:
        return None
    try:
        headers = _store().stat(key).metadata or {}
    except Exception as exc:  # noqa: BLE001 — re-raised unless it is a plain miss
        if getattr(exc, "code", None) in _GONE_CODES:
            return None
        raise
    return {name.lower().removeprefix("x-amz-meta-"): value for name, value in headers.items()}


def _cell(column: str, value: Any) -> Any:
    """One detail cell as the value it stands for.

    The loader writes every cell as text. An unmeasured cell is a single space
    and an unset `_Valid` is empty; both are None here, never 0 or False.
    """
    if not isinstance(value, str):
        return value
    text = value.strip()
    if column == "Valid" or column.endswith("_Valid"):
        return _BOOLEANS.get(text.lower())
    if column in _INTEGER_COLUMNS or _HAS_UNIT.search(column):
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return value
        return int(number) if column in _INTEGER_COLUMNS else number
    return value


def _table(df) -> list[dict[str, Any]]:
    """A detail frame (summary or points) as typed rows; [] when it is absent or empty."""
    if df is None:
        return []
    return [{column: _cell(column, value) for column, value in row.items()} for row in _records(df)]


# -- cells and names ---------------------------------------------------------


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any) -> float | None:
    # A number, or the number a text starts with ('40.9 nm'); None for an empty
    # cell and for the 'NaN' a Tip Width that was not recorded is stored as.
    found = _LEADING_NUMBER.match(_text(value))
    return float(found.group()) if found else None


def _slot(value: Any) -> str:
    # '5' where the loader read Info's `Slot N`, '07' where it fell back to the
    # file name's `.nn` tail (office 확인 2026-10-07: MAP608 and MAPC01 hold
    # both). One slot must not read as two, so the padding goes.
    text = _text(value)
    return str(int(text)) if text.isdigit() else text


def _count(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


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
    keys = [key for key in _keys(record, kind) if kind == "profile" or not _is_original(_basename(key))]
    return next(
        (key for key in keys if f"_{point}_Height" in _basename(key)),
        _key_named(record, kind, point),
    )


def _is_original(name: str) -> bool:
    # Each image list holds its originals beside the webp conversions the page
    # draws: .tiff for Result, .bmp for align, .png for tip and capture
    # (office 확인 2026-10-07).
    return not name.lower().endswith(".webp")


def _original_key(record: dict[str, Any], name: str) -> str | None:
    # Every image list holds its originals beside their webp conversions.
    # Paired by name: the webp's own, with the original's extension (office 확인 2026-10-07).
    if _is_original(name):
        return None
    stem = name.rsplit(".", 1)[0]
    for kind in _IMAGE_KINDS:
        for key in _keys(record, kind):
            base = _basename(key)
            if _is_original(base) and base.rsplit(".", 1)[0] == stem:
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
            # Stored upper-case; the page's tool slug is lower-case.
            "id": _text(record.get("id")).lower(),
            "name": _text(record.get("name")),
            "label": _text(record.get("name")),
            # The frame's `fab` is an empty string and `alias` is the pipeline's
            # code name for the tool, so the fab comes from the table above.
            "fab": _text(record.get("fab")) or _FAB_OF.get(_text(record.get("id")).upper(), ""),
        }
        for record in _rows_of(_TOOLS_KEY, _TOOLS_FIELD)
    ]


def _row(record: dict[str, Any], tool: str) -> AfmMeasurementRow:
    names = {kind: [_basename(key) for key in _keys(record, kind)] for kind in _LIST_KINDS}
    time_code = _text(record.get("time"))
    measured_code = _text(record.get("measured_time"))
    point_count = record.get("point_count")
    return {
        "unique_key": _text(record.get("unique_key")),
        "filename": _text(record.get("filename")),
        "date": _text(record.get("date")),
        "formatted_date": _text(record.get("formatted_date")) or None,
        "recipe_name": _text(record.get("recipe_name")),
        "lot_id": _text(record.get("lot_id")),
        "slot_number": _slot(record.get("slot_number")),
        # The loader writes a missing time as null, and the raw name spells it NA.
        "time": None if time_code in ("", "NA") else time_code,
        # HHMMSS (office 확인 2026-10-07). Null on a MAP608 measurement whose
        # name has NA there and whose 13-key Info has no Start Time to fall back on.
        "measured_time": None if measured_code in ("", "NA") else measured_code,
        # The column exists and is always null; `tool_id` does not exist.
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
        # Info is loaded for every measurement, so the list being non-empty says
        # nothing: a measurement has data when its points object is listed.
        "has_data": _POINTS in names["data"],
        "has_image": any(not _is_original(name) for name in names["tiff"]),
        "has_align": any(not _is_original(name) for name in names["align"]),
        "has_tip": any(not _is_original(name) for name in names["tip"]),
        "point_count": None if point_count is None else int(point_count),
        # In the frame since 2026-10-07 under these names (office 확인), read
        # off the same first data CSV as detail_points. `tip_width` is float64
        # with NaN for an unrecorded width; `_number` turns that into None.
        "tip_id": _text(record.get("tip_id")) or None,
        "tip_cassette_id": _text(record.get("tip_cassette_id")) or None,
        "tip_port_no": _text(record.get("tip_port_no")) or None,
        "tip_slot_no": _text(record.get("tip_slot_no")) or None,
        "tip_width": _number(record.get("tip_width")),
        "last_pick_up_time": _text(record.get("last_pick_up_time")) or None,
        "approach_count_mean": _number(record.get("approach_count_mean")),
        "mileage_mean": _number(record.get("mileage_mean")),
        "not_completed_count": _count(record.get("not_completed_count")),
        "invalid_count": _count(record.get("invalid_count")),
    }


def list_afm_files(tool_name: str | None = None) -> list[AfmMeasurementRow]:
    tool = normalize_tool(tool_name)
    rows = [_row(record, tool) for record in _rows_of(_MEASUREMENTS_KEY, tool)]
    # Newest first; the frame's own order is whatever the loader appended in.
    return sorted(rows, key=lambda row: (row["date"], row["time"] or ""), reverse=True)


# -- detail ------------------------------------------------------------------


def _information(df) -> dict[str, str | None]:
    # One Info line per row, in columns `name` and `value`. The keys are passed
    # through as loaded (two layouts exist); an empty value ("") becomes None.
    if df is None:
        return {}
    return {_text(row.get("name")): _text(row.get("value")) or None for row in _records(df)}


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

    # The page's point picker filters on `measurement_point`. Each row keeps
    # its `Site` — the method name of its block, which is how the page tells
    # blocks apart (never by row order: a repeat recipe revisits its points).
    data = [
        {"measurement_point": _position(row), **row}
        for row in _table(_frame(_key_named(record, "data", _POINTS)))
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
        "summary": _table(_frame(_key_named(record, "data", _SUMMARY))),
        "data": data,
        "available_points": list(dict.fromkeys(positions)),
    }


# -- profile -----------------------------------------------------------------


def _profile_key(filename: str, point: str, tool_name: str | None) -> str | None:
    record = _find(filename, tool_name)
    return None if record is None else _key_at(record, "profile", point)


def get_profile_points(
    filename: str,
    point: str,
    tool_name: str | None = None,
    site_info: dict[str, str | int | None] | None = None,
) -> list[dict[str, float | None]] | None:
    # The whole file, Z as stored (no levelling; `_records` turns NaN into None).
    # A 2048 x 256 scan is thinned for the page by the route, not here.
    df = _frame(_profile_key(filename, point, tool_name))
    if df is None:
        return None
    df.columns = [str(column).lower() for column in df.columns]
    return _records(df[["x", "y", "z"]])


def get_profile_meta(
    filename: str,
    point: str,
    tool_name: str | None = None,
) -> AfmProfileMeta | None:
    # The units are the object's user metadata, so this is a stat, not a download.
    declared = _user_metadata(_profile_key(filename, point, tool_name))
    if declared is None:
        return None
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
        if _is_original(name):
            # A browser cannot draw a TIFF; it is offered as a download instead.
            continue
        encoded = quote(name, safe="")
        image = {"name": name, "url": f"{base}/images/{image_type}/{encoded}{tool}"}
        # The page shows 원본 다운로드 only where this key is present.
        if _original_key(record, name):
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
    if record is None or _is_original(name):
        return None
    return _object(_key_named(record, image_type, name))


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
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return {"filename": _basename(key), "content_type": content_type, "data": data}


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
