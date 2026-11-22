import os
import json
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-3.5-flash-lite"

NICHES = [
    x.strip()
    for x in os.getenv(
        "NICHES",
        "AI technology, social media trends, content creation"
    ).split(",")
    if x.strip()
]


def fetch_news(niche):
    query = urllib.parse.quote(niche)

    url = (
        "https://news.google.com/rss/search?q="
        + query
        + "&hl=en-US&gl=US&ceid=US:en"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    articles = []

    for item in root.findall(".//item")[:8]:
        articles.append({
            "title": item.findtext("title", ""),
            "link": item.findtext("link", ""),
            "published": item.findtext("pubDate", ""),
            "description": item.findtext("description", "")
        })

    return articles


def ask_gemini(research):
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )

    prompt = f"""
You are an expert content research agent.

Analyse these recent public news articles.

For each niche:
1. Identify interesting emerging topics.
2. Suggest 5 original social media content ideas.
3. Explain why each topic may interest an audience.
4. Suggest suitable content formats.
5. Separate verified facts from speculation.
6. Include source URLs.
7. Never claim something is viral without evidence.

Research data:
{json.dumps(research, ensure_ascii=False)}

Return a clear, useful report in Markdown.
"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 4096
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
            with urllib.request.urlopen(
                request, timeout=120
            ) as response:
                result = json.loads(response.read())

            break

        except urllib.error.HTTPError as error:
            if error.code not in (408, 429, 500, 502, 503, 504):
                details = error.read().decode(
                    "utf-8", errors="replace"
                )
                raise RuntimeError(
                    f"Gemini API error {error.code}: {details[:1000]}"
                )

            if attempt == 4:
                raise RuntimeError(
                    "Gemini remained unavailable after 5 attempts. "
                    "Please try again later."
                )

            wait = 5 * (2 ** attempt)
            print(
                f"Gemini temporarily unavailable. "
                f"Retrying in {wait} seconds..."
            )
            time.sleep(wait)

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini returned no answer. Check model access or API limits."
        )

    parts = candidates[0].get("content", {}).get("parts", [])
    answer = "\n".join(
        part.get("text", "")
        for part in parts
        if "text" in part
    )

    if not answer:
        raise RuntimeError("Gemini returned an empty report.")

    return answer


def main():
    research = {}

    for niche in NICHES:
        print(f"Researching: {niche}")

        try:
            research[niche] = fetch_news(niche)
        except Exception as error:
            print(f"News source error: {error}")
            research[niche] = []

    if not any(research.values()):
        raise RuntimeError(
            "No research articles could be retrieved."
        )

    report = ask_gemini(research)

    os.makedirs("reports", exist_ok=True)

    filename = "reports/research_latest.md"

    with open(filename, "w", encoding="utf-8") as file:
        file.write("# AI Research Agent Report\n\n")
        file.write(
            "Generated: "
            + datetime.now(timezone.utc).isoformat()
            + "\n\n"
        )
        file.write(report)

    print("\nResearch report generated successfully!")
    print(f"Saved to: {filename}")


if __name__ == "__main__":
    main()
