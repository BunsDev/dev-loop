# Layer 2: Orchestration

## Purpose
Takes a work item from intake and turns it into an isolated, configured agent run. Handles worktree creation, agent selection, context loading, and task decomposition. This layer decides WHO works on WHAT in WHERE.

## Primary Tools

### dmux (Dev Agent Multiplexer)
- Creates isolated git worktrees per agent run
- Automatic branching (`dev-loop/LIN-123-fix-auth-bug`)
- One-key merge back to main
- Cleanup on completion

### Symphony Pattern (Reference Architecture)
We're not using Symphony directly, but borrowing its architecture:
- Isolated runs (one worktree per task)
- CI checks gate merging
- Review feedback loops back to the agent

### CC Workflow Studio (Future)
Visual design of orchestration flows. Not needed for TB-1, useful once we have 3+ tracer bullets working.

## Orchestration Flow

```
WorkItem from Intake
       │
       ▼
┌─────────────────┐
│ Task Analysis    │ ← Read ticket, determine repo, scope, complexity
│                  │   If complex: decompose into sub-tasks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Worktree Setup   │ ← dmux: git worktree add, create branch
│                  │   Copy .claude/ config from dev-loop template
│                  │   Inject project-specific CLAUDE.md
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Agent Config     │ ← Select agent persona based on labels
│                  │   Set cost ceiling from ticket metadata
│                  │   Load context from memory layer
│                  │   Configure MCP server access
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Agent Spawn      │ ← Launch Claude Code in worktree
│                  │   Pass task prompt + context
│                  │   Start OTel span
└─────────────────┘
```

## Agent Personas

Configured via label → persona mapping in `config/agents.yaml`:

```yaml
personas:
  bug-fix:
    labels: [bug]
    claude_md_overlay: |
      Focus on minimal fix. Read the failing test first.
      Do not refactor surrounding code.
    cost_ceiling_default: 1.00
    retry_max: 2

  feature:
    labels: [feature]
    claude_md_overlay: |
      Implement the feature as described in the ticket.
      Write tests for new code. Follow existing patterns.
    cost_ceiling_default: 5.00
    retry_max: 1

  refactor:
    labels: [refactor]
    claude_md_overlay: |
      Preserve all existing behavior. Run tests before and after.
      Commit in small increments.
    cost_ceiling_default: 3.00
    retry_max: 1

  security-fix:
    labels: [security]
    claude_md_overlay: |
      Fix the security vulnerability without changing functionality.
      Reference the CWE/CVE in your commit message.
      Run Aikido scan to verify the fix.
    cost_ceiling_default: 2.00
    retry_max: 3
```

### MCP Server: `orchestrator`

```
src/mcp/orchestrator/
├── server.ts          # MCP server entry
├── analyzer.ts        # Ticket → task analysis (complexity, decomposition)
├── worktree.ts        # dmux integration (create, cleanup, merge)
├── config-loader.ts   # Load agent persona, inject CLAUDE.md
├── spawner.ts         # Launch Claude Code in worktree
└── types.ts           # WorkItem → AgentRun mapping
```

**Tools exposed:**
- `analyze_ticket` — returns complexity estimate, suggested persona, decomposition
- `create_worktree` — sets up isolated env for agent
- `spawn_agent` — launches agent with full config
- `merge_worktree` — merge completed work back to main branch
- `cleanup_worktree` — remove worktree after merge or abandonment

### OTel Instrumentation
```
span: orchestration.setup
attributes:
  agent.persona: bug-fix
  agent.cost_ceiling: 1.00
  worktree.branch: dev-loop/LIN-123-fix-auth-bug
  worktree.path: /tmp/dev-loop/worktrees/LIN-123
  task.complexity: low
  task.decomposed: false
parent: intake.ticket_pickup (trace_id from intake)
```

### Tracer Bullet Coverage
- **TB-1**: Single ticket → single worktree → single agent. Simplest path.
- **TB-2**: Same setup, agent will fail. Orchestrator handles retry (re-spawn with error context).
- **TB-3**: Security persona selected based on label.
- **TB-4**: Cost ceiling passed from ticket metadata to agent config.
- **TB-5**: Orchestrator creates worktrees in TWO repos (source + dependent).
- **TB-6**: Normal orchestration, AgentLens captures the spawn.

## Scheduling & Priority

When multiple tickets are "Ready" simultaneously:
```yaml
# config/scheduling.yaml
max_concurrent_agents: 3
priority_order: [urgent, high, medium, low, none]
budget_throttle:
  80_percent: high_and_above_only
  95_percent: urgent_only
  100_percent: pause_all
```

## Model Selection

Not every task needs the most expensive model:
```yaml
personas:
  bug-fix:
    model: sonnet    # targeted fixes, cheaper
  feature:
    model: opus      # needs deep understanding
  refactor:
    model: opus      # high-stakes reasoning
  docs:
    model: haiku     # low-risk, high-volume
  security-fix:
    model: opus      # needs careful analysis
```

Override per ticket via Linear custom field: `model_override`.

## Ambiguity Detection

Before assigning an agent, the orchestration layer checks for ambiguous tickets:
- No specific file/function mentioned → flag
- Vague verbs only ("improve", "clean up", "make better") → flag
- No acceptance criteria AND no ATDD spec → flag

Flagged tickets → "Needs Clarification" status, not assigned.

### Open Questions
- [ ] dmux vs manual `git worktree add` — does dmux add enough value for TB-1?
- [ ] dmux vs Gastown (steveyegge/gastown) — Gastown handles 20-30 agents with persistent identity. Evaluate both.
- [ ] Task decomposition: LLM-based or rule-based for MVP?
- [ ] How to handle tickets that need multiple agents working in sequence (not parallel)?
- [ ] Worktree cleanup: immediate after merge, or keep for N hours for debugging?
- [ ] EnCompass (checkpoint/rewind) — can we rewind to last good state instead of full retry?
