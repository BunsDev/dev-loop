# dev-loop Handoff — 2026-03-10

## What This Is
A complete intent layer for a tracer-bullet-driven developer tooling harness. 28 files, 2,871 lines, zero code. Every document exists so the next session can build without re-deriving decisions.

## What Was Done
1. Defined 6-layer architecture: Intake → Orchestration → Runtime → Quality Gates → Observability → Feedback Loop
2. Defined 6 tracer bullets (vertical slices), each with entry/exit criteria and per-layer breakdowns
3. Wrote intent docs for all 6 layers with MCP server specs, OTel span schemas, and per-project config
4. Wrote 6 ADRs (tracer bullets, MCP integration, OpenObserve, OpenFang, Linear, dedicated committer)
5. Created 7-dimension scoring rubric (all tools TBD — score before building)
6. Identified 41 edge cases across 2 passes:
   - Pass 1 (25): race conditions, infinite loops, state recovery, security, correctness, operational, bootstrapping
   - Pass 2 (16): context scaling, backpressure, flaky tests, dangerous ops, priority, model routing, ambiguity, licensing
7. Created justfile with stub commands for all TBs + emergency-stop, recover, worktree-gc, mock intake
8. Created 3 mock ticket fixtures (tb1-sample, tb2-failure, tb3-vulnerability)
9. Created .env.example, network requirements doc, GitHub issue template

## What Was NOT Done
- No GitHub repo created (local only at ~/dev-loop)
- No code written
- No tools installed or configured
- No Linear project created
- No scoring done (all tools show TBD)
- prompt-bench not cloned

## Tool Stack (Final)

### Intake
- Linear (task management, DORA metrics)

### Orchestration
- dmux (worktree isolation) — also evaluate Gastown
- Agent personas (YAML config → CLAUDE.md overlay)
- Ambiguity detection (flag vague tickets)
- Priority queuing + budget throttling
- Model selection per persona (Haiku/Sonnet/Opus)

### Runtime
- OpenFang (WASM sandbox — deferred to TB-3)
- zsh-tool MCP (circuit breaker, hang prevention)
- Continuous-Claude-v3 OR Letta (context persistence — evaluate both)
- Headroom (context compression, 47-92% reduction)
- Token proxy (cost metering → OpenObserve)
- Tiered context loading (hot/warm/cold)

### Quality Gates (sequential)
- Gate 0: Sanity (compile, test, empty-diff check, lock file consistency)
- Gate 0.5: Task relevance (LLM-as-judge: does diff match ticket?)
- Gate 1: ATDD (acceptance tests if spec exists)
- Gate 2: Secret scanner (regex + entropy on diff)
- Gate 2.5: Dangerous operations (migrations, CI config, auth changes → human)
- Gate 3: Aikido (SAST/SCA/DAST/IaC/container)
- Gate 4: CodeRabbit (AI code review)
- Gate 5: Cost check (budget vs spend)
- Pre-gate: In-process backpressure (tsc/mypy after every edit, tests before commit)

### Observability
- OpenTelemetry (instrumentation standard, every layer emits spans)
- OpenObserve (logs, metrics, traces, 5 dashboards)
- AgentLens (session replay/debug)
- OneUptime (incidents + auto-remediation)
- DORA dashboards (deploy freq, lead time, change failure rate, MTTR)

### Feedback Loop
- Channel 1: Agent retry (gate failure → error context → re-spawn, max 2-3)
- Channel 2: Harness tuning (repeated failure pattern → suggest config change → human reviews)
- Channel 3: Cost alerts (per-run ceiling + weekly budget + throttling)
- Channel 4: Cross-repo cascade (PR merged → dependency check → downstream tickets)
- Channel 5: Changelog generation (weekly digest from Linear + PRs)
- Channel 6: DORA feedback (dashboard for human to monitor system health)

## Critical Edge Cases to Fix Before TB-1

| # | Problem | Fix |
|---|---------|-----|
| 1 | Duplicate ticket pickup | Optimistic locking (claim-before-spawn) |
| 7 | Crash mid-run, orphaned state | Heartbeat spans + `just recover` |
| 11 | Secrets in agent context | CLAUDE.md deny list + denied_paths config |
| 14 | Agent does wrong thing for ticket | Gate 0.5: task relevance check |
| 17 | No emergency stop | `just emergency-stop` (kill agents, pause intake) |
| 28 | Backpressure wasted (post-gate only) | In-process type-check/test in CLAUDE.md overlay |
| 35 | Agent hallucination | "Read before call" CLAUDE.md rule |

## Next Steps (In Order)

1. **Create GitHub repo** — `gh repo create musicofhel/dev-loop --public --source ~/dev-loop`
2. **Clone prompt-bench** — primary test target for TB-1
3. **Sign up for Linear** — free tier, create dev-loop project, verify API limits
4. **Score TB-1 tools** — Linear, dmux, CodeRabbit, OpenObserve against rubric (docs/scoring-rubric.md)
5. **Install TB-1 dependencies** — `just` (task runner), dmux, OpenObserve (Docker), CodeRabbit CLI
6. **Fix the 7 critical edge cases** above — these go into the first real code
7. **Build TB-1** — thinnest vertical slice: poll Linear → dmux worktree → Claude Code → CodeRabbit → OTel trace → retry on failure
8. **Run TB-1 on prompt-bench** — validate end-to-end
9. **Score TB-1 tools with real data** — update scoring rubric
10. **Build TB-2** — failure/retry path, requires TB-1 passing

## File Map

```
~/dev-loop/
├── README.md                              # Overview, layer table, TB status, doc index
├── CLAUDE.md                              # Build rules: tracer bullets only, no horizontal
├── .env.example                           # All required env vars
├── .gitignore
├── justfile                               # All commands: tb1-6, stack, safety, utils
├── test-fixtures/tickets/                 # Mock tickets for testing without Linear
│   ├── tb1-sample.yaml                    #   Clean bug fix
│   ├── tb2-failure.yaml                   #   Intentional failure (nonexistent file)
│   └── tb3-vulnerability.yaml             #   Intentional SQL injection
├── .github/ISSUE_TEMPLATE/
│   └── tracer-bullet.md                   # Template for new vertical slices
└── docs/
    ├── architecture.md                    # System diagram, data flow, multi-project model
    ├── tracer-bullets.md                  # 6 TBs with layer breakdowns + criteria
    ├── edge-cases.md                      # Pass 1: 25 failure modes (races, crashes, security)
    ├── edge-cases-pass2.md                # Pass 2: 16 design gaps (scaling, backpressure, ops)
    ├── scoring-rubric.md                  # 7-dimension tool eval, all TBD
    ├── test-repos.md                      # prompt-bench, backend, pipeline targets
    ├── network-requirements.md            # APIs, ports, degradation behavior
    ├── handoff.md                         # THIS FILE
    ├── layers/
    │   ├── 01-intake.md                   # Linear polling/webhooks, MCP server spec
    │   ├── 02-orchestration.md            # dmux, personas, scheduling, model selection
    │   ├── 03-runtime.md                  # Sandbox, memory, Headroom, token proxy
    │   ├── 04-quality-gates.md            # 8 gates + in-process backpressure
    │   ├── 05-observability.md            # OTel, OpenObserve, AgentLens, 5 dashboards
    │   └── 06-feedback-loop.md            # 6 feedback channels
    └── adrs/
        ├── 001-tracer-bullet-approach.md
        ├── 002-mcp-as-integration-layer.md
        ├── 003-openobserve-over-alternatives.md
        ├── 004-openfang-sandboxing.md
        ├── 005-linear-as-intake.md
        └── 006-dedicated-committer-agent.md
```
