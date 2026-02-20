"""Web tools: web_search and web_fetch."""

import html
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger

from nanobot.agent.tools.base import Tool

# Try to import Searxng HTTP client (optional, for multi-engine search)
try:
    from nanobot.agent.tools.searxng_http_client import SearxngHttpClient
    SEARXNG_AVAILABLE = True
except ImportError:
    SEARXNG_AVAILABLE = False
    logger.debug("Searxng HTTP client not available. Set SEARXNG_URL to enable.")

# Shared constants
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_REDIRECTS = 5  # Limit redirects to prevent DoS attacks

# Try to import DuckDuckGo search library (renamed to ddgs)
try:
    from ddgs import DDGS
    DDG_AVAILABLE = True
except ImportError:
    DDG_AVAILABLE = False
    logger.warning("ddgs package not installed. DuckDuckGo search will be unavailable. Install with: pip install ddgs")

def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    """Validate URL: must be http(s) with valid domain."""
    try:
        p = urlparse(url)
        if p.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)


class WebSearchTool(Tool):
    """Search web using multiple engines with Searxng metasearch.

    Engines:
    - searxng (Searxng): Multi-engine metasearch, aggregates from 70+ engines (best for research)
    - ddg (DuckDuckGo): General search, requires pip install ddgs
    - brave: Privacy-focused, requires BRAVE_API_KEY environment variable
    """

    name = "web_search"
    description = "Search web using multiple engines. Returns titles, URLs, and snippets. Engine options: 'searxng' (multi-engine metasearch, best for research), 'ddg' (DuckDuckGo - general search, default), 'brave' (privacy-focused, requires API key)."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Results (1-10)", "minimum": 1, "maximum": 10},
            "engine": {
                "type": "string",
                "description": "Search engine: 'searxng' (multi-engine metasearch), 'ddg' (DuckDuckGo, default), 'brave' (requires API key)",
                "enum": ["searxng", "ddg", "brave"]
            },
            "engines": {
                "type": "array",
                "items": {"type": "string"},
                "description": "For searxng engine: list of specific engines to use (e.g., ['duckduckgo', 'brave', 'bing'])"
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "For searxng engine: search categories (e.g., ['general', 'news', 'images'])"
            },
            "time_range": {
                "type": "string",
                "enum": ["day", "week", "month", "year"],
                "description": "For searxng engine: filter results by time range"
            }
        },
        "required": ["query"]
    }

    def __init__(self, api_key: str | None = None, max_results: int = 5, engine: str = "ddg", impersonate: str = "random"):
        """
        Initialize web search tool.

        Args:
            api_key: Brave Search API key (optional, for Brave engine)
            max_results: Maximum number of results to return
            engine: Search engine to use - "searxng", "ddg" (default), "brave"
                       - "searxng": Use Searxng metasearch server (requires SEARXNG_URL)
                       - "ddg": Use DuckDuckGo - free, no API key needed (default)
                       - "brave": Use Brave API - requires api_key
            impersonate: Browser impersonation for DuckDuckGo (default: "random")
                         Options: "random", "chrome", "firefox", "safari", etc.
        """
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        self.max_results = max_results
        self.engine = engine.lower()
        self.impersonate = impersonate
        self._ddg_available = DDG_AVAILABLE

        # Initialize Searxng HTTP client if using searxng engine
        self.searxng_client = None
        if self.engine == "searxng" and SEARXNG_AVAILABLE:
            self.searxng_client = SearxngHttpClient()

    async def _search_brave(self, query: str, n: int) -> str | None:
        """Try searching with Brave API."""
        if not self.api_key:
            logger.debug("Brave API key not provided")
            return None

        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": n},
                    headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                    timeout=15.0
                )
                r.raise_for_status()

            results = r.json().get("web", {}).get("results", [])
            if not results:
                logger.debug(f"No Brave results for: {query}")
                return None

            lines = [f"Brave results for: {query}\n"]
            for i, item in enumerate(results[:n], 1):
                lines.append(f"{i}. {item.get('title', '')}\n   {item.get('url', '')}")
                if desc := item.get("description"):
                    lines.append(f"   {desc}")
            return "\n".join(lines)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Brave API key is invalid or unauthorized")
            else:
                logger.error(f"Brave API error: {e.response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.error("Brave API timeout")
            return None
        except Exception as e:
            logger.error(f"Brave search failed: {e}")
            return None

    async def _search_ddg(self, query: str, n: int) -> str | None:
        """Try searching with DuckDuckGo."""
        if not self._ddg_available:
            logger.debug("DuckDuckGo (ddgs) not available")
            return None

        try:
            # Initialize DDGS - impersonate is handled internally by the library
            # Only pass impersonate if DDGS accepts it (older versions)
            import inspect
            import io
            import contextlib
            import sys

            ddgs_kwargs = {}
            if 'impersonate' in inspect.signature(DDGS.__init__).parameters:
                ddgs_kwargs['impersonate'] = self.impersonate

            # Suppress ddgs library warnings (printed to stderr)
            stderr_capture = io.StringIO()
            with contextlib.redirect_stderr(stderr_capture):
                ddgs = DDGS(**ddgs_kwargs)
                results = ddgs.text(query, max_results=n)

            if not results:
                logger.debug(f"No DuckDuckGo results for: {query}")
                return None

            lines = [f"DuckDuckGo results for: {query}\n"]
            for i, item in enumerate(results[:n], 1):
                lines.append(f"{i}. {item.get('title', '')}\n   {item.get('link', '')}")
                if body := item.get("body"):
                    lines.append(f"   {body}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return None

    async def _search_searxng(self, query: str, n: int, **kwargs: Any) -> str | None:
        """Try searching with Searxng metasearch engine via HTTP."""
        if not SEARXNG_AVAILABLE:
            logger.debug("Searxng HTTP client not available")
            return None

        if not self.searxng_client:
            self.searxng_client = SearxngHttpClient()

        try:
            # Extract Searxng-specific parameters
            engines = kwargs.get("engines", None)
            categories = kwargs.get("categories", None)
            time_range = kwargs.get("time_range", None)

            # Perform search (async HTTP request)
            results = await self.searxng_client.search(
                query=query,
                engines=engines,
                categories=categories,
                language="en",
                time_range=time_range,
                safesearch=0,
                count=n,
            )

            if not results:
                logger.debug(f"No Searxng results for: {query}")
                return None

            # Format results
            engine_names = engines or ["multiple"]
            lines = [f"Searxng results for: {query} (engines: {', '.join(engine_names)})\n"]

            for i, result in enumerate(results[:n], 1):
                lines.append(f"{i}. {result.get('title', '')}")
                lines.append(f"   {result.get('url', '')}")
                if content := result.get('content', ''):
                    lines.append(f"   {content[:200]}{'...' if len(content) > 200 else ''}")
                # Show which engine provided this result
                if engine := result.get('engine', ''):
                    lines.append(f"   Engine: {engine}")
                if published_date := result.get('publishedDate'):
                    lines.append(f"   Published: {published_date}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Searxng search failed: {e}")
            return None

    async def _search_engine(self, engine: str, query: str, n: int, **kwargs: Any) -> str | None:
        """Search using specified engine."""
        # Handle "auto" by falling back to "ddg" (default)
        if engine == "auto":
            engine = "ddg"

        if engine == "searxng":
            return await self._search_searxng(query, n, **kwargs)
        elif engine == "brave":
            return await self._search_brave(query, n)
        elif engine == "ddg":
            return await self._search_ddg(query, n)
        return None

    async def execute(self, query: str, count: int | None = None, engine: str | None = None, **kwargs: Any) -> str:
        n = min(max(count or self.max_results, 1), 10)

        # Use engine from parameter if provided, otherwise use default
        search_engine = (engine or self.engine).lower()

        # Search using the specified engine
        result = await self._search_engine(search_engine, query, n, **kwargs)

        if result:
            return result
        elif search_engine == "searxng":
            if not SEARXNG_AVAILABLE:
                return "Error: Searxng is not available. Check SEARXNG_PATH environment variable."
            return "Error: Searxng search failed. Try a different engine."
        elif search_engine == "brave":
            if not self.api_key:
                return "Error: Brave search requires an API key. Set BRAVE_API_KEY environment variable or pass api_key parameter."
            return "Error: Brave search failed. Check your API key is valid."
        elif search_engine == "ddg" and not DDG_AVAILABLE:
            return "Error: DuckDuckGo search requires the ddgs package. Install it with: pip install ddgs"
        return f"Error: {search_engine} search failed."


class WebFetchTool(Tool):
    """Fetch and extract content from a URL using Readability."""

    name = "web_fetch"
    description = "Fetch URL and extract readable content (HTML → markdown/text)."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "extractMode": {"type": "string", "enum": ["markdown", "text"], "default": "markdown"},
            "maxChars": {"type": "integer", "minimum": 100}
        },
        "required": ["url"]
    }

    def __init__(self, max_chars: int = 50000):
        self.max_chars = max_chars

    async def execute(self, url: str, extractMode: str = "markdown", maxChars: int | None = None, **kwargs: Any) -> str:
        from readability import Document

        max_chars = maxChars or self.max_chars

        # Validate URL before fetching
        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return json.dumps({"error": f"URL validation failed: {error_msg}", "url": url}, ensure_ascii=False)

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
                timeout=30.0
            ) as client:
                r = await client.get(url, headers={"User-Agent": USER_AGENT})
                r.raise_for_status()

            ctype = r.headers.get("content-type", "")

            # JSON
            if "application/json" in ctype:
                text, extractor = json.dumps(r.json(), indent=2, ensure_ascii=False), "json"
            # HTML
            elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
                doc = Document(r.text)
                content = self._to_markdown(doc.summary()) if extractMode == "markdown" else _strip_tags(doc.summary())
                text = f"# {doc.title()}\n\n{content}" if doc.title() else content
                extractor = "readability"
            else:
                text, extractor = r.text, "raw"

            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]

            return json.dumps({"url": url, "finalUrl": str(r.url), "status": r.status_code,
                              "extractor": extractor, "truncated": truncated, "length": len(text), "text": text}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)
    def _to_markdown(self, html: str) -> str:
        """Convert HTML to markdown."""
        # Convert links, headings, lists before stripping tags
        text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
                      lambda m: f'[{_strip_tags(m[2])}]({m[1]})', html, flags=re.I)
        text = re.sub(r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
                      lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n', html, flags=re.I)
        text = re.sub(r'<li[^>]*>([\s\S]*?)</li>', lambda m: f'\n- {_strip_tags(m[1])}', html, flags=re.I)
        text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
        text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
        return _normalize(_strip_tags(text))
