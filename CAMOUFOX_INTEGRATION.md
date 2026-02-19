# Camoufox Integration Summary

## Overview

Camoufox has been successfully integrated into nanobot as an anti-detect web browsing tool. This allows the AI to browse websites while evading bot detection systems.

## What Was Added

### 1. Package Dependency
- **File**: `pyproject.toml`
- **Status**: Already present (line 43): `"camoufox>=0.4.11"`

### 2. Browser Tool
- **File**: `nanobot/agent/tools/camoufox_browser.py`
- **Tool Name**: `camoufox_browse`
- **Class**: `CamoufoxBrowserTool`

**Features**:
- Anti-detect web browsing using Camoufox (Firefox-based)
- Fingerprint injection and rotation
- Support for complex actions (fill forms, click buttons, evaluate JS)
- Screenshot capability
- Wait for dynamic content
- Text and HTML extraction

### 3. Skill Definition
- **File**: `nanobot/skills/camoufox/SKILL.md`
- **Name**: `camoufox`
- **Description**: Anti-detect web browsing using Camoufox browser

**Contents**:
- Complete usage instructions
- Action examples (fill, click, wait, evaluate, screenshot)
- Best practices and troubleshooting
- Comparison with other web tools

### 4. Agent Integration
- **File**: `nanobot/agent/loop.py`
- **Import Added**: `from nanobot.agent.tools.camoufox_browser import CamoufoxBrowserTool`
- **Registration**: Tool is registered in the AgentLoop's tool registry

### 5. Documentation Updates
- **File**: `nanobot/skills/README.md`
- **Added**: Entry for the `camoufox` skill

## Tool Usage

### Basic Usage

```python
from nanobot.agent.tools.camoufox_browser import CamoufoxBrowserTool

tool = CamoufoxBrowserTool()
result = await tool.execute(
    url="https://example.com",
    extract_text=True
)
```

### With Actions

```python
result = await tool.execute(
    url="https://example.com",
    actions=[
        {"type": "fill", "selector": "input[name='q']", "value": "search term"},
        {"type": "click", "selector": "button[type='submit']"},
        {"type": "wait", "timeout": 2000},
    ]
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | **required** | URL to navigate to |
| `actions` | array | `null` | List of actions to perform |
| `wait_for_selector` | string | `null` | CSS selector to wait for |
| `extract_text` | boolean | `true` | Extract visible text |
| `extract_html` | boolean | `false` | Extract full HTML |
| `screenshot` | boolean | `false` | Take screenshot |
| `headless` | boolean | `true` | Run in headless mode |
| `timeout` | integer | `30000` | Timeout in milliseconds |

## Action Types

### Fill
Fill form fields:
```json
{"type": "fill", "selector": "input[name='email']", "value": "user@example.com"}
```

### Click
Click elements:
```json
{"type": "click", "selector": "button[type='submit']"}
```

### Wait
Wait for specified time:
```json
{"type": "wait", "timeout": 2000}
```

### Evaluate
Execute JavaScript:
```json
{"type": "evaluate", "code": "() => document.title"}
```

### Screenshot
Take a screenshot:
```json
{"type": "screenshot"}
```

## When to Use Camoufox

Use Camoufox when:
- Sites have **anti-bot protection** (Cloudflare, Akamai, etc.)
- `web_fetch` or `web_search` are **blocked**
- Sites **require JavaScript rendering**
- You need to **interact with forms** or buttons
- Sites **block headless browsers**

## Comparison with Other Tools

| Tool | Use Case | Detection Risk |
|------|----------|----------------|
| `web_fetch` | Simple HTML fetching | High |
| `web_search` | Search queries | Medium |
| `camoufox_browse` | Anti-bot protection | **Low** |

## Testing

A test script is provided at `test_camoufox.py`:

```bash
python3 test_camoufox.py
```

Or with the virtual environment:
```bash
.venv/bin/python3 test_camoufox.py
```

## Installation

If Camoufox is not installed:
```bash
pip install camoufox>=0.4.11
```

Or with uv:
```bash
uv pip install camoufox>=0.4.11
```

## Architecture

```
nanobot/
├── agent/
│   ├── loop.py                    # Agent loop (tool registration)
│   └── tools/
│       └── camoufox_browser.py    # Camoufox browser tool
└── skills/
    ├── README.md                  # Skills documentation
    └── camoufox/
        └── SKILL.md               # Camoufox skill instructions
```

## Key Features

1. **Anti-Detection**: Built on Firefox with C-level fingerprint injection
2. **Playwright Compatible**: Uses familiar Playwright-style API
3. **Async Support**: Fully asynchronous for better performance
4. **Flexible Actions**: Support for complex browser interactions
5. **Screenshots**: Base64-encoded PNG output
6. **Content Extraction**: Text, HTML, or both
7. **Error Handling**: Graceful failure with detailed error messages

## Limitations

- Slower than `web_fetch` (launches full browser)
- Higher resource usage (CPU, memory)
- May still be detected by advanced systems
- Content size limits (50k text, 100k HTML)

## Future Enhancements

Possible improvements:
- Custom fingerprint configuration
- Proxy support
- Cookie persistence
- Multiple tab support
- Download handling

## References

- [Camoufox GitHub](https://github.com/daijro/camoufox)
- [Camoufox Documentation](https://camoufox.com)
- [Playwright Python](https://playwright.dev/python/)
