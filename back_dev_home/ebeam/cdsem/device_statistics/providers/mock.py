"""Mock provider for cdsem device_statistics.

원본 테이블:  docs/datatables/r3_device_grp.txt, docs/datatables/device_desc.txt
계약:        docs/api-contracts/cdsem-device-statistics.yaml
픽스처:      back_dev_home/ebeam/cdsem/device_statistics/__fixtures__/

사무실 원천 (user-confirmed 2026-07-30)

이 mock 이 대역하는 실제 소스는 Redis 의 두 key 입니다. `device_info_hvm` 이
M 계열 양산(HVM) 카탈로그로 `_generate_device_desc()` 의 M11/M12/M14/M15/M16
rows 에 대응하고, `device_info_rnd` 가 R3 연구개발 카탈로그로
`_generate_r3_device_grp()` 의 fac_id="R3" rows 에 대응합니다. (문서에 기록된
이전 key 이름 device_desc / r3_device_grp 는 정정되었습니다.) 두 key 는
device-statistics 의 initial setup 카탈로그이며 요청에 따라 여기서 device
code 를 추출합니다 — 어느 한쪽이 다른 쪽의 상위 집합이 아니므로 office
어댑터는 두 key 를 모두 읽어야 합니다. device_desc 쪽 설명 컬럼은 사무실에서도
`ctn_desc` 이며, 예전 문서가 적어 둔 `stn_desc` 는 존재하지 않습니다.

이 mock 이 실물과 의도적으로 다른 점

- 결측: 실물은 빈 문자열 외에 실제 None/NaN 과 문자열 "None" 이 섞여 있으나,
  여기서는 빈 문자열("")만 생성합니다. 따라서 어댑터의 "None" -> ""
  정규화 경로는 mock 으로 검증되지 않습니다.
- 수명: 실물은 폐기된 lot_cd 까지 포함하지만 여기 rows 는 전부 유효한 것처럼
  보입니다 (recipe_tat 화면은 그래서 최근 60일 lot 과 교집합을 취합니다).

실제 컬럼/행 수/결측 분포는 사무실에서 아래로 확인합니다:

    .venv/bin/python -m scripts.inspect_device_info_keys

This module (plus its sibling `statistics.py` / `recipe_params.py` /
`rules.py` helper modules in this same `providers/` package) is
device_statistics's mock adapter. `data.py` is the feature's single public
import surface for routers and other features — this module implements the
mock behavior documented in MIGRATION.md and is never imported directly
except by `data.py`'s switch and by `recipe_tat`'s mock provider, which
imports `_lot_index` straight from here (mock fixtures interlocking with
mock fixtures — `_lot_index` is re-exported below from `statistics.py` for
exactly that reason: it must NOT go through the office/mock switch, or
office mode for device_statistics would break recipe_tat's mock).
"""

import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from back_dev_home.ebeam.cdsem.device_statistics.contracts import (
    DeviceDescRow,
    ParameterRow,
    R3DeviceGrpRow,
    RecipeInfoRow,
    RecipeParamsRow,
    SummaryRow,
    TrendBucket,
)


R3_ROW_COUNT = 2000
M_ROW_COUNT = 2000
M_FAC_IDS = ["M11", "M12", "M14", "M15", "M16"]

PLAN_CATG_TYPES = ["FULL", "ADTPJT", "MODULE", ""]
PROD_CATG_CODES = ["DRAM", "Tech", "Advanced", "FLASH", "NAND"]
R3_TECH_CODES = ["T1Z", "S128", "T1Y", "C20", "F12m", ""]
DEN_TYPES = ["16G", "1T", "512G", "256G", ""]
PROD_GROUP_TYPES = ["DDR4", "Memory Tech", "Advanced", "NAND", "Raw NAND", "HBM2E", "GDDR6", ""]
GEN_TYPES = ["1ST", "2ND", "4TH", "5TH", ""]
PLAN_GRADE_CODES = ["P1", "P2", "P3", "P4", "P5", ""]

M_TECH_NAMES = ["TP", "4G", "AA", "7D", "3D", "C2", "N2", "Q7", "R1", "None"]
M_LOT_PREFIX_BY_FAC = {
    "M11": "1",
    "M12": "2",
    "M14": "4",
    "M15": "5",
    "M16": "6"
}

DEV_PHASES = ["t-EV", "tev", "p-EV", "PV", "TV", "Pool", "pool"]
BASE_TIME = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
BASE36_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _base36(value: int, width: int) -> str:
    if value == 0:
        encoded = "0"
    else:
        chars: list[str] = []
        next_value = value

        while next_value:
            next_value, remainder = divmod(next_value, len(BASE36_ALPHABET))
            chars.append(BASE36_ALPHABET[remainder])

        encoded = "".join(reversed(chars))

    return encoded.rjust(width, "0")[-width:]


def _make_r3_lot_code(index: int) -> str:
    return f"R{_base36(index, 3)}"


def _make_m_lot_code(fac_id: str, index: int) -> str:
    prefix = M_LOT_PREFIX_BY_FAC[fac_id]

    if index % 4 == 0:
        return f"{prefix}{_base36(index, 2)}"

    return f"{prefix}{_base36(index, 3)}"


@lru_cache(maxsize=1)
def _generate_r3_device_grp() -> tuple[R3DeviceGrpRow, ...]:
    rng = random.Random(20260426)
    rows: list[R3DeviceGrpRow] = []

    for index in range(R3_ROW_COUNT):
        lot_cd = _make_r3_lot_code(index)
        prod_catg_cd = PROD_CATG_CODES[index % len(PROD_CATG_CODES)]
        tech_cd = rng.choice(R3_TECH_CODES)
        den_type = rng.choice(DEN_TYPES)
        phase = rng.choice(DEV_PHASES)
        timestamp = BASE_TIME - timedelta(hours=index * 3)

        rows.append({
            "id": f"R3-{index + 1:04d}",
            "fac_id": "R3",
            "plan_catg_type": rng.choice(PLAN_CATG_TYPES),
            "prod_catg_cd": prod_catg_cd,
            "tech_cd": tech_cd,
            "den_type": den_type,
            "prod_grp_typ": rng.choice(PROD_GROUP_TYPES),
            "gen_typ": rng.choice(GEN_TYPES),
            "lot_cd": lot_cd,
            "plan_grade_cd": rng.choice(PLAN_GRADE_CODES),
            "lake_load_tm": timestamp.strftime("%Y%m%d%H%M%S"),
            "ctn_desc": f"{phase} {prod_catg_cd} {tech_cd or 'NA'} {den_type or 'GEN'} development lot {lot_cd}"
        })

    return tuple(rows)


@lru_cache(maxsize=1)
def _generate_device_desc() -> tuple[DeviceDescRow, ...]:
    rng = random.Random(20260427)
    rows: list[DeviceDescRow] = []
    rows_per_fac = M_ROW_COUNT // len(M_FAC_IDS)

    for fac_id in M_FAC_IDS:
        for index in range(rows_per_fac):
            lot_cd = _make_m_lot_code(fac_id, index)
            tech_nm = M_TECH_NAMES[(index + rng.randint(0, 3)) % len(M_TECH_NAMES)]
            phase = rng.choice(DEV_PHASES)
            timestamp = BASE_TIME - timedelta(hours=(index * 2) + M_FAC_IDS.index(fac_id))

            # rnd_connector is a value device_desc stores natively — the R&D
            # code name a device carried before it graduated to mass
            # production. Generate it from this generator's own RNG without
            # consulting r3_device_grp; in reality the two tables come from
            # separate sources and any agreement between them is incidental.
            has_rnd_origin = rng.random() < 0.9
            rnd_connector = f"R{_base36(rng.randrange(36 ** 3), 3)}" if has_rnd_origin else ""

            rows.append({
                "id": f"{fac_id}-{index + 1:04d}",
                "fac_id": fac_id,
                "lot_cd": lot_cd,
                "ctn_desc": f"{phase} {fac_id} {tech_nm} device description lot {lot_cd}",
                "chg_tm": timestamp.isoformat().replace("+00:00", "Z"),
                "tech_nm": tech_nm,
                "rnd_connector": rnd_connector
            })

    return tuple(rows)


def get_r3_device_grp() -> list[R3DeviceGrpRow]:
    return list(_generate_r3_device_grp())


def get_device_desc(fac_ids: list[str] | None = None) -> list[DeviceDescRow]:
    rows = list(_generate_device_desc())

    if not fac_ids:
        return rows

    normalized_fac_ids = {fac_id.strip().upper() for fac_id in fac_ids if fac_id.strip()}

    if not normalized_fac_ids:
        return rows

    return [row for row in rows if row["fac_id"] in normalized_fac_ids]


# ---------------------------------------------------------------------------
# 공개 표면 재노출 — statistics.py 의 트렌드/요약 로직과 recipe_params.py /
# rules.py 를 본 모듈에서 가져옵니다. data.py 의 provider 스위치는 항상 본
# 모듈만 import 하도록 유지하기 위함입니다.
# 순환 import 회피: 위에서 BASE_TIME, get_r3_device_grp, get_device_desc 가
# 먼저 정의되었으므로 statistics.py/recipe_params.py 가 본 모듈을 (지연)
# import 할 때 충돌이 없습니다.
# ---------------------------------------------------------------------------
from .statistics import (  # noqa: E402  (의도된 후위 import)
    _lot_index,
    get_lot_index,
    get_weekly_trend_data,
)
from .recipe_params import get_recipe_params  # noqa: E402  (의도된 후위 import)
from .rules import get_rules  # noqa: E402  (의도된 후위 import)


__all__ = [
    "R3DeviceGrpRow",
    "DeviceDescRow",
    "RecipeInfoRow",
    "SummaryRow",
    "TrendBucket",
    "RecipeParamsRow",
    "ParameterRow",
    "BASE_TIME",
    "get_r3_device_grp",
    "get_device_desc",
    "get_weekly_trend_data",
    "get_recipe_params",
    "get_lot_index",
    "get_rules",
    "_lot_index",
]
