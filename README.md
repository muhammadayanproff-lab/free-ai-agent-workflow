# Click & Collect — AI Commerce Campaign Automation

This repository contains Python agents and GitHub Actions for product research, public trend signals, image generation, caption writing, campaign review and manually approved Meta publishing.

## Agents and workflows

- Researcher: public Google News niche research.
- Trend Analyst: Google Trends RSS and Google News RSS. These are not Instagram/TikTok analytics.
- Product Opportunity Researcher: evaluates a supplied product name/public URL and Pakistan public-news signals. It does not access a private Markaz catalog.
- Image Creator: Cloudflare Workers AI FLUX concept image. AI may alter product shape, logo, details and text; it is not a verified supplier photo.
- SEO & Caption Writer: keywords, metadata, captions and hashtags.
- Video Creator: 10–30 seconds (default 15), 1080x1920, 9:16, 30 FPS H.264 motion-graphics MP4 from one still image. This is NOT generative AI footage; it adds camera movement/text to a still image.
- Manager: consolidates agent artifacts into a report.
- Publisher: draft-only; never posts.
- Meta Publisher: Facebook/Instagram publishing guarded by the exact APPROVE input. This is a basic manual guard, not secure multi-person approval.
- Daily Campaign Builder: product research, trends, creative brief, image, SEO, video and review artifact.
- Meta Credential Validator: read-only Page/Instagram check.

## Required GitHub Actions secrets

Add under Settings → Secrets and variables → Actions → Repository secrets. Never put secrets in code or chat.

- GEMINI_API_KEY
- CLOUDFLARE_ACCOUNT_ID
- CLOUDFLARE_API_TOKEN
- CLOUDINARY_CLOUD_NAME
- CLOUDINARY_API_KEY
- CLOUDINARY_API_SECRET
- META_PAGE_ACCESS_TOKEN
- META_PAGE_ID
- META_IG_USER_ID

Optional repository variable: META_GRAPH_API_VERSION. Code defaults to v27.0 if unset.

## Recommended campaign process

1. Run Daily AI Campaign Builder with product name and verified details.
2. Download the click-and-collect-campaign-review artifact.
3. Manually inspect product facts, source image, video and captions.
4. If accurate, run Approved Meta Social Publishing, choose APPROVE, provide final caption and public Cloudinary media URL.
5. Check the publishing receipt.

Never approve media that misrepresents the supplier product. Use a clean supplier photo for product fidelity.

## Markaz integration status

No official public Markaz catalog API or authenticated export integration is implemented. Product workflows currently require a product name and optionally a public product URL/details. Automatic product discovery needs a supported official export/API or a supplied catalog export. Do not scrape private pages or bypass access controls.

## Video limitations

The GitHub workflow creates a vertical 15-second motion-graphics video from one image. It does not generate realistic people or physically moving products. The Kaggle notebook is also a still-image motion showcase. A real 10–15 second generative image-to-video model on free T4 GPUs is not guaranteed and is not integrated into the automatic campaign pipeline.

## Local validation

Install requirements, then run Python compileall on agents and tests, followed by unittest discovery in tests. CI runs static checks; a green CI run does not verify external API credentials, quotas, Meta publishing, Cloudinary upload or media quality.

## Costs and quotas

GitHub runners, Gemini, Cloudflare Workers AI, Cloudinary and Kaggle have separate plans, quotas and terms. Unlimited free usage or two finished generative videos every day is not guaranteed.
