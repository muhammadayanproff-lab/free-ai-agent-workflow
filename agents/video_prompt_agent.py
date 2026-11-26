import base64,json,mimetypes,os,time,urllib.error,urllib.request
from pathlib import Path
from llm_fallback import groq_chat
from local_llm import qwen_chat

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
        print("Hosted vision providers unavailable; trying text-only local Qwen. It will not be told that it inspected the photos.")
        text_only_prompt = (
            "You cannot view or analyze images. Do not claim visual inspection. "
            "Write IMAGE ANALYSIS stating that automated visual analysis is unavailable, "
            "then ONE FINAL VIDEO PROMPT for a 10-15 second vertical ecommerce video. "
            "Treat original supplier photos as strict references for the external video editor; "
            "do not invent product details. Use only these listing facts:\\n"
            + json.dumps(details, ensure_ascii=False)
        )
        local_answer = qwen_chat(text_only_prompt, max_tokens=1800)
        if isinstance(local_answer, str) and "ONE FINAL VIDEO PROMPT" in local_answer.upper() and len(local_answer) > 250:
            answer = local_answer
    if "ONE FINAL VIDEO PROMPT" not in answer.upper() or len(answer)<250:
        print(
            "Gemini/Groq vision unavailable; using a conservative reference-faithful "
            "video prompt template. The editor must visually verify every product detail."
        )
        product_name = str(
            details.get("product_name")
            or details.get("name")
            or details.get("title")
            or "the supplied product"
        ).strip()
        product_name = " ".join(product_name.split())[:180] or "the supplied product"
        answer = f"""IMAGE ANALYSIS:
Automated image analysis was unavailable because both hosted AI providers could not be reached. Treat the original supplier photos as the only source of truth. Before publishing, a human must verify the product's exact visible shape, colors, proportions, parts, included items and any uncertain details. Do not infer materials, functions, specifications or benefits from the listing title alone.

ONE FINAL VIDEO PROMPT:
Create a 10–15 second vertical 9:16 photorealistic ecommerce product video for "{product_name}". Use the supplied original supplier photos as strict visual references and preserve the exact real product identity, silhouette, proportions, colors, components and visible details in every frame. Do not redesign, morph, duplicate, embellish or add any part that is not clearly present in the references.

Beat 1 (0–4 seconds): clean opening hero shot of the exact product, centered against a simple bright neutral background; gentle camera push-in.
Beat 2 (4–10 seconds): slow controlled camera orbit and close-up cuts showing only details that are clearly visible in the original photos. Do not simulate a function or use-case unless it is unambiguously demonstrated by the reference images.
Beat 3 (10–15 seconds): return to a stable full-product hero shot with soft natural studio lighting and subtle realistic shadows.

Use smooth restrained camera movement, realistic scale, consistent product geometry and professional commercial lighting. Keep the background uncluttered. No text, subtitles, prices, badges, watermark, invented logo, extra accessories, packaging, people, unsupported claims or additional products. The product must remain visually identical to the supplied reference photos throughout."""
    return answer

def main():
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
