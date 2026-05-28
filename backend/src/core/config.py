from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Azure AI Foundry — OpenAI-compatible endpoint
    AZURE_BASE_URL = os.getenv("AZURE_BASE_URL", "").rstrip("/")
    AZURE_API_KEY = os.getenv("AZURE_API_KEY", "")

    # FLUX.1-Kontext-pro — for reference/non-tryon tasks only
    AZURE_FLUX_MODEL = os.getenv("AZURE_FLUX_MODEL", "FLUX.1-Kontext-pro")

    # FLUX Fill Pro — inpainting model (image + mask → inpainted result)
    # Deploy "flux-pro-v1.1-fill" (or "FLUX.1-Fill-pro") in Azure AI Foundry
    # and set this env var to the exact deployment name.
    AZURE_FLUX_FILL_MODEL = os.getenv("AZURE_FLUX_FILL_MODEL", "flux-pro-v1.1-fill")

    FLUX_IMAGE_SIZE = os.getenv("FLUX_IMAGE_SIZE", "1024x1536")

    # Vision model for image understanding (GPT-4o or similar)
    AZURE_VISION_MODEL = os.getenv("AZURE_VISION_MODEL", "gpt-5.4-mini")

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    RESULTS_FOLDER = os.getenv("RESULTS_FOLDER", "results")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
