# Click & Collect — Pakistan Product Research and Social Campaign Workflow

The repository is being reworked around Pakistan product discovery, Markaz Pakistan catalogue verification, image concepts, a manually generated video, review and explicit Meta publishing approval.

## Intended end-to-end process

1. **Pakistan Product Discovery** reads the owner's Markaz Pakistan Shop export, collects public Pakistan market signals (Google Trends RSS and Google News RSS), and ranks only products present in that export.
2. **Markaz product check**: the owner confirms the exact selected SKU is in Markaz Pakistan Shop and that COD is offered at checkout. The pipeline blocks campaign preparation unless this confirmation is explicitly supplied.
3. **Market analysis** evaluates problem-solution fit, public demand evidence, competitors, creative angles, risks and a conservative test recommendation.
4. **Image Creator** generates three AI concept creatives. Original Markaz supplier images are retained separately for product-fidelity review; AI concepts may alter product details.
5. **Image Analysis & Video Prompt Agent** analyzes original product photos and produces exactly one copy-ready 10–15 second, 9:16 video prompt.
6. **Manual video upload**: use the upload page at `/upload-video.html` after GitHub Pages is enabled. Upload your externally generated video to Cloudinary and copy its public HTTPS URL.
7. **SEO & Caption Agent** generates separate Instagram and Facebook captions for the image post and video post (four captions total).
8. **Approval & Publishing**: choose APPROVE only after review. The publisher submits separate image and video posts to the selected Meta platforms with platform-specific captions.

## Markaz catalogue input

Use Markaz **Export to My Store** after selecting/favouriting products from the Pakistan Shop tab. Export Shopify CSV, WooCommerce CSV or Excel; convert Excel to CSV if necessary. Commit the file as `catalog/markaz_pakistan_export.csv`.

The CSV should include product title, variant SKU, PKR price and image URL columns. Rows with clear China/prepaid indicators are filtered. The file must come from Pakistan Shop, not Markaz China. Keep this public repository free of private information; consider making it private before committing supplier/reseller data.

Markaz's published Export to My Store instructions say exports include images, variants, descriptions and prices, support CSV/Excel, and allow up to 50 products per export. The agent does not log in to Markaz or use passwords/session cookies.

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

1. In Cloudinary, create an **unsigned upload preset** restricted to video formats (MP4/MOV/WEBM), a sensible size limit, and folder `click-and-collect/manual-videos`.
2. In GitHub repository Settings → Pages, choose **GitHub Actions** as the build/deploy source.
3. Run the **Deploy video upload page** workflow once. The page will be available at `https://muhammadayanproff-lab.github.io/free-ai-agent-workflow/upload-video.html`.
4. Enter the unsigned preset name on the page when uploading. Do not put your Cloudinary API secret in the page.

## Honest limitations

- “Entire internet” cannot be exhaustively searched. Research uses selected public accessible sources and cites URLs/dates. Search/news interest is not verified orders or sales.
- A Markaz export is a snapshot, not live inventory. COD must be checked on the exact Pakistan listing/checkout by the owner; there is no verified public product-level API connection in this repository.
- Generated image concepts are not guaranteed to match the exact supplier product. Always compare them with the original Markaz photos.
- This repository does not render video. It writes one prompt; the owner creates the video externally and uploads it through the Cloudinary upload page.
- With both platforms selected, publishing creates four separate posts: Instagram image, Instagram Reel, Facebook image and Facebook video. Each has its own caption.
- GitHub Actions, Gemini, Cloudflare, Cloudinary and Meta have independent quotas/terms. Unlimited free usage is not guaranteed.

## Validation

CI compiles Python and tests repository contracts/workflow YAML. A green CI run does not verify third-party credentials, Markaz stock/COD, image quality or Meta publication.
