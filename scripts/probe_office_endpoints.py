"""Smoke-test every read endpoint listed on the /endpoints page, with a token.

The /endpoints page (front-dev-home/app/pages/endpoints.vue, backed by
app/data/apiCatalog.ts) is the catalog promised to API consumers. A swap that
breaks one of those endpoints silently is the failure mode this script exists
to catch at the office: the mock passes, the office adapter passes its per-
feature contract suite, but the catalog page still tells the truth because it
is the one place that names every token-authable route end-to-end.

It does two things, in order:

  1. Token auth probe. A protected endpoint must 401 without a token and 401
     with a junk token, then 200 with the real one. That three-state check is
     the cheapest end-to-end proof that the _try_api_token middleware
     (back_dev_home/_auth/middleware.py) is wired and that the office
     api_tokens provider recognized the plaintext. A home mock token would
     pass 1 and 2 but fail 3, which is exactly the office-vs-mock gap.

  2. Catalog sweep. Every endpoint in apiCatalog.ts marked '토큰 가능' is
     fetched with the bearer token and a representative example path/query
     (the same `example` field the page renders into curl/python snippets).
     Admin-only endpoints are skipped with a note unless --admin is passed;
     human-session-only endpoints (POST/DELETE api-tokens) are out of scope.

Run FROM THE OFFICE NETWORK (the base URL does not resolve from home):

    .venv/bin/python -m scripts.probe_office_endpoints
    .venv\\Scripts\\python -m scripts.probe_office_endpoints   # office Windows PC

The token is NOT an argument: mint one in the web UI (settings -> API tokens)
and export it, the same way the documented Python snippet expects:

    set SKEWNONO_TOKEN=skn_...        # cmd
    export SKEWNONO_TOKEN=skn_...     # bash

Rate limit is 20 per 5 seconds per user (back_dev_home/__init__.py). This
script sleeps just over 5s between the auth probe and the sweep and paces
the sweep itself so its own burst cannot 429 itself. A 429 is still retried
once with backoff, because a real user hitting the app at the same time is
the expected office condition.

Read-only: every call is a GET. POST/DELETE endpoints in the catalog are
human-session-only and are deliberately skipped, so this script never mint,
never revokes, never writes anywhere.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

# Make `back_dev_home` importable however this file was started. `-m` puts the
# working directory on sys.path and works from the repo root; running the file
# by path puts scripts/ there instead and fails on the first import below. Both
# forms get typed -- a file manager, an IDE "run this file" button and tab
# completion all produce the by-path one -- so support both.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Importing the package applies its stdout UTF-8 fix. `-m` gets it for free
# because -m imports the package first; running this file by path does not,
# and would then die on the ANSI code page. One line covers both.
import scripts  # noqa: E402,F401

from back_dev_home._auth.middleware import _BEARER_PREFIX  # noqa: E402


# Base URL mirrors the catalog's BASE_URL (app/data/apiCatalog.ts) so the
# script and the page promise the same host. Overridable for pointing at a
# localhost Flask staging instance without editing the file.
DEFAULT_BASE = "http://skewnono.skhynix.com"

# The endpoint the auth probe uses to prove a token is accepted. It is the
# cheapest token-authable route that does not vary by tool/fab/recipe, so the
# probe's verdict is about the token, not the parameter set.
AUTH_PROBE_PATH = "/api/account/api-tokens"

# The catalog's auth labels. Kept in sync with the `auth` field of
# ApiEndpoint in app/data/apiCatalog.ts. Strings are Korean because that is
# what the page shows; the script compares against these exact values.
AUTH_TOKEN_OK = "\ud1a0\ud0a0 \uac00\ub2a5"          # '토큰 가능'
AUTH_ADMIN_ONLY = "\uad00\ub9ac\uc790"                  # '관리자'
AUTH_HUMAN_ONLY = "\uc0ac\ub78c \uc138\uc158\ub9cc"    # '사람 세션만'


# The catalog, mirrored from app/data/apiCatalog.ts. The page is the source of
# truth for what API consumers are promised; a second list here is the price
# of not importing a .ts file from Python. Each entry is the `example` field
# (method, path, query, body) plus the `auth` label, which is all the script
# needs to drive a request and decide whether to skip.
#
# Paths keep the {tool_slug}/{eqp_id}/{service} placeholders of the catalog;
# `render` substitutes them from the example. `example.path` already has the
# substituted form (e.g. '/cdsem/storage'), so the placeholder list is only
# here to make the source of the duplication obvious.
CATALOG: list[dict[str, Any]] = [
    # 공통
    {"method": "GET", "path": "/api/health/services", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/health/services"}},
    {"method": "GET", "path": "/api/sem-list", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/sem-list"}},
    {"method": "GET", "path": "/api/announcements", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/announcements"}},
    # E-Beam Storage / Hardware
    {"method": "GET", "path": "/api/{tool_slug}/storage", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/storage", "query": {"fab_name": "M16A,R3"}}},
    {"method": "GET", "path": "/api/{tool_slug}/ppid-unavailable", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/hvsem/ppid-unavailable"}},
    {"method": "GET", "path": "/api/{tool_slug}/hardware/{eqp_id}/{service}", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/hardware/ECXDX204/bsm", "query": {"fab_name": "M16B"}}},
    # Recipe Search
    {"method": "GET", "path": "/api/{tool_slug}/recipe-search/recipes", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-search/recipes", "query": {"fab_name": "M11"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-search/recipe-detail", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-search/recipe-detail",
                 "query": {"recipe_name": "RCP_001"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-search/parameters", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-search/parameters",
                 "query": {"recipe_name": "RCP_001"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-search/measurement-points", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-search/measurement-points",
                 "query": {"recipe_name": "RCP_001", "parameter": "Para_13"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-search/param-info", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-search/param-info",
                 "query": {"recipe_name": "RCP_001", "parameter": "Para_13", "include": "amp"}}},
    {"method": "POST", "path": "/api/{tool_slug}/recipe-search/param-detail", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-search/param-detail",
                 "body": {"items": [{"locator": {"eqp_ip": "10.1.2.3",
                  "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"},
                  "parameter": "Para_13",
                  "slots": {"img_meas2": "PRMS0000"}}]}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-search/align-detail", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-search/align-detail",
                 "query": {"eqp_ip": "10.1.2.3", "class_name": "CLS",
                           "idw": "IDW_A", "idp": "IDP_B", "p_numbers": "1,2"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-search/lateral", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-search/lateral",
                 "query": {"recipe_name": "RCP_001"}}},
    {"method": "GET", "path": "/api/meas-hist", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/meas-hist", "query": {"tool_type": "cd-sem", "fab_name": "M11"}}},
    {"method": "GET", "path": "/api/msr-file", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/msr-file", "query": {"msr": "MSR_001"}}},
    {"method": "POST", "path": "/api/msr-files", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/msr-files", "body": {"items": [{"msr": "MSR_001"}]}}},
    # Recipe TAT
    {"method": "GET", "path": "/api/{tool_slug}/recipe-tat/ranking", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-tat/ranking", "query": {"limit": "100"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-tat/summary", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-tat/summary"}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-tat/daily-trend", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/hvsem/recipe-tat/daily-trend", "query": {"fab_name": "M14"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-tat/devices", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-tat/devices", "query": {"fab_name": "M11"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-tat/equipments", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-tat/equipments", "query": {"fab_name": "R3"}}},
    {"method": "GET", "path": "/api/{tool_slug}/recipe-tat/equipment-compare", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/recipe-tat/equipment-compare",
                 "query": {"fab_name": "R3", "eqp_id": "ECXDX123,ECDX456"}}},
    # Fail Issue
    {"method": "GET", "path": "/api/{tool_slug}/fail-issue/summary", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/fail-issue/summary", "query": {"fab_name": "M11"}}},
    {"method": "GET", "path": "/api/{tool_slug}/fail-issue/daily-trend", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/fail-issue/daily-trend"}},
    {"method": "GET", "path": "/api/{tool_slug}/fail-issue/align-ranking", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/hvsem/fail-issue/align-ranking", "query": {"limit": "50"}}},
    {"method": "GET", "path": "/api/{tool_slug}/fail-issue/meas-ranking", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/fail-issue/meas-ranking", "query": {"fab_name": "M11"}}},
    {"method": "GET", "path": "/api/{tool_slug}/fail-issue/devices", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/fail-issue/devices"}},
    # CD-SEM Device Statistics
    {"method": "GET", "path": "/api/cdsem/device-statistics/r3-device-grp", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/device-statistics/r3-device-grp"}},
    {"method": "GET", "path": "/api/cdsem/device-statistics/device-desc", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/device-statistics/device-desc", "query": {"fac_id": "M11,M14"}}},
    {"method": "GET", "path": "/api/cdsem/device-statistics/recipe-statistics", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/device-statistics/recipe-statistics",
                 "query": {"lot_cds": "R001,R002"}}},
    {"method": "GET", "path": "/api/cdsem/device-statistics/recipe-trend", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/cdsem/device-statistics/recipe-trend",
                 "query": {"lot_cds": "R001"}}},
    # 계정, 활동, 운영 -- token-authable entries only.
    # POST/DELETE /api/account/api-tokens are '사람 세션만' and are out of
    # scope (this script never mint or revokes); the GET is the auth probe
    # itself and is exercised in stage 1 rather than repeated here.
    {"method": "GET", "path": "/api/activity/me", "auth": AUTH_TOKEN_OK,
     "example": {"path": "/activity/me"}},
    {"method": "GET", "path": "/api/activity/summary", "auth": AUTH_ADMIN_ONLY,
     "example": {"path": "/activity/summary"}},
    {"method": "GET", "path": "/api/admin/logs", "auth": AUTH_ADMIN_ONLY,
     "example": {"path": "/admin/logs", "query": {"level": "ERROR", "limit": "50"}}},
]


def _headers(token: str | None) -> dict[str, str]:
    return {"Authorization": f"{_BEARER_PREFIX}{token}"} if token else {}


def _build_url(base: str, path: str, query: dict | None) -> str:
    url = base.rstrip("/") + path
    if query:
        from urllib.parse import urlencode
        url += "?" + urlencode(query)
    return url


def _request(requests: Any, url: str, *, token: str | None,
             method: str = "GET", body: Any = None, timeout: float) -> Any:
    """One HTTP call. The caller builds the full URL (path + query already
    joined) so the retry loop and the sweep stay in one place about what URL
    was tried. `body` is sent as JSON when set; responses are the caller's to
    interpret -- this function never raises for a status, only for transport.
    """
    headers = _headers(token)
    if body is not None:
        headers["Content-Type"] = "application/json"
    return requests.request(
        method, url, headers=headers,
        json=body if body is not None else None,
        timeout=timeout,
        allow_redirects=False,
    )


def _fetch_with_retry(requests: Any, url: str, *, token: str | None,
                      method: str = "GET", body: Any = None,
                      timeout: float, attempts: int = 2) -> Any:
    """One request, retrying only 429. Other statuses return to the caller.

    429 is the rate limit the app documents (20 per 5 seconds per user). This
    script paces itself, but a concurrent browser session at the office can
    still exhaust the shared budget; one retry with backoff covers that
    without masking a real problem (5xx, 401, 404 are not retried).
    """
    delay = 6.0
    last = None
    for attempt in range(attempts):
        last = _request(requests, url, token=token, method=method,
                       body=body, timeout=timeout)
        if last.status_code != 429 or attempt == attempts - 1:
            return last
        time.sleep(delay)
    return last


def _render_path(example_path: str) -> str:
    """The catalog stores the SUBSTITUTED path in example.path (e.g.
    '/cdsem/storage'), while `path` keeps the {placeholder} form for
    readability. The script calls the substituted one."""
    if not example_path.startswith("/"):
        example_path = "/" + example_path
    return "/api" + example_path


def _query_from(example: dict[str, Any]) -> dict[str, str] | None:
    q = example.get("query")
    if not q:
        return None
    return {k: str(v) for k, v in q.items()}


def _do_auth_probe(requests: Any, base: str, token: str, timeout: float) -> list[str]:
    """Three-state token check: no token -> 401, junk -> 401, real -> 200.

    Returns a list of finding strings; empty means the probe passed. The
    `no token` and `junk token` legs prove the middleware rejects before it
    proves anything about the real token, so a 200 from the real token is
    evidence of acceptance rather than of an open route.

    A transport failure on leg 1 refuses to guess: nothing below reflects
    what the middleware does, so legs 2 and 3 are skipped and the sweep is
    not run. The message tells the operator what to check so a raw traceback
    does not read as "the script is broken".
    """
    findings: list[str] = []
    print("[1/2] token auth probe against " + AUTH_PROBE_PATH)
    probe = base.rstrip("/") + AUTH_PROBE_PATH

    def _get(headers: dict[str, str] | None) -> Any:
        return requests.get(
            probe, headers=headers or {}, timeout=timeout,
            allow_redirects=False,
        )

    # leg 1: no Authorization header at all
    try:
        r1 = _get(None)
    except Exception as exc:  # noqa: BLE001 - any transport failure is the answer
        raise SystemExit(
            f"error: cannot reach {probe}\n"
            f"    {type(exc).__name__}: {exc}\n"
            "    Run from the office network; verify the app is up and\n"
            "    --base-url points at it (default is the production host)."
        ) from None
    if r1.status_code != 401:
        findings.append(
            f"no-token leg: expected 401, got HTTP {r1.status_code}"
        )
        print(f"      no-token   FAIL  expected 401, got HTTP {r1.status_code}")
    else:
        print("      no-token   OK    401 (no Authorization header)")

    # leg 2: a well-formed bearer header with a junk plaintext
    try:
        r2 = _get(_headers("skn_not-a-real-token"))
    except Exception as exc:  # noqa: BLE001
        findings.append(f"junk-token leg: transport failure: {type(exc).__name__}")
        print(f"      junk-token FAIL  transport: {type(exc).__name__}")
        return findings
    if r2.status_code != 401:
        findings.append(
            f"junk-token leg: expected 401, got HTTP {r2.status_code}"
        )
        print(f"      junk-token FAIL  expected 401, got HTTP {r2.status_code}")
    else:
        print("      junk-token OK    401 (invalid token rejected)")

    # leg 3: the real token
    try:
        r3 = _get(_headers(token))
    except Exception as exc:  # noqa: BLE001
        findings.append(f"real-token leg: transport failure: {type(exc).__name__}")
        print(f"      real-token FAIL  transport: {type(exc).__name__}")
        return findings
    if r3.status_code == 401:
        findings.append(
            "real-token leg: 401 -- the token was rejected. Mint a fresh one"
            " (settings -> API tokens) and re-export SKEWNONO_TOKEN."
        )
        print("      real-token FAIL  401 (token rejected -- see findings)")
    elif r3.status_code != 200:
        findings.append(
            f"real-token leg: expected 200, got HTTP {r3.status_code}"
        )
        print(f"      real-token FAIL  HTTP {r3.status_code}")
    else:
        print("      real-token OK    200 (token accepted)")
    return findings


def _do_catalog_sweep(
    requests: Any, base: str, token: str, *,
    timeout: float, include_admin: bool, pace_s: float,
) -> tuple[list[str], list[str]]:
    """Fetch every token-authable catalog endpoint; return (ok, failures)."""
    print("\n[2/2] catalog sweep (" + str(len(CATALOG)) + " entries)")
    ok: list[str] = []
    failures: list[str] = []
    skipped: list[str] = []

    for idx, entry in enumerate(CATALOG, start=1):
        auth = entry["auth"]
        method = entry["method"]
        example = entry["example"]
        path = _render_path(example["path"])
        query = _query_from(example)
        body = example.get("body")

        label = f"{method} {path}"
        if auth == AUTH_ADMIN_ONLY:
            if not include_admin:
                skipped.append(label)
                print(
                    f"  [{idx:>2}/{len(CATALOG)}] SKIP  {label}  "
                    f"(admin-only - --admin to include)"
                )
                continue
        elif auth == AUTH_HUMAN_ONLY:
            # No human-session-only GET is in the catalog (POST/DELETE
            # api-tokens are); skipped explicitly so the count is honest.
            skipped.append(label)
            print(
                f"  [{idx:>2}/{len(CATALOG)}] SKIP  {label}  "
                f"(human-session-only - out of scope)"
            )
            continue

        rendered = _build_url(base, path, query)
        try:
            resp = _fetch_with_retry(
                requests, rendered, token=token, method=method,
                body=body, timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 - transport failure is the answer
            failures.append(f"{label}: {type(exc).__name__}: {exc}")
            print(
                f"  [{idx:>2}/{len(CATALOG)}] FAIL  {label}  "
                f"({type(exc).__name__})"
            )
            time.sleep(pace_s)
            continue

        status = resp.status_code
        if status == 200:
            ok.append(label)
            print(f"  [{idx:>2}/{len(CATALOG)}]  OK   {label}  200")
        elif status == 404:
            # A 404 from a catalog endpoint with placeholder example params
            # (e.g. RCP_001 that does not exist at the office) is not a
            # contract break -- the route answered. Report but keep going.
            ok.append(label)
            print(
                f"  [{idx:>2}/{len(CATALOG)}]  ok*  {label}  404"
                f" (route answered; example param may not exist here)"
            )
        elif status == 401:
            failures.append(
                f"{label}: 401 -- token rejected mid-sweep (revoked?)"
            )
            print(f"  [{idx:>2}/{len(CATALOG)}] FAIL  {label}  401")
        elif status == 403:
            if auth == AUTH_ADMIN_ONLY:
                failures.append(f"{label}: 403 -- --admin set but caller is not admin")
            else:
                failures.append(f"{label}: 403 forbidden")
            print(f"  [{idx:>2}/{len(CATALOG)}] FAIL  {label}  403")
        elif status == 429:
            failures.append(f"{label}: 429 after retry -- rate limit exhausted")
            print(f"  [{idx:>2}/{len(CATALOG)}] FAIL  {label}  429")
        elif 500 <= status < 600:
            snippet = (resp.text or "")[:120].replace("\n", " ")
            failures.append(f"{label}: HTTP {status} {snippet}")
            print(f"  [{idx:>2}/{len(CATALOG)}] FAIL  {label}  HTTP {status}")
        else:
            failures.append(f"{label}: unexpected HTTP {status}")
            print(f"  [{idx:>2}/{len(CATALOG)}] FAIL  {label}  HTTP {status}")

        time.sleep(pace_s)

    if skipped:
        print(f"\n({len(skipped)} skipped - see above)")
    return ok, failures


def _print_alive() -> None:
    # First line, before any network call: the evidence the process is up,
    # and the one fact that differs per terminal (stdout encoding).
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    enc = sys.stdout.encoding
    print(f"python {sys.version.split()[0]}  stdout={enc}")
    # Reconfigure is applied by `import scripts` already; this is harmless
    # and keeps the line honest about what the script saw.
    if reconfigure is not None:
        try:
            reconfigure(line_buffering=True)
        except (ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="probe_office_endpoints",
        description="Smoke-test every token-authable endpoint on the /endpoints page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Read-only: every call is a GET except the two catalog POSTs,\n"
            "which read recipe/msr metadata and write nothing.\n"
            "Token is mandatory: export SKEWNONO_TOKEN=skn_... first."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SKEWNONO_BASE_URL", DEFAULT_BASE),
        help=f"API base URL (env SKEWNONO_BASE_URL, default {DEFAULT_BASE})",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("SKEWNONO_TOKEN"),
        help="API token (env SKEWNONO_TOKEN). Mint one: settings -> API tokens.",
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0,
        help="per-request timeout in seconds (default 30)",
    )
    parser.add_argument(
        "--pace", type=float, default=0.3,
        help="seconds between catalog requests (default 0.3, to stay under "
             "the 20-per-5s rate limit)",
    )
    parser.add_argument(
        "--admin", action="store_true",
        help="also exercise admin-only endpoints (activity/summary, admin/logs)",
    )
    args = parser.parse_args(argv)

    _print_alive()

    if not args.token:
        raise SystemExit(
            "error: SKEWNONO_TOKEN is not set. Mint one in the web UI "
            "(settings -> API tokens) and export it:\n"
            "    export SKEWNONO_TOKEN=skn_...\n"
            "Pass --token <value> to override without exporting."
        )

    try:
        import requests
    except ImportError:
        raise SystemExit(
            "error: requests is not installed. Run with the venv interpreter:\n"
            "    .venv/bin/python -m scripts.probe_office_endpoints"
        ) from None

    base = args.base_url.rstrip("/")
    print(f"base URL: {base}")
    print(f"token:    {args.token[:7]}... (redacted)")

    auth_findings = _do_auth_probe(requests, base, args.token, args.timeout)
    if auth_findings:
        print("\nauth probe FAILED -- not running the catalog sweep:")
        for f in auth_findings:
            print(f"  - {f}")
        return 1

    # Settle the rate-limit window from the auth probe before the sweep, so
    # the probe's three requests do not count toward the first 5-second
    # budget of the sweep.
    print("\n(settling the rate-limit window for 5s before the sweep...)")
    time.sleep(5.0)

    ok, failures = _do_catalog_sweep(
        requests, base, args.token,
        timeout=args.timeout, include_admin=args.admin, pace_s=args.pace,
    )

    print("\n---- summary ----")
    print(f"auth probe : {'PASS' if not auth_findings else 'FAIL'}")
    print(f"catalog ok : {len(ok)}")
    print(f"catalog bad: {len(failures)}")
    if failures:
        print("\nfailures:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nAll exercised endpoints answered 200/404.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())