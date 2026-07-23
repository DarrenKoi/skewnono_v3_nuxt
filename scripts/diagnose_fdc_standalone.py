"""Standalone FDC OpenSearch diagnosis -- NO repo imports.

Depends ONLY on `opensearchpy`. Copy this single file anywhere (e.g. the office
box) and run it:

    python diagnose_fdc_standalone.py                 # tool=MCD018, last 30 days
    python diagnose_fdc_standalone.py MCD320 30

Why this exists: `scripts/diagnose_fdc_office.py` imports `back_dev_home` and
`ops_store`, which are not importable outside the repo venv, and it read source
files with the platform default encoding -- cp949 on a Korean Windows box --
which fails on the UTF-8 punctuation in the adapter comments. This file has
neither problem: no repo imports, the only file it reads (`.env`) is read as
UTF-8, and every line it prints is ASCII, so a cp949 console never chokes.

Config: reads OPENSEARCH_HOST/PORT/USER/PASSWORD from the environment. If
OPENSEARCH_HOST is unset it hunts for a `.env` file (UTF-8) in the current
directory, its parents, and ./back_dev_home/. Host and user default to the
known skewnono cluster; the password must come from env or .env.

What it decides, in one run: does the index resolve and hold docs, how are
`eqp_id` and `timestamp` actually mapped, which eqp_id values exist (so you can
see your tool spelled exactly as stored), the real timestamp span, and -- the
payoff -- which single query clause drops the count to zero.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from opensearchpy import OpenSearch
    from opensearchpy.exceptions import RequestError
except ImportError:
    sys.exit("opensearchpy is not installed.  pip install opensearch-py")


INDEX = "network_fdc_cdsem"
EQP_ID_KW = "eqp_id.keyword"
TS_FIELD = "timestamp"

# Known from ops_index_mgmt/network_fdc_cdsem.py. Password is never hardcoded.
DEFAULT_HOST = "skewnono-db1-os.osp01.skhynix.com"
DEFAULT_USER = "skewnono001"


# --------------------------------------------------------------------------- #
# config + client
# --------------------------------------------------------------------------- #
def _load_dotenv() -> None:
    """If OPENSEARCH_HOST is unset, find a .env (read UTF-8) and load OPENSEARCH_*."""
    if os.environ.get("OPENSEARCH_HOST"):
        return
    cwd = Path.cwd()
    candidates = []
    for base in [cwd, *cwd.parents]:
        candidates.append(base / ".env")
        candidates.append(base / "back_dev_home" / ".env")
    for path in candidates:
        try:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key.startswith("OPENSEARCH_") and key not in os.environ:
                os.environ[key] = val
        if os.environ.get("OPENSEARCH_HOST"):
            print("loaded config from " + str(path))
            return


def make_client() -> OpenSearch:
    _load_dotenv()
    host = os.environ.get("OPENSEARCH_HOST", DEFAULT_HOST)
    port = int(os.environ.get("OPENSEARCH_PORT", "443"))
    user = os.environ.get("OPENSEARCH_USER", DEFAULT_USER)
    password = os.environ.get("OPENSEARCH_PASSWORD", "")
    if not password:
        sys.exit(
            "OPENSEARCH_PASSWORD is not set. Put it in the environment, or in a "
            ".env file next to this script or under ./back_dev_home/.env "
            "(OPENSEARCH_PASSWORD=...).")
    print("host=%s  port=%s  user=%s" % (host, port, user))
    return OpenSearch(
        hosts=[{"host": host, "port": port, "scheme": "https"}],
        http_auth=(user, password),
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False,
    )


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def rule(title: str) -> None:
    print("\n" + "=" * 70 + "\n" + title + "\n" + "=" * 70)


def fail(label: str, exc: Exception) -> None:
    print("  !! %s FAILED: %s: %s" % (label, type(exc).__name__, exc))


def count(client: OpenSearch, filters: list) -> int:
    body = {"size": 0, "query": {"bool": {"filter": filters}}}
    res = client.search(index=INDEX, body=body)
    total = res.get("hits", {}).get("total", {})
    return total.get("value") if isinstance(total, dict) else total


def term(field: str, value: str) -> dict:
    return {"term": {field: value}}


def time_range(field: str, start: datetime, end: datetime) -> dict:
    return {"range": {field: {"gte": start.isoformat(), "lte": end.isoformat()}}}


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
def check_connectivity(client: OpenSearch) -> None:
    rule("[1] cluster reachable")
    info = client.info()
    print("  cluster: %s  version: %s"
          % (info.get("cluster_name"),
             info.get("version", {}).get("number")))


def check_index(client: OpenSearch) -> bool:
    rule("[2] does %r resolve?" % INDEX)
    resolved = client.indices.exists(index=INDEX)
    print("  exists(%r) -> %s" % (INDEX, resolved))
    if not resolved:
        try:
            found = client.indices.get_alias(index="*fdc*")
            print("  indices/aliases matching *fdc* :")
            for name in sorted(found):
                print("    " + name)
        except Exception:
            pass
        print("  >> index does not resolve; everything below is empty for that")
        print("     reason alone.")
    return resolved


def check_docs(client: OpenSearch) -> None:
    rule("[3] doc count + one raw document verbatim")
    try:
        total = count(client, [])
        print("  total docs in %s: %s" % (INDEX, total))
    except Exception as exc:
        fail("count", exc)
    try:
        res = client.search(index=INDEX, body={"size": 1})
        hits = res.get("hits", {}).get("hits", [])
        if not hits:
            print("  no documents at all -- ingestion has not populated this index.")
            return
        src = hits[0].get("_source", {})
        print("  field names present: %s" % sorted(src))
        for key in sorted(src):
            val = src[key]
            shown = val if key != "values" else (str(val)[:120] + " ...")
            print("    %-14s= %r" % (key, shown))
    except Exception as exc:
        fail("search size=1", exc)


def _field_spec(client: OpenSearch, field: str) -> dict:
    fm = client.indices.get_field_mapping(index=INDEX, fields=field)
    for per_index in fm.values():
        spec = (per_index.get("mappings", {})
                .get(field, {}).get("mapping", {}).get(field, {}))
        if spec:
            return spec
    return {}


def check_mappings(client: OpenSearch) -> None:
    rule("[4] how are eqp_id and timestamp mapped?")
    try:
        eqp = _field_spec(client, "eqp_id")
        print("  eqp_id    : %r" % eqp)
        if "keyword" in (eqp.get("fields") or {}):
            print("    >> text + .keyword  -> term on %r is CORRECT" % EQP_ID_KW)
        elif eqp.get("type") == "keyword":
            print("    >> bare keyword     -> drop the .keyword: term on 'eqp_id'")
        else:
            print("    >> %r without a keyword subfield -- cannot exact-match"
                  % eqp.get("type"))
    except Exception as exc:
        fail("eqp_id mapping", exc)
    try:
        ts = _field_spec(client, "timestamp")
        print("  timestamp : %r" % ts)
        if ts.get("type") == "date":
            print("    >> date  -> bare %r range/sort is CORRECT" % TS_FIELD)
        elif ts.get("type") == "text":
            print("    >> text  -> range under-matches AND sort errors; use "
                  "'timestamp.keyword'")
        else:
            print("    >> unexpected type %r" % ts.get("type"))
    except Exception as exc:
        fail("timestamp mapping", exc)


def check_eqp_ids(client: OpenSearch, tool: str) -> None:
    rule("[5] which eqp_id values exist? (is %r among them, spelled how?)" % tool)
    for field in (EQP_ID_KW, "eqp_id"):
        try:
            body = {"size": 0,
                    "aggs": {"ids": {"terms": {"field": field, "size": 50}}}}
            res = client.search(index=INDEX, body=body)
            buckets = res.get("aggregations", {}).get("ids", {}).get("buckets", [])
            if not buckets:
                print("  terms on %r: (no buckets)" % field)
                continue
            keys = [b["key"] for b in buckets]
            preview = ", ".join("%s(%s)" % (b["key"], b["doc_count"])
                                for b in buckets[:20])
            print("  terms on %r: %d values" % (field, len(keys)))
            print("    " + preview)
            print("    %r present exactly: %s" % (tool, tool in keys))
        except Exception as exc:
            fail("terms agg on %s" % field, exc)


def check_timestamps(client: OpenSearch) -> None:
    rule("[6] timestamp span and spelling")
    try:
        body = {"size": 0, "aggs": {
            "lo": {"min": {"field": TS_FIELD}},
            "hi": {"max": {"field": TS_FIELD}}}}
        aggs = client.search(index=INDEX, body=body).get("aggregations", {})
        print("  span: %s .. %s"
              % (aggs.get("lo", {}).get("value_as_string"),
                 aggs.get("hi", {}).get("value_as_string")))
    except Exception as exc:
        fail("min/max agg", exc)
    try:
        body = {"size": 3, "sort": [{TS_FIELD: {"order": "desc"}}]}
        res = client.search(index=INDEX, body=body)
        print("  newest raw _source timestamps:")
        for hit in res.get("hits", {}).get("hits", []):
            ts = hit.get("_source", {}).get("timestamp")
            flag = ""
            if isinstance(ts, str) and (ts.endswith("Z") or "+" in ts):
                flag = "   <<< carries an offset"
            print("    %r%s" % (ts, flag))
    except Exception as exc:
        fail("sorted search", exc)


def check_clauses(client: OpenSearch, tool: str, days: int) -> None:
    rule("[7] THE decisive test: which clause empties the result?")
    end = datetime.now()
    start = end - timedelta(days=days)
    wide = end - timedelta(days=365)
    eqp_kw = term(EQP_ID_KW, tool)
    eqp_bare = term("eqp_id", tool)
    print("  window: %s .. %s\n" % (start.isoformat(), end.isoformat()))
    probes = [
        ("term eqp_id.keyword only (no time)", [eqp_kw]),
        ("term eqp_id (bare) only (no time)", [eqp_bare]),
        ("timestamp range only (this window)", [time_range(TS_FIELD, start, end)]),
        ("eqp_id.keyword + this window  [what the adapter sends]",
         [eqp_kw, time_range(TS_FIELD, start, end)]),
        ("eqp_id.keyword + last 365 days",
         [eqp_kw, time_range(TS_FIELD, wide, end)]),
    ]
    for label, filters in probes:
        try:
            print("  %-52s: %s docs" % (label, count(client, filters)))
        except RequestError as exc:
            # e.g. sorting/aggregating a text field, or bad field -- report, keep going
            print("  %-52s: ERROR %s" % (label, exc.error))
        except Exception as exc:
            fail(label, exc)
    print(
        "\n  read it like this:\n"
        "   * both eqp_id.keyword and bare-eqp_id are 0 -> the tool id does not\n"
        "     match any stored eqp_id (check the exact spelling printed in [5]).\n"
        "   * eqp_id.keyword > 0 but 'this window' == 0 while '365 days' > 0 ->\n"
        "     your data is older than %d days; widen the window.\n"
        "   * eqp_id.keyword + this window > 0 -> the query is fine; an empty\n"
        "     PAGE then means the fdc_key/validate step or the frontend, not OS."
        % days
    )


def check_adapter_query(client: OpenSearch, tool: str, days: int) -> None:
    rule("[8] full adapter-equivalent query (term + range + sort)")
    end = datetime.now()
    start = end - timedelta(days=days)
    body = {
        "size": 10000,
        "query": {"bool": {"filter": [
            term(EQP_ID_KW, tool),
            time_range(TS_FIELD, start, end),
        ]}},
        "sort": [{TS_FIELD: {"order": "asc"}}],
        "_source": ["eqp_id", "fdc_key", "timestamp"],
    }
    try:
        res = client.search(index=INDEX, body=body)
        hits = res.get("hits", {}).get("hits", [])
        print("  returned %d docs" % len(hits))
        keys = {}
        for h in hits:
            k = h.get("_source", {}).get("fdc_key")
            keys[k] = keys.get(k, 0) + 1
        if hits:
            print("  by fdc_key: %s" % keys)
            first = hits[0].get("_source", {})
            print("  first: fdc_key=%r  timestamp=%r  eqp_id=%r"
                  % (first.get("fdc_key"), first.get("timestamp"),
                     first.get("eqp_id")))
        else:
            print("  EMPTY -- see [7] for which clause is responsible.")
    except RequestError as exc:
        print("  ERROR: %s" % exc.error)
        print("  (a sort/fielddata error here means timestamp is NOT a date.)")
    except Exception as exc:
        fail("adapter query", exc)


def main() -> int:
    tool = sys.argv[1] if len(sys.argv) > 1 else "MCD018"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    print("FDC standalone diagnosis -- index=%r tool=%r window=%dd"
          % (INDEX, tool, days))
    client = make_client()
    try:
        check_connectivity(client)
    except Exception as exc:
        fail("connect", exc)
        print("\nCannot continue without a connection.")
        return 1
    if not check_index(client):
        return 1
    check_docs(client)
    check_mappings(client)
    check_eqp_ids(client, tool)
    check_timestamps(client)
    check_clauses(client, tool, days)
    check_adapter_query(client, tool, days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
