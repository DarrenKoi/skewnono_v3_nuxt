"""Phase 1 BM/PM mock generator.

Office counterpart — schema of record: `docs/datatables/hardware_bm_pm.txt`.
The two sides are TWO OPENSEARCH INDICES, queried once each per tool (an earlier
version of this docstring called them "two pandas DataFrames", which described
the shape after loading, not the source):

    fab_inform_notes        실적 — maintenance that HAPPENED.
                            window down_dt ~ equp_dt, time_field = down_dt,
                            past 180d. Carries the three free-form engineer
                            notes (note_comment / zzproblem / hltext) that are
                            the substance of the tab.
    tool_maintenance_plan   계획 — maintenance that is SCHEDULED.
                            window tool_start_tm ~ tool_end_tm,
                            time_field = tool_start_tm, next 90d.

THE NAMING TRAP between them, worth knowing before touching any join: the fab
field is `fab_name` on the past index and `det_fac_id` on the plan index — same
values, different names — while `fac_id` exists on BOTH under one name and is
the WRONG granularity. The field that matches by name doesn't match by meaning,
and vice versa. Likewise the event field is `eq_event` (past) vs `event_name`
(plan), shown as one column.

This module fabricates the same shape deterministically from the `eqp_id` and
the caller's `anchor`, so a given tool shows the same history for a given window
on every request without any stored fixture (the same seed-from-id trick
`sem_list/data.py` uses).

`build_bm_pm_data()` is the only public entry point; it returns plain dict
records (via `DataFrame.to_dict`) plus pre-computed summary-card values, ready
for `normalizers.bm_pm_history_payload`. The values both providers must agree
on — timestamp format, BM/PM classification, merged note, summary cards — come
from `_shared.py`, so the office adapter derives them identically.
"""

import random
from datetime import datetime, timedelta

import pandas as pd

from back_dev_home.ebeam.hardware.providers._siblings import seed_for
from back_dev_home.ebeam.hardware.providers.bm_pm._shared import (
    classify_category,
    derive_cards,
    fmt_dt,
    merge_notes,
)


__all__ = ["build_bm_pm_data"]

# Raw maintenance-type values in the office's own dirty shapes — qualified,
# sometimes empty, sometimes neither BM nor PM. Generating clean "BM"/"PM"
# here would hide the classifier (and the ""-category row) until the office.
_PM_TYPES: list[str] = ["PM2", "PM-정기", "PM4", "", "", "기타"]
_EQ_EVENTS: list[str] = [
    "PM_REGULAR", "PM_WEEKLY", "BM_ALIGN", "BM_COLUMN", "EQ_CHECK",
]
_PLAN_EVENTS: list[str] = [
    "PM_REGULAR", "PM_QUARTER", "BM_PLAN", "EQ_UPGRADE",
]

_LOT_CDS: list[str] = ["CG5000", "CG6300", "CG6380"]
_RECIPE_IDS: list[str] = [
    "CD_BIAS_A01", "DAILY_MATCH", "DUMMY_RECIPE_001", "M16_CDMEAS_01",
]
_WORK_USERS: list[str] = ["K12345", "K23456", "K34567", "P90121"]

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

_PROBLEM_TEMPLATES: list[str] = [
    "{p} 알람 반복 발생.",
    "{p} 관련 계측값 산포 증가.",
    "",
    "{p} 진공도 미달로 측정 중단됨. 재현성 확인 필요.",
    "",
    "{p} 이상음 발생. 초기 점검에서는 원인 미확인.",
]

_HIGHLIGHT_TEMPLATES: list[str] = [
    "",
    "다음 PM 때 {p} 재점검 필요.",
    "",
    "{p} 예비 부품 확보 요청함.",
    "동일 증상 재발 시 벤더 콜 예정.",
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

_WORK_ITEMS: list[str] = [
    "정기 PM — 컬럼 청소 및 정렬 확인",
    "진공 펌프 오버홀",
    "디텍터 교체 및 재교정",
    "EOS 보드 펌웨어 업그레이드",
    "스테이지 벨트 점검",
]


def _fill(rng: random.Random, templates: list[str]) -> str:
    template = rng.choice(templates)
    return template.format(p=rng.choice(_NOTE_PARTS)) if template else ""


def _lot_id(rng: random.Random) -> str:
    # Same shape recipe_tat's mock builds: lot code + a 6-digit run number.
    return f"{rng.choice(_LOT_CDS)}{rng.randint(1, 999999):06d}"


def build_past_frame(eqp_id: str, rng: random.Random, anchor: datetime) -> pd.DataFrame:
    """Completed BM/PM jobs in the ~150 days before `anchor`, newest first."""
    n_rows = rng.randint(4, 12)
    records = []
    for _ in range(n_rows):
        pm_type = rng.choice(_PM_TYPES)
        eq_event = rng.choice(_EQ_EVENTS)
        category = classify_category(pm_type, eq_event)
        # Job sometime in the last ~150 days.
        starts = anchor - timedelta(
            days=rng.randint(3, 150),
            hours=rng.randint(0, 23),
            minutes=rng.choice([0, 15, 30, 45]),
        )
        # PM windows run longer than break-down maintenance.
        duration = timedelta(hours=rng.randint(4, 12) if category == "PM" else rng.randint(1, 6))
        ends = starts + duration
        # One tool in ten is still down: no up time recorded yet.
        job_end = "" if rng.random() < 0.1 else fmt_dt(ends)
        # Engineers upload the note shortly after finishing.
        timestamp = ends + timedelta(minutes=rng.randint(10, 240))
        row = {
            "eqp_id": eqp_id,
            "job_starts": fmt_dt(starts),
            "job_end": job_end,
            "category": category,
            "pm_type": pm_type,
            "eq_event": eq_event,
            "lot_id": _lot_id(rng),
            "last_recipe_id": rng.choice(_RECIPE_IDS),
            "note_comment": _fill(rng, _NOTE_TEMPLATES),
            "zzproblem": _fill(rng, _PROBLEM_TEMPLATES),
            "hltext": _fill(rng, _HIGHLIGHT_TEMPLATES),
            "timestamp": fmt_dt(timestamp),
        }
        row["engr_note"] = merge_notes(row)
        records.append(row)

    frame = pd.DataFrame.from_records(
        records,
        columns=[
            "eqp_id", "job_starts", "job_end", "category", "pm_type", "eq_event",
            "lot_id", "last_recipe_id", "note_comment", "zzproblem", "hltext",
            "timestamp", "engr_note",
        ],
    )
    # Newest work first — the office adapter sorts on down_dt the same way.
    return frame.sort_values("job_starts", ascending=False, ignore_index=True)


def build_future_frame(eqp_id: str, rng: random.Random, anchor: datetime) -> pd.DataFrame:
    """Planned BM/PM after `anchor` — few rows (plans change), soonest first."""
    n_rows = rng.randint(0, 3)
    records = []
    for _ in range(n_rows):
        event_name = rng.choice(_PLAN_EVENTS)
        work_item_nm = rng.choice(_WORK_ITEMS)
        category = classify_category(event_name, work_item_nm)
        starts = anchor + timedelta(
            days=rng.randint(5, 90),
            hours=rng.choice([8, 9, 13]),
        )
        ends = starts + timedelta(hours=rng.randint(4, 12) if category == "PM" else rng.randint(1, 6))
        # Plan row last changed recently relative to now.
        timestamp = anchor - timedelta(days=rng.randint(0, 14), hours=rng.randint(0, 23))
        records.append(
            {
                "eqp_id": eqp_id,
                "job_starts": fmt_dt(starts),
                "job_end": fmt_dt(ends),
                "category": category,
                "event_name": event_name,
                "work_item_nm": work_item_nm,
                "work_user_cd": rng.choice(_WORK_USERS),
                "timestamp": fmt_dt(timestamp),
            }
        )

    frame = pd.DataFrame.from_records(
        records,
        columns=[
            "eqp_id", "job_starts", "job_end", "category", "event_name",
            "work_item_nm", "work_user_cd", "timestamp",
        ],
    )
    if frame.empty:
        return frame
    # Soonest plan first — the office adapter sorts on tool_start_tm the same way.
    return frame.sort_values("job_starts", ascending=True, ignore_index=True)


def build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict[str, object]:
    """Deterministic past/future BM/PM records + summary cards for one tool.

    `anchor` is the requested window end — the same clock the trend-chart
    mocks generate against, so BM/PM overlay markers land inside chart
    ranges. Same (eqp_id, anchor) → same data.

    That clock is a naive **KST wall clock**, which is what the office index
    stores (office 확인 2026-08-20: `fab_inform_notes.down_dt` came back as
    `'2026-05-31T08:57:00'`, no `Z`, no offset). `hardware/routes.py` converts
    the frontend's UTC `toISOString()` value before it gets here, so this mock
    and the office adapter are handed the same kind of value.
    """
    rng = random.Random(seed_for(eqp_id))
    past = build_past_frame(eqp_id, rng, anchor).to_dict(orient="records")
    future = build_future_frame(eqp_id, rng, anchor).to_dict(orient="records")
    return {
        "past": past,
        "future": future,
        "cards": derive_cards(past, future),
    }
