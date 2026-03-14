# Architecture

## System Overview

dev-loop is a closed-loop developer tooling harness. The output of every stage feeds back as input to an earlier stage. There is no "end" — only cycles that get tighter as the harness learns.

```
                    ┌─────────────────────┐
                    │   BEADS (Intake)     │
                    │  issues, deps,       │
                    │  DORA metrics        │
                    └──────────┬──────────┘
                               │ poll (br ready)
                    ┌──────────▼──────────┐
                    │   ORCHESTRATION      │
                    │  git worktree        │
                    │  (isolation)         │
                    │  task decomposition  │
                    │  agent assignment    │
                    └──────────┬──────────┘
                               │ spawn
                    ┌──────────▼──────────┐
                    │   AGENT RUNTIME      │
                    │  CLAUDE.md scoping   │
                    │  persona overlay     │
                    │  tool access (MCP)   │
                    │  NDJSON usage parsing│
                    └──────────┬──────────┘
                               │ output (diff, PR, artifact)
                    ┌──────────▼──────────┐
                    │   QUALITY GATES      │
                    │  Claude CLI (review) │
                    │  bandit (SAST)       │
                    │  gitleaks (secrets)  │
                    └──────────┬──────────┘
                               │ pass/fail + traces
                    ┌──────────▼──────────┐
                    │   OBSERVABILITY      │
                    │  OTel spans          │
                    │  OpenObserve (store) │
                    │  NDJSON session      │
                    │  replay (TB-6)       │
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
                    │  step efficiency     │
                    └──────────┬──────────┘
                               │
                               ▼
                         back to BEADS
```

## Integration Boundaries

Every layer communicates through one of three mechanisms:

1. **MCP servers** — Tool calls between layers. Each MCP server is a thin wrapper around one tool or service.
2. **OpenTelemetry spans** — Every layer emits spans. Spans carry context (project_id, agent_id, task_id, tracer_bullet_id) that ties the full loop together.
3. **Git** — The universal state store. Worktrees for isolation. Branches for agent work. Commits as checkpoints.

```
Layer 1 ──MCP──► Layer 2 ──MCP──► Layer 3
   │                │                │
   └──OTel──►  OpenObserve  ◄──OTel──┘
```

## Multi-Project Model

```
dev-loop (this repo)
├── shared MCP servers (beads-intake, OpenObserve, cost-proxy)
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
- Its own worktree per agent run (via `git worktree add`)
- Its own beads labels and issue prefix
- Its own quality gate thresholds (some repos need stricter security)
- Shared observability (all traces go to the same OpenObserve instance)
- Shared cost budget (with per-project breakdown)

## Data Flow for One Tracer Bullet (TB-1: Issue-to-PR)

```
1. beads issue is ready (br ready returns it — no blockers, no deferred)
2. Intake MCP server picks it up via polling
3. Intake creates OTel span: trace_id=T, span=intake
4. Orchestration layer:
   a. Reads issue metadata (repo, description, labels)
   b. Runs git worktree add to create isolated worktree + branch
   c. Selects agent config based on labels (bug fix, feature, refactor)
   d. Creates OTel span: trace_id=T, span=orchestration
5. Agent runtime:
   a. Worktree with CLAUDE.md scoping (persona overlay + deny list)
   b. Agent works in worktree (reads code, makes changes)
   c. Usage parsed from --output-format json NDJSON
   d. Creates OTel span: trace_id=T, span=agent_runtime
6. Quality gates (sequential, fail-fast):
   a. Gate 0: Sanity — compile + test
   b. Gate 0.5: Relevance — keyword overlap checks diff vs issue
   c. Gate 2: Secrets — gitleaks on the diff
   d. Gate 2.5: Dangerous ops — migration/CI/auth detection
   e. Gate 3: Security — bandit SAST (Python projects only)
   f. Gate 4: Review — Claude CLI LLM-as-judge code review
   g. Gate 5: Cost — turn/token usage check (called separately, not in fail-fast chain)
   h. Each gate creates OTel span with pass/fail
7. Observability:
   a. All spans arrive in OpenObserve
   b. NDJSON session saved for replay (TB-6)
   c. DORA metrics updated (lead time clock started at step 1)
8. Outcome routing:
   a. ALL GATES PASS → PR created, beads issue → closed
   b. ANY GATE FAILS → failure trace sent to feedback loop
9. Feedback loop (on failure):
   a. Parse failure reason from quality gate spans
   b. Feed error context back to agent
   c. Agent retries (max 2 retries, then escalate to human)
   d. On retry success → back to step 6
   e. On retry exhaustion → beads issue → blocked, human notified
```

## Key Constraints

- **No shared mutable state between agents.** Worktree isolation is mandatory.
- **Every tool is bypassable.** `just tb1 --skip-security` skips bandit. `just tb1 --skip-review` skips Claude CLI review. The loop still runs.
- **Cost tracking per run.** Usage parsed from NDJSON output (turns, tokens). On Max subscription, dollar cost is $0 but turns/tokens are still bounded. Configurable per project.
- **Human-in-the-loop by default.** PRs require human merge. Auto-merge is opt-in per project after trust is established.
- **100% open source.** Every tool in the stack is open source or built in-house. The only external dependency is the Anthropic API.
