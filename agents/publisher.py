import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MODEL = "gemini-3.5-flash-lite"
API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

ALLOWED_PLATFORMS = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tiktok": "TikTok",
}


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required workflow input is missing: {name}")
    return value


def selected_platforms(raw):
    requested = [part.strip().lower() for part in raw.split(",") if part.strip()]
    if not requested:
        raise RuntimeError("Choose at least one platform.")
    unknown = sorted(set(requested) - set(ALLOWED_PLATFORMS))
    if unknown:
        raise RuntimeError(
            "Unsupported platform(s): " + ", ".join(unknown)
            + ". Supported: Instagram, Facebook, TikTok."
        )
    # Preserve the user's selected order and remove duplicates.
    return list(dict.fromkeys(requested))


def call_gemini(topic, audience, caption, platforms, media_type, media_url, approval):
    prompt = f"""
You are Agent 6, the social publishing preparation assistant.
Create platform-specific post drafts for the selected platforms.

Topic: {topic}
Target audience: {audience}
User-provided caption/brief: {caption or "(not supplied; write a suitable draft)"}
Selected platforms: {", ".join(ALLOWED_PLATFORMS[p] for p in platforms)}
Media type: {media_type}
Media URL supplied: {"yes" if media_url else "no"}
Approval state: {approval}

Return ONLY valid JSON with this exact structure:
{{
  "posts": [
    {{
      "platform": "Instagram|Facebook|TikTok",
      "caption": "complete post caption",
      "hashtags": ["tag1", "tag2"],
      "call_to_action": "short CTA",
      "media_note": "what media is suitable or missing",
      "checks": ["one practical platform-specific review item"]
    }}
  ],
  "human_review": ["review item"]
}}

Rules:
- Return exactly one post for each selected platform, no extra platforms.
- Preserve factual meaning. Do not invent prices, offers, testimonials, guarantees,
  statistics, links, or claims.
- Tailor length, hook and tone to each platform.
- Keep hashtags relevant and avoid keyword stuffing.
- Do not state that anything has been published, scheduled, uploaded or approved.
- TikTok captions should be concise and suitable for a short video. If media type
  is image, note that the TikTok photo-post feature and account/app eligibility
  must be verified before any publishing integration is enabled.
- Instagram and Facebook drafts should be suitable for their respective feeds.
- The media URL is metadata only; do not fetch it or claim to have checked it.
- This workflow is currently draft-only. Approval input does not authorize an
  external post from this version of Agent 6.
"""
    endpoint = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.35, "maxOutputTokens": 3500},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini API error {error.code}: {details[:1000]}"
        ) from error

    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError(
            "Gemini returned no draft: "
            + json.dumps(result.get("promptFeedback", {}))[:800]
        )
    text = "\n".join(
        part.get("text", "")
        for part in candidates[0].get("content", {}).get("parts", [])
        if part.get("text")
    ).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    # Remove optional Markdown code fences before parsing JSON.
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Gemini did not return valid JSON: {text[:1000]}"
        ) from error

    posts = data.get("posts")
    if not isinstance(posts, list) or len(posts) != len(platforms):
        raise RuntimeError("Gemini response did not contain one post per platform.")

    expected = {ALLOWED_PLATFORMS[p] for p in platforms}
    actual = {post.get("platform") for post in posts if isinstance(post, dict)}
    if actual != expected:
        raise RuntimeError(
            "Platform mismatch in generated drafts. "
            f"Expected {sorted(expected)}, received {sorted(actual)}."
        )
    return data


def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")

    topic = required_env("POST_TOPIC")
    audience = os.environ.get("POST_AUDIENCE", "general audience").strip()
    caption = os.environ.get("POST_CAPTION", "").strip()
    platforms = selected_platforms(required_env("TARGET_PLATFORMS"))
    media_type = os.environ.get("MEDIA_TYPE", "none").strip().lower()
    media_url = os.environ.get("MEDIA_URL", "").strip()
    approval = os.environ.get("PUBLISH_APPROVAL", "DRAFT_ONLY").strip()

    if media_type not in {"none", "image", "video"}:
        raise RuntimeError("MEDIA_TYPE must be none, image, or video.")
    if media_url and not media_url.startswith("https://"):
        raise RuntimeError("MEDIA_URL must be a public HTTPS URL.")

    # This release intentionally cannot publish. The approval field is recorded
    # for audit only; a future release will add platform APIs after account setup.
    print("Agent 6 is running in SAFE DRAFT-ONLY mode.")
    print(f"Approval input received: {approval}")
    print("No platform API calls will be made. Nothing will be posted or scheduled.")

    result = call_gemini(
        topic, audience, caption, platforms, media_type, media_url, approval
    )

    output_dir = Path("publisher_output")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()

    package = {
        "created_at_utc": timestamp,
        "mode": "draft_only",
        "approval_input": approval,
        "topic": topic,
        "audience": audience,
        "media_type": media_type,
        "media_url": media_url or None,
        "platforms": [ALLOWED_PLATFORMS[p] for p in platforms],
        "posts": result["posts"],
        "human_review": result.get("human_review", []),
        "publishing_status": "NOT_PUBLISHED",
    }

    json_path = output_dir / "social_posts_for_review.json"
    md_path = output_dir / "social_posts_for_review.md"
    json_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with md_path.open("w", encoding="utf-8") as report:
        report.write("# Agent 6 — Social Posts for Human Review\n\n")
        report.write(f"- Created (UTC): {timestamp}\n")
        report.write("- Mode: **DRAFT ONLY**\n")
        report.write("- Publishing status: **NOT PUBLISHED**\n")
        report.write(f"- Topic: {topic}\n")
        report.write(f"- Platforms: {', '.join(package['platforms'])}\n")
        report.write(f"- Media type: {media_type}\n")
        if media_url:
            report.write(f"- Supplied media URL: {media_url}\n")
        report.write("\n> Nothing has been posted or scheduled. Review each draft before use.\n")
        for post in result["posts"]:
            report.write(f"\n---\n\n## {post['platform']}\n\n")
            report.write(post.get("caption", "") + "\n\n")
            hashtags = post.get("hashtags", [])
            if hashtags:
                report.write(" ".join("#" + str(tag).lstrip("#") for tag in hashtags) + "\n\n")
            report.write(f"**Call to action:** {post.get('call_to_action', '')}\n\n")
            report.write(f"**Media note:** {post.get('media_note', '')}\n\n")
            checks = post.get("checks", [])
            if checks:
                report.write("**Before publishing:**\n")
                for check in checks:
                    report.write(f"- [ ] {check}\n")
        review = result.get("human_review", [])
        if review:
            report.write("\n---\n\n## Final human review\n")
            for item in review:
                report.write(f"- [ ] {item}\n")

    print(f"Review files saved: {md_path} and {json_path}")


if __name__ == "__main__":
    main()
