import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClickCollectMarketAnalysis/2.0)"}

def rss(url, source, limit=18):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    return [{
        "source": source, "title": item.findtext("title", ""),
        "url": item.findtext("link", ""), "published": item.findtext("pubDate", ""),
        "snippet": re.sub(r"<[^>]+>", " ", item.findtext("description", ""))[:450]
    } for item in root.findall(".//item")[:limit]]

def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing.")
    product = json.loads(Path("product_data/product.json").read_text(encoding="utf-8"))
    query = urllib.parse.quote(f'"{product["title"]}" Pakistan')
    rss_sources, errors = [], []
    queries = [
        ("Google Trends Pakistan", "https://trends.google.com/trending/rss?geo=PK"),
        ("Google News product", "https://news.google.com/rss/search?q=" + query + "&hl=en-PK&gl=PK&ceid=PK:en"),
        ("Google News category", "https://news.google.com/rss/search?q=" + urllib.parse.quote((product.get("category") or product["title"]) + " Pakistan shopping demand") + "&hl=en-PK&gl=PK&ceid=PK:en"),
        ("Google News product reviews", "https://news.google.com/rss/search?q=" + urllib.parse.quote(product["title"] + " reviews complaints Pakistan") + "&hl=en-PK&gl=PK&ceid=PK:en"),
    ]
    for label, url in queries:
        try:
            rss_sources.extend(rss(url, label))
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    rss_sources = list({x["title"].strip().lower(): x for x in rss_sources if x["title"].strip()}.values())

    prompt = f"""
You are a skeptical Pakistan ecommerce market analyst for Click & Collect.
Use Google Search to research this exact Markaz Pakistan Shop product.
Search Pakistan retailers/marketplaces, public customer reviews and complaints, product alternatives,
publicly indexed Instagram/Facebook/TikTok/YouTube ads or product videos, and Pakistani customer use cases.
Prefer recent Pakistan sources. Do not claim access to private social analytics or ad accounts.

PRODUCT FACTS:
{json.dumps({k:v for k,v in product.items() if k not in ("local_image_files","image_urls")}, ensure_ascii=False)}

GOOGLE TRENDS / NEWS RSS:
{json.dumps(rss_sources, ensure_ascii=False)}

Return a practical Markdown report:
1. Exact problem solved and Pakistani buyer personas.
2. Demand signals with dates and URLs; separate evidence from inference.
3. Competitor products and visible pricing only where sourced.
4. Public examples of how sellers demonstrate/promote similar products (image/video concepts, hooks, formats); cite URLs.
5. Customer objections, review themes and complaints where evidence exists.
6. Product quality, sizing/compatibility, return, safety and compliance risks.
7. Click & Collect fit and qualitative sales potential: LOW / MEDIUM / HIGH with assumptions.
8. Suggested first small test, audience, hook and creative angle.
9. Missing evidence.

Never invent sales volumes, ROAS, views, ad spend, competitor prices or review counts.
Do not give exact sales forecasts without actual store/ad data. Google Trends/news are signals, not orders.
"""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}],
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 6500},
    }
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY}, method="POST")
    result = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == 4:
                errors.append(f"Gemini grounded search: HTTP {exc.code}: {detail[:700]}")
                break
            time.sleep(5 * (2 ** attempt))
    report = ""
    grounded_sources = []
    if result:
        candidate = result.get("candidates", [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])
        report = "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
        grounding = candidate.get("groundingMetadata", {})
        for chunk in grounding.get("groundingChunks", []):
            web = chunk.get("web", {})
            if web.get("uri"):
                grounded_sources.append({"title": web.get("title", ""), "url": web["uri"]})
    if not report:
        if not rss_sources:
            raise RuntimeError("Neither Google Search grounding nor Pakistan RSS sources returned research.")
        report = (
            "## Grounded web search unavailable\n\n"
            "Google Search grounding could not be used during this run. The RSS evidence below is limited; "
            "do not treat it as complete competitor or demand research.\n"
        )
    Path("market_analysis").mkdir(exist_ok=True)
    Path("market_analysis/market_analysis.md").write_text("# Pakistan Market & Trend Analysis\n\n" + report + "\n", encoding="utf-8")
    evidence = {"rss_sources": rss_sources, "grounded_search_sources": grounded_sources, "collection_errors": errors}
    Path("market_analysis/public_evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Market analysis completed: {len(rss_sources)} RSS items and {len(grounded_sources)} grounded web sources.")

if __name__ == "__main__":
    main()
