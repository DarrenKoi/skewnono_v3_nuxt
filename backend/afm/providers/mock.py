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
그대로입니다 (OFFICE-VERIFY).

확인되어 그대로 재현하는 것 (office 확인 2026-10-02):
- 장비는 MAP608 · MAPC01 · 5EAP1501 이고 MAPC01=R3, 5EAP1501=M15 입니다.
- 파일명은 `#` 구분이며 장비마다 필드 순서가 다르고, 빈자리는 `NA` 입니다.
- 측정 컬럼은 recipe 마다 다르고 모두 `(nm)` 를 포함합니다
  (MAP608 `Pad_1_H (nm)`…, 5EAP1501 `1_Minimum (nm)`…`51_Minimum (nm)`).
- MAPC01 은 data CSV 가 없어 summary·data 가 비어 있습니다.
- 5EAP1501 은 profile txt 가 없어 profile 이 없습니다.
- Site 는 현재 샘플에서 block 하나이고 그 이름은 method 명입니다. 파서가 다중
  block 을 전제하므로 여섯 행에 하나는 여러 Site 를 냅니다.
- Profile 격자는 MAP608 512×64, MAPC01 은 1D(N×1, 1024~16384)와 2D 혼재입니다.

지어냈거나 일부러 다른 것 (OFFICE-VERIFY):
- MAP608 의 fab `PKG` — raw 에 fab 필드가 없고 docs/afm/tool_info.txt 가 유일한 근거입니다.
- SAMPLE_ID·method 명·lot ID 의 생김새, recipe 별 측정 컬럼 개수, MAPC01 의 2D 격자 크기.
- MAP608 파일명의 첫 번째 시각이 무엇인지(마지막 시각만 측정 시작으로 확인됨).
- MAPC01 은 파일명의 lot 자리가 NA 라 `lot_id` 를 "NA" 로 둡니다.
- data 행의 측정 컬럼 밖 키(`Site X`, `State`, `<측정명>_Valid` …)와 Information 의 키.
- Summary 는 data 행에서 계산합니다. STDEV 는 표본 표준편차(ddof=1)이고 Valid 는 거르지 않습니다.
- Profile 의 단위는 파일마다 다르지만(um/nm/pm/Pixel) 계약에 단위 필드가 없어 싣지 못합니다.
  값은 um/um/nm 로 읽히게 만들었습니다.
- 이미지는 자리 표시 SVG 입니다. 실제는 webp 변환본이 있습니다.
"""

import hashlib
import html
import math
import random
import statistics
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from backend.afm.contracts import AfmMeasurementRow


__all__ = [
    "AfmMeasurementRow",
    "normalize_tool",
    "get_tools",
    "list_afm_files",
    "get_afm_file_detail",
    "get_profile_points",
    "get_profile_image_svg",
    "list_analysis_images",
    "get_analysis_image_svg",
]


ToolConfig = dict[str, Any]

BASE_TIME = datetime(2026, 4, 24, 9, 30, 0, tzinfo=timezone.utc)
SITES = ("1_UL", "2_UR", "3_LL", "4_LR", "5_C", "6_L", "7_R", "8_T", "9_B")
SUMMARY_ITEMS = ("MEAN", "STDEV", "MIN", "MAX", "RANGE")
STATE_CODES = ("OK", "OK", "OK", "WARN", "NG")

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

# Per tool: `filename` is the raw file name's field order, `site` the method name
# its single Site block carries, `column` the measurement-column template with one
# count per recipe (None = no data CSV), `profile_grids` the (nx, ny) shapes its
# profile txt comes in (empty = no profile txt).
TOOL_CONFIGS: dict[str, ToolConfig] = {
    "MAP608": {
        "tool_id": "map608",
        "fab": "PKG",
        "row_count": 36,
        "lot_prefixes": ("T7HQR", "T3HQR", "TT032", "CRAP1"),
        "recipes": (
            "FSOXCMP_DISHING_9PT",
            "CMP_PRE",
            "CMP_POST",
            "ETCH_GATE",
            "DEP_OXIDE",
            "PROFILE_HEIGHT_5PT"
        ),
        # The trailing time is the measurement start; the leading one is unexplained.
        "filename": "#{date}#{time}#{recipe}#{sample}#{lot}#{start}#.csv",
        "site": "Step Height",
        "column": "Pad_{}_H (nm)",
        "column_counts": (3, 2, 4, 6),
        "profile_grids": ((512, 64),)
    },
    "MAPC01": {
        "tool_id": "mapc01",
        "fab": "R3",
        "row_count": 28,
        "recipes": (
            "FSOXCMP_DISHING_9PT",
            "CMP_PRE",
            "CMP_POST",
            "ETCH_VIA",
            "DEP_NITRIDE",
            "ROUGHNESS_SCAN"
        ),
        "filename": "#{date}#{time}#{recipe}#{slot}#NA#NA#{sample}_Info.csv",
        "site": "Line Profile",
        "column": None,
        "profile_grids": ((1024, 1), (4096, 1), (512, 64), (16384, 1))
    },
    "5EAP1501": {
        "tool_id": "5eap1501",
        "fab": "M15",
        "row_count": 30,
        "lot_prefixes": ("M15AFM", "M15CMP", "T01HQR", "M15DEV"),
        "recipes": (
            "FSOXCMP_DISHING_9PT",
            "CMP_PRE",
            "CMP_POST",
            "ETCH_GATE",
            "DEP_OXIDE",
            "PROFILE_HEIGHT_5PT"
        ),
        # The real name has more text between the last `#` and `.csv`; it was not relayed.
        "filename": "#{date}#{time}#{recipe}#{sample}#{lot}#NA#.csv",
        "site": "Trench Depth",
        "column": "{}_Minimum (nm)",
        "column_counts": (51, 25, 9),
        "profile_grids": ()
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
    return list(_generate_measurements(tool))


@lru_cache(maxsize=256)
def get_afm_file_detail(
    filename: str,
    tool_name: str | None = None
) -> dict[str, Any] | None:
    row = _find_measurement(filename, tool_name)
    if row is None:
        return None

    rng = random.Random(_seed_for("detail", row["tool_name"], row["filename"]))
    sites = _sites_for(row)
    columns = _measurement_columns(row)
    summary: list[dict[str, Any]] = []
    detail: list[dict[str, Any]] = []

    # No measurement columns means no data CSV (MAPC01): both tables stay empty.
    for site_index, site in enumerate(sites if columns else ()):
        site_x = round(-4800 + (site_index % 3) * 4800 + rng.uniform(-120, 120), 1)
        site_y = round(4800 - (site_index // 3) * 3600 + rng.uniform(-120, 120), 1)
        bases = [rng.uniform(55, 120) + site_index * rng.uniform(-2, 3) for _ in columns]
        site_rows: list[dict[str, Any]] = []

        for point_no in range(1, rng.randint(20, 50) + 1):
            record: dict[str, Any] = {
                "measurement_point": site,
                "Site ID": site,
                "Site X": site_x,
                "Site Y": site_y,
                "Point No": point_no,
                "X (um)": round(site_x + rng.uniform(-1000, 1000), 1),
                "Y (um)": round(site_y + rng.uniform(-1000, 1000), 1),
                "Method ID": rng.randint(1, 5),
                "State": rng.choice(STATE_CODES),
                "Valid": rng.random() > 0.08
            }
            for column, base in zip(columns, bases, strict=True):
                record[column] = round(base + rng.uniform(-9, 9), 2)
                record[f"{column.removesuffix(' (nm)')}_Valid"] = rng.random() > 0.06
            record.update({
                "Pick Up Count": rng.randint(1, 10),
                "Sample Count": rng.randint(1, 5),
                "Approach Count": rng.randint(1, 3),
                "Mileage": round(rng.uniform(2, 98), 1)
            })
            site_rows.append(record)

        detail.extend(site_rows)
        summary.extend(_summary_records(site, site_rows, columns))

    clean_filename = _strip_known_extension(row["filename"])

    return {
        "filename": row["filename"],
        "tool": row["tool_name"],
        "pickle_filename": f"{clean_filename}.pkl",
        "information": {
            "Lot ID": row["lot_id"],
            "Recipe ID": row["recipe_name"],
            "Carrier ID": f"CAR{rng.randint(100, 999)}",
            "Sample ID": f"{row['slot_number']}_{row['measured_info']}",
            "Start Time": _display_start_time(row),
            "Tool": row["tool_name"],
            "Fab": row["fab"],
            "Operator": f"OP{rng.randint(1000, 9999)}",
            "Measurement": row["measured_info"]
        },
        "summary": summary,
        "data": detail,
        "available_points": sites
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
    # One grid shape per measurement: every point of a file was scanned the same way.
    grids = TOOL_CONFIGS[row["tool_name"]]["profile_grids"]
    nx, ny = grids[_seed_for("grid", row["tool_name"], row["filename"]) % len(grids)]
    # A 50 um scan line with square pixels; a 1D profile (ny == 1) sits on y = 0.
    step = 50 / (nx - 1)
    z_base = rng.uniform(80, 120)
    peak1_x = rng.uniform(25, 50)
    peak1_y = rng.uniform(0, 5)
    peak2_x = rng.uniform(0, 25)
    peak2_y = rng.uniform(0, 5)
    points: list[dict[str, float]] = []

    for row_index in range(ny):
        y = row_index * step
        for col_index in range(nx):
            x = col_index * step
            wave = 10 * math.sin(x / 10) * math.cos(y / 10)
            peak1 = 5 * math.exp(-((x - peak1_x) ** 2 + (y - peak1_y) ** 2) / 100)
            peak2 = 3 * math.exp(-((x - peak2_x) ** 2 + (y - peak2_y) ** 2) / 150)
            noise = rng.gauss(0, 1)

            # Four decimals: a 16384-point line steps 0.003 um, which two would merge.
            points.append({
                "x": round(x, 4),
                "y": round(y, 4),
                "z": round(z_base + wave + peak1 + peak2 + noise, 2)
            })

    return points


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
        images.append({
            "name": name,
            "url": (
                f"/api/afm/files/{encoded_filename}/images/{image_type}/{encoded_name}"
                f"?tool={encoded_tool}"
            ),
        })
    return images


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


@lru_cache(maxsize=None)
def _generate_measurements(tool_name: str) -> tuple[AfmMeasurementRow, ...]:
    config = TOOL_CONFIGS.get(tool_name)
    if config is None:
        return tuple()

    rows: list[AfmMeasurementRow] = []
    measured_values = ("1", "standard", "repeat2", "profile", "roughness")

    for index in range(config["row_count"]):
        timestamp = BASE_TIME - timedelta(days=index, hours=index % 6)
        date_code = timestamp.strftime("%y%m%d")
        time_code = timestamp.strftime("%H%M%S")
        start_code = (timestamp - timedelta(minutes=3 + index % 9)).strftime("%H%M%S")
        recipe_name = config["recipes"][index % len(config["recipes"])]
        # A tool whose file name has no lot field reports NA there, so the lot is unknown.
        lot_prefixes = config.get("lot_prefixes")
        lot_id = (
            f"{lot_prefixes[index % len(lot_prefixes)]}{_base36(index + 42, 2)}"
            if lot_prefixes else "NA"
        )
        slot_number = f"{(index % 25) + 1:02d}"
        measured_info = measured_values[index % len(measured_values)]
        slot_info = f"{slot_number}_{measured_info}"
        filename = config["filename"].format(
            date=date_code,
            time=time_code,
            recipe=recipe_name,
            slot=slot_number,
            sample=slot_info,
            lot=lot_id,
            start=start_code
        )
        unique_key = f"{date_code}#{time_code}#{recipe_name}#{slot_info}#{lot_id}#{measured_info}"
        clean_filename = _strip_known_extension(filename)
        sites = SITES[:5 + (index % 5)] if index % 6 == 5 else (config["site"],)
        has_profile = bool(config["profile_grids"]) and index % 5 != 3
        has_data = config["column"] is not None
        has_image = index % 4 != 1
        has_align = index % 6 == 0
        has_tip = index % 7 == 0

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
                _site_point_files(clean_filename, sites, "txt")
            ),
            "data_dir_list": _file_list(has_data, [filename]),
            "tiff_dir_list": _file_list(
                has_image,
                _site_point_files(clean_filename, sites, "webp")
            ),
            "align_dir_list": _file_list(
                has_align,
                [f"{clean_filename}_{sites[0]}_alignment.webp"]
            ),
            "tip_dir_list": _file_list(
                has_tip,
                [f"{clean_filename}_{sites[0]}_tip.webp"]
            ),
            "capture_dir_list": [f"{clean_filename}_{sites[0]}_capture.webp"],
            "has_profile": has_profile,
            "has_data": has_data,
            "has_image": has_image,
            "has_align": has_align,
            "has_tip": has_tip,
            "point_count": len(sites)
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


def _measurement_columns(row: AfmMeasurementRow) -> tuple[str, ...]:
    config = TOOL_CONFIGS[row["tool_name"]]
    if config["column"] is None:
        return ()

    counts = config["column_counts"]
    count = counts[config["recipes"].index(row["recipe_name"]) % len(counts)]
    return tuple(config["column"].format(number) for number in range(1, count + 1))


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
            "STDEV": statistics.stdev(values),
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


def _sites_for(row: AfmMeasurementRow) -> list[str]:
    if row["point_count"] == 1:
        return [TOOL_CONFIGS[row["tool_name"]]["site"]]
    return list(SITES[:row["point_count"]])


def _display_start_time(row: AfmMeasurementRow) -> str:
    # MAP608 alone carries the measurement start, as its file name's last field.
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


def _site_point_files(clean_filename: str, sites, extension: str) -> list[str]:
    return [
        f"{clean_filename}_{site}_{point_no:04d}_Height.{extension}"
        for site in sites[:3]
        for point_no in range(1, 4)
    ]


def _seed_for(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _base36(value: int, width: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
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
