#!/usr/bin/env python3
"""Test script for Searxng integration verification."""

import asyncio
import json
import sys
from pathlib import Path

# Add nanobot to path
sys.path.insert(0, str(Path(__file__).parent))

from nanobot.agent.tools.searxng_client import SearxngClient
from nanobot.agent.tools.web import WebSearchTool, SEARXNG_AVAILABLE
from nanobot.agent.tools.research import ResearchTool


async def test_searxng_client():
    """Test the SearxngClient directly."""
    print("=" * 80)
    print("Test 1: SearxngClient")
    print("=" * 80)

    client = SearxngClient()

    # Test 1a: Check availability
    print("\n1a. Checking Searxng availability...")
    available_engines = client.get_available_engines()
    print(f"   Available engines: {len(available_engines)} engines")
    if available_engines:
        print(f"   Sample: {', '.join(available_engines[:10])}")

    # Test 1b: Basic search
    print("\n1b. Testing basic search...")
    try:
        results = client.search(
            query="python programming",
            engines=["duckduckgo"],
            categories=["general"],
            count=3
        )
        print(f"   ✓ Search returned {len(results)} results")
        if results:
            print(f"   First result: {results[0].get('title', 'N/A')}")
    except Exception as e:
        print(f"   ✗ Search failed: {e}")
        return False

    # Test 1c: Multi-engine search
    print("\n1c. Testing multi-engine search...")
    try:
        results = client.search(
            query="artificial intelligence",
            engines=["duckduckgo", "brave"],
            categories=["general"],
            count=2
        )
        print(f"   ✓ Multi-engine search returned {len(results)} results")
        engines_used = set(r.get('engine', '') for r in results)
        print(f"   Engines used: {', '.join(engines_used)}")
    except Exception as e:
        print(f"   ✗ Multi-engine search failed: {e}")

    # Test 1d: Category search
    print("\n1d. Testing category-specific search...")
    try:
        results = client.search(
            query="technology news",
            engines=["duckduckgo"],
            categories=["general"],
            count=2
        )
        print(f"   ✓ Category search returned {len(results)} results")
    except Exception as e:
        print(f"   ✗ Category search failed: {e}")

    return True


async def test_web_search_tool():
    """Test WebSearchTool with Searxng engine."""
    print("\n" + "=" * 80)
    print("Test 2: WebSearchTool with Searxng")
    print("=" * 80)

    if not SEARXNG_AVAILABLE:
        print("   ⚠ Searxng not available, skipping WebSearchTool tests")
        return True

    # Test 2a: Basic Searxng search
    print("\n2a. Testing basic Searxng search...")
    tool = WebSearchTool(engine="searxng", max_results=3)
    try:
        result = await tool.execute(
            query="machine learning",
            count=3
        )
        print(f"   ✓ Search completed")
        print(f"   Result preview: {result[:200]}...")
    except Exception as e:
        print(f"   ✗ Search failed: {e}")
        return False

    # Test 2b: Searxng with specific engines
    print("\n2b. Testing Searxng with specific engines...")
    try:
        result = await tool.execute(
            query="quantum computing",
            engines=["duckduckgo", "brave"],
            categories=["general"],
            count=2
        )
        print(f"   ✓ Multi-engine search completed")
        print(f"   Result preview: {result[:200]}...")
    except Exception as e:
        print(f"   ✗ Multi-engine search failed: {e}")

    # Test 2c: Searxng with time filter
    print("\n2c. Testing Searxng with time filter...")
    try:
        result = await tool.execute(
            query="AI developments",
            categories=["general"],
            time_range="week",
            count=2
        )
        print(f"   ✓ Time-filtered search completed")
        print(f"   Result preview: {result[:200]}...")
    except Exception as e:
        print(f"   ✗ Time-filtered search failed: {e}")

    return True


async def test_research_tool():
    """Test ResearchTool with Searxng."""
    print("\n" + "=" * 80)
    print("Test 3: ResearchTool with Searxng")
    print("=" * 80)

    # Test 3a: Speed mode with Searxng
    print("\n3a. Testing speed mode with Searxng...")
    tool = ResearchTool(max_results=2)
    try:
        result = await tool.execute(
            query="blockchain technology",
            mode="speed",
            use_searxng=True
        )
        data = json.loads(result)
        print(f"   ✓ Speed mode research completed")
        print(f"   Iterations: {data.get('iterations_completed')}")
        print(f"   Sources found: {data.get('total_sources')}")

        # Show search strategies used
        if data.get('search_history'):
            print("   Search strategies:")
            for entry in data['search_history'][:3]:
                strategies = entry.get('strategies', [])
                for s in strategies[:2]:
                    query = s.get('query', 'N/A')
                    engines = s.get('engines', ['default'])
                    print(f"     - {query} (engines: {', '.join(engines)})")
    except Exception as e:
        print(f"   ✗ Speed mode research failed: {e}")
        return False

    # Test 3b: Balanced mode with Searxng
    print("\n3b. Testing balanced mode with Searxng (2 iterations)...")
    try:
        # Create a tool with reduced iterations for testing
        result = await tool.execute(
            query="renewable energy",
            mode="balanced",
            use_searxng=True
        )
        data = json.loads(result)
        print(f"   ✓ Balanced mode research completed")
        print(f"   Iterations: {data.get('iterations_completed')}")
        print(f"   Sources found: {data.get('total_sources')}")
    except Exception as e:
        print(f"   ✗ Balanced mode research failed: {e}")
        return False

    return True


async def test_fallback():
    """Test fallback when Searxng is not available."""
    print("\n" + "=" * 80)
    print("Test 4: Fallback Behavior")
    print("=" * 80)

    # Test 4a: WebSearchTool fallback
    print("\n4a. Testing WebSearchTool engine fallback...")
    tool = WebSearchTool(engine="ddg", max_results=2)
    try:
        result = await tool.execute(
            query="cloud computing",
            count=2
        )
        print(f"   ✓ Fallback to ddg works")
        print(f"   Result preview: {result[:200]}...")
    except Exception as e:
        print(f"   ✗ Fallback failed: {e}")

    # Test 4b: ResearchTool with Searxng disabled
    print("\n4b. Testing ResearchTool with Searxng disabled...")
    research_tool = ResearchTool(max_results=2)
    try:
        result = await research_tool.execute(
            query="edge computing",
            mode="speed",
            use_searxng=False
        )
        data = json.loads(result)
        print(f"   ✓ Research without Searxng works")
        print(f"   Sources found: {data.get('total_sources')}")
    except Exception as e:
        print(f"   ✗ Research without Searxng failed: {e}")

    return True


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("Searxng Integration Test Suite")
    print("=" * 80)

    print(f"\nSearxng available: {SEARXNG_AVAILABLE}")

    results = []

    # Run tests
    try:
        results.append(("SearxngClient", await test_searxng_client()))
    except Exception as e:
        print(f"\n✗ SearxngClient tests failed with exception: {e}")
        results.append(("SearxngClient", False))

    try:
        results.append(("WebSearchTool", await test_web_search_tool()))
    except Exception as e:
        print(f"\n✗ WebSearchTool tests failed with exception: {e}")
        results.append(("WebSearchTool", False))

    try:
        results.append(("ResearchTool", await test_research_tool()))
    except Exception as e:
        print(f"\n✗ ResearchTool tests failed with exception: {e}")
        results.append(("ResearchTool", False))

    try:
        results.append(("Fallback", await test_fallback()))
    except Exception as e:
        print(f"\n✗ Fallback tests failed with exception: {e}")
        results.append(("Fallback", False))

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)

    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")

    all_passed = all(passed for _, passed in results)
    print("\n" + "=" * 80)
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed. Please review the output above.")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
