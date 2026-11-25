import json
import os
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

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
    selected_path = Path("product_discovery_output/selected_product.json")
    if not selected_path.is_file():
        raise RuntimeError("Latest successful Product Discovery artifact has no selected product. Run Product Discovery and review its report first.")
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    product_url = str(selected.get("product_url", "")).strip()
    title_override = str(selected.get("title", "")).strip()
    price_override = str(selected.get("price_pkr", "")).strip()
    category = str(selected.get("category", "")).strip()
    image_override = ""
    images_from_listing = selected.get("image_urls", [])
    if images_from_listing:
        image_override = str(images_from_listing[0]).strip()

    parsed = urllib.parse.urlparse(product_url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.markaz.app", "markaz.app"}:
        raise RuntimeError("Selected product URL is not an HTTPS Markaz URL.")
    if not parsed.path.startswith("/shop/product/") or "/china/" in parsed.path.lower():
        raise RuntimeError("Only public Markaz Pakistan Shop product URLs are accepted; China URLs are blocked.")

    request = urllib.request.Request(product_url, headers={"User-Agent": "Mozilla/5.0 (compatible; ClickCollectProductVerifier/1.0)"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            html = response.read(8_000_001).decode("utf-8", errors="replace")
        if len(html) >= 8_000_000:
            raise RuntimeError("Markaz product page exceeded the safety read limit.")
    except Exception as exc:
        if not (title_override and image_override.startswith("https://")):
            raise RuntimeError(f"Could not fetch Markaz product page ({exc}); selected listing did not contain a usable title and image fallback.") from exc
        html = ""

    parser = DetailParser()
    if html:
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
    if not isinstance(offers, dict):
        offers = {}

    images = product.get("image", [])
    if isinstance(images, str):
        images = [images]
    images = [urllib.parse.urljoin(product_url, value) for value in images if isinstance(value, str)]
    images.extend(parser.images)
    if image_override.startswith("https://"):
        images.insert(0, image_override)
    og_image = parser.meta.get("og:image", "")
    if og_image:
        images.insert(0, urllib.parse.urljoin(product_url, og_image))
    unique_images = []
    for image in images:
        if image.startswith("https://") and image not in unique_images:
            unique_images.append(image)

    title = product.get("name") or parser.meta.get("og:title") or parser.meta.get("twitter:title", "") or title_override
    description = product.get("description") or parser.meta.get("description") or parser.meta.get("og:description", "")
    price = price_override or str(offers.get("price") or parser.meta.get("product:price:amount") or "")
    id_match = re.search(r"/(\d+)$", parsed.path)
    product_id = str(product.get("sku") or (id_match.group(1) if id_match else selected.get("product_id", "")))
    variants = []
    for key in ("color", "size", "material", "model"):
        if product.get(key):
            variants.append({key: product[key]})
    text_excerpt = re.sub(r"\s+", " ", " ".join(parser.text))[:12000]
    if not title:
        title = text_excerpt[:180].strip()
    if not unique_images:
        raise RuntimeError("No original Markaz product image could be extracted or recovered from discovery data.")
    if not title:
        raise RuntimeError("No product title could be extracted from the Markaz listing.")

    output = Path("source_product_images")
    output.mkdir(exist_ok=True)
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
            extension = ".png" if "png" in content_type else ".webp" if "webp" in content_type else ".jpg"
            path = output / f"markaz_{index:02d}{extension}"
            path.write_bytes(data)
            saved.append(str(path))
        except Exception as exc:
            print(f"Image download skipped: {url}: {exc}")
    if not saved:
        raise RuntimeError("No original product photos could be downloaded.")

    data = {
        "product_id": product_id,
        "title": title,
        "product_url": product_url,
        "price_pkr": price or "Not extracted — verify current price on Markaz",
        "description": description,
        "category": category,
        "brand": product.get("brand", ""),
        "variants": variants,
        "json_ld_product_data": product,
        "page_text_excerpt": text_excerpt,
        "discovery_assessment": selected.get("research_assessment", {}),
        "image_urls": unique_images[:8],
        "local_image_files": saved,
        "catalog_source": "Public Markaz Pakistan Shop listing and product page",
        "cod_confirmed_by_owner": False,
        "cod_verification_note": "COD was not verified because checkout is not accessible through the public listing. Confirm current COD availability and final price before approving publication.",
    }
    Path("product_data").mkdir(exist_ok=True)
    Path("product_data/product.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared selected Markaz product: {title}; {len(saved)} original photos downloaded.")

if __name__ == "__main__":
    main()
