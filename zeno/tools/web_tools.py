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
