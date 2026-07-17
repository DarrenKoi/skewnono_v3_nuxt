"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본 데이터: AFM 데이터 플랫폼 (afm_data_platform 명세 — docs/afm-migration-plan.md)
계약:        docs/api-contracts/afm.yaml
픽스처:      back_dev_home/afm/__fixtures__/

AFM 은 단일 측정 행(`AfmMeasurementRow`) 보다 풍부한 디테일·프로파일·이미지 응답
구조를 가집니다. 함수별 반환 형태가 다르므로 픽스처에 엔드포인트별 샘플을 모두
캡처해 사무실 LLM이 형태를 한눈에 볼 수 있도록 합니다.
"""

import hashlib
import html
import math
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from back_dev_home.afm.contracts import AfmMeasurementRow


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
    "list_user_activities",
    "get_user_analytics",
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

SUMMARY_COLUMNS: tuple[tuple[str, float, tuple[float, float], tuple[float, float], tuple[float, float]], ...] = (
    ("Left_H (nm)", 1.0, (0.8, 4.5), (8, 20), (15, 35)),
    ("Right_H (nm)", 0.9, (0.9, 4.2), (7, 18), (12, 32)),
    ("Ref_H (nm)", 0.7, (0.7, 3.8), (6, 16), (10, 28)),
)

TOOL_CONFIGS: dict[str, ToolConfig] = {
    "MAP608": {
        "tool_id": "map608",
        "fab": "R3",
        "row_count": 36,
        "lot_prefixes": ("T7HQR", "T3HQR", "R3AFM", "R3CMP"),
        "recipes": (
            "FSOXCMP_DISHING_9PT",
            "CMP_PRE",
            "CMP_POST",
            "ETCH_GATE",
            "DEP_OXIDE",
            "PROFILE_HEIGHT_5PT"
        )
    },
    "MAPC01": {
        "tool_id": "mapc01",
        "fab": "M12",
        "row_count": 28,
        "lot_prefixes": ("M12AFM", "M12CMP", "C1HQR", "M12DEV"),
        "recipes": (
            "FSOXCMP_DISHING_9PT",
            "CMP_PRE",
            "CMP_POST",
            "ETCH_VIA",
            "DEP_NITRIDE",
            "ROUGHNESS_SCAN"
        )
    },
    "5MAPT01": {
        "tool_id": "5mapt01",
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
        )
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
    summary: list[dict[str, Any]] = []
    detail: list[dict[str, Any]] = []

    for site_index, site in enumerate(sites):
        site_x = round(-4800 + (site_index % 3) * 4800 + rng.uniform(-120, 120), 1)
        site_y = round(4800 - (site_index // 3) * 3600 + rng.uniform(-120, 120), 1)
        position_bias = site_index * rng.uniform(-2, 3)
        point_variation = rng.uniform(-15, 15)
        process_noise = rng.uniform(0.5, 3.0)
        left_base = rng.uniform(60, 120) + position_bias + point_variation
        right_base = rng.uniform(55, 115) + position_bias + point_variation * 0.8
        ref_base = rng.uniform(50, 110) + position_bias + point_variation * 0.6

        summary.extend(
            _summary_records(
                site, left_base, right_base, ref_base, process_noise, rng
            )
        )

        num_measurements = rng.randint(20, 50)
        for point_no in range(1, num_measurements + 1):
            detail.append({
                "measurement_point": site,
                "Site ID": site,
                "Site X": site_x,
                "Site Y": site_y,
                "Point No": point_no,
                "X (um)": round(site_x + rng.uniform(-1000, 1000), 1),
                "Y (um)": round(site_y + rng.uniform(-1000, 1000), 1),
                "Method ID": rng.randint(1, 5),
                "State": rng.choice(STATE_CODES),
                "Valid": rng.random() > 0.08,
                "Left_H (nm)": round(left_base + rng.uniform(-9, 9), 2),
                "Left_H_Valid": rng.random() > 0.06,
                "Right_H (nm)": round(right_base + rng.uniform(-9, 9), 2),
                "Right_H_Valid": rng.random() > 0.06,
                "Ref_H (nm)": round(ref_base + rng.uniform(-8, 8), 2),
                "Ref_H_Valid": rng.random() > 0.06,
                "Pick Up Count": rng.randint(1, 10),
                "Sample Count": rng.randint(1, 5),
                "Approach Count": rng.randint(1, 3),
                "Mileage": round(rng.uniform(2, 98), 1)
            })

    clean_filename = _strip_known_extension(row["filename"])

    return {
        "filename": row["filename"],
        "tool": row["tool_name"],
        "pickle_filename": f"{clean_filename}.pkl",
        "information": {
            "Lot ID": row["lot_id"],
            "Recipe ID": row["recipe_name"],
            "Carrier ID": f"CAR{rng.randint(100, 999)}",
            "Sample ID": f"S{row['slot_number']}",
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
    if row is None:
        return None

    seed_parts = [
        "profile",
        row["tool_name"],
        row["filename"],
        point,
        str(site_info or {})
    ]
    rng = random.Random(_seed_for(*seed_parts))
    grid_size = 20
    z_base = rng.uniform(80, 120)
    peak1_x = rng.uniform(0, 25)
    peak1_y = rng.uniform(0, 25)
    peak2_x = rng.uniform(-25, 0)
    peak2_y = rng.uniform(0, 25)
    points: list[dict[str, float]] = []

    for row_index in range(grid_size):
        for col_index in range(grid_size):
            x = -50 + (100 * col_index / (grid_size - 1))
            y = -50 + (100 * row_index / (grid_size - 1))
            wave = 10 * math.sin(x / 10) * math.cos(y / 10)
            peak1 = 5 * math.exp(-((x - peak1_x) ** 2 + (y - peak1_y) ** 2) / 100)
            peak2 = 3 * math.exp(-((x - peak2_x) ** 2 + (y - peak2_y) ** 2) / 150)
            noise = rng.gauss(0, 1)

            points.append({
                "x": round(x, 2),
                "y": round(y, 2),
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
    for index in range(28):
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


def list_user_activities(user: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    rows = list_afm_files("MAP608")[: min(max(limit, 0), 20)]
    now = BASE_TIME + timedelta(days=4)
    activities: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        actor = user or f"engineer{(index % 4) + 1:02d}"
        detail = get_afm_file_detail(row["filename"], row["tool_name"])
        detail_count = len(detail["data"]) if detail else 0
        activities.append({
            "timestamp": (now - timedelta(minutes=index * 17)).isoformat().replace("+00:00", "Z"),
            "user": actor,
            "action": "get_detail" if index % 3 == 0 else "list_files",
            "tool": row["tool_name"],
            "filename": row["filename"],
            "summary_count": row["point_count"] * len(SUMMARY_ITEMS),
            "detail_count": detail_count
        })

    return activities


def get_user_analytics(days: int = 7) -> dict[str, Any]:
    clamped_days = max(1, min(days, 30))
    daily_stats = []

    for offset in range(clamped_days):
        date = (BASE_TIME.date() - timedelta(days=clamped_days - offset - 1)).isoformat()
        daily_stats.append({
            "date": date,
            "unique_users": 2 + (offset % 4),
            "total_sessions": 4 + (offset % 5),
            "total_actions": 18 + offset * 3,
            "avg_actions_per_session": round((18 + offset * 3) / (4 + (offset % 5)), 1)
        })

    return {
        "daily_stats": daily_stats,
        "summary": {
            "period_days": clamped_days,
            "total_unique_users": 6,
            "avg_daily_users": round(
                sum(day["unique_users"] for day in daily_stats) / len(daily_stats),
                1
            ),
            "avg_daily_sessions": round(
                sum(day["total_sessions"] for day in daily_stats) / len(daily_stats),
                1
            )
        }
    }


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
        recipe_name = config["recipes"][index % len(config["recipes"])]
        lot_prefix = config["lot_prefixes"][index % len(config["lot_prefixes"])]
        lot_id = f"{lot_prefix}{_base36(index + 42, 2)}"
        slot_number = f"{(index % 25) + 1:02d}"
        measured_info = measured_values[index % len(measured_values)]
        slot_info = f"{slot_number}_{measured_info}"
        filename = f"#{date_code}#{recipe_name}#{lot_id}_{time_code}#{slot_info}#.csv"
        unique_key = f"{date_code}#{time_code}#{recipe_name}#{slot_info}#{lot_id}#{measured_info}"
        clean_filename = _strip_known_extension(filename)
        point_count = 5 + (index % 5)
        sites = SITES[:point_count]
        has_profile = index % 5 != 3
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
                _site_point_files(clean_filename, sites, "pkl")
            ),
            "data_dir_list": [f"{clean_filename}.pkl"],
            "tiff_dir_list": _file_list(
                has_image,
                _site_point_files(clean_filename, sites, "webp")
            ),
            "align_dir_list": _file_list(
                has_align,
                [f"{clean_filename}_{sites[0]}_alignment.png"]
            ),
            "tip_dir_list": _file_list(
                has_tip,
                [f"{clean_filename}_{sites[0]}_tip.tiff"]
            ),
            "capture_dir_list": [f"{clean_filename}_{sites[0]}_capture.png"],
            "has_profile": has_profile,
            "has_data": True,
            "has_image": has_image,
            "has_align": has_align,
            "has_tip": has_tip,
            "hasProfile": has_profile,
            "hasData": True,
            "hasImage": has_image,
            "hasAlign": has_align,
            "hasTip": has_tip,
            "point_count": point_count
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


def _summary_records(
    site: str,
    left_base: float,
    right_base: float,
    ref_base: float,
    process_noise: float,
    rng: random.Random
) -> list[dict[str, Any]]:
    drift = rng.uniform(-1.5, 1.5)
    bases = (left_base, right_base, ref_base)
    column_values: dict[str, dict[str, float]] = {}

    for base, (key, drift_factor, stdev_range, offset_range, range_range) in zip(bases, SUMMARY_COLUMNS):
        column_values[key] = {
            "MEAN": base + drift * drift_factor,
            "STDEV": rng.uniform(*stdev_range) * process_noise,
            "MIN": base - rng.uniform(*offset_range),
            "MAX": base + rng.uniform(*offset_range),
            "RANGE": rng.uniform(*range_range)
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
    return list(SITES[:row["point_count"]])


def _display_start_time(row: AfmMeasurementRow) -> str:
    raw_time = row["time"].ljust(6, "0")
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
