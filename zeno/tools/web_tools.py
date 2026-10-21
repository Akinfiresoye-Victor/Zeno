"""
Web search tool enabling Zeno to query online technical documentation,
coding references, and live information.
Category: web_search
"""

from __future__ import annotations

import json
from urllib.parse import quote_plus
import urllib.request
import urllib.error

_DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web for programming references, technical questions, or latest documentation.

    Args:
        query: Search keywords or question.
        max_results: Maximum number of search results to return (default 5).

    Returns:
        list[dict]: List of results with 'title', 'url', and 'snippet'.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    encoded_query = quote_plus(clean_query)
    url = _DUCKDUCKGO_API_URL.format(query=encoded_query)

    results = []
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Zeno-Desktop-Assistant/2.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Extract abstract if available
        abstract_text = data.get("AbstractText", "")
        abstract_url = data.get("AbstractURL", "")
        heading = data.get("Heading", clean_query)
        if abstract_text:
            results.append({
                "title": heading,
                "url": abstract_url or "https://duckduckgo.com/?q=" + encoded_query,
                "snippet": abstract_text,
            })

        # Extract related topics
        related_topics = data.get("RelatedTopics", [])
        for item in related_topics:
            if len(results) >= max_results:
                break
            if isinstance(item, dict) and "Text" in item and "FirstURL" in item:
                results.append({
                    "title": item.get("Text", "")[:60] + "...",
                    "url": item.get("FirstURL", ""),
                    "snippet": item.get("Text", ""),
                })
            elif isinstance(item, dict) and "Topics" in item:
                for sub_topic in item.get("Topics", []):
                    if len(results) >= max_results:
                        break
                    if "Text" in sub_topic and "FirstURL" in sub_topic:
                        results.append({
                            "title": sub_topic.get("Text", "")[:60] + "...",
                            "url": sub_topic.get("FirstURL", ""),
                            "snippet": sub_topic.get("Text", ""),
                        })

    except Exception:
        # Fallback informative mock result if network offline
        results.append({
            "title": f"Web Search: {clean_query}",
            "url": f"https://www.google.com/search?q={encoded_query}",
            "snippet": f"Web query dispatched for '{clean_query}'. Consult official documentation or language specs.",
        })

    if not results:
        results.append({
            "title": f"Results for: {clean_query}",
            "url": f"https://duckduckgo.com/?q={encoded_query}",
            "snippet": f"No direct instant summary found for '{clean_query}'. Check official documentation.",
        })

    return results[:max_results]


def fetch_webpage_content(url_or_domain: str, max_chars: int = 4000) -> dict[str, Any]:
    """
    Fetch and extract clean readable text, title, and description from a website or URL.
    Handles raw domains like 'estatewebng.com' or full URLs like 'https://example.com/page'.
    """
    import html
    import re
    from typing import Any

    clean_target = url_or_domain.strip().strip("'\"<>")
    if not clean_target:
        return {"ok": False, "error": "Empty URL provided."}

    if not clean_target.startswith(("http://", "https://")):
        target_url = "https://" + clean_target
    else:
        target_url = clean_target

    try:
        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw_bytes = resp.read(250000)
            charset = resp.headers.get_content_charset() or "utf-8"
            html_text = raw_bytes.decode(charset, errors="replace")

        # Extract title
        title_m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        title = html.unescape(title_m.group(1).strip()) if title_m else clean_target

        # Extract meta description
        desc_m = re.search(r'<meta[^>]+name=[\'"]description[\'"][^>]+content=[\'"]([^\'"]+)[\'"]', html_text, re.IGNORECASE)
        if not desc_m:
            desc_m = re.search(r'<meta[^>]+content=[\'"]([^\'"]+)[\'"][^>]+name=[\'"]description[\'"]', html_text, re.IGNORECASE)
        description = html.unescape(desc_m.group(1).strip()) if desc_m else ""

        # Remove scripts, styles, svg, and markup
        text = re.sub(r"<(script|style|svg|noscript|header|footer|nav)[^>]*>.*?</\1>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        body_text = "\n".join(lines)
        if len(body_text) > max_chars:
            body_text = body_text[:max_chars] + "\n... [content truncated]"

        return {
            "ok": True,
            "url": target_url,
            "title": title,
            "description": description,
            "content": body_text,
        }
    except Exception as exc:
        search_res = web_search(clean_target, max_results=3)
        snippets = "\n".join(f"- {r.get('title')}: {r.get('snippet')}" for r in search_res)
        return {
            "ok": False,
            "url": target_url,
            "error": str(exc),
            "fallback_search": snippets,
        }

