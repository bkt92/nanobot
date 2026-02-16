"""Research tool cloning Perplexica's iterative deep research mechanism."""

import asyncio
import json
from datetime import datetime
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool, SEARXNG_AVAILABLE


class ResearchTool(Tool):
    """
    Deep research tool that clones Perplexica's research mechanism.

    Implements iterative search with:
    - Multiple research modes (speed/balanced/quality)
    - Multi-engine search (Searxng, DuckDuckGo, Brave)
    - Category-specific searches (general, news, images)
    - Progressive query refinement
    - Source deduplication and synthesis
    """

    name = "deep_research"
    description = (
        "Perform deep, iterative research on a topic. "
        "Supports three modes: 'speed' (2 iterations, quick answers), "
        "'balanced' (6 iterations, moderate depth with reasoning), "
        "'quality' (25 iterations, comprehensive research). "
        "Uses multiple search rounds with query refinement and source synthesis. "
        "Leverages Searxng for multi-engine, multi-category search when available."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Research topic or question",
            },
            "mode": {
                "type": "string",
                "enum": ["speed", "balanced", "quality"],
                "description": "Research mode: speed (quick), balanced (moderate), quality (comprehensive)",
            },
            "max_results": {
                "type": "integer",
                "description": "Max results per search (1-10)",
                "minimum": 1,
                "maximum": 10,
            },
            "use_searxng": {
                "type": "boolean",
                "description": "Use Searxng multi-engine search (default: true if available)",
            },
        },
        "required": ["query"],
    }

    def __init__(self, api_key: str | None = None, max_results: int = 5):
        """
        Initialize research tool.

        Args:
            api_key: Optional Brave Search API key
            max_results: Default max results per search
        """
        # Use Searxng by default if available, otherwise fall back to ddg
        default_engine = "searxng" if SEARXNG_AVAILABLE else "ddg"
        self.web_search = WebSearchTool(
            api_key=api_key,
            max_results=max_results,
            engine=default_engine
        )
        self.web_fetch = WebFetchTool()
        self.max_results = max_results
        self.searxng_available = SEARXNG_AVAILABLE

    async def execute(
        self, query: str, mode: str = "balanced", max_results: int | None = None, use_searxng: bool | None = None, **kwargs: Any
    ) -> str:
        """
        Execute deep research on the given query.

        Args:
            query: Research topic or question
            mode: Research mode (speed/balanced/quality)
            max_results: Override default max results per search
            use_searxng: Use Searxng multi-engine search (default: auto-detect)

        Returns:
            Research findings with sources
        """
        max_results = max_results or self.max_results

        # Determine if we should use Searxng
        use_searxng_engine = use_searxng if use_searxng is not None else self.searxng_available

        # Determine iterations based on mode (cloning Perplexica's approach)
        mode_iterations = {"speed": 2, "balanced": 6, "quality": 25}
        max_iterations = mode_iterations.get(mode, 6)

        logger.info(f"Starting deep research (mode={mode}, max_iterations={max_iterations}, use_searxng={use_searxng_engine}): {query}")

        # Research state
        search_history = []
        all_findings = []
        seen_urls = set()
        current_plan = "Starting research with broad queries to get an overview"

        try:
            # Iterative research loop
            for iteration in range(max_iterations):
                logger.debug(f"Research iteration {iteration + 1}/{max_iterations}")

                # Generate search strategies with engine/category configuration
                search_strategies = await self._generate_search_strategies(
                    query=query,
                    iteration=iteration,
                    max_iterations=max_iterations,
                    mode=mode,
                    use_searxng=use_searxng_engine,
                    previous_findings=all_findings,
                )

                if not search_strategies:
                    logger.debug("No more search strategies, ending research")
                    break

                # Update plan for progress tracking
                strategies_summary = ", ".join([s["query"] for s in search_strategies[:2]])
                current_plan = f"Searching for: {strategies_summary}"
                if len(search_strategies) > 2:
                    current_plan += f" and {len(search_strategies) - 2} more queries"

                # Execute searches with their specific engine/category configs
                search_tasks = []
                for strategy in search_strategies[:3]:
                    task = self.web_search.execute(
                        strategy["query"],
                        count=max_results,
                        engine=strategy.get("engine"),
                        engines=strategy.get("engines"),
                        categories=strategy.get("categories"),
                        time_range=strategy.get("time_range"),
                    )
                    search_tasks.append(task)

                search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

                # Process results
                iteration_findings = []
                for i, result in enumerate(search_results):
                    if isinstance(result, Exception):
                        logger.warning(f"Search {i+1} failed: {result}")
                        continue

                    # Extract and deduplicate findings
                    findings = self._extract_findings(result, seen_urls)
                    iteration_findings.extend(findings)
                    all_findings.extend(findings)

                search_history.append({
                    "iteration": iteration + 1,
                    "strategies": search_strategies[:3],
                    "new_sources": len(iteration_findings),
                    "plan": current_plan,
                })

                # Check if we should stop early
                if self._should_stop_early(iteration, iteration_findings, mode):
                    logger.debug(f"Stopping early at iteration {iteration + 1}")
                    break

            # Synthesize findings
            return self._synthesize_results(query, all_findings, search_history, mode)

        except Exception as e:
            logger.error(f"Research failed: {e}")
            return json.dumps({
                "error": str(e),
                "query": query,
                "partial_findings": all_findings[:5],
            })

    async def _generate_search_strategies(
        self,
        query: str,
        iteration: int,
        max_iterations: int,
        mode: str,
        use_searxng: bool,
        previous_findings: list[dict],
    ) -> list[dict]:
        """
        Generate search strategies for the current iteration.

        Each strategy includes:
        - query: Search query string
        - engine: Search engine to use (optional, defaults to tool default)
        - engines: List of engines for Searxng (optional)
        - categories: Search categories for Searxng (optional)
        - time_range: Time filter for Searxng (optional)

        This implements Perplexica's query generation strategy with Searxng enhancements:
        - Start broad, then narrow down
        - Use different engines/categories for different query types
        - Explore different angles of the topic
        """
        base_query = query.lower().strip()

        # Iteration 0: Broad overview queries
        if iteration == 0:
            strategies = [
                {
                    "query": base_query,
                    "engines": ["duckduckgo", "wikipedia"],
                    "categories": ["general"],
                },
                {
                    "query": f"{base_query} overview",
                    "engines": ["duckduckgo", "brave"],
                    "categories": ["general"],
                },
            ]
            return strategies[:2] if mode == "speed" else strategies

        # Iteration 1+: Specialized queries based on mode
        if mode == "speed":
            # Speed mode: targeted queries only
            return [
                {"query": f"{base_query} latest"},
                {"query": f"{base_query} examples"},
            ]

        # Balanced/Quality: Multi-angle exploration with Searxng
        search_strategies = [
            # Features/capabilities - general search
            {
                "query": f"{base_query} features",
                "engines": ["duckduckgo", "bing"],
                "categories": ["general"],
            },
            {
                "query": f"{base_query} how it works",
                "engines": ["duckduckgo"],
                "categories": ["general"],
            },
            # Comparisons - use multiple engines for diverse perspectives
            {
                "query": f"{base_query} vs alternatives",
                "engines": ["duckduckgo", "brave", "bing"],
                "categories": ["general"],
            },
            {
                "query": f"{base_query} comparison",
                "engines": ["duckduckgo"],
                "categories": ["general"],
            },
            # Recent info - use news category with time filter
            {
                "query": f"{base_query} latest news",
                "engines": ["bing", "brave"],
                "categories": ["news"],
                "time_range": "week" if use_searxng else None,
            },
            {
                "query": f"{base_query} recent",
                "engines": ["duckduckgo"],
                "categories": ["news"],
                "time_range": "month" if use_searxng else None,
            },
            # Reviews/opinions
            {
                "query": f"{base_query} review",
                "engines": ["duckduckgo", "bing"],
                "categories": ["general"],
            },
            {
                "query": f"{base_query} analysis",
                "engines": ["brave"],
                "categories": ["general"],
            },
            # Use cases
            {
                "query": f"{base_query} examples",
                "engines": ["duckduckgo"],
                "categories": ["general"],
            },
            {
                "query": f"{base_query} use cases",
                "engines": ["bing"],
                "categories": ["general"],
            },
            # Limitations/critiques
            {
                "query": f"{base_query} problems",
                "engines": ["duckduckgo"],
                "categories": ["general"],
            },
            {
                "query": f"{base_query} limitations",
                "engines": ["brave"],
                "categories": ["general"],
            },
            # Technical/deep dive
            {
                "query": f"{base_query} technical",
                "engines": ["duckduckgo"],
                "categories": ["general"],
            },
            {
                "query": f"{base_query} explained",
                "engines": ["wikipedia", "duckduckgo"],
                "categories": ["general"],
            },
        ]

        # Select strategies based on iteration
        # For quality mode, we go through all strategies
        # For balanced mode, we skip some to stay within iteration limit
        strategy_idx = (iteration - 1) % len(search_strategies)

        # Return 1-2 strategies per iteration
        selected = [search_strategies[strategy_idx]]

        # For quality mode or early iterations, add a second strategy
        if mode == "quality" or iteration < 3:
            next_idx = (strategy_idx + 1) % len(search_strategies)
            selected.append(search_strategies[next_idx])

        # If not using Searxng, strip out Searxng-specific fields
        if not use_searxng:
            for strategy in selected:
                strategy.pop("engines", None)
                strategy.pop("categories", None)
                strategy.pop("time_range", None)

        return selected

    def _extract_findings(self, search_result: str, seen_urls: set) -> list[dict]:
        """
        Extract structured findings from search results.

        Handles multiple formats:
        - DuckDuckGo format
        - Brave format
        - Searxng format (includes "Engine:" field)

        Returns list of finding dicts with URL deduplication.
        """
        findings = []

        # Parse DuckDuckGo/Brave/Searxng format
        lines = search_result.split("\n")
        current_finding = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect URL lines (indented with spaces)
            if line.startswith("   ") or line.startswith("\t"):
                url = line.strip()
                if url.startswith("http"):
                    # Check for duplicate
                    if url not in seen_urls:
                        seen_urls.add(url)
                        if current_finding:
                            findings.append(current_finding)
                        current_finding = {"url": url, "title": "", "snippet": ""}
                elif current_finding:
                    # This is a snippet/description or metadata
                    if line.startswith("Engine:"):
                        current_finding["engine"] = line.replace("Engine:", "").strip()
                    elif line.startswith("Published:"):
                        current_finding["publishedDate"] = line.replace("Published:", "").strip()
                    else:
                        current_finding["snippet"] = line
            # Detect result number
            elif line[0].isdigit() and "." in line[:3]:
                if current_finding and current_finding.get("url"):
                    findings.append(current_finding)
                title_part = line.split(".", 1)[1].strip() if "." in line else line
                current_finding = {"title": title_part, "url": "", "snippet": ""}
            # Detect title (skip engine headers)
            elif not line.startswith("DuckDuckGo") and not line.startswith("Brave") and not line.startswith("Searxng"):
                if current_finding and not current_finding.get("title"):
                    current_finding["title"] = line

        # Add last finding
        if current_finding and current_finding.get("url"):
            findings.append(current_finding)

        return findings

    def _should_stop_early(
        self, iteration: int, iteration_findings: list[dict], mode: str
    ) -> bool:
        """
        Determine if research should stop early.

        Clones Perplexica's early stopping logic:
        - Speed mode: stop after first successful search
        - Balanced: stop if no new findings for 2 iterations
        - Quality: rarely stop early
        """
        if mode == "speed" and iteration >= 1:
            return len(iteration_findings) > 0

        if mode == "balanced" and iteration >= 3:
            return len(iteration_findings) == 0

        # Quality mode: only stop if completely stuck
        if mode == "quality" and iteration >= 10:
            return len(iteration_findings) == 0

        return False

    def _synthesize_results(
        self,
        query: str,
        findings: list[dict],
        search_history: list[dict],
        mode: str,
    ) -> str:
        """
        Synthesize research findings into a comprehensive report.

        Clones Perplexica's writer phase approach.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = {
            "query": query,
            "mode": mode,
            "timestamp": timestamp,
            "iterations_completed": len(search_history),
            "total_sources": len(findings),
            "search_history": search_history,
            "findings": findings[:20],  # Limit to top 20 findings
        }

        # Create a formatted summary
        summary_lines = [
            f"# Research Results: {query}",
            f"",
            f"**Mode:** {mode}",
            f"**Date:** {timestamp}",
            f"**Iterations:** {len(search_history)}",
            f"**Sources Found:** {len(findings)}",
            f"",
            f"## Research Process",
        ]

        for entry in search_history:
            summary_lines.append(
                f"- Iteration {entry['iteration']}: {entry['plan']} "
                f"({entry['new_sources']} new sources)"
            )

        summary_lines.extend([
            f"",
            f"## Key Findings",
            f"",
        ])

        # Add top findings
        for i, finding in enumerate(findings[:10], 1):
            summary_lines.append(f"### {i}. {finding.get('title', 'Untitled')}")
            if finding.get('url'):
                summary_lines.append(f"**Source:** {finding['url']}")
            if finding.get('snippet'):
                summary_lines.append(f"**Excerpt:** {finding['snippet']}")
            summary_lines.append("")

        if len(findings) > 10:
            summary_lines.append(f"*... and {len(findings) - 10} more sources*")

        result["summary"] = "\n".join(summary_lines)

        return json.dumps(result, indent=2)
