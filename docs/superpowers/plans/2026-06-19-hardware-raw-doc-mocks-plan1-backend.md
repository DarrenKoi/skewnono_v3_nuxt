# Hardware Raw-Doc Mocks — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mock the five OpenSearch-sourced hardware datasets (`bsm`/beam_shape, `reso-center`, `fdc`, `mdc`, `sce`) in the Flask Phase-1 mock backend in their **final retrieved form** (the dict/dict-of-dict shapes documented in `docs/datatables/*.txt`), migrate the hardware route to the equipment-first URL `GET /api/{tool_slug}/hardware/{eqp_id}/{service}`, and expose two new faithful payload fields (`docs`, `settings`). This is the BACKEND half only; the frontend (hardware page UI/UX) is a separate plan.

**Architecture:** Feature-sliced Flask backend under `back_dev_home/ebeam/hitachi/hardware/`. The route layer (`routes.py`) parses the URL + query params and validates; the swap surface (`data.py`) selects mock vs. office provider; `providers/mock.py` dispatches per-service to faithful deterministic generators (`beam_shape_mock.py`, `reso_center_mock.py`, `fdc_mock.py`, `mdc_mock.py`, `sce_mock.py`); `normalizers.py` wraps generated data into the canonical `HardwarePayload` envelope; `contracts.py` is the TypedDict source of truth; `metrics.py` is the beam_shape metric registry that the bsm generator fabricates from. Per the cross-phase principle, the home↔office swap stays isolated to `providers/`; `routes.py`/`normalizers.py`/`contracts.py` do not branch on phase.

**Tech Stack:** Python 3.11, Flask Blueprints, pandas (`DataFrame.to_dict`), deterministic `random.Random` seeded from `md5(eqp_id)`. NO pytest in this project — verification is via runnable `python -c "..."` import-and-assert gates plus the contract harness (`scripts/capture_fixtures.py` + `scripts/check_contract.py`).

## Global Constraints

These are project-wide rules. Every task must honour all of them.

1. **No pytest.** This repo has no pytest and you must not introduce it. Verify backend logic with small `python -c "..."` one-liners (run before the code exists → observe `ImportError`/`AttributeError` = RED; run after implementing → observe assertions pass = GREEN), plus the contract harness at the end.
2. **Determinism.** Every generator seeds a `random.Random` from `int(hashlib.md5(eqp_id.encode("utf-8")).hexdigest()[:8], 16)` and anchors time at `NOW = datetime(2026, 5, 24, 9, 0)`. Mirror `providers/bsm_mock.py` and `providers/bm_pm_mock.py` exactly. Same `eqp_id` ⇒ identical docs on every request and across restarts.
3. **Keep `providers/bsm_mock.py` UNTOUCHED.** `back_dev_home/ebeam/hitachi/pm_planning/data.py` imports `build_bsm_data` from it for the BM/PM Up gate. The new faithful beam_shape generator is a **separate new file** `providers/beam_shape_mock.py`. The two BSM representations coexist by design.
4. **Faithful field spellings.** Preserve every field name and the source misspellings exactly: `Ellipicity` (not Ellipticity), `Apature angle factor` (not Aperture). Preserve the full metadata tail on every time-series doc: `timestamp`, `timestamp_date`, `eqp_ip`, `eqp_id`, `fac_id`, `fab_name`, `fdc_category`. Never emit a per-degree array shorter than 16 (source note: short arrays lose credibility).
5. **Swap surface stays intact.** `data.py` only selects a provider; it never branches on service internals. Office stubs return `available: false` for the new services (no real OpenSearch wiring this round).
6. **Contract + fixtures are deliverables.** The final task updates `docs/api-contracts/hardware.yaml`, adds the new endpoints to `scripts/capture_fixtures.py` ENDPOINTS, and runs capture + check_contract.
7. **Port note.** The capture/check scripts hardcode `http://localhost:5000`, but the user runs Flask on **:5050** in PyCharm (Windows reserves 5000). When a verification step hits the live server, use whatever port Flask is actually running on and adjust `FLASK_BASE` if needed. **Do not start Flask yourself** — the user runs it.
8. **Style.** Use `from __future__ import annotations` consistent with existing files where new modules want it; match the existing module docstring + `__all__` conventions.

---

## File Structure

| File | Created/Modified | One responsibility |
| --- | --- | --- |
| `back_dev_home/ebeam/hitachi/hardware/contracts.py` | Modified | Rename `fab_id`→`fab_name`; add `docs`/`settings` to `HardwarePayload`; remove `BsmBlock`/`BsmSummaryRow`/`BsmProfile`/`BsmCategory` + the `bsm` field; expand `VALID_SERVICES` to the 6 keys. |
| `back_dev_home/ebeam/hitachi/hardware/metrics.py` | Created | Beam_shape metric registry: the single place each per-degree (`profile16`) / `scalar` key is declared with its plausible range. |
| `back_dev_home/ebeam/hitachi/hardware/providers/beam_shape_mock.py` | Created | Faithful `type:"total"` beam_shape docs across `[start, end]`, multiple `beam_condition`s, all length-16 arrays + scalars, deterministic. |
| `back_dev_home/ebeam/hitachi/hardware/providers/reso_center_mock.py` | Created | Faithful `reso_center_log` docs across `[start, end]` (Raw/Smooth = 5 offsets × 5 numbers + scalars). |
| `back_dev_home/ebeam/hitachi/hardware/providers/fdc_mock.py` | Created | Faithful FDC docs across the 4 `fdc_key`s, each with the correct `values` list structure. |
| `back_dev_home/ebeam/hitachi/hardware/providers/mdc_mock.py` | Created | Faithful dict-of-dict `{eqp_id: {beam_condition: value}}` for the eqp + in-fab siblings, as-of `end`. |
| `back_dev_home/ebeam/hitachi/hardware/providers/sce_mock.py` | Created | Faithful dict-of-dict `{eqp_id: {FileInfo, SemCond, ImgCond, SCEParam, Coefficients[360]}}` for eqp + in-fab siblings, as-of `end`. |
| `back_dev_home/ebeam/hitachi/hardware/providers/_siblings.py` | Created | Shared helper: deterministic in-fab sibling eqp_id set + `eqp_ip`/`fac_id` derivation, used by mdc/sce (and reused for doc metadata tails). |
| `back_dev_home/ebeam/hitachi/hardware/normalizers.py` | Modified | Add `docs_payload()` + `settings_payload()`; remove `bsm_payload`; rename `fab_id`→`fab_name` everywhere. |
| `back_dev_home/ebeam/hitachi/hardware/providers/mock.py` | Modified | Dispatch all 6 services to the right generator; pass `start`/`end`/`fab_name`. |
| `back_dev_home/ebeam/hitachi/hardware/providers/office.py` | Modified | `fab_id`→`fab_name`; stub the new services as `unavailable`. |
| `back_dev_home/ebeam/hitachi/hardware/data.py` | Modified | `fab_id`→`fab_name`; thread `start`/`end` through `get_hardware_service`. |
| `back_dev_home/ebeam/hitachi/hardware/routes.py` | Modified | New path `<eqp_id>/<service>`; parse `fab_name`/`start`/`end`; 30-day default window; as-of for mdc/sce; validation (400s); CD-SEM-only services. |
| `docs/api-contracts/hardware.yaml` | Modified | New `base_path` with `{eqp_id}`; service enum adds `reso-center`/`mdc`/`sce`; query params `fab_name`/`start`/`end`; payload `fab_name` + `docs` + `settings`; worked example. |
| `scripts/capture_fixtures.py` | Modified | Add hardware ENDPOINTS (one per service with representative `eqp_id`/`fab_name`/`start`/`end`). |

Source-of-truth shapes live in `docs/datatables/{beam_shape,reso_center_data,network_fdc_cdsem,mdc_setting,sce_setting}.txt`. Read them again whenever a builder field is unclear.

---

## Task 1 — contracts.py: rename, add docs/settings, drop BsmBlock, expand services

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/contracts.py` (modify)

**Interfaces:**
- Produces: `ServiceKey = Literal["bsm", "reso-center", "fdc", "mdc", "sce", "bm-pm"]`
- Produces: `VALID_SERVICES: frozenset[str]` = those 6 keys
- Produces: `class HardwarePayload(TypedDict)` with fields `tool_slug, service, eqp_id, fab_name, available, fetched_at, summary, cards, tables` + `docs: NotRequired[list[dict]]`, `settings: NotRequired[dict[str, dict]]`, `raw: NotRequired[dict]`
- Removes: `BsmSummaryRow`, `BsmProfile`, `BsmCategory`, `BsmBlock`, and the `bsm` field

**Steps:**

- [ ] **1.1 Write the gate (RED).** Run this and confirm it fails (the new service keys / `fab_name` field / removed types don't exist yet):

  ```bash
  python -c "from back_dev_home.ebeam.hitachi.hardware import contracts as c; \
  assert c.VALID_SERVICES == frozenset({'bsm','reso-center','fdc','mdc','sce','bm-pm'}), c.VALID_SERVICES; \
  assert 'fab_name' in c.HardwarePayload.__annotations__; \
  assert 'fab_id' not in c.HardwarePayload.__annotations__; \
  assert 'docs' in c.HardwarePayload.__annotations__; \
  assert 'settings' in c.HardwarePayload.__annotations__; \
  assert not hasattr(c, 'BsmBlock'); \
  print('OK')"
  ```

- [ ] **1.2 Implement (GREEN).** Replace the entire file with:

  ```python
  """Canonical hardware API contract.

  Raw beam_shape / reso_center / FDC / MDC / SCE sources can use different field
  names per environment. This module defines the stable shape the Flask route
  returns. Faithful raw docs ride in `docs` (time-series) / `settings`
  (dict-of-dict); `cards`/`tables` carry the thin summary the page header reads.
  """

  from typing import Literal, NotRequired, TypeAlias, TypedDict


  ServiceKey = Literal["bsm", "reso-center", "fdc", "mdc", "sce", "bm-pm"]
  VALID_SERVICES: frozenset[str] = frozenset(
      {"bsm", "reso-center", "fdc", "mdc", "sce", "bm-pm"}
  )

  MetricTone = Literal["neutral", "ok", "warning", "bad"]
  RecordValue: TypeAlias = str | int | float | bool | None


  class HardwareMetricCard(TypedDict):
      key: str
      label: str
      value: RecordValue
      unit: NotRequired[str]
      tone: NotRequired[MetricTone]


  class HardwareTableColumn(TypedDict):
      key: str
      label: str
      # Long free-text columns (e.g. engr_note) render truncated with a
      # click-to-expand toggle instead of forcing a wide nowrap cell.
      expandable: NotRequired[bool]


  class HardwareTableSection(TypedDict):
      key: str
      title: str
      columns: list[HardwareTableColumn]
      rows: list[dict[str, RecordValue]]


  class HardwarePayload(TypedDict):
      tool_slug: str
      service: ServiceKey
      eqp_id: str | None
      fab_name: str | None
      available: bool
      fetched_at: str
      summary: str
      cards: list[HardwareMetricCard]
      tables: list[HardwareTableSection]
      # Faithful time-series raw docs (bsm / reso-center / fdc), ascending time.
      docs: NotRequired[list[dict]]
      # Faithful dict-of-dict (mdc / sce): selected eqp + in-fab siblings.
      settings: NotRequired[dict[str, dict]]
      raw: NotRequired[dict]
  ```

- [ ] **1.3 Run the gate (GREEN).** Re-run the 1.1 command; confirm it prints `OK`. (Note: `normalizers.py`, `office.py`, `mock.py`, `data.py`, `routes.py` still reference the old `fab_id`/`bsm_payload`/`BsmBlock` and will be fixed in later tasks. A bare `import` of those modules may break until then — that's expected; the gate above imports only `contracts`.)
- [ ] **1.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/contracts.py
  git commit -m "refactor(hardware): rename fab_name, add docs/settings, drop BsmBlock; expand services"
  ```

---

## Task 2 — metrics.py: beam_shape metric registry

The bsm generator and the frontend both key off "which doc fields are length-16 arrays vs. scalars". `metrics.py` declares that once. Per the design (§8), adding a future beam_shape key is a single registry entry. The faithful `total` doc fields and their plausible ranges come from `docs/datatables/beam_shape.txt`.

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/metrics.py` (create)

**Interfaces:**
- Produces: `BeamShapeMetric = TypedDict("BeamShapeMetric", {"key": str, "kind": Literal["profile16","scalar"], "low": float, "high": float})`
- Produces: `BEAM_SHAPE_METRICS: list[BeamShapeMetric]`
- Produces: `PROFILE16_KEYS: list[str]` (every metric whose `kind == "profile16"`)
- Produces: `SCALAR_KEYS: list[str]` (every metric whose `kind == "scalar"`)

**Steps:**

- [ ] **2.1 Write the gate (RED).**

  ```bash
  python -c "from back_dev_home.ebeam.hitachi.hardware import metrics as m; \
  assert 'Reso EB' in m.PROFILE16_KEYS and 'Reso Detector' in m.PROFILE16_KEYS; \
  assert 'Apature angle factor' in m.PROFILE16_KEYS; \
  assert 'Ellipicity' in m.SCALAR_KEYS and 'Ave. Noise' in m.SCALAR_KEYS; \
  assert all(set(x) >= {'key','kind','low','high'} for x in m.BEAM_SHAPE_METRICS); \
  assert all(x['kind'] in ('profile16','scalar') for x in m.BEAM_SHAPE_METRICS); \
  print('OK', len(m.BEAM_SHAPE_METRICS))"
  ```

- [ ] **2.2 Implement (GREEN).** Write the file:

  ```python
  """Beam_shape metric registry — the single declaration of every beam_shape
  (`type: "total"`) measurement field, its kind, and its plausible value band.

  `providers/beam_shape_mock.py` fabricates each doc straight off this list, and
  the hardware page reads the same keys off the returned docs (data-driven
  selectors). Adding a future field = one entry here; the mock emits it and the
  UI surfaces it with no further code change.

  Ranges are anchored to the sample doc in `docs/datatables/beam_shape.txt`.
  `profile16` keys produce a length-16 per-degree array; `scalar` keys produce
  one float. The `degree` axis and the `Reso EB Focus` / `Reso EB Focus Range`
  fields are emitted by the generator directly (not range-driven), so they are
  not in this registry.
  """

  from __future__ import annotations

  from typing import Literal, TypedDict


  class BeamShapeMetric(TypedDict):
      key: str
      kind: Literal["profile16", "scalar"]
      low: float
      high: float


  # Order matters only for readability; the generator emits all of them.
  BEAM_SHAPE_METRICS: list[BeamShapeMetric] = [
      # --- per-degree 16-arrays --------------------------------------------
      {"key": "Reso EB", "kind": "profile16", "low": 7.90, "high": 8.30},
      {"key": "Reso Detector", "kind": "profile16", "low": 0.0030, "high": 0.0070},
      {"key": "Noise", "kind": "profile16", "low": 6.00, "high": 6.50},
      {"key": "Focus offset", "kind": "profile16", "low": 4.00, "high": 8.00},
      {"key": "Apature angle factor", "kind": "profile16", "low": 0.00100, "high": 0.00160},
      # --- scalars ----------------------------------------------------------
      {"key": "Major Axis", "kind": "scalar", "low": 8.05, "high": 8.20},
      {"key": "Minor Axis", "kind": "scalar", "low": 7.85, "high": 8.00},
      {"key": "Ellipicity", "kind": "scalar", "low": 1.000, "high": 1.060},
      {"key": "Tilt", "kind": "scalar", "low": -45.0, "high": -25.0},
      {"key": "X range", "kind": "scalar", "low": 8.00, "high": 8.15},
      {"key": "Y range", "kind": "scalar", "low": 7.95, "high": 8.05},
      {"key": "Area", "kind": "scalar", "low": 198.0, "high": 208.0},
      {"key": "Ave. Reso Detector", "kind": "scalar", "low": 0.0025, "high": 0.0040},
      {"key": "Ave. Noise", "kind": "scalar", "low": 6.20, "high": 6.35},
      {"key": "Ave. Apature angle factor", "kind": "scalar", "low": 0.00110, "high": 0.00130},
  ]

  PROFILE16_KEYS: list[str] = [m["key"] for m in BEAM_SHAPE_METRICS if m["kind"] == "profile16"]
  SCALAR_KEYS: list[str] = [m["key"] for m in BEAM_SHAPE_METRICS if m["kind"] == "scalar"]

  __all__ = ["BeamShapeMetric", "BEAM_SHAPE_METRICS", "PROFILE16_KEYS", "SCALAR_KEYS"]
  ```

- [ ] **2.3 Run the gate (GREEN).** Re-run 2.1; confirm `OK 15`.
- [ ] **2.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/metrics.py
  git commit -m "feat(hardware): add beam_shape metric registry (metrics.py)"
  ```

---

## Task 3 — providers/_siblings.py: deterministic in-fab sibling set + metadata helpers

mdc/sce return the requested eqp + 3–5 in-fab siblings (§3.3, §9). Several builders also need a faithful metadata tail (`eqp_ip`, `fac_id`, `fab_name`, `timestamp_date`). Centralize both so every generator agrees on the same seeding + IP/fac derivation. `fac_id` derives from `fab_name` the way `sem_list/data.py` builds it (`M16B` → `M16`; `R3`/`R4` → themselves).

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/providers/_siblings.py` (create)

**Interfaces:**
- Produces: `seed_for(eqp_id: str) -> int`
- Produces: `NOW: datetime` = `datetime(2026, 5, 24, 9, 0)`
- Produces: `fac_id_for(fab_name: str | None) -> str`
- Produces: `eqp_ip_for(eqp_id: str) -> str`
- Produces: `sibling_eqp_ids(eqp_id: str, fab_name: str | None, *, count_low: int = 3, count_high: int = 5) -> list[str]` — returns a stable list starting with `eqp_id`, then same-prefix siblings, deterministic per (eqp_id, fab_name)

**Steps:**

- [ ] **3.1 Write the gate (RED).**

  ```bash
  python -c "from back_dev_home.ebeam.hitachi.hardware.providers import _siblings as s; \
  ids = s.sibling_eqp_ids('ECXDX204', 'M16B'); \
  assert ids[0] == 'ECXDX204', ids; \
  assert 4 <= len(ids) <= 6, len(ids); \
  assert ids == s.sibling_eqp_ids('ECXDX204', 'M16B'), 'not deterministic'; \
  assert all(x.startswith('ECXDX') for x in ids), ids; \
  assert s.fac_id_for('M16B') == 'M16' and s.fac_id_for('R3') == 'R3'; \
  assert s.eqp_ip_for('ECXDX204') == s.eqp_ip_for('ECXDX204'); \
  print('OK', ids)"
  ```

- [ ] **3.2 Implement (GREEN).** Write the file:

  ```python
  """Shared deterministic helpers for the fleet-style hardware mocks (mdc/sce)
  and the metadata tail every faithful doc carries.

  Same seed-from-id trick the other providers use, so a given (eqp_id, fab_name)
  always yields the same sibling set, IPs, and fac_id across requests/restarts.
  """

  from __future__ import annotations

  import hashlib
  import random
  import re
  from datetime import datetime


  # Anchor "today" so generated dates are stable regardless of wall clock.
  NOW = datetime(2026, 5, 24, 9, 0)


  def seed_for(eqp_id: str) -> int:
      """Stable int seed from the equipment id (md5, process-salt-free)."""
      digest = hashlib.md5(eqp_id.encode("utf-8")).hexdigest()
      return int(digest[:8], 16)


  def _seed_for_pair(eqp_id: str, fab_name: str | None) -> int:
      digest = hashlib.md5(f"{eqp_id}|{fab_name or ''}".encode("utf-8")).hexdigest()
      return int(digest[:8], 16)


  def fac_id_for(fab_name: str | None) -> str:
      """Derive fac_id from a fab_name the way sem_list builds it.

      `M16B` -> `M16`; `R3`/`R4` -> themselves; unknown/None -> 'M16'.
      """
      if not fab_name:
          return "M16"
      name = fab_name.strip().upper()
      if name in {"R3", "R4"}:
          return name
      m = re.match(r"^(M\d{2})[A-C]?$", name)
      if m:
          return m.group(1)
      return name


  def eqp_ip_for(eqp_id: str) -> str:
      """Deterministic plausible IP for the metadata tail (177./197. nets)."""
      rng = random.Random(seed_for(eqp_id) ^ 0x49502049)  # distinct stream
      prefix = "177" if rng.random() < 0.5 else "197"
      return f"{prefix}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"


  def _prefix_of(eqp_id: str) -> str:
      m = re.match(r"^([A-Za-z]+)", eqp_id)
      return m.group(1) if m else "ECXDX"


  def sibling_eqp_ids(
      eqp_id: str,
      fab_name: str | None,
      *,
      count_low: int = 3,
      count_high: int = 5,
  ) -> list[str]:
      """`eqp_id` first, then 3-5 stable same-prefix in-fab siblings.

      Siblings share the requested tool's id prefix (the in-fab cohort) and are
      seeded from (eqp_id, fab_name) so the set is stable per scope.
      """
      rng = random.Random(_seed_for_pair(eqp_id, fab_name))
      prefix = _prefix_of(eqp_id)
      n = rng.randint(count_low, count_high)
      result: list[str] = [eqp_id]
      seen = {eqp_id}
      attempts = 0
      while len(result) < n + 1 and attempts < 200:
          attempts += 1
          candidate = f"{prefix}{rng.randint(100, 999)}"
          if candidate not in seen:
              seen.add(candidate)
              result.append(candidate)
      return result


  __all__ = [
      "NOW",
      "seed_for",
      "fac_id_for",
      "eqp_ip_for",
      "sibling_eqp_ids",
  ]
  ```

- [ ] **3.3 Run the gate (GREEN).** Re-run 3.1; confirm it prints `OK [...]` with `ECXDX204` first.
- [ ] **3.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/providers/_siblings.py
  git commit -m "feat(hardware): add deterministic in-fab sibling + metadata helpers"
  ```

---

## Task 4 — providers/beam_shape_mock.py: faithful `type:"total"` docs

Faithful time-series of `type: "total"` beam_shape docs across `[start, end]`, several `beam_condition`s, every field from `docs/datatables/beam_shape.txt`, all per-degree arrays exactly length 16, fabricated off `metrics.BEAM_SHAPE_METRICS`. **Drop `type: index2`.** Keep source spellings.

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/providers/beam_shape_mock.py` (create)

**Interfaces:**
- Consumes: `metrics.BEAM_SHAPE_METRICS`, `metrics.PROFILE16_KEYS`; `_siblings.NOW`, `_siblings.seed_for`, `_siblings.fac_id_for`, `_siblings.eqp_ip_for`
- Produces: `build_beam_shape_docs(eqp_id: str, fab_name: str | None, start: datetime, end: datetime) -> list[dict]` — ascending-time list of faithful `total` docs

**Steps:**

- [ ] **4.1 Write the gate (RED).**

  ```bash
  python -c "from datetime import datetime; \
  from back_dev_home.ebeam.hitachi.hardware.providers.beam_shape_mock import build_beam_shape_docs as b; \
  docs = b('ECXDX204', 'M16B', datetime(2026,4,24), datetime(2026,5,24)); \
  assert len(docs) > 0; d = docs[0]; \
  assert d['type'] == 'total' and d['fdc_category'] == 'bsi_beam_shape'; \
  assert len(d['degree']) == 16 and len(d['Reso EB']) == 16 and len(d['Reso Detector']) == 16; \
  assert len(d['Apature angle factor']) == 16 and len(d['Reso EB Focus']) == 16; \
  assert 'Ellipicity' in d and 'Apature angle factor' in d; \
  assert d['eqp_id'] == 'ECXDX204' and d['fab_name'] == 'M16B' and d['fac_id'] == 'M16'; \
  assert all(set(['timestamp','timestamp_date','eqp_ip','fac_id']) <= set(x) for x in docs); \
  ts = [x['timestamp'] for x in docs]; assert ts == sorted(ts), 'not ascending'; \
  assert docs == b('ECXDX204', 'M16B', datetime(2026,4,24), datetime(2026,5,24)), 'not deterministic'; \
  print('OK', len(docs), sorted({x['beam_condition'] for x in docs}))"
  ```

- [ ] **4.2 Implement (GREEN).** Write the file:

  ```python
  """Phase 1 faithful beam_shape (`type: "total"`) mock for the hardware bsm panel.

  Produces the raw doc shape documented in `docs/datatables/beam_shape.txt`:
  per-degree length-16 arrays (Reso EB, Reso Detector, Noise, Focus offset,
  Apature angle factor, Reso EB Focus) keyed alongside a 16-step `degree` axis,
  plus the scalar summary fields and the metadata tail. Fabricated straight off
  `metrics.BEAM_SHAPE_METRICS`, so a new registry entry appears in every doc.

  This is SEPARATE from `bsm_mock.py` (kept for pm_planning's BM/PM gate). Here
  we emit the faithful raw docs the hardware page reads directly.

  Determinism mirrors the other providers: `random.Random` seeded from md5(eqp_id),
  anchored to `_siblings.NOW`. `index2` docs are intentionally not emitted.
  """

  from __future__ import annotations

  import random
  from datetime import datetime, timedelta

  from back_dev_home.ebeam.hitachi.hardware.metrics import (
      BEAM_SHAPE_METRICS,
      PROFILE16_KEYS,
  )
  from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
      eqp_ip_for,
      fac_id_for,
      seed_for,
  )


  __all__ = ["build_beam_shape_docs"]


  # 16 angular steps: 0.0, 22.5, ... 337.5
  DEGREES: list[float] = [round(i * 22.5, 1) for i in range(16)]

  # Beam conditions sampled per tool (mirrors the source `HR0800_IP0080` style).
  _BEAM_CONDITIONS: tuple[str, ...] = ("HR0800_IP0080", "HR0500_IP0080")

  # `category` values seen in the source ("I-diff_hp" etc.); one per beam_cond.
  _CATEGORY_BY_COND: dict[str, str] = {
      "HR0800_IP0080": "I-diff_hp",
      "HR0500_IP0080": "I-diff_lp",
  }

  # Scheduled monitoring runs at roughly these slots each day (matches bsm_mock).
  _DAILY_HOURS: tuple[int, ...] = (6, 14, 22)


  def _round_for(low: float, high: float, value: float) -> float:
      """Round to a sensible precision for the metric's magnitude."""
      span = abs(high)
      if span < 0.01:
          return round(value, 6)
      if span < 1.0:
          return round(value, 5)
      return round(value, 4)


  def _profile16(rng: random.Random, low: float, high: float) -> list[float]:
      """Length-16 per-degree array within [low, high] with organic wobble."""
      center = rng.uniform(low + (high - low) * 0.35, low + (high - low) * 0.65)
      wobble = (high - low) * 0.12
      out: list[float] = []
      for _ in DEGREES:
          v = min(high, max(low, center + rng.uniform(-wobble, wobble)))
          out.append(_round_for(low, high, v))
      return out


  def _scalar(rng: random.Random, low: float, high: float) -> float:
      return _round_for(low, high, rng.uniform(low, high))


  def _timestamps(rng: random.Random, start: datetime, end: datetime) -> list[datetime]:
      """3 measurements/day across [start, end], ascending."""
      moments: list[datetime] = []
      day = start.replace(hour=0, minute=0, second=0, microsecond=0)
      while day <= end:
          for hour in _DAILY_HOURS:
              moment = day.replace(hour=hour, minute=rng.choice([0, 15, 30, 45]))
              if start <= moment <= end:
                  moments.append(moment)
          day += timedelta(days=1)
      moments.sort()
      return moments


  def _build_doc(
      rng: random.Random,
      *,
      eqp_id: str,
      fab_name: str | None,
      eqp_ip: str,
      fac_id: str,
      moment: datetime,
      beam_condition: str,
  ) -> dict:
      doc: dict = {
          "category": _CATEGORY_BY_COND.get(beam_condition, "I-diff_hp"),
          "degree": list(DEGREES),
      }
      # Per-degree arrays + scalars straight off the registry.
      for metric in BEAM_SHAPE_METRICS:
          if metric["kind"] == "profile16":
              doc[metric["key"]] = _profile16(rng, metric["low"], metric["high"])
          else:
              doc[metric["key"]] = _scalar(rng, metric["low"], metric["high"])
      # `Reso EB Focus` is a per-degree array; `Reso EB Focus Range` a short list.
      doc["Reso EB Focus"] = _profile16(rng, 7.90, 9.00)
      doc["Reso EB Focus Range"] = [f"{rng.uniform(7.5, 8.5):.4f}"]
      # Faithful tail.
      doc["type"] = "total"
      doc["beam_condition"] = beam_condition
      doc["fdc_category"] = "bsi_beam_shape"
      doc["timestamp"] = moment.strftime("%Y-%m-%dT%H:%M:%S")
      doc["timestamp_date"] = moment.strftime("%Y-%m-%d")
      doc["eqp_ip"] = eqp_ip
      doc["eqp_id"] = eqp_id
      doc["fac_id"] = fac_id
      doc["fab_name"] = fab_name
      return doc


  def build_beam_shape_docs(
      eqp_id: str,
      fab_name: str | None,
      start: datetime,
      end: datetime,
  ) -> list[dict]:
      """Ascending-time faithful `total` beam_shape docs across [start, end].

      One doc per (timestamp, beam_condition). Deterministic per eqp_id.
      """
      rng = random.Random(seed_for(eqp_id))
      eqp_ip = eqp_ip_for(eqp_id)
      fac_id = fac_id_for(fab_name)
      docs: list[dict] = []
      for moment in _timestamps(rng, start, end):
          for beam_condition in _BEAM_CONDITIONS:
              docs.append(
                  _build_doc(
                      rng,
                      eqp_id=eqp_id,
                      fab_name=fab_name,
                      eqp_ip=eqp_ip,
                      fac_id=fac_id,
                      moment=moment,
                      beam_condition=beam_condition,
                  )
              )
      docs.sort(key=lambda d: (d["timestamp"], d["beam_condition"]))
      return docs
  ```

- [ ] **4.3 Run the gate (GREEN).** Re-run 4.1; confirm `OK <n> ['HR0500_IP0080', 'HR0800_IP0080']`. Sanity-check `_ = PROFILE16_KEYS` is referenced (import keeps it available for tooling); if the linter flags the unused import, remove `PROFILE16_KEYS` from the import line.
- [ ] **4.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/providers/beam_shape_mock.py
  git commit -m "feat(hardware): faithful beam_shape total-doc mock (beam_shape_mock.py)"
  ```

---

## Task 5 — providers/reso_center_mock.py: faithful `reso_center_log` docs

Faithful `category: "reso_center_log"` time-series per `docs/datatables/reso_center_data.txt`: scalars `CenterX`/`CenterY`/`BestReso`/`ResoIScenter`/`ResoDelta`; `Resolution_Range = ['-10','-5','0','5','10']`; `Resolution_Range_Raw`/`Resolution_Range_Smooth` = dict keyed by those 5 offsets, each → 5 numbers; `beam_condition`; `fdc_category == category`; metadata tail.

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/providers/reso_center_mock.py` (create)

**Interfaces:**
- Produces: `build_reso_center_docs(eqp_id: str, fab_name: str | None, start: datetime, end: datetime) -> list[dict]`

**Steps:**

- [ ] **5.1 Write the gate (RED).**

  ```bash
  python -c "from datetime import datetime; \
  from back_dev_home.ebeam.hitachi.hardware.providers.reso_center_mock import build_reso_center_docs as b; \
  docs = b('ECXDX204', 'M16B', datetime(2026,4,24), datetime(2026,5,24)); \
  assert len(docs) > 0; d = docs[0]; \
  assert d['category'] == 'reso_center_log' and d['fdc_category'] == 'reso_center_log'; \
  assert d['Resolution_Range'] == ['-10','-5','0','5','10']; \
  assert set(d['Resolution_Range_Raw']) == set(d['Resolution_Range']); \
  assert all(len(v) == 5 for v in d['Resolution_Range_Raw'].values()); \
  assert all(len(v) == 5 for v in d['Resolution_Range_Smooth'].values()); \
  assert all(k in d for k in ['CenterX','CenterY','BestReso','ResoIScenter','ResoDelta']); \
  assert d['eqp_id'] == 'ECXDX204' and d['fac_id'] == 'M16'; \
  ts = [x['timestamp'] for x in docs]; assert ts == sorted(ts); \
  assert docs == b('ECXDX204', 'M16B', datetime(2026,4,24), datetime(2026,5,24)); \
  print('OK', len(docs))"
  ```

- [ ] **5.2 Implement (GREEN).** Write the file:

  ```python
  """Phase 1 faithful reso_center (`category: "reso_center_log"`) mock.

  Raw doc shape from `docs/datatables/reso_center_data.txt`: center coordinates +
  resolution scalars, a 5-offset `Resolution_Range`, and `Raw`/`Smooth` focus
  sweeps (dict keyed by the 5 offsets, each -> 5 numbers), plus the metadata tail.
  Deterministic per eqp_id; ascending time.
  """

  from __future__ import annotations

  import random
  from datetime import datetime, timedelta

  from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
      eqp_ip_for,
      fac_id_for,
      seed_for,
  )


  __all__ = ["build_reso_center_docs"]


  _OFFSETS: list[str] = ["-10", "-5", "0", "5", "10"]
  _BEAM_CONDITIONS: tuple[str, ...] = ("HR0800_IP0080", "HR0500_IP0080")
  _DAILY_HOURS: tuple[int, ...] = (7, 19)


  def _timestamps(rng: random.Random, start: datetime, end: datetime) -> list[datetime]:
      moments: list[datetime] = []
      day = start.replace(hour=0, minute=0, second=0, microsecond=0)
      while day <= end:
          for hour in _DAILY_HOURS:
              moment = day.replace(hour=hour, minute=rng.choice([5, 25, 55]))
              if start <= moment <= end:
                  moments.append(moment)
          day += timedelta(days=1)
      moments.sort()
      return moments


  def _sweep(rng: random.Random, best: float) -> dict[str, list[float]]:
      """Per-offset 5-number resolution curve, minimised near offset 0."""
      out: dict[str, list[float]] = {}
      for off in _OFFSETS:
          penalty = abs(int(off)) * 0.012
          base = best + penalty
          out[off] = [round(base + rng.uniform(-0.02, 0.02), 4) for _ in range(5)]
      return out


  def _smooth(raw: dict[str, list[float]]) -> dict[str, list[float]]:
      """Lightly smoothed copy (3-pt moving mean per offset series)."""
      out: dict[str, list[float]] = {}
      for off, values in raw.items():
          sm: list[float] = []
          for i in range(len(values)):
              lo = max(0, i - 1)
              hi = min(len(values), i + 2)
              window = values[lo:hi]
              sm.append(round(sum(window) / len(window), 4))
          out[off] = sm
      return out


  def _build_doc(
      rng: random.Random,
      *,
      eqp_id: str,
      fab_name: str | None,
      eqp_ip: str,
      fac_id: str,
      moment: datetime,
      beam_condition: str,
  ) -> dict:
      best = round(rng.uniform(2.90, 3.10), 2)
      raw = _sweep(rng, best)
      doc: dict = {
          "category": "reso_center_log",
          "CenterX": round(rng.uniform(-1.5, 1.5), 2),
          "CenterY": round(rng.uniform(-1.5, 1.5), 2),
          "BestReso": best,
          "ResoIScenter": round(best + rng.uniform(-0.02, 0.02), 2),
          "ResoDelta": round(rng.uniform(0.02, 0.12), 2),
          "Resolution_Range": list(_OFFSETS),
          "Resolution_Range_Raw": raw,
          "Resolution_Range_Smooth": _smooth(raw),
          "beam_condition": beam_condition,
          "timestamp": moment.strftime("%Y-%m-%dT%H:%M:%S"),
          "timestamp_date": moment.strftime("%Y-%m-%d"),
          "eqp_id": eqp_id,
          "eqp_ip": eqp_ip,
          "fac_id": fac_id,
          "fab_name": fab_name,
          "fdc_category": "reso_center_log",
      }
      return doc


  def build_reso_center_docs(
      eqp_id: str,
      fab_name: str | None,
      start: datetime,
      end: datetime,
  ) -> list[dict]:
      rng = random.Random(seed_for(eqp_id) ^ 0x5253_4332)  # distinct stream from bsm
      eqp_ip = eqp_ip_for(eqp_id)
      fac_id = fac_id_for(fab_name)
      docs: list[dict] = []
      for moment in _timestamps(rng, start, end):
          for beam_condition in _BEAM_CONDITIONS:
              docs.append(
                  _build_doc(
                      rng,
                      eqp_id=eqp_id,
                      fab_name=fab_name,
                      eqp_ip=eqp_ip,
                      fac_id=fac_id,
                      moment=moment,
                      beam_condition=beam_condition,
                  )
              )
      docs.sort(key=lambda d: (d["timestamp"], d["beam_condition"]))
      return docs
  ```

- [ ] **5.3 Run the gate (GREEN).** Re-run 5.1; confirm `OK <n>`.
- [ ] **5.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/providers/reso_center_mock.py
  git commit -m "feat(hardware): faithful reso_center_log doc mock (reso_center_mock.py)"
  ```

---

## Task 6 — providers/fdc_mock.py: faithful FDC docs across 4 fdc_keys

Faithful `network_fdc_cdsem` docs per `docs/datatables/network_fdc_cdsem.txt`. **One doc = one `eqp_id` + one `timestamp` + one `values` list (one fdc_key)**. Fields: `eqp_id`, `eqp_model_cd`, `fab_name`, `eqp_ip`, `fdc_key`, `timestamp`, `values`. `values` always starts with the `fdc_key`. Structures:

- `TemperatureEchuck` → `[key, '0', position('1'|'2'|'3'), temp]`; 3 positions sampled periodically, each its own doc/timestamp clustered together.
- `SPMVoltages` → `[key, '0', A/B/C, '7', '1', '1', judgment('spline'|'quartic'), …~100 numbers]`.
- `LaserPower` → `[key, '0', x1, y1, x2, y2]` (two pairs, different scales).
- `ContactpinConductionInfo` → `[key, '0', A/B/C, n, judgment('Conduction'|'NotConduction'), …5 numbers]`.

`eqp_model_cd` should be a CD-SEM model (from `_tool_specs.TOOL_SPECS['cdsem']['eqp_models']`).

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/providers/fdc_mock.py` (create)

**Interfaces:**
- Consumes: `_siblings.seed_for/eqp_ip_for`; `_tool_specs.TOOL_SPECS`
- Produces: `build_fdc_docs(eqp_id: str, fab_name: str | None, start: datetime, end: datetime) -> list[dict]`

**Steps:**

- [ ] **6.1 Write the gate (RED).**

  ```bash
  python -c "from datetime import datetime; \
  from back_dev_home.ebeam.hitachi.hardware.providers.fdc_mock import build_fdc_docs as b; \
  docs = b('ECXDX204', 'M16B', datetime(2026,5,17), datetime(2026,5,24)); \
  keys = {d['fdc_key'] for d in docs}; \
  assert keys == {'TemperatureEchuck','SPMVoltages','LaserPower','ContactpinConductionInfo'}, keys; \
  assert all(d['values'][0] == d['fdc_key'] for d in docs); \
  assert all(set(['eqp_id','eqp_model_cd','fab_name','eqp_ip','fdc_key','timestamp','values']) <= set(d) for d in docs); \
  temp = [d for d in docs if d['fdc_key']=='TemperatureEchuck']; \
  assert all(d['values'][1]=='0' and d['values'][2] in ('1','2','3') and len(d['values'])==4 for d in temp); \
  laser = [d for d in docs if d['fdc_key']=='LaserPower']; \
  assert all(len(d['values'])==6 for d in laser); \
  spm = [d for d in docs if d['fdc_key']=='SPMVoltages']; \
  assert all(d['values'][2] in ('A','B','C') and d['values'][6] in ('spline','quartic') and len(d['values'])>=100 for d in spm); \
  cp = [d for d in docs if d['fdc_key']=='ContactpinConductionInfo']; \
  assert all(d['values'][2] in ('A','B','C') and d['values'][4] in ('Conduction','NotConduction') for d in cp); \
  ts=[d['timestamp'] for d in docs]; assert ts==sorted(ts); \
  assert docs == b('ECXDX204','M16B',datetime(2026,5,17),datetime(2026,5,24)); \
  print('OK', len(docs), sorted(keys))"
  ```

- [ ] **6.2 Implement (GREEN).** Write the file:

  ```python
  """Phase 1 faithful network_fdc_cdsem mock.

  Raw doc shape from `docs/datatables/network_fdc_cdsem.txt`. One doc = one
  (eqp_id, timestamp, values) where `values` begins with the `fdc_key` and then
  follows that key's own layout:

    TemperatureEchuck        [key, '0', pos('1'|'2'|'3'), temp]
    SPMVoltages              [key, '0', A/B/C, '7','1','1', judgment, ~100 nums]
    LaserPower               [key, '0', x1, y1, x2, y2]   (two differing scales)
    ContactpinConductionInfo [key, '0', A/B/C, n, judgment, 5 nums]

  Deterministic per eqp_id; docs ascending by timestamp.
  """

  from __future__ import annotations

  import random
  from datetime import datetime, timedelta

  from back_dev_home.ebeam.hitachi._tool_specs import TOOL_SPECS
  from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
      eqp_ip_for,
      seed_for,
  )


  __all__ = ["build_fdc_docs"]


  _ABC: tuple[str, ...] = ("A", "B", "C")
  _CDSEM_MODELS: list[str] = TOOL_SPECS["cdsem"]["eqp_models"]


  def _model_for(rng: random.Random) -> str:
      return rng.choice(_CDSEM_MODELS)


  def _fmt(moment: datetime) -> str:
      return moment.strftime("%Y-%m-%dT%H:%M:%S")


  def _base(eqp_id: str, eqp_model_cd: str, fab_name: str | None, eqp_ip: str) -> dict:
      return {
          "eqp_id": eqp_id,
          "eqp_model_cd": eqp_model_cd,
          "fab_name": fab_name,
          "eqp_ip": eqp_ip,
      }


  def _temperature_docs(
      rng: random.Random, base: dict, start: datetime, end: datetime
  ) -> list[dict]:
      """3-position temperature, sampled every few hours; positions clustered."""
      out: list[dict] = []
      cursor = start
      while cursor <= end:
          for pos in ("1", "2", "3"):
              moment = cursor + timedelta(minutes=int(pos) * rng.choice([1, 2, 3]))
              if moment > end:
                  continue
              temp = round(rng.uniform(23.20, 23.60), 5)
              out.append(
                  {
                      **base,
                      "fdc_key": "TemperatureEchuck",
                      "timestamp": _fmt(moment),
                      "values": ["TemperatureEchuck", "0", pos, f"{temp}"],
                  }
              )
          cursor += timedelta(hours=rng.choice([4, 6, 8]))
      return out


  def _spm_docs(
      rng: random.Random, base: dict, start: datetime, end: datetime
  ) -> list[dict]:
      """~100-point profile per A/B/C, judgment spline|quartic; sparse cadence."""
      out: list[dict] = []
      cursor = start + timedelta(hours=rng.randint(2, 12))
      while cursor <= end:
          for abc in _ABC:
              moment = cursor + timedelta(minutes=_ABC.index(abc) * 2)
              if moment > end:
                  continue
              judgment = rng.choice(["spline", "quartic"])
              nums = [f"{rng.uniform(-1.5, 0.5):.4f}" for _ in range(100)]
              values = ["SPMVoltages", "0", abc, "7", "1", "1", judgment, *nums]
              out.append(
                  {
                      **base,
                      "fdc_key": "SPMVoltages",
                      "timestamp": _fmt(moment),
                      "values": values,
                  }
              )
          cursor += timedelta(days=rng.choice([1, 2, 3]))
      return out


  def _laser_docs(
      rng: random.Random, base: dict, start: datetime, end: datetime
  ) -> list[dict]:
      """Two (x, y) pairs of different scale; sampled a few times/day."""
      out: list[dict] = []
      cursor = start
      while cursor <= end:
          moment = cursor.replace(hour=rng.choice([8, 16]), minute=rng.choice([0, 30]))
          if start <= moment <= end:
              x1 = f"{rng.uniform(0.70, 0.85):.2f}"
              y1 = f"{rng.uniform(0.68, 0.80):.2f}"
              x2 = f"{rng.randint(300_000_000, 360_000_000)}"
              y2 = f"{rng.randint(40_000_000, 50_000_000)}"
              out.append(
                  {
                      **base,
                      "fdc_key": "LaserPower",
                      "timestamp": _fmt(moment),
                      "values": ["LaserPower", "0", x1, y1, x2, y2],
                  }
              )
          cursor += timedelta(days=1)
      return out


  def _contactpin_docs(
      rng: random.Random, base: dict, start: datetime, end: datetime
  ) -> list[dict]:
      """A/B/C conduction status + 5 numbers; clustered in time, weekly cadence."""
      out: list[dict] = []
      cursor = start + timedelta(hours=rng.randint(1, 20))
      while cursor <= end:
          for abc in _ABC:
              moment = cursor + timedelta(minutes=_ABC.index(abc) * 3)
              if moment > end:
                  continue
              judgment = "Conduction" if rng.random() < 0.7 else "NotConduction"
              n = str(rng.randint(2, 6))
              nums = [
                  f"{rng.uniform(-25.0, 25.0):.1f}",
                  f"{rng.uniform(-5.0, 5.0):.1f}",
                  f"{rng.uniform(0.0, 25.0):.1f}",
                  f"{rng.uniform(0.0, 25.0):.1f}",
                  f"{rng.randint(100000, 200000)}",
              ]
              values = ["ContactpinConductionInfo", "0", abc, n, judgment, *nums]
              out.append(
                  {
                      **base,
                      "fdc_key": "ContactpinConductionInfo",
                      "timestamp": _fmt(moment),
                      "values": values,
                  }
              )
          cursor += timedelta(days=rng.choice([5, 7, 9]))
      return out


  def build_fdc_docs(
      eqp_id: str,
      fab_name: str | None,
      start: datetime,
      end: datetime,
  ) -> list[dict]:
      rng = random.Random(seed_for(eqp_id) ^ 0x4644_4332)  # distinct stream
      base = _base(eqp_id, _model_for(rng), fab_name, eqp_ip_for(eqp_id))
      docs: list[dict] = []
      docs += _temperature_docs(rng, base, start, end)
      docs += _spm_docs(rng, base, start, end)
      docs += _laser_docs(rng, base, start, end)
      docs += _contactpin_docs(rng, base, start, end)
      docs.sort(key=lambda d: (d["timestamp"], d["fdc_key"], str(d["values"][2:3])))
      return docs
  ```

- [ ] **6.3 Run the gate (GREEN).** Re-run 6.1; confirm it prints `OK <n> ['ContactpinConductionInfo', 'LaserPower', 'SPMVoltages', 'TemperatureEchuck']`.
- [ ] **6.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/providers/fdc_mock.py
  git commit -m "feat(hardware): faithful network_fdc_cdsem doc mock (fdc_mock.py)"
  ```

---

## Task 7 — providers/mdc_mock.py: dict-of-dict, eqp + siblings, as-of

Faithful `mdc_setting` per `docs/datatables/mdc_setting.txt`: `{ eqp_id: { beam_condition: value } }` for the requested eqp + in-fab siblings, as-of `end`. Beam conditions vary per eqp (`800V_HR_0Deg`, `500V_HR_90Deg`; some tools add `3000V` / `Valley`). Values are correction-factor strings near 1.00 (`result = MDC × raw`). The `as_of` date selects which snapshot; mock keeps it simple — the as-of date perturbs the seed so different `end`s give slightly different values, but the set of tools/conditions stays stable.

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/providers/mdc_mock.py` (create)

**Interfaces:**
- Consumes: `_siblings.sibling_eqp_ids/seed_for`
- Produces: `build_mdc_settings(eqp_id: str, fab_name: str | None, as_of: datetime) -> dict[str, dict[str, str]]`

**Steps:**

- [ ] **7.1 Write the gate (RED).**

  ```bash
  python -c "from datetime import datetime; \
  from back_dev_home.ebeam.hitachi.hardware.providers.mdc_mock import build_mdc_settings as b; \
  s = b('ECXDX204', 'M16B', datetime(2026,5,24)); \
  assert 'ECXDX204' in s; assert 4 <= len(s) <= 6, len(s); \
  for eqp, conds in s.items(): \
      assert '800V_HR_0Deg' in conds; \
      assert all(0.99 <= float(v) <= 1.01 for v in conds.values()), conds; \
  assert s == b('ECXDX204','M16B',datetime(2026,5,24)); \
  print('OK', list(s)[0], len(s), list(s['ECXDX204']))"
  ```

- [ ] **7.2 Implement (GREEN).** Write the file:

  ```python
  """Phase 1 faithful mdc_setting mock (fleet dict-of-dict, as-of snapshot).

  Shape from `docs/datatables/mdc_setting.txt`: `{eqp_id: {beam_condition: value}}`
  for the requested eqp + in-fab siblings. Values are correction-factor strings
  near 1.0 (`result = MDC * raw`). Some tools carry extra conditions (3000V,
  Valley). `as_of` perturbs values (snapshot-by-date) while the tool/condition
  set stays stable per (eqp_id, fab_name).
  """

  from __future__ import annotations

  import random

  from datetime import datetime

  from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
      seed_for,
      sibling_eqp_ids,
  )


  __all__ = ["build_mdc_settings"]


  _BASE_CONDITIONS: tuple[str, ...] = (
      "800V_HR_0Deg",
      "800V_HR_90Deg",
      "500V_HR_0Deg",
      "500V_HR_90Deg",
  )
  _EXTRA_CONDITIONS: tuple[str, ...] = ("3000V_HR_0Deg", "Valley")


  def _conditions_for(rng: random.Random) -> list[str]:
      conds = list(_BASE_CONDITIONS)
      # Some tools carry extra modes.
      if rng.random() < 0.4:
          conds.append(_EXTRA_CONDITIONS[0])
      if rng.random() < 0.25:
          conds.append(_EXTRA_CONDITIONS[1])
      return conds


  def _value(rng: random.Random) -> str:
      return f"{rng.uniform(0.995, 1.006):.6f}"


  def build_mdc_settings(
      eqp_id: str,
      fab_name: str | None,
      as_of: datetime,
  ) -> dict[str, dict[str, str]]:
      eqp_ids = sibling_eqp_ids(eqp_id, fab_name)
      # The as-of date shifts the snapshot deterministically.
      as_of_salt = int(as_of.strftime("%Y%m%d"))
      out: dict[str, dict[str, str]] = {}
      for tool in eqp_ids:
          rng = random.Random(seed_for(tool) ^ 0x4D44_4332 ^ as_of_salt)
          conds = _conditions_for(rng)
          out[tool] = {cond: _value(rng) for cond in conds}
      return out
  ```

- [ ] **7.3 Run the gate (GREEN).** Re-run 7.1; confirm `OK ECXDX204 <n> [...]`.
- [ ] **7.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/providers/mdc_mock.py
  git commit -m "feat(hardware): faithful mdc_setting fleet mock (mdc_mock.py)"
  ```

---

## Task 8 — providers/sce_mock.py: dict-of-dict, Coefficients[360], as-of

Faithful `sce_setting` per `docs/datatables/sce_setting.txt`: `{ eqp_id: { FileInfo, SemCond, ImgCond, SCEParam, Coefficients } }` for eqp + in-fab siblings, as-of `end`. `SemCond` = `{SemCond_No, SemCond_Optics, SemCond_Vacc, SemCond_Ip, SemCond_IpMode, SemCond_Detector}`; `ImgCond` = `{ImgCond_FocusOffset[], ImgCond_Mag[], ImgCond_Pixel[]}`; `SCEParam` = 7 threshold strings; `Coefficients` = list of `{index, values:[2 floats]}` for indices 0…359.

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/providers/sce_mock.py` (create)

**Interfaces:**
- Consumes: `_siblings.sibling_eqp_ids/seed_for`
- Produces: `build_sce_settings(eqp_id: str, fab_name: str | None, as_of: datetime) -> dict[str, dict]`

**Steps:**

- [ ] **8.1 Write the gate (RED).**

  ```bash
  python -c "from datetime import datetime; \
  from back_dev_home.ebeam.hitachi.hardware.providers.sce_mock import build_sce_settings as b; \
  s = b('ECXDX204', 'M16B', datetime(2026,5,24)); \
  assert 'ECXDX204' in s and 4 <= len(s) <= 6; e = s['ECXDX204']; \
  assert set(e) == {'FileInfo','SemCond','ImgCond','SCEParam','Coefficients'}, set(e); \
  assert set(e['SemCond']) == {'SemCond_No','SemCond_Optics','SemCond_Vacc','SemCond_Ip','SemCond_IpMode','SemCond_Detector'}; \
  assert set(e['ImgCond']) == {'ImgCond_FocusOffset','ImgCond_Mag','ImgCond_Pixel'}; \
  assert len(e['SCEParam']) == 7; \
  assert len(e['Coefficients']) == 360; \
  assert e['Coefficients'][0]['index'] == 0 and e['Coefficients'][359]['index'] == 359; \
  assert all(len(c['values']) == 2 for c in e['Coefficients']); \
  assert s == b('ECXDX204','M16B',datetime(2026,5,24)); \
  print('OK', len(s), len(e['Coefficients']))"
  ```

- [ ] **8.2 Implement (GREEN).** Write the file:

  ```python
  """Phase 1 faithful sce_setting mock (fleet dict-of-dict, as-of snapshot).

  Shape from `docs/datatables/sce_setting.txt`: per eqp a FileInfo/SemCond/
  ImgCond/SCEParam block plus a 360-entry Coefficients curve (`{index, values:
  [2 floats]}`, indices 0..359). Returned for the requested eqp + in-fab
  siblings. SCE is an M-fab production feature (R3/R4 don't use it); we emit for
  any CD-SEM eqp in the mock and let `normalizers.settings_payload` note usage.
  """

  from __future__ import annotations

  import random
  from datetime import datetime

  from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
      seed_for,
      sibling_eqp_ids,
  )


  __all__ = ["build_sce_settings"]


  def _file_info(rng: random.Random, eqp_id: str) -> dict[str, str]:
      day = rng.randint(1, 28)
      return {
          "FileName": f"SCE_{eqp_id}_2026{rng.randint(1, 5):02d}{day:02d}.dat",
          "Updated": f"2026-{rng.randint(1, 5):02d}-{day:02d}",
      }


  def _sem_cond(rng: random.Random) -> dict[str, str]:
      return {
          "SemCond_No": str(rng.randint(1, 8)),
          "SemCond_Optics": rng.choice(["High Reso.", "Standard"]),
          "SemCond_Vacc": rng.choice(["500", "800"]),
          "SemCond_Ip": f"{rng.uniform(6.0, 9.0):.4f}",
          "SemCond_IpMode": rng.choice(["Low", "Middle", "High"]),
          "SemCond_Detector": rng.choice(["SE+EF", "SE", "EF"]),
      }


  def _img_cond(rng: random.Random) -> dict[str, list[str]]:
      mag = str(rng.randint(150_000_000, 150_009_999))
      return {
          "ImgCond_FocusOffset": [str(rng.randint(-3, 1))],
          "ImgCond_Mag": [mag, mag],
          "ImgCond_Pixel": ["1024", "1024"],
      }


  def _sce_param(rng: random.Random) -> dict[str, str]:
      return {
          "SCEParam_CycleUpperTh": f"{rng.uniform(5.0, 7.0):.3f}",
          "SCEParam_CycleLowerTh": f"{rng.uniform(20.0, 24.0):.6f}",
          "SCEParam_SmoothRadius": str(rng.randint(5, 9)),
          "SCEParam_SmoothTheta": str(rng.randint(5, 9)),
          "SCEParam_FitRangeSt": str(rng.randint(35, 45)),
          "SCEParam_FitRangeEd": str(rng.randint(75, 85)),
          "SCEParam_CorrCoefLimit": f"{rng.uniform(0.1, 0.3):.5f}",
      }


  def _coefficients(rng: random.Random) -> list[dict]:
      out: list[dict] = []
      for index in range(360):
          v0 = round(rng.uniform(-0.02, 0.02), 6)
          v1 = round(rng.uniform(0.90, 1.00), 6)
          out.append({"index": index, "values": [v0, v1]})
      return out


  def build_sce_settings(
      eqp_id: str,
      fab_name: str | None,
      as_of: datetime,
  ) -> dict[str, dict]:
      eqp_ids = sibling_eqp_ids(eqp_id, fab_name)
      as_of_salt = int(as_of.strftime("%Y%m%d"))
      out: dict[str, dict] = {}
      for tool in eqp_ids:
          rng = random.Random(seed_for(tool) ^ 0x5343_4532 ^ as_of_salt)
          out[tool] = {
              "FileInfo": _file_info(rng, tool),
              "SemCond": _sem_cond(rng),
              "ImgCond": _img_cond(rng),
              "SCEParam": _sce_param(rng),
              "Coefficients": _coefficients(rng),
          }
      return out
  ```

- [ ] **8.3 Run the gate (GREEN).** Re-run 8.1; confirm `OK <n> 360`.
- [ ] **8.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/providers/sce_mock.py
  git commit -m "feat(hardware): faithful sce_setting fleet mock (sce_mock.py)"
  ```

---

## Task 9 — normalizers.py: docs_payload() + settings_payload(); drop bsm_payload; fab_name

Replace `bsm_payload` with two generic wrappers and rename `fab_id`→`fab_name` throughout. `docs_payload` wraps a time-series doc list (bsm/reso-center/fdc) with thin summary cards (doc count + latest timestamp). `settings_payload` wraps a dict-of-dict (mdc/sce) with thin cards (as-of date + sibling count).

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/normalizers.py` (modify)

**Interfaces:**
- Produces: `now_iso() -> str` (unchanged)
- Produces: `unavailable_payload(service, tool_slug, eqp_id, fab_name, summary) -> HardwarePayload`
- Produces: `bm_pm_payload(...)`, `bm_pm_history_payload(...)`, `normalize_office_rows(...)` — all with `fab_id`→`fab_name`
- Produces: `docs_payload(service, tool_slug, eqp_id, fab_name, *, docs, summary, extra_cards=None) -> HardwarePayload`
- Produces: `settings_payload(service, tool_slug, eqp_id, fab_name, *, settings, as_of, summary, tables=None) -> HardwarePayload`
- Removes: `bsm_payload`; the `BsmBlock` import

**Steps:**

- [ ] **9.1 Write the gate (RED).**

  ```bash
  python -c "from back_dev_home.ebeam.hitachi.hardware import normalizers as n; \
  assert not hasattr(n, 'bsm_payload'); \
  p = n.docs_payload('bsm','cdsem','ECXDX204','M16B', docs=[{'timestamp':'2026-05-01T06:00:00'}], summary='x'); \
  assert p['docs'] and p['fab_name']=='M16B' and 'fab_id' not in p; \
  assert any(c['key']=='doc_count' for c in p['cards']); \
  from datetime import datetime; \
  q = n.settings_payload('mdc','cdsem','ECXDX204','M16B', settings={'ECXDX204':{}}, as_of=datetime(2026,5,24), summary='y'); \
  assert q['settings'] and any(c['key']=='as_of' for c in q['cards']); \
  print('OK')"
  ```

- [ ] **9.2 Implement (GREEN).** Edit `normalizers.py`:
  - Change the import block to drop `BsmBlock`:

    ```python
    from back_dev_home.ebeam.hitachi.hardware.contracts import (
        HardwareMetricCard,
        HardwarePayload,
        HardwareTableSection,
        RecordValue,
        ServiceKey,
    )
    ```

  - In **every** function (`unavailable_payload`, `bm_pm_payload`, `bm_pm_history_payload`, `normalize_office_rows`), rename the `fab_id` parameter to `fab_name` and the emitted `"fab_id": fab_id` payload key to `"fab_name": fab_name`. (Mechanical rename — there are 4 such functions, each with one parameter and one payload key.)
  - **Delete** the entire `bsm_payload(...)` function.
  - **Append** the two new builders:

    ```python
    def docs_payload(
        service: ServiceKey,
        tool_slug: str,
        eqp_id: str | None,
        fab_name: str | None,
        *,
        docs: list[dict],
        summary: str,
        extra_cards: list[HardwareMetricCard] | None = None,
    ) -> HardwarePayload:
        """Wrap a faithful time-series doc list (bsm / reso-center / fdc).

        Thin summary cards only: doc count + latest timestamp. The page reads
        chart axes straight off `docs` (data-driven selectors).
        """
        latest = docs[-1].get("timestamp", "—") if docs else "—"
        cards: list[HardwareMetricCard] = [
            {"key": "doc_count", "label": "문서 수", "value": len(docs), "unit": "건", "tone": "neutral"},
            {"key": "latest_ts", "label": "최신 측정", "value": latest, "tone": "neutral"},
        ]
        if extra_cards:
            cards.extend(extra_cards)
        return {
            "tool_slug": tool_slug,
            "service": service,
            "eqp_id": eqp_id,
            "fab_name": fab_name,
            "available": True,
            "fetched_at": now_iso(),
            "summary": summary,
            "cards": cards,
            "tables": [],
            "docs": docs,
        }


    def settings_payload(
        service: ServiceKey,
        tool_slug: str,
        eqp_id: str | None,
        fab_name: str | None,
        *,
        settings: dict[str, dict],
        as_of: str,
        summary: str,
        tables: list[HardwareTableSection] | None = None,
    ) -> HardwarePayload:
        """Wrap a faithful dict-of-dict (mdc / sce): eqp + in-fab siblings.

        Thin cards: as-of date + sibling count. `tables` optional (e.g. the mdc
        matrix or sce settings-compare are built frontend-side off `settings`).
        """
        sibling_count = max(0, len(settings) - 1)
        cards: list[HardwareMetricCard] = [
            {"key": "as_of", "label": "기준일", "value": as_of, "tone": "neutral"},
            {"key": "sibling_count", "label": "동일 fab 장비", "value": sibling_count, "unit": "대", "tone": "neutral"},
        ]
        return {
            "tool_slug": tool_slug,
            "service": service,
            "eqp_id": eqp_id,
            "fab_name": fab_name,
            "available": True,
            "fetched_at": now_iso(),
            "summary": summary,
            "cards": cards,
            "tables": tables or [],
            "settings": settings,
        }
    ```

  - Note: `settings_payload` takes `as_of: str` (caller formats the as-of date); the 9.1 gate passes a `datetime` only to exercise the wrapper — adjust the gate to pass `as_of='2026-05-24'` if you prefer a string, OR accept `datetime` and `str()` it inside. Keep the signature `as_of: str` and pass a string from the caller (Task 11). Update the gate's `as_of=` to a string accordingly.
- [ ] **9.3 Run the gate (GREEN).** Adjust the 9.1 one-liner so `settings_payload(..., as_of='2026-05-24', ...)` passes a string, then run; confirm `OK`.
- [ ] **9.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/normalizers.py
  git commit -m "refactor(hardware): docs_payload/settings_payload; drop bsm_payload; fab_name"
  ```

---

## Task 10 — providers/mock.py + office.py: dispatch all 6 services

Wire the mock dispatch to call the right generator per service and pass `start`/`end`/`fab_name`; update office stubs to `fab_name` and return `unavailable` for the new services. Because `data.py`/`mock.py`/`office.py` signatures gain `start`/`end`, this task changes those signatures; `routes.py` (Task 11) supplies them.

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/providers/mock.py` (modify)
- `back_dev_home/ebeam/hitachi/hardware/providers/office.py` (modify)
- `back_dev_home/ebeam/hitachi/hardware/data.py` (modify)

**Interfaces:**
- Produces: `mock.get_hardware_service(tool_slug, service, eqp_id, fab_name, start: datetime, end: datetime) -> HardwarePayload`
- Produces: `office.get_hardware_service(tool_slug, service, eqp_id, fab_name, start, end) -> HardwarePayload`
- Produces: `data.get_hardware_service(tool_slug, service, eqp_id, fab_name, start, end) -> HardwarePayload`
- Consumes: all five `build_*` generators; `normalizers.docs_payload/settings_payload/bm_pm_history_payload/unavailable_payload/now_iso`

**Steps:**

- [ ] **10.1 Write the gate (RED).**

  ```bash
  python -c "from datetime import datetime; \
  from back_dev_home.ebeam.hitachi.hardware.providers import mock; \
  s, e = datetime(2026,4,24), datetime(2026,5,24); \
  for svc in ['bsm','reso-center','fdc']: \
      p = mock.get_hardware_service('cdsem', svc, 'ECXDX204', 'M16B', s, e); \
      assert p['available'] and p['docs'], svc; \
  for svc in ['mdc','sce']: \
      p = mock.get_hardware_service('cdsem', svc, 'ECXDX204', 'M16B', s, e); \
      assert p['available'] and p['settings'] and 'ECXDX204' in p['settings'], svc; \
  bp = mock.get_hardware_service('cdsem','bm-pm','ECXDX204','M16B', s, e); \
  assert bp['available']; \
  hv = mock.get_hardware_service('hvsem','bsm','MCD204','M16B', s, e); \
  assert hv['available'] is False, 'bsm must be cdsem-only'; \
  print('OK')"
  ```

- [ ] **10.2 Implement `data.py` (swap surface).** Replace the body so the signature threads `start`/`end` and uses `fab_name`:

  ```python
  """SWAP SURFACE - hardware-page provider selection.

  Routes import only this module. Phase-specific source wiring belongs in
  `providers/mock.py` or `providers/office.py`, then both paths normalize to the
  canonical contract in `contracts.py`.
  """

  import os
  from datetime import datetime
  from typing import Literal

  from back_dev_home._runtime.env import is_cloud
  from back_dev_home.ebeam.hitachi.hardware.contracts import (
      HardwarePayload,
      ServiceKey,
      VALID_SERVICES,
  )
  from back_dev_home.ebeam.hitachi.hardware.providers import mock, office


  ProviderKey = Literal["mock", "office"]


  def _provider_key() -> ProviderKey:
      raw = os.environ.get("SKEWNONO_HARDWARE_PROVIDER", "").strip().lower()
      if raw in {"mock", "office"}:
          return raw  # type: ignore[return-value]
      return "office" if is_cloud() else "mock"


  def get_hardware_service(
      tool_slug: str,
      service: ServiceKey,
      eqp_id: str | None,
      fab_name: str | None,
      start: datetime,
      end: datetime,
  ) -> HardwarePayload:
      provider = office if _provider_key() == "office" else mock
      return provider.get_hardware_service(
          tool_slug, service, eqp_id, fab_name, start, end
      )
  ```

  (Keep the `VALID_SERVICES` re-export import even though unused here — `routes.py` imports it from `data`.)
- [ ] **10.3 Implement `mock.py`.** Replace the file:

  ```python
  """Phase 1 hardware mock provider — dispatch all six services."""

  from datetime import datetime

  from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload, ServiceKey
  from back_dev_home.ebeam.hitachi.hardware.normalizers import (
      bm_pm_history_payload,
      docs_payload,
      now_iso,
      settings_payload,
      unavailable_payload,
  )
  from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm_mock import build_bm_pm_data
  from back_dev_home.ebeam.hitachi.hardware.providers.beam_shape_mock import build_beam_shape_docs
  from back_dev_home.ebeam.hitachi.hardware.providers.fdc_mock import build_fdc_docs
  from back_dev_home.ebeam.hitachi.hardware.providers.mdc_mock import build_mdc_settings
  from back_dev_home.ebeam.hitachi.hardware.providers.reso_center_mock import build_reso_center_docs
  from back_dev_home.ebeam.hitachi.hardware.providers.sce_mock import build_sce_settings


  # bsm / reso-center / sce are CD-SEM-only checks.
  _CDSEM_ONLY: frozenset[str] = frozenset({"bsm", "reso-center", "sce"})

  _CDSEM_ONLY_MSG: dict[str, str] = {
      "bsm": "BSM는 CD-SEM 장비에서만 제공됩니다.",
      "reso-center": "Reso Center는 CD-SEM 장비에서만 제공됩니다.",
      "sce": "SCE는 CD-SEM 장비에서만 제공됩니다.",
  }

  _EMPTY_HINT: dict[str, str] = {
      "bsm": "장비를 선택하면 BSM 추세와 360° 빔 형상을 확인할 수 있습니다.",
      "reso-center": "장비를 선택하면 Reso Center 추세를 확인할 수 있습니다.",
      "fdc": "장비를 선택하면 FDC 신호/판정 추세를 확인할 수 있습니다.",
      "mdc": "장비를 선택하면 MDC 보정 계수와 동일 fab skew를 확인할 수 있습니다.",
      "sce": "장비를 선택하면 SCE 설정과 계수 곡선을 확인할 수 있습니다.",
      "bm-pm": "장비를 선택하면 BM/PM 작업 이력과 예정 작업을 확인할 수 있습니다.",
  }


  def _empty_available(
      tool_slug: str, service: ServiceKey, fab_name: str | None
  ) -> HardwarePayload:
      return {
          "tool_slug": tool_slug,
          "service": service,
          "eqp_id": None,
          "fab_name": fab_name,
          "available": True,
          "fetched_at": now_iso(),
          "summary": _EMPTY_HINT[service],
          "cards": [],
          "tables": [],
      }


  def get_hardware_service(
      tool_slug: str,
      service: ServiceKey,
      eqp_id: str | None,
      fab_name: str | None,
      start: datetime,
      end: datetime,
  ) -> HardwarePayload:
      # CD-SEM-only services are unavailable for hvsem.
      if service in _CDSEM_ONLY and tool_slug != "cdsem":
          return unavailable_payload(
              service, tool_slug, eqp_id, fab_name, _CDSEM_ONLY_MSG[service]
          )

      if eqp_id is None:
          # No tool picked yet — available-but-empty so the page shows a hint.
          return _empty_available(tool_slug, service, fab_name)

      if service == "bm-pm":
          data = build_bm_pm_data(eqp_id)
          return bm_pm_history_payload(
              tool_slug,
              eqp_id,
              fab_name,
              past_rows=data["past"],
              future_rows=data["future"],
              cards=data["cards"],
          )

      if service == "bsm":
          docs = build_beam_shape_docs(eqp_id, fab_name, start, end)
          return docs_payload(
              service, tool_slug, eqp_id, fab_name,
              docs=docs,
              summary="beam_shape(type:total) 원시 문서를 시간순으로 제공합니다. "
                      "filter/축을 선택해 추세와 360° 빔 형상을 확인하세요.",
          )

      if service == "reso-center":
          docs = build_reso_center_docs(eqp_id, fab_name, start, end)
          return docs_payload(
              service, tool_slug, eqp_id, fab_name,
              docs=docs,
              summary="reso_center_log 원시 문서를 시간순으로 제공합니다.",
          )

      if service == "fdc":
          docs = build_fdc_docs(eqp_id, fab_name, start, end)
          return docs_payload(
              service, tool_slug, eqp_id, fab_name,
              docs=docs,
              summary="network_fdc_cdsem 원시 문서(fdc_key별)를 시간순으로 제공합니다.",
          )

      if service == "mdc":
          settings = build_mdc_settings(eqp_id, fab_name, end)
          return settings_payload(
              service, tool_slug, eqp_id, fab_name,
              settings=settings,
              as_of=end.strftime("%Y-%m-%d"),
              summary="선택 장비와 동일 fab 장비의 MDC 보정 계수 스냅샷(as-of)을 제공합니다.",
          )

      # service == "sce"
      settings = build_sce_settings(eqp_id, fab_name, end)
      return settings_payload(
          service, tool_slug, eqp_id, fab_name,
          settings=settings,
          as_of=end.strftime("%Y-%m-%d"),
          summary="선택 장비와 동일 fab 장비의 SCE 설정/계수 스냅샷(as-of)을 제공합니다. "
                  "SCE는 양산(M-fab)에서 활용됩니다.",
      )
  ```

- [ ] **10.4 Implement `office.py`.** Replace the file so signatures match and new services return unavailable:

  ```python
  """Office hardware provider.

  Wire OpenSearch, Redis, files, or internal APIs here. Keep source-specific keys
  inside this module and `normalizers.py`; the route must keep returning the
  canonical hardware contract. New raw-doc services (bsm/reso-center/fdc/mdc/sce)
  are stubbed unavailable until office data is wired.
  """

  from datetime import datetime

  from back_dev_home.ebeam.hitachi.hardware.contracts import (
      HardwarePayload,
      ServiceKey,
  )
  from back_dev_home.ebeam.hitachi.hardware.normalizers import (
      bm_pm_payload,
      unavailable_payload,
  )


  _OFFICE_PENDING: dict[str, str] = {
      "bsm": "BSM beam_shape office wiring is pending.",
      "reso-center": "Reso Center office wiring is pending.",
      "fdc": "FDC office wiring is pending.",
      "mdc": "MDC office wiring is pending.",
      "sce": "SCE office wiring is pending.",
  }


  def get_hardware_service(
      tool_slug: str,
      service: ServiceKey,
      eqp_id: str | None,
      fab_name: str | None,
      start: datetime,
      end: datetime,
  ) -> HardwarePayload:
      _ = (start, end)
      if service == "bm-pm":
          return bm_pm_payload(
              tool_slug,
              eqp_id,
              fab_name,
              last_bm_date="",
              next_pm_date="",
              pm_window_hours=0,
              open_work_orders=0,
          )
      return unavailable_payload(
          service, tool_slug, eqp_id, fab_name,
          _OFFICE_PENDING.get(service, f"{service} office wiring is pending."),
      )
  ```

- [ ] **10.5 Run the gate (GREEN).** Re-run 10.1; confirm `OK`. Also confirm pm_planning still imports cleanly (proves bsm_mock untouched):

  ```bash
  python -c "from back_dev_home.ebeam.hitachi.pm_planning import data as d; print('pm_planning OK')"
  ```

- [ ] **10.6 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/data.py \
          back_dev_home/ebeam/hitachi/hardware/providers/mock.py \
          back_dev_home/ebeam/hitachi/hardware/providers/office.py
  git commit -m "feat(hardware): dispatch all six services through mock/office providers"
  ```

---

## Task 11 — routes.py: new `<eqp_id>/<service>` path, params, window, validation

New URL `GET /<tool_slug>/hardware/<eqp_id>/<service>`. Parse `fab_name`/`start`/`end`; default window = last 30 days anchored to `NOW`; mdc/sce treat `end` as as-of (ignore `start`). Validate `tool_slug` and `service` → 400. `eqp_id` is a required path segment now (no longer a query param), but keep returning available-but-empty when the segment is a placeholder like `_` (frontend lands on the page before a tool is chosen). Decision: treat the literal segment `_` (underscore) OR empty as "no eqp selected".

**Files:**
- `back_dev_home/ebeam/hitachi/hardware/routes.py` (modify)

**Interfaces:**
- Consumes: `data.get_hardware_service(tool_slug, service, eqp_id, fab_name, start, end)`, `VALID_SERVICES`, `VALID_TOOL_SLUGS`
- Produces: Flask route `hardware_service(tool_slug, eqp_id, service)`

**Steps:**

- [ ] **11.1 Write the gate (RED).** Use Flask's test client (no live server needed):

  ```bash
  python -c "from back_dev_home import create_app; \
  c = create_app().test_client(); \
  r = c.get('/api/cdsem/hardware/ECXDX204/bsm?fab_name=M16B'); \
  assert r.status_code == 200, r.status_code; j = r.get_json(); \
  assert j['service']=='bsm' and j['eqp_id']=='ECXDX204' and j['fab_name']=='M16B'; \
  assert j['available'] and j['docs']; \
  r2 = c.get('/api/cdsem/hardware/ECXDX204/mdc?fab_name=M16B'); \
  assert r2.get_json()['settings']; \
  r3 = c.get('/api/cdsem/hardware/ECXDX204/bogus?fab_name=M16B'); assert r3.status_code==400; \
  r4 = c.get('/api/bogus/hardware/ECXDX204/bsm'); assert r4.status_code==400; \
  r5 = c.get('/api/cdsem/hardware/_/bsm'); assert r5.status_code==200 and r5.get_json()['eqp_id'] is None; \
  print('OK')"
  ```

  (If `create_app` lives elsewhere, confirm via `python -c "import back_dev_home; print(back_dev_home.create_app)"`; the project's WSGI entry `index.py` imports it from `back_dev_home`.)
- [ ] **11.2 Implement (GREEN).** Replace `routes.py`:

  ```python
  from datetime import datetime, timedelta

  from flask import Blueprint, jsonify, request

  from back_dev_home.ebeam.hitachi._tool_specs import VALID_TOOL_SLUGS
  from back_dev_home.ebeam.hitachi.hardware.data import (
      VALID_SERVICES,
      get_hardware_service,
  )


  bp = Blueprint("ebeam_hardware", __name__)

  # Anchor matches the mock generators so the default 30-day window lines up
  # with the data they fabricate.
  _NOW = datetime(2026, 5, 24, 9, 0)
  _DEFAULT_WINDOW_DAYS = 30


  def _resolve_eqp_id(raw_segment: str) -> str | None:
      seg = (raw_segment or "").strip()
      # "_" is the frontend's placeholder for "no tool selected yet".
      if not seg or seg == "_":
          return None
      return seg


  def _resolve_fab_name() -> str | None:
      raw = (request.args.get("fab_name") or "").strip()
      return raw or None


  def _parse_iso(raw: str | None) -> datetime | None:
      if not raw:
          return None
      try:
          return datetime.fromisoformat(raw.replace("Z", "").strip())
      except ValueError:
          return None


  def _resolve_window() -> tuple[datetime, datetime]:
      end = _parse_iso(request.args.get("end")) or _NOW
      start = _parse_iso(request.args.get("start")) or (end - timedelta(days=_DEFAULT_WINDOW_DAYS))
      if start > end:
          start, end = end, start
      return start, end


  @bp.get("/<tool_slug>/hardware/<eqp_id>/<service>")
  def hardware_service(tool_slug: str, eqp_id: str, service: str):
      if tool_slug not in VALID_TOOL_SLUGS:
          return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
      if service not in VALID_SERVICES:
          allowed = ", ".join(repr(s) for s in sorted(VALID_SERVICES))
          return jsonify({"error": f"service must be one of {allowed}"}), 400

      start, end = _resolve_window()
      payload = get_hardware_service(
          tool_slug,
          service,  # type: ignore[arg-type]
          _resolve_eqp_id(eqp_id),
          _resolve_fab_name(),
          start,
          end,
      )
      return jsonify(payload)
  ```

  Note: mdc/sce ignore `start` internally (they read `end` as as-of) — the route still parses both uniformly; the providers decide what to use.
- [ ] **11.3 Run the gate (GREEN).** Re-run 11.1; confirm `OK`.
- [ ] **11.4 Commit.**

  ```bash
  git add back_dev_home/ebeam/hitachi/hardware/routes.py
  git commit -m "feat(hardware): equipment-first route, fab_name/start/end params, 30-day window"
  ```

---

## Task 12 — Contract YAML + fixtures: update, capture, check

Update `docs/api-contracts/hardware.yaml` to the new surface, add hardware ENDPOINTS to `scripts/capture_fixtures.py`, then capture + check against the running server.

**Files:**
- `docs/api-contracts/hardware.yaml` (modify)
- `scripts/capture_fixtures.py` (modify)

**Interfaces:**
- Produces: updated YAML contract; new `ENDPOINTS` entries; frozen fixtures under `back_dev_home/ebeam/hitachi/hardware/__fixtures__/`

**Steps:**

- [ ] **12.1 Update `hardware.yaml`.** Make these edits:
  - `base_path: /api/{tool_slug}/hardware/{eqp_id}/{service}`
  - `description`: mention all six services (BM/PM, BSM/beam_shape, Reso Center, FDC, MDC, SCE).
  - `HardwarePayload`: rename `fab_id` → `fab_name`; change `service.enum` to `["bsm", "reso-center", "fdc", "mdc", "sce", "bm-pm"]`; add:

    ```yaml
        docs:
          type: array
          items: object
          required: false
          description: Faithful time-series raw docs (bsm / reso-center / fdc), ascending time.
        settings:
          type: object
          required: false
          description: Faithful dict-of-dict (mdc / sce) — selected eqp + in-fab siblings.
    ```

  - `endpoints[0]`:
    - `path: /api/{tool_slug}/hardware/{eqp_id}/{service}`
    - add `eqp_id` to `path_params` (`type: string`, description: "Equipment ID (required path segment; '_' = none selected yet).")
    - `service.enum` → the 6 keys
    - `query_params`: drop `eqp_id`; rename `fab_id` → `fab_name` (description: "Fab name scope hint; required for mdc/sce siblings."); add `start` and `end` (`type: string`, `format: ISO-8601`, `required: false`, default note "last 30 days"; for mdc/sce `end` is the as-of date and `start` is ignored).
    - `example_request: "GET /api/cdsem/hardware/ECXDX204/mdc?fab_name=M16B&end=2026-05-24"`
    - replace `example_response` with a worked MDC example:

      ```yaml
      example_response:
        tool_slug: cdsem
        service: mdc
        eqp_id: ECXDX204
        fab_name: M16B
        available: true
        fetched_at: "2026-05-24T00:00:00+00:00"
        summary: 선택 장비와 동일 fab 장비의 MDC 보정 계수 스냅샷(as-of)을 제공합니다.
        cards:
          - { key: as_of, label: 기준일, value: "2026-05-24", tone: neutral }
          - { key: sibling_count, label: 동일 fab 장비, value: 4, unit: 대, tone: neutral }
        tables: []
        settings:
          ECXDX204:
            "800V_HR_0Deg": "1.004984"
            "800V_HR_90Deg": "1.005625"
            "500V_HR_0Deg": "1.004096"
            "500V_HR_90Deg": "1.003888"
      ```

- [ ] **12.2 Add hardware ENDPOINTS to `scripts/capture_fixtures.py`.** Append to the `ENDPOINTS` list (one per service, representative eqp/fab/window):

  ```python
      # hitachi hardware (equipment-first path; tool_slug + eqp_id + service)
      ("ebeam/hitachi/hardware", "hardware-bsm.json",
       "/api/cdsem/hardware/ECXDX204/bsm?fab_name=M16B&start=2026-04-24&end=2026-05-24"),
      ("ebeam/hitachi/hardware", "hardware-reso-center.json",
       "/api/cdsem/hardware/ECXDX204/reso-center?fab_name=M16B&start=2026-04-24&end=2026-05-24"),
      ("ebeam/hitachi/hardware", "hardware-fdc.json",
       "/api/cdsem/hardware/ECXDX204/fdc?fab_name=M16B&start=2026-05-17&end=2026-05-24"),
      ("ebeam/hitachi/hardware", "hardware-mdc.json",
       "/api/cdsem/hardware/ECXDX204/mdc?fab_name=M16B&end=2026-05-24"),
      ("ebeam/hitachi/hardware", "hardware-sce.json",
       "/api/cdsem/hardware/ECXDX204/sce?fab_name=M16B&end=2026-05-24"),
      ("ebeam/hitachi/hardware", "hardware-bm-pm.json",
       "/api/cdsem/hardware/ECXDX204/bm-pm?fab_name=M16B"),
  ```

  Note the `_truncate` helper caps arrays at 30 rows — that's fine; `Coefficients[360]` and `values[~100]` will be truncated to 30 in the fixture, which is enough for the shape check.
- [ ] **12.3 Capture fixtures (live server).** The user runs Flask (likely on **:5050**). If so, run with the port overridden — the simplest path is to temporarily set `FLASK_BASE` via a tiny wrapper or edit it for the run:

  ```bash
  # If Flask is on :5050, point the scripts at it for this run.
  python -c "import scripts.capture_fixtures as m; m.FLASK_BASE='http://localhost:5050'; raise SystemExit(m.main())"
  ```

  (If Flask is on :5000, just run `python scripts/capture_fixtures.py`.) Confirm six `[ OK ]` lines for the new hardware endpoints and that `back_dev_home/ebeam/hitachi/hardware/__fixtures__/*.json` were written.
- [ ] **12.4 Check contract (live server).**

  ```bash
  python -c "import scripts.check_contract as m; m.FLASK_BASE='http://localhost:5050'; raise SystemExit(m.main())"
  ```

  (Or `python scripts/check_contract.py` on :5000.) Confirm the six hardware endpoints report `[ OK ]` and the run ends `N / N 통과`.
- [ ] **12.5 Markdown lint (only if markdown was touched).** This task edits a `.yaml` (not linted) but if you touched any `.md`, run:

  ```bash
  npm run lint:md
  ```

- [ ] **12.6 Commit.**

  ```bash
  git add docs/api-contracts/hardware.yaml scripts/capture_fixtures.py \
          back_dev_home/ebeam/hitachi/hardware/__fixtures__/
  git commit -m "docs(hardware): update contract + capture fixtures for raw-doc services"
  ```

---

## Self-Review — spec coverage map

Every section of `docs/superpowers/specs/2026-06-19-hardware-raw-doc-mocks-design.md` maps to a task (frontend-only items are explicitly deferred to the frontend plan):

| Spec section | Covered by |
| --- | --- |
| §1 Goal (mock 5 datasets in final retrieved form) | Tasks 4–8 |
| §2.1 Fidelity (every field, metadata tail, source spellings) | Tasks 4–8 (Global Constraint 4) |
| §2.2 URL equipment-first `<eqp_id>/<service>?fab_name&start&end` | Task 11 |
| §2.3 mdc/sce eqp + in-fab siblings, as-of from `end` | Tasks 3, 7, 8, 11 |
| §2.4 Route migration (all services one surface) | Task 11 |
| §2.5 `fabId`→`fabName` rename end-to-end | Tasks 1, 9, 10, 11 (backend half) |
| §2.6 BSM rebuild, drop `index2`, `total` only | Tasks 2, 4 |
| §3 API URL contract + 400s + CD-SEM-only `available:false` | Tasks 10, 11 |
| §4 Deep-link contract | Frontend plan (page route) — backend unaffected; noted out of scope |
| §5 Canonical payload (`docs`/`settings`, drop `bsm`/`BsmBlock`) | Tasks 1, 9 |
| §6.1 bsm faithful `total` doc shape | Tasks 2, 4 |
| §6.2 reso-center faithful doc shape | Task 5 |
| §6.3 fdc 4 fdc_key `values` structures | Task 6 |
| §6.4 mdc dict-of-dict, varying conditions, as-of | Task 7 |
| §6.5 sce dict-of-dict, Coefficients[360], as-of | Task 8 |
| §7 Hardware page UI/UX (5 panels) | Frontend plan (out of scope here) |
| §8 Module layout (metrics.py + 5 new mocks, keep bsm_mock) | Tasks 2–8 (File Structure) |
| §9 Determinism & volume (md5 seed, NOW anchor, siblings) | Tasks 3–8 (Global Constraint 2) |
| §10 Frontend changes | Frontend plan (out of scope here) |
| §11 Scope (backend mocks in scope; office stub) | Tasks 4–10 |
| §12 Blast radius (touched/untouched files) | File Structure; Global Constraint 3 (bsm_mock untouched, verified Task 10.5) |
| §13 Open assumptions (30-day default, data-driven selectors, thin cards, 3–5 siblings) | Tasks 2, 3, 9, 11 |

Verification posture confirmed: no pytest introduced; every task has a runnable RED→GREEN gate (`python -c` import-and-assert or Flask test client); the final task captures fixtures and runs the contract harness against the live server. `providers/bsm_mock.py` is never edited and `pm_planning` import is re-verified in Task 10.5.
