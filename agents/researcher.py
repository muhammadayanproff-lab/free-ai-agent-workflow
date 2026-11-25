import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
BASE = "https://www.markaz.app"
OUT = Path("product_discovery_output")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClickCollectPakistanResearch/2.0)"}
CATEGORIES = [
    "Kitchenware", "Electronics", "Personal Care Appliances",
    "Storage & Cleaning", "Sports & Outdoor", "Car & Bike Accessories",
    "Office & Stationery", "Toys", "Kids Clothing", "Home & Living",
]
MAX_PAGES = int(os.getenv("MARKAZ_MAX_PAGES_PER_CATEGORY", "2"))
MAX_PRODUCTS_PER_PAGE = 12

class ListingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.depth = 0
        self.items = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get("href", "")
        absolute_href = urllib.parse.urljoin(BASE, href)
        path = urllib.parse.urlparse(absolute_href).path
        if tag == "a" and path.startswith("/shop/product/") and "/china/" not in path.lower():
            if self.current is None:
                self.current = {"url": absolute_href, "text": "", "images": []}
                self.depth = 1
            else:
                self.depth += 1
        elif self.current is not None and tag == "img":
            src = attrs.get("src") or attrs.get("data-src") or attrs.get("data-lazy-src") or ""
            src = urllib.parse.urljoin(BASE, src)
            if src.startswith("https://") and src not in self.current["images"]:
                self.current["images"].append(src)
            alt = attrs.get("alt", "")
            if alt:
                self.current["text"] += " " + alt
    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += " " + data
    def handle_endtag(self, tag):
        if self.current is not None and tag == "a":
            self.depth -= 1
            if self.depth <= 0:
                self.items.append(self.current)
                self.current = None
                self.depth = 0

def get_html(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=35) as response:
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            raise RuntimeError(f"Expected HTML from {url}, got {content_type}")
        return response.read(5_000_001).decode("utf-8", errors="replace")

def parse_products(html, category):
    parser = ListingParser()
    parser.feed(html)
    products = []
    for item in parser.items:
        text = re.sub(r"\s+", " ", item["text"]).strip()
        price = re.search(r"PKR\s*([\d,]+)", text, re.I)
        product_id = re.search(r"/(\d+)(?:[/?#]|$)", item["url"])
        if not price or not product_id:
            continue
        title = text[:price.start()].strip()
        title = re.sub(r"^(?:Top pick|Only\s+\d+\s+left)\s*", "", title, flags=re.I)
        title = re.sub(r"\s+", " ", title).strip(" -|")
        if len(title) < 4:
            title = text.split("PKR", 1)[0].strip()
        if re.search(r"cross[- ]?border|prepaid|ship(?:ping)? from china|china catalogue", title, re.I):
            continue
        stock = re.search(r"Only\s+(\d+)\s+left", text, re.I)
        rating = re.search(r"\b([1-5]\.\d)\b", text[price.end():])
        products.append({
            "product_id": product_id.group(1),
            "title": title[:240],
            "price_pkr": price.group(1).replace(",", ""),
            "product_url": item["url"],
            "image_urls": item["images"][:5],
            "category": category,
            "stock_label": f"Only {stock.group(1)} left" if stock else "Not shown on listing card",
            "rating_label": rating.group(1) if rating else "Not shown on listing card",
            "catalog_source": "Public Markaz Pakistan Shop category listing",
            "cod_policy_source": "Pakistan Shop category pages state COD availability; exact product checkout still needs owner confirmation",
        })
    return products

def crawl_markaz_shop():
    products, errors = {}, []
    for category in CATEGORIES:
        slug = urllib.parse.quote(category, safe="")
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}/shop/home-page/{slug}"
            if page > 1:
                url += "?" + urllib.parse.urlencode({"page": page})
            try:
                html = get_html(url)
                page_items = parse_products(html, category)
                for item in page_items[:MAX_PRODUCTS_PER_PAGE]:
                    products[item["product_url"]] = item
                print(f"Markaz Pakistan / {category} page {page}: {len(page_items)} product cards")
                if not page_items:
                    break
            except Exception as exc:
                errors.append(f"{category} page {page}: {exc}")
                if page == 1:
                    break
            time.sleep(0.25)
    result = list(products.values())
    if not result:
        raise RuntimeError("Could not read any public Markaz Pakistan Shop product listings. No China catalog URLs were used.")
    return result, errors

def fetch_rss(url, source, limit=20):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    return [{
        "source": source, "title": item.findtext("title", ""),
        "url": item.findtext("link", ""), "published": item.findtext("pubDate", ""),
        "snippet": re.sub(r"<[^>]+>", " ", item.findtext("description", ""))[:450]
    } for item in root.findall(".//item")[:limit]]

def collect_rss_signals():
    rows, errors = [], []
    queries = [
        ("Google Trends Pakistan", "https://trends.google.com/trending/rss?geo=PK"),
        ("Pakistan ecommerce news", "https://news.google.com/rss/search?q=" + urllib.parse.quote("Pakistan online shopping products gadgets home") + "&hl=en-PK&gl=PK&ceid=PK:en"),
        ("Pakistan consumer problems", "https://news.google.com/rss/search?q=" + urllib.parse.quote("Pakistan household kitchen cleaning personal care everyday problems") + "&hl=en-PK&gl=PK&ceid=PK:en"),
        ("Pakistan retail demand", "https://news.google.com/rss/search?q=" + urllib.parse.quote("Pakistan ecommerce retail consumer demand products") + "&hl=en-PK&gl=PK&ceid=PK:en"),
    ]
    for label, url in queries:
        try:
            rows.extend(fetch_rss(url, label))
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    unique = {re.sub(r"\W+", " ", x["title"].lower()).strip(): x for x in rows if x["title"].strip()}
    return list(unique.values()), errors

def grounded_web_research(products):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    grouped = {}
    for product in products:
        grouped.setdefault(product["category"], []).append(product)
    search_sample = [item for category_items in grouped.values() for item in category_items[:12]][:120]
    prompt = f"""
Use Google Search to research the Pakistan market for these products actually listed in Markaz Pakistan Shop.
Focus on product demand signals, Pakistani customer problems/use cases, competitor products, public ads/videos/reels,
common price bands, reviews/complaints, and whether these are easy to demonstrate visually.
Prefer Pakistan sources, Pakistani retailers, local marketplaces, public social posts/videos and recent pages.
Do not invent sales, order counts, ad spend, ROAS, or viral metrics. State when results are not available.
Return a concise research memo with source titles, URLs and dates. Separate facts from hypotheses.
PRODUCT CANDIDATES:
{json.dumps([{"id":p["product_id"],"title":p["title"],"price_pkr":p["price_pkr"],"category":p["category"],"url":p["product_url"]} for p in search_sample],ensure_ascii=False)}
"""
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 7000}}
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY}, method="POST")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode())
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            if error.code not in (408,429,500,502,503,504) or attempt == 3:
                raise RuntimeError(f"Gemini Google Search grounding failed ({error.code}): {detail[:1000]}")
            time.sleep(5 * (2 ** attempt))
    candidate = result.get("candidates", [{}])[0]
    memo = "\n".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []) if p.get("text")).strip()
    metadata = candidate.get("groundingMetadata", {})
    sources = []
    for chunk in metadata.get("groundingChunks", []):
        web = chunk.get("web", {})
        if web.get("uri"):
            sources.append({"title": web.get("title", ""), "url": web["uri"]})
    if not memo:
        raise RuntimeError("Google Search grounding returned no research memo.")
    return memo, sources

def gemini_select(products, rss_signals, rss_errors, web_memo, web_sources):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    prompt = f"""
You are the product opportunity analyst for Click & Collect, a Pakistan online store.
Choose only among the exact products in the live public Markaz Pakistan Shop catalogue below.
All candidates come from /shop/product/ pages linked from Markaz Pakistan Shop category pages.
Never select a URL containing /china/.

Rank products for problem-solving value, urgent everyday use, broad Pakistani audience,
easy visual demonstration, accessible listed PKR price, low return/quality/compliance risk,
and evidence of interest in Pakistan. Prefer products that solve a specific problem over
generic fashion or novelty items.

Return STRICT JSON only:
{{
 "shortlist":[{{"product_id":"EXACT id","score":1-10,"problem_solved":"...","buyer":"...","evidence_summary":"...","creative_angle":"...","risks":["..."],"recommendation":"TEST_SMALL or REJECT","confidence":"high/medium/low"}}],
 "selected_product_id":"EXACT id or empty",
 "selection_reason":"...",
 "research_gaps":["..."],
 "market_signals":[{{"claim":"...","source_url":"...","published":"...","strength":"strong/medium/weak"}}]
}}
Rules:
- Opportunity score is a hypothesis, not sales data.
- Never invent monthly sales, conversion, views, competitor prices, review counts or virality.
- Only select score >=7, with clear problem solved and no critical safety/compliance concern.
- If evidence is weak, leave selected_product_id empty.
- Do not claim COD is verified at product checkout. Markaz Pakistan category pages state COD, but owner must check exact item.
- Cite only URLs from the supplied web memo or RSS sources.
- Mention if competitor ad/reel evidence is sparse.

LIVE MARKAZ PAKISTAN CATALOGUE:
{json.dumps(products[:250],ensure_ascii=False)}

GOOGLE SEARCH RESEARCH MEMO:
{web_memo}

GOOGLE SEARCH SOURCES:
{json.dumps(web_sources,ensure_ascii=False)}

GOOGLE TRENDS / NEWS RSS:
{json.dumps(rss_signals,ensure_ascii=False)}

RSS COLLECTION ERRORS:
{json.dumps(rss_errors,ensure_ascii=False)}
"""
    # Keep the request compact: the full catalogue can otherwise make Gemini
    # take too long to start returning response headers.
    compact_products = [
        {key: p.get(key, "") for key in ("product_id", "title", "price_pkr", "category", "product_url")}
        for p in products[:100]
    ]
    prompt = prompt.replace(
        json.dumps(products[:250], ensure_ascii=False),
        json.dumps(compact_products, ensure_ascii=False)
    )
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "maxOutputTokens": 5000}}
    payload = json.dumps(body).encode("utf-8")
    result = None
    errors = []
    # Switch away from an overloaded primary quickly instead of waiting 17 minutes.
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
    tertiary_model = os.getenv("GEMINI_TERTIARY_MODEL", "gemini-3.1-flash-lite")
    model_candidates = list(dict.fromkeys([MODEL, fallback_model, tertiary_model]))
    for model_index, model_name in enumerate(model_candidates):
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        for attempt in range(2):
            request = urllib.request.Request(
                endpoint, data=payload,
                headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
                method="POST"
            )
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    result = json.loads(response.read().decode("utf-8"))
                print(f"Gemini product selection succeeded with model: {model_name}")
                break
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", "replace")
                errors.append(f"{model_name} HTTP {error.code}: {detail[:500]}")
                if error.code not in (408, 429, 500, 502, 503, 504):
                    raise RuntimeError(f"Gemini product selection failed ({error.code}): {detail[:1000]}") from error
                if model_index < len(model_candidates) - 1:
                    print(f"Gemini {model_name} returned HTTP {error.code}; switching to next fallback model.")
                    break
                if attempt == 0:
                    print(f"Fallback model {model_name} returned HTTP {error.code}; retrying once in 10 seconds.")
                    time.sleep(10)
            except (TimeoutError, socket.timeout, urllib.error.URLError) as error:
                errors.append(f"{model_name} network/timeout error: {error}")
                if model_index < len(model_candidates) - 1:
                    print(f"Gemini {model_name} timed out; switching to next fallback model.")
                    break
                if attempt == 0:
                    time.sleep(10)
        if result is not None:
            break
    if result is None:
        raise RuntimeError(
            "Gemini product selection failed on primary and fallback models. "
            "Stopped after bounded retries to avoid wasting runner time. Details: "
            + " | ".join(errors)
        )
    text = "\n".join(p.get("text", "") for p in result.get("candidates", [{}])[0].get("content", {}).get("parts", []) if p.get("text")).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned invalid product selection JSON: {text[:1200]}") from exc

def preflight_gemini_model():
    """Check Gemini availability before spending time crawling the catalogue."""
    global MODEL
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
    tertiary_model = os.getenv("GEMINI_TERTIARY_MODEL", "gemini-3.1-flash-lite")
    candidates = list(dict.fromkeys([MODEL, fallback_model, tertiary_model]))
    errors = []
    for model_name in candidates:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        body = {
            "contents": [{"parts": [{"text": "Reply with the single word OK."}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 8}
        }
        request = urllib.request.Request(
            endpoint, data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
            method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.loads(response.read().decode("utf-8"))
            if not result.get("candidates"):
                raise RuntimeError(f"Gemini preflight on {model_name} returned no candidate response.")
            MODEL = model_name
            print(f"Gemini preflight passed. This run will use {MODEL}.")
            return
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            errors.append(f"{model_name} HTTP {error.code}: {detail[:400]}")
            if error.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(f"Gemini preflight failed ({error.code}) for {model_name}: {detail[:800]}") from error
            print(f"Gemini preflight: {model_name} unavailable (HTTP {error.code}).")
        except (TimeoutError, socket.timeout, urllib.error.URLError) as error:
            errors.append(f"{model_name} network/timeout: {error}")
            print(f"Gemini preflight: {model_name} unavailable ({error}).")
    raise RuntimeError(
        "Gemini preflight failed for primary and fallback models. "
        "Stopped before Markaz crawling to avoid wasting runner time. "
        + " | ".join(errors)
    )


def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")
    preflight_gemini_model()
    products, crawl_errors = crawl_markaz_shop()
    rss_signals, rss_errors = collect_rss_signals()
    try:
        web_memo, web_sources = grounded_web_research(products)
    except Exception as exc:
        web_memo, web_sources = "Google Search grounding unavailable during this run; rely only on the RSS signals below and treat evidence as limited.", []
        rss_errors.append(f"Google Search grounding: {exc}")
    if not rss_signals and not web_sources:
        raise RuntimeError("No Pakistan market research signals were collected.")
    analysis = gemini_select(products, rss_signals, rss_errors + crawl_errors, web_memo, web_sources)
    by_id = {p["product_id"]: p for p in products}
    for item in analysis.get("shortlist", []):
        if str(item.get("product_id")) not in by_id:
            raise RuntimeError("Gemini returned a product ID not found in the Markaz Pakistan catalogue crawl.")
    selected_id = str(analysis.get("selected_product_id", "")).strip()
    selected = by_id.get(selected_id)
    if selected:
        score = next((x.get("score", 0) for x in analysis.get("shortlist", []) if str(x.get("product_id")) == selected_id), 0)
        if not isinstance(score, (int, float)) or score < 7:
            raise RuntimeError("Selected product did not meet the minimum evidence score.")
        selected = dict(selected)
        selected["research_assessment"] = next(x for x in analysis.get("shortlist", []) if str(x.get("product_id")) == selected_id)
        selected["cod_status"] = "Pakistan Shop category policy states COD; exact product checkout must be confirmed by owner"
    OUT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {"generated_at_utc": timestamp, "markaz_products_scanned": len(products),
               "selected_product": selected, "analysis": analysis,
               "google_search_memo": web_memo, "google_search_sources": web_sources,
               "rss_signals": rss_signals, "collection_errors": crawl_errors + rss_errors}
    (OUT / "product_discovery_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Pakistan Product Discovery", "", f"Generated (UTC): {timestamp}",
             f"Markaz Pakistan public products scanned: {len(products)}", ""]
    if selected:
        a = selected["research_assessment"]
        lines += ["## Recommended product — verify exact COD before campaign", "",
                  f"- **{selected['title']}**", f"- Markaz product ID: {selected['product_id']}",
                  f"- Listed price: PKR {selected['price_pkr']}", f"- Category: {selected['category']}",
                  f"- Product page: {selected['product_url']}", f"- Main product image: {(selected.get('image_urls') or ['Not shown'])[0]}", f"- Opportunity score: {a.get('score')}/10",
                  f"- Problem solved: {a.get('problem_solved')}", f"- Buyer: {a.get('buyer')}",
                  f"- Creative angle: {a.get('creative_angle')}", f"- COD status: {selected['cod_status']}", "",
                  "### Evidence", a.get("evidence_summary", ""), "",
                  "### Risks", *[f"- {x}" for x in a.get("risks", [])], ""]
    else:
        lines += ["## No product passed the evidence threshold", "", analysis.get("selection_reason", "No candidate selected."), ""]
    lines += ["## Shortlist", ""]
    for item in analysis.get("shortlist", []):
        p = by_id[str(item.get("product_id"))]
        lines.append(f"- **{p['title']}** — ID {p['product_id']} — {item.get('score')}/10 — {item.get('problem_solved')}")
    lines += ["", "## Grounded web research", web_memo, "", "## Source links"]
    for source in web_sources:
        lines.append(f"- {source.get('title')}: {source.get('url')}")
    lines += ["", "## Research gaps", *[f"- {x}" for x in analysis.get("research_gaps", [])],
              "", "## Verification warning", "Markaz listing pages are a public snapshot. Before campaign generation, open the exact product in Pakistan Shop and confirm current stock, variant, price and COD at checkout. China catalogue pages are excluded."]
    (OUT / "product_discovery_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if selected:
        (OUT / "selected_product.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scanned {len(products)} Markaz Pakistan products. Selected: {selected_id or 'NONE'}")

if __name__ == "__main__":
    main()
