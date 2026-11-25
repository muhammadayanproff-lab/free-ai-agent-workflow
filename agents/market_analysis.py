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
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClickCollectMarketAnalysis/1.0)"}

def rss(url, source, limit=18):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        root = ET.fromstring(response.read())
    return [{"source": source, "title": i.findtext("title", ""),
             "url": i.findtext("link", ""), "published": i.findtext("pubDate", ""),
             "snippet": re.sub(r"<[^>]+>", " ", i.findtext("description", ""))[:450]}
            for i in root.findall(".//item")[:limit]]

def main():
    if not API_KEY: raise RuntimeError("GEMINI_API_KEY is missing.")
    product = json.loads(Path("product_data/product.json").read_text(encoding="utf-8"))
    query = urllib.parse.quote(f'"{product["title"]}" Pakistan')
    sources, errors = [], []
    urls = [
        ("Google Trends Pakistan", "https://trends.google.com/trending/rss?geo=PK"),
        ("Google News product", "https://news.google.com/rss/search?q=" + query + "&hl=en-PK&gl=PK&ceid=PK:en"),
        ("Google News category", "https://news.google.com/rss/search?q=" + urllib.parse.quote((product.get("category") or product["title"]) + " Pakistan shopping demand") + "&hl=en-PK&gl=PK&ceid=PK:en"),
        ("Google News problem use-case", "https://news.google.com/rss/search?q=" + urllib.parse.quote(product["title"] + " uses benefits reviews Pakistan") + "&hl=en-PK&gl=PK&ceid=PK:en"),
    ]
    for label, url in urls:
        try: sources.extend(rss(url, label))
        except Exception as exc: errors.append(f"{label}: {exc}")
    unique = {x["title"].strip().lower(): x for x in sources if x["title"].strip()}
    sources = list(unique.values())
    if not sources: raise RuntimeError("No public trend/news evidence collected; market analysis cannot proceed.")
    prompt = f"""
Act as a skeptical Pakistan ecommerce market analyst for Click & Collect.
Assess this exact Markaz Pakistan product using the supplied catalogue facts and public evidence.

PRODUCT:
{json.dumps({k:v for k,v in product.items() if k not in ("local_image_files","image_urls")}, ensure_ascii=False)}

PUBLIC SIGNALS:
{json.dumps(sources, ensure_ascii=False)}

Return Markdown with:
1. Exact problem solved and who has it in Pakistan.
2. Evidence of demand and source dates/URLs.
3. Competitive landscape and publicly observable creative angles; do not invent competitor prices or sales.
4. What visual demonstrations other sellers could use (clearly label these as creative hypotheses unless source evidence confirms them).
5. Likely purchase objections, return/quality/size/compatibility risks and seasonality.
6. Click & Collect fit: low/medium/high with reasoning.
7. A conservative test recommendation, suggested customer segment and ad hook.
8. What evidence is missing.

Do not provide numerical unit-sales forecasts, guaranteed sales or fabricated social metrics.
Google Trends/news are signals, not order data. Separate verified product facts from inference.
"""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    body = {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.25,"maxOutputTokens":5000}}
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers={"Content-Type":"application/json","x-goog-api-key":API_KEY}, method="POST")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as response: result=json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8","replace")
            if exc.code not in (408,429,500,502,503,504) or attempt==4: raise RuntimeError(f"Gemini market analysis HTTP {exc.code}: {detail[:1000]}")
            time.sleep(5*(2**attempt))
    parts=result.get("candidates",[{}])[0].get("content",{}).get("parts",[])
    report="\n".join(p.get("text","") for p in parts if p.get("text")).strip()
    if not report: raise RuntimeError("Gemini returned an empty market analysis.")
    Path("market_analysis").mkdir(exist_ok=True)
    Path("market_analysis/market_analysis.md").write_text("# Pakistan Market & Trend Analysis\n\n"+report+"\n",encoding="utf-8")
    Path("market_analysis/public_evidence.json").write_text(json.dumps({"sources":sources,"errors":errors},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Market analysis completed with {len(sources)} public source items.")

if __name__=="__main__": main()
