# Layer 5: Observability

## Purpose
See everything. Every ticket, every agent run, every tool call, every dollar spent, every gate result — visible in one place. Not just logging — tracing (causal chains), metrics (trends), and replay (debugging).

## The Three Pillars + One

| Pillar | Tool | What it answers |
|--------|------|----------------|
| **Traces** | OpenTelemetry → OpenObserve | "What happened in this run, step by step?" |
| **Metrics** | OpenTelemetry → OpenObserve | "Are we getting faster? Cheaper? More reliable?" |
| **Logs** | OpenObserve | "What did the agent print/say/error?" |
| **Replay** | AgentLens | "Show me exactly what the agent saw and did." |

## OpenTelemetry (Instrumentation Standard)

Every layer in dev-loop emits OTel spans. This is non-negotiable — if a layer doesn't emit spans, it's invisible.

### Span Hierarchy
```
trace: T-abc123 (one per ticket)
├── span: intake.ticket_pickup
│   └── attributes: ticket.id, ticket.repo, ticket.labels
├── span: orchestration.setup
│   └── attributes: agent.persona, worktree.branch, task.complexity
├── span: runtime.execution
│   ├── span: runtime.tool_call (N times)
│   │   └── attributes: tool.name, tool.duration_ms
│   ├── span: runtime.llm_call (N times)
│   │   └── attributes: model, tokens_in, tokens_out, cost_usd
│   └── attributes: total_tool_calls, total_tokens, total_cost
├── span: quality_gates.run_all
│   ├── span: quality_gates.gate_0_sanity
│   ├── span: quality_gates.gate_1_atdd
│   ├── span: quality_gates.gate_2_secrets
│   ├── span: quality_gates.gate_3_security
│   ├── span: quality_gates.gate_4_review
│   └── span: quality_gates.gate_5_cost
├── span: feedback.outcome_routing
│   └── attributes: outcome (pr_created | retry | blocked)
└── span: feedback.retry (if applicable)
    └── (entire runtime + gates subtree repeated)
```

### Semantic Conventions
Custom attribute namespace: `devloop.*`

```
devloop.ticket.id          # Linear ticket ID
devloop.ticket.repo        # Target repository
devloop.agent.id           # Unique agent run ID
devloop.agent.persona      # bug-fix, feature, refactor, security-fix
devloop.tracer_bullet      # tb1, tb2, etc.
devloop.cost.budget_usd    # Budget for this run
devloop.cost.spent_usd     # Actual spend
devloop.gate.name          # Gate name
devloop.gate.status        # pass, fail, skip
devloop.retry.attempt      # 0, 1, 2
devloop.retry.reason       # Why the previous attempt failed
```

## OpenObserve (Storage + Dashboards)

### Deployment
```bash
# Single binary, Docker
docker run -d \
  --name openobserve \
  -p 5080:5080 \
  -v openobserve-data:/data \
  -e ZO_ROOT_USER_EMAIL=admin@dev-loop.local \
  -e ZO_ROOT_USER_PASSWORD=devloop123 \
  public.ecr.aws/zinclabs/openobserve:latest
```

### Dashboards

**Dashboard 1: Loop Health**
- Tickets processed (today/week/month)
- Success rate (PRs created / tickets attempted)
- Average lead time (ticket pickup → PR created)
- Average cost per ticket
- Gate failure breakdown (which gates fail most)

**Dashboard 2: Agent Performance**
- Token usage per run (trend)
- Tool calls per run (trend)
- Cost per run by persona type
- Retry rate by persona type
- Time-to-completion distribution

**Dashboard 3: Quality Gate Insights**
- Gate pass/fail rates over time
- Most common failure reasons
- Security findings by CWE category
- CodeRabbit critical findings trend
- Secret scanner catches (should be zero in steady state)

**Dashboard 4: DORA Metrics**
- Deployment frequency: PRs merged per week per repo
- Lead time: ticket created → PR merged
- Change failure rate: PRs reverted or causing incidents
- MTTR: incident detected → resolved (from OneUptime)

**Dashboard 5: Cost Tracking**
- Total spend (daily/weekly/monthly)
- Spend by project
- Spend by agent persona
- Spend by model (if using multiple)
- Budget utilization (spent/budget ratio)

## AgentLens (Session Replay)

### What it captures
- Every tool call the agent made (with arguments and results)
- Every LLM call (prompt + response)
- Context window state over time
- Decision points (where the agent chose path A over path B)
- File reads and writes
- Time between actions

### Integration
AgentLens runs alongside the agent in the worktree. It hooks into Claude Code's tool execution layer.

```
src/mcp/agentlens-bridge/
├── server.ts      # MCP server that AgentLens talks to
├── recorder.ts    # Captures tool calls and LLM calls
├── linker.ts      # Links session to OTel trace_id
└── types.ts
```

### Usage
```bash
# After a failed run, find the session
just sessions list --status failed
# Replay it
just sessions replay <session-id>
# Compare two attempts of the same ticket
just sessions diff <session-id-1> <session-id-2>
```

## OneUptime (Incident Management)

### When it triggers
- OpenObserve alert rule fires (e.g., 3+ gate failures in 10 minutes)
- Agent stuck for > 5 minutes with no tool calls
- Cost ceiling exceeded across all projects
- Service health check fails (Linear API, Anthropic API, OpenObserve)

### What it does
- Creates incident with context (linked traces, gate results)
- Sends notification (webhook, Slack, email — configurable)
- Tracks resolution timeline (MTTR)
- AI-powered root cause suggestion (optional)

## MCP Server: `observability`

```
src/mcp/observability/
├── server.ts          # MCP server entry
├── otel-setup.ts      # Initialize OTel SDK, configure exporters
├── span-factory.ts    # Helper to create properly attributed spans
├── dashboards/        # Dashboard definitions (JSON/YAML)
├── alerts/            # Alert rule definitions
└── types.ts
```

**Tools exposed:**
- `query_traces` — search traces by ticket ID, agent ID, status
- `get_trace_detail` — full span tree for a trace
- `get_metrics` — query metrics (cost, token usage, lead time)
- `create_alert` — define a new alert rule
- `get_dora_metrics` — DORA metrics for a time range

### OTel Setup (Shared)

```typescript
// src/mcp/observability/otel-setup.ts
// All layers import this to get consistent instrumentation

import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter({
    url: 'http://localhost:5080/api/default/v1/traces',
  }),
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({
      url: 'http://localhost:5080/api/default/v1/metrics',
    }),
  }),
});
```

### Open Questions
- [ ] OpenObserve retention policy — how long to keep traces? (30 days default)
- [ ] AgentLens storage — local files or ship to OpenObserve?
- [ ] OneUptime self-hosted vs cloud? (self-hosted is free, cloud has more features)
- [ ] Alert fatigue — what's the right threshold before we tune out notifications?
- [ ] How to correlate AgentLens sessions with OTel traces? (trace_id as link)
