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

def request_json(req):
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Meta API HTTP {error.code}: {detail[:1200]}") from error
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError("Meta API error: " + json.dumps(data["error"])[:1200])
    return data

def post_form(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    return request_json(req)

def get_json(url):
    return request_json(urllib.request.Request(url, method="GET"))

def publish_instagram(ig_id, token, media_type, media_url, caption):
    if not media_url.startswith("https://"):
        raise RuntimeError("Instagram requires a public HTTPS media URL.")
    base = f"https://graph.facebook.com/{API_VERSION}"
    params = {"access_token": token, "caption": caption}
    if media_type == "image":
        params["image_url"] = media_url
    else:
        params.update({"media_type": "REELS", "video_url": media_url, "share_to_feed": "true"})
    container = post_form(f"{base}/{ig_id}/media", params)
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(f"Meta did not return an Instagram {media_type} container ID.")
    for _ in range(36):
        status_url = f"{base}/{creation_id}?fields=status_code&access_token={urllib.parse.quote(token)}"
        status = get_json(status_url).get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram {media_type} processing failed.")
        time.sleep(10)
    else:
        raise RuntimeError(f"Instagram {media_type} was not ready within six minutes.")
    result = post_form(f"{base}/{ig_id}/media_publish", {"creation_id": creation_id, "access_token": token})
    post_id = result.get("id")
    if not post_id:
        raise RuntimeError(f"Instagram {media_type} publish response did not include a media ID.")
    return post_id

def publish_facebook(page_id, token, media_type, media_url, caption):
    if not media_url.startswith("https://"):
        raise RuntimeError("Facebook requires a public HTTPS media URL.")
    base = f"https://graph.facebook.com/{API_VERSION}/{page_id}"
    if media_type == "image":
        result = post_form(f"{base}/photos", {"caption": caption, "url": media_url, "access_token": token})
    else:
        result = post_form(f"{base}/videos", {"description": caption, "file_url": media_url, "access_token": token})
    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook {media_type} publish response did not include a post ID.")
    return post_id

def main():
    if required("PUBLISH_APPROVAL") != "APPROVE":
        raise RuntimeError("Blocked: PUBLISH_APPROVAL must be exactly APPROVE. Nothing was published.")
    platforms = {x.strip().lower() for x in required("TARGET_PLATFORMS").split(",") if x.strip()}
    if not platforms or not platforms.issubset({"instagram", "facebook"}):
        raise RuntimeError("TARGET_PLATFORMS must contain Instagram and/or Facebook only.")
    image_url = required("IMAGE_URL")
    video_url = required("VIDEO_URL")
    image_caption = required("IMAGE_CAPTION")
    video_caption = required("VIDEO_CAPTION")
    for label, url in (("IMAGE_URL", image_url), ("VIDEO_URL", video_url)):
        if not url.startswith("https://"):
            raise RuntimeError(f"{label} must be a public HTTPS URL.")
    token = required("META_PAGE_ACCESS_TOKEN")
    outcomes = {}
    for platform in sorted(platforms):
        if platform == "instagram":
            ig_id = required("META_IG_USER_ID")
            outcomes["instagram_image_post_id"] = publish_instagram(ig_id, token, "image", image_url, image_caption)
            outcomes["instagram_video_reel_id"] = publish_instagram(ig_id, token, "video", video_url, video_caption)
        else:
            page_id = required("META_PAGE_ID")
            outcomes["facebook_image_post_id"] = publish_facebook(page_id, token, "image", image_url, image_caption)
            outcomes["facebook_video_post_id"] = publish_facebook(page_id, token, "video", video_url, video_caption)
    os.makedirs("publish_output", exist_ok=True)
    with open("publish_output/publish_receipt.json", "w", encoding="utf-8") as output:
        json.dump({"status": "PUBLISHED", "platform_results": outcomes,
                   "posts": ["image", "video"], "captions_are_separate": True}, output, indent=2)
    print("Both image and video posts were submitted with separate captions.")
    print(json.dumps(outcomes, indent=2))

if __name__ == "__main__":
    main()
