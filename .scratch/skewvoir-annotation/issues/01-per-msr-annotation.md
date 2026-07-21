# Per-MSR annotation (측정 주석) — staged feature

Type: task
Status: needs-triage

## Background

The skewvoir analysis workspace LeftRail once showed a dead `+ Annotate`
button (`onClick: undefined`, staged "for the feature discussion to follow").
It was removed on 2026-07-22 — a dead control in an engineer tool erodes trust
in every other control. This ticket carries the staged intent instead of the UI.

## What annotation would mean for engineers

An engineer attaches a judgment to a measurement (MSR): e.g. "이 CD outlier는
EQ12 PM 직후 회복 구간, 실제 skew 아님", "이슈 확정, OCAP 발행". The value is
institutional memory — the next engineer who opens the same MSR (or finds it
in search) sees the verdict instead of re-investigating.

## Minimum viable shape

- Per-MSR text note + small verdict tag (정상 / 이상 / 조치완료), authored
  identity from the existing `_auth` / x-id layer.
- New backend feature slice `annotations/` following the standard convention:
  `routes.py` + `contracts.py` + `data.py` + `providers/{mock,office_example}.py`
  and a `MIGRATION.md`. Needs a WRITE path office-side — everything skewvoir
  reads today is read-only, so the office store (Redis/OpenSearch) write design
  is the main new ground.
- Writing without reading surfaces is pointless: annotations must appear on
  the LeftRail selection card and in search results at minimum (chart-point
  badges optional later).

## Sequencing

Deferred alongside the parked chat feature (next SKEWNONO version bucket).
Do not start while Phase 2 office wiring of the 16 read-only features is
still pending. When picked up, run a proper brainstorm/spec session first
(`spec.md` in this directory).
