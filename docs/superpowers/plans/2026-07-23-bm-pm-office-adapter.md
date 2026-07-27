# BM/PM Office Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the Hardware page's BM/PM tab to the office OpenSearch indices `fab_inform_notes` (work that happened) and `tool_maintenance_plan` (work that is scheduled), widening the table rows to carry the fields engineers read.

**Architecture:** The tab already has a per-tab provider pair under `hardware/providers/bm_pm/`. A new tracked `_shared.py` holds the value logic both providers must agree on (BM/PM classification, timestamp format, note merging, summary cards); `mock.py` and `office_example.py` each build rows from their own source and pass them through it. The dispatcher, route, contract, and Vue component are untouched — `BmPmTables.vue` renders whatever `columns` the normalizer declares.

**Tech Stack:** Python 3.11+, Flask, pandas (mock only), `opensearch-py` via the vendored `ops_store`, pytest. Frontend is Nuxt 4 but needs no change.

**Spec:** `docs/superpowers/specs/2026-07-23-bm-pm-office-adapter-design.md`
**Schema references:** `docs/datatables/hardware_fab_inform_notes.txt`, `docs/datatables/hardware_tool_maintenance_plan.txt`

## Global Constraints

- Row timestamps render as `%Y-%m-%d %H:%M` everywhere. `front-dev-home/app/utils/bmPmMarkers.ts` matches `job_starts` against the trend charts' x-axis values; a different format places markers nowhere instead of failing.
- `mock.py` and `office_example.py` must return identical row keys from `build_bm_pm_data(eqp_id, anchor)`. The dispatcher swaps the modules by name, so drift surfaces as blank cells, not an error.
- `category` must be exactly `"BM"`, `"PM"`, or `""`. Any other value both mis-styles the chip and silently drops the row from the chart overlay.
- Never create `providers/bm_pm/office.py`. It is gitignored, and creating it is what switches the tab to office data. Only `office_example.py` is edited here.
- `office_example.py` must import cleanly at home with no cluster reachable (the OpenSearch client is created lazily inside `_office_search.client()`).
- Do not read `up_dt`, `fac_id`, `aufnr`, `interval_a`, `noti_no`, `oper` from `fab_inform_notes`, or `ll_dt`, `limit_dt`, `org_dt` from `tool_maintenance_plan`. See the datatable docs for why.
- Run tests with `.venv/bin/pytest` from the repo root `/Users/daeyoung/Codes/skewnono_v3_nuxt`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/_shared.py` | Create. Value logic both providers share: `TS_FMT`, `fmt_dt`, `classify_category`, `merge_notes`, `derive_cards` |
| `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/mock.py` | Modify. Fabricate the widened rows through `_shared` |
| `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py` | Modify. Replace the stub with the two-index implementation + office diagnostic |
| `back_dev_home/ebeam/hitachi/hardware/normalizers.py` | Modify lines 204-230. Widen the two `columns` lists |
| `back_dev_home/ebeam/hitachi/hardware/MIGRATION.md` | Modify. bm_pm status and source indices |
| `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py` | Create. `_shared`, mock shape, normalizer columns |
| `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py` | Create. Office adapter mapping and queries |

---

### Task 1: Shared value logic

**Files:**

- Create: `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/_shared.py`
- Test: `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `TS_FMT: str`, `fmt_dt(value: datetime | None) -> str`, `classify_category(*candidates: str) -> str`, `merge_notes(row: dict) -> str`, `derive_cards(past: list[dict], future: list[dict]) -> dict`. Tasks 2 and 4 import all five.

- [ ] **Step 1: Write the failing tests**

Create `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py`:

```python
"""BM/PM row-shape tests: shared value logic, mock parity, declared columns."""

from datetime import datetime

from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm._shared import (
    classify_category,
    derive_cards,
    fmt_dt,
    merge_notes,
)


def test_fmt_dt_matches_the_chart_axis_format():
    # bmPmMarkers.ts matches job_starts against the charts' x values.
    assert fmt_dt(datetime(2026, 5, 20, 9, 5)) == "2026-05-20 09:05"
    assert fmt_dt(None) == ""


def test_classify_category_reads_values_carrying_extra_characters():
    # Office pm_type/eq_event are not clean "BM"/"PM" strings.
    assert classify_category("PM2", "") == "PM"
    assert classify_category("", "BM_ALIGN") == "BM"


def test_classify_category_walks_past_an_unrecognisable_candidate():
    # pm_type present but meaningless: eq_event still decides.
    assert classify_category("기타", "PM_WEEKLY") == "PM"


def test_classify_category_returns_empty_when_nothing_matches():
    # The row still renders; it only drops out of the chart overlay.
    assert classify_category("기타", "") == ""
    assert classify_category() == ""


def test_classify_category_prefers_pm_when_a_value_carries_both():
    assert classify_category("BM/PM 정기") == "PM"


def test_merge_notes_labels_each_note_and_drops_empty_ones():
    row = {"note_comment": "필터 교체", "zzproblem": "", "hltext": "재점검 필요"}
    assert merge_notes(row) == "[Comment] 필터 교체\n[Highlight] 재점검 필요"


def test_merge_notes_is_empty_when_every_note_is_blank():
    assert merge_notes({"note_comment": "", "zzproblem": None}) == ""


def test_derive_cards_falls_back_to_job_starts_when_tool_is_still_down():
    past = [{"category": "BM", "job_starts": "2026-05-01 08:00", "job_end": ""}]
    cards = derive_cards(past, [])
    assert cards["last_bm"] == "2026-05-01 08:00"
    assert cards["recent_count"] == 1
    assert cards["next_pm"] == "—"
    assert cards["planned_count"] == 0


def test_derive_cards_takes_the_soonest_future_pm():
    future = [
        {"category": "BM", "job_starts": "2026-05-02 08:00"},
        {"category": "PM", "job_starts": "2026-05-10 08:00"},
        {"category": "PM", "job_starts": "2026-05-20 08:00"},
    ]
    assert derive_cards([], future)["next_pm"] == "2026-05-10 08:00"


def test_derive_cards_uses_the_most_recent_past_bm():
    past = [
        {"category": "PM", "job_starts": "2026-05-18 08:00", "job_end": "2026-05-18 16:00"},
        {"category": "BM", "job_starts": "2026-05-11 08:00", "job_end": "2026-05-11 12:00"},
        {"category": "BM", "job_starts": "2026-05-01 08:00", "job_end": "2026-05-01 12:00"},
    ]
    assert derive_cards(past, [])["last_bm"] == "2026-05-11 12:00"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py -v`
Expected: collection error — `ModuleNotFoundError: No module named '...bm_pm._shared'`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/_shared.py`:

```python
"""Row-value logic shared by the bm_pm mock and office adapters.

The dispatcher (`providers/office_example.py`) swaps `mock.py` and `office.py`
by module name, so both must produce rows with the same keys, the same
timestamp format, and the same BM/PM classification. That logic lives here,
imported by both, instead of being written twice and drifting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


__all__ = [
    "TS_FMT",
    "classify_category",
    "derive_cards",
    "fmt_dt",
    "merge_notes",
]


# Load-bearing: front-dev-home/app/utils/bmPmMarkers.ts matches `job_starts`
# against the trend charts' own x-axis values. A different format does not
# fail — it draws the overlay markers nowhere.
TS_FMT = "%Y-%m-%d %H:%M"

# Column labels for the three free-form note fields, in display order.
_NOTE_LABELS: tuple[tuple[str, str], ...] = (
    ("note_comment", "Comment"),
    ("zzproblem", "Problem"),
    ("hltext", "Highlight"),
)


def fmt_dt(value: datetime | None) -> str:
    return value.strftime(TS_FMT) if value is not None else ""


def classify_category(*candidates: str) -> str:
    """Reduce raw maintenance-type text to the "BM"/"PM" the UI needs.

    Office `pm_type`/`eq_event` values carry characters around the BM/PM part,
    so this matches on containment rather than equality. Candidates are walked
    in priority order and an unrecognisable one does NOT stop the walk: a
    `pm_type` of "기타" beside an `eq_event` of "PM_WEEKLY" is a PM record.

    An unclassifiable row yields "" and still renders — its raw `pm_type` and
    `eq_event` columns stay visible. It only drops out of the chart overlay,
    which already skips anything that is not exactly "BM" or "PM".

    "PM" is tested first because a value carrying both is far more likely a PM
    record qualified by other text than the reverse.
    """
    for candidate in candidates:
        text = (candidate or "").strip().upper()
        if "PM" in text:
            return "PM"
        if "BM" in text:
            return "BM"
    return ""


def merge_notes(row: dict[str, Any]) -> str:
    """The three note fields as one labelled block, for the overlay tooltip.

    Carried on the row but never declared as a column: `BmPmTables.vue`
    renders only declared columns, while `bmPmMarkers.ts` reads
    `row.engr_note` directly. Blank notes are dropped so a tooltip never shows
    a bare label.
    """
    parts = []
    for key, label in _NOTE_LABELS:
        text = str(row.get(key) or "").strip()
        if text:
            parts.append(f"[{label}] {text}")
    return "\n".join(parts)


def derive_cards(
    past: list[dict[str, Any]], future: list[dict[str, Any]]
) -> dict[str, Any]:
    """Summary-card values read off the finished rows.

    Relies on the row order both providers promise — `past` newest-first,
    `future` soonest-first — so the first matching row on each side is the one
    the card wants.
    """
    last_bm = "—"
    for row in past:
        if row.get("category") == "BM":
            # A tool that is still down has no job_end; show when it went down
            # rather than a blank card.
            last_bm = str(row.get("job_end") or row.get("job_starts") or "—")
            break

    next_pm = "—"
    for row in future:
        if row.get("category") == "PM":
            next_pm = str(row.get("job_starts") or "—")
            break

    return {
        "last_bm": last_bm,
        "next_pm": next_pm,
        "planned_count": len(future),
        "recent_count": len(past),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/_shared.py \
        back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py
git commit -m "feat(hardware): shared BM/PM row-value logic for both providers"
```

---

### Task 2: Widen the mock rows

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/mock.py`
- Test: `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py`

**Interfaces:**

- Consumes: `_shared.classify_category`, `_shared.derive_cards`, `_shared.merge_notes`, `_shared.fmt_dt`.
- Produces: `build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict` returning `{"past": list[dict], "future": list[dict], "cards": dict}`. Past rows carry the 12 keys `eqp_id, job_starts, job_end, category, pm_type, eq_event, lot_id, last_recipe_id, note_comment, zzproblem, hltext, timestamp` plus `engr_note`. Future rows carry `eqp_id, job_starts, job_end, category, event_name, work_item_nm, work_user_cd, timestamp`. Task 3 declares columns over these keys; Task 4 reproduces them from OpenSearch.

- [ ] **Step 1: Write the failing tests**

Append to `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py`:

```python
import re

from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm import mock as bm_pm_mock

ANCHOR = datetime(2026, 5, 20, 9, 0)

PAST_KEYS = {
    "eqp_id", "job_starts", "job_end", "category", "pm_type", "eq_event",
    "lot_id", "last_recipe_id", "note_comment", "zzproblem", "hltext",
    "timestamp", "engr_note",
}
FUTURE_KEYS = {
    "eqp_id", "job_starts", "job_end", "category", "event_name",
    "work_item_nm", "work_user_cd", "timestamp",
}


def test_mock_past_rows_carry_the_full_key_set():
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    assert data["past"], "mock should fabricate past work for any tool"
    for row in data["past"]:
        assert set(row) == PAST_KEYS


def test_mock_future_rows_carry_the_full_key_set():
    # Seeded so this tool has planned work; build_future_frame can return none.
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    for row in data["future"]:
        assert set(row) == FUTURE_KEYS


def test_mock_rows_use_the_chart_timestamp_format():
    # bmPmMarkers.ts matches these against the charts' x-axis values.
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    for row in data["past"]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row["job_starts"])
        assert row["job_end"] == "" or re.fullmatch(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row["job_end"]
        )


def test_mock_past_is_newest_first_and_future_is_soonest_first():
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    starts = [row["job_starts"] for row in data["past"]]
    assert starts == sorted(starts, reverse=True)
    plans = [row["job_starts"] for row in data["future"]]
    assert plans == sorted(plans)


def test_mock_is_deterministic_for_a_tool_and_anchor():
    first = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    second = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    assert first == second


def test_mock_produces_some_unclassifiable_rows_for_the_ui_to_render():
    # Real pm_type/eq_event do not always say BM or PM. The mock must exercise
    # that path so the "" category is visible at home, not only at the office.
    seen = set()
    for tool in ("CDX001", "CDX002", "CDX003", "HVX010", "HVX011"):
        for row in bm_pm_mock.build_bm_pm_data(tool, ANCHOR)["past"]:
            seen.add(row["category"])
    assert seen >= {"BM", "PM", ""}


def test_mock_engr_note_merges_the_populated_notes():
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    row = next(r for r in data["past"] if r["note_comment"])
    assert "[Comment]" in row["engr_note"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py -v`
Expected: FAIL — `test_mock_past_rows_carry_the_full_key_set` reports the current 6-key set, not `PAST_KEYS`

- [ ] **Step 3: Rewrite the mock generators**

In `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/mock.py`, first replace the last paragraph of the module docstring:

```python
`build_bm_pm_data()` is the only public entry point; it returns plain dict
records (via `DataFrame.to_dict`) plus pre-computed summary-card values, ready
for `normalizers.bm_pm_history_payload`.
```

with:

```python
`build_bm_pm_data()` is the only public entry point; it returns plain dict
records (via `DataFrame.to_dict`) plus pre-computed summary-card values, ready
for `normalizers.bm_pm_history_payload`. The values both providers must agree
on — timestamp format, BM/PM classification, merged note, summary cards — come
from `_shared.py`, so the office adapter derives them identically.
```

Then replace everything from line 20 (`from back_dev_home.ebeam.hitachi.hardware.providers._siblings import seed_for`) to the end of the file with:

```python
from back_dev_home.ebeam.hitachi.hardware.providers._siblings import seed_for
from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm._shared import (
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
    """
    rng = random.Random(seed_for(eqp_id))
    past = build_past_frame(eqp_id, rng, anchor).to_dict(orient="records")
    future = build_future_frame(eqp_id, rng, anchor).to_dict(orient="records")
    return {
        "past": past,
        "future": future,
        "cards": derive_cards(past, future),
    }
```

The replacement spans the whole file below the imports, so the old `Category` alias, `_TS_FMT`, `_make_note`, and `_derive_cards` are gone with it. What survives from the original file: the module docstring (with the paragraph swapped above) and the three stdlib/pandas imports on lines 15-18. Confirm nothing else references the deleted names:

Run: `grep -n "_TS_FMT\|_make_note\|_derive_cards\|Category" back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/mock.py`
Expected: no output

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py -v`
Expected: 17 passed

If `test_mock_produces_some_unclassifiable_rows_for_the_ui_to_render` fails, the five sampled tools happened to miss the `"기타"`/`""` combination — add another tool id to the loop rather than reweighting `_PM_TYPES`.

- [ ] **Step 5: Confirm the contract gate still passes**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware -v`
Expected: all pass, including `test_hardware_service_matches_contract[bm-pm]`

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/mock.py \
        back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py
git commit -m "feat(hardware): widen BM/PM mock rows to the office field set"
```

---

### Task 3: Declare the new columns

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/hardware/normalizers.py:204-230`
- Test: `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py`

**Interfaces:**

- Consumes: the row keys Task 2 produces.
- Produces: `past_work` and `future_work` table sections whose `columns` cover every displayed key. No signature change to `bm_pm_history_payload`.

- [ ] **Step 1: Write the failing tests**

Append to `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py`:

```python
from datetime import timedelta

from back_dev_home.ebeam.hitachi.hardware import data as hardware_data


def _bm_pm_payload():
    end = ANCHOR
    start = end - timedelta(days=14)
    return hardware_data.get_hardware_service("cdsem", "bm-pm", "CDX001", "R3", start, end)


def test_every_declared_column_exists_on_every_row():
    # A typo in either list shows up as a blank column, never as an error.
    payload = _bm_pm_payload()
    for section in payload["tables"]:
        declared = {column["key"] for column in section["columns"]}
        for row in section["rows"]:
            missing = declared - set(row)
            assert not missing, f"{section['key']} row is missing {sorted(missing)}"


def test_past_table_declares_the_three_note_columns_as_expandable():
    payload = _bm_pm_payload()
    past = next(s for s in payload["tables"] if s["key"] == "past_work")
    labels = {c["key"]: c for c in past["columns"]}
    for key, label in (("note_comment", "Comment"), ("zzproblem", "Problem"), ("hltext", "Highlight")):
        assert labels[key]["label"] == label
        assert labels[key]["expandable"] is True


def test_engr_note_rides_along_without_being_a_column():
    # bmPmMarkers.ts reads row.engr_note; BmPmTables.vue must not show it.
    payload = _bm_pm_payload()
    past = next(s for s in payload["tables"] if s["key"] == "past_work")
    assert "engr_note" not in {c["key"] for c in past["columns"]}
    assert all("engr_note" in row for row in past["rows"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py -k column -v`
Expected: FAIL — `KeyError: 'note_comment'` in `test_past_table_declares_the_three_note_columns_as_expandable`

- [ ] **Step 3: Widen both column lists**

In `back_dev_home/ebeam/hitachi/hardware/normalizers.py`, replace the two `"columns"` lists inside `bm_pm_history_payload` (lines 208-214 and 221-227) with:

```python
            "columns": [
                {"key": "eqp_id", "label": "EQP ID"},
                {"key": "job_starts", "label": "Down"},
                {"key": "job_end", "label": "Up"},
                {"key": "category", "label": "Category"},
                {"key": "pm_type", "label": "PM Type"},
                {"key": "eq_event", "label": "Event"},
                {"key": "lot_id", "label": "Lot"},
                {"key": "last_recipe_id", "label": "Last Recipe"},
                {"key": "note_comment", "label": "Comment", "expandable": True},
                {"key": "zzproblem", "label": "Problem", "expandable": True},
                {"key": "hltext", "label": "Highlight", "expandable": True},
                {"key": "timestamp", "label": "Uploaded"},
            ],
```

and:

```python
            "columns": [
                {"key": "eqp_id", "label": "EQP ID"},
                {"key": "job_starts", "label": "Start"},
                {"key": "job_end", "label": "End"},
                {"key": "category", "label": "Category"},
                {"key": "event_name", "label": "Event"},
                {"key": "work_item_nm", "label": "Work Item", "expandable": True},
                {"key": "work_user_cd", "label": "Worker"},
                {"key": "timestamp", "label": "Registered"},
            ],
```

Then update the docstring line "Rows arrive pre-sorted (timestamp desc) from the provider" to "Rows arrive pre-sorted from the provider — past newest-first, future soonest-first".

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware -v`
Expected: all pass

- [ ] **Step 5: Check the tab in the running app**

Start the app per the `verify` skill, open the Hardware page, pick a CD-SEM tool, open the BM/PM tab. Confirm: the past table shows Down/Up/PM Type/Event/Lot/Last Recipe plus three expandable note columns; clicking a note expands it with newlines preserved; rows with an unclassifiable category show an empty chip but still render; the BM/PM markers still appear on another tab's trend chart.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/ebeam/hitachi/hardware/normalizers.py \
        back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm.py
git commit -m "feat(hardware): declare the widened BM/PM table columns"
```

---

### Task 4: Office row mappers

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py`
- Test: `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py`

**Interfaces:**

- Consumes: `_shared` (all five names), `_office_search.text`, `_office_search.parse_dt`.
- Produces: module constants `INDEX_PAST = "fab_inform_notes"`, `INDEX_FUTURE = "tool_maintenance_plan"`, `EQP_ID_KW = "eqp_id.keyword"`, `DOWN_DT = "down_dt"`, `PLAN_START = "tool_start_tm"`, `PAST_DAYS = 180`, `FUTURE_DAYS = 90`, `MAX_ROWS = 1000`, `PAST_SOURCE: list[str]`, `FUTURE_SOURCE: list[str]`; functions `_fmt_stored(value) -> str`, `_check_eqp(doc, eqp_id, index) -> str`, `past_row(doc, eqp_id) -> dict`, `future_row(doc, eqp_id) -> dict`. Task 5 calls `past_row`/`future_row` and the constants.

- [ ] **Step 1: Write the failing tests**

Create `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py`:

```python
"""Office BM/PM adapter tests.

These exercise the TRACKED template (`office_example`), never the gitignored
`office.py`, and never touch a cluster: every test feeds fabricated `_source`
dicts to the pure mappers or monkeypatches `fetch_hits`.
"""

from datetime import datetime

import pytest

from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm import office_example as office


ANCHOR = datetime(2026, 5, 20, 9, 0)

PAST_HIT = {
    "eqp_id": "CDX001",
    "down_dt": "2026-05-11T08:00:00",
    "equp_dt": "2026-05-11T12:30:00",
    "hub_load_tm": "2026-05-11T13:05:00",
    "pm_type": "",
    "eq_event": "BM_ALIGN",
    "lot_id": "CG6300000123",
    "last_recipe_id": "CD_BIAS_A01",
    "note_comment": "필터 교체",
    "zzproblem": "진공도 미달",
    "hltext": "",
}

FUTURE_HIT = {
    "eqp_id": "CDX001",
    "tool_start_tm": "2026-06-02T08:00:00",
    "tool_end_tm": "2026-06-02T17:00:00",
    "chg_tm": "2026-05-18T11:00:00",
    "event_name": "PM_QUARTER",
    "work_item_nm": "정기 PM — 컬럼 청소",
    "work_user_cd": "K12345",
}


def test_past_row_maps_index_fields_onto_the_row_contract():
    row = office.past_row(PAST_HIT, "CDX001")
    assert row["job_starts"] == "2026-05-11 08:00"   # down_dt
    assert row["job_end"] == "2026-05-11 12:30"      # equp_dt
    assert row["timestamp"] == "2026-05-11 13:05"    # hub_load_tm
    assert row["category"] == "BM"                   # pm_type empty -> eq_event
    assert row["lot_id"] == "CG6300000123"
    assert row["engr_note"] == "[Comment] 필터 교체\n[Problem] 진공도 미달"


def test_past_row_leaves_job_end_blank_while_the_tool_is_still_down():
    hit = {**PAST_HIT, "equp_dt": None}
    assert office.past_row(hit, "CDX001")["job_end"] == ""


def test_past_row_rejects_a_row_with_no_down_time():
    hit = {**PAST_HIT, "down_dt": ""}
    with pytest.raises(ValueError, match="down_dt"):
        office.past_row(hit, "CDX001")


def test_past_row_rejects_a_hit_for_another_tool():
    hit = {**PAST_HIT, "eqp_id": "CDX999"}
    with pytest.raises(ValueError, match="CDX999"):
        office.past_row(hit, "CDX001")


def test_past_row_never_reads_up_dt():
    # up_dt is unused by contract; a populated one must not reach the row.
    hit = {**PAST_HIT, "up_dt": "2026-05-11T20:00:00"}
    assert "2026-05-11 20:00" not in office.past_row(hit, "CDX001").values()


def test_future_row_maps_index_fields_onto_the_row_contract():
    row = office.future_row(FUTURE_HIT, "CDX001")
    assert row["job_starts"] == "2026-06-02 08:00"   # tool_start_tm
    assert row["job_end"] == "2026-06-02 17:00"      # tool_end_tm
    assert row["timestamp"] == "2026-05-18 11:00"    # chg_tm
    assert row["category"] == "PM"
    assert row["work_user_cd"] == "K12345"


def test_future_row_rejects_a_row_with_no_planned_start():
    hit = {**FUTURE_HIT, "tool_start_tm": ""}
    with pytest.raises(ValueError, match="tool_start_tm"):
        office.future_row(hit, "CDX001")


def test_rows_match_the_mock_key_set_exactly():
    # The dispatcher swaps mock.py and office.py by name; divergent keys show
    # up as blank cells rather than an error, so pin them against each other.
    from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm import mock

    mock_data = mock.build_bm_pm_data("CDX001", ANCHOR)
    assert set(office.past_row(PAST_HIT, "CDX001")) == set(mock_data["past"][0])
    assert set(office.future_row(FUTURE_HIT, "CDX001")) == set(mock_data["future"][0])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py -v`
Expected: FAIL — `AttributeError: module '...office_example' has no attribute 'past_row'`

If `test_rows_match_the_mock_key_set_exactly` errors with `IndexError` on `mock_data["future"][0]`, the seeded tool produced no planned rows; change the tool id in that test to one that does.

- [ ] **Step 3: Write the mappers**

Replace the whole of `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py` with:

```python
# TEMPLATE — copy to office.py at the office, then verify against real data.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office BM/PM adapter — OpenSearch ``fab_inform_notes`` + ``tool_maintenance_plan``.

Two indices, one per table section (schema: ``docs/datatables/*.txt``):

* ``fab_inform_notes`` — maintenance that HAPPENED. ``down_dt``/``equp_dt`` are
  the tool's down/up times and the three free-form engineer notes
  (``note_comment``, ``zzproblem``, ``hltext``) are the substance of the tab.
* ``tool_maintenance_plan`` — maintenance that is SCHEDULED.
  ``tool_start_tm``/``tool_end_tm`` bound the planned window; ``chg_tm`` is the
  document's own timestamp.

Returns the same shape as ``bm_pm/mock.py``'s ``build_bm_pm_data``: ``past``
rows, ``future`` rows, and derived ``cards``, which the top-level
``providers/office.py`` dispatcher hands to ``normalizers.bm_pm_history_payload``.
``anchor`` is the request's ``end`` datetime.

Deliberately unread: ``up_dt`` (an expected-up field that is not maintained —
the planned side lives in ``tool_maintenance_plan``), ``fac_id`` (coarser than
fab and not a join key), and ``ll_dt``/``limit_dt``/``org_dt`` (normally empty).

UNVERIFIED until run at the office: whether these two indices store offset-less
KST wall clock like ``network_fdc_cdsem``. A stored ``Z`` suffix would slide
every window by nine hours. Run this module's ``__main__`` — it prints raw
stored values next to the reformatted ones — before trusting the tab.

At the office: fill OPENSEARCH_* in ``back_dev_home/.env``, ``cp`` this file
and ``providers/office_example.py`` to ``office.py``, set
``SKEWNONO_HARDWARE_PROVIDER=office``, and run hardware/MIGRATION.md's Verify.
"""

from datetime import datetime, timedelta
from typing import Any

from back_dev_home.ebeam.hitachi._office_search import (
    fetch_hits,
    parse_dt,
    query as _query,
    text as _text,
)
from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm._shared import (
    classify_category,
    derive_cards,
    fmt_dt,
    merge_notes,
)


__all__ = ["build_bm_pm_data"]


INDEX_PAST = "fab_inform_notes"
INDEX_FUTURE = "tool_maintenance_plan"

# Both indices dynamic-map eqp_id as text+keyword, so exact match needs the
# subfield; the date fields are declared `date`, so they range and sort bare.
EQP_ID_KW = "eqp_id.keyword"
DOWN_DT = "down_dt"
PLAN_START = "tool_start_tm"

# The dispatcher passes only `anchor`, so the adapter owns its windows.
PAST_DAYS = 180
FUTURE_DAYS = 90

# One non-paginated request per side. Hitting the cap means a single tool has
# more than 1000 maintenance records in half a year — the assumption broke, so
# raise rather than silently showing a truncated history.
MAX_ROWS = 1000

# Explicit field lists so a new ingestion column cannot ride along into rows.
PAST_SOURCE = [
    "eqp_id", "down_dt", "equp_dt", "hub_load_tm", "pm_type", "eq_event",
    "lot_id", "last_recipe_id", "note_comment", "zzproblem", "hltext",
]
FUTURE_SOURCE = [
    "eqp_id", "tool_start_tm", "tool_end_tm", "chg_tm", "event_name",
    "work_item_nm", "work_user_cd",
]


def _fmt_stored(value: Any) -> str:
    """Reformat a stored OpenSearch date to the chart's ``TS_FMT``.

    Reformats only — never converts. The stored wall clock reaches the table
    verbatim, which is what keeps overlay markers aligned with chart x-values
    whichever convention the index turns out to use. An unparseable value is
    passed through as trimmed text rather than raising: a malformed *display*
    timestamp should not blank the whole tab. The two fields that order the
    tables are validated separately, in the row mappers.
    """
    raw = _text(value)
    if not raw:
        return ""
    try:
        return fmt_dt(parse_dt(raw))
    except ValueError:
        return raw


def _check_eqp(doc: dict[str, Any], eqp_id: str, index: str) -> str:
    """Fail loudly if a hit belongs to another tool.

    A mismatch means the term clause matched more than intended — usually a
    mapping drift on the ``.keyword`` subfield — and the page would otherwise
    show another tool's maintenance under this tool's name.
    """
    doc_eqp = _text(doc.get("eqp_id"))
    if doc_eqp and doc_eqp != eqp_id:
        raise ValueError(
            f"{index}: expected eqp_id {eqp_id!r} but a hit carries "
            f"{doc_eqp!r} — check the {EQP_ID_KW} mapping."
        )
    return doc_eqp or eqp_id


def past_row(doc: dict[str, Any], eqp_id: str) -> dict[str, Any]:
    """One ``fab_inform_notes`` hit as a past-work row."""
    tool = _check_eqp(doc, eqp_id, INDEX_PAST)
    job_starts = _fmt_stored(doc.get("down_dt"))
    if not job_starts:
        raise ValueError(
            f"{INDEX_PAST}: a hit for {eqp_id!r} has an empty down_dt, so it "
            "cannot be ordered or placed on the timeline."
        )
    row = {
        "eqp_id": tool,
        "job_starts": job_starts,
        # Blank while the tool is still down — expected, not an error.
        "job_end": _fmt_stored(doc.get("equp_dt")),
        "category": classify_category(
            _text(doc.get("pm_type")), _text(doc.get("eq_event"))
        ),
        "pm_type": _text(doc.get("pm_type")),
        "eq_event": _text(doc.get("eq_event")),
        "lot_id": _text(doc.get("lot_id")),
        "last_recipe_id": _text(doc.get("last_recipe_id")),
        "note_comment": _text(doc.get("note_comment")),
        "zzproblem": _text(doc.get("zzproblem")),
        "hltext": _text(doc.get("hltext")),
        "timestamp": _fmt_stored(doc.get("hub_load_tm")),
    }
    row["engr_note"] = merge_notes(row)
    return row


def future_row(doc: dict[str, Any], eqp_id: str) -> dict[str, Any]:
    """One ``tool_maintenance_plan`` hit as a planned-work row."""
    tool = _check_eqp(doc, eqp_id, INDEX_FUTURE)
    job_starts = _fmt_stored(doc.get("tool_start_tm"))
    if not job_starts:
        raise ValueError(
            f"{INDEX_FUTURE}: a hit for {eqp_id!r} has an empty "
            "tool_start_tm, so it cannot be ordered or placed on the timeline."
        )
    work_item_nm = _text(doc.get("work_item_nm"))
    event_name = _text(doc.get("event_name"))
    return {
        "eqp_id": tool,
        "job_starts": job_starts,
        "job_end": _fmt_stored(doc.get("tool_end_tm")),
        "category": classify_category(event_name, work_item_nm),
        "event_name": event_name,
        "work_item_nm": work_item_nm,
        "work_user_cd": _text(doc.get("work_user_cd")),
        "timestamp": _fmt_stored(doc.get("chg_tm")),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py \
        back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py
git commit -m "feat(hardware): map BM/PM office rows from the two ops indices"
```

---

### Task 5: Office queries

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py`
- Test: `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py`

**Interfaces:**

- Consumes: everything Task 4 produced.
- Produces: `build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict[str, object]` — the builder name the dispatcher calls, identical in signature and return shape to the mock's.

- [ ] **Step 1: Write the failing tests**

Append to `back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py`:

```python
def _capture(monkeypatch, past_hits=(), future_hits=()):
    """Record each fetch_hits call and serve canned hits per index."""
    calls = []

    def fake_fetch_hits(index, query_body, size, sort=None, source=None):
        calls.append(
            {"index": index, "query": query_body, "size": size,
             "sort": sort, "source": source}
        )
        return list(past_hits if index == office.INDEX_PAST else future_hits)

    monkeypatch.setattr(office, "fetch_hits", fake_fetch_hits)
    return calls


def test_build_queries_both_indices_with_the_documented_windows(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_bm_pm_data("CDX001", ANCHOR)

    past = next(c for c in calls if c["index"] == office.INDEX_PAST)
    clauses = past["query"]["bool"]["filter"]
    assert {"term": {office.EQP_ID_KW: "CDX001"}} in clauses
    rng = next(c["range"][office.DOWN_DT] for c in clauses if "range" in c)
    assert rng["gte"] == "2025-11-21T09:00:00"   # anchor - 180d
    assert rng["lte"] == "2026-05-20T09:00:00"
    assert past["sort"] == [{office.DOWN_DT: {"order": "desc"}}]

    future = next(c for c in calls if c["index"] == office.INDEX_FUTURE)
    clauses = future["query"]["bool"]["filter"]
    rng = next(c["range"][office.PLAN_START] for c in clauses if "range" in c)
    assert rng["gte"] == "2026-05-20T09:00:00"
    assert rng["lte"] == "2026-08-18T09:00:00"    # anchor + 90d
    assert future["sort"] == [{office.PLAN_START: {"order": "asc"}}]


def test_build_does_not_filter_on_fab(monkeypatch):
    # eqp_id is the identity; a stale fab label must not empty the table.
    calls = _capture(monkeypatch)
    office.build_bm_pm_data("CDX001", ANCHOR)
    for call in calls:
        rendered = repr(call["query"])
        assert "fab_name" not in rendered
        assert "det_fac_id" not in rendered
        assert "fac_id" not in rendered


def test_build_requests_only_the_documented_source_fields(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_bm_pm_data("CDX001", ANCHOR)
    past = next(c for c in calls if c["index"] == office.INDEX_PAST)
    assert "up_dt" not in past["source"]
    assert set(past["source"]) == set(office.PAST_SOURCE)


def test_build_returns_mapped_rows_and_cards(monkeypatch):
    _capture(monkeypatch, past_hits=[PAST_HIT], future_hits=[FUTURE_HIT])
    data = office.build_bm_pm_data("CDX001", ANCHOR)
    assert data["past"][0]["category"] == "BM"
    assert data["future"][0]["category"] == "PM"
    assert data["cards"] == {
        "last_bm": "2026-05-11 12:30",
        "next_pm": "2026-06-02 08:00",
        "planned_count": 1,
        "recent_count": 1,
    }


def test_build_is_an_empty_result_not_an_error_for_a_tool_with_no_work(monkeypatch):
    _capture(monkeypatch)
    data = office.build_bm_pm_data("CDX001", ANCHOR)
    assert data["past"] == []
    assert data["future"] == []
    assert data["cards"]["last_bm"] == "—"


def test_build_raises_when_a_side_fills_the_row_cap(monkeypatch):
    _capture(monkeypatch, past_hits=[PAST_HIT] * office.MAX_ROWS)
    with pytest.raises(LookupError, match="cap"):
        office.build_bm_pm_data("CDX001", ANCHOR)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py -k build -v`
Expected: FAIL — `AttributeError: module '...office_example' has no attribute 'build_bm_pm_data'`

- [ ] **Step 3: Write the query layer**

Append to `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py`:

```python
def _fetch(
    index: str,
    eqp_id: str,
    range_field: str,
    gte: datetime,
    lte: datetime,
    order: str,
    source: list[str],
) -> list[dict[str, Any]]:
    """One capped, sorted, tool-scoped pull from one index.

    ``fab_name`` is deliberately NOT a filter: ``eqp_id`` is already the lookup
    identity and a tool belongs to one fab, so filtering on both would let a
    stale fab label silently empty the table. The two indices also spell fab
    differently (``fab_name`` vs ``det_fac_id``), which is exactly the kind of
    mismatch that empties a result without erroring.
    """
    clauses: list[dict[str, Any]] = [
        {"term": {EQP_ID_KW: eqp_id}},
        {"range": {range_field: {"gte": gte.isoformat(), "lte": lte.isoformat()}}},
    ]
    hits = fetch_hits(
        index,
        _query(clauses),
        size=MAX_ROWS,
        sort=[{range_field: {"order": order}}],
        source=source,
    )
    if len(hits) >= MAX_ROWS:
        raise LookupError(
            f"{index}: {eqp_id} returned the full {MAX_ROWS}-row cap, so the "
            "result is probably truncated. Narrow the window, or add "
            "pagination before raising the cap."
        )
    return hits


def build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict[str, object]:
    """Past/future BM/PM rows + summary cards for one tool.

    Past covers ``anchor - PAST_DAYS .. anchor`` by ``down_dt`` (newest first);
    future covers ``anchor .. anchor + FUTURE_DAYS`` by ``tool_start_tm``
    (soonest first). ``eqp_id`` is never None here — ``normalizers.service_gate``
    returns the "pick a tool" payload before the dispatcher reaches this call.

    A tool with no maintenance in either window is a valid empty result, not an
    error: empty tables and "—" cards.
    """
    past_hits = _fetch(
        INDEX_PAST, eqp_id, DOWN_DT,
        anchor - timedelta(days=PAST_DAYS), anchor, "desc", PAST_SOURCE,
    )
    future_hits = _fetch(
        INDEX_FUTURE, eqp_id, PLAN_START,
        anchor, anchor + timedelta(days=FUTURE_DAYS), "asc", FUTURE_SOURCE,
    )
    past = [past_row(hit, eqp_id) for hit in past_hits]
    future = [future_row(hit, eqp_id) for hit in future_hits]
    return {"past": past, "future": future, "cards": derive_cards(past, future)}
```

- [ ] **Step 4: Run the full hardware suite**

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware -v`
Expected: all pass. `bm_pm` still has no `office.py`, so the dispatcher fallback tests keep skipping it.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py \
        back_dev_home/ebeam/hitachi/hardware/tests/test_bm_pm_office.py
git commit -m "feat(hardware): query fab_inform_notes and tool_maintenance_plan for BM/PM"
```

---

### Task 6: Office diagnostic and migration docs

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py`
- Modify: `back_dev_home/ebeam/hitachi/hardware/MIGRATION.md:14`, and the `<!-- OFFICE: ... -->` line near line 125

**Interfaces:**

- Consumes: `build_bm_pm_data`, the module constants.
- Produces: a `python -m` entry point. Nothing imports it.

- [ ] **Step 1: Append the diagnostic**

Append to `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py`:

```python
# --------------------------------------------------------------------------- #
# Office smoke test / diagnosis — run this module directly (see __main__).
# --------------------------------------------------------------------------- #
def _diagnose(eqp_id: str, anchor: datetime) -> None:  # pragma: no cover
    """Answer the three questions an empty BM/PM tab raises, in order: is the
    tool spelled this way, is the window right, and is the stored timestamp
    the wall clock we assume? ASCII-only output, so a cp949 Windows console
    never raises."""
    from back_dev_home.ebeam.hitachi._office_search import client

    os_client = client()

    def _count(index: str, filters: list) -> Any:
        res = os_client.search(
            index=index, body={"size": 0, "query": {"bool": {"filter": filters}}}
        )
        total = res.get("hits", {}).get("total", {})
        return total.get("value") if isinstance(total, dict) else total

    def _rng(field: str, lo: datetime, hi: datetime) -> dict:
        return {"range": {field: {"gte": lo.isoformat(), "lte": hi.isoformat()}}}

    eqp = {"term": {EQP_ID_KW: eqp_id}}
    sides = [
        (INDEX_PAST, DOWN_DT, anchor - timedelta(days=PAST_DAYS), anchor),
        (INDEX_FUTURE, PLAN_START, anchor, anchor + timedelta(days=FUTURE_DAYS)),
    ]

    for index, field, lo, hi in sides:
        print("\n=== %s (tool=%s) ===" % (index, eqp_id))

        # [1] Which eqp_id values exist, spelled how?
        try:
            body = {"size": 0,
                    "aggs": {"ids": {"terms": {"field": EQP_ID_KW, "size": 50}}}}
            buckets = (os_client.search(index=index, body=body)
                       .get("aggregations", {}).get("ids", {}).get("buckets", []))
            names = [b["key"] for b in buckets]
            print("[1] %d eqp_ids; %r present: %s"
                  % (len(names), eqp_id, eqp_id in names))
            if names:
                print("    " + ", ".join("%s(%s)" % (b["key"], b["doc_count"])
                                         for b in buckets[:20]))
        except Exception as exc:  # noqa: BLE001 — diagnostic path, never fatal
            print("[1] eqp_id terms FAILED: %s" % exc)

        # [2] Which single clause drops the count to zero?
        probes = [
            ("eqp_id only (no time)", [eqp]),
            ("time range only", [_rng(field, lo, hi)]),
            ("eqp_id + window [adapter]", [eqp, _rng(field, lo, hi)]),
        ]
        print("[2] clause isolation on %s (%s .. %s):"
              % (field, lo.isoformat(), hi.isoformat()))
        for label, filters in probes:
            try:
                print("    %-28s: %s docs" % (label, _count(index, filters)))
            except Exception as exc:  # noqa: BLE001
                print("    %-28s: ERROR %s" % (label, exc))

        # [3] The timezone check: raw stored value next to what the row shows.
        try:
            sample = fetch_hits(index, _query([eqp]), size=1,
                                sort=[{field: {"order": "desc"}}])
            if sample:
                raw = sample[0].get(field)
                print("[3] stored %s=%r -> row shows %r"
                      % (field, raw, _fmt_stored(raw)))
                print("    A 'Z'/offset suffix here means the window and the "
                      "displayed clock are 9h apart from KST. Compare against "
                      "a job you know the real time of before trusting the tab.")
            else:
                print("[3] no docs for this tool; cannot check the stored format")
        except Exception as exc:  # noqa: BLE001
            print("[3] sample FAILED: %s" % exc)


if __name__ == "__main__":  # pragma: no cover
    #   python -m back_dev_home.ebeam.hitachi.hardware.providers.bm_pm.office
    # Diagnoses both indices one clause at a time, then runs build_bm_pm_data.
    # Edit TOOL below and run with no args; passing args overrides.
    import sys
    from collections import Counter

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # ---- EDIT: real eqp_ids look like "6MCDE305" (NOT "MCD018") ----
    TOOL = "6MCDE305"
    tool = sys.argv[1] if len(sys.argv) > 1 else TOOL
    now = datetime.now()

    _diagnose(tool, now)

    print("\n=== build_bm_pm_data (both indices + map + cards) ===")
    try:
        pulled = build_bm_pm_data(tool, now)
    except Exception as exc:  # noqa: BLE001 — show the error, keep the diagnosis
        print("build_bm_pm_data raised: %s: %s" % (type(exc).__name__, exc))
    else:
        print("past=%d future=%d cards=%s"
              % (len(pulled["past"]), len(pulled["future"]), pulled["cards"]))
        print("past categories: %s"
              % dict(Counter(r["category"] or "(unclassified)"
                             for r in pulled["past"])))
        if pulled["past"]:
            first = pulled["past"][0]
            print("newest past row: down=%r up=%r pm_type=%r eq_event=%r"
                  % (first["job_starts"], first["job_end"],
                     first["pm_type"], first["eq_event"]))
```

- [ ] **Step 2: Verify the module still imports without a cluster**

Run: `.venv/bin/python -c "from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm import office_example as o; print(o.INDEX_PAST, o.INDEX_FUTURE)"`
Expected: `fab_inform_notes tool_maintenance_plan`

- [ ] **Step 3: Update MIGRATION.md**

In `back_dev_home/ebeam/hitachi/hardware/MIGRATION.md`, replace the bm_pm table row (line 14):

```markdown
| `bm_pm/` | `build_bm_pm_data` | OpenSearch `fab_inform_notes` + `tool_maintenance_plan` | written — `cp` + verify |
```

In the `<!-- OFFICE: ... -->` data-source comment near line 125, replace `BM/PM work-order table` with `fab_inform_notes + tool_maintenance_plan`.

Then add this paragraph after the table's `fdc/office_example.py` note:

```markdown
`bm_pm/office_example.py` is implemented too, over two indices: `fab_inform_notes`
for the past-work table (`down_dt`/`equp_dt` plus the three engineer notes) and
`tool_maintenance_plan` for the planned-work table. Run its `__main__` before
`cp`-ing it — the diagnostic prints the raw stored timestamps, which is the one
thing about these indices that is still unverified (see the module docstring).
Schema: `docs/datatables/hardware_fab_inform_notes.txt`, `docs/datatables/hardware_tool_maintenance_plan.txt`.
```

- [ ] **Step 4: Lint the docs and run the suite**

Run: `npm run lint:md`
Expected: `Summary: 0 error(s)`

Run: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/hardware/providers/bm_pm/office_example.py \
        back_dev_home/ebeam/hitachi/hardware/MIGRATION.md
git commit -m "feat(hardware): BM/PM office diagnostic + migration notes"
```

---

## Done When

- `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware` passes.
- The BM/PM tab at home shows the widened columns against mock data, notes expand, and unclassified rows render.
- BM/PM markers still overlay the other hardware trend charts.
- `providers/bm_pm/office_example.py` is a complete implementation with a runnable diagnostic, and no `office.py` exists in the repo.
- Remaining office-side work is the `cp` + verify recorded in `hardware/MIGRATION.md`.
