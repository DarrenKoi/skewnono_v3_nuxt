import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import TypedDict


class R3DeviceGrpRow(TypedDict):
    id: str
    fac_id: str
    plan_catg_type: str
    prod_catg_cd: str
    tech_cd: str
    den_type: str
    prod_grp_typ: str
    gen_typ: str
    lot_cd: str
    plan_grade_cd: str
    lake_load_tm: str
    ctn_desc: str


class DeviceDescRow(TypedDict):
    id: str
    fac_id: str
    lot_cd: str
    ctn_desc: str
    chg_tm: str
    tech_nm: str
    rnd_connector: str


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
