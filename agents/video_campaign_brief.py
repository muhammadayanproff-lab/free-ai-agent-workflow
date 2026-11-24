import json, os, re, urllib.error, urllib.request
MODEL = "gemini-3.5-flash-lite"

def main():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    product = os.environ.get("PRODUCT_NAME", "").strip()
    notes = os.environ.get("PRODUCT_NOTES", "").strip()
    if not api_key: raise RuntimeError("GEMINI_API_KEY secret is missing.")
    if not product: raise RuntimeError("PRODUCT_NAME is required.")
    prompt = f"""
You are the creative director for Click and Collect, a Pakistan-focused online store.
Create a factual brief for a 15-second 9:16 portrait product-photo motion showcase.
Product name: {product}
Verified details: {notes or "None supplied"}
Return ONLY JSON with string keys image_prompt, video_title, video_subtitle, video_cta.
image_prompt: photorealistic premium studio product photo, one clearly visible centered product, vertical 9:16, uncluttered background. Absolutely no text, letters, numbers, logos, watermarks, websites, fake packaging, extra products or invented product details.
video_title: short, max 55 characters.
video_subtitle: only facts in name/notes; if none, "A simple choice for everyday use".
video_cta: max 25 characters, e.g. "Shop now".
Never invent specifications, materials, performance, discounts, prices, warranties or health claims.
"""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    payload = {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.3,"maxOutputTokens":1200,"responseMimeType":"application/json"}}
    request = urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
    try:
        with urllib.request.urlopen(request,timeout=120) as response: result=json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Gemini API error {error.code}: {error.read().decode('utf-8',errors='replace')[:1000]}")
    candidates=result.get("candidates",[])
    if not candidates: raise RuntimeError("Gemini returned no creative brief.")
    raw="\n".join(p.get("text","") for p in candidates[0].get("content",{}).get("parts",[]) if p.get("text")).strip()
    raw=re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$","",raw,flags=re.I)
    try: brief=json.loads(raw)
    except json.JSONDecodeError as error: raise RuntimeError(f"Gemini did not return valid JSON: {raw[:800]}") from error
    keys=("image_prompt","video_title","video_subtitle","video_cta")
    for key in keys:
        if not isinstance(brief.get(key),str) or not brief[key].strip(): raise RuntimeError(f"Creative brief is missing {key}.")
    output_path=os.environ.get("GITHUB_OUTPUT")
    if not output_path: raise RuntimeError("GitHub Actions output file is unavailable.")
    with open(output_path,"a",encoding="utf-8") as output:
        for key in keys:
            value=brief[key].strip(); delimiter="END_"+key.upper()
            while delimiter in value: delimiter+="_X"
            output.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")
    os.makedirs("creative_output",exist_ok=True)
    with open("creative_output/auto_generated_creative_brief.json","w",encoding="utf-8") as file:
        json.dump({"product":product,**brief},file,ensure_ascii=False,indent=2)
    print("Generated factual brief for a 15-second vertical product showcase.")

if __name__=="__main__": main()
