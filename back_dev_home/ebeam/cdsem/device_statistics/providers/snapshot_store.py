"""주차 스냅샷의 집(home) 구현 — 디스크에 JSON 을 씁니다.

사무실은 같은 payload 를 MinIO 에 올립니다(``office_example.py`` 의
``write_weekly_snapshot``). ``msr_image`` 의 ``DiskImageCache`` /
``MinioImageCache`` 분기와 같은 형태입니다.

**읽기 경로는 의도적으로 갈라집니다 — 이 모듈이 쓴 파일을 화면이 읽지
않습니다.** 사무실 어댑터는 과거 주차를 스냅샷에서 읽고 스냅샷이 없는 주차는
응답에서 빼지만(datatable 문서 읽기 규칙 3), mock 의
``get_weekly_trend_data`` 는 지금처럼 **모든 주차를 라이브로 계산**합니다.
새 체크아웃에는 스냅샷이 하나도 없으므로 그 규칙을 집에 옮기면 트렌드가 8개
대신 1개 날짜만 돌려주고, 월요일이 여덟 번 지날 때까지 차트가 비어 있게
됩니다. 결정론적 seed 덕분에 라이브 계산은 같은 날짜에 늘 같은 값을 줍니다.

따라서 집에서 이 모듈이 검증하는 것은 **payload 를 만들어 남기는 데까지**이며,
그것이 사무실에서 MinIO 에 올라갈 바로 그 payload 입니다.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from back_dev_home.ebeam.cdsem.device_statistics.providers.statistics import (
    RCP_BUCKETS,
    _trend_dates,
    get_weekly_trend_data,
)

logger = logging.getLogger("skewnono.scheduler")

KST = timezone(timedelta(hours=9))

# YYYY-MM-DD.json 인 파일만 스냅샷으로 취급합니다. sweep 이 같은 폴더의 다른
# 파일을 지우지 않도록 하는 유일한 방어선입니다.
_SNAPSHOT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def snapshot_dir() -> Path:
    """``SKEWNONO_WEEKLY_TREND_DIR`` 또는 기본 ``var/weekly_trend``.

    환경변수를 매번 읽습니다 — 모듈 로드 시점에 고정하면 테스트가
    monkeypatch 로 경로를 바꿀 수 없습니다.
    """
    raw = os.environ.get("SKEWNONO_WEEKLY_TREND_DIR", "").strip()
    return Path(raw) if raw else Path("var/weekly_trend")


def _current_week() -> str:
    """mock 이 '이번 주차'로 부르는 날짜.

    ``_trend_dates`` 와 같은 앵커(BASE_TIME)를 씁니다. 오늘 날짜로 계산하면
    트렌드가 절대 돌려주지 않는 주차 이름으로 파일이 생깁니다.
    """
    return _trend_dates(points=1, interval_days=7)[-1]


def build_weekly_snapshot(date_key: str | None = None) -> dict[str, Any]:
    """한 주차 payload — **모든 device 의 summary 만**.

    ``*_rcp_info`` 는 일부러 담지 않습니다. recipe 단위 상세는 device 4000개 ×
    버킷 4개 × recipe 100~200개가 되어 매주 GB 급이 되는데, 그것을 읽는 화면이
    없습니다(docs/datatables/device_statistics_weekly_trend.txt).
    """
    anchor = date_key or _current_week()
    # points=1 — a snapshot only needs one week. Across 4000 lots the mock
    # costs ~4.6s per week; asking for 8 (to reuse _trend_dates' window) would
    # make every write 8x slower for the seven buckets we'd throw away.
    # points=1 lands on the same latest-Monday anchor _current_week() computes.
    trend = get_weekly_trend_data(None, points=1, interval_days=7, include_recipes=False)
    bucket = trend.get(anchor)
    if bucket is None:
        # 드문 예외가 아니라 **``date_key`` 를 넘긴 모든 호출의 유일한 경로**
        # 입니다. 위에서 ``points=1`` 로 받으므로 ``trend`` 에는 이번 주차 하나만
        # 들어 있고, 이번 주차가 아닌 이름은 전부 여기로 옵니다. 즉 집에서
        # ``write_weekly_snapshot("2026-06-01")`` 은 6월 이름표를 단 이번 주차
        # 데이터를 씁니다.
        #
        # 집에서는 이 파일을 읽는 화면이 없으므로(모듈 docstring — mock 은 트렌드를
        # 매번 라이브로 계산합니다) 그대로 둡니다. 사무실 어댑터는 지난 주차를
        # 실제 스냅샷에서 읽으므로 같은 대체를 하면 안 됩니다.
        bucket = trend[next(reversed(trend))]
    return {
        "date": anchor,
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "summaries": {name: list(bucket[f"{name}_summary"]) for name in RCP_BUCKETS},
    }


def write_weekly_snapshot(date_key: str | None = None) -> str:
    """payload 를 파일로 남기고 그 경로를 돌려줍니다. 같은 주차를 다시 불러도
    덮어쓰므로 재실행에 안전합니다."""
    payload = build_weekly_snapshot(date_key)
    directory = snapshot_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{payload['date']}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "device_statistics: wrote weekly snapshot %s (%d lots)",
        path, len(payload["summaries"].get("all", [])),
    )
    return str(path)


def _snapshot_dates(directory: Path) -> list[str]:
    return sorted(
        p.stem for p in directory.glob("*.json") if _SNAPSHOT_NAME.match(p.stem)
    )


def sweep_weekly_snapshots(keep_weeks: int = 26) -> int:
    """가장 최근 ``keep_weeks`` 주차만 남기고 지웁니다. 지운 개수를 돌려줍니다.

    **key 의 날짜로 판단하며 파일의 mtime 으로 하지 않습니다.** 놓친 주를 메우려
    ``write_weekly_snapshot("2026-06-01")`` 을 다시 부르면 그 파일의 mtime 은
    오늘이 됩니다. mtime 기준이면 그 오래된 백필을 남기고 정상적인 최근 것을
    지웁니다.
    """
    directory = snapshot_dir()
    if not directory.is_dir():
        return 0
    dates = _snapshot_dates(directory)
    doomed = dates[:-keep_weeks] if keep_weeks > 0 else dates
    removed = 0
    for stem in doomed:
        try:
            (directory / f"{stem}.json").unlink()
            removed += 1
        except OSError:
            logger.exception("failed to delete weekly snapshot %s", stem)
    logger.info("device_statistics: swept %d weekly snapshots", removed)
    return removed


__all__ = [
    "build_weekly_snapshot",
    "snapshot_dir",
    "sweep_weekly_snapshots",
    "write_weekly_snapshot",
]
