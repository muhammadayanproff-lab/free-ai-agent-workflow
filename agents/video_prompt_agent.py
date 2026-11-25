import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")
IMAGES_DIR = Path(os.getenv("PRODUCT_IMAGES_DIR", "source_product_images"))
PRODUCT_DETAILS = os.getenv("PRODUCT_DETAILS", "").strip()

def call_gemini(image_paths):
    parts = [{
        "text": f"""
You are a senior ecommerce creative director and product-visual analyst for Click & Collect Pakistan.

Analyze the supplied REAL Markaz product photographs carefully. Identify only visible, verifiable product attributes: shape, parts, colors, materials only when visually clear, proportions, packaging and included accessories. Clearly flag uncertain details. Never invent features.

Product context supplied by the owner:
{PRODUCT_DETAILS or "No additional product facts supplied."}

Return exactly two sections:
1. IMAGE ANALYSIS: concise bullet list of what is visibly confirmed and what must not be claimed.
2. ONE FINAL VIDEO PROMPT: write one polished, ready-to-copy prompt for a 10–15 second vertical 9:16 promotional video.

The one video prompt must:
- preserve the exact same product identity, silhouette, proportions, colors, visible controls, attachments and design as the reference photos
- show a believable use-case/problem-solution demonstration only if the photos/details support it
- specify shot sequence, camera motion, lighting, environment, human interaction only when suitable, pacing and final hero shot
- avoid fake features, extra accessories, altered logos, changed packaging, text overlays, subtitles, watermarks and brand marks not visible in the source
- be practical for an external image-to-video/video generator
- ask the video model not to morph, duplicate or redesign the product
- contain no unsupported discount, price, warranty, delivery or performance claims

Do not provide multiple prompt options. There must be ONE prompt only.
"""
    }]
    for path in image_paths:
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        parts.append({"inlineData": {"mimeType": mime, "data": data}})
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    payload = {"contents": [{"role": "user", "parts": parts}],
               "generationConfig": {"temperature": 0.25, "maxOutputTokens": 3500}}
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY}, method="POST")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                result = json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 4:
                raise RuntimeError(f"Gemini image-analysis request failed ({error.code}): {detail[:1000]}")
            time.sleep(5 * (2 ** attempt))
    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no image analysis.")
    answer = "\n".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if p.get("text")).strip()
    if "ONE FINAL VIDEO PROMPT" not in answer.upper() or len(answer) < 250:
        raise RuntimeError("Gemini response did not contain the required single video prompt.")
    return answer

def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")
    if not IMAGES_DIR.is_dir():
        raise RuntimeError(f"Product image folder does not exist: {IMAGES_DIR}")
    images = sorted(p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    if not images:
        raise RuntimeError(f"No product images found in {IMAGES_DIR}.")
    images = images[:5]
    report = call_gemini(images)
    out = Path("video_prompt_output")
    out.mkdir(parents=True, exist_ok=True)
    (out / "image_analysis_and_video_prompt.md").write_text(
        "# Product Image Analysis & Single Video Prompt\n\n"
        f"Reference images analyzed: {len(images)}\n\n{report}\n",
        encoding="utf-8")
    (out / "video_prompt.txt").write_text(report.split("ONE FINAL VIDEO PROMPT", 1)[-1].strip() + "\n", encoding="utf-8")
    (out / "reference_images.json").write_text(json.dumps([str(p) for p in images], indent=2) + "\n", encoding="utf-8")
    print("One 10–15 second video prompt generated. No video was rendered.")

if __name__ == "__main__":
    main()
