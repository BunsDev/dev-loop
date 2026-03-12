# Tracer Bullets

Every feature is a vertical slice through all six layers. No horizontal building. Each TB has a single `just` command that runs it end-to-end.

---

## TB-1: Issue-to-PR (The Golden Path)

**What it proves:** The entire loop works. An issue goes in, a PR comes out, every layer is touched.

### Vertical Slice

| Layer | What happens | Minimal implementation |
|-------|-------------|----------------------|
| Intake | beads issue with no blockers detected | Poll `br ready --json` via MCP server |
| Orchestration | Worktree created, agent assigned | `git worktree add` + persona selection from `config/agents.yaml` |
| Runtime | Agent reads issue, modifies code, commits | `claude --print` via stdin pipe in worktree with scoped CLAUDE.md |
| Quality Gates | Gate 0 sanity (tests), Gate 2 gitleaks (secrets), Gate 4 LLM review | Claude Code CLI `--json-schema` for review + gitleaks scan |
| Observability | Full trace visible in OpenObserve | OTel spans at each layer boundary |
| Feedback Loop | On gate failure, error fed back to agent for 1 retry | Simple retry with error context appended to prompt |

### Entry Criteria
- beads workspace initialized with a test issue
- prompt-bench repo cloned and configured as test target
- OpenObserve running (Docker)
- gitleaks installed (`shutil.which` or `~/.local/bin`)

### Exit Criteria
- Issue moves from open → closed without human intervention
- All gates pass (Gate 0 sanity + Gate 2 secrets + Gate 4 review)
- Full trace visible in OpenObserve (intake → orchestration → runtime → gate → outcome)
- On gate failure, agent retries once with error context

### Command
```bash
just tb1 <issue_id> <repo_path>    # full run
```

### Status: PASSING (2026-03-12)
- 2 successful e2e runs: bug fix (94s), feature add (245s with 1 retry)
- 85 unit tests passing

---

## TB-2: Failure-to-Retry (The Feedback Path)

**What it proves:** The loop actually loops. Failures don't dead-end — they feed back and self-correct.

### Vertical Slice

| Layer | What happens | Minimal implementation |
|-------|-------------|----------------------|
| Intake | Issue that will intentionally fail gates | Seed issue with pre-seeded tricky test in prompt-bench |
| Orchestration | Same as TB-1 | `git worktree add` + persona selection |
| Runtime | Agent attempts work, produces code that fails pre-seeded tests | `claude --print` via stdin pipe |
| Quality Gates | Gate 0 fails with structured pytest error | Gate 0 catches test failures, returns error context |
| Observability | Failure trace captured, linked across attempts | OTel spans with explicit links between retry attempts |
| Feedback Loop | Error parsed, context injected, agent retried | Retry with accumulated gate failures in prompt |

### Entry Criteria
- TB-1 passes (golden path works)
- OpenObserve running (Docker)

### Exit Criteria
- Agent fails → retries with error context → succeeds on retry
- Both attempts visible as linked OTel traces (shared trace_id, span links)
- Agent stdout and gate results captured per attempt (retry_history)
- After max retries, issue correctly moves to "blocked" (verified programmatically)

### Command
```bash
just tb2 <issue_id> <repo_path>          # organic mode (tricky issue)
just tb2-force <issue_id> <repo_path>    # forced first-attempt failure
```

### Status: PASSING (2026-03-12)
- 3 successful e2e runs:
  - Forced failure mode: 202s (forced Gate 0 fail → retry → pass)
  - Organic mode: 134s (pre-seeded test trap caught missing edge case → retry → pass)
  - Escalation path: 41s (max_retries=0 + forced fail → blocked_verified=true)
- OTel span linking works (attempt_span_ids captured per run)
- `_verify_blocked_status()` confirms beads status = "blocked" after escalation

---

## TB-3: Security-Gate-to-Fix (The Safety Path)

**What it proves:** Security scanning is in the loop, not bolted on. Agents can self-remediate security findings.

### Vertical Slice

| Layer | What happens | Minimal implementation |
|-------|-------------|----------------------|
| Intake | Issue that will produce code with a known vulnerability | Seed issue: "add user search with raw SQL" |
| Orchestration | `git worktree add` + security-fix persona | `git worktree add` + `config/agents.yaml` security-fix persona |
| Runtime | Agent writes vulnerable code (SQL injection) | `claude --print` via stdin pipe, follows ticket literally |
| Quality Gates | Gate 3 (bandit SAST) catches vulnerability | `bandit -r src/ -f json` → structured Finding with CWE-89 |
| Observability | Security finding logged with CWE classification | OTel span with `security.cwe_ids`, `security.finding.B608` attributes |
| Feedback Loop | Finding fed back to agent with CWE context | Agent re-generates code using parameterized queries |

### Entry Criteria
- TB-1 and TB-2 pass
- bandit installed (`pip install bandit` or `uv sync`)

### Exit Criteria
- Agent produces vulnerable code → Gate 3 catches it → agent fixes it → clean scan
- Security finding appears in OpenObserve with CWE classification
- Fix diff is minimal (agent uses parameterized queries, not a rewrite)
- After max retries, issue correctly moves to "blocked"

### Command
```bash
just tb3 <issue_id> <repo_path>          # seeded mode (deterministic)
just tb3-organic <issue_id> <repo_path>  # organic mode (relies on agent)
```

### Status: PASSING (2026-03-12)
- 1 successful e2e run: seeded mode (55s, Gate 3 caught CWE-89 → retry → agent fixed → clean scan)
- Pre-flight scan detects 2 SQL injection findings (B608 CWE-89 at lines 24, 43)
- Agent uses parameterized queries on retry, vulnerability_fixed=true
- 121 unit tests passing

---

## TB-4: Cost-Spike-to-Pause (The Budget Path)

**What it proves:** Token spend is visible and controllable. Runaway agents get killed, not just logged.

### Vertical Slice

| Layer | What happens | Minimal implementation |
|-------|-------------|----------------------|
| Intake | Issue with intentionally vague/large scope | Seed issue: "refactor the entire codebase" |
| Orchestration | Agent assigned with cost ceiling | `git worktree add` + cost limit in runtime config |
| Runtime | Token proxy tracks spend per API call | OTel-instrumented proxy between agent and LLM API |
| Quality Gates | Cost gate checks total spend before PR creation | Threshold comparison (spent vs budget) |
| Observability | Real-time cost dashboard in OpenObserve | Token counts + model pricing → dollar amounts |
| Feedback Loop | On budget exceeded: agent killed, issue marked, human alerted | Kill signal → beads comment with cost breakdown |

### Entry Criteria
- TB-1 passes
- Token proxy deployed (even if just logging, not blocking)

### Exit Criteria
- Agent runs until cost ceiling hit → gracefully stopped
- Cost breakdown visible in OpenObserve (per-call, per-model, cumulative)
- beads issue gets a comment: "Budget exceeded: $X.XX spent of $Y.YY limit"
- Human can approve budget increase and restart

### Command
```bash
just tb4                    # run with low budget ($0.50)
just tb4 --budget 5.00      # override budget
```

---

## TB-5: Cross-Repo Cascade (The Multi-Project Path)

**What it proves:** Changes in one repo trigger downstream work in dependent repos.

### Vertical Slice

| Layer | What happens | Minimal implementation |
|-------|-------------|----------------------|
| Intake | PR merged in repo A that affects repo B's API contract | Watch for merged PRs via GitHub webhook |
| Orchestration | Detect dependency, create issue in beads for repo B | Dependency map config + beads issue creation |
| Runtime | Agent in repo B makes compatible changes | Claude Code in repo B worktree |
| Quality Gates | Both repos' test suites pass | Run tests in both worktrees |
| Observability | Cross-repo trace links both PRs to same root cause | OTel trace spans both repos with shared trace_id |
| Feedback Loop | If repo B fails, repo A PR gets a warning comment | GitHub comment on source PR |

### Entry Criteria
- TB-1 passes on at least 2 repos independently
- Dependency map defined (even if manual YAML for now)

### Exit Criteria
- Change in repo A → auto-issue in beads for repo B → auto-PR in repo B
- Both PRs linked via trace in OpenObserve
- If repo B can't adapt, repo A PR gets a comment warning about breakage

### Command
```bash
just tb5                    # trigger with test change in prompt-bench
just tb5 --source prompt-bench --target omniswipe-backend
```

---

## TB-6: Session Replay Debug (The Observability Path)

**What it proves:** When something goes wrong, you can replay and inspect every decision the agent made.

### Vertical Slice

| Layer | What happens | Minimal implementation |
|-------|-------------|----------------------|
| Intake | Any issue (reuse TB-2's failure case) | Existing issue |
| Orchestration | Normal flow | `git worktree add` + persona |
| Runtime | Agent session fully captured | AgentLens recording every tool call, context state, decision |
| Quality Gates | Gate failure triggers session save | On failure, session marked for review |
| Observability | Session browsable in AgentLens, linked to OTel trace | AgentLens UI shows timeline, tool calls, context window |
| Feedback Loop | Human reviews session → adjusts CLAUDE.md or harness config | Manual step: review → config change → re-run confirms fix |

### Entry Criteria
- TB-2 passes (we have a failure to debug)
- AgentLens capturing sessions

### Exit Criteria
- Failed session is fully replayable in AgentLens
- Can identify exactly which tool call / decision led to failure
- CLAUDE.md change based on session analysis prevents the same failure on re-run

### Command
```bash
just tb6                    # re-run TB-2 failure with full capture
just tb6 --session <id>     # replay a specific session
```

---

## Implementation Order

```
TB-1 (golden path) ──► TB-2 (failure/retry) ──► TB-3 (security gate)
                                                       │
TB-4 (cost control) ◄────────────────────────────────┘
       │
       ▼
TB-5 (cross-repo) ──► TB-6 (session replay)
```

TB-1 is the spine. Everything else builds on it. Do NOT start TB-2 until TB-1 passes end-to-end on prompt-bench.
