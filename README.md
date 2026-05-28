# Virtual Try-On Demo

A simple demo that uses AI to generate a virtual try-on image: upload a photo
of a person and one or more clothing items, and the app produces a composite
image of the same person wearing those clothes.

Powered by **Black Forest Labs FLUX.2 Pro on Azure AI Foundry**, using the
model's `input_images` reference-image feature.

## Project Structure

```
virtual-tryon-demo/
├── backend/
│   ├── src/
│   │   ├── app.py                  # Flask app + serves the demo UI
│   │   ├── index.html              # Simple drag-and-drop UI
│   │   ├── api/routes.py           # POST /api/tryon
│   │   ├── services/tryon_service.py  # OpenAI image-edit integration
│   │   ├── models/schemas.py
│   │   └── core/config.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/                       # Optional React frontend (not required)
```

## Quick Start

### 1. Install backend dependencies

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

### 2. Configure your Azure AI Foundry deployment

```bash
copy .env.example .env            # Windows
# cp .env.example .env            # macOS / Linux
```

Edit `.env`:

```
AZURE_FLUX_ENDPOINT=https://<your-resource>.services.ai.azure.com/providers/blackforestlabs/v1/flux-2-pro
AZURE_FLUX_API_KEY=<your-foundry-api-key>
```

> Get the endpoint URL and key from the FLUX.2 Pro deployment's **"Consume"** /
> **"Keys and Endpoint"** page in Azure AI Foundry.

### 3. Run

```bash
python src/app.py
```

Open <http://localhost:5000> in your browser.

## How to use

1. Drop a photo of a person into the **Person photo** area.
2. Drop one or more clothing item images into **Clothing items**.
3. (Optional) Add styling notes (e.g. *"tuck the shirt in, outdoor setting"*).
4. Choose how many variations to generate (1–4).
5. Click **Generate Try-On**. Generated images appear on the right and are also
   saved into the `backend/results/` folder.

## API

`POST /api/tryon` — `multipart/form-data`

| Field      | Type            | Notes                                        |
|------------|-----------------|----------------------------------------------|
| `person`   | file (image)    | Required. Photo of the person.               |
| `garments` | file(s) (image) | Required. One or more clothing item images.  |
| `notes`    | string          | Optional styling notes.                      |
| `n`        | integer 1–4     | Optional. Number of variations (default 1).  |

Response: `{ "images": ["data:image/png;base64,..."] }`

## Notes

- The model preserves the person's face, body, and pose while replacing the
  outfit. Quality depends on the clarity of input photos.
- FLUX.2 Pro on Azure AI Foundry is billed per image — see your Foundry
  deployment page for current pricing.
- The optional React frontend in `frontend/` is not needed to run the demo —
  the backend serves a self-contained HTML/JS UI.
