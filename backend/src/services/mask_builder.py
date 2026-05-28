"""mask_builder.py — Garment-type mask generation using proportional body regions.

Builds a binary mask (white=inpaint, black=preserve) based on garment type.
Uses proportional bounding boxes relative to image size — no external ML deps needed.

White (255) = region to replace with FLUX output.
Black  (0)  = region to preserve exactly (composited in from original).
"""
from __future__ import annotations

import io
import logging

import numpy as np
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# ── Garment type → mask strategy mapping ─────────────────────────────────────

GARMENT_TYPE_MAP: dict[str, str] = {
    "glasses": "glasses", "sunglasses": "glasses", "goggles": "glasses",
    "hat": "hat", "cap": "hat", "beanie": "hat", "helmet": "hat",
    "beret": "hat", "snapback": "hat", "bucket hat": "hat",
    "scarf": "neck", "tie": "neck", "bow tie": "neck", "necklace": "neck",
    "shirt": "top", "t-shirt": "top", "tee": "top", "polo": "top",
    "sweater": "top", "hoodie": "top", "sweatshirt": "top",
    "jacket": "top", "coat": "top", "blazer": "top", "vest": "top",
    "top": "top", "blouse": "top", "cardigan": "top",
    "dress": "dress", "gown": "dress", "jumpsuit": "dress", "romper": "dress",
    "pants": "pants", "jeans": "pants", "shorts": "pants", "skirt": "pants",
    "trousers": "pants", "leggings": "pants",
    "shoes": "shoes", "boots": "shoes", "sneakers": "shoes",
    "sandals": "shoes", "heels": "shoes", "loafers": "shoes",
    "backpack": "backpack", "rucksack": "backpack",
    "bag": "bag", "handbag": "bag", "tote": "bag", "purse": "bag",
    "belt": "belt",
}

# Proportional bounding boxes (fractions of image width/height)
# Tuned for a standard portrait/full-body photo with person centred.
_STRATEGY_BOXES: dict[str, tuple[float, float, float, float]] = {
    # (x1, y1, x2, y2) as fractions
    "glasses":  (0.22, 0.10, 0.78, 0.24),
    "hat":      (0.18, 0.00, 0.82, 0.18),
    "neck":     (0.32, 0.20, 0.68, 0.35),
    "top":      (0.10, 0.22, 0.90, 0.65),
    "dress":    (0.10, 0.22, 0.90, 0.92),
    "pants":    (0.12, 0.58, 0.88, 0.97),
    "shoes":    (0.15, 0.87, 0.85, 1.00),
    "backpack": (0.05, 0.20, 0.95, 0.72),
    "bag":      (0.00, 0.48, 0.48, 0.80),
    "belt":     (0.12, 0.57, 0.88, 0.65),
}


def _get_strategy(garment_type: str) -> str:
    g = garment_type.lower()
    for keyword, strategy in GARMENT_TYPE_MAP.items():
        if keyword in g:
            return strategy
    return "top"


def _dilate(mask_arr: np.ndarray, px: int) -> np.ndarray:
    """Simple dilation using max-pooling with a square kernel."""
    if px <= 0:
        return mask_arr
    from PIL import ImageFilter
    img = Image.fromarray(mask_arr, "L")
    # Use MaxFilter for dilation equivalent
    img = img.filter(ImageFilter.MaxFilter(size=px * 2 + 1))
    arr = np.array(img)
    arr[arr > 127] = 255
    arr[arr <= 127] = 0
    return arr


# ── Public API ────────────────────────────────────────────────────────────────

def build_mask(
    person_img: Image.Image,
    garment_type: str,
    dilate_px: int = 25,
) -> Image.Image:
    """Build a binary inpainting mask for the given garment type.

    Returns:
        PIL Image mode "L", same size as person_img.
        White (255) = region to inpaint.  Black (0) = preserve exactly.
    """
    w, h = person_img.size
    strategy = _get_strategy(garment_type)
    logger.info("Mask strategy: '%s' for garment type '%s'", strategy, garment_type)

    box = _STRATEGY_BOXES.get(strategy, _STRATEGY_BOXES["top"])
    x1 = int(box[0] * w)
    y1 = int(box[1] * h)
    x2 = int(box[2] * w)
    y2 = int(box[3] * h)

    mask_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask_img)
    draw.rectangle([x1, y1, x2, y2], fill=255)

    # Dilate + binarise
    mask_arr = _dilate(np.array(mask_img), dilate_px)
    result = Image.fromarray(mask_arr, mode="L")

    assert result.size == (w, h), f"Mask size mismatch: {result.size} vs {(w, h)}"
    logger.info("Mask built: size=%s  box=(%d,%d,%d,%d)", result.size, x1, y1, x2, y2)
    return result


def mask_to_png_bytes(mask: Image.Image) -> bytes:
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()


def mask_overlay(person_img: Image.Image, mask: Image.Image, alpha: float = 0.45) -> Image.Image:
    """Blend red mask overlay over person image for debug visualisation."""
    base = person_img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    mask_arr = np.array(mask)
    red = np.zeros((*mask_arr.shape, 4), dtype=np.uint8)
    red[mask_arr > 127] = [255, 0, 0, int(255 * alpha)]
    overlay.paste(Image.fromarray(red, "RGBA"))
    return Image.alpha_composite(base, overlay).convert("RGB")
