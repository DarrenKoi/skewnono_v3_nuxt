from urllib.parse import quote, unquote

from flask import Blueprint, Response, jsonify, request

from back_dev_home.afm.data import (
    get_afm_file_detail,
    get_analysis_image_svg,
    get_profile_image_svg,
    get_profile_points,
    get_tools,
    get_user_analytics,
    list_afm_files,
    list_analysis_images,
    list_user_activities,
    normalize_tool
)

bp = Blueprint("afm", __name__)

_VALID_IMAGE_TYPES = ("align", "tip", "capture", "tiff")


@bp.get("/afm/tools")
def afm_tools():
    return jsonify(get_tools())


@bp.get("/afm/files")
@bp.get("/afm-files")
def afm_files():
    tool_name = _tool_name()
    rows = list_afm_files(tool_name)
    return jsonify({
        "success": True,
        "data": rows,
        "total": len(rows),
        "tool": tool_name,
        "message": f"Successfully loaded {len(rows)} AFM measurements for {tool_name}"
    })


@bp.get("/afm/files/<path:filename>")
@bp.get("/afm-files/detail/<path:filename>")
def afm_file_detail(filename: str):
    tool_name = _tool_name()
    decoded_filename = unquote(filename)
    detail = get_afm_file_detail(decoded_filename, tool_name)

    if detail is None:
        return jsonify({
            "success": False,
            "error": "Measurement file not found",
            "message": f"No AFM measurement found for {decoded_filename}",
            "tool": tool_name
        }), 404

    return jsonify({
        "success": True,
        "data": detail,
        "message": f"Successfully loaded measurement data for {decoded_filename}"
    })


@bp.get("/afm/files/<path:filename>/profile/<path:point>")
@bp.get("/afm-files/profile/<path:filename>/<path:point>")
def afm_profile(filename: str, point: str):
    tool_name = _tool_name()
    decoded_filename = unquote(filename)
    decoded_point = unquote(point)
    profile_points = get_profile_points(
        decoded_filename,
        decoded_point,
        tool_name,
        _site_info()
    )

    if profile_points is None:
        return jsonify({
            "success": False,
            "error": "Profile file not found",
            "message": f"No profile found for {decoded_filename}, point {decoded_point}",
            "tool": tool_name
        }), 404

    return jsonify({
        "success": True,
        "data": profile_points,
        "count": len(profile_points),
        "tool": tool_name,
        "message": f"Successfully loaded profile data for {decoded_filename}, point {decoded_point}"
    })


@bp.get("/afm/files/<path:filename>/image/<path:point>")
@bp.get("/afm-files/image/<path:filename>/<path:point>")
def afm_image(filename: str, point: str):
    tool_name = _tool_name()
    decoded_filename = unquote(filename)
    decoded_point = unquote(point)
    svg = get_profile_image_svg(decoded_filename, decoded_point, tool_name)

    if svg is None:
        return jsonify({
            "success": False,
            "error": "Image file not found",
            "message": f"No image found for {decoded_filename}, point {decoded_point}",
            "tool": tool_name
        }), 404

    encoded_filename = quote(decoded_filename, safe="")
    encoded_point = quote(decoded_point, safe="")
    image_url = (
        f"/api/afm/files/{encoded_filename}/image-file/{encoded_point}"
        f"?tool={quote(tool_name, safe='')}"
    )

    return jsonify({
        "success": True,
        "data": {
            "filename": f"{decoded_filename}_{decoded_point}_Height.svg",
            "relative_path": f"{decoded_filename}_{decoded_point}_Height.svg",
            "url": image_url
        },
        "tool": tool_name,
        "message": f"Successfully found image for {decoded_filename}, point {decoded_point}"
    })


@bp.get("/afm/files/<path:filename>/image-file/<path:point>")
@bp.get("/afm-files/image-file/<path:filename>/<path:point>")
def afm_image_file(filename: str, point: str):
    tool_name = _tool_name()
    decoded_filename = unquote(filename)
    decoded_point = unquote(point)
    svg = get_profile_image_svg(decoded_filename, decoded_point, tool_name)

    if svg is None:
        return "Image file not found", 404

    return Response(svg, mimetype="image/svg+xml")


@bp.get("/afm/files/<path:filename>/images/<image_type>")
def afm_analysis_images(filename: str, image_type: str):
    tool_name = _tool_name()
    if image_type not in _VALID_IMAGE_TYPES:
        return jsonify({
            "success": False,
            "error": "Invalid image type",
            "message": f"Unknown image type '{image_type}'",
            "tool": tool_name
        }), 404

    decoded_filename = unquote(filename)
    images = list_analysis_images(decoded_filename, image_type, tool_name)
    return jsonify({
        "success": True,
        "data": images,
        "count": len(images),
        "tool": tool_name,
        "message": f"Found {len(images)} {image_type} images for {decoded_filename}"
    })


@bp.get("/afm/files/<path:filename>/images/<image_type>/<path:name>")
def afm_analysis_image_file(filename: str, image_type: str, name: str):
    if image_type not in _VALID_IMAGE_TYPES:
        return "Invalid image type", 404

    tool_name = _tool_name()
    decoded_filename = unquote(filename)
    decoded_name = unquote(name)
    svg = get_analysis_image_svg(decoded_filename, image_type, decoded_name, tool_name)

    if svg is None:
        return "Image file not found", 404

    return Response(svg, mimetype="image/svg+xml")


@bp.get("/afm/activities")
def afm_activities():
    user = request.args.get("user")
    limit = _int_arg("limit", 100)
    activities = list_user_activities(user, limit)
    return jsonify({
        "success": True,
        "data": activities,
        "count": len(activities),
        "message": f"Retrieved {len(activities)} AFM activities"
    })


@bp.get("/afm/activities/me")
def afm_my_activities():
    user = request.cookies.get("LASTUSER") or request.cookies.get("LAST_USER") or "anonymous"
    activities = list_user_activities(user, 50)
    return jsonify({
        "success": True,
        "user": user,
        "data": activities,
        "count": len(activities),
        "message": f"Retrieved {len(activities)} AFM activities for {user}"
    })


@bp.get("/afm/current-user")
def afm_current_user():
    user = request.cookies.get("LASTUSER") or request.cookies.get("LAST_USER") or "anonymous"
    return jsonify({
        "success": True,
        "user": user,
        "message": f"Current user: {user}"
    })


@bp.get("/afm/analytics")
def afm_analytics():
    days = _int_arg("days", 7)
    return jsonify({
        "success": True,
        "data": get_user_analytics(days),
        "message": f"User analytics for the last {days} days"
    })


def _tool_name() -> str:
    return normalize_tool(request.args.get("tool"))


def _site_info() -> dict[str, str | int | None]:
    point_no = request.args.get("point_no")
    parsed_point_no: int | None

    try:
        parsed_point_no = int(point_no) if point_no else None
    except ValueError:
        parsed_point_no = None

    return {
        "site_id": request.args.get("site_id"),
        "site_x": request.args.get("site_x"),
        "site_y": request.args.get("site_y"),
        "point_no": parsed_point_no
    }


def _int_arg(name: str, default: int) -> int:
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
