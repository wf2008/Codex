"""Web scraping tool to extract content from URLs"""
import requests
from bs4 import BeautifulSoup
import re


def web_scraper(url: str, max_chars: int = 8000) -> str:
    """Extract readable text content from a URL"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Get text
        text = soup.get_text(separator="\n")

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        # Truncate if too long
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"

        return f"Content from {url}:\n\n{text}"
    except Exception as e:
        return f"Scraping error for {url}: {e}"
