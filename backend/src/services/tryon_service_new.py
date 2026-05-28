"""Virtual try-on service — FLUX.2-pro on Azure AI Foundry.

Uses BFL's image_prompt (image-to-image) API to preserve the person's
identity while dressing them in the provided garments.

Flow:
  1. POST {endpoint}  -> {"id": "...", "polling_url": "..."} or synchronous result
  2. GET  polling_url -> {"status": "Ready", "data": [{...}]}  (BFL async)
"""

from __future__ import annotations

import base64
import io
import logging
import os
import time
from datetime import datetime
from typing import Iterable, List

import requests
from PIL import Image

from core.config import Config

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 2.0
POLL_TIMEOUT_S = 180


class TryOnService:
    def __init__(self) -> None:
        if not Config.AZURE_FLUX_API_KEY or not Config.AZURE_FLUX_ENDPOINT:
            logger.warning(
                "AZURE_FLUX_ENDPOINT or AZURE_FLUX_API_KEY is not set. "
                "/api/tryon will fail until both are configured."
            )
        os.makedirs(Config.RESULTS_FOLDER, exist_ok=True)

    @staticmethod
    def _to_b64_png(file_storage, max_side: int = 1536) -> str:
        img = Image.open(file_storage.stream).convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def _build_prompt(self, garment_count: int, notes: str | None) -> str:
        garment_desc = (
            "the exact clothing item shown in the reference garment image"
            if garment_count == 1
            else f"all {garment_count} clothing items shown in the reference garment images"
        )
        prompt = (
            "Virtual try-on: Take the exact person from the reference image — preserving their "
            "face, facial features, skin tone, hair color and style, body proportions, and pose "
            f"completely unchanged — and dress them in {garment_desc}. "
            "Render the clothing with photorealistic fabric texture, natural draping, correct fit "
            "and proportions. The person's identity must be indistinguishable from the input photo. "
            "Keep the original background. No text, no watermarks."
        )
        if notes:
            prompt += f" {notes.strip()}"
        return prompt

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "api-key": Config.AZURE_FLUX_API_KEY,
            "Authorization": f"Bearer {Config.AZURE_FLUX_API_KEY}",
        }

    def _submit(self, payload: dict) -> dict:
        resp = requests.post(
            Config.AZURE_FLUX_ENDPOINT,
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"FLUX submit failed [{resp.status_code}]: {resp.text}")
        return resp.json()

    def _poll(self, polling_url: str) -> dict:
        deadline = time.time() + POLL_TIMEOUT_S
        while time.time() < deadline:
            r = requests.get(polling_url, headers=self._headers(), timeout=30)
            if r.status_code >= 400:
                raise RuntimeError(f"FLUX poll failed [{r.status_code}]: {r.text}")
            data = r.json()
            status = (data.get("status") or "").lower()
            if status in ("ready", "succeeded", "completed"):
                return data
            if status in ("error", "failed", "content_moderated", "request_moderated"):
                raise RuntimeError(f"FLUX job ended with status '{status}': {data}")
            time.sleep(POLL_INTERVAL_S)
        raise TimeoutError("Timed out waiting for FLUX result.")

    @staticmethod
    def _extract_image_b64(result_payload: dict) -> str:
        # OpenAI-style: {"data": [{"b64_json": "..."}]}
        data_list = result_payload.get("data")
        if data_list and isinstance(data_list, list):
            item = data_list[0]
            b64 = item.get("b64_json") or item.get("url")
            if b64:
                if b64.startswith("http"):
                    r = requests.get(b64, timeout=60)
                    r.raise_for_status()
                    return base64.b64encode(r.content).decode("ascii")
                if b64.startswith("data:"):
                    return b64.split(",", 1)[1]
                return b64

        # BFL async-style: {"result": {"sample": "..."}}
        result = result_payload.get("result") or {}
        sample = result.get("sample") or result.get("image") or result.get("b64_json")
        if sample:
            if isinstance(sample, str) and sample.startswith("http"):
                r = requests.get(sample, timeout=60)
                r.raise_for_status()
                return base64.b64encode(r.content).decode("ascii")
            if isinstance(sample, str) and sample.startswith("data:"):
                return sample.split(",", 1)[1]
            return sample

        raise RuntimeError(f"No image in result payload: {result_payload}")

    def generate_tryon(
        self,
        person_file,
        garment_files: Iterable,
        notes: str | None = None,
        n: int = 1,
    ) -> List[str]:
        if not Config.AZURE_FLUX_ENDPOINT or not Config.AZURE_FLUX_API_KEY:
            raise RuntimeError("Azure FLUX endpoint/key are not configured on the server.")

        garment_files = list(garment_files)
        if not garment_files:
            raise ValueError("At least one clothing image is required.")

        person_b64 = self._to_b64_png(person_file)
        garments_b64 = [self._to_b64_png(g) for g in garment_files]
        prompt = self._build_prompt(len(garments_b64), notes)
        n = max(1, min(int(n), 4))

        data_urls: List[str] = []
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        for i in range(n):
            payload = {
                "model": Config.AZURE_FLUX_MODEL,
                "image_prompt": person_b64,
                "image_prompt_strength": Config.FLUX_IMAGE_PROMPT_STRENGTH,
                "prompt": prompt,
                "width": Config.FLUX_IMAGE_WIDTH,
                "height": Config.FLUX_IMAGE_HEIGHT,
                "prompt_upsampling": True,
                "safety_tolerance": 2,
                "output_format": "png",
            }
            submit = self._submit(payload)
            polling_url = submit.get("polling_url") or (submit.get("urls") or {}).get("get")

            if polling_url:
                result = self._poll(polling_url)
                b64 = self._extract_image_b64(result)
            else:
                b64 = self._extract_image_b64(submit)

            out_path = os.path.join(Config.RESULTS_FOLDER, f"tryon_{ts}_{i}.png")
            try:
                with open(out_path, "wb") as f:
                    f.write(base64.b64decode(b64))
            except OSError as e:
                logger.warning("Could not save result image: %s", e)
            data_urls.append(f"data:image/png;base64,{b64}")

        if not data_urls:
            raise RuntimeError("FLUX returned no image data.")
        return data_urls
