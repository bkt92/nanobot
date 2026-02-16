# Searxng Integration Guide

This guide explains how to use Searxng's multi-engine search capabilities in nanobot.

## Overview

Searxng is a metasearch engine that aggregates results from 70+ search engines. The integration provides:

- **Multiple search engines**: DuckDuckGo, Brave, Bing, Google, Wikipedia, and more
- **Rich categories**: General web, images, videos, news, science, IT, etc.
- **Time filters**: Day, week, month, year
- **No API keys**: Most engines work without authentication
- **Privacy-focused**: Many engines respect user privacy

## Configuration

### Environment Variables

```bash
# Path to Searxng installation (default: /root/nanobot/searxng)
export SEARXNG_PATH="/path/to/searxng"

# Optional: Brave API key for Brave search engine
export BRAVE_API_KEY="your-api-key"
```

### Configuration File

Add to your `config.yaml`:

```yaml
tools:
  web:
    search:
      engine: "searxng"  # or "auto", "ddg", "brave"
      max_results: 5
      api_key: ""  # Brave API key

      # Searxng-specific options
      searxng_path: "/root/nanobot/searxng"
      searxng_enabled: true
      default_engines:
        - duckduckgo
        - brave
        - bing
      default_categories:
        - general
```

## Usage

### WebSearchTool

#### Basic Search

```python
from nanobot.agent.tools.web import WebSearchTool

# Use Searxng (multi-engine)
tool = WebSearchTool(engine="searxng")
result = await tool.execute("python programming", count=5)
print(result)
```

Output:
```
Searxng results for: python programming (engines: duckduckgo, brave)

1. Python Programming
   https://www.python.org
   Official Python documentation and tutorials. Learn to program in Python.
   Engine: duckduckgo

2. Python Tutorial - W3Schools
   https://www.w3schools.com/python/
   Learn Python from scratch. Interactive examples and exercises.
   Engine: brave
```

#### Multi-Engine Search

```python
result = await tool.execute(
    query="machine learning",
    engines=["duckduckgo", "brave", "bing"],
    categories=["general"],
    count=5
)
```

#### News Search with Time Filter

```python
result = await tool.execute(
    query="artificial intelligence",
    categories=["news"],
    time_range="week",  # day, week, month, year
    count=5
)
```

#### Image Search

```python
result = await tool.execute(
    query="python logo",
    categories=["images"],
    count=3
)
```

### ResearchTool

The ResearchTool automatically uses Searxng when available for multi-source research.

```python
from nanobot.agent.tools.research import ResearchTool

tool = ResearchTool(max_results=3)

# Speed mode with Searxng
result = await tool.execute(
    query="quantum computing",
    mode="speed",
    use_searxng=True
)
```

The ResearchTool uses different engines and categories based on query strategy:

- **Overview queries**: duckduckgo, wikipedia (general)
- **Comparison queries**: duckduckgo, brave, bing (general)
- **Recent news**: bing, brave (news, time_range="week")
- **Technical queries**: duckduckgo, wikipedia (general)
- **Reviews**: duckduckgo, bing (general)

### Direct SearxngClient

For advanced usage, you can use the SearxngClient directly:

```python
from nanobot.agent.tools.searxng_client import SearxngClient

client = SearxngClient()

# Basic search
results = client.search(
    query="machine learning",
    engines=["duckduckgo", "brave"],
    categories=["general"],
    lang="en",
    safesearch=0,
    count=10
)

for result in results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Engine: {result['engine']}")
    print(f"Score: {result['score']}")
    print()
```

## API Reference

### SearxngClient

```python
class SearxngClient:
    def __init__(self, searxng_path: str | None = None)
    def initialize(self) -> bool
    def search(
        self,
        query: str,
        engines: list[str] | None = None,
        categories: list[str] | None = None,
        lang: str = "en",
        safesearch: int = 0,
        time_range: str | None = None,
        count: int = 10
    ) -> list[dict]
    def get_available_engines(self) -> list[str]
    def get_available_categories(self) -> list[str]
```

### WebSearchTool Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query (required) |
| `count` | int | Number of results (1-10) |
| `engine` | str | Engine: "searxng", "ddg", "brave" |
| `engines` | list[str] | For searxng: specific engines to use |
| `categories` | list[str] | For searxng: search categories |
| `time_range` | str | For searxng: "day", "week", "month", "year" |

### ResearchTool Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Research topic (required) |
| `mode` | str | "speed", "balanced", "quality" |
| `max_results` | int | Max results per search (1-10) |
| `use_searxng` | bool | Use Searxng multi-engine search |

## Available Engines

Common engines available in Searxng:

- `duckduckgo` - General web search (default)
- `brave` - Privacy-focused search
- `bing` - Microsoft Bing
- `google` - Google Search
- `wikipedia` - Wikipedia encyclopedia
- `startpage` - Privacy metasearch

Check available engines:
```python
client = SearxngClient()
engines = client.get_available_engines()
print(engines)
```

## Available Categories

- `general` - General web search (default)
- `images` - Image search
- `videos` - Video search
- `news` - News articles
- `map` - Maps
- `music` - Music
- `it` - IT/Technology
- `science` - Science
- `files` - File search
- `social media` - Social media

## Examples

### Example 1: Comprehensive Research

```python
from nanobot.agent.tools.research import ResearchTool

tool = ResearchTool(max_results=5)

# Quality mode for comprehensive research
result = await tool.execute(
    query="renewable energy storage technologies",
    mode="quality",
    use_searxng=True
)

import json
data = json.loads(result)
print(f"Iterations: {data['iterations_completed']}")
print(f"Sources: {data['total_sources']}")
print(data['summary'])
```

### Example 2: News Monitoring

```python
from nanobot.agent.tools.web import WebSearchTool

tool = WebSearchTool(engine="searxng")

# Get recent news about AI
result = await tool.execute(
    query="artificial intelligence breakthrough",
    categories=["news"],
    time_range="day",
    count=10
)
```

### Example 3: Multi-Engine Comparison

```python
from nanobot.agent.tools.web import WebSearchTool

tool = WebSearchTool(engine="searxng")

# Compare results from multiple engines
result = await tool.execute(
    query="best python frameworks 2025",
    engines=["duckduckgo", "brave", "bing"],
    categories=["general"],
    count=5
)
```

## Troubleshooting

### Searxng Not Available

**Problem**: `Searxng is not available` error

**Solutions**:
1. Check SEARXNG_PATH environment variable
2. Verify Searxng is installed at the path
3. Check file permissions

```bash
echo $SEARXNG_PATH
ls -la $SEARXNG_PATH/searx
```

### Engine Failures

**Problem**: Some engines return no results

**Solutions**:
1. Try different engines
2. Check network connectivity
3. Some engines may be rate-limited

```python
# Fallback to specific engines
result = await tool.execute(
    query="your query",
    engines=["duckduckgo"],  # Use only reliable engines
    count=5
)
```

### Initialization Errors

**Problem**: Searxng initialization fails

**Solutions**:
1. Check Searxng settings configuration
2. Verify dependencies are installed
3. Check Searxng logs

```bash
cd /root/nanobot/searxng
python -c "from searx.search import initialize; initialize()"
```

## Performance Tips

1. **Use specific engines**: Limit engines to reduce search time
   ```python
   engines=["duckduckgo", "brave"]  # Faster than engines=["duckduckgo", "brave", "bing", "google"]
   ```

2. **Limit results**: Reduce count for faster responses
   ```python
   count=3  # Faster than count=10
   ```

3. **Use appropriate mode**: Speed mode for quick answers
   ```python
   mode="speed"  # 2 iterations vs 25 for quality
   ```

4. **Cache results**: Store frequently searched queries

## Comparison with Original Engines

| Feature | Searxng | DuckDuckGo | Brave API |
|---------|---------|------------|-----------|
| Engines | 70+ | 1 | 1 |
| Categories | 10+ | 1 | 1 |
| Time Filters | ✓ | ✗ | ✓ |
| API Key | Not required | Not required | Required |
| Privacy | High | High | High |
| Result Quality | High | Good | Good |
| Speed | Medium | Fast | Fast |

## Migration Guide

### From DuckDuckGo to Searxng

**Before**:
```python
tool = WebSearchTool(engine="ddg")
result = await tool.execute("query")
```

**After**:
```python
tool = WebSearchTool(engine="searxng")
result = await tool.execute("query")
# Results now include multiple engines!
```

### From Brave API to Searxng

**Before**:
```python
tool = WebSearchTool(engine="brave", api_key="your-key")
result = await tool.execute("query")
```

**After**:
```python
tool = WebSearchTool(engine="searxng")
result = await tool.execute("query", engines=["brave"])
# No API key needed!
```

## Testing

Run the integration test suite:

```bash
cd /root/nanobot
python test_searxng_integration.py
```

This will test:
- SearxngClient initialization and search
- WebSearchTool with Searxng engine
- ResearchTool with Searxng multi-source search
- Fallback behavior when Searxng unavailable

## Advanced Configuration

### Custom Engine Selection

Create custom engine combinations for specific use cases:

```python
# For academic research
academic_engines = ["google", "bing", "wikipedia"]

# For privacy-focused search
privacy_engines = ["duckduckgo", "brave", "startpage"]

# For comprehensive results
comprehensive_engines = ["duckduckgo", "brave", "bing", "google"]
```

### Category-Specific Strategies

```python
# Technology news
tech_news = {
    "engines": ["bing", "brave"],
    "categories": ["news", "science"],
    "time_range": "week"
}

# General research
general_research = {
    "engines": ["duckduckgo", "wikipedia"],
    "categories": ["general", "science"]
}
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Searxng documentation: https://docs.searxng.org
3. Run test suite: `python test_searxng_integration.py`
4. Check nanobot logs for error messages
