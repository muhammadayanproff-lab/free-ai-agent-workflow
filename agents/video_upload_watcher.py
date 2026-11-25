import base64
import json
import os
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def gh_json(*args):
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return json.loads(result.stdout or "null")


def main():
    cloud = os.environ["CLOUDINARY_CLOUD_NAME"].strip()
    key = os.environ["CLOUDINARY_API_KEY"].strip()
    secret = os.environ["CLOUDINARY_API_SECRET"].strip()
    repo = os.environ["GITHUB_REPOSITORY"].strip()
    run_id = os.environ["CAMPAIGN_RUN_ID"].strip()
    run_started = parse_time(os.environ["CAMPAIGN_RUN_STARTED_AT"].strip())

    query = urllib.parse.urlencode({"max_results": "100", "tags": "true"})
    url = f"https://api.cloudinary.com/v1_1/{cloud}/resources/video/upload?{query}"
    credentials = base64.b64encode(f"{key}:{secret}".encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {credentials}"})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))

    resources = payload.get("resources", [])
    def is_campaign_upload(item):
        tags = {str(tag).lower() for tag in item.get("tags", [])}
        folder = str(item.get("asset_folder") or item.get("folder") or "").strip("/")
        public_id = str(item.get("public_id", ""))
        tagged = "click_collect_campaign_video" in tags
        in_folder = folder == "click-and-collect/manual-videos" or public_id.startswith("click-and-collect/manual-videos/")
        return tagged or in_folder

    eligible = [
        item for item in resources
        if is_campaign_upload(item)
        and item.get("secure_url", "").startswith("https://")
        and item.get("created_at")
        and parse_time(item["created_at"]) >= run_started
    ]
    if not eligible:
        print("No new video upload found for the latest campaign yet.")
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("video_found=false\n")
        return

    video = max(eligible, key=lambda item: parse_time(item["created_at"]))
    video_url = video["secure_url"]
    issue_title = f"Campaign approval required: run {run_id}"
    existing = gh_json("issue", "list", "--repo", repo, "--state", "all",
                       "--limit", "100", "--json", "number,title")
    if any(item.get("title") == issue_title for item in existing):
        print(f"Approval issue already exists for campaign run {run_id}.")
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("video_found=false\n")
        return

    review_dir = Path("campaign_review")
    review_dir.mkdir(exist_ok=True)
    details = {
        "video_url": video_url,
        "public_id": video.get("public_id", ""),
        "asset_folder": video.get("asset_folder") or video.get("folder", ""),
        "created_at": video.get("created_at", ""),
        "format": video.get("format", ""),
        "bytes": video.get("bytes", 0),
        "duration_seconds": video.get("duration"),
        "campaign_run_id": run_id,
    }
    (review_dir / "video_upload.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (review_dir / "REVIEW.md").open("a", encoding="utf-8") as report:
        report.write("\n## Uploaded campaign video\n")
        report.write(f"Cloudinary video URL: {video_url}\n")
        report.write(f"Uploaded at: {video.get('created_at', 'unknown')}\n")
        report.write("\n## Final checks before approval\n")
        report.write("- Compare AI images with the original supplier photos.\n")
        report.write("- Confirm current product stock, final customer price and COD/payment options at checkout.\n")
        report.write("- Confirm the uploaded video shows the correct product.\n")

    workflow_url = f"https://github.com/{repo}/actions/runs/{run_id}"
    watcher_run_url = f"https://github.com/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    body = f"""Your campaign assets and uploaded video are ready for final review.

**Campaign review artifact:** download it from [the campaign workflow run]({workflow_url}).
**Video upload:** [Open uploaded video]({video_url}).
**Combined review:** the video watcher run is [here]({watcher_run_url}); open its `click-collect-final-approval` artifact.

Before approving, check the original supplier photo against AI concepts, verify current stock and final price, and confirm COD/payment availability at checkout. The system does not have access to Markaz's private checkout.

To publish the selected image plus video to Instagram and Facebook (four separate posts with their platform-specific captions), comment exactly:

`APPROVE`

Only the repository owner can approve. No post is published before that approval.

<!-- campaign_run_id={run_id} -->
<!-- video_url={video_url} -->
"""
    created = subprocess.run(
        ["gh", "issue", "create", "--repo", repo, "--title", issue_title, "--body", body],
        check=True, capture_output=True, text=True
    )
    print(created.stdout.strip())
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write("video_found=true\n")


if __name__ == "__main__":
    main()
