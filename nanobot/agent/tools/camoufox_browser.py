"""Camoufox browser tool for anti-detect web browsing.

This tool provides web browsing capabilities using Camoufox, an anti-detect
browser built on Firefox that evades bot detection systems.
"""

import asyncio
import json
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool

# Try to import Camoufox (optional dependency)
try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    logger.debug(
        "Camoufox not installed. Install with: pip install camoufox>=0.4.11"
    )


class CamoufoxBrowserTool(Tool):
    """
    Anti-detect browser tool using Camoufox.

    Provides advanced web browsing capabilities with bot detection evasion.
    Camoufox is built on Firefox and provides:
    - Fingerprint injection and rotation
    - Anti-bot evasion
    - Human-like mouse movement
    - Ad blocking
    - Playwright-compatible API

    Best used for:
    - Accessing sites with anti-bot protection
    - Web scraping with stealth
    - Automated browsing that appears human
    - Sites that block traditional headless browsers
    """

    name = "camoufox_browse"
    description = (
        "Browse the web using Camoufox anti-detect browser. "
        "Navigates to URLs, extracts content, and interacts with pages "
        "while evading bot detection. Best for sites with anti-bot protection. "
        "Returns page content, title, URL, and metadata."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to navigate to (must start with http:// or https://)",
            },
            "actions": {
                "type": "array",
                "description": "Optional list of actions to perform (e.g., fill forms, click buttons)",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["fill", "click", "wait", "evaluate", "screenshot"],
                            "description": "Action type",
                        },
                        "selector": {"type": "string", "description": "CSS selector for fill/click"},
                        "value": {"type": "string", "description": "Value for fill action"},
                        "timeout": {"type": "integer", "description": "Timeout in milliseconds"},
                        "code": {"type": "string", "description": "JavaScript code for evaluate action"},
                    },
                },
            },
            "wait_for_selector": {
                "type": "string",
                "description": "CSS selector to wait for before returning content",
            },
            "extract_text": {
                "type": "boolean",
                "description": "Extract visible text from page (default: true)",
            },
            "extract_html": {
                "type": "boolean",
                "description": "Extract full HTML from page (default: false)",
            },
            "screenshot": {
                "type": "boolean",
                "description": "Take a screenshot of the page (default: false)",
            },
            "headless": {
                "type": "boolean",
                "description": "Run browser in headless mode (default: true)",
            },
            "timeout": {
                "type": "integer",
                "description": "Navigation timeout in milliseconds (default: 30000)",
            },
        },
        "required": ["url"],
    }

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize Camoufox browser tool.

        Args:
            headless: Run browser in headless mode (default: true)
            timeout: Default navigation timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self._available = CAMOUFOX_AVAILABLE

    async def execute(
        self,
        url: str,
        actions: list[dict] | None = None,
        wait_for_selector: str | None = None,
        extract_text: bool = True,
        extract_html: bool = False,
        screenshot: bool = False,
        headless: bool | None = None,
        timeout: int | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute browsing with Camoufox.

        Args:
            url: URL to navigate to
            actions: Optional list of actions to perform
            wait_for_selector: CSS selector to wait for
            extract_text: Extract visible text from page
            extract_html: Extract full HTML from page
            screenshot: Take a screenshot of the page
            headless: Override default headless setting
            timeout: Override default timeout setting

        Returns:
            JSON string with page content and metadata
        """
        if not self._available:
            return json.dumps({
                "error": "Camoufox is not installed. Install with: pip install camoufox>=0.4.11",
                "url": url,
            })

        # Validate URL
        if not url.startswith(("http://", "https://")):
            return json.dumps({
                "error": "URL must start with http:// or https://",
                "url": url,
            })

        # Use instance defaults if not overridden
        use_headless = headless if headless is not None else self.headless
        use_timeout = timeout if timeout is not None else self.timeout

        logger.info(f"Camoufox browsing: {url} (headless={use_headless})")

        try:
            # Configure Camoufox
            config = {
                "headless": use_headless,
            }

            # Create browser session
            async with AsyncCamoufox(config=config) as browser:
                page = await browser.new_page()

                # Navigate to URL
                try:
                    await page.goto(url, timeout=use_timeout)
                except Exception as e:
                    logger.warning(f"Navigation to {url} failed: {e}")
                    return json.dumps({
                        "error": f"Failed to navigate to {url}: {str(e)}",
                        "url": url,
                    })

                # Wait for selector if specified
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=use_timeout)
                    except Exception as e:
                        logger.warning(f"Wait for selector '{wait_for_selector}' failed: {e}")

                # Execute actions if provided
                action_results = []
                if actions:
                    for action in actions:
                        result = await self._execute_action(page, action)
                        action_results.append(result)

                # Extract content
                result = {
                    "url": page.url,
                    "title": await page.title(),
                    "success": True,
                }

                # Extract text
                if extract_text:
                    try:
                        # Get body text
                        body_text = await page.inner_text("body")
                        result["text"] = body_text[:50000]  # Limit to 50k chars
                        result["text_truncated"] = len(body_text) > 50000
                    except Exception as e:
                        logger.warning(f"Failed to extract text: {e}")
                        result["text"] = ""

                # Extract HTML
                if extract_html:
                    try:
                        html_content = await page.content()
                        result["html"] = html_content[:100000]  # Limit to 100k chars
                        result["html_truncated"] = len(html_content) > 100000
                    except Exception as e:
                        logger.warning(f"Failed to extract HTML: {e}")
                        result["html"] = ""

                # Take screenshot
                if screenshot:
                    try:
                        screenshot_bytes = await page.screenshot(full_page=False)
                        import base64
                        result["screenshot"] = base64.b64encode(screenshot_bytes).decode("utf-8")
                        result["screenshot_format"] = "png"
                    except Exception as e:
                        logger.warning(f"Failed to take screenshot: {e}")

                # Add action results
                if action_results:
                    result["actions"] = action_results

                logger.info(f"Camoufox browsing completed: {url}")
                return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Camoufox browsing failed: {e}")
            return json.dumps({
                "error": str(e),
                "url": url,
                "success": False,
            })

    async def _execute_action(self, page, action: dict) -> dict:
        """Execute a single action on the page."""
        action_type = action.get("type")
        result = {"type": action_type, "success": False}

        try:
            if action_type == "fill":
                selector = action.get("selector")
                value = action.get("value")
                if selector and value:
                    await page.fill(selector, value)
                    result["success"] = True
                    result["selector"] = selector

            elif action_type == "click":
                selector = action.get("selector")
                if selector:
                    await page.click(selector)
                    result["success"] = True
                    result["selector"] = selector

            elif action_type == "wait":
                timeout = action.get("timeout", 5000)
                await asyncio.sleep(timeout / 1000)
                result["success"] = True
                result["timeout"] = timeout

            elif action_type == "evaluate":
                code = action.get("code")
                if code:
                    eval_result = await page.evaluate(code)
                    result["success"] = True
                    result["result"] = eval_result

            elif action_type == "screenshot":
                import base64
                screenshot_bytes = await page.screenshot(full_page=False)
                result["success"] = True
                result["screenshot"] = base64.b64encode(screenshot_bytes).decode("utf-8")
                result["format"] = "png"

            else:
                result["error"] = f"Unknown action type: {action_type}"

        except Exception as e:
            result["error"] = str(e)

        return result
