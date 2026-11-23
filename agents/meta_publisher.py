import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

API_VERSION = os.getenv("META_GRAPH_API_VERSION", "").strip() or "v27.0"

def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing GitHub secret/input: {name}")
    return value

def post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/x-www-form-urlencoded"}, method="POST")
    return request_json(req)

def get_json(url):
    return request_json(urllib.request.Request(url, method="GET"))

def request_json(req):
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            payload = response.read().decode("utf-8")
            data = json.loads(payload)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Meta API HTTP {e.code}: {detail[:1200]}") from e
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError("Meta API error: " + json.dumps(data["error"])[:1200])
    return data

def publish_instagram(ig_id, token, media_type, media_url, caption):
    if not media_url.startswith("https://"):
        raise RuntimeError("Instagram requires a publicly accessible HTTPS media URL.")
    base = f"https://graph.facebook.com/{API_VERSION}"
    params = {"access_token": token, "caption": caption}
    if media_type == "image":
        params["image_url"] = media_url
    elif media_type == "video":
        params["media_type"] = "REELS"
        params["video_url"] = media_url
        params["share_to_feed"] = "true"
    else:
        raise RuntimeError("Instagram supports image or video in this release.")
    container = post_form(f"{base}/{ig_id}/media", params)
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError("Meta did not return an Instagram media container ID.")
    # Meta processes video asynchronously; poll until publishable.
    for _ in range(30):
        status_url = f"{base}/{creation_id}?fields=status_code&access_token={urllib.parse.quote(token)}"
        status = get_json(status_url).get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("Instagram media processing failed.")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram media was not ready within five minutes.")
    result = post_form(f"{base}/{ig_id}/media_publish", {
        "creation_id": creation_id, "access_token": token
    })
    if not result.get("id"):
        raise RuntimeError("Instagram publish response did not include a media ID.")
    return result["id"]

def publish_facebook(page_id, token, caption, product_url, media_type, media_url):
    base = f"https://graph.facebook.com/{API_VERSION}/{page_id}"
    if media_type == "image" and media_url:
        if not media_url.startswith("https://"):
            raise RuntimeError("Facebook image requires a publicly accessible HTTPS media URL.")
        data = {"caption": caption, "url": media_url, "access_token": token}
        result = post_form(f"{base}/photos", data)
    elif media_type == "video" and media_url:
        if not media_url.startswith("https://"):
            raise RuntimeError("Facebook video requires a publicly accessible HTTPS media URL.")
        data = {"description": caption, "file_url": media_url, "access_token": token}
        result = post_form(f"{base}/videos", data)
    else:
        data = {"message": caption, "access_token": token}
        if product_url:
            data["link"] = product_url
        result = post_form(f"{base}/feed", data)
    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise RuntimeError("Facebook publish response did not include a post ID.")
    return post_id

def main():
    approval = os.getenv("PUBLISH_APPROVAL", "").strip()
    if approval != "APPROVE":
        raise RuntimeError("Blocked: PUBLISH_APPROVAL must be exactly APPROVE. Nothing was published.")
    caption = required("POST_CAPTION")
    platforms = {p.strip().lower() for p in required("TARGET_PLATFORMS").split(",") if p.strip()}
    if not platforms or not platforms.issubset({"instagram", "facebook"}):
        raise RuntimeError("TARGET_PLATFORMS must contain Instagram and/or Facebook only.")
    media_type = os.getenv("MEDIA_TYPE", "image").strip().lower()
    media_url = os.getenv("MEDIA_URL", "").strip()
    product_url = os.getenv("PRODUCT_URL", "").strip()
    if product_url and not product_url.startswith("https://"):
        raise RuntimeError("PRODUCT_URL must be HTTPS.")
    outcomes = {}
    if "instagram" in platforms:
        outcomes["instagram_media_id"] = publish_instagram(
            required("META_IG_USER_ID"), required("META_PAGE_ACCESS_TOKEN"),
            media_type, media_url, caption
        )
    if "facebook" in platforms:
        outcomes["facebook_post_id"] = publish_facebook(
            required("META_PAGE_ID"), required("META_PAGE_ACCESS_TOKEN"),
            caption, product_url, media_type, media_url
        )
    os.makedirs("publish_output", exist_ok=True)
    with open("publish_output/publish_receipt.json", "w", encoding="utf-8") as f:
        json.dump({"status":"PUBLISHED","platform_results":outcomes}, f, indent=2)
    print("PUBLISH COMPLETE")
    print(json.dumps(outcomes, indent=2))

if __name__ == "__main__":
    main()
