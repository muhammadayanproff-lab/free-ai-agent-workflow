import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone

def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required input: {name}")
    return value

def main():
    image_dir = Path("generated_images")
    images = sorted(image_dir.glob("*"))
    image_path = Path(os.environ.get("INPUT_IMAGE", "").strip()) if os.environ.get("INPUT_IMAGE", "").strip() else (images[-1] if images else None)
    if not image_path or not image_path.is_file():
        raise RuntimeError("No input image found. Generate an image first or provide INPUT_IMAGE.")

    title = required("VIDEO_TITLE")
    subtitle = os.environ.get("VIDEO_SUBTITLE", "Discover it today").strip()
    cta = os.environ.get("VIDEO_CTA", "Shop now").strip()
    duration = int(os.environ.get("VIDEO_DURATION", "15"))
    if duration < 6 or duration > 30:
        raise RuntimeError("VIDEO_DURATION must be between 6 and 30 seconds.")

    output_dir = Path("generated_videos")
    output_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"product_promo_{stamp}.mp4"

    # Use text files to avoid shell/drawtext escaping problems with product names.
    title_file = output_dir / "title.txt"
    subtitle_file = output_dir / "subtitle.txt"
    cta_file = output_dir / "cta.txt"
    title_file.write_text(title[:90], encoding="utf-8")
    subtitle_file.write_text(subtitle[:110], encoding="utf-8")
    cta_file.write_text(cta[:45], encoding="utf-8")

    fps = 30
    frames = duration * fps
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan=z='min(zoom+0.0007,1.06)':d={frames}:s=1080x1920:fps={fps},"
        f"drawtext=fontfile={font}:textfile={title_file}:fontcolor=white:fontsize=64:"
        "box=1:boxcolor=black@0.48:boxborderw=24:x=(w-text_w)/2:y=h*0.12,"
        f"drawtext=fontfile={font}:textfile={subtitle_file}:fontcolor=white:fontsize=38:"
        "box=1:boxcolor=black@0.42:boxborderw=18:x=(w-text_w)/2:y=h*0.22,"
        f"drawtext=fontfile={font}:textfile={cta_file}:fontcolor=white:fontsize=52:"
        "box=1:boxcolor=0x146B45@0.92:boxborderw=24:x=(w-text_w)/2:y=h*0.82"
    )
    command = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-vf", vf, "-t", str(duration), "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(output_path)
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("FFmpeg failed: " + result.stderr[-2500:])

    print(f"VIDEO_CREATED={output_path}")
    print(f"DURATION_SECONDS={duration}")
    print("FORMAT=MP4 1080x1920 vertical, H.264")
    print("NOTE=This is a motion-graphics promo from one still image, not a filmed or AI-generated scene.")

if __name__ == "__main__":
    main()
