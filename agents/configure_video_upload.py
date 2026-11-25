import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

PRESET_NAME = "click_collect_manual_video"
ALLOWED_FORMATS = "mp4,mov,webm"

def request(method, url, key, secret, data=None):
    credentials = base64.b64encode(f"{key}:{secret}".encode()).decode()
    headers = {"Authorization": f"Basic {credentials}"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        if exc.code == 404:
            return None
        raise RuntimeError(f"Cloudinary Admin API HTTP {exc.code}: {body[:900]}") from exc

def main():
    cloud = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    if not all((cloud, key, secret)):
        raise RuntimeError("CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET secrets are required.")

    base = f"https://api.cloudinary.com/v1_1/{urllib.parse.quote(cloud, safe='')}/upload_presets"
    current = request("GET", f"{base}/{PRESET_NAME}", key, secret)
    fields = {
        "name": PRESET_NAME,
        "unsigned": "true",
        "folder": "click-and-collect/manual-videos",
        "allowed_formats": ALLOWED_FORMATS,
        "disallow_public_id": "true",
    }
    body = urllib.parse.urlencode(fields).encode()
    if current:
        result = request("PUT", f"{base}/{PRESET_NAME}", key, secret, body)
        action = "updated"
    else:
        result = request("POST", base, key, secret, body)
        action = "created"

    verified = request("GET", f"{base}/{PRESET_NAME}", key, secret)
    if not verified or verified.get("unsigned") is not True:
        raise RuntimeError("Cloudinary preset was not verified as unsigned.")
    settings = verified.get("settings", {})
    allowed = settings.get("allowed_formats", "")
    # Cloudinary may return allowed_formats as either a list or a comma-separated string.
    if isinstance(allowed, str):
        actual_formats = {item.strip().lower() for item in allowed.split(",") if item.strip()}
    elif isinstance(allowed, (list, tuple, set)):
        actual_formats = {str(item).strip().lower() for item in allowed if str(item).strip()}
    else:
        actual_formats = set()
    expected_formats = {item.strip().lower() for item in ALLOWED_FORMATS.split(",")}
    if not expected_formats.issubset(actual_formats):
        raise RuntimeError(
            f"Preset allowed_formats verification failed: expected {sorted(expected_formats)}, "
            f"received {allowed!r}"
        )
    print(f"Cloudinary video upload preset {PRESET_NAME} {action} and verified.")
    print("Allowed formats: mp4, mov, webm. Folder: click-and-collect/manual-videos.")
    print("Note: Cloudinary upload presets do not enforce a per-preset file-size cap; the upload page checks 100 MB client-side.")

if __name__ == "__main__":
    main()
