"""화면별 OpenSearch 왕복 실태를 활동 로그에서 집계합니다.

`_logging/os_timing.py` 가 요청마다 남기는 네 필드를 path 별로 묶어,
"한 화면이 왕복을 몇 번 하는가" 와 "그 시간이 횟수에 있는가 느린 질의 하나에
있는가" 를 한 표로 보여 줍니다. msearch 도입 여부는 이 표로 판정합니다.

    python -m scripts.measure_opensearch_roundtrips
    python scripts/measure_opensearch_roundtrips.py --environment production
    python scripts/measure_opensearch_roundtrips.py --days 1 --limit 50

alias 는 `--environment` 가 정하며, 기본값은 SKEWNONO_LOG_ENV 입니다.
어느 alias 로 나가고 있는지는 `GET /api/health/logging` 이 알려 줍니다.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import scripts  # noqa: E402,F401  (applies the stdout UTF-8 fix)

from ops_index_mgmt.skewnono_logging import (  # noqa: E402
    create_skewnono_client,
    target_for,
)
from ops_store import OSSearch  # noqa: E402


def build_query(days: int, limit: int) -> dict[str, Any]:
    """path 별 왕복 통계. exists 필터가 계측 이전 문서를 걸러 냅니다."""
    return {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"event": "request"}},
                    {"exists": {"field": "opensearch_query_count"}},
                    {"range": {"@timestamp": {"gte": f"now-{days}d"}}},
                ]
            }
        },
        "aggs": {
            "by_path": {
                "terms": {
                    "field": "path",
                    "size": limit,
                    "order": {"max_trips": "desc"},
                },
                "aggs": {
                    "max_trips": {"max": {"field": "opensearch_query_count"}},
                    "avg_trips": {"avg": {"field": "opensearch_query_count"}},
                    "avg_total_ms": {"avg": {"field": "opensearch_total_ms"}},
                    "avg_slowest_ms": {"avg": {"field": "opensearch_slowest_ms"}},
                    "avg_latency_ms": {"avg": {"field": "latency_ms"}},
                    "slowest_index": {
                        "terms": {"field": "opensearch_slowest_index", "size": 1}
                    },
                },
            }
        },
    }


_HEADER = (
    f"{'path':<42}{'n':>6}{'trips_max':>10}{'trips_avg':>10}"
    f"{'os_ms':>8}{'slowest':>9}{'req_ms':>8}  slowest_index"
)


def format_rows(buckets: list[dict[str, Any]]) -> list[str]:
    rows = []
    for bucket in buckets:
        top = bucket["slowest_index"]["buckets"]
        rows.append(
            f"{bucket['key'][:42]:<42}"
            f"{bucket['doc_count']:>6}"
            f"{bucket['max_trips']['value']:>10.0f}"
            f"{bucket['avg_trips']['value']:>10.1f}"
            f"{bucket['avg_total_ms']['value']:>8.0f}"
            f"{bucket['avg_slowest_ms']['value']:>9.0f}"
            f"{bucket['avg_latency_ms']['value']:>8.0f}"
            f"  {top[0]['key'] if top else '-'}"
        )
    return rows


_VERDICT = """
판정 기준 (trips = 한 요청이 쓴 OpenSearch 왕복 횟수)
  trips_max 가 1~2                     -> msearch 가 없앨 왕복이 없습니다. 종결.
  trips 는 큰데 slowest 가 os_ms 와 비슷 -> 느린 질의 하나가 지배합니다.
                                          배치가 아니라 그 질의를 고칠 일입니다.
  trips 가 크고 slowest 가 os_ms 보다 훨씬 작으며
  os_ms 가 req_ms 의 큰 몫              -> 이때만 msearch 가 후보로 남습니다.

세 번째가 나와도 채택이 아니라 검토 재개입니다. msearch 는 하위 요청의 실패를
HTTP 200 본문에 담아 돌려주므로 NotFoundError 매핑이 멈추고, 데이터 문제가
502 가 아니라 503 으로 나갑니다. 그 비용은 이 표와 무관하게 그대로입니다.
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--environment",
        default=os.environ.get("SKEWNONO_LOG_ENV", "local"),
        choices=("local", "production"),
        help="읽을 로그 alias. 기본값은 SKEWNONO_LOG_ENV, 없으면 local 입니다.",
    )
    parser.add_argument("--days", type=int, default=7, help="조회 기간 (기본 7일)")
    parser.add_argument("--limit", type=int, default=30, help="표시할 path 수")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")

    alias = target_for(args.environment).alias
    print(f"alias={alias}  days={args.days}")

    try:
        search = OSSearch(client=create_skewnono_client(), index=alias)
        result = search.search_raw(build_query(args.days, args.limit))
    except Exception as exc:
        raise SystemExit(
            f"OpenSearch 조회 실패: {type(exc).__name__}: {exc}\n"
            "OPENSEARCH_HOST/USER/PASSWORD 가 환경 또는 back_dev_home/.env 에\n"
            "있는지, alias 이름이 맞는지 확인하십시오. 실제로 쓰이는 alias 는\n"
            "    GET /api/health/logging\n"
            "이 target.alias 로 알려 줍니다."
        ) from exc

    buckets = result["aggregations"]["by_path"]["buckets"]
    if not buckets:
        print()
        print(f"{alias} 에 opensearch_query_count 를 가진 request 행이 없습니다.")
        print("확인 순서:")
        print("  1. GET /api/health/logging 이 installed=true 이고 이 alias 인가")
        print("  2. 계측을 배포한 뒤에 무거운 화면을 실제로 열었는가")
        print("  3. 매핑이 반영되었는가 (python -m ops_index_mgmt.skewnono_logging)")
        return 0

    print()
    print(_HEADER)
    print("-" * len(_HEADER))
    for row in format_rows(buckets):
        print(row)
    print(_VERDICT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
