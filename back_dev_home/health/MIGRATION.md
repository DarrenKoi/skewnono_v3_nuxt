# health — office migration

## Rules

- FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/health/services

- Handler: `routes.py` → `data.get_services_health()`, returned directly
  as the JSON body via `jsonify(...)`. The route has no auth decorator and
  no try/except — any exception propagates as a plain 500 from Flask.
- Contract: `ServicesHealthResponse` (row shape `ServiceHealth`) —

  ```python
  Status = Literal["up", "down"]


  class ServiceHealth(TypedDict):
      id: str
      label: str
      status: Status
      latency_ms: int | None
      detail: str


  class ServicesHealthResponse(TypedDict):
      checked_at: str
      services: list[ServiceHealth]
  ```

- **Important — this feature is NOT canned data.** Unlike most other
  features, the mock implementation (`providers/mock.py`) already contains
  the real office probe logic, guarded by try/except:
  - **Redis**: connects via `redis.Redis(...)` (host/port/password from
    `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD` env vars) and calls
    `.ping()`, timing the round trip.
  - **OpenSearch**: queries `ops_store.OSSearch(index="meas_hist_cdsem")`
    for the latest document sorted by `timestamp`; `"up"` if the latest
    timestamp is within `FRESHNESS_WINDOW` (1 hour) of now, else
    `"down"` with a `stale: ...` detail.
  - **MinIO**: reads `minio_path` (`"bucket/key"`) off the OpenSearch
    latest doc, then `minio_handler.MinioObject(bucket=...).stat(key)`;
    `"up"` if the object's `last_modified` is within the freshness window.
  - In the home environment none of these three servers are actually
    running, so every checker's `except Exception` branch fires (missing
    library, connection refused, etc.) and falls back to a canned
    `_MOCK_REDIS` / `_MOCK_OPENSEARCH` / `_MOCK_MINIO` value — each with a
    `"mock · "`-prefixed `detail` string so the fallback is visible in the
    response.
  - **Consequence for this migration: the contract fixes only the
    response SHAPE, not the values.** In the office, if Redis/OpenSearch/
    MinIO are reachable, the real probe branches run and `status`/
    `latency_ms`/`detail` will legitimately differ from the mock's canned
    "up" values (e.g. a real outage should surface as `"status": "down"`
    with a `stale: ...` or connection-error detail — that is correct
    behavior, not a regression). Do not try to make office match mock's
    literal values; only make it match `ServicesHealthResponse`'s shape.
  - Because of this, `providers/office.py` may end up being a very thin
    wrapper (or even a re-export) once the office runtime environment
    actually has `redis`, `ops_store`, and `minio_handler` available and
    configured — confirm connectivity/env vars are office-ready before
    assuming more code is needed here.
- Aggregation: `get_services_health()` always runs all three checks (no
  short-circuiting) and returns all three rows in the fixed order
  `[redis, opensearch, minio]`, plus a `checked_at` timestamp stamped at
  call time (`_now().isoformat(timespec="seconds")`, UTC).
- Empty/error handling: there is no "empty" response — the endpoint
  always returns exactly 3 `ServiceHealth` rows; a probe failure is
  represented as `status: "down"` (or the mock fallback), never as a
  missing row or a raised exception out of `get_services_health()`
  itself (each checker traps its own exceptions).
- Office data source: <!-- OFFICE: confirm REDIS_HOST/REDIS_PORT/
  REDIS_PASSWORD, the `meas_hist_cdsem` OpenSearch index, and the MinIO
  bucket referenced by that index's `minio_path` are reachable from the
  office Flask process -->
- Notes:
  - `checked_at` is volatile (scrubbed by the parity harness) — office
    does not need to match it byte-for-byte, and neither does the
    contract test care about its exact value, only that it is a `str`.
  - The parity harness pins `GET /api/health/services` as a `200`
    response reflecting the mock fallback values (all three services
    `"up"`) captured in the home environment. The contract test in
    `tests/test_contract.py` calls `data.get_services_health()` directly,
    so it always exercises the real `ServicesHealthResponse` shape
    regardless of which provider is active.

## Verify

    SKEWNONO_HEALTH_PROVIDER=office .venv/bin/pytest back_dev_home/health
