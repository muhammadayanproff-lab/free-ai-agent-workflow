import json
import os
import re
import urllib.error
import urllib.request

MODEL = "gemini-3.5-flash-lite"

def main():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    product = os.environ.get("PRODUCT_NAME", "").strip()
    notes = os.environ.get("PRODUCT_NOTES", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")
    if not product:
        raise RuntimeError("PRODUCT_NAME is required.")

    prompt = f"""
You are the creative director for Click and Collect, a Pakistan-focused online store.
Create a concise, factual creative brief for a vertical social-media product promo.

Product name supplied by owner: {product}
Additional verified details supplied by owner: {notes or "None supplied"}

Return ONLY valid JSON with exactly these string keys:
image_prompt, video_title, video_subtitle, video_cta.

Rules:
- image_prompt: detailed photorealistic commercial product image prompt. Show the product clearly, clean premium studio setting, attractive lighting, vertical 9:16 composition. Do not add written words, logos, fake packaging, or invented product features.
- video_title: short attention-grabbing title, max 55 characters.
- video_subtitle: one short supporting line, max 75 characters. Only use facts in the supplied name/notes. If no benefits are verified, use a neutral line such as "A simple choice for everyday use".
- video_cta: short call to action, max 25 characters, e.g. "Shop now".
- Do not invent specifications, materials, performance, discounts, prices, warranties, or health claims.
- Keep wording natural for Pakistan shoppers, in clear English.
"""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 1200,
                             "responseMimeType": "application/json"}
    }
    request = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error {error.code}: {detail[:1000]}") from error

    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no creative brief.")
    raw = "\n".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if p.get("text")).strip()
    raw = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw, flags=re.I)
    try:
        brief = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Gemini did not return valid JSON: {raw[:800]}") from error

    keys = ("image_prompt", "video_title", "video_subtitle", "video_cta")
    for key in keys:
        if not isinstance(brief.get(key), str) or not brief[key].strip():
            raise RuntimeError(f"Creative brief is missing {key}.")

    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        raise RuntimeError("GitHub Actions output file is unavailable.")
    with open(output_path, "a", encoding="utf-8") as output:
        for key in keys:
            value = brief[key].strip()
            delimiter = "END_" + key.upper()
            while delimiter in value:
                delimiter += "_X"
            output.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")

    os.makedirs("creative_output", exist_ok=True)
    with open("creative_output/auto_generated_creative_brief.json", "w", encoding="utf-8") as file:
        json.dump({"product": product, **brief}, file, ensure_ascii=False, indent=2)
    print("AI automatically generated the image prompt, video headline, subtitle and CTA.")

if __name__ == "__main__":
    main()
