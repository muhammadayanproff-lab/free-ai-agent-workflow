import os
import json
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone

ACCOUNT_ID = os.environ["CLOUDFLARE_ACCOUNT_ID"]
API_TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]
MODEL = "@cf/black-forest-labs/flux-1-schnell"

PROMPT = os.environ.get("IMAGE_PROMPT", "").strip() or (
    "Create a clean premium commercial studio photograph of the exact product described. "
    "Show one product only, centered, fully visible, on a simple uncluttered background. "
    "Vertical 9:16 portrait composition. Photorealistic lighting and realistic materials. "
    "Do not include any text, letters, numbers, labels, logos, watermarks, websites, "
    "brand marks, packaging text, extra products, props covering the product, or invented controls."
)

def generate_image():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{MODEL}"
    payload = {"prompt": PROMPT, "steps": 4}
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + API_TOKEN, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Cloudflare API error {error.code}: {details[:1000]}")
    image_data = result.get("result", {}).get("image")
    if not image_data:
        raise RuntimeError("No image returned by Cloudflare: " + str(result)[:1000])
    image_bytes = base64.b64decode(image_data)
    os.makedirs("generated_images", exist_ok=True)
    filename = "generated_images/image_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + ".jpg"
    with open(filename, "wb") as image_file:
        image_file.write(image_bytes)
    print("IMAGE GENERATED SUCCESSFULLY")
    print("Saved:", filename)
    print("Reminder: AI-generated images may alter product design; use a verified original product photo for exact product fidelity.")

if __name__ == "__main__":
    generate_image()
