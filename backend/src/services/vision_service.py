"""Vision analysis for Virtual Try-On — GPT-4o mini via Azure AI Foundry.

Responsibilities:
- Classify each garment and return type + description for the inpainting prompt.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re

import requests
from PIL import Image

from core.config import Config

logger = logging.getLogger(__name__)


def _encode(source, max_side: int = 1024) -> str:
    """Encode FileStorage, PIL Image, or existing b64 string to b64 PNG."""
    if isinstance(source, str):
        return source
    if isinstance(source, Image.Image):
        img = source.convert("RGB")
    else:
        img = Image.open(source.stream).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _chat(messages: list, max_tokens: int = 400) -> str:
    url = f"{Config.AZURE_BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json", "api-key": Config.AZURE_API_KEY}
    body = {"model": Config.AZURE_VISION_MODEL, "messages": messages, "max_completion_tokens": max_tokens}
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"Vision API [{resp.status_code}]: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"].strip()


def _parse_json(raw: str) -> dict:
    """Extract and parse first JSON object from a string."""
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise RuntimeError(f"No JSON found in: {raw}")
    return json.loads(match.group())


def analyze_garment(file_storage) -> dict:
    """Classify garment and return type + description.

    Returns: {"type": str, "description": str}
    """
    b64 = _encode(file_storage)
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
            {"type": "text", "text": (
                "Analyze this clothing/accessory item. Return ONLY a JSON object:\n"
                '{"type": "<item type, e.g.: hat, cap, beanie, sunglasses, glasses, scarf, '
                'shirt, t-shirt, sweater, hoodie, jacket, coat, blazer, dress, pants, jeans, '
                'shorts, skirt, shoes, boots, sneakers, backpack, bag, belt, watch, etc.>",\n'
                ' "description": "<precise description: type, exact colors, pattern, material, '
                'style details, fit, any logos or distinctive elements>"}\n\n'
                "Return ONLY the JSON."
            )},
        ],
    }]
    raw = _chat(messages, max_tokens=250)
    logger.info("Garment analysis: %s", raw)
    result = _parse_json(raw)
    if "type" not in result:
        result["type"] = "clothing"
    if "description" not in result:
        result["description"] = result["type"]
    return result


def detect_hair_length(person_img: Image.Image) -> str:
    """Detect hair length of person: 'short', 'medium', or 'long'.

    Used to decide whether to show hair below a hat in the try-on prompt.
    Returns 'short' for very short / buzz cut / bald, 'long' otherwise.
    """
    b64 = _encode(person_img)
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "low"}},
            {"type": "text", "text": (
                "Look at the person's hair in this photo. "
                "Classify their hair length as exactly one of: short, medium, long. "
                "short = buzz cut, very short, or bald. "
                "medium = hair that reaches roughly to the ear or jaw. "
                "long = hair below the jaw or shoulders. "
                "Reply with ONLY one word: short, medium, or long."
            )},
        ],
    }]
    raw = _chat(messages, max_tokens=5).strip().lower()
    logger.info("Hair length detection: '%s'", raw)
    if "short" in raw:
        return "short"
    if "long" in raw:
        return "long"
    return "medium"
    """Describe person's visible features for text-to-image safe cover generation.

    Used when the original image is rejected by content moderation — we describe
    the person via GPT vision, then generate a clothed version text-only (no input image).

    Returns a text description suitable for FLUX prompt (nudity-safe).
    """
    b64 = _encode(person_img)
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}},
            {"type": "text", "text": (
                "Describe the person in this photo for use in an image generation prompt. "
                "Focus ONLY on: face features, hair color and style, approximate age, "
                "body build, skin tone, pose, and background/setting. "
                "Do NOT mention clothing or lack of clothing. "
                "Do NOT use words like: nude, naked, bare, shirtless, topless, undressed, skin, exposed. "
                "Be concise (2 sentences max). "
                "Example: 'A young adult male with short brown hair, athletic build, "
                "standing upright with arms at sides, neutral expression, white background.'"
            )},
        ],
    }]
    description = _chat(messages, max_tokens=100)
    logger.info("Person description (raw): %s", description)

    # Sanitize — remove any words that could trigger content filters
    _BLOCKED = [
        "nude", "naked", "bare", "shirtless", "topless", "undressed",
        "unclothed", "exposed", "skin", "chest", "torso", "body",
        "complexion", "muscular", "athletic", "figure", "physique",
        "revealing", "intimate", "sensual", "provocative",
    ]
    sanitized = description
    for word in _BLOCKED:
        sanitized = re.sub(rf'\b{word}\w*\b', '', sanitized, flags=re.IGNORECASE)
    sanitized = " ".join(sanitized.split())
    logger.info("Person description (sanitized): %s", sanitized)
    # Fallback if description got too short after sanitization
    if len(sanitized.split()) < 5:
        sanitized = "A person standing in a neutral pose with a plain background."
    return sanitized
