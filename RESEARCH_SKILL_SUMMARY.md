# Research Skill Implementation Summary

This document summarizes the implementation of the research skill that clones Perplexica's mechanism for nanobot.

## What Was Created

### 1. Research Tool (`nanobot/agent/tools/research.py`)

A new `ResearchTool` class that implements Perplexica's iterative deep research mechanism:

**Key Features:**
- Three research modes: `speed` (2 iterations), `balanced` (6 iterations), `quality` (25 iterations)
- Iterative query generation with progressive refinement
- URL deduplication to avoid duplicate sources
- Parallel search execution for efficiency
- Structured JSON output with findings and research history
- Early stopping logic based on mode and results

**Core Methods:**
- `execute()` - Main entry point, runs the research loop
- `_generate_queries()` - Creates search queries for each iteration based on mode
- `_extract_findings()` - Parses search results and deduplicates URLs
- `_should_stop_early()` - Implements Perplexica's early stopping logic
- `_synthesize_results()` - Creates formatted summary with citations

### 2. Research Skill (`nanobot/skills/research/SKILL.md`)

Documentation for the research skill following nanobot's skill format:
- YAML frontmatter with metadata
- Usage instructions and examples
- Mode descriptions
- Best practices

### 3. Technical Documentation (`nanobot/skills/research/PERPLEXICA_CLONE.md`)

Detailed technical documentation explaining:
- Architecture comparison between Perplexica and nanobot
- Implementation details of each component
- Query generation strategies
- Key differences and trade-offs
- Future enhancement ideas

### 4. Agent Loop Integration (`nanobot/agent/loop.py`)

Modified to register the `ResearchTool`:
- Added import for `ResearchTool`
- Registered tool in `_register_default_tools()` method
- Tool now available to all agents

### 5. Test Script (`test_research.py`)

Comprehensive test script to verify:
- Query generation strategies for each mode
- Full research execution
- Result parsing and display
- Error handling

## How It Works

```
User Query
    ↓
deep_research(query, mode)
    ↓
┌─────────────────────────────────────┐
│  Iterative Research Loop             │
│  ┌─────────────────────────────────┐│
│  │ 1. Generate queries for this     ││
│  │    iteration (broad → specific)  ││
│  └─────────────────────────────────┘│
│  ┌─────────────────────────────────┐│
│  │ 2. Execute searches in parallel  ││
│  │    (using WebSearchTool)         ││
│  └─────────────────────────────────┘│
│  ┌─────────────────────────────────┐│
│  │ 3. Extract & deduplicate findings││
│  └─────────────────────────────────┘│
│  ┌─────────────────────────────────┐│
│  │ 4. Check if should stop early    ││
│  └─────────────────────────────────┘│
│  ┌─────────────────────────────────┐│
│  │ 5. Repeat until max iterations   ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
    ↓
Synthesize Results
    ↓
JSON Output with:
- Summary (markdown-formatted)
- Research process timeline
- Top findings with citations
- Complete search history
```

## Query Generation Strategy

### Speed Mode (2 iterations)
```
Iteration 0: [query, "overview", "introduction"]
Iteration 1: [query + "latest", "examples"]
Stop if any results found
```

### Balanced Mode (6 iterations)
```
Iteration 0: Broad overview
Iteration 1+: Features → Comparisons → Recent → Reviews → Use Cases → Limitations
Stop if 0 new findings for 2+ iterations
```

### Quality Mode (25 iterations)
```
Iteration 0: Broad overview
Iteration 1-24: Cycle through all strategies
- Core definition/overview
- Features/capabilities
- Comparisons with alternatives
- Recent news/updates
- Reviews/opinions from experts
- Use cases and applications
- Limitations/critiques
- Technical/deep dive
Rarely stops early
```

## Usage Examples

### Basic Usage
```python
from nanobot.agent.tools.research import ResearchTool

tool = ResearchTool(max_results=5)

# Speed mode - quick answers
result = await tool.execute(
    query="What is GPT-5?",
    mode="speed"
)

# Balanced mode - moderate depth
result = await tool.execute(
    query="Latest developments in quantum computing",
    mode="balanced"
)

# Quality mode - comprehensive research
result = await tool.execute(
    query="Comprehensive analysis of renewable energy storage",
    mode="quality"
)
```

### Via Agent (CLI)
```
User: Research the latest developments in quantum computing
Agent: [Uses deep_research tool with balanced mode]

User: Give me a quick overview of GPT-5
Agent: [Uses deep_research tool with speed mode]

User: I need comprehensive analysis of renewable energy storage
Agent: [Uses deep_research tool with quality mode]
```

## Output Format

```json
{
  "query": "artificial intelligence",
  "mode": "balanced",
  "timestamp": "2025-02-16 12:34:56",
  "iterations_completed": 6,
  "total_sources": 15,
  "search_history": [
    {
      "iteration": 1,
      "queries": ["artificial intelligence", "overview"],
      "new_sources": 5,
      "plan": "Searching for: artificial intelligence, overview"
    }
  ],
  "findings": [
    {
      "title": "Artificial Intelligence - Wikipedia",
      "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "snippet": "Artificial intelligence (AI) is intelligence demonstrated..."
    }
  ],
  "summary": "# Research Results: artificial intelligence\n\n..."
}
```

## Comparison with Perplexica

### Similarities
✓ Iterative research loop with mode-based iterations
✓ Progressive query refinement (broad → specific)
✓ URL deduplication and content merging
✓ Early stopping logic
✓ Multi-angle search strategies
✓ Source citation in results

### Differences
✗ No LLM-based query classification (simpler, faster)
✗ No separate writer agent (template-based synthesis)
✗ No SearxNG dependency (uses DuckDuckGo/Brave directly)
✗ Single tool interface (simpler API)
✗ No reasoning preamble tool calls in output

### Advantages
- **Faster**: Fewer LLM calls (no intermediate classifications)
- **Simpler**: Easier to understand and modify
- **Cheaper**: Lower API costs
- **Self-contained**: No external search service needed

### Trade-offs
- **Less intelligent**: No LLM-based query optimization
- **Template synthesis**: Not as sophisticated as Perplexica's writer
- **Simpler prompts**: Less elaborate prompt engineering

## Testing

Run the test script to verify the implementation:

```bash
cd /root/nanobot
python test_research.py
```

This will:
1. Test query generation strategies for each mode
2. Run full research queries in each mode
3. Display results and research process
4. Verify error handling

## Files Modified/Created

### Created
- `nanobot/agent/tools/research.py` - Research tool implementation
- `nanobot/skills/research/SKILL.md` - Skill documentation
- `nanobot/skills/research/PERPLEXICA_CLONE.md` - Technical documentation
- `test_research.py` - Test script

### Modified
- `nanobot/agent/loop.py` - Added ResearchTool registration
- `nanobot/skills/README.md` - Added research skill to list

## Future Enhancements

To more closely match Perplexica's capabilities:

1. **LLM-based classification** - Classify query type and optimal sources
2. **Reasoning tool** - Add `__reasoning_preamble` tool for transparency
3. **Multi-source support** - Add academic_search, social_search actions
4. **LLM synthesis** - Use LLM for final answer generation
5. **Streaming output** - Stream research progress in real-time
6. **Embedding-based reranking** - Rerank results by relevance
7. **File upload support** - Search uploaded documents
8. **Domain-specific search** - Restrict search to specific domains

## Integration with Nanobot

The research tool is now available to all agents through the standard tool registry. Agents can use it naturally:

```
User: Can you research the latest developments in AI?
Agent: I'll use the deep_research tool to gather comprehensive information about recent AI developments.
[Agent calls deep_research with query="latest developments in AI", mode="balanced"]
```

The tool integrates seamlessly with:
- **Message tool** - Can send progress updates
- **Spawn tool** - Can spawn subagents for parallel research
- **Memory system** - Research results can be stored in memory
- **Todo tool** - Can create tasks for multi-step research
