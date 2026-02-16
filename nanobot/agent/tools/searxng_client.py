"""Searxng search client wrapper for nanobot.

This module provides a clean interface to Searxng's search capabilities,
handling initialization and returning structured results.
"""

import os
import sys
import threading
from typing import Any

from loguru import logger


class SearxngClient:
    """
    Client for Searxng metasearch engine.

    Provides access to 70+ search engines through a unified interface.
    Handles lazy initialization and thread-safe operations.
    """

    # Class-level lock for thread-safe initialization
    _init_lock = threading.Lock()
    _initialized = False

    def __init__(self, searxng_path: str | None = None):
        """
        Initialize Searxng client.

        Args:
            searxng_path: Path to Searxng installation. Defaults to
                          /root/nanobot/searxng or SEARXNG_PATH env var.
        """
        self.searxng_path = searxng_path or os.getenv(
            "SEARXNG_PATH", "/root/nanobot/searxng"
        )

        # Add Searxng to Python path if not already there
        if self.searxng_path not in sys.path:
            sys.path.insert(0, self.searxng_path)

        # Import Searxng modules (lazy loading)
        self._settings = None
        self._SearchQuery = None
        self._EngineRef = None
        self._Search = None

    def initialize(self) -> bool:
        """
        Initialize Searxng search engine.

        This loads engine configurations and initializes network settings.
        Thread-safe and only initializes once.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        # Double-checked locking pattern for thread safety
        if SearxngClient._initialized:
            return True

        with SearxngClient._init_lock:
            # Check again after acquiring lock
            if SearxngClient._initialized:
                return True

            try:
                # Import Searxng modules
                from searx import settings
                from searx.search import initialize as searxng_init
                from searx.search.models import SearchQuery, EngineRef
                from searx.search import Search

                self._settings = settings
                self._SearchQuery = SearchQuery
                self._EngineRef = EngineRef
                self._Search = Search

                # Initialize Searxng with settings
                logger.info("Initializing Searxng search engine...")
                searxng_init(
                    settings_engines=settings.get("engines", []),
                    enable_checker=False,
                    check_network=False,
                    enable_metrics=False,
                )

                SearxngClient._initialized = True
                logger.info("Searxng initialized successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to initialize Searxng: {e}")
                SearxngClient._initialized = False
                return False

    def search(
        self,
        query: str,
        engines: list[str] | None = None,
        categories: list[str] | None = None,
        lang: str = "en",
        safesearch: int = 0,
        time_range: str | None = None,
        count: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Perform search using Searxng.

        Args:
            query: Search query string.
            engines: List of engine names to use (e.g., ['duckduckgo', 'brave']).
                     If None, uses default engines from settings.
            categories: List of categories to search (e.g., ['general', 'news']).
                        If None, searches 'general' category.
            lang: Language code (default: 'en').
            safesearch: Safe search level (0=none, 1=moderate, 2=strict).
            time_range: Time range filter ('day', 'week', 'month', 'year').
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
        # Ensure initialized
        if not SearxngClient._initialized:
            if not self.initialize():
                logger.error("Cannot search: Searxng initialization failed")
                return []

        try:
            # Default engines and categories
            if engines is None:
                engines = ["duckduckgo", "brave"]
            if categories is None:
                categories = ["general"]

            # Build engine reference list
            engineref_list = []
            for engine in engines:
                for category in categories:
                    # Check if engine supports this category
                    if self._is_engine_supported(engine, category):
                        engineref_list.append(self._EngineRef(engine, category))

            if not engineref_list:
                logger.warning(
                    f"No valid engine/category combinations for engines={engines}, categories={categories}"
                )
                # Fallback to duckduckgo/general
                engineref_list = [self._EngineRef("duckduckgo", "general")]

            # Create search query
            search_query = self._SearchQuery(
                query=query,
                engineref_list=engineref_list,
                lang=lang,
                safesearch=safesearch,
                pageno=1,
                time_range=time_range,
            )

            # Perform search
            search = self._Search(search_query)
            result_container = search.search()

            # Get ordered results
            results = result_container.get_ordered_results()

            # Convert to structured format
            formatted_results = []
            for result in results[:count]:
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
                    formatted_result["publishedDate"] = result["publishedDate"].isoformat()
                if result.get("img_src"):
                    formatted_result["img_src"] = result["img_src"]
                if result.get("thumbnail"):
                    formatted_result["thumbnail"] = result["thumbnail"]

                formatted_results.append(formatted_result)

            logger.debug(
                f"Searxng search completed: query='{query}', engines={engines}, results={len(formatted_results)}"
            )
            return formatted_results

        except Exception as e:
            logger.error(f"Searxng search failed: {e}")
            return []

    def _is_engine_supported(self, engine_name: str, category: str) -> bool:
        """
        Check if an engine supports a specific category.

        This is a simplified check. In production, you would query the
        actual engine configuration from Searxng settings.

        Args:
            engine_name: Name of the search engine.
            category: Category to check.

        Returns:
            True if engine likely supports the category.
        """
        # Common category mappings
        # This is a basic implementation - could be enhanced by reading
        # actual engine capabilities from Searxng settings
        supported_categories = {
            "duckduckgo": ["general"],
            "brave": ["general"],
            "bing": ["general", "images", "videos", "news"],
            "google": ["general", "images", "videos", "news"],
            "wikipedia": ["general"],
            "startpage": ["general"],
        }

        engine_categories = supported_categories.get(engine_name, ["general"])

        # Map common category aliases
        category_map = {
            "web": "general",
        }
        normalized_category = category_map.get(category, category)

        return normalized_category in engine_categories

    def get_available_engines(self) -> list[str]:
        """
        Get list of available search engines.

        Returns:
            List of engine names that can be used for searches.
        """
        if not SearxngClient._initialized:
            if not self.initialize():
                return []

        try:
            if self._settings and "engines" in self._settings:
                return [
                    engine["name"]
                    for engine in self._settings["engines"]
                    if engine.get("enabled", True)
                ]
        except Exception as e:
            logger.error(f"Failed to get available engines: {e}")

        return []

    def get_available_categories(self) -> list[str]:
        """
        Get list of available search categories.

        Returns:
            List of category names that can be used for searches.
        """
        # Common Searxng categories
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
