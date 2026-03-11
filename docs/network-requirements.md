# Network Requirements

## External APIs Called

| Service | URL | Required For | Fallback If Unreachable |
|---------|-----|-------------|------------------------|
| Linear API | api.linear.app | Intake (all TBs) | `just run-direct` or `--mock-intake` |
| Anthropic API | api.anthropic.com | Agent runtime (all TBs) | None — agents can't work without it |
| GitHub API | api.github.com | PR creation, cascade detection | Manual PR creation |
| CodeRabbit | api.coderabbit.ai | Gate 4 review (TB-1+) | `--skip-review` flag |
| Aikido | api.aikido.dev | Gate 3 security (TB-3+) | `--skip-security` flag |

## Local Ports

| Port | Service | Purpose |
|------|---------|---------|
| 5080 | OpenObserve | Traces, metrics, logs, dashboards |
| 4318 | OTel Collector (optional) | OTLP HTTP receiver (if using collector) |

## What Happens When Things Are Down

### Anthropic API down
**Impact:** Total stop. No agents can run.
**Detection:** Health check in `just stack-health`.
**Response:** Queue tickets, resume when API returns.

### Linear API down
**Impact:** No new tickets picked up. In-flight work continues.
**Detection:** Polling returns error, logged + alerted.
**Response:** Use `just run-direct` for urgent work.

### GitHub API down
**Impact:** PRs can't be created. Agent work completes but isn't published.
**Detection:** PR creation fails, logged.
**Response:** Worktree with completed work persists. PR created when GitHub returns.

### OpenObserve down
**Impact:** Traces queue in memory (OTel SDK buffering). No dashboards.
**Detection:** `just stack-health` reports unhealthy.
**Response:** Loop continues. Traces flush when OpenObserve recovers. Buffer overflow drops oldest spans.

### CodeRabbit/Aikido down
**Impact:** Quality gates that depend on them can't run.
**Detection:** Gate timeout (30s default).
**Response:** Gate marked as "skipped (service unavailable)" — does NOT block the PR. Logged as warning. Human reviews PR without AI review assistance.
