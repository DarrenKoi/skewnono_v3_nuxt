"""Local MinIO connection settings.

This file is gitignored. Paste your keys here and they will be picked up
automatically by ``MinioConfig.from_env()`` / ``load_config()`` and by
``MinioObject(...)`` when ``bucket`` / ``prefix`` are omitted.

Precedence (highest → lowest) when resolving a final value:

1. Explicit kwargs passed to ``MinioConfig(...)`` or ``MinioObject(...)``
2. Environment variables (``MINIO_ENDPOINT`` etc.)
3. Constants defined in this file
4. Built-in defaults

Leaving a value as ``None`` means "no opinion — fall through to env/default".
"""

# --- connection ---
ENDPOINT: str | None = "aistor-api.lake.skhynix.com"
ACCESS_KEY: str | None = None
SECRET_KEY: str | None = None
SECURE: bool | None = False
REGION: str | None = None
CERT_CHECK: bool | None = True

# --- MinioObject defaults ---
BUCKET: str | None = "user"
PREFIX: str | None = "2067928/"
