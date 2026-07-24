# TEMPLATE — copy to office.py at the office, then run the Verify command.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office BSM adapter — faithful ``beam_shape`` (``type: "total"``) docs.

Source: OpenSearch ``beam_shape`` index, the ``type:"total"`` /
``fdc_category:"bsi_beam_shape"`` documents (CD-SEM only). Return the raw docs
ascending by ``(timestamp, beam_condition)`` scoped to ``[start, end]``; the
top-level ``providers/office.py`` dispatcher wraps them with
``normalizers.docs_payload``. The hardware page reads filter/axis/metric fields
straight off each doc (see ``front-dev-home/app/utils/beamMetrics.ts``), so the
field NAMES must stay identical to ``bsm/mock.py`` — only the value SHAPES are
normalized here.

Two real-source shapes differ from the mock and would silently drop metrics if
passed through verbatim (the frontend classifies a radar metric as a length-16
numeric array, and ignores anything else):

* ``Reso EB Focus`` arrives doubly-nested — ``[['8.94', ... 16 ...]]`` (a
  length-1 array holding one inner array). Flattened to a flat length-16 array
  so it classifies as a radar (profile) metric like the other per-degree keys.
* ``Reso EB Focus Range`` arrives as a one-element list — ``['8.0000']``. That
  is neither a length-16 array nor a scalar, so the panel ignores it entirely.
  Unwrapped to a bare float here so it surfaces as a scalar trend / KPI metric
  (focus-range drift over time). ``bsm/mock.py`` emits the same float scalar so
  home and office render this field identically.

Per-degree arrays and scalars are coerced to floats (the source mixes floats
and numeric strings — ``'6.118456'`` — within the same array). Anything that
cannot be coerced to a clean length-16 numeric array is DROPPED from the doc
rather than emitted malformed, mirroring the source rule "if not 16 numbers we
ignore". The metadata tail (``type``, ``beam_condition``, ``fdc_category``,
``category``, ``timestamp*``, ``eqp_ip``, ``eqp_id``, ``fac_id``, ``fab_name``)
passes through verbatim.

Timezone: ``beam_shape`` stores KST wall-clock ``timestamp`` values without an
offset (the office storage convention, same as the meas_hist indices). The
range filter is built from the naive ``start``/``end`` the route already
anchors to ``datetime(2026, 5, 24, 9, 0)``, so both sides compare KST-as-UTC
wall-clock and line up.

OFFICE-VERIFY (check once on the first office run):
* Index/alias name is ``beam_shape`` (``INDEX`` below). Adjust if the alias
  differs.
* ``type`` / ``fdc_category`` / ``eqp_id`` / ``fab_name`` are matched through
  their ``.keyword`` sub-fields (the convention for analyzed ``text`` mappings
  here). If these are mapped as bare ``keyword`` the ``.keyword`` suffix must
  be dropped.
* ``fab_name`` is uppercased for the term match (M16A, R3, ...), matching the
  meas_hist convention. Confirm one real ``fab_name`` value.

At the office: fill in OPENSEARCH_* in ``back_dev_home/.env``,
``cp office_example.py office.py``, set ``SKEWNONO_HARDWARE_PROVIDER=office``,
then run the Verify command in ``hardware/MIGRATION.md``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from back_dev_home.ebeam.hitachi._office_search import (
    fetch_hits,
    query as _query,
    text as _text,
)


__all__ = ["build_beam_shape_docs"]


# OpenSearch index/alias holding the beam_shape documents (CD-SEM only).
INDEX = "beam_shape"

# Fixed selectors for the faithful "total" docs (per docs/datatables/beam_shape.txt).
DOC_TYPE = "total"
FDC_CATEGORY = "bsi_beam_shape"

# Exact-match fields go through their .keyword sub-fields: the base mappings are
# `text` (analyzed), so a term query on them matches nothing.
TYPE_KW = "type.keyword"
FDC_CATEGORY_KW = "fdc_category.keyword"
EQP_ID_KW = "eqp_id.keyword"
FAB_NAME_KW = "fab_name.keyword"
TIME_FIELD = "timestamp"  # date field: drives the range filter and the sort

# One doc per (timestamp, beam_condition). A 30-day window over a handful of
# conditions at ~3 runs/day is well under this cap; it exists only so a mapping
# surprise cannot pull an unbounded result set. Truncation is detected below.
MAX_DOCS = 10_000

# Keys carrying per-degree arrays. `Reso EB Focus` rides here too — it is a
# length-16 profile once flattened. The frontend derives the metric list from
# the doc, so this only governs coercion, not what the UI shows.
_PROFILE_KEYS = frozenset({
    "Reso EB",
    "Reso Detector",
    "Noise",
    "Focus offset",
    "Apature angle factor",
    "Reso EB Focus",
})

# Scalar summary keys (one float each).
_SCALAR_KEYS = frozenset({
    "Major Axis",
    "Minor Axis",
    "Ellipicity",
    "Tilt",
    "X range",
    "Y range",
    "Area",
    "Ave. Reso Detector",
    "Ave. Noise",
    "Ave. Apature angle factor",
})

# Metadata passed through verbatim (strings / already-correct types).
_META_KEYS = (
    "category",
    "type",
    "beam_condition",
    "fdc_category",
    "timestamp",
    "timestamp_date",
    "eqp_ip",
    "eqp_id",
    "fac_id",
    "fab_name",
)

# `degree` is the 16-step angular axis; emitted like a profile but never a metric.
_DEGREE_KEY = "degree"
# One-element list in the source; unwrapped to a scalar for display.
_RANGE_KEY = "Reso EB Focus Range"


def _as_float(value: Any) -> float | None:
    """Coerce a source cell (float OR numeric string) to a finite float."""
    if isinstance(value, bool):  # bool is an int subclass — never a measurement
        return None
    if isinstance(value, (int, float)):
        f = float(value)
    elif isinstance(value, str):
        try:
            f = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _flatten16(value: Any) -> list[float] | None:
    """A source per-degree field as a flat length-16 float array, or None.

    Handles both the flat shape and the doubly-nested ``[[...16...]]`` shape
    ``Reso EB Focus`` arrives in. Returns None when the result is not exactly
    16 clean numbers, so the caller drops the key (source rule: "if not 16
    numbers we ignore").
    """
    if not isinstance(value, (list, tuple)):
        return None
    # Unwrap a length-1 wrapper around the real array (Reso EB Focus).
    if len(value) == 1 and isinstance(value[0], (list, tuple)):
        value = value[0]
    if len(value) != 16:
        return None
    out: list[float] = []
    for cell in value:
        f = _as_float(cell)
        if f is None:
            return None
        out.append(f)
    return out


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    """Reshape one raw ``_source`` doc to match ``bsm/mock.py``'s shape."""
    out: dict[str, Any] = {}

    # Angular axis + per-degree profiles (incl. the flattened Reso EB Focus).
    degrees = _flatten16(doc.get(_DEGREE_KEY))
    if degrees is not None:
        out[_DEGREE_KEY] = degrees
    for key in _PROFILE_KEYS:
        if key not in doc:
            continue
        arr = _flatten16(doc.get(key))
        if arr is not None:
            out[key] = arr  # else drop: a non-16 array loses credibility

    # Scalars.
    for key in _SCALAR_KEYS:
        if key not in doc:
            continue
        f = _as_float(doc.get(key))
        if f is not None:
            out[key] = f

    # Reso EB Focus Range: unwrap the 1-element list to a scalar float so the
    # panel surfaces it as a trend / KPI metric (see module docstring).
    if _RANGE_KEY in doc:
        raw = doc.get(_RANGE_KEY)
        if isinstance(raw, (list, tuple)) and raw:
            raw = raw[0]
        f = _as_float(raw)
        if f is not None:
            out[_RANGE_KEY] = f

    # Metadata tail, verbatim (strings normalized so "None"/NaN fall out).
    for key in _META_KEYS:
        if key in doc:
            out[key] = _text(doc.get(key)) if key != "fab_name" else doc.get(key)
    return out


def build_beam_shape_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Ascending-time faithful ``total`` beam_shape docs across ``[start, end]``.

    One doc per (timestamp, beam_condition). Filtered to the ``total`` /
    ``bsi_beam_shape`` documents for ``eqp_id`` (when given) and ``fab_name``
    (when given), then reshaped to match ``bsm/mock.py``.
    """
    clauses: list[dict[str, Any]] = [
        {"term": {TYPE_KW: DOC_TYPE}},
        {"term": {FDC_CATEGORY_KW: FDC_CATEGORY}},
        {
            "range": {
                TIME_FIELD: {
                    "gte": start.strftime("%Y-%m-%dT%H:%M:%S"),
                    "lte": end.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            }
        },
    ]
    if eqp_id:
        clauses.append({"term": {EQP_ID_KW: eqp_id}})
    if fab_name:
        clauses.append({"term": {FAB_NAME_KW: fab_name.strip().upper()}})

    hits = fetch_hits(
        INDEX,
        _query(clauses),
        size=MAX_DOCS,
        sort=[{TIME_FIELD: "asc"}],
    )
    if len(hits) == MAX_DOCS:
        raise LookupError(
            f"beam_shape returned {MAX_DOCS} documents (the cap) for the "
            "requested window — showing a truncated series would misreport the "
            "trend. Narrow the window or raise MAX_DOCS."
        )

    docs = [_normalize(hit) for hit in hits]
    # Match the mock's ordering exactly: (timestamp, beam_condition) ascending.
    docs.sort(key=lambda d: (_text(d.get("timestamp")), _text(d.get("beam_condition"))))
    return docs


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #   .venv/bin/python -m back_dev_home.ebeam.hitachi.hardware.providers.bsm.office
    import sys
    from datetime import timedelta

    eqp = sys.argv[1] if len(sys.argv) > 1 else ""
    now = datetime(2026, 5, 24, 9, 0)
    result = build_beam_shape_docs(eqp, None, now - timedelta(days=30), now)
    print(f"{len(result)} docs for eqp_id={eqp!r}")
    if result:
        d = result[0]
        conds = sorted({r.get("beam_condition") for r in result})
        print("beam_conditions:", conds)
        print("first ts:", d.get("timestamp"), "| category:", d.get("category"))
        print("Reso EB len:", len(d.get("Reso EB", [])),
              "| Reso EB Focus len:", len(d.get("Reso EB Focus", [])))
        print("Reso EB Focus Range:", d.get("Reso EB Focus Range"))
