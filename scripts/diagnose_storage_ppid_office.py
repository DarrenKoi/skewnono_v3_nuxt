"""Diagnose an empty "PPID 미접속 장비" panel while the Redis hash has data.

`get_ppid_unavailable` reads ONE combined CD-SEM+HV-SEM hash and then narrows
it down in four steps. Every step drops rows silently -- a fully drained
result is still a valid, non-error `{"latest_date": ..., "rows": []}`, which
is why the panel shows its "no failing tools" empty state rather than an
error. This script prints the funnel so the draining step is obvious:

    hash fields -> latest day's IPs -> sem_list join -> tool-type -> fab_name

Two of those steps are the usual suspects:

  * sem_list join     -- office drops an IP with no sem_list match entirely
                         (the mock keeps it as an orphan row), so a format
                         mismatch in eqp_ip empties the table.
  * tool-type filter  -- `model_to_tool_type()` is an EXACT-match allowlist of
                         model codes in `_tool_specs.py`. A real model code
                         outside that list classifies as None and is dropped
                         under both tabs. The mock cannot catch this because it
                         fabricates its IPs from those same listed codes.

Run FROM THE REPO ROOT at the office (reads REDIS_* from back_dev_home/.env
exactly like the adapter does):

    .venv/bin/python -m scripts.diagnose_storage_ppid_office
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime

from back_dev_home._runtime.office_redis import redis_client
from back_dev_home.ebeam.hitachi._tool_specs import (
    SLUG_TO_TOOL_TYPE,
    TOOL_SPECS,
    model_to_tool_type,
)

try:
    from back_dev_home.ebeam.hitachi.storage.providers.office import (  # type: ignore[attr-defined]
        _PPID_HASH,
        _load_ppid_snapshots,
    )
except ModuleNotFoundError:
    raise SystemExit(
        "error: storage providers/office.py not found (it is gitignored).\n"
        "       Create it first:\n"
        "         .venv/bin/python -m scripts.sync_office_adapters storage"
    )


SAMPLE = 5


def rule(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def main() -> int:
    findings: list[str] = []

    # -- 1. the raw hash -----------------------------------------------------
    rule(f"1. Redis hash {_PPID_HASH!r}")
    client = redis_client()
    if not client.exists(_PPID_HASH):
        print(f"NOT FOUND. The adapter returns an empty snapshot for a missing key.")
        print("Check the key name against docs/datatables/storage_ppid.txt.")
        return 1

    snapshots = _load_ppid_snapshots(client)
    print(f"fields (days): {len(snapshots)}")
    if not snapshots:
        print("Hash exists but has no fields -> adapter returns latest_date='' and no rows.")
        return 1

    bad_fields = []
    for field in snapshots:
        try:
            datetime.strptime(field, "%Y%m%d")
        except ValueError:
            bad_fields.append(field)
    print(f"sample fields: {sorted(snapshots)[:SAMPLE]}")
    if bad_fields:
        print(f"!! {len(bad_fields)} field(s) are not compact %Y%m%d: {bad_fields[:SAMPLE]}")
        print("   The adapter does max(fields) then strptime -- a stray field can")
        print("   either win max() and raise, or mis-order the 'latest' day.")
        findings.append("hash has non-%Y%m%d fields")

    # -- 2. the latest day ---------------------------------------------------
    rule("2. Latest day's IP list")
    latest_key = max(snapshots)
    latest_ips = snapshots[latest_key]
    unique_ips = list(dict.fromkeys(latest_ips))
    print(f"latest field : {latest_key}")
    print(f"IPs that day : {len(latest_ips)} ({len(unique_ips)} unique)")
    print(f"sample       : {unique_ips[:SAMPLE]}")
    if not unique_ips:
        print("!! The latest day's list is EMPTY -> panel shows a date but no rows.")
        print("   A day written before the collector ran would look like this;")
        print("   the adapter always takes max(field), even if that day is blank.")
        findings.append(f"latest day {latest_key} has an empty IP list")
        return report(findings)

    # -- 3. the sem_list join ------------------------------------------------
    rule("3. Join against sem_list on eqp_ip")
    from back_dev_home.sem_list.data import get_sem_list

    sem_rows = get_sem_list()
    sem_by_ip = {row["eqp_ip"]: row for row in sem_rows}
    print(f"sem_list rows: {len(sem_rows)}")
    print(f"sample sem_list eqp_ip: {[r['eqp_ip'] for r in sem_rows[:SAMPLE]]}")

    matched = [ip for ip in unique_ips if ip in sem_by_ip]
    unmatched = [ip for ip in unique_ips if ip not in sem_by_ip]
    print(f"\nmatched   : {len(matched)}/{len(unique_ips)}")
    print(f"unmatched : {len(unmatched)}  {unmatched[:SAMPLE]}")

    if unmatched:
        # Whitespace / case are the cheap explanations; check before blaming data.
        stripped = {ip.strip(): ip for ip in sem_by_ip}
        recoverable = [ip for ip in unmatched if ip.strip() in stripped and ip not in sem_by_ip]
        if recoverable:
            print(f"!! {len(recoverable)} would match after .strip() -> whitespace mismatch.")
            findings.append("eqp_ip join needs whitespace normalization")
    if not matched:
        print("\n!! NOTHING matched sem_list. Office mode drops unmatched IPs")
        print("   outright, so every row dies here and the panel renders empty.")
        findings.append("no latest-day IP matches any sem_list eqp_ip")
        return report(findings)

    # -- 4. the tool-type filter --------------------------------------------
    rule("4. Tool-type classification (model_to_tool_type)")
    print(f"allowlist: {sorted(m for spec in TOOL_SPECS.values() for m in spec['eqp_models'])}\n")

    models = Counter(str(sem_by_ip[ip]["eqp_model_cd"]) for ip in matched)
    unknown_total = 0
    for model, count in models.most_common():
        tool_type = model_to_tool_type(model)
        flag = "" if tool_type else "   <-- NOT IN ALLOWLIST, dropped from both tabs"
        if not tool_type:
            unknown_total += count
        print(f"  {model!r:>14} x{count:<4} -> {tool_type}{flag}")

    if unknown_total:
        print(f"\n!! {unknown_total}/{len(matched)} matched IPs classify as None.")
        print("   Fix by adding the real model codes to TOOL_SPECS in")
        print("   back_dev_home/ebeam/hitachi/_tool_specs.py (the frontend's")
        print("   classifyToolType() is prefix-based, so it already accepts them).")
        findings.append(f"{unknown_total} IPs have model codes outside TOOL_SPECS")

    # -- 5. per-tab outcome --------------------------------------------------
    rule("5. Rows the API will actually return")
    for slug, tool_type in SLUG_TO_TOOL_TYPE.items():
        kept = [ip for ip in matched if model_to_tool_type(str(sem_by_ip[ip]["eqp_model_cd"])) == tool_type]
        fabs = Counter(str(sem_by_ip[ip]["fab_name"]) for ip in kept)
        print(f"\n/api/{slug}/ppid-unavailable  latest_date={latest_key}  rows={len(kept)}")
        if kept:
            print(f"  fab_name spread: {dict(fabs)}")
            print("  (the page requests ONE fab via ?fab_name=; a fab absent above shows empty)")
        else:
            print("  EMPTY -- this tab renders the 'no failing tools' state.")
            findings.append(f"{slug} keeps 0 rows after the tool-type filter")

    return report(findings)


def report(findings: list[str]) -> int:
    rule("VERDICT")
    if not findings:
        print("No draining step found: the adapter should be returning rows.")
        print("If the panel is still empty, compare the fab the page requests")
        print("against the fab_name spread in step 5.")
        return 0
    for item in findings:
        print(f"  - {item}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
