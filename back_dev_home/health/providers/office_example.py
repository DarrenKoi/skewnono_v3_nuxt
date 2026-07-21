# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office adapter for health — re-exports the shared live-probe logic.

Unlike most features, health's `providers/mock.py` is NOT canned data: it
already contains the real office probe logic, each check guarded by try/except:

- Redis      : `redis.Redis(...).ping()` (REDIS_HOST/REDIS_PORT/REDIS_PASSWORD)
- OpenSearch : `ops_store.OSSearch(index="meas_hist_cdsem").latest("timestamp")`
               — "up" if the latest doc is < 1h old (OPENSEARCH_* config)
- MinIO      : `minio_handler.MinioObject(bucket=...).stat(key)` off the latest
               OpenSearch doc's `minio_path` (MINIO_* config)

When a server or its client library is unavailable, that check falls back to a
visible `"mock · "` value instead of raising. In the office runtime — where
redis / ops_store / minio_handler are installed and REDIS_*/OPENSEARCH_*/MINIO_*
are set — the same probes return live results. So the office adapter is a thin
re-export (see health/MIGRATION.md: "may end up being … even a re-export").

Consequence: selecting office mode for health NEVER raises. A real outage
surfaces as `status: "down"`; an unconfigured probe shows a `"mock · "`
fallback; `/api/health/services` always returns a valid
`ServicesHealthResponse`. This is what keeps app startup clean when the master
switch (`SKEWNONO_DATA_PROVIDER=office`) flips health to office.
"""

from back_dev_home.health.providers.mock import get_services_health


__all__ = ["get_services_health"]
