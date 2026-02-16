# Searxng HTTP Integration Guide

This guide explains how to run Searxng as a separate server and integrate it with nanobot via HTTP API.

## Overview

Searxng runs as a standalone web service, and nanobot makes HTTP requests to it for search. This approach:

- **Cleaner separation**: Searxng runs independently
- **No dependency conflicts**: No need to install Searxng dependencies in nanobot
- **Easier updates**: Update Searxng without restarting nanobot
- **Resource isolation**: Searxng can run on a different server
- **Simpler setup**: Just point to SEARXNG_URL

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  nanobot process                                            │
│    │                                                        │
│    ├── WebSearchTool (engine="searxng")                     │
│    │   │                                                    │
│    │   └── SearxngHttpClient                               │
│    │        │                                               │
│    │        └── HTTP GET /search?q=query&format=json      │
│    │                   │                                    │
└────────────────────────│────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Searxng Server (separate process)                          │
│    │                                                        │
│    ├── Flask webapp.py                                      │
│    ├── Search engines (70+)                                 │
│    └── Result aggregation                                   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start Searxng Server

```bash
cd /root/nanobot/searxng

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Start Searxng server (default: http://localhost:8888)
python searx/webapp.py
```

Searxng will start on `http://localhost:8888` by default.

### 2. Configure nanobot

Set the `SEARXNG_URL` environment variable:

```bash
export SEARXNG_URL="http://localhost:8888"

# Or add to your nanobot config
python -m nanobot.cli
```

### 3. Use Searxng in nanobot

```python
from nanobot.agent.tools.web import WebSearchTool

tool = WebSearchTool(engine="searxng")
result = await tool.execute("python programming")
print(result)
```

## Running Searxng as a Service

### Option 1: systemd Service

Create `/etc/systemd/system/searxng.service`:

```ini
[Unit]
Description=Searxng Metasearch Engine
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/root/nanobot/searxng
Environment="SEARXNG_SETTINGS_PATH=/root/nanobot/searxng/searx/settings.yml"
ExecStart=/usr/bin/python3 /root/nanobot/searxng/searx/webapp.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable searxng
sudo systemctl start searxng
sudo systemctl status searxng
```

### Option 2: Docker

```bash
cd /root/nanobot/searxng

# Build image
docker build -t searxng .

# Run container
docker run -d \
  --name searxng \
  -p 8888:8888 \
  -v /root/nanobot/searxng:/etc/searxng \
  searxng
```

### Option 3: Background Process with screen/tmux

```bash
# Using tmux
tmux new-session -d -s searxng
tmux send-keys -t searxng "cd /root/nanobot/searxng" Enter
tmux send-keys -t searxng "python searx/webapp.py" Enter

# Attach to view logs
tmux attach -t searxng

# Detach: Ctrl+B, D
```

## Configuration

### Searxng Server Configuration

Edit `/root/nanobot/searxng/searx/settings.yml`:

```yaml
# Server settings
server:
  # Must be 0.0.0.0 to accept connections from other machines
  bind_address: "0.0.0.0"
  port: 8888
  secret_key: "your-secret-key-here"  # Generate with: openssl rand -hex 32

  # CORS settings (if nanobot runs on different domain)
  methods: "GET, POST"
  cors:
    access_control_allow_origin: "*"
    access_control_allow_methods: "GET, POST"
    access_control_allow_headers: "Content-Type, X-Requested-With"

# Search settings
search:
  # Safe search (0: none, 1: moderate, 2: strict)
  safe_search: 0

  # Default language
  language: "en"

  # Default engines (remove engines you don't want)
  engines:
    - name: duckduckgo
      enabled: true

    - name: brave
      enabled: true

    - name: bing
      enabled: true

    - name: google
      enabled: false  # Google may require configuration

    - name: wikipedia
      enabled: true

    # ... more engines in settings.yml

# Result limits
result_proxy:
  # Maximum result timeout
  timeout: 3.0

# Limit maximum requests
limits:
  # Maximum queries per minute (0: no limit)
  request_timeout: 3.0
```

### nanobot Configuration

```yaml
# config.yaml
tools:
  web:
    search:
      engine: "searxng"  # Use Searxng by default
      max_results: 5
      api_key: ""  # Brave API key (for brave engine)

      # Searxng HTTP client configuration
      searxng_url: "http://localhost:8888"  # Searxng server URL
      default_engines:
        - duckduckgo
        - brave
        - bing
      default_categories:
        - general
```

### Environment Variables

```bash
# Required: Searxng server URL
export SEARXNG_URL="http://localhost:8888"

# Optional: Searxng API timeout (seconds)
export SEARXNG_TIMEOUT="30"

# Optional: Brave API key (for brave engine fallback)
export BRAVE_API_KEY="your-brave-api-key"
```

## Usage Examples

### Basic Web Search

```python
from nanobot.agent.tools.web import WebSearchTool

tool = WebSearchTool(engine="searxng", max_results=5)
result = await tool.execute("machine learning", count=5)
print(result)
```

Output:
```
Searxng results for: machine learning (engines: multiple)

1. Introduction to Machine Learning
   https://www.example.com/ml-intro
   Machine learning is a subset of artificial intelligence...
   Engine: duckduckgo

2. Machine Learning Basics
   https://www.example.com/ml-basics
   Learn the fundamentals of ML algorithms...
   Engine: brave
```

### Multi-Engine Search

```python
result = await tool.execute(
    query="quantum computing",
    engines=["duckduckgo", "brave", "bing"],
    categories=["general"],
    count=5
)
```

### News Search with Time Filter

```python
result = await tool.execute(
    query="AI breakthrough",
    categories=["news"],
    time_range="week",  # day, week, month, year
    count=10
)
```

### Research Tool with Searxng

```python
from nanobot.agent.tools.research import ResearchTool

tool = ResearchTool(max_results=5)
result = await tool.execute(
    query="renewable energy storage",
    mode="balanced",
    use_searxng=True  # Will use SEARXNG_URL if set
)
```

## API Reference

### SearxngHttpClient

```python
class SearxngHttpClient:
    def __init__(self, base_url: str = "http://localhost:8888", timeout: float = 30.0)
    async def search(
        self,
        query: str,
        engines: list[str] | None = None,
        categories: list[str] | None = None,
        language: str = "en",
        time_range: str | None = None,
        safesearch: int = 0,
        count: int = 10
    ) -> list[dict]
    async def health_check() -> bool
```

### HTTP API Endpoints

Searxng exposes these HTTP endpoints:

#### `GET /search`

Main search endpoint.

**Query Parameters:**
- `q` (required): Search query
- `format`: Response format (`json`, `csv`, `rss`)
- `engines`: Comma-separated engine names
- `categories`: Comma-separated categories
- `language`: Language code (e.g., `en`, `fr`)
- `time_range`: Time filter (`day`, `week`, `month`, `year`)
- `safesearch`: Safe search level (0, 1, 2)
- `pageno`: Page number

**Example:**
```bash
curl "http://localhost:8888/search?q=python&format=json&engines=duckduckgo,brave&categories=general"
```

**Response:**
```json
{
  "query": "python",
  "results": [
    {
      "title": "Python Official Website",
      "url": "https://www.python.org",
      "content": "Welcome to Python.org",
      "engine": "duckduckgo",
      "category": "general",
      "score": 0.95
    }
  ],
  "answers": [],
  "infoboxes": []
}
```

## Testing

### Test Searxng Server

```bash
# Check if server is running
curl http://localhost:8888/

# Test search
curl "http://localhost:8888/search?q=test&format=json" | jq
```

### Test nanobot Integration

```python
import asyncio
from nanobot.agent.tools.searxng_http_client import SearxngHttpClient

async def test():
    client = SearxngHttpClient()

    # Health check
    healthy = await client.health_check()
    print(f"Searxng healthy: {healthy}")

    # Search
    results = await client.search("python programming", count=3)
    print(f"Results: {len(results)}")
    for r in results:
        print(f"  - {r['title']} ({r['engine']})")

    await client.close()

asyncio.run(test())
```

## Troubleshooting

### Searxng Server Not Starting

**Problem**: Server fails to start

**Solutions**:
1. Check port 8888 is not in use:
   ```bash
   lsof -i :8888
   ```
2. Check logs for errors
3. Verify dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

### nanobot Cannot Connect to Searxng

**Problem**: `Failed to connect to Searxng server`

**Solutions**:
1. Verify Searxng is running:
   ```bash
   curl http://localhost:8888/
   ```
2. Check SEARXNG_URL is set correctly:
   ```bash
   echo $SEARXNG_URL
   ```
3. Check firewall rules:
   ```bash
   sudo ufw allow 8888
   ```
4. If using Docker, ensure port is mapped:
   ```bash
   docker ps | grep searxng
   ```

### CORS Errors

**Problem**: Browser/console shows CORS errors

**Solutions**:
1. Update Searxng settings.yml:
   ```yaml
   server:
     cors:
       access_control_allow_origin: "*"
   ```
2. Restart Searxng server

### Slow Searches

**Problem**: Searches take too long

**Solutions**:
1. Reduce `result_proxy.timeout` in settings.yml
2. Disable slow engines in settings.yml
3. Limit number of engines:
   ```python
   result = await tool.execute(
       query="test",
       engines=["duckduckgo", "brave"],  # Only use fast engines
       count=5
   )
   ```

### No Results

**Problem**: Search returns empty results

**Solutions**:
1. Check Searxng logs for engine errors
2. Try with different engines
3. Check if engines are enabled in settings.yml
4. Verify network connectivity from Searxng server

## Production Deployment

### Security

1. **Use secret_key** in settings.yml:
   ```bash
   openssl rand -hex 32
   ```

2. **Limit method types**:
   ```yaml
   server:
     methods: "GET"
   ```

3. **Rate limiting**:
   ```yaml
   limits:
     request_timeout: 3.0
   ```

4. **Use reverse proxy** (nginx):
   ```nginx
   location /searxng {
       proxy_pass http://localhost:8888;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
   }
   ```

### Performance

1. **Enable caching** in Searxng settings:
   ```yaml
   search:
     cache: true
   ```

2. **Use Redis** for distributed caching (optional)

3. **Load balancing**: Run multiple Searxng instances behind nginx

### Monitoring

```bash
# Check Searxng logs
tail -f /var/log/searxng/searxng.log

# Monitor resource usage
htop

# Test search endpoint
watch -n 5 'curl -s "http://localhost:8888/search?q=test&format=json" | jq ".results | length"'
```

## Comparison: HTTP vs Library Import

| Aspect | HTTP Approach | Library Import |
|--------|--------------|----------------|
| Separation | ✓ Separate process | ✗ Same process |
| Dependencies | ✓ Isolated | ✗ Shared |
| Updates | ✓ Independent | ✗ Coupled |
| Debugging | ✓ Easier | ✗ Harder |
| Network | ✓ Remote possible | ✗ Local only |
| Overhead | Small HTTP | None |
| Setup | ✓ Simpler | ✗ Complex |

## Migration from Library to HTTP

If you were using the library import approach:

**Before:**
```python
# Had SEARXNG_PATH set
export SEARXNG_PATH="/root/nanobot/searxng"
```

**After:**
```python
# Start Searxng server
cd /root/nanobot/searxng
python searx/webapp.py &

# Set SEARXNG_URL instead
export SEARXNG_URL="http://localhost:8888"
```

The nanobot code remains the same - just update the environment variable!

## Support

For issues:
1. Check Searxng documentation: https://docs.searxng.org
2. Check Searxng logs
3. Test HTTP endpoint directly with curl
4. Verify nanobot can reach the Searxng URL
