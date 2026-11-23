import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import uuid

def upload_file(path):
    cloud = os.environ["CLOUDINARY_CLOUD_NAME"].strip()
    key = os.environ["CLOUDINARY_API_KEY"].strip()
    secret = os.environ["CLOUDINARY_API_SECRET"].strip()
    if not all((cloud, key, secret)):
        raise RuntimeError("Missing Cloudinary credentials.")

    timestamp = str(int(time.time()))
    folder = "click-and-collect"
    params = {"folder": folder, "timestamp": timestamp}
    to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params))
    signature = hashlib.sha1((to_sign + secret).encode("utf-8")).hexdigest()

    boundary = "----ChatGPTUpload" + uuid.uuid4().hex
    fields = {
        "api_key": key,
        "timestamp": timestamp,
        "folder": folder,
        "signature": signature,
    }
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(str(value).encode())
        body.extend(b"\r\n")

    filename = os.path.basename(path)
    with open(path, "rb") as f:
        content = f.read()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(content)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    url = f"https://api.cloudinary.com/v1_1/{cloud}/image/upload"
    req = urllib.request.Request(url, data=bytes(body), headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        if hasattr(exc, "read"):
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Cloudinary upload failed: {detail[:1000]}") from exc
        raise
    secure_url = result.get("secure_url")
    if not secure_url or not secure_url.startswith("https://"):
        raise RuntimeError("Cloudinary did not return a public HTTPS URL.")
    os.makedirs("media_output", exist_ok=True)
    with open("media_output/image_url.txt", "w", encoding="utf-8") as out:
        out.write(secure_url + "\n")
    print("CLOUDINARY_UPLOAD_SUCCESS")
    print("Public image URL saved to media_output/image_url.txt")

if __name__ == "__main__":
    import glob
    files = sorted(glob.glob("generated_images/*"))
    if not files:
        raise RuntimeError("No generated image found.")
    upload_file(files[-1])
