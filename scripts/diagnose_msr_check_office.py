"""Print what the office meas_hist indices actually store in ``msr_check``.

Why this exists: on 2026-08-19 the skewvoir 검색 결과 table started gating the
row click on ``msr_check != "No"``, and at the office the whole table went
non-clickable while MinIO held the data. The frontend gate is gone again (see
front-dev-home/app/utils/measHistSelection.ts), but the underlying question is
still open, and it is not answerable from home:

  H1: the stored value is not the literal "Yes" that the adapter looks for.
      ``providers/office_example.py`` maps ANY unrecognized value to "No"
      (``_text(src.get("msr_check")).lower() == "yes"``), so "Y", "TRUE" or a
      boolean True all arrive at the frontend as "No".
  H2: the value really is "No" on those rows, but "No" does not mean the raw
      data is absent: ``minio_msr`` / ``minio_pkl`` are populated anyway.
  H3: ``msr`` itself is empty on most documents, so the rows never had an
      identity to open.

Each hypothesis implies a different fix, and two other places depend on the
answer: ``ebeam/_office_msr_cd.py`` filters ``msr_check.keyword == "Yes"`` for
tttm / pm-planning, and ``msr_file``'s adapter reads ``minio_pkl``. If H1 holds,
those screens are silently empty at the office for the same reason.

Read-only: counts, aggregations and a few sampled documents. Nothing is
written and no MinIO object is fetched.

Run FROM THE REPO ROOT at the office (reads OPENSEARCH_* from
back_dev_home/.env like the adapter does):

    .venv/bin/python -m scripts.diagnose_msr_check_office
"""

from __future__ import annotations

import os

import sys
from pathlib import Path
# Make `back_dev_home` importable however this file was started. `-m` puts the
# working directory on sys.path and works from the repo root; running the file
# by path puts scripts/ there instead and fails on the first import below. Both
# forms get typed, so support both.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Importing the package applies its stdout UTF-8 fix. `-m` gets it for free
# because -m imports the package first; running this file by path does not.
import scripts  # noqa: E402,F401

from back_dev_home._runtime.office_redis import load_env_file  # noqa: E402
from back_dev_home.ebeam._office_meas_hist import INDEX as _INDEX  # noqa: E402
from ops_store import OSSearch, create_client  # noqa: E402

# Sampled documents are printed WHOLE (no _source allowlist). The first run of
# this script listed six fields and so could not have seen a renamed identifier,
# which is exactly what the answer turned on.


def _adapter_verdict(raw: object) -> str:
    """What providers/office_example.py would hand the frontend for `raw`."""
    return "Yes" if str(raw or "").strip().lower() == "yes" else "No"


def _count(search: OSSearch, query: dict | None) -> int:
    return int(search.count(query=query).get("count") or 0)


def _report_index(tool: str, index: str, client: object) -> None:
    search = OSSearch(client=client, index=index)
    total = _count(search, None)
    print(f"\n[{tool}] alias={index}  total docs={total}")
    if total == 0:
        print("  (empty alias, nothing to diagnose)")
        return

    # H1. The raw stored values. A terms agg needs the .keyword subfield;
    # msr_check is mapped as text, and whether it HAS that subfield is itself
    # load-bearing: _office_msr_cd filters on msr_check.keyword, so a missing
    # subfield means tttm / pm-planning match nothing at the office either.
    print("  -- H1: stored msr_check values --")
    try:
        buckets = (
            search.aggregate({"vals": {"terms": {"field": "msr_check.keyword", "size": 20}}}, query=None)
            .get("aggregations", {})
            .get("vals", {})
            .get("buckets", [])
        )
    except Exception as exc:  # noqa: BLE001 - the failure IS the finding
        print(f"  terms on msr_check.keyword FAILED: {type(exc).__name__}: {exc}")
        print("  -> no .keyword subfield. _office_msr_cd's msr_check.keyword")
        print("     filter matches nothing, so tttm / pm-planning are empty too.")
        buckets = []
    for bucket in buckets:
        key = bucket["key"]
        verdict = _adapter_verdict(key)
        flag = "" if verdict == "Yes" or str(key).strip().lower() == "no" else "   <-- H1 CONFIRMED"
        print(f"    {key!r:20} docs={bucket['doc_count']:>8}  adapter emits {verdict!r}{flag}")
    if not buckets:
        print("    (no buckets)")

    missing_check = _count(search, {"bool": {"must_not": [{"exists": {"field": "msr_check"}}]}})
    print(f"    documents with NO msr_check field at all: {missing_check}")

    # H3. Identity. Without msr there is nothing to put in the analysis URL.
    print("  -- H3: msr identity --")
    missing_msr = _count(search, {"bool": {"must_not": [{"exists": {"field": "msr"}}]}})
    print(f"    documents with NO msr field: {missing_msr} of {total}")

    # H2. Does a "No" document still point at MinIO?
    print("  -- H2: MinIO paths vs msr_check --")
    for label, query in (
        ("has minio_pkl", {"bool": {"filter": [{"exists": {"field": "minio_pkl"}}]}}),
        ("has minio_msr", {"bool": {"filter": [{"exists": {"field": "minio_msr"}}]}}),
    ):
        print(f"    {label}: {_count(search, query)} of {total}")
    no_docs_with_pkl = _count(search, {
        "bool": {
            "filter": [{"exists": {"field": "minio_pkl"}}],
            "must_not": [{"term": {"msr_check.keyword": "Yes"}}],
        }
    })
    print(f"    minio_pkl present while msr_check is not \"Yes\": {no_docs_with_pkl}")
    if no_docs_with_pkl:
        print("    -> H2 CONFIRMED: msr_check does not decide MinIO presence.")

    # H3 detail. `msr` missing on ~1% of all documents but on the NEWEST ones
    # is the signature of an ingestion change rather than scattered bad rows,
    # and the newest documents are what a default skewvoir search returns.
    print("  -- H3 detail: when did msr stop appearing --")
    no_msr = {"bool": {"must_not": [{"exists": {"field": "msr"}}]}}
    orphan = {
        "bool": {
            "filter": [{"exists": {"field": "minio_pkl"}}],
            "must_not": [{"exists": {"field": "msr"}}],
        }
    }
    print(f"    minio_pkl present but NO msr (unreachable by the UI): {_count(search, orphan)}")
    try:
        months = (
            search.aggregate(
                {"by_month": {"date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "month",
                    "format": "yyyy-MM",
                    "min_doc_count": 1,
                }}},
                query=no_msr,
            )
            .get("aggregations", {})
            .get("by_month", {})
            .get("buckets", [])
        )
        for bucket in months[-12:]:
            print(f"      {bucket['key_as_string']}  msr-less docs={bucket['doc_count']}")
    except Exception as exc:  # noqa: BLE001 - the failure IS the finding
        print(f"    date_histogram FAILED: {type(exc).__name__}: {exc}")

    # Ground truth: whole documents, so a renamed identifier cannot hide.
    # Printed for the newest overall AND the newest msr-less one, because the
    # difference between those two documents is the whole question.
    for label, query in (("newest document", None), ("newest msr-less document", no_msr)):
        body = {"size": 1, "sort": [{"timestamp": "desc"}]}
        if query is not None:
            body["query"] = query
        hits = search.search_raw(body).get("hits", {}).get("hits", [])
        print(f"  -- {label}, EVERY field as stored --")
        if not hits:
            print("    (none)")
            continue
        hit = hits[0]
        print(f"    _id={hit.get('_id')!r}")
        for key, value in sorted(hit.get("_source", {}).items()):
            print(f"      {key} = {value!r}")


def main() -> None:
    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")
    if not os.environ.get("OPENSEARCH_HOST"):
        load_env_file("OPENSEARCH_HOST")
    client = create_client()

    for tool, index in _INDEX.items():
        _report_index(tool, index, client)

    print("\n----")
    print("읽는 법:")
    print("  H1 = msr_check 값이 'Yes'/'No' 가 아니면 어댑터가 전부 'No' 로 만듭니다.")
    print("  H2 = msr_check 가 'Yes' 가 아닌데 minio_pkl 이 있으면, msr_check 는")
    print("       MinIO 저장 여부를 뜻하지 않습니다.")
    print("  H3 = msr 필드가 없는 문서 수. 그 행은 분석 화면을 열 키가 없습니다.")
    print("결과를 docs/datatables/hitachi/meas_hist.txt 의 msr_check 절에 옮겨 적으십시오.")


if __name__ == "__main__":
    main()
