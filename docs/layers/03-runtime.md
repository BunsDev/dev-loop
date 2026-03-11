# Layer 3: Agent Runtime

## Purpose
The execution environment for agents. Handles sandboxing, memory/context persistence, tool access control, and token metering. This is where agents actually do work — reading code, making changes, running commands.

## Primary Tools

### OpenFang (Agent OS)
- WASM sandboxes with 16 security layers
- Capability-based permissions (agent gets tokens for specific operations, not raw credentials)
- Resource metering (CPU, memory, tokens)
- Prompt injection detection and taint tracking
- MIT licensed, 137k lines of Rust

**TB-1 reality check:** OpenFang is ambitious. For TB-1, we run Claude Code directly in a worktree with a scoped CLAUDE.md. OpenFang integration comes in TB-3/TB-4 when we need real sandboxing and cost control.

### zsh-tool MCP (Shell Safety)
- Yield-based execution with circuit breaker
- Prevents command hangs and infinite loops
- PTY mode for interactive commands
- Short-term learning to detect retry loops

### Continuous-Claude-v3 (Context Persistence)
- Ledgers and handoffs that survive context compaction
- Multi-agent safe memory
- Skill activation based on context
- Already built for Claude Code

### Letta Context Repositories (Git-backed Memory)
- Agent context stored as local files in a git repo
- Versioned, diffable, concurrent-safe
- Progressive disclosure (agent sees what it needs, not everything)
- Agents can programmatically restructure their own memory

### Headroom (Context Compression)
- Transparent proxy that compresses LLM context by 47-92%
- Strips boilerplate from tool outputs, DB queries, file reads
- Agent sees same information with fewer tokens
- Directly reduces cost AND fits more code into context window

### Token Proxy (Cost Metering)
Custom component — thin OTel-instrumented proxy between agents and LLM APIs.

```
Agent ──► Headroom (compress) ──► Token Proxy (meter) ──► Anthropic API
                                       │
                                       ▼
                                  OpenObserve
                                  (token counts, costs, latency)
```

## Runtime Phases

```
Phase 1: Context Load
  ├── Read CLAUDE.md (project + dev-loop overlay)
  ├── Load relevant context from memory (Letta/Continuous-Claude)
  ├── Read ticket description + any linked context
  └── Emit span: runtime.context_load

Phase 2: Execution
  ├── Agent reads codebase (scoped to relevant files)
  ├── Agent makes changes (edit, create, delete files)
  ├── Agent runs tests (if applicable)
  ├── Agent commits to worktree branch
  ├── Every tool call goes through zsh-tool MCP (safety)
  ├── Every LLM call goes through token proxy (metering)
  └── Emit span: runtime.execution (with tool_call_count, token_count)

Phase 3: Output
  ├── Agent produces: diff, commit(s), optional PR description
  ├── Context updates written back to memory
  ├── Session saved for AgentLens
  └── Emit span: runtime.output
```

## MCP Server: `runtime-manager`

```
src/mcp/runtime-manager/
├── server.ts          # MCP server entry
├── sandbox.ts         # OpenFang integration (future), basic isolation (now)
├── memory.ts          # Letta/Continuous-Claude context loading
├── token-proxy.ts     # LLM API proxy with metering
├── circuit-breaker.ts # Kill agent on budget exceeded or hung state
└── types.ts
```

**Tools exposed:**
- `load_context` — retrieve relevant memory for this task
- `save_context` — persist learnings back to context repo
- `get_token_usage` — current spend for this agent run
- `kill_agent` — force-stop a hung or over-budget agent

### Capability Scoping (TB-1 Minimal)

For TB-1, capability scoping is done via CLAUDE.md rules, not OpenFang:

```yaml
# config/capabilities.yaml
prompt-bench:
  allowed_tools:
    - Read
    - Write
    - Edit
    - Glob
    - Grep
    - Bash  # scoped to test/lint commands only
  denied_paths:
    - .env
    - secrets/
    - "*.pem"
    - "*.key"
  bash_allowlist:
    - "npm test"
    - "npm run lint"
    - "npm run build"
    - "git status"
    - "git diff"
    - "git add"
    - "git commit"
```

### OTel Instrumentation
```
span: runtime.execution
attributes:
  agent.id: agent-abc123
  agent.persona: bug-fix
  runtime.tool_calls: 14
  runtime.tokens_input: 12500
  runtime.tokens_output: 3200
  runtime.cost_usd: 0.42
  runtime.duration_s: 45
  runtime.files_read: 8
  runtime.files_modified: 2
  runtime.commits: 1
  memory.context_loaded: true
  memory.context_saved: true
parent: orchestration.setup
```

### Progressive Implementation

| Phase | What's active | What's stubbed |
|-------|--------------|----------------|
| TB-1 | Claude Code in worktree, CLAUDE.md scoping | Token proxy (logs only), memory (no persistence) |
| TB-2 | + retry context injection | + memory persistence |
| TB-3 | + Aikido as runtime tool | + OpenFang sandbox |
| TB-4 | + token proxy with kill switch | + real cost ceilings |
| TB-5 | + multi-worktree agent runs | |
| TB-6 | + full AgentLens session capture | |

### Open Questions
- [ ] OpenFang maturity — is it production-ready or experimental?
- [ ] Token proxy: custom build or existing tool? (LiteLLM proxy is an option)
- [ ] Memory: Letta vs Continuous-Claude-v3 — or both? Need to evaluate overlap
- [ ] How does the agent report "I'm stuck" vs silently failing?
- [ ] Max execution time per agent run? (separate from cost ceiling)
