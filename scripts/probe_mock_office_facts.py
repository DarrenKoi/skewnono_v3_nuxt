"""Settle the OFFICE-VERIFY questions left by the mock/office drift sweep.

The 2026-08-10 sweep of all 31 mock/office_example pairs fixed what could be
decided from the code. Five questions could not be: they are facts about the
real data that home cannot see. Each one is currently an assumption sitting in
a provider, and each is recorded in `.scratch/mock-office-drift/`.

This script answers all five in one run, so the office trip is one command
instead of five ad-hoc queries.

    [1] msr_check vocabulary + meastime presence   -> issue 04
        Is `meastime` really absent unless msr_check == "Yes"? And is the
        stored value "Yes" or "Y"? office_example.py compares
        `.lower() == "yes"`, so a stored "Y" would flip EVERY row to "No"
        without raising anything.

    [2] fail_ratio presence                        -> issue 03
        avg_fail_ratio now divides by the group's doc_count, treating a
        missing value as 0.0 (what the row path already does). That is only
        interesting if the field ever goes missing.

    [3] lot_cd catalog overlap                     -> issues 01, 02
        M-fab was chosen to win an overlapping lot_cd. If the two catalogs
        never overlap, that decision is moot and only the self-contradiction
        mattered.

    [4] worst drift-sigma distribution             -> issue 05
        The mock's `health` and the office's are on different scales. Whether
        that is worth unifying depends on where real MSRs actually sit.

    [5] blank `mp_image_name 01`                   -> issue 07
        Never observed, thought possible. The adapter now derives the image
        trio from one list and logs rows whose raw columns disagreed; this
        stage counts them over a sample.

Run FROM THE REPO ROOT at the office:

    .venv/bin/python -m scripts.probe_mock_office_facts

    # skip the slow stage (it fetches pickles from MinIO)
    .venv/bin/python -m scripts.probe_mock_office_facts --msr-sample 0

    # widen the window / sample, or look at one tool family
    .venv/bin/python -m scripts.probe_mock_office_facts --days 180 --msr-sample 50
    .venv/bin/python -m scripts.probe_mock_office_facts --tool-type hv-sem

Whatever this proves belongs in TWO places (CLAUDE.md): the relevant
`docs/datatables/*.txt` AND the feature's mock. Mark each fact
`office 확인 YYYY-MM-DD`, and close the matching issue file.

Read-only: aggregations, Redis GETs and MinIO object reads only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Make `back_dev_home` importable however this file was started. `-m` puts the
# working directory on sys.path and works from the repo root; running the file
# by path puts scripts/ there instead and fails on the first import below.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Importing the package applies its stdout UTF-8 fix. `-m` gets it for free;
# running this file by path does not, and would then die on the ANSI code page.
import scripts  # noqa: E402,F401

from back_dev_home._runtime.office_redis import load_env_file  # noqa: E402
from back_dev_home.ebeam._office_meas_hist import (  # noqa: E402
    INDEX,
    TIME_FIELD,
    aggregate,
    device_desc,
    fetch_hits,
    query,
    r3_device_grp,
    text,
)

DEFAULT_DAYS = 90
DEFAULT_MSR_SAMPLE = 20

# Percent of a group; keeps the "is this rare or systematic" read one glance.
def _pct(part: int, whole: int) -> str:
    return f"{100.0 * part / whole:6.2f}%" if whole else "     - "


def _rule(title: str) -> None:
    print(f"\n{'-' * 72}\n{title}\n{'-' * 72}")


def _window(days: int) -> dict[str, Any]:
    return query([{"range": {TIME_FIELD: {"gte": f"now-{days}d"}}}])


def stage_meastime(tool_type: str, days: int) -> None:
    """[1] msr_check vocabulary and meastime presence (issue 04)."""
    _rule(f"[1] {INDEX[tool_type]} - msr_check 어휘와 meastime 결측 (issue 04)")

    aggs = {
        # timestamp is the range field, so every in-scope doc has one: this is
        # an exact document count, which is what DOC_COUNT_AGG relies on.
        "docs": {"value_count": {"field": TIME_FIELD}},
        "with_meastime": {"value_count": {"field": "meastime"}},
        "by_check": {
            "terms": {"field": "msr_check.keyword", "size": 10},
            "aggs": {"with_meastime": {"value_count": {"field": "meastime"}}},
        },
    }
    result = aggregate(INDEX[tool_type], aggs, _window(days))

    docs = int(result.get("docs", {}).get("value") or 0)
    with_meas = int(result.get("with_meastime", {}).get("value") or 0)
    if not docs:
        print(f"  최근 {days}일 문서 0건 - 창을 넓혀 보십시오 (--days).")
        return

    print(f"  문서            {docs:>10,}")
    print(f"  meastime 있음   {with_meas:>10,}   ({_pct(with_meas, docs)})")
    print(f"  meastime 결측   {docs - with_meas:>10,}   ({_pct(docs - with_meas, docs)})")

    print(f"\n  {'msr_check':<12} {'문서':>10} {'meastime 있음':>14} {'결측':>10}")
    print(f"  {'-' * 12} {'-' * 10} {'-' * 14} {'-' * 10}")
    buckets = result.get("by_check", {}).get("buckets", []) or []
    values = []
    for bucket in buckets:
        key = text(bucket.get("key"))
        count = int(bucket.get("doc_count") or 0)
        has = int(bucket.get("with_meastime", {}).get("value") or 0)
        values.append(key)
        print(f"  {key:<12} {count:>10,} {has:>14,} {count - has:>10,}")

    # The comparison office_example.py actually performs.
    accepted = [v for v in values if v.strip().lower() == "yes"]
    rejected = [v for v in values if v.strip().lower() != "yes"]
    print(f"\n  관측된 msr_check 값: {values or '(없음)'}")
    if not values:
        # A terms agg on a field the mapping does not have returns zero buckets
        # and no error, which looks identical to "no documents". Say so instead
        # of reporting it as a vocabulary problem.
        print(
            "  *** 버킷이 0개입니다. 문서는 있는데 버킷이 없다면 원인은 값이\n"
            "      아니라 필드입니다 - msr_check.keyword 가 매핑에 없으면\n"
            "      terms 집계가 오류 없이 빈 결과를 냅니다. 매핑을 먼저\n"
            "      확인하십시오 (아래 'yes' 판정은 의미가 없습니다)."
        )
    elif not accepted:
        print(
            "  *** 경고: 어느 값도 .lower() == 'yes' 가 아닙니다.\n"
            "      meas_hist/providers/office_example.py 의 msr_check 정규화가\n"
            "      모든 행을 'No' 로 뒤집고 있습니다 - 오류 없이 조용히 틀립니다.\n"
            f"      실제 값 {values} 를 받도록 그 비교를 고치십시오."
        )
    elif rejected:
        print(f"  -> 'Yes' 로 인정되지 않는 값: {rejected} (계약은 Yes/No 만 압니다)")

    # The rule issue 04 is built on.
    holes = [
        text(b.get("key"))
        for b in buckets
        if text(b.get("key")).strip().lower() == "yes"
        and int(b.get("with_meastime", {}).get("value") or 0) != int(b.get("doc_count") or 0)
    ]
    if holes:
        print(
            "  -> msr_check == 'Yes' 인데 meastime 이 없는 문서가 있습니다.\n"
            "     'Yes 이면 meastime 존재' 규칙이 깨집니다 - issue 04 재검토."
        )
    elif with_meas == docs:
        print(
            "  -> 결측이 하나도 없습니다. doc_count 와 value_count(meastime) 가\n"
            "     같은 값이므로 issue 04 의 분리는 방어로만 남습니다."
        )
    else:
        print("  -> 'Yes 이면 meastime 존재' 규칙과 일치합니다 (issue 04 확정).")


def stage_fail_ratio(tool_type: str, days: int) -> None:
    """[2] fail_ratio presence (issue 03)."""
    _rule(f"[2] {INDEX[tool_type]} - fail_ratio 결측 (issue 03)")

    aggs = {
        "docs": {"value_count": {"field": TIME_FIELD}},
        "with_ratio": {"value_count": {"field": "fail_ratio"}},
        "sum_ratio": {"sum": {"field": "fail_ratio"}},
        "avg_ratio": {"avg": {"field": "fail_ratio"}},
    }
    result = aggregate(INDEX[tool_type], aggs, _window(days))

    docs = int(result.get("docs", {}).get("value") or 0)
    with_ratio = int(result.get("with_ratio", {}).get("value") or 0)
    if not docs:
        print(f"  최근 {days}일 문서 0건 - 창을 넓혀 보십시오 (--days).")
        return

    print(f"  문서              {docs:>10,}")
    print(f"  fail_ratio 있음   {with_ratio:>10,}   ({_pct(with_ratio, docs)})")
    print(f"  fail_ratio 결측   {docs - with_ratio:>10,}   ({_pct(docs - with_ratio, docs)})")

    # The two candidate denominators, side by side.
    total = float(result.get("sum_ratio", {}).get("value") or 0.0)
    os_avg = float(result.get("avg_ratio", {}).get("value") or 0.0)
    ours = total / docs if docs else 0.0
    print(f"\n  sum / doc_count      {ours:8.4f}   <- 어댑터가 쓰는 값 (결측 = 0.0)")
    print(f"  OpenSearch avg       {os_avg:8.4f}   <- 결측을 뺀 값")
    if with_ratio == docs:
        print("  -> 결측 없음. 두 값이 같으므로 issue 03 의 수정은 방어로만 남습니다.")
    else:
        print(
            "  -> 결측이 존재합니다. 행 경로가 결측을 0.0 으로 강제하므로\n"
            "     어댑터의 sum/doc_count 가 '표에 보이는 것의 평균' 입니다."
        )


def stage_catalog_overlap() -> None:
    """[3] Do the two lot_cd catalogs overlap at all? (issues 01, 02)."""
    _rule("[3] lot_cd 카탈로그 겹침 - device_desc vs r3_device_grp (issue 01, 02)")

    hvm = device_desc()
    r3 = r3_device_grp()
    both = sorted(set(hvm) & set(r3))

    print(f"  device_desc (M계열)   {len(hvm):>8,} lot_cd")
    print(f"  r3_device_grp (R3)    {len(r3):>8,} lot_cd")
    print(f"  양쪽 모두             {len(both):>8,} lot_cd")

    if not both:
        print(
            "\n  -> 겹치는 lot_cd 가 없습니다. M계열 우선 결정은 실질적으로\n"
            "     무의미하고, 고친 것 중 의미가 있는 부분은 device_statistics 의\n"
            "     자기모순 정리뿐입니다 (issue 01)."
        )
        return

    print(f"\n  겹치는 lot_cd 예시 (최대 10개): {both[:10]}")
    print(f"  {'lot_cd':<10} {'M계열 fac_id':<14} {'M계열 tech_nm':<16} {'R3 prod_catg_cd'}")
    print(f"  {'-' * 10} {'-' * 14} {'-' * 16} {'-' * 16}")
    for lot_cd in both[:10]:
        meta = hvm.get(lot_cd, {})
        print(
            f"  {lot_cd:<10} {text(meta.get('fac_id')):<14} "
            f"{text(meta.get('tech_nm')):<16} {text(r3.get(lot_cd))}"
        )
    print(
        "\n  -> 겹침이 실재합니다. M계열 우선(tech_nm 이 이김)이 적용됩니다 -\n"
        "     위 표의 R3 prod_catg_cd 값들은 화면에서 버려집니다. 그것이\n"
        "     의도인지 한 번 더 확인하십시오 (issue 01, 02)."
    )


def stage_msr_sample(tool_type: str, days: int, sample: int) -> None:
    """[4][5] Drift distribution and blank 01, over a pickle sample."""
    _rule(f"[4][5] MSR 표본 {sample}건 - drift 분포와 빈 01 (issue 05, 07)")
    if sample <= 0:
        print("  --msr-sample 0 - 건너뜁니다.")
        return

    # Imported here: this is the only stage that needs MinIO, and a host
    # without a MinIO config should still get stages 1-3.
    from back_dev_home.msr_file.providers import office_example as msr_office

    hits = fetch_hits(
        INDEX[tool_type],
        _window(days),
        size=sample,
        sort=[{TIME_FIELD: {"order": "desc"}}],
        source=["msr"],
    )
    msrs = [text(hit.get("msr")) for hit in hits]
    msrs = [m for m in msrs if m]
    if not msrs:
        print(f"  최근 {days}일에 MSR 이 없습니다.")
        return

    worsts: list[float] = []
    healths: list[float] = []
    blank_first = 0
    count_mismatch = 0
    rows_seen = 0
    failed = 0

    for msr in msrs:
        # One bad pickle must not end the run (scripts/README.md rule 7).
        try:
            response = msr_office.get_msr_file(msr)
        except Exception as exc:  # noqa: BLE001 - 수집은 계속합니다
            failed += 1
            print(f"  {msr}: {type(exc).__name__}: {exc}")
            continue
        if response is None:
            failed += 1
            continue

        healths.append(float(response["health"]))
        drifts = [float(s["drift_sigma"]) for s in response["fdc_params"]]
        worsts.append(max(drifts) if drifts else 0.0)

        for row in response["rows"]:
            rows_seen += 1
            names = row["mp_image_names"]
            if names and not names[0]:
                blank_first += 1
            if row["no_of_mp_image"] != len(names):
                count_mismatch += 1

    ok = len(worsts)
    print(f"  읽은 MSR {ok}/{len(msrs)}  (실패 {failed})  행 {rows_seen:,}")
    if not ok:
        print("  -> 표본을 하나도 읽지 못했습니다. MinIO 설정을 확인하십시오.")
        return

    ordered = sorted(worsts)
    def _q(frac: float) -> float:
        return ordered[min(len(ordered) - 1, int(frac * len(ordered)))]

    print("\n  worst drift_sigma 분포 (issue 05)")
    print(f"    min {ordered[0]:6.2f}   p50 {_q(0.50):6.2f}   p90 {_q(0.90):6.2f}"
          f"   max {ordered[-1]:6.2f}")
    print(f"    health  min {min(healths):5.3f}   max {max(healths):5.3f}")
    print(
        "    -> mock 은 health 를 제곱 분포로 뽑습니다. 위 분포와 크게 다르면\n"
        "       mock 쪽 분포를 손볼 값어치가 있습니다 (issue 05)."
    )

    print("\n  이미지 컬럼 (issue 07)")
    print(f"    빈 01 을 가진 행        {blank_first:,}")
    print(f"    no_of_mp_image 불일치   {count_mismatch:,}")
    if blank_first or count_mismatch:
        print(
            "    -> 관측됐습니다. OFFICE-VERIFY 를 office 확인 으로 승격하고\n"
            "       docs/datatables/msr_file_pickle.txt 를 갱신하십시오."
        )
    else:
        print("    -> 이 표본에는 없습니다. OFFICE-VERIFY 로 남깁니다.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="mock/office 드리프트 정리에서 남은 OFFICE-VERIFY 5건을 실측합니다.",
    )
    parser.add_argument("--tool-type", default="cd-sem", choices=sorted(INDEX))
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"집계 창 (기본 {DEFAULT_DAYS}일)")
    parser.add_argument("--msr-sample", type=int, default=DEFAULT_MSR_SAMPLE,
                        help=f"pickle 을 읽을 MSR 수, 0 이면 생략 (기본 {DEFAULT_MSR_SAMPLE})")
    args = parser.parse_args()

    # Evidence the process started, before anything slow (README rule 4).
    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")
    print(f"tool_type={args.tool_type}  days={args.days}  msr_sample={args.msr_sample}")

    # Unconditionally, so one missing variable does not drop the rest of the
    # file to defaults (README rule 5).
    load_env_file("OPENSEARCH_HOST")

    stages = (
        ("1", lambda: stage_meastime(args.tool_type, args.days)),
        ("2", lambda: stage_fail_ratio(args.tool_type, args.days)),
        ("3", stage_catalog_overlap),
        ("4/5", lambda: stage_msr_sample(args.tool_type, args.days, args.msr_sample)),
    )

    failures = 0
    for name, run in stages:
        try:
            run()
        except Exception as exc:  # noqa: BLE001 - 한 단계 실패가 나머지를 막지 않습니다
            failures += 1
            print(f"\n  [{name}] 실패: {type(exc).__name__}: {exc}")
            print("  이 단계만 건너뛰고 계속합니다.")

    _rule("정리")
    print("  확인된 사실은 두 곳에 기록합니다 (CLAUDE.md):")
    print("    docs/datatables/<source>.txt  AND  해당 feature 의 providers/mock.py")
    print("  각 항목에 'office 확인 YYYY-MM-DD' 를 붙이고,")
    print("  .scratch/mock-office-drift/issues/ 의 해당 파일을 닫으십시오.")
    if failures:
        print(f"\n  단계 {failures}개가 실패했습니다 - 위 메시지를 보십시오.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
