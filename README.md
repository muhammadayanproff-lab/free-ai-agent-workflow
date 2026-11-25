# Click & Collect — Automated Pakistan Product-to-Social Campaign

The pipeline is scheduled and chained. You do not need to manually start each GitHub Actions workflow.

## Automatic schedule and handoffs

1. **Every other day at 2:00 PM Pakistan time**, Product Discovery runs automatically. GitHub schedules a daily check at 09:00 UTC; a Pakistan-time date guard allows every second day, anchored on 26 November 2026.
2. When Product Discovery succeeds, **Campaign Assets starts automatically**. It verifies the public Markaz Pakistan Shop listing, downloads original photos, researches the market, creates three AI image concepts, generates one 10–15 second video prompt, writes SEO and four platform-specific captions, and uploads the images to Cloudinary.
3. The process pauses for your one manual creative task: copy the generated video prompt into your chosen video generator, create the video, and upload it at the upload page:
   https://muhammadayanproff-lab.github.io/free-ai-agent-workflow/upload-video.html
4. A background GitHub workflow checks the Cloudinary video folder every five minutes. When it detects a video uploaded after the latest campaign, it creates a final approval issue and attaches a combined review artifact. You do not need to copy a URL or run another workflow.
5. Review the original supplier image, AI concepts, video, SEO and captions. Also verify current product stock, final price and COD/payment availability at checkout. When ready, comment exactly **APPROVE** on the approval issue.
6. The approval comment automatically publishes the selected AI image concept and uploaded video as four separate posts: Instagram image, Instagram Reel, Facebook image and Facebook video. Each post uses its own generated caption. The workflow then posts a receipt and closes the approval issue.

## What still requires you

- Generate the video externally from the supplied prompt and upload it on the upload page.
- Give the final approval by commenting **APPROVE** on the campaign approval issue.

## Important verification limits

- Markaz's private checkout is not accessible through the public product listing. The automation does not claim COD is verified and instructs the copywriter not to promise COD or unverified payment/delivery terms. Check stock, final price and payment options before approval.
- Public Markaz Shop pages are snapshots. Stock and price can change.
- AI image concepts may change product details. Compare them with the original supplier photos before approval.
- The researcher uses public category pages, Google Search grounding, Google Trends RSS and Google News RSS; it cannot exhaustively search the entire internet or private social analytics.
- Video rendering remains external; this repository creates the prompt and automatically handles the uploaded result afterwards.
- Publishing requires the existing Meta secrets and appropriate Instagram/Facebook permissions. GitHub Actions, Gemini, Cloudflare, Cloudinary and Meta have independent quotas/terms; unlimited free use is not guaranteed.

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

## One-time setup already used by this project

- Configure the restricted unsigned Cloudinary video preset `click_collect_manual_video` once.
- GitHub Pages must use **GitHub Actions** as its build source for the upload page.
- The Cloudinary upload page enforces a 100 MB browser-side limit. The preset does not enforce a server-side per-preset size cap.
- GitHub Actions schedule events can be delayed by GitHub; 2:00 PM Pakistan time is the requested schedule, not a guaranteed exact start second.

## Validation

CI compiles Python and tests repository contracts/workflow YAML. A green CI run does not verify external API access, Markaz stock/COD, image fidelity or successful Meta publication.
