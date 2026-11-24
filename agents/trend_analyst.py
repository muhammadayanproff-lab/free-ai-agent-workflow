import os
import json
import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-3.5-flash-lite"
TRENDS_GEO = os.getenv("TRENDS_GEO", "PK").upper()
NEWS_GEO = os.getenv("NEWS_GEO", "PK").upper()
NEWS_HL = os.getenv("NEWS_HL", "en-PK")

NICHES = [
    x.strip()
    for x in os.getenv(
        "NICHES",
        "AI technology, social media trends, content creation"
    ).split(",")
    if x.strip()
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrendAnalyst/1.0)"}


def fetch_rss(url, source, limit=15):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    results = []

    for item in root.findall(".//item")[:limit]:
        results.append({
            "source": source,
            "title": item.findtext("title", ""),
            "link": item.findtext("link", ""),
            "published": item.findtext("pubDate", ""),
            "description": item.findtext("description", "")
        })

    return results


def collect_trends():
    results = []
    errors = []

    # Google Trends: currently popular Google searches.
    try:
        trends = fetch_rss(
            f"https://trends.google.com/trending/rss?geo={TRENDS_GEO}",
            "Google Trends",
            20
        )
        results.extend(trends)
        print(f"Google Trends: {len(trends)} items")
    except Exception as error:
        errors.append(f"Google Trends unavailable: {error}")
        print(errors[-1])

    # Google News: recent coverage in selected niches.
    for niche in NICHES:
        try:
            query = urllib.parse.quote(niche)
            url = (
                "https://news.google.com/rss/search?q="
                + query
                + "&hl=" + urllib.parse.quote(NEWS_HL) + "&gl=" + NEWS_GEO + "&ceid=" + NEWS_GEO + ":en"
            )

            articles = fetch_rss(url, "Google News", 8)
            results.extend(articles)
            print(f"{niche}: {len(articles)} articles")

        except Exception as error:
            errors.append(f"{niche} news unavailable: {error}")
            print(errors[-1])

    # Remove duplicate titles.
    unique = {}
    for item in results:
        title = item["title"].strip().lower()
        if title:
            unique[title] = item

    return list(unique.values()), errors


def analyse_with_gemini(items, errors):
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )

    prompt = f"""
You are a professional social media trend analyst.

Analyse the following recent Google Trends and Google News data.

Niches:
{", ".join(NICHES)}

Your tasks:

1. Identify the strongest emerging topics.
2. Rank the 10 best content opportunities.
3. Explain the evidence behind each opportunity.
4. Identify repeated topics appearing across sources.
5. Suggest Instagram Reel, TikTok and YouTube Shorts ideas.
6. Suggest suitable hooks for each idea.
7. Identify topics that appear to be losing relevance, if evidence supports it.
8. Give each opportunity a potential score from 1 to 10.
9. Clearly distinguish Google search trends from social-media trends.
10. Never invent view counts, engagement figures or viral statistics.
11. Include source links wherever available.
12. Explain when the available evidence is insufficient.

Important:
Google Trends search interest is not the same as Instagram or TikTok
views, engagement or viral rankings. Do not confuse them.

Research data:
{json.dumps(items, ensure_ascii=False)}

Source collection errors:
{json.dumps(errors, ensure_ascii=False)}

Return a professional Markdown report with headings, rankings,
evidence, content ideas and a final recommended content priority.
"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.3,
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
            details = error.read().decode(
                "utf-8", errors="replace"
            )

            if error.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(
                    f"Gemini API error {error.code}: {details[:1000]}"
                )

            if attempt == 4:
                raise RuntimeError(
                    f"Gemini unavailable after 5 attempts: "
                    f"HTTP {error.code}"
                )

            wait = 5 * (2 ** attempt)
            print(f"Gemini temporary error. Retrying in {wait}s...")
            time.sleep(wait)

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            "Gemini returned no analysis. Check API access and quota."
        )

    parts = candidates[0].get("content", {}).get("parts", [])
    report = "\n".join(
        part.get("text", "")
        for part in parts
        if "text" in part
    )

    if not report.strip():
        raise RuntimeError("Gemini returned an empty analysis.")

    return report


def main():
    os.makedirs("reports", exist_ok=True)

    filename = "reports/trend_analysis_latest.md"

    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")

    print("Starting Trend Analyst...")
    items, errors = collect_trends()

    if not items:
        report = (
            "# Trend Analyst Report\n\n"
            "No trend data could be retrieved during this run.\n\n"
            + "\n".join(f"- {error}" for error in errors)
        )
    else:
        try:
            report = analyse_with_gemini(items, errors)
        except Exception as error:
            report = (
                "# Trend Analyst Report\n\n"
                "Trend data was collected, but AI analysis failed.\n\n"
                f"Error: {error}\n\n"
                "Collected data:\n\n"
                "```json\n"
                + json.dumps(items, ensure_ascii=False, indent=2)
                + "\n```\n"
            )

    with open(filename, "w", encoding="utf-8") as file:
        file.write("# AI Workforce — Trend Analyst\n\n")
        file.write(
            "Generated: "
            + datetime.now(timezone.utc).isoformat()
            + "\n\n"
        )
        file.write(f"Sources collected: {len(items)}\n\n")
        file.write(report)

    print(f"Trend report saved: {filename}")
    print("Trend Analyst finished.")


if __name__ == "__main__":
    main()
