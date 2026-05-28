"""inpaint_service.py — Virtual try-on via Azure BFL native endpoint.

Endpoint: https://<resource>.services.ai.azure.com/providers/blackforestlabs/v1/flux-2-pro?api-version=preview
Auth: Authorization: Bearer <api_key>

FLUX.2-pro try-on payload:
  model: "FLUX.2-pro"
  input_image:   full person photo (base64)   — sets pose/framing
  input_image_2: face crop from person photo  — locks identity/gender/face
  prompt: clothing edit instruction with explicit identity lock
  width/height: from image dimensions
  n: 1
"""
from __future__ import annotations

import base64
import io
import logging
import time

import requests
from PIL import Image

from core.config import Config

logger = logging.getLogger(__name__)

INPAINT_PROMPT_TEMPLATE = (
    "Virtual try-on photo edit. "
    "Keep the exact same person — same face, hair color, hair length, age, pose, and background. "
    "Change only the outfit. "
    "The person is now wearing: {garment_description}. "
    "Photorealistic result."
)

INPAINT_PROMPT_TEMPLATE_HAT = (
    "Virtual try-on photo edit. "
    "Keep the exact same person — same face, hair color, hair length, age, pose, and background. "
    "Place the hat/cap naturally on the person's head. "
    "Hair color and visible length below the hat must remain the same. "
    "The face must stay completely unchanged. "
    "The person is now wearing: {garment_description}. "
    "Photorealistic result."
)

INPAINT_PROMPT_TEMPLATE_HAT_SHORT_HAIR = (
    "Virtual try-on photo edit. "
    "Keep the exact same person — same face, age, pose, and background. "
    "Place the hat/cap naturally on the person's head. "
    "The person has very short hair — no hair should be visible below or around the hat. "
    "The face must stay completely unchanged. "
    "The person is now wearing: {garment_description}. "
    "Photorealistic result."
)


def _resource_root() -> str:
    return Config.AZURE_BASE_URL.split("/openai")[0]


def _bfl_base_url() -> str:
    return f"{_resource_root()}/providers/blackforestlabs/v1"


def _bearer_headers() -> dict:
    return {
        "Authorization": f"Bearer {Config.AZURE_API_KEY}",
        "Content-Type": "application/json",
    }


def _encode_image(img: Image.Image, max_side: int = 1536) -> str:
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _crop_face(img: Image.Image, has_hat: bool = False) -> Image.Image:
    """Crop face region for identity lock.

    No hat: top 35% — includes hair top → locks face AND hair style/color.
    Has hat: middle face only (y 12%–32%, center 60% of width) — skips
             top of head so hat placement doesn't conflict with face reference.
    """
    w, h = img.size
    if has_hat:
        # Tight face crop — skip top of head (hat area)
        x1 = int(w * 0.20)
        y1 = int(h * 0.12)
        x2 = int(w * 0.80)
        y2 = int(h * 0.32)
    else:
        # Full face + hair crop
        x1 = 0
        y1 = 0
        x2 = w
        y2 = max(int(h * 0.35), 128)
    return img.crop((x1, y1, x2, y2))


def _b64_to_image(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")


def _url_to_image(url: str, timeout: int = 60) -> Image.Image:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


class ContentModerationError(Exception):
    """Raised when BFL rejects the image due to content policy."""


def _parse_bfl_response(data: dict) -> Image.Image:
    """Handle async (id → polling) and sync BFL responses."""
    if "id" in data:
        task_id = data["id"]
        poll_url = f"{_bfl_base_url()}/get_result?id={task_id}"
        logger.info("BFL async task %s — polling", task_id)
        for _ in range(60):
            time.sleep(3)
            result = requests.get(poll_url, headers=_bearer_headers(), timeout=30).json()
            status = result.get("status")
            logger.debug("BFL poll: %s", status)
            if status == "Ready":
                return _url_to_image(result["result"]["sample"])
            if status == "content_moderated":
                raise ContentModerationError("Image rejected by content moderation")
            if status in ("Error", "Failed"):
                raise RuntimeError(f"BFL task failed: {status}")
        raise RuntimeError("BFL task timed out after 3 minutes")

    if "result" in data:
        sample = data["result"].get("sample") or data["result"].get("url")
        return _url_to_image(sample)
    if "data" in data:
        item = data["data"][0]
        if "b64_json" in item:
            return _b64_to_image(item["b64_json"])
        return _url_to_image(item["url"])

    raise RuntimeError(f"Unexpected BFL response keys: {list(data.keys())}")


def _flux2_pro(person_img: Image.Image, prompt: str, has_hat: bool = False) -> Image.Image:
    """FLUX.2-pro via BFL native endpoint.

    input_image   = full person photo (pose/framing reference)
    input_image_2 = face crop — strategy depends on has_hat:
                    no hat  → top 35% (face + hair, full width)
                    has hat → center face only (y 12-32%) to avoid hat conflict
    width/height  = from source image (BFL uses these, not 'size')
    """
    endpoint = f"{_bfl_base_url()}/flux-2-pro?api-version=preview"
    face_crop = _crop_face(person_img, has_hat=has_hat)

    # Keep width/height as multiples of 32, max 1024
    w, h = person_img.size
    scale = min(1.0, 1024 / max(w, h))
    out_w = int(w * scale // 32) * 32
    out_h = int(h * scale // 32) * 32

    body = {
        "model": "FLUX.2-pro",
        "prompt": prompt,
        "input_image": _encode_image(person_img),
        "input_image_2": _encode_image(face_crop),
        "width": out_w,
        "height": out_h,
        "n": 1,
    }
    logger.info("FLUX.2-pro: endpoint=%s  size=%dx%d  face_crop=%s",
                endpoint, out_w, out_h, face_crop.size)
    resp = requests.post(endpoint, headers=_bearer_headers(), json=body, timeout=180)

    if resp.status_code >= 400:
        err_text = resp.text
        if resp.status_code == 400 and (
            "sexual content" in err_text.lower()
            or "content_moderated" in err_text.lower()
            or "content rejected" in err_text.lower()
        ):
            raise ContentModerationError(f"Image rejected by content moderation: {err_text[:200]}")
        raise RuntimeError(f"FLUX.2-pro [{resp.status_code}]: {err_text[:400]}")

    data = resp.json()
    logger.info("FLUX.2-pro response keys: %s", list(data.keys()))
    return _parse_bfl_response(data)


def _flux2_pro_text_only(prompt: str, width: int = 768, height: int = 1024) -> Image.Image:
    """FLUX.2-pro text-to-image (no input_image) — used for safe cover generation."""
    endpoint = f"{_bfl_base_url()}/flux-2-pro?api-version=preview"
    out_w = int(width // 32) * 32
    out_h = int(height // 32) * 32
    body = {
        "model": "FLUX.2-pro",
        "prompt": prompt,
        "width": out_w,
        "height": out_h,
        "n": 1,
    }
    logger.info("FLUX.2-pro text-only: %dx%d", out_w, out_h)
    resp = requests.post(endpoint, headers=_bearer_headers(), json=body, timeout=180)
    if resp.status_code >= 400:
        raise RuntimeError(f"FLUX.2-pro text-only [{resp.status_code}]: {resp.text[:300]}")
    return _parse_bfl_response(resp.json())


def _safe_cover(person_img: Image.Image) -> Image.Image:
    """Generate a clothed version of the person using text-only FLUX call.

    Strategy: GPT vision describes the person (face/pose/background) → FLUX generates
    fully clothed version from text — no input_image sent (avoids moderation on nude input).
    """
    from services import vision_service
    logger.info("Generating safe cover via text-to-image (no input image sent to FLUX)")
    person_desc = vision_service.describe_person_for_safe_cover(person_img)
    w, h = person_img.size
    safe_prompt = (
        f"Portrait photo of a person: {person_desc} "
        "Wearing a plain white t-shirt and grey trousers. "
        "Professional photo, neutral background."
    )
    return _flux2_pro_text_only(safe_prompt, width=w, height=h)


def build_prompt(garment_description: str, has_hat: bool = False, short_hair: bool = False) -> str:
    if has_hat and short_hair:
        template = INPAINT_PROMPT_TEMPLATE_HAT_SHORT_HAIR
    elif has_hat:
        template = INPAINT_PROMPT_TEMPLATE_HAT
    else:
        template = INPAINT_PROMPT_TEMPLATE
    return template.format(garment_description=garment_description)


def inpaint(
    canvas: Image.Image,
    mask: Image.Image,
    prompt: str,
    garment_img: Image.Image | None = None,
    strength: float = 0.92,
    has_hat: bool = False,
) -> Image.Image:
    """Run try-on via FLUX.2-pro with face-crop identity lock.

    has_hat=True  → tight face crop (skips top of head) + hat-aware prompt
    has_hat=False → full face+hair crop for maximum hair/face preservation

    If content moderation rejects the source image, automatically generates
    a safe-covered version (white tee + grey shorts) and retries from that.
    """
    assert canvas.size == mask.size, f"Canvas/mask size mismatch: {canvas.size} vs {mask.size}"
    logger.info("inpaint(): canvas=%s  has_hat=%s", canvas.size, has_hat)

    try:
        output = _flux2_pro(canvas, prompt, has_hat=has_hat)
    except ContentModerationError:
        logger.warning("Content moderation on original — generating safe cover and retrying")
        safe_canvas = _safe_cover(canvas)
        if safe_canvas.size != canvas.size:
            safe_canvas = safe_canvas.resize(canvas.size, Image.LANCZOS)
        output = _flux2_pro(safe_canvas, prompt, has_hat=has_hat)

    logger.info("FLUX.2-pro succeeded")
    if output.size != canvas.size:
        output = output.resize(canvas.size, Image.LANCZOS)
    return output
