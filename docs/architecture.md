# Architecture

## System Overview

dev-loop is a closed-loop developer tooling harness. The output of every stage feeds back as input to an earlier stage. There is no "end" — only cycles that get tighter as the harness learns.

```
                    ┌─────────────────────┐
                    │   LINEAR (Intake)    │
                    │  tickets, sprints,   │
                    │  DORA metrics        │
                    └──────────┬──────────┘
                               │ webhook / poll
                    ┌──────────▼──────────┐
                    │   ORCHESTRATION      │
                    │  dmux (worktrees)    │
                    │  task decomposition  │
                    │  agent assignment    │
                    └──────────┬──────────┘
                               │ spawn
                    ┌──────────▼──────────┐
                    │   AGENT RUNTIME      │
                    │  OpenFang sandbox    │
                    │  memory/context      │
                    │  tool access (MCP)   │
                    │  token metering      │
                    └──────────┬──────────┘
                               │ output (diff, PR, artifact)
                    ┌──────────▼──────────┐
                    │   QUALITY GATES      │
                    │  CodeRabbit (review) │
                    │  Aikido (security)   │
                    │  DeepEval (LLM eval) │
                    │  ATDD (acceptance)   │
                    │  secret scan         │
                    └──────────┬──────────┘
                               │ pass/fail + traces
                    ┌──────────▼──────────┐
                    │   OBSERVABILITY      │
                    │  OTel spans          │
                    │  OpenObserve (store) │
                    │  AgentLens (replay)  │
                    │  OneUptime (alerts)  │
                    │  DORA dashboards     │
                    └──────────┬──────────┘
                               │ signals
                    ┌──────────▼──────────┐
                    │   FEEDBACK LOOP      │
                    │  retry failed tasks  │
                    │  harness tuning      │
                    │  changelog gen       │
                    │  cost alerts         │
                    │  cross-repo cascade  │
                    └──────────┬──────────┘
                               │
                               ▼
                         back to LINEAR
```

## Integration Boundaries

Every layer communicates through one of three mechanisms:

1. **MCP servers** — Tool calls between layers. Each MCP server is a thin wrapper around one tool or service.
2. **OpenTelemetry spans** — Every layer emits spans. Spans carry context (project_id, agent_id, task_id, tracer_bullet_id) that ties the full loop together.
3. **Git** — The universal state store. Worktrees for isolation. Branches for agent work. Commits as checkpoints. Context repos for memory.

```
Layer 1 ──MCP──► Layer 2 ──MCP──► Layer 3
   │                │                │
   └──OTel──►  OpenObserve  ◄──OTel──┘
```

## Multi-Project Model

```
dev-loop (this repo)
├── shared MCP servers (Linear, OpenObserve, cost-proxy)
├── shared CLAUDE.md template
└── per-project overrides

project-a/
├── .claude/settings.local.json  → points to shared MCP servers
├── CLAUDE.md                    → extends dev-loop template
└── (project code)

project-b/
├── .claude/settings.local.json  → same shared MCP servers
├── CLAUDE.md                    → extends dev-loop template
└── (project code)
```

Each project gets:
- Its own worktree per agent run (via dmux)
- Its own Linear project/labels
- Its own quality gate thresholds (some repos need stricter security)
- Shared observability (all traces go to the same OpenObserve instance)
- Shared cost budget (with per-project breakdown)

## Data Flow for One Tracer Bullet (TB-1: Ticket-to-PR)

```
1. Linear ticket moves to "Ready" status
2. Webhook hits dev-loop intake MCP server
3. Intake creates OTel span: trace_id=T, span=intake
4. Orchestration layer:
   a. Reads ticket metadata (repo, description, labels)
   b. Runs dmux to create isolated worktree + branch
   c. Selects agent config based on labels (bug fix, feature, refactor)
   d. Creates OTel span: trace_id=T, span=orchestration
5. Agent runtime:
   a. OpenFang sandbox initialized with scoped capabilities
   b. Agent loads context from Letta/Continuous-Claude context repo
   c. Agent works in worktree (reads code, makes changes)
   d. Token proxy logs every LLM call with project_id, task_id
   e. Creates OTel span: trace_id=T, span=agent_runtime
6. Quality gates (sequential):
   a. ATDD — run acceptance tests if spec exists
   b. CodeRabbit CLI — review the diff
   c. Aikido — security scan the diff
   d. Secret scanner — check for leaked credentials
   e. Each gate creates OTel span with pass/fail
7. Observability:
   a. All spans arrive in OpenObserve
   b. AgentLens captures full agent session for replay
   c. DORA metrics updated (lead time clock started at step 1)
8. Outcome routing:
   a. ALL GATES PASS → PR created, Linear ticket → "In Review"
   b. ANY GATE FAILS → failure trace sent to feedback loop
9. Feedback loop (on failure):
   a. Parse failure reason from quality gate spans
   b. Feed error context back to agent
   c. Agent retries (max 2 retries, then escalate to human)
   d. On retry success → back to step 6
   e. On retry exhaustion → Linear ticket → "Blocked", human notified
```

## Key Constraints

- **No shared mutable state between agents.** Worktree isolation is mandatory.
- **Every tool is bypassable.** `just tb1 --skip-security` skips Aikido. `just tb1 --skip-review` skips CodeRabbit. The loop still runs.
- **Cost ceiling per run.** Token proxy enforces a hard limit. Agent is killed if it exceeds budget. Configurable per project.
- **Human-in-the-loop by default.** PRs require human merge. Auto-merge is opt-in per project after trust is established.
