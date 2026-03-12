# dev-loop Handoff — 2026-03-12

## Status: TB-1 PASSING

TB-1 is fully operational. Two successful end-to-end runs completed:
- **Bug fix** (modulo zero-guard): 94s, all gates passed first try
- **Feature add** (factorial function): 245s, failed Gate 0 on first try, succeeded on retry

## What Was Done This Session

### 1. Created beads issues from handoff, executed all 17
Previous session left 6 TODO items. Created beads for each, added dependencies, executed in order. Then audited the codebase with fresh eyes, found 8 more issues, created and executed those too. Plus 2 test issues for real TB-1 runs.

### 2. Wired justfile + populated prompt-bench
- `just tb1 <issue_id> <repo_path>` now calls `run_tb1()` with JSON output
- `~/prompt-bench` has a real Python project: calculator module (add, subtract, multiply, divide, power, modulo) with 5 pytest tests, pyproject.toml with `[dependency-groups] dev`

### 3. Lint pass (13 errors → 0)
Fixed f-string placeholders, ambiguous variable names, line lengths, unused variables, import ordering, aliased errors.

### 4. Git committed (6 commits on main)
```
61f708a Re-score tools with real TB-1 data from 4 pipeline runs
a75cbe9 Fix Gate 0: detect committed changes and install worktree deps correctly
d1663fc Add 85 unit tests across 7 test files
f243c62 Harden TB-1 pipeline: timeouts, error handling, portability
1e368a5 Fix CLI integration: use stdin for prompts, unset CLAUDECODE for nesting
898caad TB-1 code-complete: 6 MCP servers, pipeline orchestrator, full OSS stack
```

### 5. CLI integration fixes (discovered during first e2e runs)
- **CLAUDECODE env var** blocks nested `claude --print` — now unset before spawn
- **`--cwd` and `--message` not valid flags** — switched to stdin pipe for prompts
- **anthropic SDK replaced** with `claude --print` for Gate 4 review — no API key needed
- **`--json-schema`** added for structured Gate 4 review output

### 6. Hardening (8 issues)
- timeout=30 on all `br` subprocess calls (3 files)
- GateSuiteResult guard with try/except in retry and pipeline
- WORKTREE_BASE extracted to shared `paths.py`, configurable via `DEVLOOP_WORKTREE_DIR`
- gitleaks resolution: `shutil.which()` first, `~/.local/bin` fallback, clear error if missing
- Atomic heartbeat metadata writes (tempfile + os.replace)
- Dead code removed (`_find_session_output`)
- VIRTUAL_ENV cleaned from gate subprocess env

### 7. Gate 0 fixes (discovered during real runs)
- Detect committed changes via merge-base diff (not just unstaged/staged)
- `uv sync --dev` installs `[dependency-groups] dev` (pytest) in worktree
- Clean VIRTUAL_ENV from subprocess env to avoid venv conflicts

### 8. Unit tests (85 tests, 7 files)
- test_beads_poller.py (17) — poll, claim, WorkItem properties
- test_deny_list.py (30) — is_path_denied parametrized across all patterns
- test_orchestration.py (13) — persona matching, config loading
- test_gates.py (8) — gitleaks discovery, project type detection
- test_heartbeat.py (5) — stale runs, start/stop heartbeat
- test_paths.py (3) — default path, env var override

### 9. Re-scored tools with real data
Key finding: **Claude Code CLI replaces both DeepEval and dmux** for TB-1.
- dmux downgraded 0.80→0.65 (TUI-only, can't automate)
- gitleaks upgraded 0.86→0.88 (fast, zero false positives)
- Claude Code CLI scored 0.90 (new entry — agent spawn + LLM review)

## Architecture (Current)

```
just tb1 <issue_id> <repo_path>
    → run_tb1() in feedback/pipeline.py
        → Phase 1: poll_ready() — br ready --json
        → Phase 2: claim_issue() — br update --claim
        → Phase 3: setup_worktree() — git worktree add
        → Phase 4: select_persona() + build_claude_md_overlay()
        → Phase 5: init_tracing() — OTel → OpenObserve
        → Phase 6: start_heartbeat() — background thread
        → Phase 7: spawn_agent() — claude --print via stdin
        → Phase 8: run_all_gates() — Gate 0 → Gate 2 → Gate 4
        → Phase 9: gates pass → success
        → Phase 10: gates fail → retry with error context
        → Phase 11: retries exhausted → escalate_to_human()
        → Phase 12: cleanup — stop heartbeat, remove worktree
```

No API key required — uses existing Claude Code auth (Max subscription/OAuth).

## File Map
```
~/dev-loop/
├── CLAUDE.md, README.md, justfile, pyproject.toml, uv.lock
├── config/
│   ├── agents.yaml              # 5 personas
│   ├── capabilities.yaml        # Tool/path scoping
│   ├── dependencies.yaml        # Cross-repo cascade (TB-5)
│   ├── review-gate.yaml         # LLM review criteria
│   ├── scheduling.yaml          # Priority/budget (TB-4)
│   └── projects/prompt-bench.yaml
├── src/devloop/
│   ├── paths.py                 # Shared WORKTREE_BASE constant
│   ├── intake/                  # Layer 1: beads polling + claiming
│   ├── orchestration/           # Layer 2: worktree + persona
│   ├── runtime/                 # Layer 3: claude --print spawn
│   ├── gates/                   # Layer 4: sanity + gitleaks + review
│   ├── observability/           # Layer 5: OTel + heartbeat
│   └── feedback/                # Layer 6: retry + escalate + pipeline
├── tests/                       # 85 unit tests, 7 files
├── docs/                        # 28+ docs, 8 ADRs
├── test-fixtures/tickets/       # 3 mock YAML tickets
└── .beads/                      # 65 issues, all closed
```

## What's Next: TB-2

TB-1 is passing. Per docs/tracer-bullets.md, TB-2 is **Failure-to-Retry**:
- Seed an issue that will intentionally fail gates
- Verify retry loop extracts failure → re-prompts agent → agent fixes it
- Both attempts visible as linked OTel traces
- After max retries, issue correctly moves to "blocked"

Note: Run #4 (factorial) already exercised the retry path successfully (failed Gate 0 on first attempt, passed on retry). TB-2 would formalize this with intentional failures and trace verification.

Other TBs in order: TB-3 (security gate), TB-4 (cost control), TB-5 (cross-repo), TB-6 (session replay).

## Docker
- **OpenObserve**: `docker start dev-loop-openobserve` → :5080
- Login: `admin@dev-loop.local` / `devloop123`
- Must start Docker Desktop on Windows first for WSL2

## Key Gotchas
- `CLAUDECODE` env var must be unset for `claude --print` to work from within Claude Code
- `--cwd` and `--message` are NOT valid claude CLI flags — use stdin pipe + subprocess `cwd=`
- prompt-bench uses `[dependency-groups] dev` (not `[project.optional-dependencies]`) for `uv sync --dev` to install pytest
- Gate 0 checks merge-base diff for committed changes, not just working tree
- VIRTUAL_ENV must be cleared from subprocess env or uv in worktrees picks up the wrong venv
