import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

MODEL = "gemini-3.5-flash-lite"
API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
PRODUCT = os.environ.get("PRODUCT_NAME", "").strip()
PRODUCT_URL = os.environ.get("PRODUCT_URL", "").strip()
PRICE = os.environ.get("PRODUCT_PRICE", "").strip()
CATEGORY = os.environ.get("PRODUCT_CATEGORY", "").strip()
NOTES = os.environ.get("PRODUCT_NOTES", "").strip()


def fetch_public_product_page(url):
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("PRODUCT_URL must be a public HTTPS URL.")
    # Do not send credentials or cookies; only retrieve a public page.
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; ClickCollectResearch/1.0)"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return ""
            raw = response.read(600_000).decode("utf-8", errors="replace")
    except Exception as error:
        print(f"Public product page could not be fetched: {error}")
        return ""
    raw = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = unescape(re.sub(r"\s+", " ", raw))
    return raw[:10000]


def fetch_market_signals(query):
    search = urllib.parse.quote(query + " Pakistan")
    url = (
        "https://news.google.com/rss/search?q=" + search
        + "&hl=en-PK&gl=PK&ceid=PK:en"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            root = ET.fromstring(response.read())
    except Exception as error:
        print(f"Market signal feed unavailable: {error}")
        return []
    items = []
    for item in root.findall(".//item")[:12]:
        items.append({
            "title": item.findtext("title", ""),
            "url": item.findtext("link", ""),
            "published": item.findtext("pubDate", ""),
            "snippet": re.sub(r"<[^>]+>", " ", item.findtext("description", ""))[:500],
        })
    return items


def call_gemini(payload):
    endpoint = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )
    prompt = f"""
You are the product opportunity analyst for Click and Collect, a Pakistan-focused
online reselling store. Assess the supplied product using ONLY the evidence below.

Return a clear Markdown approval report with:
- Product summary (separate supplied facts from inferred details)
- Likely Pakistan customer segments and use cases
- Demand signals from the supplied public articles, with dates and source URLs
- Competition/pricing considerations (never invent competitor prices)
- Opportunity score from 1-5 with a short evidence-based explanation
- Risks: quality, sizing/compatibility, delivery, returns, seasonality, compliance
- Questions the owner must verify with the supplier
- Suggested product title, factual description, SEO keywords and image brief
- A go / test-small / reject recommendation

Critical rules:
- News/RSS coverage is NOT sales data, search-volume data, or proof of demand.
- Do not claim a product is trending, viral, best-selling, or high-demand without
  direct evidence. Label weak signals as weak.
- Never invent product specifications, materials, warranty, stock, delivery time,
  supplier reliability, reviews, prices, or profit margins.
- If evidence is insufficient, say so and recommend what to validate.
- Keep the report useful for a human decision. This agent does not list or publish
  anything and does not approve purchases.

Evidence:
{json.dumps(payload, ensure_ascii=False)}
"""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 5000},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
        method="POST",
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 4:
                raise RuntimeError(f"Gemini API error {error.code}: {detail[:1000]}")
            time.sleep(5 * (2 ** attempt))
    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no product assessment.")
    answer = "\n".join(
        p.get("text", "") for p in candidates[0].get("content", {}).get("parts", [])
        if p.get("text")
    ).strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty product assessment.")
    return answer


def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")
    if not PRODUCT and not PRODUCT_URL:
        raise RuntimeError("Provide PRODUCT_NAME or PRODUCT_URL in workflow inputs.")
    page_text = fetch_public_product_page(PRODUCT_URL)
    search_term = PRODUCT or PRODUCT_URL
    signals = fetch_market_signals(search_term)
    evidence = {
        "market": "Pakistan",
        "product_name_as_supplied": PRODUCT or None,
        "product_url_as_supplied": PRODUCT_URL or None,
        "price_as_supplied": PRICE or None,
        "category_as_supplied": CATEGORY or None,
        "owner_notes": NOTES or None,
        "public_page_text_excerpt": page_text or None,
        "public_news_signals": signals,
        "limitations": [
            "No private Markaz account access was used.",
            "No Markaz API or authenticated catalog export was assumed.",
            "News mentions are not sales or search-volume measurements.",
        ],
    }
    report = call_gemini(evidence)
    out = Path("product_research_output")
    out.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    (out / "product_opportunity_latest.md").write_text(
        "# Click and Collect — Product Opportunity Review\n\n"
        f"- Generated (UTC): {timestamp}\n"
        f"- Product: {PRODUCT or 'See supplied URL'}\n"
        f"- Source URL: {PRODUCT_URL or 'Not supplied'}\n"
        "- Status: **RESEARCH ONLY — NOT APPROVED, NOT LISTED**\n\n"
        + report + "\n",
        encoding="utf-8",
    )
    (out / "product_evidence_latest.json").write_text(
        json.dumps({"generated_at_utc": timestamp, "evidence": evidence},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Product opportunity review created. No listing or publishing action was taken.")


if __name__ == "__main__":
    main()
