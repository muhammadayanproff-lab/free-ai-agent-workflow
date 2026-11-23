import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "").strip()
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "").strip()
MODEL = "gemini-3.5-flash-lite"

ARTIFACT_SOURCES = [
    {
        "label": "Researcher",
        "workflow": "researcher.yml",
        "artifact": "daily-research-report",
        "folder": "research",
        "expected": ["research_latest.md"],
    },
    {
        "label": "Trend Analyst",
        "workflow": "trend_analyst.yml",
        "artifact": "trend-analysis-report",
        "folder": "trends",
        "expected": ["trend_analysis_latest.md"],
    },
    {
        "label": "Image Creator",
        "workflow": "image_creator.yml",
        "artifact": "ai-generated-image-and-url",
        "folder": "images",
        "expected": [],
    },
    {
        "label": "SEO & Caption Writer",
        "workflow": "seo_caption_writer.yml",
        "artifact": "seo-caption-report",
        "folder": "seo",
        "expected": ["seo_content_latest.md"],
    },
]

MAX_FILE_CHARS = 18000


def run_command(args):
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Unknown command error").strip()
        raise RuntimeError(detail[:1200])
    return result.stdout.strip()


def latest_successful_run(workflow_file):
    output = run_command([
        "gh", "run", "list",
        "--repo", GITHUB_REPOSITORY,
        "--workflow", workflow_file,
        "--status", "completed",
        "--limit", "20",
        "--json", "databaseId,conclusion",
        "--jq", "map(select(.conclusion == \"success\")) | .[0].databaseId // empty",
    ])
    return output


def download_artifact(source):
    destination = Path("manager_inputs") / source["folder"]
    destination.mkdir(parents=True, exist_ok=True)

    run_id = latest_successful_run(source["workflow"])
    if not run_id:
        return {
            "label": source["label"],
            "status": "missing",
            "detail": "No successful workflow run was found.",
            "files": [],
        }

    try:
        run_command([
            "gh", "run", "download", run_id,
            "--repo", GITHUB_REPOSITORY,
            "--name", source["artifact"],
            "--dir", str(destination),
        ])
    except Exception as error:
        return {
            "label": source["label"],
            "status": "download_failed",
            "detail": str(error)[:1000],
            "run_id": run_id,
            "files": [],
        }

    files = sorted(
        path for path in destination.rglob("*") if path.is_file()
    )

    # Some artifact downloads may contain a ZIP file; safely extract it.
    for archive in [p for p in files if p.suffix.lower() == ".zip"]:
        try:
            with zipfile.ZipFile(archive) as zip_file:
                for member in zip_file.infolist():
                    target = (destination / member.filename).resolve()
                    if destination.resolve() not in target.parents and target != destination.resolve():
                        raise RuntimeError("Unsafe path inside downloaded ZIP.")
                zip_file.extractall(destination)
            archive.unlink()
        except Exception as error:
            print(f"Could not extract {archive.name}: {error}")

    files = sorted(
        path for path in destination.rglob("*") if path.is_file()
    )
    return {
        "label": source["label"],
        "status": "downloaded" if files else "empty",
        "detail": f"Downloaded from successful run {run_id}.",
        "run_id": run_id,
        "files": files,
    }


def read_text_reports(downloads):
    sections = []
    inventory = []

    for item in downloads:
        inventory.append({
            "agent": item["label"],
            "status": item["status"],
            "detail": item["detail"],
            "files": [str(path) for path in item["files"]],
        })

        for path in item["files"]:
            if path.suffix.lower() not in (".md", ".txt", ".json", ".csv"):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as error:
                content = f"Could not read report: {error}"
            sections.append(
                f"\n\n===== {item['label']} / {path.name} =====\n"
                + content[:MAX_FILE_CHARS]
            )

    return inventory, "\n".join(sections)


def ask_gemini(inventory, source_text):
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )
    prompt = f"""
You are the Manager Agent for a small AI content production workflow.

Review the supplied outputs from four agents:
- Researcher: topic research and source links.
- Trend Analyst: trend evidence and content opportunities.
- Image Creator: generated image artifact availability (the image pixels are
  not provided here, so do not claim to have visually inspected them).
- SEO & Caption Writer: SEO metadata, outline, captions and hashtags.

Artifact inventory:
{json.dumps(inventory, ensure_ascii=False, indent=2)}

Text reports:
{source_text if source_text else "No readable text reports were downloaded."}

Prepare a practical management report in Markdown with:
1. Executive summary.
2. Agent-by-agent status and what files were actually available.
3. Strongest content opportunities supported by the reports.
4. Recommended content package: topic, audience, format, suggested hook,
   SEO angle and which image file could accompany it (only if an image exists).
5. Quality review: inconsistencies, unsupported claims, missing sources,
   weak captions, keyword stuffing or other issues actually observed.
6. Missing inputs and specific actions needed to fix them.
7. A prioritized next-step checklist for a human reviewer.

Important:
- Do not invent data, results, file contents, metrics or source links.
- Distinguish missing artifacts from failed agents.
- Do not claim to have inspected image contents; report only filenames and
  availability for the Image Creator artifact.
- Do not publish, post, schedule, delete or modify anything.
- If reports disagree, explain the disagreement instead of silently choosing.
- Be concise but specific. Use only evidence in the supplied material.
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.25,
            "maxOutputTokens": 5000,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY,
        },
        method="POST",
    )

    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if error.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(
                    f"Gemini API error {error.code}: {details[:1000]}"
                ) from error
            if attempt == 4:
                raise RuntimeError(
                    f"Gemini unavailable after 5 attempts "
                    f"(HTTP {error.code}): {details[:500]}"
                ) from error
            delay = 5 * (2 ** attempt)
            print(f"Gemini temporarily unavailable; retrying in {delay}s.")
            time.sleep(delay)

    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError(
            "Gemini returned no report: "
            + json.dumps(result.get("promptFeedback", {}))[:800]
        )

    parts = candidates[0].get("content", {}).get("parts", [])
    report = "\n".join(
        part.get("text", "") for part in parts if part.get("text")
    ).strip()
    if not report:
        raise RuntimeError("Gemini returned an empty manager report.")
    return report


def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")
    if not GITHUB_REPOSITORY or not GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_REPOSITORY or GH_TOKEN is missing. "
            "Check the manager workflow environment."
        )

    print("Manager Agent: collecting the latest successful agent artifacts.")
    Path("manager_inputs").mkdir(exist_ok=True)

    downloads = []
    for source in ARTIFACT_SOURCES:
        print(f"Collecting {source['label']} artifact...")
        try:
            item = download_artifact(source)
        except Exception as error:
            item = {
                "label": source["label"],
                "status": "collection_error",
                "detail": str(error)[:1000],
                "files": [],
            }
        downloads.append(item)
        print(f"{item['label']}: {item['status']}")

    inventory, source_text = read_text_reports(downloads)
    report = ask_gemini(inventory, source_text)

    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "manager_report_latest.md"

    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write("# AI Workforce — Manager Report\n\n")
        output_file.write(
            f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}\n\n"
        )
        output_file.write("## Artifact inventory\n\n")
        output_file.write("| Agent | Status | Files |\n")
        output_file.write("|---|---|---|\n")
        for item in inventory:
            filenames = ", ".join(Path(name).name for name in item["files"]) or "None"
            output_file.write(
                f"| {item['agent']} | {item['status']} | {filenames} |\n"
            )
        output_file.write("\n---\n\n")
        output_file.write(report)
        output_file.write("\n")

    print(f"Manager report saved: {output_path}")


if __name__ == "__main__":
    main()
