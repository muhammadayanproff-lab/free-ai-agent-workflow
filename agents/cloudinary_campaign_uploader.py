import hashlib
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

def upload(path, cloud, key, secret):
    timestamp=str(int(time.time()))
    folder="click-and-collect/campaign-assets"
    params={"folder":folder,"timestamp":timestamp}
    signature=hashlib.sha1(("&".join(f"{k}={params[k]}" for k in sorted(params))+secret).encode()).hexdigest()
    boundary="----ClickCollect"+uuid.uuid4().hex
    fields={"api_key":key,"timestamp":timestamp,"folder":folder,"signature":signature}
    body=bytearray()
    for name,value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    content=path.read_bytes()
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode())
    body.extend(content); body.extend(f"\r\n--{boundary}--\r\n".encode())
    url=f"https://api.cloudinary.com/v1_1/{cloud}/image/upload"
    req=urllib.request.Request(url,data=bytes(body),headers={"Content-Type":f"multipart/form-data; boundary={boundary}"},method="POST")
    with urllib.request.urlopen(req,timeout=180) as res: result=json.loads(res.read().decode())
    secure=result.get("secure_url")
    if not secure or not secure.startswith("https://"): raise RuntimeError("Cloudinary did not return a public HTTPS image URL.")
    return secure

def main():
    cloud=os.environ.get("CLOUDINARY_CLOUD_NAME","").strip()
    key=os.environ.get("CLOUDINARY_API_KEY","").strip()
    secret=os.environ.get("CLOUDINARY_API_SECRET","").strip()
    if not all((cloud,key,secret)): raise RuntimeError("Cloudinary secrets are missing.")
    files=sorted(Path("generated_images").glob("concept_*"))
    if not files: raise RuntimeError("No generated concept images found.")
    result=[]
    for p in files:
        result.append({"file":str(p),"url":upload(p,cloud,key,secret)})
    Path("campaign_media_urls.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Uploaded {len(result)} campaign images to Cloudinary.")

if __name__=="__main__": main()
