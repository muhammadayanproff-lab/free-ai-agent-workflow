"""Optional Groq fallback for campaign agents.

Uses Groq's OpenAI-compatible API and only models currently exposed by the
configured account. Vision calls are restricted to catalogue models whose IDs
indicate image-capable Llama 4 Scout/Vision support.
"""
import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.groq.com/openai/v1"


def _models(headers):
    request = urllib.request.Request(API_URL + "/models", headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [
        item.get("id", "") for item in payload.get("data", [])
        if item.get("id") and item.get("active", True)
    ]


def groq_chat(prompt, max_tokens=5000, json_mode=False, image_paths=None):
    """Return Groq text, or parsed JSON when json_mode=True; None if unavailable."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        print("Groq fallback skipped: GROQ_API_KEY is not configured.")
        return None
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    vision_paths = [Path(p) for p in (image_paths or [])]
    available = []
    try:
        available = _models(headers)
    except Exception as exc:
        print(f"Groq model catalogue unavailable ({exc}); trying known compatible model IDs directly.")

    if vision_paths:
        candidates = [
            name for name in available
            if ("scout" in name.lower() or "vision" in name.lower())
            and ("llama-4" in name.lower() or "llama4" in name.lower())
        ][:3]
        if not candidates and not available:
            candidates = ["meta-llama/llama-4-scout-17b-16e-instruct"]
        if not candidates:
            print("Groq fallback has no active image-capable Llama vision model for this account.")
            return None
    else:
        preferred = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
        candidates = (list(dict.fromkeys([m for m in preferred if m in available] + available)) if available else preferred)[:5]

    errors = []
    for model in candidates:
        content = [{"type": "text", "text": prompt}]
        if vision_paths:
            for path in vision_paths:
                mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                })
        body = {
            "model": model,
            "messages": [{"role": "user", "content": content if vision_paths else prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            API_URL + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
            answer = result["choices"][0]["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Groq returned an empty response")
            print(f"Groq fallback succeeded with model: {model}")
            return json.loads(answer) if json_mode else answer.strip()
        except (urllib.error.HTTPError, TimeoutError, OSError, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
            detail = exc
            if isinstance(exc, urllib.error.HTTPError):
                detail = f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:350]}"
            errors.append(f"{model}: {detail}")
            print(f"Groq model {model} failed; trying another available model: {detail}")
    print("All Groq fallback models failed: " + " | ".join(errors))
    return None
