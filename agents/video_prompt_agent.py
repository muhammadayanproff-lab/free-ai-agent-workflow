import base64,json,mimetypes,os,time,urllib.error,urllib.request
from pathlib import Path

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
    endpoint=f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body={"contents":[{"role":"user","parts":parts}],"generationConfig":{"temperature":0.2,"maxOutputTokens":3500}}
    req=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={"Content-Type":"application/json","x-goog-api-key":API_KEY},method="POST")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req,timeout=180) as res: result=json.loads(res.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")
            if exc.code not in (408,429,500,502,503,504) or attempt==4: raise RuntimeError(f"Gemini visual analysis HTTP {exc.code}: {detail[:900]}")
            time.sleep(5*(2**attempt))
    parts=result.get("candidates",[{}])[0].get("content",{}).get("parts",[])
    answer="\n".join(x.get("text","") for x in parts if x.get("text")).strip()
    if "ONE FINAL VIDEO PROMPT" not in answer.upper() or len(answer)<250: raise RuntimeError("Gemini did not return the required single video prompt.")
    return answer

def main():
    if not API_KEY: raise RuntimeError("GEMINI_API_KEY is missing.")
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
