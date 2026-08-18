# health — office migration

## Rules

- FIRST copy the tracked adapter, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
  The `cp` is also what switches the feature on — there is no activation list.
- `office_example.py` is **already fully implemented**. Nothing is stubbed out;
  the office step really is just the `cp`. Change it only if the office proves
  something wrong, and make that change in `office_example.py` (tracked) as
  well as the copy, or it is lost on the next sync.
- Edit ONLY `providers/office.py` (and, for anything worth keeping,
  `providers/office_example.py`). Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `providers/probe_common.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Only one of this feature's endpoints swaps

| Endpoint | Auth | Provider swap | Source |
| --- | --- | --- | --- |
| `GET /api/health/services` | open to all users | yes, via `data.py` | `providers/{mock,office}.py` |
| `GET /api/health/providers` | `@require_admin` | no — carve-out | `_runtime/data_provider.py` |
| `GET /api/health/data-mode` | open to all users | no — carve-out | `_runtime/data_provider.py` |
| `GET /api/health/deployment` | open to all users | no — carve-out | `_runtime/env.py` |
| `GET /api/health/logging` | `@require_admin` | no — carve-out | `_logging/opensearch_handler.py` |
| `GET /api/health/jobs` | `@require_admin` | no — carve-out | `app.extensions["scheduler_run_log"]` |

Every carve-out reads the runtime **directly** on purpose. They are
introspection, not phase-swappable data, and each would be self-defeating if it
went through `data.py`: a swappable `/health/providers` could misreport itself
in exactly the situation you would query it, a swappable `/health/data-mode`
could not answer "is this generated data?" honestly *because the answer is
which provider is running*, and a swappable `/health/logging` could hide the
very log loss being asked about. A test pins that `health/data.py` never grows
a `get_provider_table`, so do not "fix" this by routing them through `data.py`.

**A carve-out is not automatically admin-only.** The gate follows what the
answer reveals, not how it is sourced:

- `/health/providers` and `/health/jobs` enumerate every feature or job with
  the reason each resolved as it did — deployment shape, admin-only.
- `/health/logging` names the log index alias — admin-only.
- `/health/data-mode` answers about one named feature the caller already picked.
  A "this is demo data" marker only admins can see is not a marker, so it is
  open, and it returns no reason string.
- `/health/deployment` answers which deployment the caller is already talking
  to, which the address bar gives away. The SPA reads it to keep unvalidated
  실험실 rows out of the production menu, so a normal user must be able to ask.

At home the no-cookie fallback identity is `local-dev`, which **is** an admin,
so a bare curl answers 200 on the gated ones too; send a member id
(`-b "LASTUSER=1234567"`) to see the 403.

## Endpoint: GET /api/health/services

- Handler: `routes.py` → `data.get_services_health()`, returned as the JSON
  body via `jsonify(...)`. No auth gate — a normal user seeing "Redis is down"
  is the whole point of the landing page's health card. The route wraps the
  call in a try/except that answers a stable JSON 503
  (`{"error": {"code": "health_unavailable", ...}}`) if the *provider itself*
  breaks — a bad `office.py` import, a config raise — instead of Flask's bare
  HTML 500.
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

- **This feature is NOT canned data, and the probes live in neither
  provider.** `providers/probe_common.py` holds the single implementation of
  all three checks (`check_redis` / `check_opensearch` / `check_minio`, and
  `probe_services()` which runs all three); both providers call it. Two copies
  is how they drifted before: the office copy stopped chaining MinIO to the
  OpenSearch doc while the home copy kept doing it.
- Each provider keeps only what actually differs. `mock.py` owns the mode gate
  and the canned home rows: when `get_mode() != "office"` it short-circuits
  and returns `"mock · "` rows without dialing anything. That gate is mode,
  not reachability — home's `.env` carries the office `REDIS_HOST`, so probing
  from home is a guaranteed connect-timeout block on every call, not a cheap
  "try and fall back". `office_example.py` owns the standalone self-check and
  its raw payload dump.
- `probe_services(capture=...)` is the one knob. Pass nothing — the request
  path — and the probes stay a plain liveness check. Pass a dict and each
  probe records what it pulled off the wire and does the extra reads worth
  doing for a human (Redis `SCAN`, a longer MinIO page). It is a parameter,
  not a module flag, because the server answers every request on a fresh
  thread and a shared capture dict raced across them.
- The probes:
  - **Redis** — `PING` only, via the shared fail-fast client in
    `_runtime/office_redis.py` (`REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD`).
    `PING` already proves the connection is open **and** authenticated, so the
    request path runs no `DBSIZE`/`SCAN`; that sampling is standalone-only.
  - **OpenSearch** — `ops_store.OSSearch(index="meas_hist_cdsem")`,
    `.latest("timestamp", size=1)`. `"up"` when the newest doc is within the
    1-hour freshness window, `"down"` with a `stale: ...` detail when it is
    older, `"down"` with `no data in meas_hist_cdsem` when the index is empty,
    `"down"` with `unusable timestamp in latest doc` when the field is renamed
    or reformatted. Stale counts as down on purpose: the cluster answers, but
    the ingest pipeline behind it has stopped, and the user-visible symptom is
    an outage. Schema drift gets its own row rather than falling into the
    failure trap, because calling it a failed probe sends an operator hunting
    a network problem that isn't there.
  - **MinIO** — a plain connectivity + auth check: a non-recursive listing of
    the bucket/prefix from `minio_handler/minio_config.py` (gitignored, **not**
    `.env` — env vars would override that file), bounded to the first
    `LIST_SAMPLE` entries. An empty listing is still `"up"`
    (`connected · user/2067928 is empty`) because MinIO answered and
    authorized the request.
  - **MinIO is deliberately NOT chained to the OpenSearch doc.** It used to
    stat the object named by the latest doc's `minio_path`, which proved more
    but left MinIO unverifiable whenever OpenSearch was down — the row said
    "no minio_path" and nothing about MinIO itself. The card's actual question
    is "can we reach storage and are we authenticated", and listing answers it
    on its own.
- **Failure detail is the exception CLASS only.** `/api/health/services` is
  open to every user, and `str(exc)` off a driver typically carries internal
  hostnames and ports. Each probe's failure row reads
  `probe failed (ConnectionError)` with `latency_ms: null` (the contract doc's
  "null when status is down"); the full message, the elapsed time and the
  traceback go to the `skewnono.health` server log
  (`probe_common.failure_row`). Do not put the driver text back on the wire,
  and do not relabel the phrase "unreachable" — the same trap catches missing
  libraries and API drift, which are not network problems.
- **Office mode never fakes a green row.** An office machine that has not yet
  `cp`'d `office.py` runs `mock.py`'s live probes — and a failed probe there
  renders `status: "down"`, never the canned `"up · mock"` row. That fallback
  used to exist and turned a real Redis outage into a green card.
- Aggregation: `get_services_health()` always runs all three probes (no
  short-circuiting) and returns all three rows in the fixed order
  `[redis, opensearch, minio]`, plus a `checked_at` stamped at call time
  (UTC, second resolution, `Z`-suffixed).
- Empty/error handling: there is no "empty" response — a successful call
  always returns exactly 3 `ServiceHealth` rows. A probe failure is
  `status: "down"`, never a missing row and never an exception out of
  `get_services_health()`. Only a provider-level blowup produces the route's
  503, and that body carries no `services` key at all rather than a short list
  that would read as "two services are fine".
- Office data source: <!-- OFFICE: confirm REDIS_HOST/REDIS_PORT/
  REDIS_PASSWORD, the `meas_hist_cdsem` OpenSearch index, and the MinIO
  bucket/prefix in minio_handler/minio_config.py are reachable from the
  office Flask process -->

## Standalone self-check

From the repo root at the office, without Flask, Nuxt or the provider switch
in the way:

```bash
python -m back_dev_home.health.providers.office
```

It prints the row each service would return over HTTP, then dumps the **raw**
payload pulled off each server — OpenSearch field names, the `timestamp` both
raw and parsed, the MinIO endpoint/bucket/listing — so the parsing can be
confirmed instead of trusting a green "up". Exits 1 if any service is down, so
it doubles as a shell check.

The raw capture is the `capture` dict `_main()` passes into `probe_services()`
— a local, not module state. The request path captures nothing, which is also
why it skips the `DBSIZE`/`SCAN` and reads only a bounded MinIO sample.
Logging is configured in `_main()` because the HTTP detail says only
`probe failed (ConnectionError)` — the driver's real message is in the log,
and on a self-check that log is the point.

## Notes

- `checked_at` is volatile (scrubbed by the parity harness) — office does not
  need to match it byte-for-byte, and the contract test only cares that it is
  a `str`.
- `tests/test_contract.py` calls `data.get_services_health()` directly, so it
  exercises whichever provider is active. `tests/test_office_template.py`
  drives `office_example.py` and `probe_common.py` against fake
  Redis/OpenSearch/MinIO clients, so every probe's success and failure path is
  covered from home too.
- Two repo-level docs still describe the pre-gate `/api/health/providers` as a
  bare post-deploy `curl` (`docs/back-end/provider-selection.md`,
  `docs/deployment.md` / `scripts/deploy/pack.py`). They now need an admin
  identity — `curl -b "LASTUSER=<admin id>"` — and were left untouched here
  only because this change is scoped to `back_dev_home/health/`.

## Verify

    SKEWNONO_HEALTH_PROVIDER=office .venv/bin/pytest back_dev_home/health
