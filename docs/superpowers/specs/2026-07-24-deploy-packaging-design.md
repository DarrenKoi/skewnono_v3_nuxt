# Deployment Packaging — Office → Cloud Bundle — Design

Date: 2026-07-24
Feature: `scripts/pack_deploy.py` (Phase 3 deploy tooling)

## Goal

Turn the repository working tree into a self-contained folder that can be copied
to `/project/workSpace` on the cloud host and run, carrying only what the
application needs at runtime. The deploy flow becomes:

```text
npm run build  →  python -m scripts.pack_deploy  →  copy folder to cloud  →  run
```

## Scope

In scope:

- `scripts/pack_deploy.py` — preflight checks, allowlist copy, prune, verify,
  and generated `MANIFEST.txt` + `DEPLOY.md`.
- `docs/deployment.md` — the human runbook for the office → cloud transfer.

Out of scope:

- Automating the transfer itself. The script stops at a folder on disk; moving
  it to the cloud stays manual.
- Vendoring Python wheels. The cloud reaches an internal PyPI mirror, so
  `pip install -r back_dev_home/requirements.txt` is sufficient.
- `ProxyFix` and the rate-limiter storage backend. Both are real issues (see
  Known Gaps) but are application changes, not packaging changes.

## Context That Constrains the Design

Three properties of this repository decide nearly every choice below.

**Depth is load-bearing.** `_runtime/env.py` defines `is_cloud()` as "does this
file resolve under `/project/workSpace`", and `spa_dir()` as
`parents[2] / "front-dev-home" / ".output" / "public"`. Cloud mode — which
gates the auth blueprint, the SPA mount, and office site detection — is a
property of the filesystem path, not of configuration. A flattened or
re-nested bundle loses all three while still returning HTTP 200.

**The files that matter most are untracked.** `providers/office.py` (6 exist
today), `minio_handler/minio_config.py`, and `back_dev_home/.env` are all
gitignored by design. A `git archive` based packer would produce a bundle that
boots cleanly and serves mock data in production — the worst available failure
mode, because nothing announces it.

**The bundle is hostname-agnostic.** The SPA resolves its API as the relative
`/api`, and Flask serves the SPA same-origin. One bundle therefore works on
both `skewnono-v3-webapp.aipp01.skhynix.com` and `skewnono.skhynix.com`; the
cutover needs no rebuild.

## Bundle Layout

The bundle root becomes `/project/workSpace` on the cloud host. Relative depths
below it must match the repository exactly.

```text
dist/skewnono-<YYYYMMDD-HHMM>/
├── index.py                        WSGI entry
├── wsgi.ini                        uwsgi config
├── DEPLOY.md                       generated runbook
├── MANIFEST.txt                    generated provenance record
├── back_dev_home/                  all .py + .env
├── front-dev-home/.output/public/  built SPA — this exact path or no UI
├── ops_store/
├── minio_handler/                  incl. gitignored minio_config.py
└── ftp_handler/
```

### Included

| Path | Reason |
| --- | --- |
| `index.py`, `wsgi.ini` | Entry point and process config |
| `back_dev_home/**/*.py` | The application, including `providers/office.py` |
| `back_dev_home/.env` | Boot config; `create_app()` loads it via `load_dotenv` |
| `back_dev_home/requirements.txt` | Installed on the cloud host |
| `front-dev-home/.output/public/` | Built SPA served by `_spa/serving.py` |
| `ops_store/` | Imported by `_logging`, `ebeam/hitachi/_office_search` |
| `minio_handler/` | Imported by `msr_image`, `msr_file`, `health` |
| `ftp_handler/` | Imported by `msr_image` office adapter |

### Excluded

| Path | Reason |
| --- | --- |
| `afm_data_platform/` | 1.8 MB; referenced only in a mock docstring |
| `ops_index_mgmt/` | Index-creation tooling; never imported by the app |
| `tests/`, `back_dev_home/**/tests/`, `conftest.py` | 64 test files, no runtime role |
| `back_dev_home/**/*.md` | 22 `MIGRATION.md` + READMEs — office-migration notes |
| `docs/`, `openwiki/`, `scripts/` | Development-time only |
| `node_modules/`, `.nuxt/`, `front-dev-home/app/` | Build inputs, not build outputs |
| `__pycache__/`, `*.pyc`, `.DS_Store`, `*.log` | Noise |

`providers/office_example.py` templates ship. They are small, and
`_runtime/office_template.py` reads them at boot to classify each adapter as
`SYNCED`/`STALE`/`EDITED`.

## Preflight Checks

The script refuses to produce a bundle that would misrepresent itself. Each
check corresponds to a failure that is invisible once deployed.

| Check | Failure it prevents | On failure |
| --- | --- | --- |
| `detect_site() == "office"` | Packing at home yields a mock-mode bundle | Refuse (`--force`) |
| `.output/public/index.html` exists | No SPA mount; blank page | Refuse |
| Build newer than newest `front-dev-home/app/**` | Shipping yesterday's UI | Refuse (`--allow-stale-build`) |
| `back_dev_home/.env` exists | Boot config missing | Refuse |
| `SKEWNONO_SECRET_KEY` is not the default | Prod sessions signed with `dev-only-not-for-prod` | Refuse (`--force`) |
| At least one `providers/office.py` | Bundle serves mock data in production | Refuse (`--force`) |
| `office_template.stale_adapters()` is empty | An `office.py` predating its template | Warn and list (`--force`) |

The stale-adapter check reuses `back_dev_home/_runtime/office_template.py`
rather than reimplementing the classification. That module already documents
the concrete incident it exists to prevent: commit `768f16b` moved a
`fail_ratio` derivation into the adapter, and office copies that predated it
silently rendered failure rates above 100%.

## Postflight Verification

After copying, the script asserts against the bundle itself rather than trusting
the copy logic:

1. `<bundle>/back_dev_home/_runtime/env.py` exists and its `parents[2]` equals
   the bundle root, so `spa_dir()` will resolve correctly on the cloud.
2. `<bundle>/front-dev-home/.output/public/index.html` exists.
3. No `__pycache__` directory survived the prune.

Catching a layout mistake here costs seconds; catching it on the cloud costs a
full transfer round-trip.

## MANIFEST.txt

Written into the bundle root. Records git SHA, branch, dirty flag, pack
timestamp, host, total size, file count, and the roster of features that have a
`providers/office.py` — that is, which tabs will serve real fab data.

The adapter roster is the point. Presence detection leaves no configuration line
to read afterwards, so without this file there is no way to answer "what is
actually running up there?" without shell access to the cloud host.

## Secrets

The bundle contains credentials: `back_dev_home/.env` and
`minio_handler/minio_config.py`. The script therefore:

- `chmod 700`s the output directory,
- prints a closing warning naming each credential file it copied,
- writes into `dist/`, which is already gitignored.

## CLI

```text
python -m scripts.pack_deploy [options]

--build               run `npm run build` in front-dev-home/ first
--out DIR             output parent directory (default: dist/)
--force               downgrade refusals to warnings
--allow-stale-build   skip the build-freshness check
```

## Cloud-Side Setup

Neither hostname requires a code or configuration change. The items below are
one-time, environment-side, and outside this repository.

1. **Unpack at `/project/workSpace`.** This path, not the URL, is what enables
   cloud mode.
2. **Confirm `hcputil` is on the cloud image.** `CloudIdentityProvider.__init__`
   imports `hcputil.auto.sso` eagerly and it is deliberately absent from
   `requirements.txt`. If missing, `create_app()` raises at boot. Verify with
   `python -c "import hcputil.auto.sso"` before deploying.
3. **Register the hostname with the SSO service.** `login_redirect_url` takes
   its base from the SSO object, so the app adapts on its own — but the SSO
   side needs the service URL allowlisted, once per hostname.
4. **Set a real `SKEWNONO_SECRET_KEY`**, distinct between the test host and
   production, so a test session cannot be replayed against production.

Explicitly do not add CORS origins (same-origin in cloud mode) and do not set
`SESSION_COOKIE_SECURE` or HSTS — both URLs are `http://`, and a Secure cookie
breaks login with no error message.

## Runbook

Generated into the bundle as `DEPLOY.md`:

```text
1. copy dist/skewnono-<stamp>/  →  /project/workSpace/ on the cloud host
2. pip install -r back_dev_home/requirements.txt
3. uwsgi --ini wsgi.ini        (or: python index.py)
4. verify: curl localhost:5000/api/health/providers
```

Step 4 matters: `/api/health/providers` is the one endpoint that deliberately
bypasses the provider swap mechanism, so it is the honest answer to whether
office mode actually engaged.

## Known Gaps

Neither is a packaging concern; both are recorded here because a test deploy is
where they will first be observable.

- **No `ProxyFix`.** Behind the aipp01 ingress, `request.remote_addr` is the
  proxy IP, so `_logging/activity.py` records the proxy rather than the user.
  Authenticated rate limiting is unaffected — it keys on `user_id` first — but
  anonymous traffic collapses into a single bucket.
- **Rate limiter uses `memory://` with `processes = 4`.** Counters are
  per-worker, so the effective limit is roughly 4× the configured value.

## Testing

- Preflight checks: unit tests with a temporary tree, one test per refusal.
- Prune rules: assert excluded patterns are absent from a packed fixture tree.
- Postflight: assert the depth invariant holds and that breaking it is caught.
- Manifest: assert the adapter roster matches the `office.py` files present.
