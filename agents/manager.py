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
MODEL = "gemini-2.5-flash"

ARTIFACT_SOURCES = [
    {
        "label": "Pakistan Product Discovery",
        "workflow": "product_discovery.yml",
        "artifact": "pakistan-product-discovery",
        "folder": "discovery",
        "expected": ["product_discovery_report.md", "selected_product.json"],
    },
    {
        "label": "Campaign Assets",
        "workflow": "campaign_assets.yml",
        "artifact": "click-collect-campaign-review",
        "folder": "campaign",
        "expected": ["REVIEW.md", "campaign_copy.md", "video_prompt.txt"],
    },
    {
        "label": "Trend Analyst",
        "workflow": "trend_analyst.yml",
        "artifact": "trend-analysis-report",
        "folder": "trends",
        "expected": ["trend_analysis_latest.md"],
    },
    {
        "label": "Meta Publishing",
        "workflow": "meta_publisher.yml",
        "artifact": "meta-publishing-receipt",
        "folder": "publishing",
        "expected": ["publish_receipt.json"],
    },
]    prompt = f"""
You are the Click & Collect campaign manager. Review only the supplied outputs:
- Pakistan Product Discovery: shortlist and Markaz Pakistan catalogue evidence.
- Campaign Assets: original supplier photos, generated image concepts, market analysis,
  one manual video prompt, and four platform/media captions.
- Trend Analyst: additional public trend signals.
- Meta Publishing: actual publish receipt, if present.

Artifact inventory:
{json.dumps(inventory, ensure_ascii=False, indent=2)}

Reports and files:
{source_text if source_text else "No readable reports were downloaded."}

Write a concise but useful Markdown review:
1. Overall status: what actually ran and what did not.
2. Product recommendation and evidence gaps, especially Markaz SKU, Pakistan Shop source,
   current stock/price and COD confirmation.
3. Image/video prompt/caption quality issues visible in the text files.
4. Whether video URL and final human approval are still missing.
5. Publishing receipt status; never claim a post was published without a receipt.
6. A prioritized next-action checklist.

Do not invent sales numbers, stock, metrics, file contents, image inspection or publish status.
The image files are not visually supplied to you here; do not claim pixel-level inspection.
Do not publish or change anything.
"""ort json
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
MODEL = "gemini-2.5-flash"

ARTIFACT_SOURCES = [
    {
        "label": "Pakistan Product Discovery",
        "workflow": "product_discovery.yml",
        "artifact": "pakistan-product-discovery",
        "folder": "discovery",
        "expected": ["product_discovery_report.md", "selected_product.json"],
    },
    {
        "label": "Campaign Assets",
        "workflow": "campaign_assets.yml",
        "artifact": "click-collect-campaign-review",
        "folder": "campaign",
        "expected": ["REVIEW.md", "campaign_copy.md", "video_prompt.txt"],
    },
    {
        "label": "Trend Analyst",
        "workflow": "trend_analyst.yml",
        "artifact": "trend-analysis-report",
        "folder": "trends",
        "expected": ["trend_analysis_latest.md"],
    },
    {
        "label": "Meta Publishing",
        "workflow": "meta_publisher.yml",
        "artifact": "meta-publishing-receipt",
        "folder": "publishing",
        "expected": ["publish_receipt.json"],
    },
]
