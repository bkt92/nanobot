# Team Manager Skill

A dynamic project management skill that enables the main agent to intelligently orchestrate multiple subagents as a team. The main agent analyzes user requests, creates execution plans, spawns specialized subagents, and synthesizes their results.

## Capabilities

1. **Task Analysis**: Break down complex requests into subtasks
2. **Team Planning**: Decide which agents to spawn with what roles/profiles
3. **Progress Tracking**: Track all subagents in TodoTool
4. **Result Routing**: Intelligently pass outputs between agents
5. **Synthesis**: Combine results from multiple agents into coherent responses

## How It Works

1. User provides a complex goal
2. Main agent analyzes and creates a plan
3. Agent spawns subagents with specific roles
4. Progress is tracked in todo lists
5. Results are routed between agents as needed
6. Final synthesis produces the deliverable

## Use Cases

- **Parallel Research**: "Compare 5 AI models and create a comparison table"
- **Multi-step Analysis**: "Analyze this codebase, find bugs, create fixes, and write tests"
- **Content Pipeline**: "Research topic → Create outline → Write content → Review → Publish"
- **Data Processing**: "Fetch data → Process → Analyze → Visualize → Report"

## Example Conversation

**User**: "Research quantum computing applications in finance and create a report"

**Team Manager Agent**:
```
I'll orchestrate a team to handle this:

PLAN:
1. Spawn Researcher 1: Quantum computing in trading
2. Spawn Researcher 2: Quantum computing in risk analysis
3. Spawn Researcher 3: Quantum computing in portfolio optimization
4. After all complete, spawn Writer: Synthesize findings into report

[Tracking in todo: team_manager/quantum_finance_report]

→ Spawning subagent: Quantum Trading Research...
→ Spawning subagent: Quantum Risk Research...
→ Spawning subagent: Quantum Portfolio Research...
```

**[Subagents work in parallel...]**

**Team Manager Agent**:
```
✓ Quantum Trading Research complete
✓ Quantum Risk Research complete
✓ Quantum Portfolio Research complete

→ Spawning subagent: Report Writer to synthesize findings...

[Report Writer receives all three research results and creates final report]

✓ Report complete! Saved to: workspace/reports/quantum_finance_report.md
```

## Implementation

The team_manager integrates these tools:
- `spawn()` - Create subagents with specific profiles
- `list_subagents()` - Monitor team progress
- `todo add/list/update` - Track tasks and milestones
- `write_file()` - Save deliverables

## Workflow Pattern

```
User Request
    ↓
Main Agent (Team Manager)
    ↓
Analysis & Planning Phase
    ├─ Understand goal
    ├─ Break down into tasks
    ├─ Identify dependencies
    └─ Create execution plan
    ↓
Orchestration Phase
    ├─ Spawn subagents (parallel/sequential)
    ├─ Track in todo lists
    ├─ Monitor progress
    └─ Handle errors/retries
    ↓
Synthesis Phase
    ├─ Collect all results
    ├─ Route outputs between agents
    ├- Spawn synthesis agents if needed
    └─ Create final deliverable
    ↓
Final Output to User
```

## Profile System

Users define profiles in `~/.nanobot/config.json`. The team_manager skill uses these profiles to assign appropriate specialists:

**Example Profile Configuration**:
```json
{
  "agents": {
    "profiles": {
      "researcher": {
        "model": "anthropic/claude-sonnet-4-5",
        "temperature": 0.2,
        "system_prompt": "You are a research specialist. Find, analyze, and synthesize information from multiple sources.",
        "memory_isolation": "isolated"
      },
      "coder": {
        "model": "anthropic/claude-sonnet-4-5",
        "temperature": 0.1,
        "system_prompt": "You are a senior software engineer. Analyze code, find bugs, and write clean solutions.",
        "memory_isolation": "isolated"
      },
      "writer": {
        "model": "anthropic/claude-sonnet-4-5",
        "temperature": 0.7,
        "system_prompt": "You are a professional writer. Create clear, engaging, well-structured content."
      },
      "analyst": {
        "model": "anthropic/claude-sonnet-4-5",
        "temperature": 0.2,
        "system_prompt": "You are a data analyst. Process data, find patterns, and provide insights."
      }
    }
  }
}
```

## Best Practices

1. **Always start with a plan** - Analyze before spawning
2. **Use appropriate profiles** - Match profile to task type
3. **Track everything** - Use TodoTool for visibility
4. **Parallel when possible** - Independent tasks run concurrently
5. **Synthesize results** - Don't just paste outputs together
6. **Handle failures** - Retry or adjust when subagents fail

## Notes

- This skill makes the main agent a "meta-agent" that manages other agents
- Subagents don't know about each other - main agent routes all communication
- Progress is visible via `list_subagents()` and TodoTool
- Complex workflows emerge from simple agent interactions
- Users can create custom profiles for their specific needs
