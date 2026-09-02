from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from back_dev_home.msr_file.contracts import MsrArtifactError
from back_dev_home.msr_file.data import get_msr_artifact, get_msr_file


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


@bp.post("/msr-files")
def msr_files_bulk():
    """Batch sibling of /msr-file.

    The skewvoir AnalyzePanel multi-selects MSRs; one request per MSR trips the
    per-user rate limit (50/5s in back_dev_home/__init__.py) and leaves the panel
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

        # bool is a subclass of int, so guard against it; also reject negatives to
        # match the single endpoint's isdigit() validation.
        total_images = item.get("total_images")
        if not isinstance(total_images, int) or isinstance(total_images, bool) or total_images < 0:
            total_images = None

        result = get_msr_file(msr, class_name, total_images)
        if result is not None:
            results.append(result)

    return jsonify({"results": results})


@bp.get("/msr-file/download")
def msr_file_download():
    """Serve the MinIO original behind an MSR — raw .MSR text or the pickle.

    Deliberately keyed on `msr`, never on a MinIO key. Our credentials are
    valid for the whole `user/2067928/` prefix (image_cache and other apps'
    objects included), so accepting a key from the caller would turn this into
    a read primitive over that entire prefix. Taking the id and letting the
    adapter look the path up in meas_hist keeps the reachable set to objects
    that a measurement actually points at.

    Sits under /msr-file/ so the activity logger files it as `skewvoir`
    without a feature_map entry — _logging matches a path prefix plus "/".
    """
    msr = (request.args.get("msr") or "").strip()
    if not msr:
        return jsonify({"error": "msr query param is required"}), 400

    kind = (request.args.get("kind") or "").strip()
    if not kind:
        return jsonify({"error": "kind query param is required (raw | pkl)"}), 400

    try:
        artifact = get_msr_artifact(msr, kind)
    except MsrArtifactError as exc:
        return jsonify({"error": exc.message, "kind": kind, "msr": msr}), exc.status

    # RFC 5987: the office filename can carry non-ASCII, and a bare filename=
    # with such bytes makes the browser save "download" or mangle the name.
    name = artifact["filename"]
    disposition = f"attachment; filename=\"{name}\"; filename*=UTF-8\'\'{quote(name)}"
    return Response(
        artifact["data"],
        # content_type, NOT mimetype: Flask appends its own charset to any
        # mimetype starting with "text/", which both doubles the parameter on
        # the mock's utf-8 text AND silently stamps UTF-8 onto the office's
        # deliberately charset-less text/plain — the one label that must stay
        # off until the .MSR encoding is verified.
        content_type=artifact["content_type"],
        headers={
            "Content-Disposition": disposition,
            # An MSR's originals never change once written, but they DO get
            # deleted at retention, so a long browser cache would keep serving
            # a file the store no longer has. Revalidate instead.
            "Cache-Control": "no-cache",
        },
    )
