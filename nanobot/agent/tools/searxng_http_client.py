"""Searxng HTTP client for nanobot.

This module provides a client that makes HTTP requests to a running Searxng server
instead of importing Searxng as a Python library.
"""

import os
from typing import Any

import httpx
from loguru import logger


class SearxngHttpClient:
    """
    HTTP client for Searxng metasearch engine.

    Makes requests to a running Searxng server instead of importing it as a library.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize Searxng HTTP client.

        Args:
            base_url: URL of the Searxng server (e.g., "http://localhost:8888").
                     Defaults to SEARXNG_URL env var or "http://localhost:8888".
            timeout: Request timeout in seconds.
        """
        self.base_url = (base_url or os.getenv(
            "SEARXNG_URL", "http://localhost:8888"
        )).rstrip("/")

        self.timeout = timeout
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        query: str,
        engines: list[str] | None = None,
        categories: list[str] | None = None,
        language: str = "en",
        time_range: str | None = None,
        safesearch: int = 0,
        count: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Perform search using Searxng HTTP API.

        Args:
            query: Search query string.
            engines: List of engine names to use (e.g., ['duckduckgo', 'brave']).
                     If None, uses Searxng server default engines.
            categories: List of categories to search (e.g., ['general', 'news']).
                        If None, searches default categories.
            language: Language code (default: 'en').
            time_range: Time range filter ('day', 'week', 'month', 'year').
            safesearch: Safe search level (0=none, 1=moderate, 2=strict).
            count: Maximum number of results to return.

        Returns:
            List of search result dictionaries with keys:
            - title: Result title.
            - url: Result URL.
            - content: Result snippet/content.
            - engine: Search engine that provided the result.
            - category: Result category.
            - score: Result relevance score.
            - publishedDate: Publication date (if available).
        """
        client = self._get_client()

        try:
            # Build query parameters for Searxng API
            params = {
                "q": query,
                "format": "json",
                "language": language,
                "safesearch": safesearch,
            }

            # Add optional parameters
            if engines:
                params["engines"] = ",".join(engines)
            if categories:
                params["categories"] = ",".join(categories)
            if time_range:
                params["time_range"] = time_range
            if count:
                params["pageno"] = 1  # Always use first page

            # Make request to Searxng search API
            response = await client.get(
                f"{self.base_url}/search",
                params=params,
            )
            response.raise_for_status()

            data = response.json()

            # Extract and format results
            results = []
            for result in data.get("results", [])[:count]:
                formatted_result = {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "engine": result.get("engine", ""),
                    "category": result.get("category", ""),
                    "score": result.get("score", 0.0),
                }

                # Add optional fields
                if result.get("publishedDate"):
                    formatted_result["publishedDate"] = result["publishedDate"]
                if result.get("img_src"):
                    formatted_result["img_src"] = result["img_src"]
                if result.get("thumbnail"):
                    formatted_result["thumbnail"] = result["thumbnail"]

                results.append(formatted_result)

            logger.debug(
                f"Searxng HTTP search completed: query='{query}', engines={engines}, results={len(results)}"
            )
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"Searxng HTTP error: {e.response.status_code} - {e.response.text}")
            return []
        except httpx.ConnectError:
            logger.error(f"Failed to connect to Searxng server at {self.base_url}")
            return []
        except httpx.TimeoutException:
            logger.error(f"Searxng request timed out")
            return []
        except Exception as e:
            logger.error(f"Searxng HTTP search failed: {e}")
            return []

    async def health_check(self) -> bool:
        """
        Check if Searxng server is reachable.

        Returns:
            True if server is reachable, False otherwise.
        """
        try:
            client = self._get_client()
            response = await client.get(
                f"{self.base_url}/",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Searxng health check failed: {e}")
            return False

    def get_available_engines(self) -> list[str]:
        """
        Get list of available search engines.

        Note: This would require an additional API call to /config endpoint.
        For now, returns common engine names.

        Returns:
            List of engine names.
        """
        # Common Searxng engines
        return [
            "duckduckgo",
            "brave",
            "bing",
            "google",
            "wikipedia",
            "startpage",
        ]

    def get_available_categories(self) -> list[str]:
        """
        Get list of available search categories.

        Returns:
            List of category names.
        """
        return [
            "general",
            "images",
            "videos",
            "news",
            "map",
            "music",
            "it",
            "science",
            "files",
            "social media",
        ]
