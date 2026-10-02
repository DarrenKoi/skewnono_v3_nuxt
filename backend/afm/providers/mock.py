"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본 데이터: AFM 장비 raw 파일 — docs/datatables/afm/afm_raw_files.txt
            (회신 원문 docs/afm/office-data-findings.md, 이관 이력 docs/afm-migration-plan.md)
계약:        docs/api-contracts/afm.yaml
픽스처:      backend/afm/__fixtures__/

AFM 은 단일 측정 행(`AfmMeasurementRow`) 보다 풍부한 디테일·프로파일·이미지 응답
구조를 가집니다. 함수별 반환 형태가 다르므로 픽스처에 엔드포인트별 샘플을 모두
캡처해 사무실 LLM이 형태를 한눈에 볼 수 있도록 합니다.

이 mock 이 대신하는 것은 각 장비에서 추출한 **raw 파일**(ETL 이전)입니다. ETL 이후
Redis 색인·MinIO 객체의 형태는 아직 회신되지 않았으므로, 목록 행의 키와
`*_dir_list` 값의 뜻(파일명인지 MinIO 경로인지)은 2025-08 요구사항의 가정
그대로입니다 (OFFICE-VERIFY). 적재 형태 가운데 먼저 확인된 것은 profile 하나입니다 —
X/Y/Z parquet 에 객체 metadata(XUnit·YUnit·ZUnit·DataSize·SurfaceSize)가 붙습니다.

확인되어 그대로 재현하는 것 (office 확인 2026-10-02, 회신 4회):
- 장비는 MAP608 · MAPC01 · 5EAP1501 이고 MAPC01=R3, 5EAP1501=M15 입니다.
- 파일명은 `#` 구분이며 장비마다 필드 순서가 다르고, 빈자리는 `NA` 입니다.
  - MAP608 의 첫 시각은 **세션(폴더) 시작 시각**이라 같은 세션의 측정들이 공유합니다.
    뒤 시각이 측정 시작이고, 오래된 파일은 그 자리가 `NA` 입니다. 그때 Info 의
    `Start Time` 은 첫 시각과 같습니다.
  - MAPC01 은 `_Info.csv` 가 모든 측정에 있고 data CSV 는 같은 이름에서 `_Info` 를 뺀
    것입니다. 측정 한 건은 앞 4필드(date#time#recipe#slot)이며, 같은 sample 이 하루에
    여러 번 다시 측정되어 시각만 다릅니다. lot 은 파일명에 없고(NA) Info 의 `Lot ID` 에 있습니다.
  - 5EAP1501 의 끝은 RECIPE+LOT+SAMPLE 을 구분자 없이 이은 원본 파일명이고 접미
    (`_SOP_LEFT_UR` 등)가 붙기도 합니다. SAMPLE_ID 는 `<lot>.<nn>` 입니다.
- recipe 명에는 세 장비 모두 공백·괄호·소문자가 들어갈 수 있습니다 (`Fi-Tapping TEST`,
  `RQQA_PFH_MONF (1)`, `xy scanner opm`, `zeroscan 5point pm`).
- 어떤 파일(data CSV·profile txt·이미지)이 있는지는 **recipe 설정**이 정합니다. 없는 것이
  정상 상태이므로 `has_*` 와 `*_dir_list` 는 행 번호가 아니라 recipe 에서 나옵니다.
  5EAP1501 은 profile txt 가 없습니다.
- point 수도 recipe 가 정하며 1~36 까지 실측되었습니다.
- 측정 컬럼은 recipe 마다 다르고 모두 `(nm)` 를 포함합니다 — `Left_H`/`Right_H`/`Ref_H`,
  `Dishing_H`, `Bottom_H`/`Top_H`, `Ref_Range`/`Left_TRIM_H`, `ROUGHNESS_RANGE`/`Ra`/`Rq`,
  `Pad_1_H`…, `1_Minimum`…`51_Minimum`, `RZ1_Minimum`…, `Line1_Residue_H`, `SITE19_21_H`.
- Summary block 의 이름은 method 명이고 한 파일에 여러 개일 수 있습니다
  (`Profile_LEFT_UL` + `Profile_RIGHT_UL`). Data 도 block 마다 나뉘고 block 은 point 마다
  한 행을 냅니다. block 마다 컬럼이 다를 수 있습니다 — 실측된 것은 중단된 뒤쪽 block 이
  측정 컬럼 없이 STOPPED 행만 남기는 경우이고, 그 block 은 Summary 가 비어 있습니다.
- **block 은 순서로만 맞춥니다.** `Method_ID` 는 한 파일의 모든 block 에서 같은 값이라
  (숫자 `2`, 또는 `L1_XDEC_5MM_LINE` 같은 문자열) block 을 가리는 키가 아닙니다.
- Summary 가 없는 파일(Info 뒤에 바로 Data), 표가 없는 Data 도 있습니다.
- 위치 키는 4자리 point 번호입니다 (`Point No`=1 ↔ 파일명 `_0001`). Site ID 를 기록하는
  recipe 만 `Site ID`·`Site X`·`Site Y` 컬럼을 갖고, 그때 파일명은
  `_0004_X000_Y-002_0002_Height.txt` 처럼 Site ID 뒤에 point 번호가 붙습니다.
  `Site X`·`Site Y` 는 Site ID 안의 숫자와 같고 단위가 없습니다.
- `State` 는 COMPLETED · FAILED · STOPPED 셋입니다. point 가 하나면 STDEV·RANGE 는 0.0 입니다.
- Info 의 값은 빈 문자열일 수 있습니다 (`Carrier ID`, `Last Pick Up Time`, `Last Put Back Time`).
- Profile 격자는 MAP608 512×64, MAPC01 은 1D(N×1, 1024~16384)와 2D 혼재입니다. 1D 는 Y 가
  0 으로 고정되고 DataSize(`1024 x 1`)로 구분합니다. 단위는 통일하지 않고 파일마다
  um/nm/pm/Pixel 로 다릅니다.

지어냈거나 일부러 다른 것 (OFFICE-VERIFY):
- MAP608 의 fab `PKG` — 사무실 답은 "미정"입니다(raw 에 fab 필드가 없음).
- recipe 명 가운데 실측된 것은 `BSOXCMP_CORRELATION_36PT`·`RL1A_LPCCMP_CMPWEAK2`·
  `RX1A_M0A_COT_X_PDG`·`VED_BS_TOP01`·`RL1C_L1_XDEC_5MM_LINE`·`VM_GTFILLOX_5PT_R1`·
  `Fi-Tapping TEST`·`RQQA_PFH_MONF (1)`·`xy scanner opm`·`zeroscan 5point pm` 이고 나머지는
  지어냈습니다. 어느 recipe 가 어느 장비·method·파일 종류·point 수를 갖는지는 일부만
  확인된 대응입니다.
- lot ID 는 실측 예(`MON69683`, `5PNN1768`)의 생김새만 따랐습니다. MAP608 의 SAMPLE_ID 와
  MAPC01 의 원본 파일명도 `<lot>.<nn>` 이라고 보았습니다.
- MAPC01·5EAP1501 의 profile·이미지 파일명에서 위치 키 앞부분, MAPC01 의 2D 격자 크기.
- Site ID recipe 에서 한 Site 에 point 가 몇 개인지 — 파일명 예(`0004…_0002`)로 여럿일 수
  있다는 것만 알고, mock 은 한 recipe 에만 Site 당 2개를 둡니다.
- 숫자가 아닌 `Method_ID` 는 recipe 명에서 첫 토막을 뺀 것으로 만들었습니다(실측 한 건이
  그 모양입니다). 컬럼 이름이 `Method_ID` 인지 `Method ID` 인지도 회신마다 달랐습니다.
- `Valid` 는 FALSE 가 아직 실측되지 않았습니다. mock 은 일부를 False 로 냅니다.
- data 행의 나머지 키(`X (um)`, `<측정명>_Valid`, `Mileage` …)와 Information 의 다른 키.
- 측정값의 수준·추세·퍼짐은 전부 지어낸 것입니다. recipe·컬럼마다 고정된 수준(55~120 nm)에
  측정 시각에 비례하는 완만한 드리프트(하루 ±0.4 nm 이내), sample(lot+slot) 공통 오프셋
  (σ 0.8 nm, 재측정끼리 같음), 중심에서 바깥으로 커지는 site 패턴(반지름²당 0.25 nm),
  포인트 노이즈(σ 0.6 nm)를 더하고, 9건에 1건꼴로 +7.5 nm 이탈이 FAILED·Valid=FALSE·
  Approach Count 증가와 함께 옵니다. 시계열 비교가 집에서도 추세·관리선 밖·포인트 패턴·
  재현성을 잡을 수 있게 둔 구조이지 실측 값 범위가 아닙니다. 드리프트는 BASE_TIME 기준
  절대 시각의 함수라 파일이 오래돼도 값이 바뀌지 않습니다.
- Summary 는 그 block 의 행에서 계산합니다. STDEV 는 표본 표준편차(ddof=1)이고 Valid 는
  거르지 않습니다.
- "method 명 줄만 있는 빈 Summary" 는 행 목록으로는 "Summary 없음"과 구분되지 않아 같은 모양으로 냅니다.
- 시각의 시간대는 미정입니다(장비 현지 시각, KST 로 추정).
- 목록은 **오늘 날짜에서 끝납니다**(KST 기준). 하루가 지나면 하루치가 새로 생기고
  가장 오래된 하루치가 빠지며, 이미 있던 파일의 이름·lot·내용은 바뀌지 않습니다. 오늘
  측정의 시각은 고정이라 조회 시각보다 뒤일 수 있습니다.
- 시작 시각이 `NA` 인 "오래된 파일"은 실제로는 어느 시점 이전의 파일이지만, mock 은 며칠
  간격으로 되풀이되는 구간으로 냅니다(오늘 기준 목록에도 항상 섞이도록).
- profile metadata 의 `SurfaceSize` 값 형식, Pixel 축의 길이 환산(근거 없음).
- 이미지는 자리 표시 SVG 입니다. 실제는 webp 변환본이 있습니다.
- 원본 TIFF 는 MinIO 에 있고 내려받을 수 있어야 합니다(user-confirmed 2026-10-03). mock 은
  Result 이미지마다 256x256 8bit 회색조 TIFF 를 지어냅니다. 원본의 파일명(변환본 이름에서
  확장자만 `.tiff` 로 바꾼 것으로 가정), 크기·bit 수·장비 전용 태그, MinIO 경로, 보존
  기간은 모두 OFFICE-VERIFY 입니다.
"""

import hashlib
import html
import io
import math
import random
import statistics
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from backend.afm.contracts import AfmMeasurementRow, AfmOriginalFile, AfmProfileMeta


__all__ = [
    "AfmMeasurementRow",
    "normalize_tool",
    "get_tools",
    "list_afm_files",
    "get_afm_file_detail",
    "get_profile_points",
    "get_profile_meta",
    "get_profile_image_svg",
    "list_analysis_images",
    "get_analysis_image_svg",
    "get_tiff_original",
]


ToolConfig = dict[str, Any]

# The day the row numbering is anchored on. Row 0 is this day's first
# measurement; every later day counts down from it, so a day's files are the
# same whichever day the list is read on.
BASE_TIME = datetime(2026, 4, 24, 9, 30, 0, tzinfo=timezone.utc)


# Korea has no DST, so a fixed offset is exact (the same choice, for the same
# reason, as ebeam/recipe_tat's mock).
KST = timezone(timedelta(hours=9), "KST")


def _today() -> date:
    """The list's newest day, in KST: the viewer's "오늘" is a Korean date, and
    a UTC host would otherwise serve yesterday's list until 09:00.
    A function so a test can pin it.
    """
    return datetime.now(KST).date()


# (Site X, Site Y) of each measured position, centre outwards; 36 is the most seen.
SITE_LAYOUT = tuple(sorted(
    ((site_x, site_y) for site_x in range(-3, 3) for site_y in range(-3, 3)),
    key=lambda position: (position[0] ** 2 + position[1] ** 2, position)
))
SUMMARY_ITEMS = ("MEAN", "STDEV", "MIN", "MAX", "RANGE")
# A point fails now and then; STOPPED rows come only from a block that stopped
# (OFFICE-VERIFY: the real failure rate is unknown).
STATE_CODES = ("COMPLETED",) * 24 + ("FAILED",)

# A profile file states its own X/Y/Z units; nothing unifies them. The factors turn
# the mock's um (lateral) and nm (height) into the unit a file declares.
_UM_UM_NM = ("um", "um", "nm")
_LATERAL_PER_UM = {"um": 1.0, "nm": 1e3, "pm": 1e6}
_HEIGHT_PER_NM = {"um": 1e-3, "nm": 1.0, "pm": 1e3}
# Lateral length of a scan line.
_SCAN_UM = 50

IMAGE_TYPE_FIELDS: dict[str, str] = {
    "align": "align_dir_list",
    "tip": "tip_dir_list",
    "capture": "capture_dir_list",
    "tiff": "tiff_dir_list",
}

_IMAGE_TYPE_ACCENT: dict[str, str] = {
    "align": "#2563eb",
    "tip": "#d97706",
    "capture": "#7c3aed",
    "tiff": "#0f766e",
}

def _numbered(template: str, count: int) -> tuple[str, ...]:
    return tuple(template.format(number) for number in range(1, count + 1))


_HEIGHTS = ("Left_H (nm)", "Right_H (nm)", "Ref_H (nm)")
_ROUGHNESS = ("ROUGHNESS_RANGE (nm)", "Ra (nm)", "Rq (nm)")

# What a recipe is configured to write, which is the only thing that decides
# what exists: `columns` of its data CSV (None = no data CSV), `methods` naming
# its Summary/Data blocks, how many `points`, whether rows carry a `site_id`
# (and then how many points `per_site`), `profile` txt or not, and which
# `images`. `method_id` is the Method_ID every block of the recipe reports;
# left out, it is the recipe name without its first token.
RECIPES: dict[str, dict[str, Any]] = {
    "BSOXCMP_CORRELATION_36PT": {
        "columns": ("Bottom_H (nm)", "Top_H (nm)"), "methods": ("Correlation",),
        "points": 36, "site_id": True, "profile": True, "images": ("tiff", "align", "tip")
    },
    "VED_BS_TOP01": {
        "columns": _HEIGHTS, "methods": ("Profile_LEFT_UL", "Profile_RIGHT_UL"),
        "points": 10, "site_id": True, "per_site": 2, "profile": True, "images": ("tiff",)
    },
    "CMP_POST": {
        "columns": _HEIGHTS, "methods": ("Profile_LEFT_UL", "Profile_RIGHT_UL"),
        "points": 9, "site_id": True, "profile": True, "images": ("tiff", "tip")
    },
    "Fi-Tapping TEST": {
        "columns": _ROUGHNESS, "methods": ("Roughness",),
        "points": 1, "site_id": False, "profile": True, "images": ("align",)
    },
    "ROUGHNESS_SCAN": {
        "columns": _ROUGHNESS, "methods": ("Roughness",),
        "points": 5, "site_id": False, "profile": True, "images": ("tiff",)
    },
    "FSOXCMP_DISHING_9PT": {
        "columns": ("Dishing_H (nm)",), "methods": ("Dishing",),
        "points": 9, "site_id": True, "profile": False, "images": ("tiff", "tip")
    },
    "ETCH_TRIM": {
        "columns": ("Ref_Range (nm)", "Left_TRIM_H (nm)"), "methods": ("Trim Height",),
        "points": 13, "site_id": False, "profile": False, "images": ("tiff", "align")
    },
    "PAD_HEIGHT_3PAD": {
        "columns": _numbered("Pad_{}_H (nm)", 3), "methods": ("Step Height",),
        "points": 5, "site_id": False, "profile": True, "images": ()
    },
    "RL1A_LPCCMP_CMPWEAK2": {
        "columns": ("Line1_Residue_H (nm)",), "methods": ("Line Residue",),
        "points": 17, "site_id": True, "profile": True, "images": ("tiff",)
    },
    "RX1A_M0A_COT_X_PDG": {
        "columns": ("SITE19_21_H (nm)",), "methods": ("Step Height",),
        "points": 21, "site_id": True, "profile": False, "images": ("tiff", "align")
    },
    "RQQA_PFH_MONF (1)": {
        "columns": None, "methods": (),
        "points": 5, "site_id": True, "profile": True, "images": ("tiff",)
    },
    "RL1C_L1_XDEC_5MM_LINE": {
        "columns": ("Line1_Residue_H (nm)",), "methods": ("Line Residue",),
        "points": 3, "site_id": False, "profile": True, "images": ()
    },
    "VM_GTFILLOX_5PT_R1": {
        "columns": ("Bottom_H (nm)", "Top_H (nm)"), "methods": ("Correlation",),
        "points": 5, "site_id": True, "profile": False, "images": ("tiff", "align")
    },
    "xy scanner opm": {
        "columns": _numbered("RZ{}_Minimum (nm)", 12), "methods": ("Trench Depth",),
        "points": 1, "site_id": False, "profile": False, "images": (), "method_id": 2
    },
    "zeroscan 5point pm": {
        "columns": _numbered("{}_Minimum (nm)", 9), "methods": ("Trench Depth",),
        "points": 5, "site_id": False, "profile": False, "images": ("tiff", "tip")
    },
    "TRENCH_MIN_51LINE": {
        "columns": _numbered("{}_Minimum (nm)", 51), "methods": ("Trench Depth",),
        "points": 13, "site_id": True, "profile": False, "images": ("tiff",),
        "method_id": 2
    }
}

# Per tool: `filename` is the raw file name's field order, `profile_grids` the
# (nx, ny) shapes its profile txt comes in (empty = the tool writes no profile
# txt) and `profile_units` the X/Y/Z unit sets those files declare.
TOOL_CONFIGS: dict[str, ToolConfig] = {
    "MAP608": {
        "tool_id": "map608",
        "fab": "PKG",
        "row_count": 36,
        "lot_prefixes": ("T7HQR", "T3HQR", "TT032", "CRAP1"),
        "recipes": (
            "BSOXCMP_CORRELATION_36PT",
            "VED_BS_TOP01",
            "Fi-Tapping TEST",
            "PAD_HEIGHT_3PAD",
            "FSOXCMP_DISHING_9PT",
            "ETCH_TRIM"
        ),
        # The leading time is the session (folder) start, shared by the session's
        # measurements; the trailing one is the measurement start, NA on old files.
        "filename": "#{date}#{time}#{recipe}#{sample}#{lot}#{start}#.csv",
        "session_size": 3,
        "profile_grids": ((512, 64),),
        "profile_units": (_UM_UM_NM,)
    },
    "MAPC01": {
        "tool_id": "mapc01",
        "fab": "R3",
        "row_count": 28,
        "lot_prefixes": ("MON69", "MON70", "RL1C0"),
        "recipes": (
            "RQQA_PFH_MONF (1)",
            "RL1A_LPCCMP_CMPWEAK2",
            "RL1C_L1_XDEC_5MM_LINE",
            "ROUGHNESS_SCAN",
            "RX1A_M0A_COT_X_PDG",
            "CMP_POST"
        ),
        # The lot is not in the name (NA); it is read from the Info section. The last
        # segment is the tool's original file name, and the data CSV drops `_Info`.
        "filename": "#{date}#{time}#{recipe}#{slot}#NA#NA#{sample}_Info.csv",
        # The same sample is measured again later the same day; only the time differs.
        "repeats": 3,
        "profile_grids": ((1024, 1), (512, 64), (4096, 1), (16384, 1)),
        "profile_units": (
            _UM_UM_NM,
            ("nm", "nm", "nm"),
            ("um", "um", "pm"),
            ("Pixel", "Pixel", "nm")
        )
    },
    "5EAP1501": {
        "tool_id": "5eap1501",
        "fab": "M15",
        "row_count": 30,
        "lot_prefixes": ("5PNN17", "5PNN18", "5PMM20"),
        "recipes": (
            "xy scanner opm",
            "TRENCH_MIN_51LINE",
            "zeroscan 5point pm",
            "VM_GTFILLOX_5PT_R1"
        ),
        # The tail is the tool's original file name: RECIPE + LOT + SAMPLE run
        # together with no separator, sometimes with a suffix such as _SOP_LEFT_UR.
        "filename": "#{date}#{time}#{recipe}#{sample}#{lot}#NA#{recipe}{lot}{sample}{suffix}.csv",
        "profile_grids": (),
        "profile_units": ()
    }
}


def normalize_tool(tool_name: str | None) -> str:
    if not tool_name:
        return "MAP608"

    normalized = tool_name.strip().upper()
    if not normalized:
        return "MAP608"

    return normalized


def get_tools() -> list[dict[str, str]]:
    return [
        {
            "id": config["tool_id"],
            "name": tool_name,
            "label": tool_name,
            "fab": config["fab"]
        }
        for tool_name, config in TOOL_CONFIGS.items()
    ]


def list_afm_files(tool_name: str | None = None) -> list[AfmMeasurementRow]:
    tool = normalize_tool(tool_name)
    return list(_generate_measurements(tool, _today()))


@lru_cache(maxsize=256)
def get_afm_file_detail(
    filename: str,
    tool_name: str | None = None
) -> dict[str, Any] | None:
    row = _find_measurement(filename, tool_name)
    if row is None:
        return None

    rng = random.Random(_seed_for("detail", row["tool_name"], row["filename"]))
    recipe = RECIPES[row["recipe_name"]]
    positions = _positions(recipe)
    # A recipe with no data CSV has no blocks, so both tables stay empty.
    columns = recipe["columns"] or ()
    method_id = recipe.get("method_id", row["recipe_name"].split("_", 1)[-1])
    # A measurement stopped part-way leaves its later blocks with rows but no values.
    stopped_early = (
        len(recipe["methods"]) > 1
        and _seed_for("stopped", row["tool_name"], row["filename"]) % 3 == 0
    )
    excursion = _is_excursion(row)
    summary: list[dict[str, Any]] = []
    detail: list[dict[str, Any]] = []

    for method_index, method in enumerate(recipe["methods"]):
        stopped = stopped_early and method_index > 0
        bases = [_baseline(row, column, method_index) for column in columns]
        block_rows: list[dict[str, Any]] = []

        for key, site_id, (site_x, site_y), point_no in positions:
            record: dict[str, Any] = {"measurement_point": key}
            if site_id:
                record.update({"Site ID": site_id, "Site X": site_x, "Site Y": site_y})
            record.update({
                "Point No": point_no,
                "X (um)": round(site_x * 8000 + rng.uniform(-100, 100), 1),
                "Y (um)": round(site_y * 8000 + rng.uniform(-100, 100), 1),
                "Method_ID": method_id,
                "State": (
                    "STOPPED" if stopped
                    else "FAILED" if excursion and rng.random() < 0.3
                    else rng.choice(STATE_CODES)
                ),
                "Valid": rng.random() > (0.3 if excursion else 0.08)
            })
            if not stopped:
                bowl = _BOWL_NM * (site_x ** 2 + site_y ** 2)
                for column, base in zip(columns, bases, strict=True):
                    record[column] = round(base + bowl + rng.gauss(0, _POINT_NOISE_NM), 2)
                    record[f"{column.removesuffix(' (nm)')}_Valid"] = rng.random() > 0.06
            record.update({
                "Pick Up Count": rng.randint(1, 10),
                "Sample Count": rng.randint(1, 5),
                "Approach Count": rng.randint(1, 3) + (rng.randint(1, 2) if excursion else 0),
                "Mileage": round(rng.uniform(2, 98), 1)
            })
            block_rows.append(record)

        detail.extend(block_rows)
        if not stopped:
            summary.extend(_summary_records(method, block_rows, columns))

    # Both were seen in real files: one with no Summary, one whose Data has no table.
    oddity = _seed_for("oddity", row["tool_name"], row["filename"]) % 12
    if oddity == 0:
        summary = []
    elif oddity == 1:
        detail = []

    clean_filename = _strip_known_extension(row["filename"])
    start_time = _display_start_time(row)

    return {
        "filename": row["filename"],
        "tool": row["tool_name"],
        "pickle_filename": f"{clean_filename}.pkl",
        "information": {
            "Lot ID": row["lot_id"],
            "Recipe ID": row["recipe_name"],
            "Carrier ID": "" if rng.random() < 0.2 else f"CAR{rng.randint(100, 999)}",
            "Sample ID": f"{row['lot_id']}.{row['slot_number']}",
            "Start Time": start_time,
            "Last Pick Up Time": "" if rng.random() < 0.3 else start_time,
            "Last Put Back Time": "" if rng.random() < 0.3 else start_time,
            "Tool": row["tool_name"],
            "Fab": row["fab"],
            "Operator": f"OP{rng.randint(1000, 9999)}",
            "Measurement": row["measured_info"]
        },
        "summary": summary,
        "data": detail,
        "available_points": [key for key, *_ in positions]
    }


def get_profile_points(
    filename: str,
    point: str,
    tool_name: str | None = None,
    site_info: dict[str, str | int | None] | None = None
) -> list[dict[str, float]] | None:
    row = _find_measurement(filename, tool_name)
    if row is None or not row["has_profile"]:
        return None

    seed_parts = [
        "profile",
        row["tool_name"],
        row["filename"],
        point,
        str(site_info or {})
    ]
    rng = random.Random(_seed_for(*seed_parts))
    nx, ny, (x_unit, y_unit, z_unit) = _profile_layout(row)
    step = _SCAN_UM / (nx - 1)
    z_base = rng.uniform(80, 120)
    peak1_x = rng.uniform(25, 50)
    peak1_y = rng.uniform(0, 5)
    peak2_x = rng.uniform(0, 25)
    peak2_y = rng.uniform(0, 5)
    points: list[dict[str, float]] = []

    # A 1D profile (ny == 1) sits on y = 0.
    for row_index in range(ny):
        y = row_index * step
        for col_index in range(nx):
            x = col_index * step
            wave = 10 * math.sin(x / 10) * math.cos(y / 10)
            peak1 = 5 * math.exp(-((x - peak1_x) ** 2 + (y - peak1_y) ** 2) / 100)
            peak2 = 3 * math.exp(-((x - peak2_x) ** 2 + (y - peak2_y) ** 2) / 150)
            noise = rng.gauss(0, 1)
            z = z_base + wave + peak1 + peak2 + noise

            points.append({
                "x": _lateral(x, col_index, x_unit),
                "y": _lateral(y, row_index, y_unit),
                "z": round(z * _HEIGHT_PER_NM[z_unit], 5)
            })

    return points


def get_profile_meta(
    filename: str,
    point: str,
    tool_name: str | None = None
) -> AfmProfileMeta | None:
    # `point` is unused here — a mock file scans every point the same way — but the
    # office reads one object per point, each with its own metadata.
    row = _find_measurement(filename, tool_name)
    if row is None or not row["has_profile"]:
        return None

    nx, ny, (x_unit, y_unit, z_unit) = _profile_layout(row)
    step = _SCAN_UM / (nx - 1)
    width = _lateral(_SCAN_UM, nx - 1, x_unit)
    height = _lateral(step * (ny - 1), ny - 1, y_unit)

    return {
        "x_unit": x_unit,
        "y_unit": y_unit,
        "z_unit": z_unit,
        "data_size": f"{nx} x {ny}",
        "surface_size": f"{width:g} x {height:g}"
    }


def get_profile_image_svg(
    filename: str,
    point: str,
    tool_name: str | None = None
) -> str | None:
    row = _find_measurement(filename, tool_name)
    if row is None:
        return None

    rng = random.Random(_seed_for("image", row["tool_name"], row["filename"], point))
    stops = [
        ("0%", "#18213a"),
        ("35%", "#136f63"),
        ("70%", "#d7a334"),
        ("100%", "#f4f0e6")
    ]
    circles = []
    for _ in range(28):
        circles.append(
            "<circle "
            f"cx=\"{rng.randint(35, 605)}\" "
            f"cy=\"{rng.randint(55, 365)}\" "
            f"r=\"{rng.randint(14, 58)}\" "
            f"fill=\"rgba(255,255,255,{rng.uniform(0.05, 0.18):.2f})\" />"
        )

    label = html.escape(f"{row['tool_name']} {row['lot_id']} {point}")
    recipe = html.escape(row["recipe_name"])
    stop_markup = "\n".join(
        f"<stop offset=\"{offset}\" stop-color=\"{color}\" />"
        for offset, color in stops
    )
    circle_markup = "\n".join(circles)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">
  <defs>
    <linearGradient id="surface" x1="0" x2="1" y1="0" y2="1">
      {stop_markup}
    </linearGradient>
  </defs>
  <rect width="640" height="420" fill="#0f172a" />
  <rect x="24" y="24" width="592" height="328" rx="10" fill="url(#surface)" />
  {circle_markup}
  <path d="M48 300 C 155 190, 255 365, 374 214 S 520 135, 592 232" fill="none" stroke="#f8fafc" stroke-width="3" stroke-opacity="0.8" />
  <text x="36" y="385" fill="#f8fafc" font-family="Arial, sans-serif" font-size="19" font-weight="700">{label}</text>
  <text x="36" y="407" fill="#cbd5e1" font-family="Arial, sans-serif" font-size="13">{recipe}</text>
</svg>"""


def list_analysis_images(
    filename: str,
    image_type: str,
    tool_name: str | None = None,
) -> list[dict[str, str]]:
    field = IMAGE_TYPE_FIELDS.get(image_type)
    if field is None:
        return []

    row = _find_measurement(filename, tool_name)
    if row is None:
        return []

    tool = normalize_tool(tool_name)
    encoded_filename = quote(row["filename"], safe="")
    encoded_tool = quote(tool, safe="")

    images: list[dict[str, str]] = []
    for name in row.get(field, []):
        if not name or name == "no files":
            continue
        encoded_name = quote(name, safe="")
        image = {
            "name": name,
            "url": (
                f"/api/afm/files/{encoded_filename}/images/{image_type}/{encoded_name}"
                f"?tool={encoded_tool}"
            ),
        }
        # Only a Result image is a conversion of a stored TIFF; align / tip /
        # capture have no original behind them.
        if image_type == "tiff":
            image["original_url"] = (
                f"/api/afm/files/{encoded_filename}/tiff/{encoded_name}?tool={encoded_tool}"
            )
        images.append(image)
    return images


def get_tiff_original(
    filename: str,
    name: str,
    tool_name: str | None = None,
) -> AfmOriginalFile | None:
    row = _find_measurement(filename, tool_name)
    if row is None or name not in row["tiff_dir_list"] or name == "no files":
        return None

    # Lazy: Pillow is only needed for this one download.
    from PIL import Image

    rng = random.Random(_seed_for("tiff-original", row["tool_name"], row["filename"], name))
    fx, fy, phase = rng.uniform(0.02, 0.09), rng.uniform(0.02, 0.09), rng.uniform(0, math.tau)
    size = 256
    pixels = bytes(
        int(127.5 + 127.5 * math.sin(x * fx + phase) * math.cos(y * fy))
        for y in range(size)
        for x in range(size)
    )
    buffer = io.BytesIO()
    Image.frombytes("L", (size, size), pixels).save(buffer, format="TIFF")
    return {
        "filename": f"{name.rsplit('.', 1)[0]}.tiff",
        "content_type": "image/tiff",
        "data": buffer.getvalue(),
    }


def get_analysis_image_svg(
    filename: str,
    image_type: str,
    name: str,
    tool_name: str | None = None,
) -> str | None:
    field = IMAGE_TYPE_FIELDS.get(image_type)
    if field is None:
        return None

    row = _find_measurement(filename, tool_name)
    if row is None:
        return None

    names = [n for n in row.get(field, []) if n and n != "no files"]
    if name not in names:
        return None

    rng = random.Random(
        _seed_for("analysis-image", row["tool_name"], row["filename"], f"{image_type}:{name}")
    )
    accent = _IMAGE_TYPE_ACCENT.get(image_type, "#0f766e")
    shapes = "\n".join(
        "<circle "
        f"cx=\"{rng.randint(30, 610)}\" cy=\"{rng.randint(45, 285)}\" "
        f"r=\"{rng.randint(10, 46)}\" "
        f"fill=\"rgba(255,255,255,{rng.uniform(0.04, 0.16):.2f})\" />"
        for _ in range(18)
    )
    title = html.escape(f"{image_type.upper()} · {row['tool_name']} {row['lot_id']}")
    subtitle = html.escape(name)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
  <rect width="640" height="360" fill="#0f172a" />
  <rect x="20" y="20" width="600" height="280" rx="10" fill="{accent}" fill-opacity="0.85" />
  {shapes}
  <text x="32" y="330" fill="#f8fafc" font-family="Arial, sans-serif" font-size="18" font-weight="700">{title}</text>
  <text x="32" y="351" fill="#cbd5e1" font-family="Arial, sans-serif" font-size="12">{subtitle}</text>
</svg>"""


# ponytail: only today's window is searched, so a file older than the list
# (12 days on MAP608) answers 404 to a saved group that still names it. Derive
# the day from the file name if home use ever keeps groups that long.
@lru_cache(maxsize=8)
def _generate_measurements(tool_name: str, today: date) -> tuple[AfmMeasurementRow, ...]:
    config = TOOL_CONFIGS.get(tool_name)
    if config is None:
        return tuple()

    rows: list[AfmMeasurementRow] = []
    measured_values = ("1", "standard", "repeat2", "profile", "roughness")

    session_size = config.get("session_size", 1)
    repeats = config.get("repeats", 1)

    # The list ends today: each day after BASE_TIME moves the window one group
    # on, into negative indices. Everything below is a function of the index
    # alone, so a file keeps its name, lot and contents as it ages.
    group_size = session_size * repeats
    newest = (BASE_TIME.date() - today).days * group_size

    for index in range(newest, newest + config["row_count"]):
        # A day holds one group: a session of different samples (MAP608) or the
        # repeated runs of one sample (MAPC01). Elsewhere a group is a single row.
        day, member = divmod(index, group_size)
        sample_no = index // repeats
        timestamp = (
            BASE_TIME - timedelta(days=day, hours=day % 6)
            + timedelta(minutes=157 * (index % repeats))
        )
        date_code = timestamp.strftime("%y%m%d")
        time_code = timestamp.strftime("%H%M%S")
        # Old files carry NA where the start time goes. Here it is a stretch of
        # days that comes round again, so the list always holds some.
        start_code = (
            "NA" if index % config["row_count"] >= 24
            else (timestamp + timedelta(minutes=4 + 11 * member)).strftime("%H%M%S")
        )
        recipe_name = config["recipes"][sample_no % len(config["recipes"])]
        recipe = RECIPES[recipe_name]
        lot_prefixes = config["lot_prefixes"]
        lot_id = f"{lot_prefixes[sample_no % len(lot_prefixes)]}{_base36(sample_no + 42, 2)}"
        slot_number = f"{(sample_no % 25) + 1:02d}"
        measured_info = measured_values[index % len(measured_values)]
        filename = config["filename"].format(
            date=date_code,
            time=time_code,
            recipe=recipe_name,
            slot=slot_number,
            sample=f"{lot_id}.{slot_number}",
            lot=lot_id,
            start=start_code,
            suffix="_SOP_LEFT_UR" if index % 4 == 3 else ""
        )
        unique_key = (
            f"{date_code}#{time_code}#{recipe_name}#{slot_number}_{measured_info}"
            f"#{lot_id}#{measured_info}"
        )
        # Every other file of the measurement is named after the data CSV.
        data_filename = filename.replace("_Info.csv", ".csv")
        clean_filename = _strip_known_extension(data_filename)
        keys = [key for key, *_ in _positions(recipe)]
        has_profile = recipe["profile"] and bool(config["profile_grids"])
        has_data = recipe["columns"] is not None
        has_image = "tiff" in recipe["images"]
        has_align = "align" in recipe["images"]
        has_tip = "tip" in recipe["images"]

        rows.append({
            "unique_key": unique_key,
            "filename": filename,
            "date": date_code,
            "formatted_date": timestamp.strftime("%Y-%m-%d"),
            "recipe_name": recipe_name,
            "lot_id": lot_id,
            "slot_number": slot_number,
            "time": time_code,
            "measured_info": measured_info,
            "tool_name": tool_name,
            "tool_id": config["tool_id"],
            "fab": config["fab"],
            "profile_dir_list": _file_list(
                has_profile,
                _point_files(clean_filename, keys, "txt")
            ),
            "data_dir_list": _file_list(has_data, [data_filename]),
            "tiff_dir_list": _file_list(
                has_image,
                _point_files(clean_filename, keys, "webp")
            ),
            "align_dir_list": _file_list(
                has_align,
                [f"{clean_filename}_{keys[0]}_alignment.webp"]
            ),
            "tip_dir_list": _file_list(
                has_tip,
                [f"{clean_filename}_{keys[0]}_tip.webp"]
            ),
            "capture_dir_list": [f"{clean_filename}_{keys[0]}_capture.webp"],
            "has_profile": has_profile,
            "has_data": has_data,
            "has_image": has_image,
            "has_align": has_align,
            "has_tip": has_tip,
            "point_count": len(keys)
        })

    return tuple(rows)


def _find_measurement(
    filename: str,
    tool_name: str | None = None
) -> AfmMeasurementRow | None:
    clean_filename = _strip_known_extension(filename)
    tool = normalize_tool(tool_name)

    for row in list_afm_files(tool):
        if _strip_known_extension(row["filename"]) == clean_filename:
            return row

    return None


# The value model is fabricated (OFFICE-VERIFY): the real levels, drift and spread
# are unknown. It is shaped so the trend views have something to find at home.
_POINT_NOISE_NM = 0.6
_BOWL_NM = 0.25           # centre-out site pattern, per unit of site radius²
_SAMPLE_SIGMA_NM = 0.8    # one offset per sample, shared by its re-measurements
_DRIFT_PER_DAY_NM = 0.4   # bound of the slow drift a recipe's column follows
_EXCURSION_NM = 7.5
_EXCURSION_EVERY = 9      # about one measurement in nine


def _is_excursion(row: AfmMeasurementRow) -> bool:
    return _seed_for("excursion", row["tool_name"], row["filename"]) % _EXCURSION_EVERY == 0


def _baseline(row: AfmMeasurementRow, column: str, method_index: int) -> float:
    """A column's level on this measurement, before the per-point terms.

    Recipe level (shared by every lot of the recipe) + a slow drift keyed on the
    measurement's own timestamp, so a file reads the same as it ages + an offset
    per sample, so re-measurements of one sample agree + an excursion on about
    one file in nine.
    """
    recipe_rng = random.Random(_seed_for("level", row["recipe_name"], column))
    level = recipe_rng.uniform(55, 120)
    method_offset = method_index * recipe_rng.uniform(-6, 6)
    drift_per_day = recipe_rng.uniform(-_DRIFT_PER_DAY_NM, _DRIFT_PER_DAY_NM)
    measured_at = datetime.strptime(row["date"] + row["time"], "%y%m%d%H%M%S")
    days = (measured_at.replace(tzinfo=timezone.utc) - BASE_TIME).total_seconds() / 86400
    sample_rng = random.Random(
        _seed_for("sample", row["tool_name"], row["lot_id"], row["slot_number"])
    )
    return (
        level + method_offset + drift_per_day * days
        + sample_rng.gauss(0, _SAMPLE_SIGMA_NM)
        + (_EXCURSION_NM if _is_excursion(row) else 0.0)
    )


def _summary_records(
    site: str,
    site_rows: list[dict[str, Any]],
    columns: tuple[str, ...]
) -> list[dict[str, Any]]:
    column_values: dict[str, dict[str, float]] = {}

    for column in columns:
        values = [record[column] for record in site_rows]
        column_values[column] = {
            "MEAN": statistics.fmean(values),
            "STDEV": statistics.stdev(values) if len(values) > 1 else 0.0,
            "MIN": min(values),
            "MAX": max(values),
            "RANGE": max(values) - min(values)
        }

    return [
        {
            "Site": site,
            "ITEM": item,
            **{key: round(values[item], 2) for key, values in column_values.items()}
        }
        for item in SUMMARY_ITEMS
    ]


def _signed(value: int) -> str:
    return f"{'-' if value < 0 else ''}{abs(value):03d}"


def _positions(recipe: dict[str, Any]) -> list[tuple[str, str | None, tuple[int, int], int]]:
    """(key, Site ID, (Site X, Site Y), Point No) of every measured point.

    The key is what a point's profile and image files are named after: the
    4-digit point number alone (`0001`), or on a recipe that records Site ID
    the Site ID followed by the point number within that site
    (`0004_X000_Y-002_0002`).
    """
    per_site = recipe.get("per_site", 1) if recipe["site_id"] else 1
    positions = []
    for index in range(recipe["points"]):
        site_no, point_no = divmod(index, per_site)
        site_x, site_y = SITE_LAYOUT[site_no]
        if recipe["site_id"]:
            site_id = f"{site_no + 1:04d}_X{_signed(site_x)}_Y{_signed(site_y)}"
            key = f"{site_id}_{point_no + 1:04d}"
        else:
            site_id, key = None, f"{index + 1:04d}"
        positions.append((key, site_id, (site_x, site_y), point_no + 1 if site_id else index + 1))
    return positions


def _profile_layout(row: AfmMeasurementRow) -> tuple[int, int, tuple[str, str, str]]:
    # The scan is recipe configuration like everything else, so a recipe keeps one
    # grid shape and one unit set: the tool's lists are dealt out in recipe order.
    config = TOOL_CONFIGS[row["tool_name"]]
    grids, units = config["profile_grids"], config["profile_units"]
    position = config["recipes"].index(row["recipe_name"])
    return (*grids[position % len(grids)], units[position % len(units)])


def _lateral(value_um: float, index: int, unit: str) -> float:
    # A Pixel axis counts samples; nothing in the source says how long a pixel is.
    if unit == "Pixel":
        return float(index)
    # Four decimals in um: a 16384-point line steps 0.003 um, which two would merge.
    return round(value_um * _LATERAL_PER_UM[unit], 4)


def _display_start_time(row: AfmMeasurementRow) -> str:
    # MAP608 alone carries the measurement start, as its file name's trailing time.
    # Where that is NA, and on the other tools, the leading time is the start.
    start = row["filename"].split("#")[6]
    raw_time = (start if start.isdigit() else row["time"]).ljust(6, "0")
    return (
        f"{row['formatted_date']} "
        f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}"
    )


def _strip_known_extension(filename: str) -> str:
    if filename.endswith(".csv") or filename.endswith(".pkl"):
        return filename[:-4]
    return filename


def _file_list(has_files: bool, files: list[str]) -> list[str]:
    return files if has_files else ["no files"]


def _point_files(clean_filename: str, keys: list[str], extension: str) -> list[str]:
    return [f"{clean_filename}_{key}_Height.{extension}" for key in keys]


def _seed_for(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _base36(value: int, width: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # Only the last `width` digits are kept, so wrap first: the result is the
    # same for any non-negative value, and a negative one (a day after
    # BASE_TIME) no longer divides forever.
    value %= len(alphabet) ** width
    if value == 0:
        encoded = "0"
    else:
        chars = []
        next_value = value
        while next_value:
            next_value, remainder = divmod(next_value, len(alphabet))
            chars.append(alphabet[remainder])
        encoded = "".join(reversed(chars))

    return encoded.rjust(width, "0")[-width:]
