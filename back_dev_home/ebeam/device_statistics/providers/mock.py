"""Mock provider for cdsem device_statistics.

원본 테이블:  docs/datatables/hitachi/r3_device_grp.txt, docs/datatables/hitachi/device_desc.txt
계약:        docs/api-contracts/cdsem-device-statistics.yaml
픽스처:      back_dev_home/ebeam/device_statistics/__fixtures__/

사무실 원천 (user-confirmed 2026-07-31)

이 mock 이 대역하는 실제 소스는 Redis 의 두 key 입니다. `device_desc` 가
M 계열 양산 카탈로그로 `_generate_device_desc()` 의 M10/M11/M14/M15/M16
rows 에 대응하고, `r3_device_grp` 가 R3 연구개발 카탈로그로
`_generate_r3_device_grp()` 의 fac_id="R3" rows 에 대응합니다. 두 key 는
device-statistics 의 initial setup 카탈로그이며 요청에 따라 여기서 device
code 를 추출합니다 — 어느 한쪽이 다른 쪽의 상위 집합이 아니므로 office
어댑터는 두 key 를 모두 읽어야 합니다.

설명 컬럼은 `ctn_desc` 입니다 — 예전 문서가 `stn_desc` 로 적었던 적이 있어
office 어댑터가 두 이름을 모두 받아 줍니다.

이 mock 이 실물과 의도적으로 다른 점

- 결측: 실물은 빈 문자열 외에 실제 None/NaN 과 문자열 "None" 이 섞여 있으나,
  여기서는 빈 문자열("")만 생성합니다. 따라서 어댑터의 "None" -> ""
  정규화 경로는 mock 으로 검증되지 않습니다.
- 수명: 실물 카탈로그는 폐기된 lot_cd 까지 포함하므로 office 어댑터가
  ebeam_tas_lot_hist 최근 90일 창의 lot_cd 집합과 교집합을 취해 "현재 생산 중"
  만 목록에 남깁니다 (_active_lot_cds, user-confirmed 2026-08-04 — recipe_tat
  의 60일 필터와 같은 방식이되 창은 다릅니다). 이 mock 은 그 필터를 대역하지
  않고 생성된 rows 전부를 최근 활동이 있는 것처럼 돌려줍니다 — 어떤 lot 이
  실제로 최근에 측정됐는지는 mock 이 알 수 없는 사실이기 때문입니다.

실제 컬럼/행 수/결측 분포는 사무실에서 아래로 확인합니다:

    .venv/bin/python -m scripts.probes.inspect_device_info_keys

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

from back_dev_home._core.timefmt import iso_z
from back_dev_home.ebeam.device_statistics.para_buckets import _str_digest
from back_dev_home.ebeam.device_statistics.contracts import (
    DeviceDescRow,
    MeasActivityRow,
    ParameterRow,
    R3DeviceGrpRow,
    RecipeInfoRow,
    RecipeParamsRow,
    SummaryRow,
    TrendBucket,
)


R3_ROW_COUNT = 2000
M_ROW_COUNT = 2000
# 운영 중인 M-fab 전부입니다. 예전 mock에 있던 M12는 실재하지 않는 값이었고
# (docs/datatables/hitachi/sem_list.txt, user-confirmed 2026-08-03), sem_list의 FAC_IDS가
# 이 어휘의 진실입니다. 여기가 어긋나면 recipe_tat이 장비(sem_list)와
# lot(여기)을 fac_id로 짝지을 때 만나지 못하는 조합이 생깁니다.
M_FAC_IDS = ["M10", "M11", "M14", "M15", "M16"]

PLAN_CATG_TYPES = ["FULL", "ADTPJT", "MODULE", ""]
PROD_CATG_CODES = ["DRAM", "Tech", "Advanced", "FLASH", "NAND"]
R3_TECH_CODES = ["T1Z", "S128", "T1Y", "C20", "F12m", ""]
DEN_TYPES = ["16G", "1T", "512G", "256G", ""]
PROD_GROUP_TYPES = ["DDR4", "Memory Tech", "Advanced", "NAND", "Raw NAND", "HBM2E", "GDDR6", ""]
GEN_TYPES = ["1ST", "2ND", "4TH", "5TH", ""]
PLAN_GRADE_CODES = ["P1", "P2", "P3", "P4", "P5", ""]

M_TECH_NAMES = ["TP", "4G", "AA", "7D", "3D", "C2", "N2", "Q7", "R1", "None"]
M_LOT_PREFIX_BY_FAC = {
    "M10": "0",
    "M11": "1",
    "M14": "4",
    "M15": "5",
    "M16": "6"
}

# phase 와 Pool 은 **직교하는 두 축**입니다. 예전에는 이 목록이 "Pool"/"pool" 을
# phase 토큰에 섞어 두어(CONTEXT.md §Flagged ambiguities 가 정비 대상으로 표시해
# 둔 그것), 한 device 의 ctn_desc 가 Pool 이거나 phase 이거나 **둘 중 하나**였
# 습니다. 실물은 둘이 함께 옵니다 — "DRAM Pool제 (@Spica PV)"
# (user-confirmed 2026-08-25). 섞어 두면 "Pool 이 phase 를 이긴다" 는 경로가
# 집에서 한 번도 실행되지 않습니다(lotHealth.extractStage, ruleEngine
# .selectorMatches 둘 다).
DEV_PHASES = ["t-EV", "tev", "p-EV", "PV", "TV"]

# ctn_desc 에 나타나는 Pool 표기. office `_family_of` 의 `_POOL_TOKEN`(=pool|풀)
# 이 셋 다 잡습니다.
POOL_TOKENS = ["Pool제", "Pool", "풀"]

# 실물 ctn_desc 에 섞여 있는 개발코드 명. "Spica" 만 실제로 본 값이고
# (user-confirmed 2026-08-25), 나머지는 형태만 맞춘 자리 채움입니다.
DEV_CODES = ["Spica", "Vega", "Altair", "Rigel"]  # OFFICE-VERIFY (Spica 제외)

# VG·RTC·Cubic 은 한 제품군인데 **표기가 여럿**입니다 (user-confirmed
# 2026-08-25). office `_family_of` 의 `_VG_TOKEN` 이 이 다섯을 모두 잡으므로,
# mock 도 다섯을 고루 내야 그 패턴의 각 가지가 집에서 실행됩니다.
VG_TOKENS = ["Vertical Gate", "VerticalGate", "Vertical", "VG", "RTC", "Cubic"]


def _dev_ctn_desc(rng: random.Random, phase: str, head: str, tail: str) -> str:
    """device 설명문 한 줄.

    세 제품군을 실물 비율에 가깝게 섞습니다 — **VG > Pool > Core** 우선순위가
    집에서 실제로 실행되도록.

    - 약 1/8 은 VG·RTC·Cubic 이고, 그중 일부는 Pool 토큰까지 함께 답니다.
      그때 family 는 VG 여야 합니다(VG 가 Pool 을 이깁니다).
    - VG 는 보통 phase 표현을 쓰지 않으므로(user-confirmed 2026-08-25)
      대부분 phase 토큰 없이 냅니다 — `rules.py` 의 VG 셀이 phase 를 키잉하지
      않는 이유가 바로 이것이고, 그 조합이 mock 에 없으면 그 결정이 옳은지
      집에서 확인할 수 없습니다.
    - 약 1/4 은 Pool 이고, 그 경우 **Pool 토큰과 phase 토큰이 한 문자열에
      같이** 실립니다("DRAM Pool제 (@Spica PV)"). 판정·칩 양쪽에서 Pool 이
      phase 를 이깁니다.
    """
    code = rng.choice(DEV_CODES)

    if rng.random() < 0.125:
        vg = rng.choice(VG_TOKENS)
        # VG 중 1/5 은 Pool 토큰도 답니다 — 겹칠 때 VG 가 이기는지 보는 표본.
        pool = f" {rng.choice(POOL_TOKENS)}" if rng.random() < 0.2 else ""
        # VG 중 1/4 만 phase 표현을 답니다.
        tag = f" (@{code} {phase})" if rng.random() < 0.25 else f" (@{code})"
        return f"{head} {vg}{pool}{tag} {tail}"

    if rng.random() < 0.25:
        pool = rng.choice(POOL_TOKENS)
        return f"{head} {pool} (@{code} {phase}) {tail}"

    return f"{phase} {head} {tail}"
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
            "ctn_desc": _dev_ctn_desc(
                rng, phase,
                f"{prod_catg_cd} {tech_cd or 'NA'} {den_type or 'GEN'}",
                f"development lot {lot_cd}",
            )
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
                "ctn_desc": _dev_ctn_desc(
                    rng, phase, f"{fac_id} {tech_nm}",
                    f"device description lot {lot_cd}",
                ),
                "chg_tm": iso_z(timestamp),
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


def _meas_count(lot_cd: str) -> int:
    """이 lot 의 최근 90일 측정 건수 대역 — lot_cd 만으로 결정론적입니다.

    실물 분포는 소수 양산 주력 device 에 측정이 몰리는 heavy-tail 이므로,
    균등 난수 대신 제곱으로 눌러 상위 소수 + 긴 꼬리 모양을 만듭니다. 절대값은
    mock 이 알 수 없는 사실이라 자릿수(수십~수천)만 실물스럽게 잡습니다.
    """
    digest = _str_digest(lot_cd)
    unit = ((digest * 2654435761) & 0xFFFFFFFF) / 0xFFFFFFFF  # 0.0 ~ 1.0
    return 10 + round((unit ** 4) * 4990)


def get_meas_activity(fac_id: str) -> list[MeasActivityRow]:
    """한 fab 의 lot_cd 별 최근 측정 건수, meas_count 내림차순.

    원천(office)은 ebeam_tas_lot_hist 최근 90일의 lot_cd terms 집계입니다.
    mock 은 그 창의 실제 활동을 알 수 없으므로 카탈로그의 lot 전부에
    결정론적 가짜 건수를 부여합니다 — 순위 화면(측정 상위 N 필터)이 집에서
    안정적으로 동작하는 것이 목적입니다. 같은 lot_cd 는 항상 같은 순위입니다.
    """
    wanted = fac_id.strip().upper()
    rows: list[DeviceDescRow] | list[R3DeviceGrpRow]
    # 빈 fab 은 빈 순위입니다 — office 어댑터와 같은 판단입니다. 이 가드가
    # 없으면 get_device_desc([""]) 의 빈-토큰 경로로 떨어져 M-fab 전체 행이
    # 돌아왔고, 프런트가 빈 fab 을 보내는 버그가 집에서는 fab 을 가로지르는
    # 순위로, 사무실에서는 빈 화면으로 서로 다르게 보였습니다.
    if not wanted:
        return []
    if wanted.startswith("R"):
        rows = [r for r in get_r3_device_grp() if r["fac_id"].strip().upper() == wanted]
    else:
        rows = get_device_desc([wanted])

    ranked: list[MeasActivityRow] = [
        {"lot_cd": row["lot_cd"], "meas_count": _meas_count(row["lot_cd"])}
        for row in rows
    ]
    # 동률은 lot_cd 로 갈라 정렬을 결정론적으로 유지합니다.
    ranked.sort(key=lambda entry: (-entry["meas_count"], entry["lot_cd"]))
    return ranked


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
    get_weekly_trend_data,
)
from .recipe_params import get_recipe_params  # noqa: E402  (의도된 후위 import)
from .rules import get_rules  # noqa: E402  (의도된 후위 import)
from .snapshot_store import (  # noqa: E402  (의도된 후위 import)
    sweep_weekly_snapshots,
    write_weekly_snapshot,
)


__all__ = [
    "R3DeviceGrpRow",
    "DeviceDescRow",
    "RecipeInfoRow",
    "SummaryRow",
    "TrendBucket",
    "RecipeParamsRow",
    "ParameterRow",
    "MeasActivityRow",
    "BASE_TIME",
    "get_r3_device_grp",
    "get_device_desc",
    "get_meas_activity",
    "get_weekly_trend_data",
    "get_recipe_params",
    "get_rules",
    "_lot_index",
    "write_weekly_snapshot",
    "sweep_weekly_snapshots",
]
