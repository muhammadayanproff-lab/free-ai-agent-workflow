import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = "gemini-3.5-flash-lite"
TOPIC = os.environ.get("CONTENT_TOPIC", "").strip()
AUDIENCE = os.environ.get("TARGET_AUDIENCE", "general audience").strip()
PLATFORM = os.environ.get("CONTENT_PLATFORM", "Instagram, TikTok, YouTube").strip()
KEYWORDS = os.environ.get("TARGET_KEYWORDS", "").strip()


def build_prompt():
    return f"""
You are a careful SEO strategist and social-media copywriter.
Create a useful, original content package for the topic below.

TOPIC:
{TOPIC}

TARGET AUDIENCE:
{AUDIENCE}

PLATFORMS:
{PLATFORM}

USER-PROVIDED KEYWORDS:
{KEYWORDS if KEYWORDS else "No keywords supplied. Suggest relevant phrases."}

Return Markdown with these sections:
1. Search intent and audience need.
2. Primary keyword and 8-12 relevant secondary/long-tail keywords.
3. SEO title (aim for 50-60 characters; do not pad unnaturally).
4. Meta description (aim for 140-160 characters; accurately describe the content).
5. Suggested URL slug.
6. A useful article/post outline with H1, H2 and H3 headings where appropriate.
7. One platform-appropriate caption for each requested platform. Include a strong
   opening hook, useful body copy and a natural call to action.
8. 8-15 relevant hashtags where hashtags suit the platform. Do not use irrelevant
   or repetitive hashtags.
9. Image alt text that describes the likely visual clearly and accessibly.
10. A short factuality and SEO checklist.

Rules:
- Do not invent statistics, research, product features, prices or claims.
- Do not promise rankings, virality or guaranteed traffic.
- Match search intent; avoid keyword stuffing and repetitive wording.
- If the topic is ambiguous, state the assumption briefly.
- Keep the output practical and ready for a human to review.
"""


def call_gemini(prompt):
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.45,
            "maxOutputTokens": 5000
        }
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY
        },
        method="POST"
    )

    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if error.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(
                    f"Gemini API error {error.code}: {details[:1200]}"
                ) from error
            if attempt == 4:
                raise RuntimeError(
                    f"Gemini remained unavailable after 5 attempts "
                    f"(HTTP {error.code}): {details[:500]}"
                ) from error
            wait_seconds = 5 * (2 ** attempt)
            print(f"Gemini temporarily unavailable; retrying in {wait_seconds}s.")
            time.sleep(wait_seconds)

    candidates = result.get("candidates", [])
    if not candidates:
        feedback = result.get("promptFeedback", {})
        raise RuntimeError(
            "Gemini returned no content. "
            + json.dumps(feedback, ensure_ascii=False)[:800]
        )

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "\n".join(
        part.get("text", "") for part in parts if part.get("text")
    ).strip()

    if not text:
        raise RuntimeError("Gemini returned an empty content package.")
    return text


def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")
    if not TOPIC:
        raise RuntimeError(
            "CONTENT_TOPIC is empty. Enter a topic in the workflow form."
        )

    print("Starting SEO & Caption Writer...")
    print(f"Topic: {TOPIC}")
    report = call_gemini(build_prompt())

    os.makedirs("reports", exist_ok=True)
    output_path = "reports/seo_content_latest.md"
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write("# SEO & Caption Writer\n\n")
        output_file.write(
            f"Generated (UTC): {datetime.now(timezone.utc).isoformat()}\n\n"
        )
        output_file.write(f"**Topic:** {TOPIC}\n\n")
        output_file.write(f"**Audience:** {AUDIENCE}\n\n")
        output_file.write(f"**Platforms:** {PLATFORM}\n\n")
        output_file.write("---\n\n")
        output_file.write(report)
        output_file.write("\n")

    if os.path.getsize(output_path) < 300:
        raise RuntimeError("Generated report is unexpectedly short.")

    print("SEO & Caption Writer completed successfully.")
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
