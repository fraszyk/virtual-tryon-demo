"""tryon_service.py — Virtual try-on via FLUX.2-pro multi-garment single-pass.

Pipeline:
  1. Load source person photo.
  2. Classify ALL garments in parallel → collect descriptions.
  3. Build single combined prompt with all garment descriptions.
  4. Single FLUX.2-pro call per variation — no sequential overwriting.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import List

import numpy as np
from PIL import Image

from services import vision_service
from services import mask_builder
from services import inpaint_service

logger = logging.getLogger(__name__)


HAT_TYPES = {"hat", "cap", "beanie", "baseball cap", "snapback", "bucket hat", "headwear", "beret", "fedora", "helmet"}

def _is_hat(garment_type: str) -> bool:
    return any(h in garment_type.lower() for h in HAT_TYPES)


class TryOnService:

    def generate_tryon(
        self,
        person_file,
        garment_files: List,
        notes: str | None = None,
        n: int = 1,
        strength: float = 0.92,
    ) -> List[str]:
        """Classify all garments, build one combined prompt, run single FLUX call per variation."""
        person_file.stream.seek(0)
        person_img = Image.open(person_file.stream).convert("RGB")
        logger.info("Source person image: %s", person_img.size)

        # Classify all garments and collect descriptions
        garment_descs: List[str] = []
        garment_types: List[str] = []
        for idx, garment_file in enumerate(garment_files):
            garment_file.stream.seek(0)
            garment_info = vision_service.analyze_garment(garment_file)
            garment_desc = garment_info.get("description", garment_info.get("type", "clothing item"))
            garment_type = garment_info.get("type", "top")
            garment_descs.append(garment_desc)
            garment_types.append(garment_type)
            logger.info("Garment %d: type='%s'  desc='%s'", idx + 1, garment_type, garment_desc)

        has_hat = any(_is_hat(t) for t in garment_types)
        logger.info("has_hat=%s  garment_types=%s", has_hat, garment_types)

        short_hair = False
        if has_hat:
            hair_length = vision_service.detect_hair_length(person_img)
            short_hair = (hair_length == "short")
            logger.info("hair_length=%s  short_hair=%s", hair_length, short_hair)

        # Build single combined prompt
        if len(garment_descs) == 1:
            combined_desc = garment_descs[0]
        else:
            *rest, last = garment_descs
            combined_desc = ", ".join(rest) + f" and {last}"

        prompt = inpaint_service.build_prompt(combined_desc, has_hat=has_hat, short_hair=short_hair)
        if notes:
            prompt += f" Additional styling notes: {notes}"
        logger.info("Combined prompt: %s", prompt[:120])

        # Build combined mask using already-classified garment types (no second API call)
        combined_mask = None
        for idx, garment_type in enumerate(garment_types):
            mask = mask_builder.build_mask(person_img, garment_type)
            if combined_mask is None:
                combined_mask = mask
            else:
                combined_arr = np.maximum(
                    np.array(combined_mask), np.array(mask)
                )
                combined_mask = Image.fromarray(combined_arr)

        results: List[str] = []
        for _ in range(max(1, n)):
            output = inpaint_service.inpaint(
                person_img.copy(), combined_mask, prompt, strength=strength, has_hat=has_hat
            )
            buf = io.BytesIO()
            output.save(buf, format="PNG")
            results.append(base64.b64encode(buf.getvalue()).decode("ascii"))

        return results

    def get_mask_preview(
        self,
        person_file,
        garment_file,
    ) -> str:
        """Return base64 PNG of mask overlay for debug/preview."""
        person_img = Image.open(person_file.stream).convert("RGB")
        garment_file.stream.seek(0)
        garment_info = vision_service.analyze_garment(garment_file)
        garment_type = garment_info.get("type", "top")
        mask = mask_builder.build_mask(person_img, garment_type)
        overlay = mask_builder.mask_overlay(person_img, mask)
        buf = io.BytesIO()
        overlay.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
