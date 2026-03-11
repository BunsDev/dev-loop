# Layer 1: Intake

## Purpose
Single entry point for all work. Every task enters the system as a Linear ticket. No back-channel requests, no "just run this real quick." If it doesn't have a ticket, it doesn't get an agent.

## Primary Tool: Linear

### Why Linear
- Developer-focused, keyboard-driven — agents and humans use the same interface
- API-first with webhooks — no scraping or polling hacks needed
- Projects, labels, and custom fields map cleanly to our orchestration needs
- Symphony (OpenAI) already integrates with Linear → proven pattern

### What Linear Tracks
- **Tickets** — one ticket per unit of work (bug fix, feature, refactor)
- **Labels** — map to agent config: `bug`, `feature`, `refactor`, `security`, `docs`
- **Custom fields** — `target_repo`, `cost_ceiling`, `priority`
- **Status flow**: Backlog → Ready → In Progress → In Review → Done / Blocked
- **DORA metrics** — lead time (Ready → Done), deployment frequency (Done count/week)

### MCP Server: `linear-intake`

```
src/mcp/linear-intake/
├── server.ts          # MCP server entry
├── poll.ts            # Poll Linear API for "Ready" tickets
├── webhook.ts         # Handle Linear webhooks (faster, TB-1 uses polling first)
├── ticket-parser.ts   # Extract structured data from ticket
└── types.ts           # Linear ticket → internal WorkItem type
```

**Tools exposed:**
- `poll_ready_tickets` — returns all tickets in "Ready" status for configured projects
- `get_ticket_detail` — full ticket with metadata, comments, linked issues
- `update_ticket_status` — move ticket to new status
- `add_ticket_comment` — post agent status updates back to the ticket

### OTel Instrumentation
Every ticket pickup emits a span:
```
span: intake.ticket_pickup
attributes:
  ticket.id: LIN-123
  ticket.repo: prompt-bench
  ticket.labels: [bug, backend]
  ticket.cost_ceiling: 2.00
  ticket.priority: high
```
This span becomes the root of the full trace for this work item.

### Tracer Bullet Coverage
- **TB-1**: Polling loop picks up a "Ready" ticket, starts the trace
- **TB-2**: Seed ticket with bad data, same intake path
- **TB-3**: Seed ticket that will produce a security vuln
- **TB-4**: Seed ticket with intentionally large scope
- **TB-5**: Listens for merged PR webhooks, creates downstream tickets
- **TB-6**: Same intake, full session captured downstream

### Escape Hatches
- `just run-direct --repo prompt-bench --task "fix the typo in README"` — bypass Linear entirely for quick one-offs
- Polling interval configurable (default 60s, `--poll-interval 10` for testing)
- Webhook mode optional — polling works for MVP, webhooks for production

### Open Questions
- [ ] Linear free tier limits? Need to verify API rate limits for polling
- [ ] Do we create sub-tickets for decomposed tasks, or keep it flat?
- [ ] How do we handle tickets that span multiple repos? (TB-5 addresses this)
