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

## Framing: This Is a Feasibility Deploy

The first target is `http://skewnono-v3-webapp.aipp01.skhynix.com`, deployed
while the mock→office transition is still in progress. The question being
answered is **"does this application boot and serve in the cloud at all"** —
not "does it serve complete fab data".

That ordering decides the severity of every check in this document. A bundle
that boots and serves mock data on most tabs is a **success**. A bundle that
refuses to start is the only real failure. Checks therefore split into:

- **Blocking** — guarantees a dead deploy (no SPA, no `.env`, wrong layout).
- **Advisory** — the deploy works but serves less than it could (features
  still on mock, stale adapters). Warn, record in `MANIFEST.txt`, continue.

Data-completeness gates that would refuse to pack an incomplete transition are
explicitly wrong here and are advisory-only.

## Scope

In scope:

- `scripts/pack_deploy.py` — preflight checks, allowlist copy, prune, verify,
  and generated `MANIFEST.txt` + `DEPLOY.md`.
- `scripts/preflight_cloud.py` — ships **inside** the bundle as `preflight.py`
  and runs on the cloud host before uwsgi starts. Verifies imports, layout,
  and config, so a broken deploy is diagnosed in one command instead of by
  reading a uwsgi crash log.
- `back_dev_home/_auth/provider.py` — fix the `hcputil` module path
  (`auth`, not `auto`) with a dual-path import.
- `docs/deployment.md` — the human runbook for the office → cloud transfer.

Out of scope:

- Automating the transfer itself. The script stops at a folder on disk; moving
  it to the cloud stays manual.
- Vendoring Python wheels. The cloud reaches an internal PyPI mirror, so
  `pip install -r back_dev_home/requirements.txt` is sufficient.
- `ProxyFix` and the rate-limiter storage backend. Both are real issues (see
  Known Gaps) but are application changes, not packaging changes.
- Completing the mock→office transition. Orthogonal, and deliberately not a
  precondition for this deploy.

## The `hcputil` Import Bug

`back_dev_home/_auth/provider.py:32` reads:

```python
from hcputil.auto.sso import SSO
```

The correct module is `hcputil.auth.sso`. The typo traces to
`afm_data_platform/개발요구.txt:31`, the in-house requirements doc the code was
written from — a transcription that also contains `reutrn` and smart quotes,
so it is not a reliable source for the spelling.

This is a **boot blocker, not a warning**. `create_app()` constructs
`CloudIdentityProvider()` unconditionally when `is_cloud()` is true, with no
`try`/`except` around it, and `wsgi.ini` sets `need-app = true`. A wrong module
name means uwsgi refuses to start — the deploy fails before serving one request.

Because the cloud offers a slow iteration loop and the two candidate spellings
cannot both be verified from here, the fix tries both and reports both names if
neither resolves:

```python
def _load_sso_class():
    """`hcputil` is supplied by the cloud image, not by requirements.txt.

    The in-house doc this code was written from spells the module `auto`;
    the library spells it `auth`. Trying both costs one import attempt and
    removes an entire class of boot failure from a deploy we cannot easily
    iterate on.
    """
    errors = []
    for module_path in ("hcputil.auth.sso", "hcputil.auto.sso"):
        try:
            return importlib.import_module(module_path).SSO
        except ImportError as exc:
            errors.append(f"{module_path}: {exc}")
    raise ImportError(
        "hcputil SSO not importable; the cloud image must provide it. Tried:\n  "
        + "\n  ".join(errors)
    )
```

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
├── preflight.py                    on-cloud boot checker (run this first)
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
| `docs/`, `openwiki/`, `scripts/` | Development-time only — except `scripts/preflight_cloud.py`, copied to the bundle root as `preflight.py` |
| `node_modules/`, `.nuxt/`, `front-dev-home/app/` | Build inputs, not build outputs |
| `__pycache__/`, `*.pyc`, `.DS_Store`, `*.log` | Noise |

`providers/office_example.py` templates ship. They are small, and
`_runtime/office_template.py` reads them at boot to classify each adapter as
`SYNCED`/`STALE`/`EDITED`.

## Preflight Checks (Office Side)

Severity follows the feasibility framing: block only what guarantees a dead
deploy, advise on everything else.

| Check | Failure it prevents | Severity |
| --- | --- | --- |
| `.output/public/index.html` exists | No SPA mount; blank page | Block |
| `back_dev_home/.env` exists | `load_dotenv` finds nothing; unconfigured boot | Block |
| `back_dev_home/requirements.txt` exists | Nothing to `pip install` on the cloud | Block |
| Every included root exists and is non-empty | Silently truncated bundle | Block |
| Build newer than newest `front-dev-home/app/**` | Shipping yesterday's UI | Advisory |
| `SKEWNONO_SECRET_KEY` is not the default | Sessions signed with `dev-only-not-for-prod` | Advisory |
| `detect_site() == "office"` | Bundle packed at home carries no office adapters | Advisory |
| At least one `providers/office.py` | Every feature serves mock | Advisory |
| `office_template.stale_adapters()` is empty | An `office.py` predating its template | Advisory |

Blocking checks exit non-zero and write nothing. Advisory checks print a
`WARN:` line, are copied verbatim into `MANIFEST.txt`, and are summarised again
at the end of the run so a long log cannot hide them. `--strict` promotes every
advisory to blocking — the setting to use once the transition is complete and a
mock-serving bundle *should* fail the build.

The `SKEWNONO_SECRET_KEY` check is advisory rather than blocking only because
this deploy's purpose is reachability. It must be resolved before the
`skewnono.skhynix.com` cutover, and `MANIFEST.txt` records whether it was set.

The stale-adapter check reuses `back_dev_home/_runtime/office_template.py`
rather than reimplementing the classification. That module already documents
the concrete incident it exists to prevent: commit `768f16b` moved a
`fail_ratio` derivation into the adapter, and office copies that predated it
silently rendered failure rates above 100%.

## Cloud-Side Preflight (`preflight.py`)

The bundle carries a self-contained checker, run on the cloud host **before**
starting uwsgi. It exists because `need-app = true` turns any boot problem into
a uwsgi crash log, which is a poor diagnostic surface for a first deploy on a
host with a slow iteration loop.

```text
cd /project/workSpace && python preflight.py
```

It has no third-party imports of its own, so it runs before
`pip install` succeeds and can report *why* the install is incomplete.

| Check | Detects |
| --- | --- |
| `Path(__file__).parent` is under `/project/workSpace` | Unpacked at the wrong path — cloud mode off, no auth, no SPA |
| `back_dev_home/_runtime/env.py` `parents[2]` == bundle root | Layout mangled in transfer; `spa_dir()` will miss |
| `front-dev-home/.output/public/index.html` present | SPA lost in transfer |
| Import `flask`, `flask_cors`, `flask_limiter`, `pandas`, `pyarrow`, `redis`, `minio`, `opensearchpy`, `apscheduler`, `dotenv` | Incomplete `pip install`, named per package |
| Import `hcputil.auth.sso` or `hcputil.auto.sso` | The boot blocker above; reports which spelling the image provides |
| `back_dev_home/.env` present and parses | Missing or malformed config |
| `SKEWNONO_SECRET_KEY` set and not the default | Sessions signed with a known key |
| Roster of `providers/office.py` found | Which tabs will serve real data |

Exit code 0 means "uwsgi will start". Each failure prints the exact remedy.
Reporting *which* `hcputil` spelling resolved is the single most valuable line
of output from this first deploy — it settles the question permanently.

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
.venv/bin/python -m scripts.pack_deploy [options]

--build     run `npm run build` in front-dev-home/ first
--out DIR   output parent directory (default: dist/)
--strict    promote every advisory check to blocking; use after the
            mock→office transition is complete
```

Run from the repository root, matching `scripts/sync_office_adapters.py`.

## Cloud-Side Setup

Neither hostname requires a code or configuration change. The items below are
one-time, environment-side, and outside this repository.

1. **Unpack at `/project/workSpace`.** This path, not the URL, is what enables
   cloud mode.
2. **Confirm `hcputil` is on the cloud image.** `CloudIdentityProvider.__init__`
   imports it eagerly and it is deliberately absent from `requirements.txt`.
   If missing, `create_app()` raises at boot. `preflight.py` checks this and
   reports which module spelling the image provides.
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
2. cd /project/workSpace && python preflight.py       # expect exit 0
3. pip install -r back_dev_home/requirements.txt
4. python preflight.py                                # again: imports now resolve
5. uwsgi --ini wsgi.ini        (or: python index.py)
6. verify: curl localhost:5000/api/health/providers
```

`preflight.py` runs twice on purpose. The first pass — before `pip install` —
confirms the transfer landed at the right path with the right layout, which is
the failure that produces the most confusing symptoms. The second confirms the
dependency install actually completed and that `hcputil` is present.

Step 6 matters: `/api/health/providers` is the one endpoint that deliberately
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

`tests/test_pack_deploy.py`, run with `.venv/bin/python -m pytest tests/ -q`:

- Preflight severity: one test per check, asserting blocking checks exit
  non-zero and advisory checks continue while emitting `WARN:`.
- `--strict` promotes advisories to blocking.
- Prune rules: assert excluded patterns are absent from a packed fixture tree.
- Postflight: assert the depth invariant holds, and that a deliberately
  mangled bundle is caught.
- Manifest: assert the adapter roster matches the `office.py` files present.

`tests/test_preflight_cloud.py`:

- Reports a missing import by package name rather than raising.
- Accepts either `hcputil` spelling and names the one it found.
- Fails when the bundle root is not under `/project/workSpace`.

`back_dev_home/_auth/tests/test_provider.py`:

- `_load_sso_class()` returns the class when only `hcputil.auth.sso` exists.
- Falls back when only `hcputil.auto.sso` exists.
- Raises an `ImportError` naming both paths when neither exists.

Tests use `sys.modules` injection for the `hcputil` stubs, since the real
library exists only on the cloud image.
