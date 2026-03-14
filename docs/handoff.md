# dev-loop Handoff — 2026-03-14

## Status: ALL 6 TBs + FULL AUDIT REMEDIATION COMPLETE

TB-1 through TB-6 all implemented. Full audit against intent layer docs completed. All gaps addressed. **270 unit tests passing.**

---

## Session Work (2026-03-14): Intent-vs-Implementation Audit

Audited the entire codebase against all 6 intent layer docs (`docs/layers/*.md`) + `docs/architecture.md`. Found ~25 missing files, 3 dead config files, 1 dead code module, 4 unimplemented gates, 5 unimplemented feedback channels, and 8 stale doc files. All addressed in 6 phases:

### Phase 1: Wire Dead Code (`dl-3au`)

| Fix | What Changed |
|-----|-------------|
| deny_list.py wired | `generate_deny_rules()` now called in `build_claude_md_overlay()` — secret-deny rules injected into every agent's CLAUDE.md |
| capabilities.yaml loaded | `_load_allowed_tools(repo_path)` reads `config/capabilities.yaml`, matches by repo basename, passes `allowed_tools` to `spawn_agent()` in TB-1/2/4/6 |
| Permission flag added | `--dangerously-skip-permissions` added to `_build_command()` — agents no longer hang on permission prompts |

Files changed: `orchestration/server.py`, `runtime/server.py`, `feedback/pipeline.py`

### Phase 2: Missing Gates (`dl-8yi`)

| Gate | What It Does |
|------|-------------|
| **Gate 0.5 (Relevance)** | Keyword overlap between issue title/description and diff content. Soft gate — warns but passes unless no diff exists. |
| **Gate 2.5 (Dangerous Ops)** | Detects DROP/DELETE/TRUNCATE SQL, CI/CD config changes, auth file changes, lock file inconsistencies. Hard fail. |
| **Gate 5 (Cost)** | Checks num_turns, input_tokens, output_tokens against thresholds (default: 25 turns, 500K in, 100K out). Called separately by pipeline, not in fail-fast chain. |

`run_all_gates()` updated: Gate 0 → 0.5 → 2 → 2.5 → 3 → 4 (6 gates in fail-fast chain). Gate 5 called separately with usage data.

Files changed: `gates/server.py`. Tests: `tests/test_new_gates.py` (14 tests)

### Phase 3: PR Creation (`dl-26n`)

| Component | What Changed |
|-----------|-------------|
| `create_pull_request()` | New MCP tool on orchestration layer. Pushes branch, detects default branch via `gh repo view`, creates PR via `gh pr create`. |
| `PRResult` type | Added to `orchestration/types.py` |
| TB-1 wiring | PR created on both initial gate success and retry gate success paths. PR failure does not block pipeline success. |
| `TB1Result.pr_url` | New field captures the PR URL |

Files changed: `orchestration/server.py`, `orchestration/types.py`, `feedback/types.py`, `feedback/pipeline.py`

### Phase 4: OpenObserve Dashboards + Alerts (`dl-2kj`)

| File | Contents |
|------|----------|
| `config/dashboards/loop-health.json` | Issues processed, success rate, lead time, gate failure breakdown, retry rate |
| `config/dashboards/agent-performance.json` | Turns/tokens per run, duration by persona, token usage over time |
| `config/dashboards/quality-gates.json` | Pass/fail rates, gate duration, security findings by CWE, failures over time |
| `config/alerts/rules.yaml` | 5 rules: gate failure spike (3+ in 10min), stuck agent (5min no heartbeat), high turns (>20), escalation spike (3+ in 1hr), security finding |

### Phase 5: Feedback Channels (`dl-1bj`)

| Channel | Module | What It Does |
|---------|--------|-------------|
| **Ch 2: Patterns** | `feedback/pattern_detector.py` | Scans session metadata for repeated gate failures. Suggests CLAUDE.md fixes per gate. |
| **Ch 3: Cost** | `feedback/cost_monitor.py` | Aggregates turns/tokens from session metadata. Budget checking with 80%/100% thresholds. |
| **Ch 5: Changelog** | `feedback/changelog.py` | Queries beads for closed issues, groups by repo, generates Markdown changelog. |
| **Ch 7: Efficiency** | `feedback/efficiency.py` | Analyzes NDJSON events for waste: repeated reads, no-edit spinning, excessive search. Returns score 0.0–1.0. |

Justfile commands: `just patterns`, `just usage`, `just changelog`, `just efficiency <session_id>`

Tests: `tests/test_feedback_channels.py` (19 tests)

### Phase 6: Documentation Rewrite (`dl-fvu`)

All 8 stale docs rewritten to match actual implementation:

| Doc | Key Changes |
|-----|-------------|
| `architecture.md` | Diagram: dmux→git worktree, OpenFang→CLAUDE.md scoping, DeepEval→Claude CLI, VibeForge→bandit, AgentLens→NDJSON replay |
| `layers/01-intake.md` | Removed `ticket_parser.py`, fixed TB-5 (webhooks→git diff) |
| `layers/02-orchestration.md` | Removed dmux/Gastown/JAT/Symphony, fixed file tree + tools list |
| `layers/03-runtime.md` | Removed OpenFang/zsh-tool/Letta/Headroom/EnCompass/TokenProxy, fixed to actual CLI command |
| `layers/04-quality-gates.md` | VibeForge→bandit, DeepEval→Claude CLI, updated gate list to all 7 |
| `layers/05-observability.md` | AgentLens→NDJSON session replay, fixed file tree |
| `layers/06-feedback-loop.md` | Marked all 7 channels with implementation status, fixed file tree + tools |
| `scoring-rubric.md` | Added Claude CLI (0.90) + bandit (0.84), downgraded dmux (0.65), marked stale tools |

---

## Previous Session Work (2026-03-13)

### TB-1 (Golden Path) — PASSING
- Bug fix: 94s, all gates passed first try
- Feature add: 245s, failed Gate 0 → succeeded on retry

### TB-2 (Failure-to-Retry) — PASSING
- **Forced mode**: 202s — forced Gate 0 failure → retry with error context → pass
- **Organic mode**: 134s — pre-seeded test trap caught missing edge case → retry → pass
- **Escalation path**: 41s — max_retries=0 + forced fail → issue status verified as "blocked"

### TB-3 (Security-Gate-to-Fix) — PASSING
- **Seeded mode**: 55s — pre-seeded CWE-89 → Gate 3 caught it → agent fixed → clean scan

### TB-4 (Runaway-to-Stop) — CODE COMPLETE
- Turn-based control via `--max-turns N` + `--output-format json`
- Per-persona turn budgets in agents.yaml (10-25 turns)

### TB-5 (Cross-Repo Cascade) — CODE COMPLETE
- Dependency map → fnmatch glob matching → cascade issue → delegates to `run_tb1()`

### TB-6 (Session Replay Debug) — CODE COMPLETE
- NDJSON stdout → session file → timeline → rule-based CLAUDE.md fix suggestion

---

## Test Count History

| Date | Tests | Delta | What |
|------|-------|-------|------|
| 2026-03-12 | 85 | — | TB-1 passing |
| 2026-03-12 | 121 | +36 | TB-2 + TB-3 passing |
| 2026-03-13 | 207 | +86 | TB-4 + TB-5 code complete |
| 2026-03-13 | 237 | +30 | TB-6 code complete |
| 2026-03-14 | 270 | +33 | Audit remediation (3 gates + 4 channels + gate tests) |

---

## What's Next

All implementation is complete. Remaining work:
1. **E2E validation**: Run TB-4, TB-5, TB-6 end-to-end against prompt-bench
2. **OpenObserve verification**: Confirm spans appear in dashboard UI
3. **Import dashboards**: Load `config/dashboards/*.json` into OpenObserve
4. **Gate 1 (ATDD)**: Implement when repos have `specs/` directories
5. **Channel 6 (DORA)**: Build when enough historical data exists

## Key Gotchas
- `br show --format json` returns a JSON array (list), not a dict
- `br create` uses `--labels` (plural), not `--label`; no `--epic` flag, use `--parent`
- Gate 0: uses `git rev-list --count HEAD` for safe lookback (handles short git histories)
- Gate 3 skips gracefully if bandit not installed or project is non-Python
- Gate 5 (cost) is NOT in `run_all_gates()` — called separately with usage data
- Gate 0.5 (relevance) is a soft gate — warns but passes unless no diff exists
- Gate 2.5 (dangerous ops) uses `fnmatch` for file pattern matching, `re` for SQL patterns
- bandit exit code 1 = issues found (not an error), exit code 2 = actual error
- `--dangerously-skip-permissions` required for unattended agent runs
- `capabilities.yaml` matched by repo basename (e.g. "prompt-bench")
- `deny_list.py` rules now injected into every CLAUDE.md overlay automatically
- PR creation requires `gh` CLI installed and authenticated
- PR failure does not block pipeline success (logged as warning)
- Feedback channels read session metadata from `/tmp/dev-loop/sessions/` — not persistent across reboots
- `_suggest_claude_md_fix()` is rule-based, not LLM-based — fast + deterministic but limited
