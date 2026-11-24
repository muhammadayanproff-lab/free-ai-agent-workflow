# Click & Collect 15-second vertical product video

This notebook no longer downloads or runs Stable Video Diffusion XT. The previous SVD-XT run produced only 25 frames at 7 FPS (3.57 seconds) in landscape 1024x576, and changed product details.

## Run once
1. Open `click_collect_svd_xt.ipynb` in Kaggle.
2. Replace `IMAGE_URL` with a clean, public HTTPS product photo URL.
3. Click Run All.
4. Download `click_collect_vertical_15s.mp4` from Kaggle Output.

## Output
- 15 seconds
- 1080 x 1920 portrait (9:16)
- 30 FPS, H.264 MP4
- Slow, restrained camera push using the supplied product photo

This is a photo-based motion-graphics product showcase, not generative AI footage. It preserves the source photo rather than inventing object movement. The current sample source has supplier text in its upper-right corner; the center portrait crop is intended to trim that text for this centered blender image. For other products, use a clean original photo with the product centered. The notebook does not publish to social platforms.
