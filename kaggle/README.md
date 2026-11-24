# Kaggle image-to-video notebook

Open `click_collect_svd_xt.ipynb` in Kaggle (or download this file and use Kaggle's **Import Notebook** option).

## Run it

1. In Kaggle, enable **GPU** in Notebook settings.
2. Open the notebook. In its single code cell, replace `PASTE_PUBLIC_PRODUCT_IMAGE_URL_HERE` with the public HTTPS URL of the product image (for example, the Cloudinary image URL produced by this repository).
3. Click **Run All** once. The first run downloads the SVD-XT model into `/root/.cache/huggingface`.
4. When complete, download `click_collect_ai_video.mp4` from the Kaggle Output panel.

## What it generates

Stable Video Diffusion XT creates a short image-conditioned clip (25 frames, 7 fps) from the supplied product image. The notebook uses FP16, model CPU offload, and UNet forward chunking to reduce VRAM use.

## Important limitations

- This is a short AI-generated motion clip, not a guaranteed faithful product advertisement. Product shape, logos, labels, and fine details can change between frames.
- SVD can produce subtle or no motion and does not accept text prompts for precise scene control.
- Generation time on Kaggle Tesla T4 GPUs is not guaranteed.
- Review Stability AI's [SVD community licence](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt) before commercial use.
- This notebook saves the MP4 in Kaggle output. It does not automatically upload to Cloudinary or publish to Instagram/Facebook.
