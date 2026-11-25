import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from llm_fallback import groq_chat

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
    for attempt in (range(5) if API_KEY else range(0)):
        try:
            with urllib.request.urlopen(req,timeout=180) as res: data=json.loads(res.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")
            if exc.code not in (408,429,500,502,503,504) or attempt==4: raise RuntimeError(f"Gemini prompt generation HTTP {exc.code}: {detail[:800]}")
            time.sleep(5*(2**attempt))
    if data is not None:
        text="\n".join(p.get("text","") for p in data.get("candidates",[{}])[0].get("content",{}).get("parts",[]) if p.get("text"))
        try: prompts=json.loads(text).get("prompts",[])
        except Exception as exc: raise RuntimeError(f"Invalid image prompt JSON: {text[:700]}") from exc
    else:
        print("Gemini image-prompt generation unavailable; trying Groq JSON fallback.")
        fallback = groq_chat(prompt, max_tokens=2500, json_mode=True)
        prompts = fallback.get("prompts", []) if isinstance(fallback, dict) else []
    if len(prompts)!=3 or not all(isinstance(x,str) and len(x)>30 for x in prompts): raise RuntimeError("Gemini did not return exactly three usable image prompts.")
    return prompts

def generate(prompt, path):
    url=f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{IMAGE_MODEL}"
    payload={"prompt":prompt,"steps":4}
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+CF_TOKEN,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=180) as res: result=json.loads(res.read().decode())
    except urllib.error.HTTPError as exc: raise RuntimeError(f"Cloudflare image API HTTP {exc.code}: {exc.read().decode('utf-8','replace')[:800]}")
    image=result.get("result",{}).get("image")
    if not image: raise RuntimeError("Cloudflare returned no image.")
    path.write_bytes(base64.b64decode(image))

def main():
    if not API_KEY and not os.environ.get("GROQ_API_KEY","").strip(): raise RuntimeError("Neither GEMINI_API_KEY nor GROQ_API_KEY is configured.")
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
