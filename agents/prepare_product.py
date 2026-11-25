import csv
import json
import os
import re
import urllib.request
from pathlib import Path

CATALOG = Path(os.getenv("MARKAZ_CATALOG", "catalog/markaz_pakistan_export.csv"))
SKU = os.getenv("PRODUCT_SKU", "").strip()
COD_CONFIRMED = os.getenv("MARKAZ_COD_CONFIRMED", "").strip().upper() == "YES"

ALIASES = {
    "title": ["title", "name", "product name", "product title"],
    "sku": ["variant sku", "sku", "product sku", "id"],
    "price": ["variant price", "price", "selling price", "markaz price", "regular price"],
    "description": ["body (html)", "description", "product description", "short description"],
    "image": ["image src", "image url", "image", "images", "featured image"],
    "url": ["product url", "url", "link"],
    "handle": ["handle"],
    "source": ["source", "market", "catalog", "origin"],
    "payment": ["payment", "payment method", "cod", "delivery note"],
    "category": ["type", "category", "product type"],
}

def norm(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()

def pick(row, aliases):
    data = {norm(k): (v or "").strip() for k, v in row.items() if k}
    return next((data.get(norm(a), "") for a in aliases if data.get(norm(a), "")), "")

def main():
    if not SKU:
        raise RuntimeError("PRODUCT_SKU input is required.")
    if not COD_CONFIRMED:
        raise RuntimeError("Before continuing, open this exact SKU in Markaz Pakistan Shop and confirm the COD option. Set MARKAZ_COD_CONFIRMED=YES only after checking.")
    if not CATALOG.exists():
        raise RuntimeError(f"Missing {CATALOG}. Add your Markaz Pakistan Shop CSV export first.")
    found = None
    with CATALOG.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096); f.seek(0)
        try: dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error: dialect = csv.excel
        for row in csv.DictReader(f, dialect=dialect):
            if pick(row, ALIASES["sku"]) == SKU:
                found = {
                    "sku": SKU, "title": pick(row, ALIASES["title"]),
                    "price_pkr": pick(row, ALIASES["price"]),
                    "description": pick(row, ALIASES["description"]),
                    "category": pick(row, ALIASES["category"]),
                    "product_url": pick(row, ALIASES["url"]),
                    "handle": pick(row, ALIASES["handle"]),
                    "source_label": pick(row, ALIASES["source"]),
                    "payment_note": pick(row, ALIASES["payment"]),
                    "image_urls": []
                }
                for value in re.split(r"[|;\n]", pick(row, ALIASES["image"])):
                    value = value.strip()
                    if value.startswith("https://") and value not in found["image_urls"]:
                        found["image_urls"].append(value)
                break
    if not found:
        raise RuntimeError(f"SKU {SKU} was not found in the Markaz Pakistan export.")
    combined = " ".join([found["title"], found["description"], found["product_url"], found["source_label"], found["payment_note"]]).lower()
    if any(term in combined for term in ("/china", "markaz china", "advance payment", "prepaid only")):
        raise RuntimeError("This SKU appears to be China/prepaid. China products are excluded from this Pakistan COD workflow.")
    if not found["title"] or not found["price_pkr"] or not found["image_urls"]:
        raise RuntimeError("The selected CSV row must include title, PKR price and at least one HTTPS product image.")
    out = Path("source_product_images"); out.mkdir(exist_ok=True)
    saved = []
    for index, url in enumerate(found["image_urls"][:8], start=1):
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=40) as response:
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                continue
            data = response.read(12_000_001)
        if len(data) > 12_000_000:
            continue
        ext = ".png" if "png" in content_type else ".webp" if "webp" in content_type else ".jpg"
        path = out / f"markaz_{index:02d}{ext}"
        path.write_bytes(data); saved.append(str(path))
    if not saved:
        raise RuntimeError("Could not download any valid Markaz product images.")
    found["local_image_files"] = saved
    found["markaz_source"] = "Pakistan Shop export supplied by store owner"
    found["cod_confirmed_by_owner"] = True
    found["verification_note"] = "Owner confirmed COD on the exact product's Pakistan checkout. This is not a live API verification."
    Path("product_data").mkdir(exist_ok=True)
    Path("product_data/product.json").write_text(json.dumps(found, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {found['title']} ({SKU}) with {len(saved)} original product images.")

if __name__ == "__main__":
    main()
