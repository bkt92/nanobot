# Perplexica vs Nanobot Research Architecture

## Perplexica Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Perplexica System                            │
└─────────────────────────────────────────────────────────────────────┘

User Query
    ↓
┌───────────────────────┐
│  API Endpoint         │
│  (POST /api/search)   │
└───────────────────────┘
    ↓
┌───────────────────────────────────────────────────────────────────┐
│  SearchAgent.searchAsync()                                         │
│  ┌─────────────────┐  ┌─────────────────┐                        │
│  │ 1. Classifier   │  │ 2. Widget       │                        │
│  │    - LLM call   │  │    Executor     │                        │
│  │    - Determine  │  │    - Weather    │                        │
│  │      sources    │  │    - Stocks     │                        │
│  │    - skip?      │  │    - Calc       │                        │
│  └────────┬────────┘  └─────────────────┘                        │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────┐                                              │
│  │ 3. Researcher   │                                              │
│  │    Loop:        │                                              │
│  │    for i in 0..max_iterations:                                 │
│  │      ┌─────────────────────────────────────┐                   │
│  │      │ 1. Get researcher prompt            │                   │
│  │      │    - different for speed/bal/quality│                   │
│  │      │    - includes tool descriptions     │                   │
│  │      └─────────────────────────────────────┘                   │
│  │      ┌─────────────────────────────────────┐                   │
│  │      │ 2. LLM streamText with tools        │                   │
│  │      │    - __reasoning_preamble (optional)│                   │
│  │      │    - web_search, academic_search,   │                   │
│  │      │      social_search, scrape_url,     │                   │
│  │      │      uploads_search, done           │                   │
│  │      └─────────────────────────────────────┘                   │
│  │      ┌─────────────────────────────────────┐                   │
│  │      │ 3. Emit research blocks             │                   │
│  │      │    - reasoning (plan)               │                   │
│  │      │    - searching (queries)            │                   │
│  │      │    - search_results (findings)      │                   │
│  │      └─────────────────────────────────────┘                   │
│  │      ┌─────────────────────────────────────┐                   │
│  │      │ 4. Execute tools (parallel)         │                   │
│  │      │    - ActionRegistry.executeAll()    │                   │
│  │      └─────────────────────────────────────┘                   │
│  │      ┌─────────────────────────────────────┐                   │
│  │      │ 5. Check if "done" called           │                   │
│  │      │    break if yes                     │                   │
│  │      └─────────────────────────────────────┘                   │
│  │                                                          │      │
│  └──────────────────────────────────────────────────────────┘      │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────┐                                              │
│  │ 4. Writer       │                                              │
│  │    - LLM call   │                                              │
│  │    - Synthesize │                                              │
│  │      findings   │                                              │
│  └─────────────────┘                                              │
└───────────────────────────────────────────────────────────────────┘
    ↓
JSON Response
- Newline-delimited stream
- Research blocks
- Final answer
```

## Nanobot Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Nanobot System                              │
└─────────────────────────────────────────────────────────────────────┘

User Query
    ↓
┌───────────────────────┐
│  Agent Loop           │
│  (Message Processing) │
└───────────────────────┘
    ↓
┌───────────────────────────────────────────────────────────────────┐
│  deep_research tool call                                          │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ ResearchTool.execute(query, mode)                           │ │
│  │                                                              │ │
│  │ Set max_iterations based on mode:                           │ │
│  │   - speed: 2                                                │ │
│  │   - balanced: 6                                             │ │
│  │   - quality: 25                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Iterative Research Loop                                      │ │
│  │ for iteration in range(max_iterations):                     │ │
│  │   ┌───────────────────────────────────────────────────────┐│ │
│  │   │ 1. Generate queries                                   ││ │
│  │   │    - _generate_queries()                              ││ │
│  │   │    - Strategy based on iteration & mode               ││ │
│  │   │    - Broad → Specific → Multi-angle                   ││ │
│  │   └───────────────────────────────────────────────────────┘│ │
│  │   ┌───────────────────────────────────────────────────────┐│ │
│  │   │ 2. Execute searches (parallel)                        ││ │
│  │   │    - asyncio.gather()                                 ││ │
│  │   │    - WebSearchTool.execute() for each query           ││ │
│  │   └───────────────────────────────────────────────────────┘│ │
│  │   ┌───────────────────────────────────────────────────────┐│ │
│  │   │ 3. Extract & deduplicate findings                     ││ │
│  │   │    - _extract_findings()                              ││ │
│  │   │    - Track seen_urls set                              ││ │
│  │   └───────────────────────────────────────────────────────┘│ │
│  │   ┌───────────────────────────────────────────────────────┐│ │
│  │   │ 4. Track search history                               ││ │
│  │   │    - iteration, queries, new_sources, plan            ││ │
│  │   └───────────────────────────────────────────────────────┘│ │
│  │   ┌───────────────────────────────────────────────────────┐│ │
│  │   │ 5. Check early stopping                               ││ │
│  │   │    - _should_stop_early()                             ││ │
│  │   │    - Mode-specific logic                              ││ │
│  │   └───────────────────────────────────────────────────────┘│ │
│  │   Break if stop condition met                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Synthesize Results                                           │ │
│  │ _synthesize_results()                                        │ │
│  │  - Create markdown summary                                  │ │
│  │  - Format research process timeline                        │ │
│  │  - List top findings with citations                        │ │
│  │  - Return structured JSON                                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────┘
    ↓
JSON Response
- summary (markdown)
- findings (with URLs)
- search_history
- metadata
```

## Key Component Mapping

| Perplexica | Nanobot | Notes |
|-----------|---------|-------|
| `SearchAgent.searchAsync()` | `ResearchTool.execute()` | Main entry point |
| `classify()` | Direct tool call | No LLM classification |
| `Researcher.research()` | Iterative loop | Same pattern, simplified |
| `ActionRegistry` | `_generate_queries()` | Different approach |
| `getResearcherPrompt()` | Query strategies | Template vs LLM |
| `session.emitBlock()` | `search_history` list | No streaming |
| `__reasoning_preamble` | `current_plan` string | No tool call |
| `Writer` (LLM call) | `_synthesize_results()` | Template vs LLM |
| `web_search` action | `WebSearchTool` | Reused existing |
| `scrape_url` action | `WebFetchTool` | Reused existing |
| SearxNG integration | DuckDuckGo/Brave | Different search |

## Data Flow Comparison

### Perplexica Data Flow
```
Query
  → LLM Classification (sources, skip?)
  → Researcher Loop
    → LLM Plan + Tool Calls
    → SearxNG Search
    → HTML Scraping
    → Embedding Rerank
    → LLM Writer
  → Streamed JSON Response
```

### Nanobot Data Flow
```
Query
  → Research Tool
  → Query Strategy Generation
  → Parallel WebSearchTool calls
  → Result Extraction & Dedup
  → Template-based Synthesis
  → JSON Response
```

## Complexity Comparison

### Perplexica
- **Total LLM calls per query**: 3-30 (classification + researcher iterations + writer)
- **External dependencies**: SearxNG, embedding model
- **Lines of code**: ~2000+ (full search system)
- **Features**: Streaming, reasoning blocks, multiple sources, file uploads

### Nanobot
- **Total LLM calls per query**: 0-1 (optional for synthesis)
- **External dependencies**: DuckDuckGo/Brave API
- **Lines of code**: ~400 (research tool only)
- **Features**: JSON output, progress tracking, URL deduplication

## Performance Characteristics

### Speed
```
Perplexica:  ~15-60s (classification + 6-25 iterations + writer)
Nanobot:     ~5-20s (direct search + template synthesis)
Speedup:     ~3x faster (no intermediate LLM calls)
```

### Quality
```
Perplexica:  Higher (LLM-optimized queries and synthesis)
Nanobot:     Good (multi-angle strategies, template synthesis)
Trade-off:   Simplicity vs intelligence
```

### Cost
```
Perplexica:  ~15-30 LLM calls per research
Nanobot:     ~0-1 LLM calls per research
Cost savings: ~95% reduction
```

## Integration Points

### Perplexica
- Next.js frontend
- API routes
- SearxNG backend
- PostgreSQL database
- Redis cache
- File upload storage

### Nanobot
- CLI interface
- Agent loop
- Tool registry
- Message bus
- Session manager
- Memory store

## When to Use Each

### Use Perplexica when:
- You need a full-featured search UI
- Streaming progress updates are critical
- Multiple search sources (web, academic, discussions)
- File upload support required
- Embedding-based reranking needed
- Full-featured self-hosted solution

### Use Nanobot Research Tool when:
- You want simple programmatic research
- Fast results are more important than optimization
- You already have nanobot deployed
- You need to integrate research into agent workflows
- Lower API costs are important
- You prefer simplicity and transparency
