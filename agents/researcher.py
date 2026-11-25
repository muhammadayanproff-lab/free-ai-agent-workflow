import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
CATALOG = Path(os.getenv("MARKAZ_CATALOG", "catalog/markaz_pakistan_export.csv"))
OUT = Path("product_discovery_output")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ClickCollectProductResearch/2.0)"}

ALIASES = {
    "title": ["title", "name", "product name", "product title"],
    "sku": ["variant sku", "sku", "product sku", "id"],
    "price": ["variant price", "price", "selling price", "markaz price", "regular price"],
    "description": ["body (html)", "description", "product description", "short description"],
    "image": ["image src", "image url", "image", "images", "featured image"],
    "url": ["product url", "url", "link", "handle"],
    "source": ["source", "market", "catalog", "origin"],
    "payment": ["payment", "payment method", "cod", "delivery note"],
    "category": ["type", "category", "product type"],
}

def norm(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()

def pick(row, aliases):
    lookup = {norm(k): (v or "").strip() for k, v in row.items() if k}
    for alias in aliases:
        value = lookup.get(norm(alias), "")
        if value:
            return value
    return ""

def read_markaz_catalog():
    if not CATALOG.exists():
        raise RuntimeError(
            f"Markaz Pakistan export not found: {CATALOG}. Export products from the Markaz Pakistan Shop tab "
            "using Markaz Export to My Store (CSV/Excel), save as catalog/markaz_pakistan_export.csv, "
            "and commit it to this repository. Do not export from Markaz China."
        )
    products = {}
    with CATALOG.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        for row in csv.DictReader(f, dialect=dialect):
            title = pick(row, ALIASES["title"])
            sku = pick(row, ALIASES["sku"])
            price = pick(row, ALIASES["price"])
            desc = pick(row, ALIASES["description"])
            image = pick(row, ALIASES["image"])
            url = pick(row, ALIASES["url"])
            source = pick(row, ALIASES["source"])
            payment = pick(row, ALIASES["payment"])
            category = pick(row, ALIASES["category"])
            if not title or not sku:
                continue
            combined = " ".join([title, desc, url, source, payment]).lower()
            if "/china" in combined or "markaz china" in combined or "advance payment" in combined or "prepaid only" in combined:
                continue
            if not price or not image:
                continue
            key = sku.strip()
            item = products.setdefault(key, {
                "sku": key, "title": title, "price_pkr": price, "description": desc[:3500],
                "category": category, "product_url": url, "source_label": source,
                "payment_note": payment, "images": []
            })
            for raw in re.split(r"[|;\\n]", image):
                raw = raw.strip()
                if raw.startswith("https://") and raw not in item["images"]:
                    item["images"].append(raw)
    if not products:
        raise RuntimeError(
            "No usable Pakistan catalog rows found. CSV must contain product title, SKU, PKR price and image URL. "
            "China/prepaid rows are deliberately excluded."
        )
    return list(products.values())

def fetch_rss(url, source, limit=25):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as res:
        root = ET.fromstring(res.read())
    rows = []
    for item in root.findall(".//item")[:limit]:
        rows.append({
            "source": source,
            "title": item.findtext("title", ""),
            "url": item.findtext("link", ""),
            "published": item.findtext("pubDate", ""),
            "snippet": re.sub(r"<[^>]+>", " ", item.findtext("description", ""))[:500]
        })
    return rows

def collect_public_signals():
    rows, errors = [], []
    sources = [
        ("Google Trends Pakistan", "https://trends.google.com/trending/rss?geo=PK"),
        ("Google News Pakistan ecommerce", "https://news.google.com/rss/search?q=" +
         urllib.parse.quote('Pakistan online shopping products gadgets home problem solving') +
         "&hl=en-PK&gl=PK&ceid=PK:en"),
        ("Google News Pakistan consumer needs", "https://news.google.com/rss/search?q=" +
         urllib.parse.quote('Pakistan household problems kitchen organization personal care gadgets') +
         "&hl=en-PK&gl=PK&ceid=PK:en"),
        ("Google News Pakistan product demand", "https://news.google.com/rss/search?q=" +
         urllib.parse.quote('Pakistan ecommerce trending products retail consumer demand') +
         "&hl=en-PK&gl=PK&ceid=PK:en"),
    ]
    for source, url in sources:
        try:
            data = fetch_rss(url, source, 25)
            rows.extend(data)
            print(f"{source}: {len(data)} public items")
        except Exception as exc:
            errors.append(f"{source}: {exc}")
    unique = {}
    for row in rows:
        key = norm(row["title"])
        if key:
            unique[key] = row
    return list(unique.values()), errors

def gemini_json(catalog, signals, errors):
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    prompt = f"""
You are Click & Collect's Pakistan product opportunity research analyst.
Select ONLY from the supplied Markaz Pakistan Shop export. These products came from
the Pakistan catalog export file, not Markaz China; rows mentioning China/prepaid were
already removed. Do not invent products or facts.

Evaluate each plausible product for:
- clear everyday problem solved and urgency
- broad Pakistan audience and likely buyer persona
- visual demonstration potential for Instagram/Facebook
- price accessibility using only supplied PKR price
- competition and differentiation using public evidence below
- seasonality, fragility, sizing/compatibility, returns and compliance risks
- whether supplied evidence supports a small test

Return STRICT JSON only:
{{
 "shortlist":[{{"sku":"EXACT supplied SKU","score":1-10,"problem_solved":"...","buyer":"...","evidence_summary":"...","risks":["..."],"recommendation":"TEST_SMALL or REJECT","confidence":"high/medium/low"}}],
 "selected_sku":"EXACT SKU or empty string",
 "selection_reason":"...",
 "research_gaps":["..."],
 "market_signals":[{{"claim":"...","source_url":"...","published":"...","strength":"strong/medium/weak"}}]
}}
Rules:
- Score is an opportunity hypothesis, NOT a sales forecast.
- News and Google Trends are not proof of product sales, conversion or monthly units.
- Never claim exact sales estimates, viral status or competitor prices without evidence.
- Only select a product scoring >=7 with a clear problem solved and no critical safety/compliance risk.
- If evidence is weak, set selected_sku to empty and explain why.
- Do not claim product-level COD is verified solely by generic Markaz policy. Mark COD as requiring final product checkout confirmation.
- Use source URLs and publication dates from the evidence; don't fabricate citations.

MARKAZ PAKISTAN CATALOG:
{json.dumps(catalog, ensure_ascii=False)}

PUBLIC PAKISTAN SIGNALS:
{json.dumps(signals, ensure_ascii=False)}

SOURCE COLLECTION ERRORS:
{json.dumps(errors, ensure_ascii=False)}
"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "maxOutputTokens": 7000}
    }
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY}, method="POST")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as res:
                result = json.loads(res.read().decode())
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if exc.code not in (408,429,500,502,503,504) or attempt == 4:
                raise RuntimeError(f"Gemini API HTTP {exc.code}: {detail[:1000]}")
            time.sleep(4 * (2 ** attempt))
    parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
    if not text:
        raise RuntimeError("Gemini returned no product discovery JSON.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned invalid JSON: {text[:1000]}") from exc

def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")
    catalog = read_markaz_catalog()
    signals, errors = collect_public_signals()
    if not signals:
        raise RuntimeError("No public Pakistan market signals were collected; refusing to make an unsupported product pick.")
    result = gemini_json(catalog, signals, errors)
    by_sku = {p["sku"]: p for p in catalog}
    shortlist = result.get("shortlist", [])
    for row in shortlist:
        if row.get("sku") not in by_sku:
            raise RuntimeError("Gemini returned a SKU that is not present in the Markaz export.")
    selected_sku = str(result.get("selected_sku", "")).strip()
    selected = by_sku.get(selected_sku)
    if selected:
        score = next((x.get("score", 0) for x in shortlist if x.get("sku") == selected_sku), 0)
        if not isinstance(score, (int, float)) or score < 7:
            raise RuntimeError("Selected product did not pass the minimum opportunity score.")
        selected = dict(selected)
        selected["research_assessment"] = next(x for x in shortlist if x.get("sku") == selected_sku)
        selected["cod_status"] = "NOT_INDEPENDENTLY_VERIFIED — confirm on the exact Pakistan product checkout before approval"
        selected["catalog_source"] = "User-exported Markaz Pakistan Shop CSV; China/prepaid indicators filtered"
    OUT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    (OUT / "product_discovery_report.json").write_text(json.dumps({
        "generated_at_utc": timestamp, "catalog_file": str(CATALOG),
        "catalog_products_scanned": len(catalog), "public_signal_count": len(signals),
        "selected_product": selected, "analysis": result, "source_errors": errors
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# Pakistan Product Discovery", "", f"Generated (UTC): {timestamp}",
          f"Markaz Pakistan catalog rows scanned: {len(catalog)}",
          f"Public market signals collected: {len(signals)}", ""]
    if selected:
        md += ["## Recommended product for owner verification", "",
               f"- **{selected['title']}**", f"- SKU: {selected['sku']}",
               f"- Markaz export price: PKR {selected['price_pkr']}",
               f"- Opportunity score: {selected['research_assessment'].get('score')}/10",
               f"- Problem solved: {selected['research_assessment'].get('problem_solved')}",
               f"- COD: {selected['cod_status']}", "",
               "### Why it was shortlisted", selected['research_assessment'].get('evidence_summary',''), "",
               "### Risks", *[f"- {x}" for x in selected['research_assessment'].get('risks', [])], ""]
    else:
        md += ["## No product passed the evidence threshold", "", result.get("selection_reason", "No safe candidate selected."), ""]
    md += ["## Shortlist", ""]
    for item in shortlist:
        md += [f"- **{item.get('sku')}** — {item.get('score')}/10 — {item.get('recommendation')} — {item.get('problem_solved')}"]
    md += ["", "## Research gaps", *[f"- {x}" for x in result.get("research_gaps", [])],
           "", "## Source signals"]
    for item in result.get("market_signals", []):
        md += [f"- {item.get('claim')} — {item.get('published')} — {item.get('source_url')} ({item.get('strength')})"]
    md += ["", "## Verification warning", "A Pakistan catalog export is not a live inventory guarantee. Open the exact product in Markaz Pakistan Shop and confirm current stock, price, variant, COD checkout, delivery, returns and supplier terms before approving."]
    (OUT / "product_discovery_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if selected:
        (OUT / "selected_product.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Product discovery finished. Selected candidate:", selected_sku or "NONE")

if __name__ == "__main__":
    main()
