import hashlib
import json
import os
import time
import urllib.request
import urllib.error
import uuid
from pathlib import Path

def upload(path, cloud, key, secret):
    timestamp = str(int(time.time()))
    folder = "click-and-collect/campaign-assets"
    params = {"folder": folder, "timestamp": timestamp}
    signature = hashlib.sha1(("&".join(f"{k}={params[k]}" for k in sorted(params)) + secret).encode()).hexdigest()
    boundary = "----ClickCollect" + uuid.uuid4().hex
    fields = {"api_key": key, "timestamp": timestamp, "folder": folder, "signature": signature}
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode())
    body.extend(path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"https://api.cloudinary.com/v1_1/{cloud}/image/upload",
        data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    result = None
    last_error = ""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            last_error = f"Cloudinary HTTP {exc.code}: {detail[:600]}"
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(last_error) from exc
            time.sleep(8 * (attempt + 1))
        except (TimeoutError, OSError) as exc:
            last_error = f"Cloudinary network/timeout: {exc}"
            if attempt == 3:
                raise RuntimeError(last_error) from exc
            time.sleep(8 * (attempt + 1))
    if result is None:
        raise RuntimeError(last_error or "Cloudinary returned no response.")
    url = result.get("secure_url")
    if not url or not url.startswith("https://"):
        raise RuntimeError("Cloudinary did not return a public HTTPS image URL.")
    return url

def main():
    cloud = os.environ.get("CLOUDINARY_CLOUD_NAME", "").strip()
    key = os.environ.get("CLOUDINARY_API_KEY", "").strip()
    secret = os.environ.get("CLOUDINARY_API_SECRET", "").strip()
    if not all((cloud, key, secret)):
        raise RuntimeError("Cloudinary secrets are missing.")
    generated = sorted(Path("generated_images").glob("concept_*"))
    originals = sorted(p for p in Path("source_product_images").glob("*")
                       if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    if len(generated) != 3:
        raise RuntimeError("Expected exactly three generated AI concept images.")
    if not originals:
        raise RuntimeError("No original Markaz product photo is available.")
    result = []
    for index, path in enumerate(generated, 1):
        result.append({"choice": f"concept_{index}", "type": "AI concept",
                       "file": str(path), "url": upload(path, cloud, key, secret)})
    path = originals[0]
    result.append({"choice": "original_1", "type": "Original Markaz product photo",
                   "file": str(path), "url": upload(path, cloud, key, secret)})
    Path("campaign_media_urls.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Uploaded three AI concepts and one original product photo to Cloudinary.")

if __name__ == "__main__":
    main()
