import json
import os
import urllib.parse
import urllib.request
import urllib.error

version = os.getenv("META_GRAPH_API_VERSION", "").strip() or "v27.0"
token = os.environ["META_PAGE_ACCESS_TOKEN"].strip()
page_id = os.environ["META_PAGE_ID"].strip()
ig_id = os.environ["META_IG_USER_ID"].strip()

def get(path, fields):
    query = urllib.parse.urlencode({"fields": fields, "access_token": token})
    url = f"https://graph.facebook.com/{version}/{path}?{query}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Meta API validation failed (HTTP {exc.code}): {detail[:1200]}") from exc

page = get(page_id, "id,name,instagram_business_account")
if str(page.get("id")) != page_id:
    raise RuntimeError("Meta returned a different Page ID.")
ig = get(ig_id, "id,username,account_type")
if str(ig.get("id")) != ig_id:
    raise RuntimeError("Meta returned a different Instagram account ID.")

linked = page.get("instagram_business_account", {})
if linked and str(linked.get("id")) != ig_id:
    raise RuntimeError("The Instagram account linked to this Page does not match META_IG_USER_ID.")

print("META_CREDENTIALS_VALID")
print("Facebook Page:", page.get("name", "(name not returned)"))
print("Page ID verified:", page_id)
print("Instagram account ID verified:", ig_id)
print("Instagram username:", ig.get("username", "(not returned)"))
print("No posts were created or published.")
