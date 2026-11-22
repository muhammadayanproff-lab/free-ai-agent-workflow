import os
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

API_KEY = os.environ["GEMINI_API_KEY"]
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
        + query + "&hl=en-US&gl=US&ceid=US:en"
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
        "v1beta/models/gemini-2.5-flash:generateContent"
    )

    prompt = f"""
You are an expert content research agent.

Analyse these recent public news and search results.

For each niche:
1. Identify interesting emerging topics.
2. Suggest 5 original social media content ideas.
3. Explain why each topic may interest an audience.
4. Suggest suitable content formats.
5. Separate verified information from speculation.
6. Include source URLs.
7. Never invent facts or claim that a topic is viral
   without evidence.

Research data:
{json.dumps(research, ensure_ascii=False)}

Return a clear report in Markdown.
"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
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

    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.loads(response.read())

    return result["candidates"][0]["content"]["parts"][0]["text"]

def main():
    research = {}

    for niche in NICHES:
        print(f"Researching: {niche}")
        try:
            research[niche] = fetch_news(niche)
        except Exception as error:
            print(f"Source error for {niche}: {error}")
            research[niche] = []

    if not any(research.values()):
        raise RuntimeError("No research sources were retrieved.")

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
    print("\n" + report)

if __name__ == "__main__":
    main()
