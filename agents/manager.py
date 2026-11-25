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
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "").strip()
MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
SOURCES = [
    ("Pakistan Product Discovery", "product_discovery.yml", "pakistan-product-discovery", "discovery"),
    ("Campaign Assets", "campaign_assets.yml", "click-collect-campaign-review", "campaign"),
    ("Trend Analyst", "trend_analyst.yml", "trend-analysis-report", "trends"),
    ("Meta Publishing", "meta_publisher.yml", "meta-publishing-receipt", "publishing"),
]

def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "GitHub CLI failed")[:1200])
    return result.stdout.strip()

def download_latest(label, workflow, artifact, folder):
    target = Path("manager_inputs") / folder
    target.mkdir(parents=True, exist_ok=True)
    run_id = command([
        "gh", "run", "list", "--repo", REPOSITORY, "--workflow", workflow,
        "--status", "completed", "--limit", "20", "--json", "databaseId,conclusion",
        "--jq", 'map(select(.conclusion == "success")) | .[0].databaseId // empty'
    ])
    if not run_id:
        return {"agent": label, "status": "missing", "files": [], "detail": "No successful run found."}
    try:
        command(["gh", "run", "download", run_id, "--repo", REPOSITORY,
                 "--name", artifact, "--dir", str(target)])
    except Exception as exc:
        return {"agent": label, "status": "download_failed", "files": [], "detail": str(exc)[:900]}
    for archive in list(target.rglob("*.zip")):
        with zipfile.ZipFile(archive) as zf:
            root = target.resolve()
            for member in zf.infolist():
                dest = (target / member.filename).resolve()
                if dest != root and root not in dest.parents:
                    raise RuntimeError("Unsafe path in artifact archive.")
            zf.extractall(target)
        archive.unlink()
    files = sorted(p for p in target.rglob("*") if p.is_file())
    return {"agent": label, "status": "downloaded" if files else "empty",
            "files": files, "detail": f"Latest successful run: {run_id}"}

def collect(downloads):
    inventory, sections = [], []
    for item in downloads:
        inventory.append({"agent": item["agent"], "status": item["status"],
                          "detail": item["detail"], "files": [str(x) for x in item["files"]]})
        for path in item["files"]:
            if path.suffix.lower() not in {".md", ".txt", ".json"}:
                continue
            sections.append(f"\n\n### {item['agent']} / {path.name}\n" +
                            path.read_text(encoding="utf-8", errors="replace")[:16000])
    return inventory, "\n".join(sections)

def ask_gemini(inventory, source_text):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    prompt = f"""
You are the Click & Collect campaign manager. Review only the supplied outputs:
- Pakistan Product Discovery: candidates and Markaz Pakistan catalogue evidence.
- Campaign Assets: original supplier photos, AI image concepts, market analysis,
  one manual video prompt and four separate captions.
- Trend Analyst: additional public trend signals.
- Meta Publishing: actual publishing receipt, if available.

Artifact inventory:
{json.dumps(inventory, ensure_ascii=False, indent=2)}

Reports:
{source_text or "No reports available."}

Create a concise Markdown report:
1. What actually completed and what is missing.
2. Product recommendation and evidence gaps, especially SKU, Pakistan Shop source,
   current stock/price and owner-confirmed COD.
3. Risks or inconsistencies in image concepts, prompt and captions.
4. Whether a manually generated video URL and human approval are still needed.
5. Publishing status: only say published if a receipt confirms it.
6. Prioritized next steps.

Never invent sales, stock, metrics, visual inspection, file contents or publishing status.
Do not claim to have visually inspected image files; only text reports are provided.
Do not publish or modify anything.
"""
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.25, "maxOutputTokens": 4500}}
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY}, method="POST")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=150) as response:
                result = json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 4:
                raise RuntimeError(f"Gemini manager HTTP {exc.code}: {detail[:1000]}")
            time.sleep(5 * (2 ** attempt))
    parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    report = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
    if not report:
        raise RuntimeError("Gemini returned an empty manager report.")
    return report

def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")
    if not REPOSITORY or not os.getenv("GH_TOKEN", "").strip():
        raise RuntimeError("GITHUB_REPOSITORY or GH_TOKEN is missing.")
    Path("manager_inputs").mkdir(exist_ok=True)
    downloads = []
    for label, workflow, artifact, folder in SOURCES:
        try:
            item = download_latest(label, workflow, artifact, folder)
        except Exception as exc:
            item = {"agent": label, "status": "collection_error", "files": [], "detail": str(exc)[:900]}
        downloads.append(item)
        print(f"{label}: {item['status']}")
    inventory, source_text = collect(downloads)
    report = ask_gemini(inventory, source_text)
    out = Path("reports")
    out.mkdir(exist_ok=True)
    path = out / "manager_report_latest.md"
    lines = ["# Click & Collect — Manager Report", "",
             f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}", "",
             "| Agent | Status | Files |", "|---|---|---|"]
    for item in inventory:
        names = ", ".join(Path(x).name for x in item["files"]) or "None"
        lines.append(f"| {item['agent']} | {item['status']} | {names} |")
    lines.extend(["", "---", "", report, ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Manager report saved: {path}")

if __name__ == "__main__":
    main()
