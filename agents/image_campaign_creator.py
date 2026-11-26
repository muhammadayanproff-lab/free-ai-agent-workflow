import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from llm_fallback import groq_chat
from local_llm import qwen_chat

API_KEY=os.environ.get("GEMINI_API_KEY","").strip()
CF_ACCOUNT=os.environ.get("CLOUDFLARE_ACCOUNT_ID","").strip()
CF_TOKEN=os.environ.get("CLOUDFLARE_API_TOKEN","").strip()
TEXT_MODEL=os.getenv("GEMINI_TEXT_MODEL","gemini-3.8-flash")
IMAGE_MODEL="@cf/black-forest-labs/flux-1-schnell"

def gemini_prompts(product, analysis):
    endpoint=f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent"
    prompt=f"""
Create exactly THREE distinct commercial image-generation prompts for a Pakistan ecommerce product campaign.
Use the product's real supplied facts only. Make the scenes useful for the identified Pakistani audience.
Each prompt should have a distinct angle: (1) clean premium hero, (2) problem-solution lifestyle scene, (3) close-up/detail or use-case scene.
Do not invent features, materials, accessories, packaging, brand logos, claims or specifications.
No readable text, price labels, fake badges, watermark or extra products.
AI images are concept creatives and may not exactly reproduce the supplier product; the original Markaz images must remain available for truth checking.
Return STRICT JSON: {{"prompts":["...","...","..."]}}.
Product facts: {json.dumps({k:v for k,v in product.items() if k not in ("local_image_files","image_urls")},ensure_ascii=False)}
Market analysis: {analysis[:7000]}
"""
    body={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.55,"responseMimeType":"application/json","maxOutputTokens":2500}}
    req=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","x-goog-api-key":API_KEY},method="POST")
    data = None
    gemini_error = ""
    for attempt in (range(5) if API_KEY else range(0)):
        try:
            with urllib.request.urlopen(req,timeout=90) as res:
                data=json.loads(res.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")
            gemini_error=f"Gemini HTTP {exc.code}: {detail[:500]}"
            if exc.code not in (408,429,500,502,503,504):
                print(gemini_error)
                break
            if attempt < 4:
                delay=min(30,5*(2**attempt))
                print(f"{gemini_error}; retrying in {delay}s.")
                time.sleep(delay)
        except (TimeoutError, OSError) as exc:
            gemini_error=f"Gemini network/timeout: {exc}"
            if attempt < 4:
                time.sleep(min(30,5*(2**attempt)))
    if data is None:
        print(f"{gemini_error or 'Gemini is not configured.'} Trying Groq fallback.")
    prompts = []
    if data is not None:
        text="\n".join(p.get("text","") for p in data.get("candidates",[{}])[0].get("content",{}).get("parts",[]) if p.get("text"))
        try:
            prompts=json.loads(text).get("prompts",[])
        except Exception as exc:
            print(f"Gemini returned invalid image-prompt JSON ({exc}); trying Groq.")
    if len(prompts) != 3:
        fallback = groq_chat(prompt, max_tokens=2500, json_mode=True)
        prompts = fallback.get("prompts", []) if isinstance(fallback, dict) else []
    if len(prompts) != 3:
        print("Hosted prompt providers unavailable; trying local Qwen.")
        fallback = qwen_chat(prompt, max_tokens=1800, json_mode=True)
        prompts = fallback.get("prompts", []) if isinstance(fallback, dict) else []
    if len(prompts) != 3 or not all(isinstance(x, str) and len(x) > 30 for x in prompts):
        # Last-resort local prompt templates keep the campaign moving when both
        # hosted text providers are unavailable. They use only the product name
        # and explicitly instruct the image model not to invent product details.
        product_name = str(
            product.get("product_name")
            or product.get("name")
            or product.get("title")
            or "the supplied product"
        ).strip()
        product_name = " ".join(product_name.split())[:180] or "the supplied product"
        print(
            "Gemini/Groq prompt generation unavailable; using three conservative "
            "local creative templates. No product features will be added."
        )
        subject = f'the exact product shown in the supplied reference: "{product_name}"'
        prompts = [
            (
                f"Create a premium, photorealistic ecommerce hero photograph featuring only {subject}. "
                "Preserve the reference product's exact shape, colors, proportions, parts, and appearance. "
                "Place it centered on a clean softly lit neutral studio surface with tasteful shadows and "
                "a simple uncluttered background. Do not add accessories, packaging, logos, labels, text, "
                "badges, extra products, or any feature not visible in the reference."
            ),
            (
                f"Create a natural Pakistani home lifestyle ecommerce photograph featuring {subject} "
                "in a believable everyday setting. Keep the product itself identical to the reference "
                "image; show a clear, realistic context without implying unverified performance or benefits. "
                "Use warm natural daylight, a tidy environment, and restrained composition. Do not add "
                "accessories, packaging, logos, labels, text, badges, extra products, or invented details."
            ),
            (
                f"Create a close-up commercial product photograph of {subject}, using the supplied image "
                "as the strict visual reference. Emphasize only details that are actually visible on the "
                "real product, with crisp focus, realistic materials, soft directional lighting, and a "
                "simple background. Do not invent components, materials, features, accessories, logos, "
                "packaging, readable text, badges, or extra products."
            ),
        ]
    return prompts

def generate(prompt, path):
    url=f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{IMAGE_MODEL}"
    payload={"prompt":prompt,"steps":4}
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+CF_TOKEN,"Content-Type":"application/json"},method="POST")
    result = None
    last_error = ""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req,timeout=180) as res:
                result=json.loads(res.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")
            last_error=f"Cloudflare image API HTTP {exc.code}: {detail[:700]}"
            if exc.code not in (408,429,500,502,503,504) or attempt == 3:
                raise RuntimeError(last_error) from exc
            delay=10*(attempt+1)
            print(f"{last_error}; retrying in {delay}s.")
            time.sleep(delay)
        except (TimeoutError, OSError) as exc:
            last_error=f"Cloudflare image API network/timeout: {exc}"
            if attempt == 3:
                raise RuntimeError(last_error) from exc
            time.sleep(10*(attempt+1))
    if result is None:
        raise RuntimeError(last_error or "Cloudflare image generation returned no response.")
    image=result.get("result",{}).get("image")
    if not image: raise RuntimeError("Cloudflare returned no image.")
    path.write_bytes(base64.b64decode(image))

def main():
    if not CF_ACCOUNT or not CF_TOKEN: raise RuntimeError("CLOUDFLARE_ACCOUNT_ID/API_TOKEN secret is missing.")
    product=json.loads(Path("product_data/product.json").read_text(encoding="utf-8"))
    analysis=Path("market_analysis/market_analysis.md").read_text(encoding="utf-8")
    prompts=gemini_prompts(product,analysis)
    out=Path("generated_images"); out.mkdir(exist_ok=True)
    (out/"image_prompts.json").write_text(json.dumps(prompts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for index,prompt in enumerate(prompts,1):
        path=out/f"concept_{index:02d}.jpg"
        generate(prompt,path)
        print("Generated",path)
    print("Three AI concept creatives generated. Original Markaz images remain separately preserved.")

if __name__=="__main__": main()
