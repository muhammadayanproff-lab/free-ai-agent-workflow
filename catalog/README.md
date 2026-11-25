# Markaz Pakistan catalogue input

1. Open the Markaz app/site and switch to **Pakistan Shop** (not Markaz China).
2. Favourite the products you want the research agent to evaluate.
3. Use Markaz **Export to My Store** and export Shopify CSV, WooCommerce CSV or Excel.
4. Convert Excel to CSV if needed.
5. Save the export here as `markaz_pakistan_export.csv` and commit it to this repository.
6. Run **Pakistan Product Discovery** in GitHub Actions.

The discovery agent reads product titles, SKUs, prices, descriptions and image URLs from the export. It filters rows that explicitly identify China or prepaid/advance payment. It cannot log into your Markaz account or independently prove live stock/COD for a specific SKU. You must check the exact product's Pakistan Shop listing and checkout before approving it.

Markaz's public Export to My Store instructions say the export includes images, variants, descriptions and reseller prices, supports CSV/Excel, and allows up to 50 products per export. The export tool is the supported way to provide authenticated catalogue data; do not share your Markaz password or session cookies with GitHub.
