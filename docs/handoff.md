# dev-loop Handoff — 2026-03-12

## Status: TB-3 CODE COMPLETE

TB-1 and TB-2 are passing. TB-3 is code complete, awaiting e2e run.

### TB-1 (Golden Path) — PASSING
- Bug fix: 94s, all gates passed first try
- Feature add: 245s, failed Gate 0 → succeeded on retry

### TB-2 (Failure-to-Retry) — PASSING
- **Forced mode**: 202s — forced Gate 0 failure → retry with error context → pass
- **Organic mode**: 134s — pre-seeded test trap caught missing edge case → retry → pass
- **Escalation path**: 41s — max_retries=0 + forced fail → issue status verified as "blocked"

### TB-3 (Security-Gate-to-Fix) — CODE COMPLETE
- Gate 3 (bandit SAST) added between Gate 2 (secrets) and Gate 4 (review)
- `run_tb3()` pipeline with vulnerable code seeding + retry + CWE tracking
- bandit detects CWE-89 (SQL injection) in pre-seeded fixture
- 23 new unit tests (121 total)
- Awaiting first e2e run

## What Was Done This Session

### 1. Implemented Gate 3: Security SAST Scan
Added `run_gate_3_security()` to `src/devloop/gates/server.py`:
- Uses bandit for Python SAST scanning
- Parses JSON output into `Finding` objects with CWE classification
- Maps bandit severity (HIGH/MEDIUM) to critical findings
- Relative file paths in findings for cleaner output
- CWE IDs as OTel span attributes for observability
- Gracefully skips if bandit not installed or project is non-Python

### 2. Updated run_all_gates() sequence
Gate order is now: 0 (sanity) → 2 (secrets) → 3 (security) → 4 (review).
Gate 3 is fail-fast like others. Skipped gates don't block the suite.

### 3. Added `cwe` field to Finding model
`src/devloop/gates/types.py` — Finding now has `cwe: str | None = None`

### 4. Added TB-3 types
`src/devloop/feedback/types.py`:
- `SecurityFinding` — CWE, severity, file, line, rule, fixed flag
- `TB3Result` — extends base with security_findings, vulnerability_fixed, cwe_ids, vuln_seeded

### 5. Implemented run_tb3() pipeline
`src/devloop/feedback/pipeline.py`:
- 12-phase structure matching TB-1/TB-2 pattern
- Phase 3.5: `_seed_vulnerable_code()` — copies CWE-89 fixture into worktree
- Seeded mode (default): deterministic via pre-seeded vulnerable file
- Organic mode: relies on agent following ticket instructions
- `_make_forced_security_failure()` — synthetic Gate 3 failure for testing
- `_extract_security_findings()` — extracts CWE/severity from gate results
- OTel span linking, retry history, escalation support
- Security-fix persona (retry_max=3, model=opus)

### 6. Created vulnerable code fixture
`test-fixtures/code/vulnerable_search.py`:
- Two SQL injection vulnerabilities (CWE-89)
- bandit flags both as B608 at lines 24 and 43
- Simulates "user search endpoint with raw SQL" ticket

### 7. Added bandit dependency
`pyproject.toml`: Added `bandit>=1.7` to main dependencies

### 8. Unit tests (23 new, 121 total)
`tests/test_tb3_helpers.py`:
- `TestSeedVulnerableCode` (3 tests)
- `TestMakeForcedSecurityFailure` (4 tests)
- `TestExtractSecurityFindings` (5 tests)
- `TestGate3Security` (6 tests — mocked bandit, skip behaviors)
- `TestTB3Result` (3 tests)
- `TestSecurityFinding` (2 tests)

### 9. Wired justfile
- `just tb3 <issue_id> <repo_path>` — seeded mode
- `just tb3-organic <issue_id> <repo_path>` — organic mode

## Architecture (TB-3 additions)

```
just tb3 <issue_id> <repo_path>
    → run_tb3() in feedback/pipeline.py
        → Phase 1:   poll_ready() — br ready --json
        → Phase 2:   claim_issue() — br update --claim
        → Phase 3:   setup_worktree() — git worktree add
        → Phase 3.5: seed_vulnerable_code() — copy CWE-89 fixture into worktree
        → Phase 4:   select_persona() — security-fix persona (retry_max=3)
        → Phase 5:   init_tracing() — OTel → OpenObserve
        → Phase 6:   start_heartbeat() — background thread
        → Phase 7:   spawn_agent() — claude --print via stdin
        → Phase 8:   run_all_gates() — 0 → 2 → 3 → 4 (Gate 3 catches vuln)
        → Phase 9:   gates pass → success (agent fixed vuln on first try)
        → Phase 10:  gates fail → retry with security finding + CWE in prompt
        → Phase 11:  retries exhausted → escalate to human
        → Phase 12:  cleanup — stop heartbeat, preserve worktree on escalation
        → Flush:     provider.force_flush() for trace verification
```

## File Map (TB-3 additions)
```
src/devloop/gates/
├── server.py            # Gate 0 + Gate 2 + Gate 3 (NEW) + Gate 4 + run_all_gates
└── types.py             # Finding (now with cwe field)

src/devloop/feedback/
├── pipeline.py          # run_tb1() + run_tb2() + run_tb3() (NEW) + TB-3 helpers
├── types.py             # + SecurityFinding, TB3Result (NEW)
└── server.py            # retry_agent(), escalate_to_human() (unchanged)

test-fixtures/
├── code/vulnerable_search.py   # Pre-seeded SQL injection (CWE-89 x2)
├── tickets/tb3-vulnerability.yaml  # "Add user search with raw SQL" ticket
└── tests/test_factorial_trap.py    # TB-2 test trap (unchanged)

tests/
├── test_tb2_helpers.py  # 13 tests for TB-2
└── test_tb3_helpers.py  # 23 tests for TB-3 (NEW)
```

## What's Next: TB-3 E2E Run

To run TB-3 end-to-end:
1. Create a beads issue: `br create --title "Add user search endpoint" --labels security --parent dl-ajr`
2. Run: `just tb3 <issue_id> ~/prompt-bench`
3. Verify: Gate 3 catches CWE-89 → retry → agent fixes → clean scan
4. Check OpenObserve for security spans with CWE attributes

After TB-3 passes: TB-4 (cost control), TB-5 (cross-repo), TB-6 (session replay).

## Key Gotchas
- `br show --format json` returns a JSON array (list), not a dict
- `br create` uses `--labels` (plural), not `--label`; no `--epic` flag, use `--parent`
- Gate 3 skips gracefully if bandit not installed or project is non-Python
- bandit exit code 1 = issues found (not an error), exit code 2 = actual error
- Pre-seeded vulnerable code goes into first `src/<pkg>/` directory with `__init__.py`
- Gate 3 scans `src/` if it exists, otherwise the whole worktree
- `provider.force_flush()` needed after pipeline to ensure spans export
