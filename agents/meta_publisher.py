import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

API_VERSION = os.getenv("META_GRAPH_API_VERSION", "").strip() or "v27.0"

def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing GitHub secret/input: {name}")
    return value

def request_json(request):
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Meta API HTTP {error.code}: {error.read().decode('utf-8','replace')[:1200]}") from error
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError("Meta API error: " + json.dumps(data["error"])[:1200])
    return data

def post_form(url, data):
    request = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    return request_json(request)

def get_json(url):
    return request_json(urllib.request.Request(url, method="GET"))

def publish_instagram(ig_id, token, kind, media_url, caption):
    if not media_url.startswith("https://"):
        raise RuntimeError("Instagram media must be public HTTPS.")
    base = f"https://graph.facebook.com/{API_VERSION}"
    params = {"access_token": token, "caption": caption}
    if kind == "image":
        params["image_url"] = media_url
    else:
        params.update({"media_type": "REELS", "video_url": media_url, "share_to_feed": "true"})
    container = post_form(f"{base}/{ig_id}/media", params)
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(f"Instagram {kind} container ID missing.")
    for _ in range(36):
        status = get_json(
            f"{base}/{creation_id}?fields=status_code&access_token={urllib.parse.quote(token)}"
        ).get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram {kind} processing failed.")
        time.sleep(10)
    else:
        raise RuntimeError(f"Instagram {kind} processing timed out.")
    result = post_form(f"{base}/{ig_id}/media_publish",
        {"creation_id": creation_id, "access_token": token})
    if not result.get("id"):
        raise RuntimeError(f"Instagram {kind} publish returned no media ID.")
    return result["id"]

def publish_facebook(page_id, token, kind, media_url, caption):
    if not media_url.startswith("https://"):
        raise RuntimeError("Facebook media must be public HTTPS.")
    base = f"https://graph.facebook.com/{API_VERSION}/{page_id}"
    if kind == "image":
        result = post_form(f"{base}/photos",
            {"caption": caption, "url": media_url, "access_token": token})
    else:
        result = post_form(f"{base}/videos",
            {"description": caption, "file_url": media_url, "access_token": token})
    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook {kind} publish returned no post ID.")
    return post_id

def main():
    if required("PUBLISH_APPROVAL") != "APPROVE":
        raise RuntimeError("Blocked: explicit APPROVE is required.")
    platforms = {x.strip().lower() for x in required("TARGET_PLATFORMS").split(",") if x.strip()}
    if not platforms or not platforms.issubset({"instagram", "facebook"}):
        raise RuntimeError("Choose Instagram and/or Facebook only.")
    review_dir = Path(os.getenv("CAMPAIGN_REVIEW_DIR", "campaign_review"))
    copy_path = review_dir / "campaign_copy" / "campaign_copy.json"
    media_path = review_dir / "campaign_media_urls.json"
    if not copy_path.is_file() or not media_path.is_file():
        raise RuntimeError("Latest campaign artifact is missing campaign_copy.json or campaign_media_urls.json.")
    copy = json.loads(copy_path.read_text(encoding="utf-8"))
    media = json.loads(media_path.read_text(encoding="utf-8"))
    choice = os.getenv("IMAGE_CHOICE", "concept_1").strip()
    selected_image = next((item for item in media if item.get("choice") == choice), None)
    if not selected_image:
        available = ", ".join(item.get("choice", "") for item in media)
        raise RuntimeError(f"IMAGE_CHOICE '{choice}' is unavailable. Available: {available}")
    image_url = selected_image.get("url", "")
    video_url = required("VIDEO_URL")
    captions = {
        ("instagram", "image"): copy.get("instagram_image_caption", ""),
        ("facebook", "image"): copy.get("facebook_image_caption", ""),
        ("instagram", "video"): copy.get("instagram_video_caption", ""),
        ("facebook", "video"): copy.get("facebook_video_caption", ""),
    }
    if not image_url.startswith("https://") or not video_url.startswith("https://"):
        raise RuntimeError("Selected image and uploaded video must both have public HTTPS URLs.")
    missing = [f"{platform}_{kind}" for (platform, kind), caption in captions.items()
               if platform in platforms and not str(caption).strip()]
    if missing:
        raise RuntimeError("Campaign copy is missing captions: " + ", ".join(missing))

    token = required("META_PAGE_ACCESS_TOKEN")
    outcomes = {}
    for platform in sorted(platforms):
        for kind, media_url in (("image", image_url), ("video", video_url)):
            caption = captions[(platform, kind)]
            if platform == "instagram":
                post_id = publish_instagram(required("META_IG_USER_ID"), token, kind, media_url, caption)
            else:
                post_id = publish_facebook(required("META_PAGE_ID"), token, kind, media_url, caption)
            outcomes[f"{platform}_{kind}_post_id"] = post_id

    os.makedirs("publish_output", exist_ok=True)
    receipt = {
        "status": "PUBLISHED",
        "platform_results": outcomes,
        "image_choice": choice,
        "image_type": selected_image.get("type", ""),
        "image_url": image_url,
        "video_url": video_url,
        "captions_loaded_from_campaign_artifact": True,
        "separate_image_video_posts": True,
        "platform_specific_captions": True,
    }
    Path("publish_output/publish_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Image and video submitted as separate posts with four platform-specific captions.")
    print(json.dumps(outcomes, indent=2))

if __name__ == "__main__":
    main()
