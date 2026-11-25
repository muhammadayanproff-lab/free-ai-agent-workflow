import json,os,time,urllib.parse,urllib.request,urllib.error
API_VERSION=os.getenv("META_GRAPH_API_VERSION","").strip() or "v27.0"
def required(name):
    value=os.getenv(name,"").strip()
    if not value: raise RuntimeError(f"Missing GitHub secret/input: {name}")
    return value
def request_json(req):
    try:
        with urllib.request.urlopen(req,timeout=90) as response: data=json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc: raise RuntimeError(f"Meta API HTTP {exc.code}: {exc.read().decode('utf-8','replace')[:1200]}") from exc
    if isinstance(data,dict) and data.get("error"): raise RuntimeError("Meta API error: "+json.dumps(data["error"])[:1200])
    return data
def post_form(url,data):
    return request_json(urllib.request.Request(url,data=urllib.parse.urlencode(data).encode(),headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST"))
def get_json(url): return request_json(urllib.request.Request(url,method="GET"))
def publish_instagram(ig_id,token,kind,url,caption):
    if not url.startswith("https://"): raise RuntimeError("Instagram media must be public HTTPS.")
    base=f"https://graph.facebook.com/{API_VERSION}"; params={"access_token":token,"caption":caption}
    if kind=="image": params["image_url"]=url
    else: params.update({"media_type":"REELS","video_url":url,"share_to_feed":"true"})
    container=post_form(f"{base}/{ig_id}/media",params); cid=container.get("id")
    if not cid: raise RuntimeError(f"Instagram {kind} container ID missing.")
    for _ in range(36):
        status=get_json(f"{base}/{cid}?fields=status_code&access_token={urllib.parse.quote(token)}").get("status_code")
        if status=="FINISHED": break
        if status=="ERROR": raise RuntimeError(f"Instagram {kind} processing failed.")
        time.sleep(10)
    else: raise RuntimeError(f"Instagram {kind} processing timed out.")
    result=post_form(f"{base}/{ig_id}/media_publish",{"creation_id":cid,"access_token":token})
    if not result.get("id"): raise RuntimeError(f"Instagram {kind} publish returned no media ID.")
    return result["id"]
def publish_facebook(page_id,token,kind,url,caption):
    if not url.startswith("https://"): raise RuntimeError("Facebook media must be public HTTPS.")
    base=f"https://graph.facebook.com/{API_VERSION}/{page_id}"
    if kind=="image": result=post_form(f"{base}/photos",{"caption":caption,"url":url,"access_token":token})
    else: result=post_form(f"{base}/videos",{"description":caption,"file_url":url,"access_token":token})
    post_id=result.get("post_id") or result.get("id")
    if not post_id: raise RuntimeError(f"Facebook {kind} publish returned no post ID.")
    return post_id
def main():
    if required("PUBLISH_APPROVAL")!="APPROVE": raise RuntimeError("Blocked: explicit APPROVE is required.")
    platforms={x.strip().lower() for x in required("TARGET_PLATFORMS").split(",") if x.strip()}
    if not platforms or not platforms.issubset({"instagram","facebook"}): raise RuntimeError("Choose Instagram and/or Facebook only.")
    media={"image":required("IMAGE_URL"),"video":required("VIDEO_URL")}
    captions={
      ("instagram","image"):required("IG_IMAGE_CAPTION"),("facebook","image"):required("FB_IMAGE_CAPTION"),
      ("instagram","video"):required("IG_VIDEO_CAPTION"),("facebook","video"):required("FB_VIDEO_CAPTION")}
    for label,url in media.items():
        if not url.startswith("https://"): raise RuntimeError(f"{label} URL must be public HTTPS.")
    token=required("META_PAGE_ACCESS_TOKEN"); outcomes={}
    for platform in sorted(platforms):
        for kind,url in media.items():
            caption=captions[(platform,kind)]
            if platform=="instagram":
                post_id=publish_instagram(required("META_IG_USER_ID"),token,kind,url,caption)
            else:
                post_id=publish_facebook(required("META_PAGE_ID"),token,kind,url,caption)
            outcomes[f"{platform}_{kind}_post_id"]=post_id
    os.makedirs("publish_output",exist_ok=True)
    Path("publish_output/publish_receipt.json").write_text(json.dumps({"status":"PUBLISHED","platform_results":outcomes,"separate_image_video_posts":True,"platform_specific_captions":True},indent=2)+"\n",encoding="utf-8")
    print("Image and video submitted as separate posts with separate Instagram/Facebook captions.")
    print(json.dumps(outcomes,indent=2))
if __name__=="__main__": main()
