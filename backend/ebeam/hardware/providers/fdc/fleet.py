"""FDC fab fleet view — the one aggregation both providers share.

The office writer stores typed side-fields next to `values`
(`ops_index_mgmt/network_fdc_cdsem.side_fields`, office 확인 2026-09-28), so a
fleet view is one native aggregation instead of a raw pull. This module owns
the request body (`fleet_aggs`) and turns the response into the contract
(`fleet_from_aggs`). The office adapter sends the body to OpenSearch; the mock
emulates the response from its own docs. Either way the same normalizer runs,
so home exercises the office's parsing path.

Old docs carry no side-fields (no backfill), so the view fills in over ~30 days
from the writer's deployment. Averages are immune to the index's exact
duplicates; counts are not (~1 %), so Contactpin counts use `cardinality` on
`timestamp`. `_id` is fab_eqp_key_timestamp, which makes a distinct
timestamp exactly one deduped doc. SPM is never fleet-compared: per-tool unit
scales differ up to 100x.
"""

from typing import Any

from backend.ebeam._tool_specs import model_to_tool_type
from backend.ebeam.hardware.contracts import FdcFleet, FdcFleetTool


__all__ = ["SPREAD_BIN_WIDTH", "fab_roster", "fleet_aggs", "fleet_from_aggs"]

# Office field names (dynamic mapping: strings aggregate on .keyword). The
# writer stores `pin_judgment` / `spm_judgment`, no 'e' (office 확인
# 2026-09-28). A wrong name is not an error: OpenSearch answers an unmapped
# field with empty buckets, so the view would stay blank forever.
JUDGMENT_KW = "pin_judgment.keyword"
CHANNEL_KW = "pin_channel.keyword"
SPREAD_BIN_WIDTH = 2.0
# Tools in one fab are tens, so one terms page holds them all.
_TOOLS_SIZE = 500
# cardinality is exact only below its precision_threshold (default ~3000). The
# busiest tools log ~2.7k Contactpin docs per 30 days (office 확인
# 2026-09-28), so the default sits at the edge; 40000 is the cap and keeps a
# longer window exact.
_CARDINALITY_PRECISION = 40_000


def fab_roster(rows: list[dict], fab_name: str) -> dict[str, str]:
    """eqp_id -> eqp_model_cd for the fab's CD-SEM tools (first row wins; the
    roster repeats a few ids). FDC is CD-SEM only."""
    fab = fab_name.strip().upper()
    roster: dict[str, str] = {}
    for row in rows:
        if str(row.get("fab_name", "")).strip().upper() != fab:
            continue
        if model_to_tool_type(str(row.get("eqp_model_cd", ""))) != "cd-sem":
            continue
        roster.setdefault(str(row["eqp_id"]), str(row["eqp_model_cd"]))
    return roster


def fleet_aggs() -> dict[str, Any]:
    """The request's `aggs`: per tool, window means, daily temp means, deduped
    Contactpin counts and counter spans; fleet-wide, the margin histogram."""
    return {
        "tools": {
            "terms": {"field": "eqp_id.keyword", "size": _TOOLS_SIZE},
            "aggs": {
                "temp_c": {"avg": {"field": "temp_c"}},
                "laser_x1": {"avg": {"field": "laser_x1"}},
                "laser_y1": {"avg": {"field": "laser_y1"}},
                "days": {
                    "date_histogram": {
                        "field": "timestamp", "calendar_interval": "1d",
                        "format": "yyyy-MM-dd", "min_doc_count": 1,
                    },
                    "aggs": {"temp_c": {"avg": {"field": "temp_c"}}},
                },
                "judgment": {
                    "terms": {"field": JUDGMENT_KW, "size": 10},
                    "aggs": {"docs": {"cardinality": {
                        "field": "timestamp", "precision_threshold": _CARDINALITY_PRECISION,
                    }}},
                },
                "channels": {
                    "terms": {"field": CHANNEL_KW, "size": 10},
                    "aggs": {
                        "c_min": {"min": {"field": "pin_counter"}},
                        "c_max": {"max": {"field": "pin_counter"}},
                        "t_min": {"min": {"field": "timestamp"}},
                        "t_max": {"max": {"field": "timestamp"}},
                    },
                },
            },
        },
        "margin": {
            "terms": {"field": JUDGMENT_KW, "size": 10},
            "aggs": {"spread": {"histogram": {"field": "pin_spread", "interval": SPREAD_BIN_WIDTH}}},
        },
    }


def _value(node: dict[str, Any], key: str) -> float | None:
    value = (node.get(key) or {}).get("value")
    return None if value is None else float(value)


def _buckets(node: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return (node.get(key) or {}).get("buckets") or []


def fleet_from_aggs(aggs: dict[str, Any], roster: dict[str, str]) -> FdcFleet:
    """An aggregation response -> the contract, tools sorted by eqp_id."""
    tools: list[FdcFleetTool] = []
    for bucket in _buckets(aggs, "tools"):
        eqp_id = str(bucket["key"])
        temp_days = [
            {"day": str(day["key_as_string"]), "temp_c": temp}
            for day in _buckets(bucket, "days")
            if (temp := _value(day, "temp_c")) is not None
        ]
        rates = []
        for channel in _buckets(bucket, "channels"):
            c_min, c_max = _value(channel, "c_min"), _value(channel, "c_max")
            t_min, t_max = _value(channel, "t_min"), _value(channel, "t_max")
            days = None if t_min is None or t_max is None else (t_max - t_min) / 86_400_000
            per_day = (c_max - c_min) / days if days and c_min is not None and c_max is not None else None
            rates.append({"channel": str(channel["key"]), "per_day": per_day})
        tools.append({
            "eqp_id": eqp_id,
            "eqp_model_cd": roster.get(eqp_id),
            "temp_c": _value(bucket, "temp_c"),
            "temp_days": temp_days,
            "laser_x1": _value(bucket, "laser_x1"),
            "laser_y1": _value(bucket, "laser_y1"),
            "pin_counts": {
                str(j["key"]): int(_value(j, "docs") or 0) for j in _buckets(bucket, "judgment")
            },
            "counter_rates": sorted(rates, key=lambda r: r["channel"]),
        })
    spread_bins = [
        {"judgment": str(j["key"]), "lo": float(h["key"]), "count": int(h["doc_count"])}
        for j in _buckets(aggs, "margin")
        for h in _buckets(j, "spread")
    ]
    return {
        "tools": sorted(tools, key=lambda t: t["eqp_id"]),
        "spread_bins": spread_bins,
        "spread_bin_width": SPREAD_BIN_WIDTH,
    }
