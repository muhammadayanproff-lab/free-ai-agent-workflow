# Click & Collect — Pakistan Product Research and Social Campaign Workflow

The repository now centers on Pakistani product discovery, public Markaz Pakistan Shop verification, market analysis, image concepts, one manually generated video prompt, manual video upload, campaign review and explicit Meta publishing approval.

## End-to-end workflow

1. **Pakistan Product Discovery** crawls public product cards from Markaz Pakistan Shop category pages (never Markaz China), collects Pakistan Google Trends and News RSS, and uses Gemini Google Search grounding to research Pakistani demand, customer problems, competitor products and publicly indexed creative examples.
2. **Product selection** ranks only products found in the live Markaz Pakistan Shop crawl. The report includes the exact public product URL, listed price, category, images, stock label (if shown), and evidence/risks.
3. **Markaz COD gate**: open the exact product URL in Pakistan Shop and confirm COD at checkout. Campaign preparation is blocked unless you explicitly confirm this. Public category pages describe COD availability, but a live item-specific checkout confirmation is still required.
4. **Market Analysis Agent** searches for product demand, reviews, competitor products and creative examples; it distinguishes evidence from hypotheses and does not invent sales or ROAS.
5. **Image Creator** generates three AI concept creatives. Original Markaz supplier images are downloaded and preserved separately for product-fidelity review; generated images may alter product details.
6. **Image Analysis & Video Prompt Agent** analyzes original product photos and creates exactly one copy-ready 10–15 second, 9:16 video prompt.
7. **Manual video upload**: use the upload page at `/upload-video.html` after it is deployed. Upload your externally generated video to Cloudinary and copy its public HTTPS URL.
8. **SEO & Caption Agent** creates four separate captions: Instagram image, Facebook image, Instagram Reel and Facebook video.
9. **Approval & Publishing**: choose APPROVE only after reviewing everything. The publishing workflow automatically downloads the latest campaign captions and image URLs; you only select which generated image, paste the uploaded video URL, select platforms and choose APPROVE.

## Required GitHub Actions secrets

- `GEMINI_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `META_PAGE_ACCESS_TOKEN`
- `META_PAGE_ID`
- `META_IG_USER_ID`

Optional variable: `META_GRAPH_API_VERSION` (default `v27.0`).

## One-time video upload setup

1. In Cloudinary, create an **unsigned upload preset** restricted to MP4/MOV/WEBM, a sensible file-size limit, and folder `click-and-collect/manual-videos`.
2. In repository Settings → Pages, select **GitHub Actions** as the build source. The GitHub Actions integration cannot enable Pages on this repository until you do this one-time setting.
3. After successful deployment, open `https://muhammadayanproff-lab.github.io/free-ai-agent-workflow/upload-video.html`.
4. Enter the unsigned preset name on the page and upload your video. Never put your Cloudinary API secret in the page.

## Honest limitations

- “Entire internet” cannot be exhaustively searched. The researcher uses public category pages, Google Search grounding, Google Trends RSS and Google News RSS; private social analytics, actual orders and ad-account metrics are not available.
- Public Markaz Shop pages are a snapshot. Stock and price can change. Confirm the exact product's COD checkout before campaign creation.
- Generated image concepts are not guaranteed to match the exact supplier product. Original product photos remain in the artifact for comparison.
- This repository does not render videos. It creates one prompt; you generate the video externally and upload it using the Cloudinary upload page.
- When both platforms are selected, publishing creates four posts: Instagram image, Instagram Reel, Facebook image and Facebook video. Each has its own caption.
- GitHub Actions, Gemini, Cloudflare, Cloudinary and Meta have independent quotas/terms. Unlimited free use is not guaranteed.

## Validation

CI compiles Python and tests repository contracts/workflow YAML. A green CI run does not verify external API access, Markaz stock/COD, image fidelity or Meta publication.
