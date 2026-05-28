# Virtual Try-On Demo

A simple demo that uses AI to generate a virtual try-on image: upload a photo
of a person and one or more clothing items, and the app produces a composite
image of the same person wearing those clothes.

Powered by **FLUX.2 Pro** (inpainting) and **GPT-5.4 mini** (garment classification) on **Azure AI Foundry**, using masked inpainting via MediaPipe body landmark detection.

## How it works

1. **GPT-5.4 mini** classifies the uploaded garment image (type + description)
2. **MediaPipe** detects body landmarks to generate a precise binary mask (white = inpaint, black = preserve)
3. **FLUX.2 Pro** (FLUX Fill) inpaints only the masked region — face, pose and background are preserved pixel-for-pixel
4. For multiple garments, inpainting is applied sequentially on the same canvas

## Project Structure

```
virtual-tryon-demo/
├── backend/
│   ├── src/
│   │   ├── app.py                          # Flask app + serves the UI
│   │   ├── index.html                      # Drag-and-drop UI
│   │   ├── api/routes.py                   # POST /api/tryon, POST /api/mask-preview
│   │   ├── services/
│   │   │   ├── inpaint_service.py          # FLUX.2 Pro inpainting
│   │   │   ├── vision_service.py           # GPT-5.4 mini garment classification
│   │   │   └── mask_builder.py             # MediaPipe → binary mask
│   │   ├── models/schemas.py
│   │   └── core/config.py
│   ├── requirements.txt
│   ├── run.bat                             # One-click start (Windows)
│   └── .env.example
└── frontend/                               # Optional React frontend (not required)
```

## Quick Start

### 1. Configure Azure AI Foundry

Deploy the following models in [Azure AI Foundry](https://ai.azure.com):

| Model | Purpose | Env var |
|-------|---------|---------|
| **FLUX.2 Pro** (`flux-pro-v1.1-fill`) | Inpainting | `AZURE_FLUX_FILL_MODEL` |
| **GPT-5.4 mini** | Garment classification | `AZURE_VISION_MODEL` |

### 2. Set up environment

```bat
cd backend
copy .env.example .env
```

Edit `.env`:

```env
AZURE_BASE_URL=https://<your-resource>.services.ai.azure.com/openai/v1
AZURE_API_KEY=<your-foundry-api-key>
AZURE_FLUX_FILL_MODEL=flux-pro-v1.1-fill
AZURE_VISION_MODEL=gpt-5.4-mini
```

> Get the base URL and key from **Keys and Endpoint** page of your Azure AI Foundry resource.

### 3. Run

```bat
cd backend
run.bat
```

Open <http://localhost:5000> in your browser.

## How to use

1. Drop a photo of a person into the **Person photo** area.
2. Drop one or more clothing item images into **Clothing items**.
3. (Optional) Add styling notes (e.g. *"tuck the shirt in, outdoor setting"*).
4. Click **🎭 Mask** to preview the inpaint region before generating.
5. Click **Generate Try-On**. Results appear on the right and are saved to `backend/results/`.

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/tryon` | Generate try-on |
| `POST` | `/api/mask-preview` | Preview mask overlay (debug) |
| `GET`  | `/api/health` | Health check |

`POST /api/tryon` — `multipart/form-data`

| Field      | Type            | Notes                                       |
|------------|-----------------|---------------------------------------------|
| `person`   | file (image)    | Required. Photo of the person.              |
| `garments` | file(s) (image) | Required. One or more clothing item images. |
| `notes`    | string          | Optional styling notes.                     |
| `n`        | integer 1–4     | Number of variations (default 1).           |

Response: `{ "images": ["data:image/png;base64,..."] }`

## Notes

- FLUX.2 Pro preserves identity, face, pose and background — only the masked clothing region is changed.
- FLUX.2 Pro and GPT-5.4 mini on Azure AI Foundry are billed per use — see your Foundry deployment page for pricing.
- The React frontend in `frontend/` is optional — the backend serves a self-contained HTML/JS UI.
