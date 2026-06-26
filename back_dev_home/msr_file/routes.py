from flask import Blueprint, Response, jsonify, request

from back_dev_home.msr_file.data import get_msr_file, get_msr_image


bp = Blueprint("msr_file", __name__)

# Cap a single batch so a runaway client can't ask for an unbounded payload.
# The skewvoir picker only ever offers the 200 visible rows.
MAX_BULK = 200


@bp.get("/msr-file")
def msr_file_index():
    msr = (request.args.get("msr") or "").strip()
    if not msr:
        return jsonify({"error": "msr query param is required"}), 400

    class_name = (request.args.get("class_name") or "").strip() or None

    total_images_raw = (request.args.get("total_images") or "").strip()
    total_images = int(total_images_raw) if total_images_raw.isdigit() else None

    result = get_msr_file(msr, class_name, total_images)
    if result is None:
        return jsonify({"error": f"MSR not found: {msr}"}), 404

    return jsonify(result)


@bp.get("/msr-image")
def msr_image():
    """Serve a SEM micrograph for an mp_image filename.

    Office: the backend fetches the real image from the tool by this filename.
    Home: a deterministic SVG placeholder (see get_msr_image). The route + URL
    contract is identical across phases — only the data layer swaps.
    """
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name query param is required"}), 400

    svg = get_msr_image(name)
    return Response(
        svg,
        mimetype="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@bp.post("/msr-files")
def msr_files_bulk():
    """Batch sibling of /msr-file.

    The skewvoir AnalyzePanel multi-selects MSRs; one request per MSR trips the
    per-user rate limit (20/5s in back_dev_home/__init__.py) and leaves the panel
    stuck "loading". Collapsing the whole selection into a single request makes a
    200-MSR pick cost ONE rate-limit slot instead of 200.

    Body: {"items": [{"msr": str, "class_name": str|null, "total_images": int|null}, ...]}
    Returns: {"results": [MsrFileResponse, ...]} — found MSRs only, request order.
    Not-found MSRs are silently skipped (same shape the single endpoint 404s on),
    so the caller maps results by `msr` and ignores misses.
    """
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list):
        return jsonify({"error": "items must be a list"}), 400
    if len(items) > MAX_BULK:
        return jsonify({"error": f"items exceeds the {MAX_BULK}-MSR limit"}), 400

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        msr = str(item.get("msr") or "").strip()
        if not msr:
            continue

        class_name = item.get("class_name")
        class_name = class_name.strip() if isinstance(class_name, str) and class_name.strip() else None

        total_images = item.get("total_images")
        total_images = total_images if isinstance(total_images, int) else None

        result = get_msr_file(msr, class_name, total_images)
        if result is not None:
            results.append(result)

    return jsonify({"results": results})
