# Perplexica Research Mechanism - Implementation Notes

This document explains how the research skill clones Perplexica's research mechanism.

## Architecture Overview

Perplexica's research system consists of several key components that have been adapted:

### 1. Research Agent (src/lib/agents/search/researcher/index.ts)

**Original Perplexica Flow:**
```
Query → Classifier → Researcher (iterative loop) → Writer → Answer
           ↓              ↓
         Sources     Action Registry
                      (web_search, academic_search,
                       social_search, scrape_url, plan, done)
```

**Nanobot Implementation:**
```
Query → deep_research tool → Iterative search loop → Synthesis → JSON results
                                   ↓
                            Query Strategies
                            (broad → specific → multi-angle)
```

### 2. Mode-Based Iterations

Perplexica uses different iteration counts based on mode:

| Mode | Iterations | Description |
|------|-----------|-------------|
| speed | 2 | Quick answers, minimal searching |
| balanced | 6 | Moderate depth with reasoning steps |
| quality | 25 | Comprehensive deep research |

This is preserved in `ResearchTool.execute()`:
```python
mode_iterations = {"speed": 2, "balanced": 6, "quality": 25}
max_iterations = mode_iterations.get(mode, 6)
```

### 3. Action Registry (src/lib/agents/search/researcher/actions/registry.ts)

Perplexica has a dynamic action registry that:
- Registers available research actions
- Filters actions based on classification
- Executes actions in parallel
- Returns structured outputs

Nanobot's implementation uses:
- `_generate_queries()` - Implements query strategy rotation
- `WebSearchTool` - Reuses existing search infrastructure
- Parallel execution via `asyncio.gather()`

### 4. Query Generation Strategy

Perplexica's researcher uses different query strategies per iteration:

**Speed Mode:** Targeted queries only
```
iteration 0: [base_query, "overview", "introduction"]
iteration 1: [base_query + "latest", "examples"]
```

**Balanced Mode:** Progressive refinement
```
iteration 0: Broad overview
iteration 1+: Features, comparisons, recent info, reviews, etc.
```

**Quality Mode:** Exhaustive multi-angle search
```
- Core definition/overview
- Features/capabilities
- Comparisons
- Recent news/updates
- Reviews/opinions
- Use cases
- Limitations/critiques
- Technical details
```

This is implemented in `_generate_queries()` with query_strategies.

### 5. Reasoning Steps

Perplexica uses `__reasoning_preamble` tool calls to:
- Outline research approach
- Reflect on results
- Plan next steps
- Provide transparency

Nanobot's implementation tracks reasoning in `current_plan` variable
and includes it in search_history for output.

### 6. Source Deduplication

Perplexica deduplicates URLs and merges content:
```typescript
const seenUrls = new Map<string, number>();
// Merges content from same URL
```

Nanobot's implementation:
```python
seen_urls = set()
def _extract_findings(search_result, seen_urls):
    # Check URL against seen_urls set
    # Only add if not seen before
```

### 7. Research Blocks (Session Management)

Perplexica emits research progress blocks:
- `reasoning` - Research plan/thought process
- `searching` - Current queries being executed
- `search_results` - Results being processed

Nanobot tracks this in `search_history`:
```python
search_history.append({
    "iteration": iteration + 1,
    "queries": queries[:3],
    "new_sources": len(iteration_findings),
    "plan": current_plan,
})
```

### 8. Early Stopping Logic

Perplexica's `shouldStopEarly`:
- Speed: Stop after first successful search
- Balanced: Stop if no new findings for 2 iterations
- Quality: Rarely stop early

Nanobot's `_should_stop_early()` implements the same logic.

### 9. Writer Phase (Synthesis)

Perplexica's writer synthesizes findings with citations:
```typescript
const finalContext = searchResults.searchFindings
  .map((f, index) =>
    `<result index=${index + 1} title=${f.metadata.title}>${f.content}</result>`
  )
  .join('\n');
```

Nanobot's `_synthesize_results()`:
- Creates markdown-formatted summary
- Includes research process timeline
- Lists top findings with sources
- Returns structured JSON output

## Key Differences from Perplexica

### Simplified Approach
1. **No LLM-based classification** - Perplexica classifies queries to determine sources; nanobot uses direct tool calls
2. **No separate writer agent** - Perplexica uses another LLM call for synthesis; nanobot uses template-based synthesis
3. **No SearxNG dependency** - Perplexica requires SearxNG; nanobot uses DuckDuckGo/Brave directly
4. **Single tool interface** - Simpler API with `deep_research(query, mode)`

### Advantages
- Faster execution (fewer LLM calls)
- Simpler deployment (no external search service)
- Lower cost (no intermediate LLM classifications)
- Easier to understand and modify

### Trade-offs
- Less intelligent query classification
- Template-based vs LLM-based synthesis
- No reasoning preamble tool calls in output
- Simpler prompt engineering

## Usage Example

```python
# Speed mode - quick answers
result = await research_tool.execute(
    query="What is GPT-5?",
    mode="speed"
)

# Balanced mode - moderate depth
result = await research_tool.execute(
    query="Latest developments in quantum computing",
    mode="balanced"
)

# Quality mode - comprehensive research
result = await research_tool.execute(
    query="Comprehensive analysis of renewable energy storage technologies",
    mode="quality"
)
```

## Future Enhancements

To more closely match Perplexica's capabilities:

1. **LLM-based classification** - Classify query type and optimal sources
2. **Reasoning tool** - Add `__reasoning_preamble` tool for transparency
3. **Multi-source support** - Add academic_search, social_search actions
4. **LLM synthesis** - Use LLM for final answer generation
5. **Streaming output** - Stream research progress in real-time
6. **Embedding-based reranking** - Rerank results by relevance
7. **File upload support** - Search uploaded documents like Perplexica
8. **Domain-specific search** - Restrict search to specific domains

## References

- Perplexica: https://github.com/ItzCrazyKns/Perplexica
- Researcher implementation: src/lib/agents/search/researcher/
- Action registry: src/lib/agents/search/researcher/actions/registry.ts
- Researcher prompts: src/lib/prompts/search/researcher.ts
