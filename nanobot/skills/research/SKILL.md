---
name: research
description: Deep research skill with iterative search and synthesis, cloning Perplexica's research mechanism
always: false
---

# Research Skill

## Overview

This skill clones Perplexica's research mechanism to provide deep, comprehensive research on any topic. It uses an iterative search process with reasoning steps to gather information from multiple angles and synthesize findings.

## When to Use

Use this skill when the user asks for:
- Research on a topic ("research quantum computing")
- Deep dives into subjects ("give me a comprehensive overview of AI")
- Finding latest information ("what's new with GPT-5?")
- Multi-faceted investigations ("compare and analyze different approaches to X")
- Literature reviews or academic-style research

## Research Modes

The `deep_research` tool supports three modes:

1. **speed** (default): 2 iterations, quick answers
2. **balanced**: 6 iterations, moderate depth with reasoning steps
3. **quality**: 25 iterations, comprehensive deep research

## How It Works

1. **Analysis**: The system analyzes the query and determines research angles
2. **Planning**: Creates a research plan with multiple query strategies
3. **Iteration**: Runs multiple search rounds, each refining based on previous results
4. **Synthesis**: Combines findings from all searches into a comprehensive answer

## Research Strategy (Quality Mode)

For any topic, the system searches:
- Core definition/overview
- Features/capabilities
- Comparisons with alternatives
- Recent news/updates
- Reviews/opinions from experts
- Use cases and applications
- Limitations/critiques

## Tool

```python
deep_research(query, mode="balanced")
```

## Example Usage

```
User: "Research the latest developments in quantum computing"
→ Use deep_research with mode="quality"

User: "Quick overview of GPT-5"
→ Use deep_research with mode="speed"

User: "Give me comprehensive analysis of renewable energy storage"
→ Use deep_research with mode="quality"
```

## Progress Updates

The skill emits progress updates showing:
- Current research phase/iteration
- Queries being executed
- Reasoning about next steps
- Number of sources found

## Best Practices

1. Start with **balanced** mode for most queries
2. Use **speed** mode for quick factual answers
3. Use **quality** mode for comprehensive research or unknown topics
4. The system automatically deduplicates URLs and merges related content
5. Results are synthesized with citations to sources

## Underlying Mechanism (Perplexica Clone)

This skill implements Perplexica's research agent architecture:
- **Action Registry**: Dynamic tool availability based on classification
- **Researcher Loop**: Iterative search with configurable max iterations
- **Reasoning Steps**: Optional __reasoning_preamble before each tool call
- **Session Blocks**: Emits research progress blocks (reasoning, searching, results)
- **Classifier**: Determines if search is needed and optimal strategies
- **Writer Phase**: Synthesizes findings into comprehensive answers with citations
