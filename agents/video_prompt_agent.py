import base64,json,mimetypes,os,time,urllib.error,urllib.request
from pathlib import Path
from llm_fallback import groq_chat

API_KEY=os.environ.get("GEMINI_API_KEY","").strip()
MODEL=os.getenv("GEMINI_VISION_MODEL","gemini-3.8-flash")
IMAGES_DIR=Path(os.getenv("PRODUCT_IMAGES_DIR","source_product_images"))

def call_gemini(image_paths,details):
    parts=[{"text":f"""
You are Click & Collect Pakistan's ecommerce creative director.
Study the real Markaz supplier photos and the verified listing facts below. Identify only visually confirmed attributes; flag uncertain material/features. Do not invent details.

VERIFIED LISTING DATA:
{json.dumps(details,ensure_ascii=False)}

Return exactly:
1. IMAGE ANALYSIS: confirmed visible shape, proportions, colors, controls, included items, and anything uncertain.
2. ONE FINAL VIDEO PROMPT: one ready-to-copy prompt for a 10–15 second vertical 9:16 product promotion.

The single prompt must preserve the exact product identity, silhouette, proportions, colors, visible details and attachments from the source photos. Specify a simple 3-beat sequence, camera movement, lighting, realistic use-case only when supported, pacing and final hero shot. Do not morph, duplicate or redesign the product. No fake features, unsupported claims, text, subtitles, watermark or invented logos. Do not provide alternatives.
"""}]
    for path in image_paths:
        mime=mimetypes.guess_type(path.name)[0] or "image/jpeg"
        parts.append({"inlineData":{"mimeType":mime,"data":base64.b64encode(path.read_bytes()).decode("ascii")}})
    prompt_text = parts[0]["text"]
    endpoint=f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body={"contents":[{"role":"user","parts":parts}],"generationConfig":{"temperature":0.2,"maxOutputTokens":3500}}
    req=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","x-goog-api-key":API_KEY},method="POST")
    result = None
    gemini_error = ""
    for attempt in (range(5) if API_KEY else range(0)):
        try:
            with urllib.request.urlopen(req,timeout=90) as res:
                result=json.loads(res.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")
            gemini_error=f"Gemini vision HTTP {exc.code}: {detail[:500]}"
            if exc.code not in (408,429,500,502,503,504):
                print(gemini_error)
                break
            if attempt < 4:
                delay=min(30,5*(2**attempt))
                print(f"{gemini_error}; retrying in {delay}s.")
                time.sleep(delay)
        except (TimeoutError, OSError) as exc:
            gemini_error=f"Gemini vision network/timeout: {exc}"
            if attempt < 4:
                time.sleep(min(30,5*(2**attempt)))
    if result is None:
        print(f"{gemini_error or 'Gemini is not configured.'} Trying Groq vision fallback.")
    if result is not None:
        parts=result.get("candidates",[{}])[0].get("content",{}).get("parts",[])
        answer="\n".join(x.get("text","") for x in parts if x.get("text")).strip()
    else:
        answer = groq_chat(prompt_text, max_tokens=3500, image_paths=image_paths) or ""
    if "ONE FINAL VIDEO PROMPT" not in answer.upper() or len(answer)<250:
        print("Gemini response did not meet the required format; retrying with Groq vision.")
        answer = groq_chat(parts[0]["text"], max_tokens=3500, image_paths=image_paths) or ""
    if "ONE FINAL VIDEO PROMPT" not in answer.upper() or len(answer)<250:
        raise RuntimeError("Gemini and Groq did not return the required single video prompt. Groq vision requires an active image-capable model and valid API key.")
    return answer

def main():
    if not API_KEY and not os.environ.get("GROQ_API_KEY","").strip(): raise RuntimeError("Neither GEMINI_API_KEY nor GROQ_API_KEY is configured.")
    product_file=Path("product_data/product.json")
    if not product_file.exists(): raise RuntimeError("Run product preparation first; product_data/product.json is missing.")
    details=json.loads(product_file.read_text(encoding="utf-8"))
    if not IMAGES_DIR.is_dir(): raise RuntimeError(f"Product image folder not found: {IMAGES_DIR}")
    images=sorted(p for p in IMAGES_DIR.iterdir() if p.suffix.lower() in {".jpg",".jpeg",".png",".webp"})[:5]
    if not images: raise RuntimeError("No original product images found.")
    report=call_gemini(images,details)
    out=Path("video_prompt_output"); out.mkdir(exist_ok=True)
    (out/"image_analysis_and_video_prompt.md").write_text("# Product Image Analysis & Single Video Prompt\n\n"+report+"\n",encoding="utf-8")
    (out/"video_prompt.txt").write_text(report.split("ONE FINAL VIDEO PROMPT",1)[-1].strip()+"\n",encoding="utf-8")
    print("One 10–15 second video prompt generated. No video rendering was run.")
if __name__=="__main__": main()
