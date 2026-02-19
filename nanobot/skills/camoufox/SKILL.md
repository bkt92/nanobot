---
name: camoufox
description: Anti-detect web browsing using Camoufox browser for accessing sites with bot protection
always: false
---

# Camoufox Browser Skill

## Overview

This skill provides access to the Camoufox anti-detect browser, an advanced web browsing tool built on Firefox that evades bot detection systems. Unlike traditional headless browsers, Camoufox uses fingerprint injection and anti-bot evasion techniques to appear as a genuine human user.

## What is Camoufox?

Camoufox is an open-source anti-detect browser with these key capabilities:
- **Fingerprint injection & rotation** - Spoofs device, OS, browser, and hardware properties
- **Anti-bot evasion** - Invisible to anti-bot systems and JavaScript inspection
- **Human-like mouse movement** - Natural cursor movement algorithms
- **Ad blocking** - Blocks and circumvents ads automatically
- **Memory optimized** - Uses ~200MB less memory than standard Firefox
- **Playwright compatible** - Works with Playwright-style APIs

## When to Use

Use this skill when:
- The target site has **anti-bot protection** (Cloudflare, Akamai, etc.)
- Traditional `web_fetch` or `web_search` are **blocked or return errors**
- You need to **bypass bot detection** systems
- Sites **require JavaScript rendering** to display content
- You need to **interact with forms** or click buttons
- Sites **block headless browsers** (Selenium, Puppeteer, etc.)

## How It Works

1. **Launch Camoufox** - Starts a stealth Firefox browser with randomized fingerprints
2. **Navigate to URL** - Goes to the target site with human-like behavior
3. **Wait for content** - Waits for page to fully render
4. **Extract content** - Returns text, HTML, or screenshots
5. **Optional actions** - Can fill forms, click buttons, wait for elements

## Tool

```python
camoufox_browse(
    url,
    actions=None,
    wait_for_selector=None,
    extract_text=True,
    extract_html=False,
    screenshot=False,
    headless=True,
    timeout=30000
)
```

### Parameters

- **url** (required): URL to navigate to (must start with http:// or https://)
- **actions** (optional): List of actions to perform (fill, click, wait, evaluate, screenshot)
- **wait_for_selector** (optional): CSS selector to wait for before extracting content
- **extract_text** (default: true): Extract visible text from page
- **extract_html** (default: false): Extract full HTML from page
- **screenshot** (default: false): Take a screenshot of the page
- **headless** (default: true): Run browser in headless mode (set false for debugging)
- **timeout** (default: 30000): Navigation timeout in milliseconds

## Actions

The `actions` parameter allows complex interactions:

### Fill Action
Fill form fields with values.
```json
{"type": "fill", "selector": "input[name='email']", "value": "user@example.com"}
```

### Click Action
Click on elements.
```json
{"type": "click", "selector": "button[type='submit']"}
```

### Wait Action
Wait for a specified time.
```json
{"type": "wait", "timeout": 2000}
```

### Evaluate Action
Execute JavaScript code.
```json
{"type": "evaluate", "code": "() => document.title"}
```

### Screenshot Action
Take a screenshot.
```json
{"type": "screenshot"}
```

## Example Usage

### Basic Page Fetch
```
User: "Check what's on example.com"
→ Use camoufox_browse with url="https://example.com"
```

### Bypass Cloudflare
```
User: "Get content from cloudflare-protected-site.com"
→ Use camoufox_browse with url="https://cloudflare-protected-site.com"
→ Camoufox will automatically handle the Cloudflare challenge
```

### Wait for Dynamic Content
```
User: "Get the price from example.com after it loads"
→ Use camoufox_browse with:
   - url="https://example.com"
   - wait_for_selector=".price"
   - extract_text=true
```

### Fill and Submit Form
```
User: "Search for 'python' on example.com"
→ Use camoufox_browse with:
   - url="https://example.com"
   - actions=[
       {"type": "fill", "selector": "input[name='q']", "value": "python"},
       {"type": "click", "selector": "button[type='submit']"},
       {"type": "wait", "timeout": 2000}
     ]
   - extract_text=true
```

### Extract Specific Elements
```
User: "Get all article titles from news-site.com"
→ Use camoufox_browse with:
   - url="https://news-site.com"
   - wait_for_selector=".article"
   - extract_text=true
→ Then parse the returned text to extract article titles
```

### Take Screenshot
```
User: "Show me what example.com looks like"
→ Use camoufox_browse with:
   - url="https://example.com"
   - screenshot=true
→ The response will include the screenshot file path
→ To send via Telegram: message(content="Here's the screenshot", media=["/path/to/screenshot.png"])
```

### Evaluate JavaScript
```
User: "Get the scroll height of example.com"
→ Use camoufox_browse with:
   - url="https://example.com"
   - actions=[
       {"type": "evaluate", "code": "() => document.body.scrollHeight"}
     ]
```

## Response Format

The tool returns JSON with:
```json
{
  "url": "https://example.com",
  "title": "Example Domain",
  "success": true,
  "text": "Page text content...",
  "text_truncated": false,
  "html": "<html>...</html>",
  "html_truncated": false,
  "screenshot_path": "/home/user/.nanobot/screenshots/camoufox_abc123_123456.png",
  "actions": [
    {"type": "fill", "selector": "...", "success": true}
  ]
}
```

## Best Practices

1. **Start with `web_fetch`** - Only use Camoufox if simpler tools fail
2. **Use `wait_for_selector`** - For dynamic content, wait for specific elements
3. **Set appropriate timeouts** - Default is 30s, increase for slow sites
4. **Headless mode** - Keep `headless=true` for production, `false` for debugging
5. **Limit content size** - Text is limited to 50k chars, HTML to 100k chars
6. **Handle errors** - Check `success` field and `error` messages
7. **Be respectful** - Don't overload sites with requests

## Comparison with Other Tools

| Tool | Best For | Bot Detection |
|------|----------|---------------|
| `web_fetch` | Simple HTML fetching | Easily detected |
| `web_search` | Search queries | Varies by engine |
| `camoufox_browse` | Anti-bot protection | **Evades detection** |

## Limitations

- Slower than `web_fetch` (launches full browser)
- Higher resource usage (CPU, memory)
- May still be detected by advanced systems
- Requires Camoufox package (>=0.4.11)
- Not suitable for high-volume scraping

## Troubleshooting

### "Camoufox is not installed"
Install with: `pip install camoufox>=0.4.11`

### "Failed to navigate to URL"
- Check URL starts with http:// or https://
- Verify site is accessible
- Try increasing timeout parameter

### "Wait for selector failed"
- Selector may be incorrect
- Element may not exist on page
- Page may still be loading (increase timeout)

### Empty content returned
- Site may require JavaScript (check `extract_html`)
- Content may be in iframe (harder to scrape)
- Try `wait_for_selector` for dynamic content

## Advanced Usage

### Custom Fingerprinting
For advanced users, Camoufox supports custom fingerprint configuration through the tool's internal config. Contact the administrator for customization options.

### Proxy Support
Camoufox can be configured to use proxies for additional anonymity. This requires environment setup beyond the basic tool usage.

## Sources

- [Camoufox GitHub Repository](https://github.com/daijro/camoufox)
- [Camoufox Official Documentation](https://camoufox.com)
- [Playwright Documentation](https://playwright.dev/python/) (API compatible)
