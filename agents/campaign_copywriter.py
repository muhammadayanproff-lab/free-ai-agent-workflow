import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from llm_fallback import groq_chat

API_KEY=os.environ.get("GEMINI_API_KEY","").strip()
MODEL=os.getenv("GEMINI_TEXT_MODEL","gemini-3.8-flash")

def main():
    product=json.loads(Path("product_data/product.json").read_text(encoding="utf-8"))
    market=Path("market_analysis/market_analysis.md").read_text(encoding="utf-8")
    visual=Path("video_prompt_output/image_analysis_and_video_prompt.md").read_text(encoding="utf-8")
    prompt=f"""
You are the senior Pakistan ecommerce SEO and social copywriter for Click & Collect.
Create four separate, platform-native captions:
- Instagram image post
- Facebook image post
- Instagram video/Reel post
- Facebook video post

Also create concise SEO title, meta description, primary keyword, 8-12 secondary keywords, product alt text, and 8-12 relevant hashtags for each caption where suitable.
Write in natural Pakistani English with optional simple Roman Urdu phrases only where useful.
Use only product facts from the supplied Markaz listing. Do not invent product performance, material, warranty, stock, delivery dates, discount, review or Cash on Delivery (COD) claims. COD and checkout availability are not verified from the public listing, so never promise COD, delivery terms or payment methods.
Don't include an exact selling price unless the supplied verified data explicitly includes the final Click & Collect price. The Markaz supplier price is not automatically the store's customer price.
Keep each platform caption distinct. Image caption and video caption must not be duplicates. Include an appropriate CTA without inventing a product page URL.
Return STRICT JSON with keys:
seo_title, meta_description, primary_keyword, secondary_keywords, alt_text,
instagram_image_caption, facebook_image_caption, instagram_video_caption, facebook_video_caption,
image_hashtags, video_hashtags, factuality_notes.
Product: {json.dumps({k:v for k,v in product.items() if k not in ("local_image_files","image_urls")},ensure_ascii=False)}
Market analysis: {market[:8000]}
Visual analysis/video prompt: {visual[:5000]}
"""
    endpoint=f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.35,"responseMimeType":"application/json","maxOutputTokens":5000}}
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
            gemini_error=f"Gemini copywriter HTTP {exc.code}: {detail[:500]}"
            if exc.code not in (408,429,500,502,503,504):
                print(gemini_error)
                break
            if attempt < 4:
                delay=min(30,5*(2**attempt))
                print(f"{gemini_error}; retrying in {delay}s.")
                time.sleep(delay)
        except (TimeoutError, OSError) as exc:
            gemini_error=f"Gemini copywriter network/timeout: {exc}"
            if attempt < 4:
                time.sleep(min(30,5*(2**attempt)))
    if data is None:
        print(f"{gemini_error or 'Gemini is not configured.'} Trying Groq fallback.")
    result = None
    if data is not None:
        text="\n".join(p.get("text","") for p in data.get("candidates",[{}])[0].get("content",{}).get("parts",[]) if p.get("text"))
        try:
            result=json.loads(text)
        except Exception as exc:
            print(f"Gemini returned invalid copy JSON ({exc}); trying Groq.")
    if not isinstance(result, dict):
        result = groq_chat(prompt, max_tokens=5000, json_mode=True)
    if not isinstance(result, dict):
        raise RuntimeError("Gemini and Groq copywriting providers failed. Check GROQ_API_KEY access and provider quotas.")
    required=["instagram_image_caption","facebook_image_caption","instagram_video_caption","facebook_video_caption","seo_title","meta_description"]
    missing=[k for k in required if not str(result.get(k,"")).strip()]
    if missing: raise RuntimeError("Copywriter omitted required fields: "+", ".join(missing))
    out=Path("campaign_copy"); out.mkdir(exist_ok=True)
    (out/"campaign_copy.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# SEO & Campaign Captions","",f"## SEO title\n{result['seo_title']}","",f"## Meta description\n{result['meta_description']}","",f"## Primary keyword\n{result.get('primary_keyword','')}","",f"## Secondary keywords\n{', '.join(result.get('secondary_keywords',[]))}"]
    for key,label in [("instagram_image_caption","Instagram — Image"),("facebook_image_caption","Facebook — Image"),("instagram_video_caption","Instagram — Video/Reel"),("facebook_video_caption","Facebook — Video")]:
        lines += ["",f"## {label}",result[key]]
    lines += ["","## Image hashtags"," ".join(result.get("image_hashtags",[])),"","## Video hashtags"," ".join(result.get("video_hashtags",[])),"","## Factuality notes",str(result.get("factuality_notes",[]))]
    (out/"campaign_copy.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("SEO and four separate platform/media captions generated.")

if __name__=="__main__": main()
