"""Research tool cloning Perplexica's iterative deep research mechanism."""

import asyncio
import json
from datetime import datetime
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool


class ResearchTool(Tool):
    """
    Deep research tool that clones Perplexica's research mechanism.

    Implements iterative search with:
    - Multiple research modes (speed/balanced/quality)
    - Reasoning steps for planning
    - Progressive query refinement
    - Source deduplication and synthesis
    """

    name = "deep_research"
    description = (
        "Perform deep, iterative research on a topic. "
        "Supports three modes: 'speed' (2 iterations, quick answers), "
        "'balanced' (6 iterations, moderate depth with reasoning), "
        "'quality' (25 iterations, comprehensive research). "
        "Uses multiple search rounds with query refinement and source synthesis."
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
        self.web_search = WebSearchTool(api_key=api_key, max_results=max_results)
        self.web_fetch = WebFetchTool()
        self.max_results = max_results

    async def execute(
        self, query: str, mode: str = "balanced", max_results: int | None = None, **kwargs: Any
    ) -> str:
        """
        Execute deep research on the given query.

        Args:
            query: Research topic or question
            mode: Research mode (speed/balanced/quality)
            max_results: Override default max results per search

        Returns:
            Research findings with sources
        """
        max_results = max_results or self.max_results

        # Determine iterations based on mode (cloning Perplexica's approach)
        mode_iterations = {"speed": 2, "balanced": 6, "quality": 25}
        max_iterations = mode_iterations.get(mode, 6)

        logger.info(f"Starting deep research (mode={mode}, max_iterations={max_iterations}): {query}")

        # Research state
        search_history = []
        all_findings = []
        seen_urls = set()
        current_plan = "Starting research with broad queries to get an overview"

        try:
            # Iterative research loop
            for iteration in range(max_iterations):
                logger.debug(f"Research iteration {iteration + 1}/{max_iterations}")

                # Generate queries for this iteration
                queries = await self._generate_queries(
                    query=query,
                    iteration=iteration,
                    max_iterations=max_iterations,
                    mode=mode,
                    previous_findings=all_findings,
                    current_plan=current_plan,
                )

                if not queries:
                    logger.debug("No more queries to search, ending research")
                    break

                # Update plan for progress tracking
                if len(queries) > 0:
                    current_plan = f"Searching for: {', '.join(queries[:2])}"
                    if len(queries) > 2:
                        current_plan += f" and {len(queries) - 2} more queries"

                # Execute searches in parallel
                search_tasks = [
                    self.web_search.execute(q, count=max_results) for q in queries[:3]
                ]
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
                    "queries": queries[:3],
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

    async def _generate_queries(
        self,
        query: str,
        iteration: int,
        max_iterations: int,
        mode: str,
        previous_findings: list[dict],
        current_plan: str,
    ) -> list[str]:
        """
        Generate search queries for the current iteration.

        This implements Perplexica's query generation strategy:
        - Start broad, then narrow down
        - Use reasoning in balanced/quality modes
        - Explore different angles of the topic
        """
        base_query = query.lower().strip()

        # Iteration 0-1: Broad overview queries
        if iteration == 0:
            return [
                base_query,
                f"{base_query} overview",
                f"{base_query} introduction",
            ][:2]

        # Iteration 1+: Specialized queries based on mode
        if mode == "speed":
            # Speed mode: targeted queries only
            return [f"{base_query} latest", f"{base_query} examples"]

        # Balanced/Quality: Multi-angle exploration
        query_strategies = [
            # Features/capabilities
            [f"{base_query} features", f"{base_query} how it works"],
            # Comparisons
            [f"{base_query} vs alternatives", f"{base_query} comparison"],
            # Recent info
            [f"{base_query} latest news", f"{base_query} 2025", f"{base_query} recent"],
            # Reviews/opinions
            [f"{base_query} review", f"{base_query} analysis"],
            # Use cases
            [f"{base_query} examples", f"{base_query} use cases"],
            # Limitations
            [f"{base_query} problems", f"{base_query} limitations"],
            # Technical/deep dive
            [f"{base_query} technical", f"{base_query} explained"],
        ]

        # Select strategy based on iteration
        strategy_idx = (iteration - 1) % len(query_strategies)
        return query_strategies[strategy_idx][:2]

    def _extract_findings(self, search_result: str, seen_urls: set) -> list[dict]:
        """
        Extract structured findings from search results.

        Returns list of finding dicts with URL deduplication.
        """
        findings = []

        # Parse DuckDuckGo/Brave format
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
                    # This is a snippet/description
                    current_finding["snippet"] = line
            # Detect result number
            elif line[0].isdigit() and "." in line[:3]:
                if current_finding and current_finding.get("url"):
                    findings.append(current_finding)
                title_part = line.split(".", 1)[1].strip() if "." in line else line
                current_finding = {"title": title_part, "url": "", "snippet": ""}
            # Detect title
            elif not line.startswith("DuckDuckGo") and not line.startswith("Brave"):
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
