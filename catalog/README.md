# Markaz Pakistan public catalogue

The Product Discovery Agent now reads public Markaz Pakistan Shop category pages directly. A separate CSV export is **not required** for normal product discovery.

The public crawler uses category URLs under `/shop/home-page/` and accepts only product links under `/shop/product/`. It deliberately excludes Markaz China URLs. The campaign workflow then fetches the exact selected product page and downloads its public product images.

Optional: Markaz's Export to My Store can still be used manually when extra supplier/variant details are needed. It exports product images, variants, descriptions and prices as CSV/Excel (up to 50 products per export). Do not share Markaz passwords, cookies or private account credentials with this repository.
