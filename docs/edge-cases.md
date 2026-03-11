# Edge Cases & Failure Modes

Things that will break if we don't design for them.

---

## Race Conditions

### 1. Duplicate Ticket Pickup
**Problem:** Two polling cycles fire before the first one marks the ticket "In Progress." Two agents grab the same ticket.

**Fix:** Optimistic locking. Before spawning an agent, atomically update the ticket status to "In Progress" via Linear API. If the update fails (status already changed), skip the ticket. The poll → claim → spawn sequence must be atomic.

```
poll() → ticket is "Ready"
claim(ticket) → Linear API: update status to "In Progress" ONLY IF current status is "Ready"
  → success: spawn agent
  → failure (409/conflict): another instance claimed it, skip
```

**TB-1 action:** Implement claim-before-spawn in intake MCP server.

### 2. Merge Conflicts on Worktree Merge
**Problem:** Two agents work on the same repo simultaneously (different tickets). Agent A merges first. Agent B's worktree now has conflicts with main.

**Fix:**
- Before merging, rebase worktree branch onto updated main
- If rebase conflicts: attempt auto-resolve (accept both for additive changes)
- If auto-resolve fails: mark ticket as "Needs Manual Merge" instead of "Blocked"
- Long-term: dmux handles this, but we need to verify its conflict resolution behavior

**TB-5 action:** This is primarily a TB-5 concern (cross-repo cascade), but can happen in TB-1 if running multiple tickets concurrently.

### 3. Webhook Deduplication
**Problem:** Linear/GitHub fires the same webhook twice (network retry, infrastructure hiccup). Same ticket gets processed twice.

**Fix:** Idempotency key. Every webhook has a unique event ID. Store processed event IDs in a set (Redis, file, in-memory for MVP). Skip if already seen.

```
webhook received → event_id = "evt_abc123"
if event_id in processed_set → skip
else → processed_set.add(event_id) → process
```

TTL on the set: 24 hours (no need to remember forever).

**TB-1 action:** Polling-based intake doesn't have this problem (we check ticket status). Relevant when we add webhook mode.

---

## Infinite Loops

### 4. Agent ↔ Gate Disagreement Loop
**Problem:** Agent produces code → CodeRabbit says "add error handling" → agent adds error handling → CodeRabbit says "error handling is too verbose" → agent simplifies → CodeRabbit says "add error handling" → forever.

**Fix:** Retry cap is necessary but not sufficient. Additional rule: **the retry prompt must include ALL previous gate feedback, not just the latest.** This way the agent sees the contradiction and can make a balanced choice.

Also: after max retries, the gate failure history gets attached to the "Blocked" ticket so a human can see the oscillation pattern and adjust gate config.

**TB-2 action:** Include full gate history in retry context, not just last failure.

### 5. Cross-Repo Cascade Loop
**Problem:** Repo A changes API → cascade creates ticket for Repo B → Repo B updates its code → Repo B's PR merges → cascade detector sees Repo B changed → creates ticket for Repo A → infinite loop.

**Fix:** Cascade has a `source_trace_id`. If a cascaded ticket's resolution triggers another cascade, check if the new cascade traces back to the same `source_trace_id`. If yes: stop, log, alert. One cascade chain per root cause.

```yaml
# Each cascade event carries lineage
cascade:
  source_trace_id: T-abc123  # original root cause
  depth: 2                    # how many hops from root
  max_depth: 3                # hard limit
```

**TB-5 action:** Implement cascade depth tracking and cycle detection.

### 6. Harness Tuning Regression
**Problem:** Pattern detector suggests a CLAUDE.md change. Change makes gate X pass but gate Y now fails more often. Next tuning cycle suggests reverting. Oscillation.

**Fix:** This is a human-reviewed channel (Channel 2 in feedback loop doc), so the human is the circuit breaker. But we need to arm the human with data: **before/after metrics for every harness change.** Track which config version each run used, so you can diff performance across config versions.

**TB-6 action:** Tag every OTel trace with `harness.config_version`. Dashboard shows pass rates by config version.

---

## State & Recovery

### 7. Harness Crashes Mid-Run
**Problem:** The orchestrator crashes after spawning an agent but before the quality gates run. Ticket stuck in "In Progress" forever. Orphaned worktree. No trace completion.

**Fix:** Heartbeat + timeout.
- Agent emits a heartbeat span every 30 seconds while running
- If no heartbeat for 5 minutes: assume crash
- Recovery: check ticket status, check worktree exists, check for uncommitted work
- If uncommitted work exists: save worktree state, mark ticket "Interrupted" with recovery context
- If no work: clean up worktree, reset ticket to "Ready"

**TB-1 action:** Implement heartbeat as OTel spans. Add a `just recover` command that finds orphaned runs.

### 8. Orphaned Worktrees
**Problem:** Crashed runs, killed agents, or bugs leave worktrees that never get cleaned up. Disk fills up.

**Fix:**
- `just worktree-gc` command: find worktrees older than 24h with no recent commits, prompt to delete
- Each worktree gets a `.dev-loop-metadata.json` with creation time, ticket ID, agent ID
- Stack health check (`just stack-health`) reports orphaned worktree count

**TB-1 action:** Write metadata file on worktree creation. Add GC to justfile.

### 9. Token Proxy SPOF
**Problem:** If the token proxy crashes, agents can't make LLM calls. All in-flight work stalls.

**Fix:** Token proxy should be optional. If proxy is unreachable, agents fall back to direct API calls. Metering data is lost for that run, but work isn't blocked. Log a warning.

Design: proxy as a sidecar, not a gateway. Agent tries proxy → timeout after 2s → fall back to direct.

**TB-4 action:** This is the TB where cost control becomes real. For TB-1, skip proxy entirely.

### 10. OpenObserve Down
**Problem:** OpenObserve crashes or is unreachable. OTel exporter fails. Does the whole loop stop?

**Fix:** No. OTel exporters have built-in retry and buffering. If OpenObserve is down, spans queue in memory and flush when it recovers. The loop itself never depends on observability being available — it's fire-and-forget instrumentation.

**TB-1 action:** Verify that OTel SDK doesn't block on export failure. Set reasonable buffer limits.

---

## Security

### 11. Secrets in Agent Context → LLM API
**Problem:** Agent reads a `.env` file during codebase exploration. File contents end up in the context window. Context gets sent to the LLM API. Secret is now in Anthropic's logs.

**Fix:** Multiple layers:
1. **CLAUDE.md deny list:** Agent is told to never read `.env`, `*.key`, `*.pem`, `credentials.*`
2. **Capability scoping:** `denied_paths` in config blocks tool calls to sensitive files
3. **Secret scanner in context:** Before every LLM call, scan the outgoing prompt for high-entropy strings matching secret patterns. If found, redact and log.
4. **Long-term (OpenFang):** File system capabilities that prevent the agent from reading sensitive paths at the OS level.

**TB-1 action:** CLAUDE.md deny list + denied_paths config. Layer 3 (context scanning) in TB-3.

### 12. Webhook Signature Verification
**Problem:** Anyone who knows the webhook URL can send fake events. Attacker sends a fake "ticket ready" webhook → agent runs on attacker-controlled ticket description → prompt injection.

**Fix:** Verify webhook signatures. Linear signs webhooks with HMAC-SHA256. GitHub uses `X-Hub-Signature-256`. Always verify before processing.

**TB-1 action:** Not relevant (polling mode). Must be in place before enabling webhook mode.

### 13. MCP Server Authentication
**Problem:** MCP servers listen on localhost ports. Any local process can call them. If the machine is compromised, attacker can call any MCP tool.

**Fix:** For local-only development: acceptable risk (same trust boundary). For remote/shared deployment: MCP servers should require a bearer token. Design MCP servers with an optional auth middleware from day one.

**TB-1 action:** Accept localhost-only risk. Note in architecture doc.

---

## Correctness

### 14. Task Relevance Gap
**Problem:** Quality gates check code quality (security, style, tests) but NOT whether the change actually addresses the ticket. Agent could make a perfect, well-tested change to the wrong thing.

**Fix:** Add a Gate 0.5: **Task Relevance Check.** LLM-as-judge compares the diff against the ticket description and scores relevance. If the diff doesn't address the ticket requirements, gate fails.

```
Ticket: "Fix the auth token refresh race condition"
Diff: Reformatted README.md

Task Relevance: FAIL
Reason: Changes do not address the stated issue.
```

This is different from CodeRabbit (which reviews code quality) — this reviews task alignment.

**TB-2 action:** Add relevance check. It's cheap (one LLM call) and catches a real failure mode.

### 15. "Done But Empty"
**Problem:** Agent reports success but didn't actually make meaningful changes. Maybe it read the code, decided the ticket was already resolved, and committed nothing.

**Fix:** Gate 0 (sanity check) should verify: `git diff --stat` shows at least 1 file changed. If zero changes: gate fails with "no changes detected." Agent is re-prompted: "You reported completion but made no changes. Either make the fix or explain why no changes are needed."

If agent explains (ticket already fixed, duplicate, etc.): route to human for verification. Don't auto-close.

**TB-1 action:** Add empty-diff check to Gate 0.

### 16. Scope Creep
**Problem:** Ticket says "fix typo in auth.ts" but agent refactors the entire auth module because it "noticed improvements."

**Fix:**
- CLAUDE.md rule: "Only modify files directly related to the ticket. Do not refactor surrounding code."
- Gate metric: `files_modified_count`. If the ticket is labeled `bug` and >5 files changed, flag for review.
- CodeRabbit can also flag this: "These changes appear to go beyond the stated scope."

**TB-1 action:** CLAUDE.md scope rule. File count threshold in Gate 0.

---

## Operational

### 17. Emergency Stop
**Problem:** Something goes badly wrong and you need to stop ALL agents immediately. There's no kill switch.

**Fix:** `just emergency-stop` command:
1. Kill all running agent processes
2. Mark all "In Progress" tickets as "Interrupted"
3. Stop polling/webhooks
4. Post to all open worktrees: "Emergency stop triggered at [timestamp]"
5. Leave worktrees intact for forensics

**TB-1 action:** Add to justfile. Even if implementation is `pkill -f "claude"`, the command should exist.

### 18. Who Watches the Watchmen?
**Problem:** The harness itself has bugs. OpenObserve tracks agent runs but not harness health. If the intake poller silently stops, nobody notices.

**Fix:**
- Harness emits its own health metrics: `devloop.intake.last_poll_time`, `devloop.orchestrator.active_runs`, `devloop.gates.queue_depth`
- OneUptime health check: ping `just stack-health` every 5 minutes
- If any component reports unhealthy: alert

**TB-1 action:** Add basic health metrics to intake. Full monitoring in TB-6.

### 19. Config Versioning
**Problem:** You update `config/agents.yaml` or a project's quality gate thresholds. How do you know which config version was active for a given run? How do you roll back a bad config change?

**Fix:** The config directory is in git. Every config change is a commit. OTel traces include `harness.config_commit` (the git SHA of the dev-loop repo at run time). To roll back: `git revert` the config change.

**TB-1 action:** Add `harness.config_commit` to root span attributes.

---

## Bootstrapping

### 20. Cold Start / First Run
**Problem:** First time running TB-1, there's no memory, no traces, no context. The feedback loop has nothing to feed back. Agent has no prior context about the repo.

**Fix:** This is fine. The first run IS the bootstrap. Memory starts empty, traces start from zero. The system is designed to improve over time — the first run is the worst it will ever be. Document this: "Expect the first run to be slow and possibly fail. That's the point — the feedback loop starts learning."

**TB-1 action:** No action needed. Just set expectations.

### 21. Linear Setup Chicken-and-Egg
**Problem:** You need Linear configured before TB-1 can run. But you might want to test the harness layers without Linear.

**Fix:** Already handled — `just run-direct` bypasses Linear. But we should also have a `just tb1 --mock-intake` that simulates a Linear ticket from a local YAML file.

```yaml
# test-fixtures/tickets/tb1-sample.yaml
id: MOCK-001
title: "Fix typo in README.md"
repo: prompt-bench
labels: [bug]
cost_ceiling: 1.00
description: "There's a typo in the installation section..."
```

**TB-1 action:** Add mock intake mode to justfile and test fixtures directory.

---

## Missing from Current Docs

### 22. No `.env.example`
Need a file showing all required environment variables:
- `LINEAR_API_KEY`
- `ANTHROPIC_API_KEY`
- `GITHUB_TOKEN`
- `OPENOBSERVE_URL`
- `CODERABBIT_API_KEY`
- `AIKIDO_API_KEY` (TB-3)

### 23. No Network Requirements
Document what external APIs the harness calls, what ports it listens on, and what happens when each is unreachable.

### 24. No Gastown Reference
The graph has `steveyegge/gastown` — multi-agent workspace manager that persists work state in git-backed hooks, handles 20-30 concurrent agents. This is an alternative to dmux worth evaluating. Add to scoring rubric.

### 25. EnCompass (Checkpoint/Rewind)
Graph has `EnCompass` — lets you rewind LLM-powered programs to a checkpoint when they go off track. Useful for the retry path (TB-2) — instead of restarting the agent from scratch, rewind to the last good checkpoint.

---

## Priority Matrix

| Edge Case | Severity | TB Affected | When to Fix |
|-----------|----------|-------------|-------------|
| #1 Duplicate pickup | HIGH | TB-1 | Before TB-1 |
| #7 Crash recovery | HIGH | TB-1 | Before TB-1 |
| #11 Secrets in context | HIGH | TB-1 | Before TB-1 |
| #14 Task relevance | HIGH | TB-1 | Before TB-2 |
| #17 Emergency stop | HIGH | All | Before TB-1 |
| #15 Done-but-empty | MEDIUM | TB-1 | During TB-1 |
| #4 Gate disagreement | MEDIUM | TB-2 | During TB-2 |
| #2 Merge conflicts | MEDIUM | TB-5 | During TB-5 |
| #5 Cascade loops | MEDIUM | TB-5 | During TB-5 |
| #8 Orphaned worktrees | LOW | TB-1 | After TB-1 |
| #3 Webhook dedup | LOW | N/A (polling) | When webhooks added |
| #9 Token proxy SPOF | LOW | TB-4 | During TB-4 |
| #16 Scope creep | LOW | TB-1 | During TB-1 |
