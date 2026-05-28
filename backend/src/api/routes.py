from flask import Blueprint, request, jsonify

from services.tryon_service import TryOnService

api_routes = Blueprint("api", __name__, url_prefix="/api")
_service = TryOnService()


@api_routes.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@api_routes.route("/tryon", methods=["POST"])
def tryon():
    person = request.files.get("person")
    if person is None:
        return jsonify({"error": "Missing 'person' image."}), 400

    garments = request.files.getlist("garments")
    if not garments:
        return jsonify({"error": "At least one 'garments' image is required."}), 400

    notes = request.form.get("notes", "").strip() or None
    try:
        n = int(request.form.get("n", "1"))
    except ValueError:
        n = 1
    try:
        strength = float(request.form.get("strength", "0.92"))
        strength = max(0.0, min(1.0, strength))
    except ValueError:
        strength = 0.92

    try:
        images = _service.generate_tryon(person, garments, notes=notes, n=n, strength=strength)
        return jsonify({"images": images}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Generation failed: {e}"}), 500


@api_routes.route("/mask-preview", methods=["POST"])
def mask_preview():
    """Return a debug mask overlay image for the given person + first garment."""
    person = request.files.get("person")
    if person is None:
        return jsonify({"error": "Missing 'person' image."}), 400

    garment = request.files.get("garments")
    if garment is None:
        # Try list form
        garments = request.files.getlist("garments")
        garment = garments[0] if garments else None
    if garment is None:
        return jsonify({"error": "Missing 'garments' image."}), 400

    try:
        b64 = _service.get_mask_preview(person, garment)
        return jsonify({"mask_overlay": b64}), 200
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Mask preview failed: {e}"}), 500

