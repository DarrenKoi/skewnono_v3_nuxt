# Resolution Center — Flat Field Set + Per-Condition Timeseries — Design

Date: 2026-07-24
Feature: `hardware` → `reso-center` (CD-SEM only)

## Goal

Bring the Resolution Center panel and its `reso_center_log` data in line with the
office schema: a flat scalar doc (no focus-sweep objects), `ResoDelta` derived as
the difference between `BestReso` and `ResoIScenter`, and a timeseries chart that
shows the two resolution lines per `beam_condition`. Remove Focus Sweep entirely.

## Scope

In scope:

- Backend mock `providers/reso_center/mock.py` — flat doc, derived `ResoDelta`.
- Backend `providers/reso_center/office_example.py` — docstring only (still a
  `NotImplementedError` template).
- `__fixtures__/hardware-reso-center.json` — regenerate to the new shape.
- `docs/datatables/reso_center_data.txt` — rewrite to the 13-field list.
- Frontend `app/components/ebeam/hardware/ResoCenterPanel.vue` — drop sweep +
  time selector, two-line per-condition timeseries.

Out of scope:

- The office adapter body (deferred to office; template docstring only).
- `MIGRATION.md` — its reso-center references are generic and stay accurate.
- `ops_index_mgmt/beam_reso_cdsem.py` — the store-only `Resolution_Range*`
  mapping is harmless if unused; the office may keep or drop it independently.

## Data Shape

`reso_center_log` doc is exactly these 13 fields:

`category` ("reso_center_log"), `CenterX`, `CenterY`, `BestReso`,
`ResoIScenter`, `ResoDelta`, `beam_condition`, `timestamp`, `timestamp_date`,
`eqp_ip`, `eqp_id`, `fac_id`, `fab_name`.

Removed: `Resolution_Range`, `Resolution_Range_Raw`, `Resolution_Range_Smooth`,
`fdc_category`.

`ResoDelta` semantics: `BestReso` is the best-focus resolution (the minimum over
the sweep), `ResoIScenter` is resolution at center focus, so
`ResoDelta = round(ResoIScenter − BestReso, 2)` and is `≥ 0`. The mock generates
`ResoIScenter = BestReso + uniform(0, 0.12)` so the three stay consistent; the
office passes the stored `ResoDelta` through.

## Provider Behavior

- Mock: deterministic per `eqp_id`, ascending by `(timestamp, beam_condition)`,
  two beam conditions per moment, unchanged cadence. Only the per-doc field set
  and the `ResoDelta`/`ResoIScenter` relationship change.
- Office (template): fetch raw `reso_center_log` docs scoped to `[start, end]`,
  ascending by `timestamp`, CD-SEM only; the dispatcher wraps with
  `normalizers.docs_payload`. No sweep post-processing.

## Frontend Behavior

- `beam_condition` is a required single-select; default = first concrete
  condition. No "All conditions" option (merging conditions makes the timeseries
  a meaningless zig-zag).
- Charts (two, side by side):
  - Center Drift scatter — `CenterX` vs `CenterY`, latest emphasized, scoped to
    the selected condition.
  - Resolution Trend — `BestReso` and `ResoIScenter` as two lines on one shared
    nm y-axis; tooltip shows `Best · ISCenter · Δ` (Δ from the stored
    `ResoDelta`). BM/PM `markLine` retained on one series.
- Removed: Focus Sweep chart, the measurement-time selector, and the
  click-to-highlight (their only purpose was choosing a sweep to display).

## Testing

- `test_contract.py` stays green (validates the `HardwarePayload` envelope).
- Add an assertion that reso-center docs carry none of the removed keys and that
  `ResoDelta == round(ResoIScenter − BestReso, 2)` for every doc.
- Manual: launch the app, open Hardware → Reso Center on a CD-SEM tool, confirm
  the two-line timeseries per `beam_condition`, tooltip Δ, and no sweep chart.
