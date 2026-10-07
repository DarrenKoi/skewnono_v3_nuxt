import io
import zipfile
from urllib.parse import quote, unquote

from flask import Blueprint, Response, jsonify, request

from backend.afm.profile_sampling import thin_profile

from backend.afm.data import (
    get_afm_file_detail,
    get_analysis_image_svg,
    get_profile_image_svg,
    get_profile_meta,
    get_profile_points,
    get_tiff_original,
    get_tools,
    list_afm_files,
    list_analysis_images,
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

    # A dense scan is thinned to what the page can draw; `total` is what the file
    # holds. `?full=1` is the export asking for the file itself: a sheet outlives
    # the screen, and nothing in it would say it was a decimated scan.
    full = request.args.get("full") == "1"
    shown = profile_points if full else thin_profile(profile_points)
    return jsonify({
        "success": True,
        "data": shown,
        # The file's own X/Y/Z units; they differ per file and are never unified.
        "meta": get_profile_meta(decoded_filename, decoded_point, tool_name),
        "count": len(shown),
        "total": len(profile_points),
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

    return _image(svg)


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

    return _image(svg)


@bp.get("/afm/files/<path:filename>/tiff/<path:name>")
def afm_tiff_original(filename: str, name: str):
    """The untouched original behind one displayed image, as a download.

    `name` is the listed (display) image name; the provider maps it to the
    stored original, so the page never has to know the storage layout. The
    path says `tiff` because Result images came first: an align original is a
    .bmp, a tip or capture one a .png.
    """
    original = get_tiff_original(unquote(filename), unquote(name), _tool_name())

    if original is None:
        return "TIFF file not found", 404

    return _attachment(original["data"], original["content_type"], original["filename"])


@bp.get("/afm/files/<path:filename>/tiff.zip")
def afm_tiff_zip(filename: str):
    """Every original of one image type (`?type=`, Result by default) in one zip.

    Built from the same two seams as the single download, so the office adapter
    needs nothing new: the Result list says which images have an original, and
    `get_tiff_original` fetches each. One that vanished between the two (past
    retention) is left out rather than failing the whole archive.
    """
    image_type = request.args.get("type", "tiff")
    if image_type not in _VALID_IMAGE_TYPES:
        return "Invalid image type", 404

    tool_name = _tool_name()
    decoded_filename = unquote(filename)
    names = [
        image["name"]
        for image in list_analysis_images(decoded_filename, image_type, tool_name)
        if image.get("original_url")
    ]

    # ponytail: the archive is built in memory, so its peak is the sum of the
    # originals (36 points x the TIFF size, OFFICE-VERIFY). Accepted on purpose:
    # the server has 8 GB (user-confirmed 2026-10-03), so even 36 x 50 MB fits.
    # Stream through a SpooledTemporaryFile only if concurrent zips run it out.
    buffer = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            original = get_tiff_original(decoded_filename, name, tool_name)
            if original is not None:
                archive.writestr(original["filename"], original["data"])
                count += 1

    if count == 0:
        return "TIFF file not found", 404

    stem = decoded_filename.removesuffix(".csv").removesuffix(".pkl")
    suffix = "TIFF" if image_type == "tiff" else f"{image_type}_original"
    return _attachment(buffer.getvalue(), "application/zip", f"{stem}_{suffix}.zip")


@bp.get("/afm/files/<path:filename>/images.zip")
def afm_images_zip(filename: str):
    """Every displayed image of one type (`?type=`) in a single zip.

    Composed from the list and the single-image seams, like `tiff.zip`, so the
    office adapter needs nothing new. An image past retention is left out.
    """
    image_type = request.args.get("type", "")
    if image_type not in _VALID_IMAGE_TYPES:
        return "Invalid image type", 404

    tool_name = _tool_name()
    decoded_filename = unquote(filename)
    buffer = io.BytesIO()
    count = 0
    # Stored, not deflated: a webp is already compressed.
    with zipfile.ZipFile(buffer, "w") as archive:
        for image in list_analysis_images(decoded_filename, image_type, tool_name):
            body = get_analysis_image_svg(decoded_filename, image_type, image["name"], tool_name)
            if body is not None:
                archive.writestr(image["name"], body)
                count += 1

    if count == 0:
        return "Image file not found", 404

    stem = decoded_filename.removesuffix(".csv").removesuffix(".pkl")
    return _attachment(buffer.getvalue(), "application/zip", f"{stem}_{image_type}.zip")


def _image(body: str | bytes) -> Response:
    # The mock draws a placeholder SVG (str); the office hands over the stored
    # webp conversion as it is (bytes).
    return Response(body, mimetype="image/svg+xml" if isinstance(body, str) else "image/webp")


def _attachment(data: bytes, content_type: str, name: str) -> Response:
    # RFC 5987: a recipe name can carry spaces and parentheses, and a bare
    # filename= with anything non-ASCII makes the browser mangle the name.
    return Response(
        data,
        content_type=content_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{name}\"; filename*=UTF-8''{quote(name)}"
            ),
            # Originals do not change once written but may be deleted at
            # retention, so revalidate rather than cache.
            "Cache-Control": "no-cache",
        },
    )


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
