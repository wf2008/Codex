"""Multi-engine web search (DuckDuckGo + SearXNG fallback)"""
import requests
import json
from typing import Optional


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using multiple engines"""
    try:
        # Try DuckDuckGo first
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if results:
            formatted = []
            for idx, r in enumerate(results, 1):
                title = r.get("title", "Untitled")
                body = r.get("body", "")
                href = r.get("href", "")
                formatted.append(f"{idx}. {title}\n{body}\nSource: {href}")
            return "\n\n".join(formatted)
    except Exception:
        pass

    # Fallback to SearXNG (self-hosted or public instances)
    searx_instances = [
        "https://search.sapti.me",
        "https://search.bus-hit.me",
        "https://search.projectsegfault.com",
    ]
    for instance in searx_instances:
        try:
            resp = requests.get(
                f"{instance}/search",
                params={"q": query, "format": "json", "engines": "google,bing,duckduckgo"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])[:max_results]
                if results:
                    formatted = []
                    for idx, r in enumerate(results, 1):
                        title = r.get("title", "Untitled")
                        content = r.get("content", "")
                        url = r.get("url", "")
                        formatted.append(f"{idx}. {title}\n{content}\nSource: {url}")
                    return "\n\n".join(formatted)
        except Exception:
            continue

    return f"Search error: Could not retrieve results for '{query}'. Try again later."
