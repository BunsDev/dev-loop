# dev-loop Handoff — 2026-03-12

## Status: TB-2 PASSING

TB-1 and TB-2 are both fully operational.

### TB-1 (Golden Path) — PASSING
- Bug fix: 94s, all gates passed first try
- Feature add: 245s, failed Gate 0 → succeeded on retry

### TB-2 (Failure-to-Retry) — PASSING
- **Forced mode**: 202s — forced Gate 0 failure → retry with error context → pass
- **Organic mode**: 134s — pre-seeded test trap caught missing edge case → retry → pass
- **Escalation path**: 41s — max_retries=0 + forced fail → issue status verified as "blocked"

## What Was Done This Session

### 1. Updated docs/tracer-bullets.md
Replaced all dmux and DeepEval references with actual TB-1 implementation (Claude Code CLI, `git worktree add`). Added TB-1 and TB-2 passing status sections.

### 2. Implemented TB-2: Failure-to-Retry
Full vertical slice through all 6 layers:

- **Types** (`feedback/types.py`): Added `TB2Result` with trace_id, attempt_span_ids, blocked_verified, force_gate_fail_used, retry_history fields. Added `RetryAttempt` model.
- **Pipeline** (`feedback/pipeline.py`): Added `run_tb2()` with:
  - Pre-seeded test fixture injection (Phase 3.5)
  - Force-gate-fail mode for deterministic retry testing
  - OTel span linking between retry attempts (`opentelemetry.trace.Link`)
  - Blocked status verification after escalation
  - OTel force-flush after pipeline completion
  - Worktree preservation on escalation for post-mortem
- **Test fixtures**: Updated `test-fixtures/tickets/tb2-failure.yaml` (factorial issue), created `test-fixtures/tests/test_factorial_trap.py` (edge case trap: float input, negative input, exact message matching)
- **Justfile**: Wired `just tb2` and `just tb2-force` commands

### 3. Fixed `_verify_blocked_status()` parser
`br show --format json` returns a JSON array, not object. Added list unwrapping.

### 4. Added pytest testpaths config
`test-fixtures/tests/` was being collected by pytest. Added `[tool.pytest.ini_options] testpaths = ["tests"]` to pyproject.toml.

### 5. Unit tests (13 new, 98 total)
- `test_tb2_helpers.py` — forced failure, fixture seeding, blocked verification, TB2Result model

### 6. Created 5 beads for TB-2 (all closed)
- dl-jd4.6 through dl-jd4.10 under TB-2 epic

## Architecture (Current)

```
just tb2 <issue_id> <repo_path>
    → run_tb2() in feedback/pipeline.py
        → Phase 1:   poll_ready() — br ready --json
        → Phase 2:   claim_issue() — br update --claim
        → Phase 3:   setup_worktree() — git worktree add
        → Phase 3.5: seed_test_fixture() — copy trap test into worktree
        → Phase 4:   select_persona() + build_claude_md_overlay()
        → Phase 5:   init_tracing() — OTel → OpenObserve
        → Phase 6:   start_heartbeat() — background thread
        → Phase 7:   spawn_agent() — claude --print via stdin
        → Phase 8:   run_all_gates() or _make_forced_failure()
        → Phase 9:   gates pass → success (note: retry path not exercised)
        → Phase 10:  gates fail → retry with span links (Link to previous)
        → Phase 11:  retries exhausted → escalate + verify_blocked_status()
        → Phase 12:  cleanup — stop heartbeat, preserve worktree on escalation
        → Flush:     provider.force_flush() for trace verification
```

## File Map (TB-2 additions)
```
src/devloop/feedback/
├── pipeline.py          # run_tb1() + run_tb2() + TB-2 helpers
├── types.py             # TB1Result, TB2Result, RetryAttempt
└── server.py            # retry_agent(), escalate_to_human() (unchanged)

test-fixtures/
├── tickets/tb2-failure.yaml     # Factorial issue with edge cases
└── tests/test_factorial_trap.py # Pre-seeded test trap (float, negative, message match)

tests/
└── test_tb2_helpers.py  # 13 tests for TB-2 helpers
```

## What's Next: TB-3

TB-2 is passing. Per docs/tracer-bullets.md, TB-3 is **Security-Gate-to-Fix**:
- Seed issue that produces code with a known vulnerability
- VibeForge Scanner catches it (or equivalent security scanner)
- Agent self-remediates based on structured finding
- Security finding appears in OpenObserve with CWE classification

Other TBs in order: TB-4 (cost control), TB-5 (cross-repo), TB-6 (session replay).

## Key Gotchas
- `br show --format json` returns a JSON array (list), not a dict
- `br create` uses `--labels` (plural), not `--label`; no `--epic` flag, use `--parent`
- Pre-seeded test trap is the key to organic TB-2 failures — the `float(5.0)` TypeError check is what agents miss most often
- `provider.force_flush()` needed after pipeline to ensure spans export before verification
- Worktree preserved on escalation (`keep_worktree_on_failure` logic)
