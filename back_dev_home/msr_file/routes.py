from flask import Blueprint, jsonify, request

from back_dev_home.msr_file.data import get_msr_file


bp = Blueprint("msr_file", __name__)


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
