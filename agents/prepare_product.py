import json
import os
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

PRODUCT_URL = os.getenv("PRODUCT_URL", "").strip()
COD_CONFIRMED = os.getenv("MARKAZ_COD_CONFIRMED", "").strip().upper() == "YES"
PRICE_OVERRIDE = os.getenv("PRODUCT_PRICE", "").strip()

class DetailParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.images = []
        self.text = []
        self.json_scripts = []
        self.in_json = False
        self.script_data = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name") or attrs.get("itemprop")
            if key and attrs.get("content"):
                self.meta[key.lower()] = attrs["content"].strip()
        elif tag == "img":
            for key in ("src", "data-src", "data-lazy-src"):
                value = attrs.get(key, "")
                if value:
                    url = urllib.parse.urljoin("https://www.markaz.app", value)
                    if url.startswith("https://") and url not in self.images:
                        self.images.append(url)
        elif tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.in_json = True
            self.script_data = []
    def handle_data(self, data):
        if self.in_json:
            self.script_data.append(data)
        elif data.strip():
            self.text.append(data.strip())
    def handle_endtag(self, tag):
        if tag == "script" and self.in_json:
            self.json_scripts.append("".join(self.script_data))
            self.in_json = False
            self.script_data = []

def find_products(value):
    found = []
    if isinstance(value, dict):
        kind = value.get("@type", "")
        if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
            found.append(value)
        for child in value.values():
            found.extend(find_products(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_products(child))
    return found

def main():
    if not COD_CONFIRMED:
        raise RuntimeError("Open this exact product in Markaz Pakistan Shop and confirm COD before continuing.")
    parsed = urllib.parse.urlparse(PRODUCT_URL)
    if parsed.scheme != "https" or parsed.hostname not in {"www.markaz.app", "markaz.app"}:
        raise RuntimeError("PRODUCT_URL must be an HTTPS Markaz public product URL.")
    if not parsed.path.startswith("/shop/product/") or "/china/" in parsed.path.lower():
        raise RuntimeError("Only public Markaz Pakistan Shop product URLs are accepted; China URLs are blocked.")

    request = urllib.request.Request(PRODUCT_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; ClickCollectProductVerifier/1.0)"})
    with urllib.request.urlopen(request, timeout=45) as response:
        html = response.read(8_000_001).decode("utf-8", errors="replace")
    if len(html) >= 8_000_000:
        raise RuntimeError("Markaz product page exceeded the safety read limit.")

    parser = DetailParser()
    parser.feed(html)
    json_products = []
    for raw in parser.json_scripts:
        try:
            json_products.extend(find_products(json.loads(raw)))
        except Exception:
            continue
    product = json_products[0] if json_products else {}
    offers = product.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    images = product.get("image", [])
    if isinstance(images, str):
        images = [images]
    images = [urllib.parse.urljoin(PRODUCT_URL, x) for x in images if isinstance(x, str)]
    images.extend(parser.images)
    og_image = parser.meta.get("og:image", "")
    if og_image:
        images.insert(0, urllib.parse.urljoin(PRODUCT_URL, og_image))
    unique_images = []
    for image in images:
        if image.startswith("https://") and image not in unique_images:
            unique_images.append(image)

    title = product.get("name") or parser.meta.get("og:title") or parser.meta.get("twitter:title", "")
    description = product.get("description") or parser.meta.get("description") or parser.meta.get("og:description", "")
    price = PRICE_OVERRIDE or str(offers.get("price") or parser.meta.get("product:price:amount") or "")
    sku = str(product.get("sku") or re.search(r"/(\d+)$", parsed.path).group(1) if re.search(r"/(\d+)$", parsed.path) else "")
    variants = []
    for key in ("color", "size", "material", "model"):
        if product.get(key):
            variants.append({key: product[key]})
    text_excerpt = re.sub(r"\s+", " ", " ".join(parser.text))[:12000]
    if not title:
        title = text_excerpt[:180].strip()
    if not unique_images:
        raise RuntimeError("Could not extract original supplier images from this Markaz product page.")
    if not title:
        raise RuntimeError("Could not extract product title from the Markaz page.")

    out = Path("source_product_images")
    out.mkdir(exist_ok=True)
    saved = []
    for index, url in enumerate(unique_images[:8], start=1):
        try:
            image_request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(image_request, timeout=35) as response:
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    continue
                data = response.read(12_000_001)
            if len(data) > 12_000_000:
                continue
            ext = ".png" if "png" in content_type else ".webp" if "webp" in content_type else ".jpg"
            path = out / f"markaz_{index:02d}{ext}"
            path.write_bytes(data)
            saved.append(str(path))
        except Exception as exc:
            print(f"Image download skipped: {url}: {exc}")
    if not saved:
        raise RuntimeError("No original product images could be downloaded from Markaz.")

    data = {
        "product_id": sku,
        "title": title,
        "product_url": PRODUCT_URL,
        "price_pkr": price or "Not extracted — confirm on Markaz page",
        "description": description,
        "category": os.getenv("PRODUCT_CATEGORY", ""),
        "brand": product.get("brand", ""),
        "variants": variants,
        "json_ld_product_data": product,
        "page_text_excerpt": text_excerpt,
        "image_urls": unique_images[:8],
        "local_image_files": saved,
        "catalog_source": "Public Markaz Pakistan Shop product page (/shop/product/)",
        "cod_confirmed_by_owner": True,
        "cod_verification_note": "Owner confirmed COD on this exact Pakistan product checkout. Not a live private API check.",
    }
    Path("product_data").mkdir(exist_ok=True)
    Path("product_data/product.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified public Markaz Pakistan listing: {title}; downloaded {len(saved)} original images.")

if __name__ == "__main__":
    main()
