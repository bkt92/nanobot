#!/usr/bin/env python3
"""Test script for Camoufox browser tool."""

import asyncio
import json
import sys

from nanobot.agent.tools.camoufox_browser import CamoufoxBrowserTool


async def test_basic_browsing():
    """Test basic web browsing with Camoufox."""
    print("Testing Camoufox browser tool...")
    print("=" * 60)

    tool = CamoufoxBrowserTool(headless=True, timeout=30000)

    if not tool._available:
        print("✗ Camoufox is not installed!")
        print("  Install with: pip install camoufox>=0.4.11")
        return False

    print(f"✓ Tool initialized: {tool.name}")
    print(f"✓ Camoufox available: {tool._available}")

    # Test 1: Basic page fetch
    print("\n[Test 1] Basic page fetch - example.com")
    print("-" * 60)
    result = await tool.execute(
        url="https://example.com",
        extract_text=True,
        extract_html=False,
    )
    data = json.loads(result)
    if data.get("success"):
        print(f"✓ Successfully fetched {data['url']}")
        print(f"  Title: {data['title']}")
        print(f"  Text length: {len(data.get('text', ''))} chars")
    else:
        print(f"✗ Failed: {data.get('error')}")
        return False

    # Test 2: Page with screenshot
    print("\n[Test 2] Page fetch with screenshot - example.com")
    print("-" * 60)
    result = await tool.execute(
        url="https://example.com",
        extract_text=False,
        screenshot=True,
    )
    data = json.loads(result)
    if data.get("success") and data.get("screenshot"):
        print(f"✓ Screenshot captured ({data.get('screenshot_format')})")
        print(f"  Base64 length: {len(data['screenshot'])} chars")
    else:
        print(f"✗ Failed to capture screenshot")

    # Test 3: With wait for selector
    print("\n[Test 3] Wait for selector - example.com")
    print("-" * 60)
    result = await tool.execute(
        url="https://example.com",
        wait_for_selector="h1",
        extract_text=True,
    )
    data = json.loads(result)
    if data.get("success"):
        print(f"✓ Successfully waited for h1 element")
        print(f"  Title: {data['title']}")
    else:
        print(f"✗ Failed: {data.get('error')}")

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    return True


async def test_actions():
    """Test browser actions."""
    print("\n[Test 4] Browser actions - evaluate JavaScript")
    print("-" * 60)

    tool = CamoufoxBrowserTool()

    result = await tool.execute(
        url="https://example.com",
        actions=[
            {"type": "evaluate", "code": "() => ({ title: document.title, url: window.location.href })"},
        ],
    )
    data = json.loads(result)

    if data.get("success") and data.get("actions"):
        action_result = data["actions"][0]
        if action_result.get("success"):
            print(f"✓ JavaScript evaluation successful")
            print(f"  Result: {action_result.get('result')}")
        else:
            print(f"✗ JavaScript evaluation failed: {action_result.get('error')}")
    else:
        print(f"✗ Actions test failed: {data.get('error')}")


async def main():
    """Run all tests."""
    try:
        success = await test_basic_browsing()
        if success:
            await test_actions()
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
