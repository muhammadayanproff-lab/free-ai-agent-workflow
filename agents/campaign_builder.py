import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run_agent(label, script, extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})
    print(f"\n===== {label} =====", flush=True)
    result = subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=ROOT,
        env=env,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")

def copy_if_exists(source, destination):
    source = ROOT / source
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    elif source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)

def main():
    product = os.environ.get("PRODUCT_NAME", "").strip()
    product_url = os.environ.get("PRODUCT_URL", "").strip()
    if not product and not product_url:
        raise RuntimeError("Enter a product name or public product URL.")

    audience = os.environ.get("TARGET_AUDIENCE", "Pakistan online shoppers").strip()
    category = os.environ.get("PRODUCT_CATEGORY", "").strip()
    price = os.environ.get("PRODUCT_PRICE", "").strip()
    notes = os.environ.get("PRODUCT_NOTES", "").strip()
    platforms = os.environ.get("TARGET_PLATFORMS", "Instagram,Facebook,TikTok").strip()
    image_prompt = os.environ.get("IMAGE_PROMPT", "").strip()
    if not image_prompt:
        image_prompt = (
            f"Create a clean premium ecommerce promotional product image for {product}. "
            "Show one clear product hero on a simple studio background. "
            "Do not add text, logos, fake product features, accessories, or badges."
        )
    video_title = os.environ.get("VIDEO_TITLE", product or "Product highlight").strip()
    video_subtitle = os.environ.get("VIDEO_SUBTITLE", "").strip()
    video_cta = os.environ.get("VIDEO_CTA", "Shop now").strip()
    duration = os.environ.get("VIDEO_DURATION", "15").strip()

    common_brief = " | ".join(x for x in [category, price, notes] if x)
    topic = product or product_url
    caption_brief = (
        f"Product: {topic}. Category: {category or 'not supplied'}. "
        f"Supplier price: {price or 'not supplied'}. "
        f"Verified details/notes: {notes or 'not supplied'}. "
        "Only state supplied and verified facts. Do not invent specifications, "
        "discounts, delivery promises, warranty, reviews, or stock."
    )

    run_agent("1/5 Product opportunity research", "agents/product_researcher.py", {
        "PRODUCT_NAME": product, "PRODUCT_URL": product_url,
        "PRODUCT_PRICE": price, "PRODUCT_CATEGORY": category, "PRODUCT_NOTES": notes,
    })
    run_agent("2/5 SEO and captions", "agents/seo_caption_writer.py", {
        "CONTENT_TOPIC": caption_brief, "TARGET_AUDIENCE": audience,
        "CONTENT_PLATFORM": platforms, "TARGET_KEYWORDS": product + " Pakistan " + category,
    })
    run_agent("3/5 Promotional image", "agents/images_creator.py", {
        "IMAGE_PROMPT": image_prompt,
    })
    run_agent("4/5 Vertical promotional video", "agents/video_creator.py", {
        "VIDEO_TITLE": video_title, "VIDEO_SUBTITLE": video_subtitle,
        "VIDEO_CTA": video_cta, "VIDEO_DURATION": duration,
    })
    run_agent("5/5 Platform-specific post drafts", "agents/publisher.py", {
        "POST_TOPIC": topic, "POST_AUDIENCE": audience, "POST_CAPTION": caption_brief,
        "TARGET_PLATFORMS": platforms, "MEDIA_TYPE": "video",
        "MEDIA_URL": "", "PUBLISH_APPROVAL": "DRAFT_ONLY",
    })

    package = ROOT / "campaign_package"
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)

    copy_if_exists("product_research_output", package / "product_research")
    copy_if_exists("reports/seo_content_latest.md", package / "seo_and_captions.md")
    copy_if_exists("generated_images", package / "images")
    copy_if_exists("generated_videos", package / "videos")
    copy_if_exists("publisher_output", package / "social_post_drafts")

    readme = f"""# Click and Collect — Campaign Approval Package

Product: {product or product_url}
Audience: {audience}
Platforms drafted: {platforms}

## Included
- Product opportunity research and evidence
- SEO copy and social caption suggestions
- Generated promotional image
- Vertical MP4 motion-graphics promo
- Platform-specific post drafts (Instagram/Facebook/TikTok as selected)

## Important status
**DRAFT ONLY — NOT APPROVED — NOT PUBLISHED — NOT LISTED ON THE STORE**

The image/video are creative mockups generated from the supplied prompt, not proof of the exact supplier item.
Check the actual Markaz listing, supplier, product specifications, price, stock, delivery, returns and legal compliance.
No external social post or website product listing is created by this workflow.
"""
    (package / "APPROVAL_README.md").write_text(readme, encoding="utf-8")
    print("\nCAMPAIGN PACKAGE CREATED: campaign_package/")
    print("Publishing status: NOT PUBLISHED")
    print("Store listing status: NOT LISTED")

if __name__ == "__main__":
    main()
