# Layer 6: Feedback Loop

## Purpose
Close the loop. Every output from the system feeds back as input. Failed runs get retried. Cost spikes get throttled. Trace patterns get turned into harness improvements. Nothing dead-ends.

## Feedback Channels

### Channel 1: Agent Retry (Automatic)

When a quality gate fails, the feedback loop:
1. Extracts the structured failure from the gate result
2. Builds a retry prompt with the failure context
3. Re-spawns the agent in the same worktree with the error appended
4. Tracks retry count (max from agent persona config)

```
Gate Failure
    │
    ▼
Parse failure reason ──► Build retry context ──► Re-spawn agent
                                                      │
                                                      ▼
                                               Run gates again
                                                      │
                                          ┌───────────┴───────────┐
                                          │                       │
                                       Pass → PR              Fail again
                                                                  │
                                                         Retry limit?
                                                      ┌─────┴─────┐
                                                      No          Yes
                                                      │           │
                                                   Retry      Escalate
                                                              (ticket → Blocked)
```

Retry context template:
```
Your previous attempt failed at the {{gate_name}} quality gate.

Failure details:
{{structured_failure}}

Please fix the issue and try again. Do not start over — your previous changes
are still in the worktree. Make the minimal change needed to pass the gate.
```

### Channel 2: Harness Tuning (Semi-Automatic)

When the same failure pattern repeats across multiple tickets:
1. OpenObserve alert fires: "Gate X has failed 5+ times this week with similar reasons"
2. AgentLens sessions for those failures are collected
3. Pattern analysis identifies the root cause (e.g., "agents keep introducing SQL injection because CLAUDE.md doesn't mention parameterized queries")
4. **Human reviews** the suggestion and updates harness config

This is the "harness engineering" approach from LangChain — improve the harness (prompts, tools, config), not the model.

```
Repeated failures
    │
    ▼
Alert: "pattern detected"
    │
    ▼
Collect AgentLens sessions
    │
    ▼
Analyze: what do failures have in common?
    │
    ▼
Suggest: CLAUDE.md rule, new gate, config change
    │
    ▼
Human approves ──► Config updated ──► Re-run to verify
```

### Channel 3: Cost Alerts (Automatic)

```
Token proxy ──► Per-run cost check
                    │
                    ├── Under budget → continue
                    ├── 80% of budget → warning span emitted
                    └── Over budget → agent killed, ticket commented

Aggregate cost ──► Daily/weekly budget check
                    │
                    ├── Under → normal
                    ├── 80% of weekly budget → Slack/email alert
                    └── Over → all new agent spawns paused, human unblocks
```

### Channel 4: Cross-Repo Cascade (Automatic)

```
PR merged in repo A
    │
    ▼
Dependency map check: does any other repo depend on changed files?
    │
    ├── No dependencies → done
    └── Repo B depends on changed API
         │
         ▼
    Create Linear ticket for repo B:
    "Upstream change in repo A (PR #123) may require updates.
     Changed files: src/api/auth.ts
     Breaking change: function signature changed"
         │
         ▼
    Ticket enters intake → normal loop for repo B
```

Dependency map (manual for now):
```yaml
# config/dependencies.yaml
dependencies:
  - source: prompt-bench
    target: omniswipe-backend
    watches:
      - "src/api/**"
      - "src/types/**"
    type: api-contract

  - source: omniswipe-backend
    target: omniswipe-mobile
    watches:
      - "src/routes/**"
      - "prisma/schema.prisma"
    type: api-contract
```

### Channel 5: Changelog Generation (Automatic)

```
PR merged
    │
    ▼
Extract: ticket title, PR description, files changed, gate results
    │
    ▼
Accumulate in changelog buffer
    │
    ▼
Weekly: generate changelog from buffer
    │
    ▼
Post to: Linear project update, GitHub release, Slack channel
```

Format:
```markdown
## Week of 2026-03-10

### prompt-bench
- **Fixed** auth token refresh race condition (LIN-123) — 0.87 USD, 1 retry
- **Added** rate limiter to /api/eval endpoint (LIN-125) — 1.23 USD, 0 retries

### omniswipe-backend
- **Fixed** Prisma connection pool exhaustion (LIN-130) — 0.45 USD, 0 retries

### Stats
- Tickets completed: 3
- Total cost: $2.55
- Average lead time: 12 minutes
- Gate failure rate: 33% (1 retry in 3 runs)
```

### Channel 6: DORA Feedback (Dashboard)

Not automatic — this is for the human to monitor and adjust the system:
- If lead time is increasing → investigate: are agents getting stuck? are gates too strict?
- If change failure rate is high → investigate: are gates not catching regressions?
- If deployment frequency is low → investigate: are tickets too large? decomposition needed?
- If MTTR is high → investigate: is OneUptime alerting? are incidents actionable?

## MCP Server: `feedback-loop`

```
src/mcp/feedback-loop/
├── server.ts          # MCP server entry
├── retry.ts           # Parse gate failure → build retry context → re-spawn
├── pattern-detector.ts # Find repeated failure patterns across runs
├── cascade.ts         # Watch for merged PRs → create downstream tickets
├── changelog.ts       # Accumulate and generate changelogs
├── cost-monitor.ts    # Aggregate cost tracking and alerting
└── types.ts
```

**Tools exposed:**
- `retry_agent` — re-spawn agent with failure context
- `detect_patterns` — analyze recent failures for common causes
- `check_cascade` — given a merged PR, find affected downstream repos
- `generate_changelog` — produce changelog for a time range
- `get_cost_summary` — aggregate cost data with breakdown

### OTel Instrumentation
```
span: feedback.retry
attributes:
  retry.attempt: 1
  retry.reason: "security gate: SQL injection in src/db/query.ts:42"
  retry.gate_failed: security
  retry.previous_span_id: <span from failed run>
parent: trace root (same trace as original attempt)

span: feedback.cascade
attributes:
  cascade.source_repo: prompt-bench
  cascade.source_pr: 123
  cascade.target_repo: omniswipe-backend
  cascade.ticket_created: LIN-456
parent: new trace (linked to source trace)
```

### Open Questions
- [ ] Retry prompt: should we include the full gate output or a summary?
- [ ] Pattern detection: LLM-based or rule-based? (rule-based for TB-2, LLM for later)
- [ ] Cascade: how to detect breaking vs non-breaking changes? (start with "all changes cascade")
- [ ] Changelog: per-repo or unified? (unified for now, per-repo if noise increases)
- [ ] How does the human "approve" a harness tuning suggestion? (PR to dev-loop repo?)
