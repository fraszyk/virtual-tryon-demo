# Virtual Try-On Demo

AI-powered virtual try-on using **FLUX.2 Pro** masked inpainting + **GPT-5.4 mini** garment classification + **MediaPipe** body landmark detection. Upload a person photo and one or more garment images — only the clothing region changes; face, pose, and background are preserved pixel-for-pixel.

---

## How it works

### Architecture

```
Person photo  ──┐
                ├──► GPT-5.4 mini (garment classifier) ──► garment type + description
Garment photo ──┘
                        │
                        ▼
              MediaPipe Pose + FaceMesh
              (body landmark detection)
                        │
                        ▼
              mask_builder.py
              (garment-type → binary B&W mask)
              white = inpaint here
              black = preserve exactly
                        │
                        ▼
              FLUX Fill Pro (inpainting endpoint)
              image (canvas) + mask + prompt
                        │
                        ▼
              Result image — only masked region changed
```

### Sequential multi-garment inpainting

For multiple garments (e.g. jacket + hat + backpack), inpainting is applied sequentially:

```
canvas = source_person_image.copy()
for each garment:
    mask = mask_builder.build_mask(canvas, garment_type)
    canvas = flux_fill.inpaint(canvas, mask, prompt)
return canvas
```

Every step preserves everything outside the white mask region.

### Mask strategies per garment type

| Garment | Mask region |
|---------|------------|
| glasses / sunglasses | Eye area + nose bridge (FaceMesh landmarks) |
| hat / cap / beanie | Top of head above eyebrows (Pose + FaceMesh) |
| scarf / tie / necklace | Neck to upper chest |
| shirt / jacket / coat / hoodie | Shoulders to hips (torso) |
| dress / jumpsuit | Shoulders to knees |
| pants / jeans / shorts | Hips to ankles |
| shoes / boots | Ankle region |
| backpack | Upper back / torso area |
| bag / handbag | Hip-side region |
| belt | Narrow hip-level band |
| unknown | Torso fallback |

Masks are dilated by 25px and thresholded to pure black/white (no grey).

### Inpainting prompt template

```
Task: virtual try-on via MASKED INPAINTING.
Rules: Modify ONLY the masked (white) region.
Preserve everything outside the mask exactly — identity, face, pose, background, lighting, camera angle.
Replace the masked region with: {garment_description}.
Fit requirements: natural fit to body geometry and pose, realistic folds, shadows and occlusions.
Do not change facial features or body proportions.
```

---

## Setup

### Prerequisites

- Python 3.10+ (`py -3`)
- Azure AI Foundry account with these models deployed:
  - **FLUX.2 Pro** (`flux-pro-v1.1-fill`) — for inpainting ← **required**
  - **GPT-5.4 mini** (`gpt-5.4-mini`) — for garment classification

### Install & run

```bat
cd backend
run.bat
```

The script creates a `.venv`, installs dependencies, and starts Flask on `http://localhost:5000`.

### Environment variables (`.env`)

```env
AZURE_BASE_URL=https://<your-resource>.services.ai.azure.com/openai/v1
AZURE_API_KEY=<your-key>
AZURE_FLUX_FILL_MODEL=flux-pro-v1.1-fill   # FLUX.2 Pro deployment name
AZURE_VISION_MODEL=gpt-5.4-mini            # GPT-5.4 mini deployment name
AZURE_FLUX_MODEL=FLUX.1-Kontext-pro        # (unused for try-on, kept for reference)
```

> **Note:** If FLUX Fill is not available on Azure, set `BFL_API_KEY` to use the direct BFL API (`api.bfl.ai`). The service will automatically fall back.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/tryon` | Generate try-on (multipart: `person`, `garments[]`, `notes`, `n`) |
| `POST` | `/api/mask-preview` | Return mask overlay PNG for debug (multipart: `person`, `garments`) |

### `/api/tryon` response

```json
{
  "images": ["<base64 PNG>", ...]
}
```

### `/api/mask-preview` response

```json
{
  "mask_overlay": "<base64 PNG with red overlay on inpaint region>"
}
```

---

## Debug: mask overlay

Click **🎭 Mask** in the UI before generating to preview where the mask will be applied (red = inpaint region). Use this to verify the mask is on the correct body part.

---

## Troubleshooting: mask doesn't work

### 1. Canvas size ≠ mask size

**Symptom:** `AssertionError: Mask/canvas size mismatch`  
**Fix:** `mask_builder.build_mask()` always returns a mask with the same size as `person_img`. Check that you are passing the same PIL Image to both functions without resizing in between.

### 2. Wrong mask polarity (black/white inverted)

**Symptom:** Entire image except clothing changes (background gets edited, person disappears)  
**Fix:** FLUX Fill convention: **white = inpaint, black = preserve**. Check that `mask.getpixel((cx, cy))` in the clothing region returns 255, not 0.

### 3. Grey mask (not pure black/white)

**Symptom:** Soft or blurry transitions, API errors about mask format  
**Fix:** `mask_builder.py` applies `cv2.threshold` to produce pure binary output. If you're generating masks elsewhere, ensure you threshold: `_, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)`.

### 4. Wrong inpainting endpoint (Kontext instead of Fill)

**Symptom:** Person identity changes, face/body gets regenerated  
**Cause:** FLUX.1-Kontext-pro is an image-to-image editing model, not an inpainting model. It ignores masks.  
**Fix:** Deploy `flux-pro-v1.1-fill` in Azure AI Foundry and set `AZURE_FLUX_FILL_MODEL` in `.env`. FLUX Fill respects the mask and only generates in white areas.

### 5. MediaPipe detects no landmarks

**Symptom:** Mask falls back to proportional bounding box (may be too large/small)  
**Cause:** Low-res image, unusual pose, heavy occlusion, or dark/low-contrast photo  
**Fix:** Use a clear, well-lit photo where the person's body is mostly visible. Increase `min_detection_confidence` in `mask_builder.py` down to `0.2` for difficult images.

### 6. FLUX Fill returns 400 / model not found

**Symptom:** `Azure FLUX Fill [404]: DeploymentNotFound`  
**Fix:** The model name in `AZURE_FLUX_FILL_MODEL` must match the exact deployment name in your Azure AI Foundry project. Check the portal under **Deployments**.

### 7. All-black mask → output identical to input

This is the correct behaviour (black = preserve everything). If you see this:
- Check that `analyze_garment()` returned a recognised garment type.
- Check the MediaPipe pose detection log for "no landmarks detected".
- Try the **🎭 Mask** preview button to see the raw mask before generating.
