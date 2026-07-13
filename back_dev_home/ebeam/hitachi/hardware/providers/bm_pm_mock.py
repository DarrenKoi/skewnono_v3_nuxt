"""Phase 1 BM/PM mock generator.

Real office BM/PM data arrives as two pandas DataFrames per tool — completed
maintenance ("past work") and planned maintenance ("future work"). This module
fabricates the same shape deterministically from the `eqp_id` and the caller's
`anchor`, so a given tool shows the same history for a given window on every
request without any stored fixture (the same seed-from-id trick
`sem_list/data.py` uses).

`build_bm_pm_data()` is the only public entry point; it returns plain dict
records (via `DataFrame.to_dict`) plus pre-computed summary-card values, ready
for `normalizers.bm_pm_history_payload`.
"""

import hashlib
import random
from datetime import datetime, timedelta

import pandas as pd


__all__ = ["build_bm_pm_data"]


_TS_FMT = "%Y-%m-%d %H:%M"

Category = str  # "BM" | "PM"

# Free-form engineer notes of deliberately varied length — terse one-liners
# through multi-sentence write-ups — to exercise the truncate/expand UI. `{p}`
# is filled with a maintenance-part phrase so notes differ across rows.
_NOTE_TEMPLATES: list[str] = [
    "{p} 교체 완료.",
    "{p} 점검, 이상 없음.",
    "{p} 재교정.",
    "정기 점검 진행. {p} 상태 양호하며 추가 조치 불필요.",
    "{p} 누유 발견되어 교체 후 진공도 재확인함. 다음 PM 때 재점검 필요.",
    "{p} 알람 발생 이력 확인. 청소 및 재교정 후 정상화. 약 2시간 소요됨.",
    (
        "{p} 관련 간헐적 오류로 분해 점검 실시. 내부 오염 확인하여 세척하고 "
        "부품 일부 교체함. 재조립 후 빔 안정성 테스트 통과. 모니터링 지속 예정."
    ),
    (
        "고객 요청으로 긴급 대응. {p} 이상 증상 재현되지 않았으나 예방 차원에서 "
        "교체 진행. 작업 중 인접 모듈 케이블 정리도 함께 수행. 특이사항 없음."
    ),
    "{p} 펌웨어 업데이트 적용.",
    "{p} 토크 재조정 후 시운전 정상.",
]

_NOTE_PARTS: list[str] = [
    "스테이지",
    "전자총",
    "진공 펌프",
    "디텍터",
    "컬럼 정렬",
    "냉각 라인",
    "EOS 보드",
    "로드락",
    "필라멘트",
    "렌즈 코일",
]


def _seed_for(eqp_id: str) -> int:
    """Stable int seed derived from the equipment id.

    `hash()` is salted per-process, so we hash explicitly to keep the same tool
    reproducible across requests and restarts.
    """
    digest = hashlib.md5(eqp_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _fmt(dt: datetime) -> str:
    return dt.strftime(_TS_FMT)


def _make_note(rng: random.Random) -> str:
    template = rng.choice(_NOTE_TEMPLATES)
    return template.format(p=rng.choice(_NOTE_PARTS))


def build_past_frame(eqp_id: str, rng: random.Random, anchor: datetime) -> pd.DataFrame:
    """Completed BM/PM jobs in the ~150 days before `anchor`, ts-desc."""
    n_rows = rng.randint(4, 12)
    records = []
    for _ in range(n_rows):
        category: Category = "PM" if rng.random() < 0.55 else "BM"
        # Job sometime in the last ~150 days.
        starts = anchor - timedelta(
            days=rng.randint(3, 150),
            hours=rng.randint(0, 23),
            minutes=rng.choice([0, 15, 30, 45]),
        )
        # PM windows run longer than break-down maintenance.
        duration = timedelta(hours=rng.randint(4, 12) if category == "PM" else rng.randint(1, 6))
        ends = starts + duration
        # Engineers upload the note shortly after finishing.
        timestamp = ends + timedelta(minutes=rng.randint(10, 240))
        records.append(
            {
                "timestamp": _fmt(timestamp),
                "eqp_id": eqp_id,
                "category": category,
                "job_starts": _fmt(starts),
                "job_end": _fmt(ends),
                "engr_note": _make_note(rng),
            }
        )

    frame = pd.DataFrame.from_records(
        records,
        columns=["timestamp", "eqp_id", "category", "job_starts", "job_end", "engr_note"],
    )
    return frame.sort_values("timestamp", ascending=False, ignore_index=True)


def build_future_frame(eqp_id: str, rng: random.Random, anchor: datetime) -> pd.DataFrame:
    """Planned BM/PM after `anchor` — few rows (plans change), ts-desc."""
    n_rows = rng.randint(0, 3)
    records = []
    for _ in range(n_rows):
        # Planned PM dominates the forward schedule.
        category: Category = "PM" if rng.random() < 0.8 else "BM"
        starts = anchor + timedelta(
            days=rng.randint(5, 90),
            hours=rng.choice([8, 9, 13]),
        )
        ends = starts + timedelta(hours=rng.randint(4, 12) if category == "PM" else rng.randint(1, 6))
        # Plan registered recently relative to now.
        timestamp = anchor - timedelta(days=rng.randint(0, 14), hours=rng.randint(0, 23))
        records.append(
            {
                "eqp_id": eqp_id,
                "category": category,
                "job_starts": _fmt(starts),
                "job_end": _fmt(ends),
                "timestamp": _fmt(timestamp),
            }
        )

    frame = pd.DataFrame.from_records(
        records,
        columns=["eqp_id", "category", "job_starts", "job_end", "timestamp"],
    )
    if frame.empty:
        return frame
    return frame.sort_values("timestamp", ascending=False, ignore_index=True)


def _derive_cards(past: pd.DataFrame, future: pd.DataFrame) -> dict[str, object]:
    """Summary values for the metric cards, read off the generated frames."""
    # Past is already timestamp-desc; the most recent BM is the first BM row.
    past_bm = past[past["category"] == "BM"] if not past.empty else past
    last_bm = past_bm.iloc[0]["job_end"] if not past_bm.empty else "—"

    # Earliest upcoming PM = the future PM with the soonest job_starts.
    next_pm = "—"
    if not future.empty:
        future_pm = future[future["category"] == "PM"]
        if not future_pm.empty:
            next_pm = future_pm.sort_values("job_starts").iloc[0]["job_starts"]

    return {
        "last_bm": last_bm,
        "next_pm": next_pm,
        "planned_count": int(len(future)),
        "recent_count": int(len(past)),
    }


def build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict[str, object]:
    """Deterministic past/future BM/PM records + summary cards for one tool.

    `anchor` is the requested window end — the same clock the trend-chart
    mocks generate against, so BM/PM overlay markers land inside chart
    ranges. Same (eqp_id, anchor) → same data.
    """
    rng = random.Random(_seed_for(eqp_id))
    past = build_past_frame(eqp_id, rng, anchor)
    future = build_future_frame(eqp_id, rng, anchor)
    return {
        "past": past.to_dict(orient="records"),
        "future": future.to_dict(orient="records"),
        "cards": _derive_cards(past, future),
    }
