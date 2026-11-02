"""Rule 없는 장비 계열(HV-SEM / VeritySEM / Provision)의 mock 표 A~D.

사무실 요청서: docs/office-migration/to-office-device-statistics-families-261102.md
계약:        contracts.py 의 Family*Row

화면·라우트는 아직 없습니다. 사무실 데이터가 오기 전에 집에서 같은 모양의 데이터를
먼저 갖춰 두려는 모듈입니다 — 답안지가 돌아오면 여기 OFFICE-VERIFY 를 하나씩
확정값으로 바꿉니다.

실물에서 확인된 것 (user-confirmed 2026-10-27, docs/datatables/hitachi/planstep_r3.txt)

- R3 step 원천은 계열별 index 입니다. 제품 수(prod_id)와 문서 수가 아래 규모의
  근거입니다 — hv 233 / 3,569, verify 92 / 1,200, provision 275 / 7,564.
  device 당 평균 step 수(약 15 / 13 / 27)가 :data:`FAMILY_SPECS` 의 범위입니다.
- skip_yn 은 "Y" / "N" / 빈 값 세 가지이고, recipe_id 는 한 device 안에서 여러
  step 이 함께 씁니다.
- 파라미터 원천은 HV-SEM 이 hvsem_idp_ver(cdsem 과 같은 형태 — 종류 column 없음,
  Mother_Para 있음), VeritySEM·Provision 은 측정 결과 data 입니다.
- Dummy·Align 이 있으면 측정 순서의 맨 앞에 옵니다(CD-SEM 에서 확인 — 이 계열은 Q15).

일부러 남긴 성질

- **계열 간 recipe 이름 충돌.** 이름 조각을 CD-SEM 과 같은 digest 로 고르므로, 같은
  device 를 두 계열이 재면 같은 recipe_id 가 계열마다 다른 파라미터로 나옵니다.
  조인 키가 (tool_type, recipe_id) 여야 하는 이유를 집에서 보이게 하려는 것입니다.
- **네 상태가 모두 나옵니다** (ok / empty / not_found / failed). 표 B 만 보면 셋이
  "행 없음" 으로 똑같습니다.
- **param_type 이 채워진 계열과 빈 계열이 섞입니다.** HV-SEM 은 빈 값(idp 에
  종류가 없음), AMAT 은 채움(추정) — 두 경로가 모두 집에서 실행됩니다.
- **표 A 에 있는데 표 D 에 없는 device**(계획은 있는데 최근 90일 측정 없음)와
  **표 D 에만 있는 device**(측정은 있는데 step 원본 없음 — CD-SEM 의 RX1R)가 섞입니다.

OFFICE-VERIFY (답안지 번호)

- M fab 에 이 계열 step 이 있는지와 규모(Q2) — device 수·step 수는 지어낸 값입니다.
- AMAT 의 param_type 존재(Q4), mother 부재(Q6), 상태 비율 — 전부 추정입니다.
- step 이름·recipe 이름·파라미터 이름 어휘는 CD-SEM mock 을 빌린 것입니다(Q7, Q16).
- AVIS/ICANS step 비율(Q17).

eqp_id 는 sem_list mock 에서 **그 계열·그 fab 의 장비**만 고릅니다. 장비가 없는 fab
에는 step 을 만들지 않습니다.

Internal module: mock.py 가 재노출합니다.
"""

from __future__ import annotations

import hashlib
import random
from datetime import timedelta
from functools import lru_cache
from typing import TypedDict

from backend.ebeam._tool_specs import model_to_tool_type
from backend.ebeam.device_statistics.contracts import (
    FamilyActivityRow,
    FamilyParamRow,
    FamilyRecipeStatusRow,
    FamilyStepRow,
    FamilyToolType,
)
from backend.ebeam.device_statistics.providers.recipe_params import (
    _assign_regions,
    _build_parameters,
    _has_helper_params,
)
from backend.ebeam.device_statistics.providers.recipe_population import (
    _OPER_PREFIXES,
    IMAGE_STEP_SUFFIXES,
    SHARED_RECIPE_RATIO,
    _recipe_name,
    _skip_yn,
    _step_name,
    is_exempt_job,
)


class _Spec(TypedDict):
    seed: int
    r3_lots: int
    r3_steps: tuple[int, int]
    m_lots_per_fab: int              # OFFICE-VERIFY (Q2)
    m_steps: tuple[int, int]         # OFFICE-VERIFY (Q2)
    source_kind: str                 # "idp" | "measurement"
    has_mother: bool                 # OFFICE-VERIFY (Q6) — AMAT
    typed_params: bool               # OFFICE-VERIFY (Q4) — AMAT
    status_weights: tuple[float, float, float, float]  # ok, empty, not_found, failed


FAMILY_SPECS: dict[FamilyToolType, _Spec] = {
    "hv-sem": {
        "seed": 20261102, "r3_lots": 233, "r3_steps": (10, 21),
        "m_lots_per_fab": 30, "m_steps": (4, 12),
        "source_kind": "idp", "has_mother": True, "typed_params": False,
        "status_weights": (0.95, 0.01, 0.03, 0.01),
    },
    "veritysem": {
        "seed": 20261103, "r3_lots": 92, "r3_steps": (8, 18),
        "m_lots_per_fab": 8, "m_steps": (3, 8),
        "source_kind": "measurement", "has_mother": False, "typed_params": True,
        "status_weights": (0.85, 0.02, 0.10, 0.03),
    },
    "provision": {
        "seed": 20261104, "r3_lots": 275, "r3_steps": (18, 37),
        "m_lots_per_fab": 15, "m_steps": (4, 12),
        "source_kind": "measurement", "has_mother": False, "typed_params": True,
        "status_weights": (0.88, 0.02, 0.07, 0.03),
    },
}

STATUSES = ("ok", "empty", "not_found", "failed")
IMAGE_STEP_RATIO = 0.03          # OFFICE-VERIFY (Q17)
ACTIVE_RATIO = 0.90              # 표 A device 중 최근 90일 측정이 있는 비율
NO_STEP_RATIO = 0.03             # 표 D 에만 있는 device 비율 (표 A device 수 대비)
WINDOW_DAYS = 90


def _kst(dt) -> str:
    """offset 없는 KST wall-clock — 실물 chg_tm 의 모양(statistics.py 와 같음)."""
    return (dt + timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")


def _digest(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def _param_type(name: str) -> str:
    """AMAT 원천에 종류 column 이 있다고 가정하고 채울 값(Q4). 비측정은 빈 값."""
    upper = name.upper()
    for kind in ("WAFER", "LEVEL", "EDGE_EX", "EDGE"):
        if upper.startswith(kind):
            return kind
    return "" if upper in ("DUMMY", "ALIGN") else "OTHER"


def _tools_by_fab(tool_type: FamilyToolType) -> dict[str, list[str]]:
    from backend.sem_list.providers import mock as sem_list_mock

    tools: dict[str, list[str]] = {}
    for row in sem_list_mock.get_sem_list():
        if model_to_tool_type(row["eqp_model_cd"]) == tool_type:
            tools.setdefault(row["fac_id"], []).append(row["eqp_id"])
    return {fab: sorted(set(ids)) for fab, ids in tools.items()}


def _r3_steps(rng: random.Random, tool_type, lot_cd, n, eqps, base_time) -> list[FamilyStepRow]:
    rows: list[FamilyStepRow] = []
    oper_seq, samp_seq = 0, 1
    for idx in range(n):
        if rows and rng.random() < 0.2:
            samp_seq += 1                  # 같은 공정의 두 번째 sample
        else:
            oper_seq, samp_seq = oper_seq + 10, 1
        oper_desc = _step_name(rng)
        if rng.random() < IMAGE_STEP_RATIO:
            oper_desc += " " + rng.choice(sorted(IMAGE_STEP_SUFFIXES))
        recipe_id = (
            rows[-1]["recipe_id"]
            if rows and rng.random() < SHARED_RECIPE_RATIO
            else _recipe_name(rng, lot_cd, idx)
        )
        rows.append({
            "tool_type": tool_type, "fac_id": "R3", "lot_cd": lot_cd,
            "oper_id": f"{rng.choice(_OPER_PREFIXES)}-{rng.randint(100, 999)}",
            "oper_desc": oper_desc, "oper_seq": oper_seq, "samp_seq": samp_seq,
            "recipe_id": recipe_id, "eqp_id": rng.choice(eqps),
            "skip_yn": _skip_yn(rng),
            "chg_tm": _kst(base_time - timedelta(hours=rng.randint(0, 24 * 120))),
        })
    return rows


def _m_steps(rng: random.Random, tool_type, fac_id, lot_cd, n, eqps) -> list[FamilyStepRow]:
    """M fab — 90일 창의 unique oper_det_desc. 순서·skip·chg_tm 이 없습니다."""
    rows: list[FamilyStepRow] = []
    seen: set[str] = set()
    for idx in range(n * 3):               # 이름이 겹치면 다시 뽑되 무한히는 아님
        if len(rows) == n:
            break
        oper_desc = _step_name(rng)
        if oper_desc in seen:
            continue
        seen.add(oper_desc)
        rows.append({
            "tool_type": tool_type, "fac_id": fac_id, "lot_cd": lot_cd,
            "oper_id": f"{rng.choice(_OPER_PREFIXES)}-{rng.randint(100, 999)}",
            "oper_desc": oper_desc, "oper_seq": None, "samp_seq": None,
            "recipe_id": _recipe_name(rng, lot_cd, idx), "eqp_id": rng.choice(eqps),
            "skip_yn": "", "chg_tm": "",
        })
    return rows


def _recipe_tables(
    tool_type: FamilyToolType, spec: _Spec, steps: list[FamilyStepRow], base_time,
) -> tuple[list[FamilyParamRow], list[FamilyRecipeStatusRow]]:
    first_eqp: dict[str, str] = {}
    for step in steps:
        first_eqp.setdefault(step["recipe_id"], step["eqp_id"])

    params: list[FamilyParamRow] = []
    statuses: list[FamilyRecipeStatusRow] = []
    kind = spec["source_kind"]
    for recipe_id in sorted(first_eqp):
        prng = random.Random(spec["seed"] ^ _digest(f"{tool_type}:{recipe_id}"))
        status = prng.choices(STATUSES, weights=spec["status_weights"])[0]
        when = base_time - timedelta(hours=prng.randint(0, 24 * 60))
        ref = f"v{prng.randint(1, 30)}" if kind == "idp" else (
            f"{first_eqp[recipe_id]}:{(when + timedelta(hours=9)):%Y%m%d%H%M%S}"
        )
        has_source = status in ("ok", "empty")
        statuses.append({
            "tool_type": tool_type, "recipe_id": recipe_id, "status": status,
            "source_kind": kind,  # type: ignore[typeddict-item]
            "source_ref": ref if has_source else "",
            "source_tm": _kst(when) if has_source else "",
            "note": "parse error: unexpected parameter block" if status == "failed" else "",
        })
        if status != "ok":
            continue

        built = _build_parameters(
            prng, bloated=prng.random() < 0.1, over_measured=False,
            exempt_job=is_exempt_job(recipe_id),
            helpers=_has_helper_params(f"{tool_type}:{recipe_id}"),
        )
        if spec["has_mother"]:
            _assign_regions(built, True, prng)
        for seq, param in enumerate(built, start=1):
            params.append({
                "tool_type": tool_type, "recipe_id": recipe_id, "param_seq": seq,
                "param_name": param["name"],
                "param_type": _param_type(param["name"]) if spec["typed_params"] else "",
                "point_count": param["point_count"],
                "mother": param["mother"] if spec["has_mother"] else None,
                "region": param["region"] if spec["has_mother"] else None,
            })
    return params, statuses


@lru_cache(maxsize=None)
def _tables(tool_type: FamilyToolType):
    # 순환 import 회피: mock.py 가 이 모듈을 맨 아래에서 재노출합니다.
    from backend.ebeam.device_statistics.providers import mock

    spec = FAMILY_SPECS[tool_type]
    rng = random.Random(spec["seed"])
    tools = _tools_by_fab(tool_type)
    catalog: dict[str, list[str]] = {"R3": [r["lot_cd"] for r in mock.get_r3_device_grp()]}
    for row in mock.get_device_desc():
        catalog.setdefault(row["fac_id"], []).append(row["lot_cd"])

    steps: list[FamilyStepRow] = []
    lots_by_fab: dict[str, list[str]] = {}
    for fac_id in sorted(tools):
        pool = catalog.get(fac_id, [])
        size = spec["r3_lots"] if fac_id == "R3" else spec["m_lots_per_fab"]
        lots = sorted(rng.sample(pool, min(size, len(pool))))
        lots_by_fab[fac_id] = lots
        for lot_cd in lots:
            if fac_id == "R3":
                steps += _r3_steps(rng, tool_type, lot_cd, rng.randint(*spec["r3_steps"]),
                                   tools[fac_id], mock.BASE_TIME)
            else:
                steps += _m_steps(rng, tool_type, fac_id, lot_cd,
                                  rng.randint(*spec["m_steps"]), tools[fac_id])

    params, statuses = _recipe_tables(tool_type, spec, steps, mock.BASE_TIME)

    activity: list[FamilyActivityRow] = []
    for fac_id, lots in lots_by_fab.items():
        active = [lot for lot in lots if rng.random() < ACTIVE_RATIO]
        spare = sorted(set(catalog.get(fac_id, [])) - set(lots))
        extra = rng.sample(spare, min(len(spare), max(1, round(len(lots) * NO_STEP_RATIO))))
        ranked = [
            {
                "tool_type": tool_type, "fac_id": fac_id, "lot_cd": lot_cd,
                "meas_count": mock._meas_count(f"{tool_type}:{lot_cd}"),
                "window_days": WINDOW_DAYS, "as_of": _kst(mock.BASE_TIME),
            }
            for lot_cd in active + extra
        ]
        ranked.sort(key=lambda r: (-r["meas_count"], r["lot_cd"]))
        activity += ranked  # type: ignore[arg-type]

    return tuple(steps), tuple(params), tuple(statuses), tuple(activity)


def get_family_steps(tool_type: FamilyToolType) -> list[FamilyStepRow]:
    """표 A."""
    return list(_tables(tool_type)[0])


def get_family_params(tool_type: FamilyToolType) -> list[FamilyParamRow]:
    """표 B — status == "ok" 인 recipe 만 행이 있습니다."""
    return list(_tables(tool_type)[1])


def get_family_recipe_status(tool_type: FamilyToolType) -> list[FamilyRecipeStatusRow]:
    """표 C — 표 A 의 distinct recipe 마다 한 행."""
    return list(_tables(tool_type)[2])


def get_family_activity(tool_type: FamilyToolType) -> list[FamilyActivityRow]:
    """표 D — fab 별로 meas_count 내림차순."""
    return list(_tables(tool_type)[3])
