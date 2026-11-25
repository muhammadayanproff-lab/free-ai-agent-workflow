# Click & Collect — Pakistan Product Research and Social Campaign Workflow

This repository is being reworked around product discovery, Markaz Pakistan catalogue verification, creative assets, a manually generated video, review and explicit Meta publishing approval.

## New intended process

1. **Pakistan Product Discovery** reads the owner's Markaz Pakistan Shop export, collects public Pakistan market signals (Google Trends RSS and Google News RSS), and ranks only products actually present in that export.
2. **Markaz verification** uses the official Pakistan catalogue export as the product source. The exact product's current availability, variant, price and COD checkout still need final confirmation in Markaz before it is approved for campaign production.
3. **Market and creative analysis** checks the product's problem-solution fit, public demand evidence, risks and competing creative patterns. Search interest is not actual sales data.
4. **Image creation** creates a small set of concept creatives. Original Markaz supplier images must remain in the campaign package for product-fidelity checks; generated images may alter product details and must be reviewed.
5. **Image analysis & video prompt** analyzes the product photos and produces exactly one copy-ready prompt for a 10–15 second 9:16 promotional video. This repository no longer renders videos.
6. **Manual video upload**: create the video with your chosen external tool, upload it to Cloudinary, and paste its public HTTPS URL into the final publishing workflow.
7. **SEO & captions**: create separate SEO-aware captions for the image post and video/Reel post, each adapted to Instagram and Facebook.
8. **Approval & publishing**: only the explicit APPROVE choice can publish. The publisher submits separate image and video posts, each with its own caption, to the selected Meta platforms.

## Markaz Pakistan catalogue input

Use Markaz's **Export to My Store** feature after selecting/favouriting products in the Pakistan Shop tab. Export Shopify CSV, WooCommerce CSV or Excel, convert Excel to CSV if necessary, then commit the file as:

`catalog/markaz_pakistan_export.csv`

The research workflow expects product title, variant SKU, PKR price and image URL columns. It excludes obvious China/prepaid rows. Never export from Markaz China for this pipeline. The file can contain private reseller pricing, so keep the repository private if you do not want that data public.

Markaz documents that its export includes product images, variants, descriptions and prices, supports CSV/Excel, and allows up to 50 products per export. The exporter is an authenticated owner action; the agent does not log into Markaz or use your password.

## Secrets

Repository secrets (never paste these into code or chat):
- `GEMINI_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `META_PAGE_ACCESS_TOKEN`
- `META_PAGE_ID`
- `META_IG_USER_ID`

Optional variable: `META_GRAPH_API_VERSION` (defaults to `v27.0`).

## Important limits

- “Entire internet” cannot be exhaustively searched. The researcher uses selected public, accessible sources and records source URLs/dates; search/news trends are only demand signals, not verified sales.
- A Markaz export is a snapshot, not a live stock guarantee. Check the exact Pakistan product page and COD option before moving a product forward. The system does not access private Markaz sessions or bypass access controls.
- Generated images are creative concepts, not guaranteed exact supplier photos. Preserve the original product photos and review every generated image.
- No automatic video rendering is included. The system writes one prompt; you generate the video externally and provide its public HTTPS URL.
- Meta publishing creates four posts when both platforms are selected: image and video on Instagram, and image and video on Facebook. Captions are separate. A successful workflow run is required to confirm publication.
- GitHub Actions, Gemini, Cloudflare, Cloudinary and Meta have independent quotas and terms. Unlimited free use is not guaranteed.

## Validation

CI checks Python syntax, workflow YAML and repository contracts. A green CI run does not validate live third-party credentials, Markaz stock/COD, image quality or Meta publishing.
