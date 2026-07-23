# Hardware Daily FDC Office Adapter — Design

- **Date:** 2026-07-22
- **Feature:** `back_dev_home/ebeam/hitachi/hardware`
- **Status:** Approved design, pending implementation plan

## Goal

Connect the Hardware page's Daily FDC tab to the office OpenSearch index
`network_fdc_cdsem` without changing the Flask route or frontend response
contract. This first increment supports CD-SEM only. HV-SEM FDC data has not
been gathered yet, and the other Hardware tabs will be connected separately.

## Scope

The implementation updates only the tracked template
`providers/office_example.py`. At the office, that template is copied to the
gitignored `providers/office.py` before enabling the provider.

In scope:

- CD-SEM FDC document lookup for one selected equipment ID.
- The request's inclusive `start` and `end` timestamp window.
- Ascending timestamp order required by the FDC charts and `docs_payload()`.
- Validation of the four known FDC document shapes.
- The existing empty-selection response when no equipment is selected.

Out of scope:

- HV-SEM FDC.
- BSM, Reso Center, MDC, SCE, BM/PM, and Sharpness office sources.
- Mock fallback from the office adapter.
- Route, frontend, contract, normalizer, or provider-selection changes.
- OpenSearch aggregation or chart downsampling.

## Provider Behavior

`get_hardware_service()` dispatches only the `fdc` service for `cdsem`.
Requests for every other service, and FDC requests for `hvsem`, raise a clear
`NotImplementedError`. This is intentional: office mode must not silently
return mock or placeholder data for tabs whose real source is not connected.

When `eqp_id` is `None`, the adapter does not contact OpenSearch. It returns an
available-but-empty FDC payload with the existing equipment-selection hint,
empty cards, and empty tables.

When an equipment ID is present, the adapter queries OpenSearch and wraps the
result with the existing `docs_payload()` normalizer. A selected tool with no
matching documents is a valid empty result: `available` remains true,
`doc_count` is zero, and `docs` is an empty list.

## OpenSearch Query

The fixed index is `network_fdc_cdsem`. The selected tool is matched exactly
through `eqp_id.keyword`, because `eqp_id` is a `text` field with a `keyword`
subfield.

The query uses these filters:

```python
[
    {"term": {"eqp_id.keyword": eqp_id}},
    {
        "range": {
            "timestamp": {
                "gte": start.isoformat(),
                "lte": end.isoformat(),
            }
        }
    },
]
```

OpenSearch sorts by `timestamp` ascending. The adapter requests only these
mapped source fields:

- `eqp_id`
- `eqp_ip`
- `eqp_model_cd`
- `fab_name`
- `fdc_key`
- `os_inserted`
- `timestamp`
- `values`

`fab_name` is not an additional query filter because the selected `eqp_id` is
the lookup identity supplied by the Hardware tool selector. The document's
actual `fab_name` remains in the returned raw source.

The query uses the repository's shared `_office_search.fetch_hits()` helper so
OpenSearch configuration, connection reuse, and missing-index errors follow
the same conventions as the other Hitachi office adapters.

## Result Bound and Validation

The first implementation uses a 10,000-document request cap. Reaching the cap
raises `LookupError` rather than returning a possibly truncated chart. This is
an explicit operational signal to narrow the requested window or introduce a
paginated/downsampled contract later.

Every returned document must have:

- the selected `eqp_id`;
- a non-empty `timestamp`;
- one of `SPMVoltages`, `ContactpinConductionInfo`, `LaserPower`, or
  `TemperatureEChuck` as `fdc_key`;
- `values` as a list whose first item equals `fdc_key`.

Unexpected or malformed documents raise `ValueError`. The adapter preserves
the original `values` list and the requested mapped metadata instead of
interpreting the FDC measurements in Python; the existing frontend parser
continues to own the per-key presentation logic.

## Error Handling

- Missing OpenSearch configuration or a connection failure propagates through
  the shared office-search error path.
- A missing `network_fdc_cdsem` index becomes a clear `LookupError`.
- A result at the document cap raises `LookupError` to prevent silent partial
  history.
- A malformed document raises `ValueError` with the equipment ID and offending
  field context.
- Unsupported service or tool-family requests raise `NotImplementedError` and
  name the unconnected scope.

The Hardware page's separate BM/PM overlay request may fail while that source
is unconnected; the frontend already treats that secondary request as no
overlay markers, so the primary FDC panel remains usable.

## Verification

Before copying the template to `office.py`:

- Import and compile the updated module without contacting OpenSearch.
- Exercise the query builder and response normalization with a fake
  `fetch_hits()` result covering all four FDC keys.
- Verify exact `eqp_id.keyword` filtering, inclusive timestamp bounds,
  ascending sort, and source-field projection.
- Verify no-equipment behavior without an OpenSearch call.
- Verify malformed documents, cap detection, HV-SEM FDC, and non-FDC services
  fail explicitly.
- Run `git diff --check`.

At the office, copy the template to `providers/office.py`, configure
`OPENSEARCH_*`, and run a selected CD-SEM equipment smoke check against a
short date window. The current all-service Hardware office contract test is
not expected to pass until the remaining Hardware services are connected.
