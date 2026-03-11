# Layer 4: Quality Gates

## Purpose
Every agent output passes through a gauntlet of automated checks before it becomes a PR. Gates run sequentially — fail fast, fail cheap. Each gate produces structured output that the feedback loop can parse and act on.

## In-Process Backpressure (Pre-Gate)

Gates run AFTER the agent finishes. But the cheapest feedback happens DURING agent work. The agent's CLAUDE.md overlay mandates in-process checks:

```
For TypeScript repos:
  After every file edit → tsc --noEmit (type check)
  After all edits → npm test (affected tests only)
  Only commit when local checks pass

For Python repos:
  After every file edit → mypy / pyright (if configured)
  After all edits → pytest (affected tests only)
  Only commit when local checks pass
```

This catches 80% of problems at 10% of the cost. Gates become a safety net, not the primary check.

## Gate Execution Order

```
Agent Output (diff + commits)
       │
       ▼
┌─────────────────┐
│ Gate 0: Sanity   │ ← Does the code compile/parse? Are tests passing?
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ Gate 1: ATDD     │ ← Do acceptance tests pass (if spec exists)?
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ Gate 2: Secrets  │ ← Any leaked credentials in the diff?
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ Gate 3: Security │ ← SAST/SCA/DAST scan (Aikido)
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ Gate 4: Review   │ ← AI code review (CodeRabbit)
└────────┬────────┘
         │ pass
         ▼
┌─────────────────┐
│ Gate 5: Cost     │ ← Did the agent stay within budget?
└────────┬────────┘
         │ pass
         ▼
       PR Created
```

**Why this order:**
- Gate 0 is free and fast — catches garbage before spending money on scans
- Gate 0.5 (relevance) is cheap (one LLM call) — catches off-topic work early
- Gate 1 (ATDD) catches behavioral regressions early
- Gate 2 (secrets) is critical — must run before any code leaves the machine
- Gate 2.5 (dangerous ops) catches migrations, destructive commands
- Gate 3 (security) catches vulns before human reviewers see the PR
- Gate 4 (review) is the most expensive gate — runs last on clean code
- Gate 5 (cost) is a bookkeeping check, not a code check

### Gate 0.5: Task Relevance Check
LLM-as-judge compares the diff against the ticket description. Scores how well the change addresses the stated requirements. Catches agents that did good work on the wrong thing.

### Gate 2.5: Dangerous Operations
Scans the diff for operations that require human approval regardless of quality:
- **Database migrations** with destructive SQL (DROP, DELETE, TRUNCATE, RENAME)
- **Lock file** inconsistency (package.json changed but lock file doesn't match)
- **CI/CD config** changes (.github/workflows, Dockerfile, deploy scripts)
- **Permission/auth** changes (RBAC rules, OAuth config, API key rotation)

If detected: gate pauses and escalates to human. Never auto-passes.

## Gate Details

### Gate 0: Sanity Check
```bash
# Per-language sanity
npm run build          # TypeScript/JS
npm test               # Unit tests
python -m py_compile   # Python
cargo check            # Rust
```
- **Pass**: exit code 0
- **Fail**: structured error with file:line:message

### Gate 1: ATDD (Acceptance Test Driven Development)
Tool: `swingerman/atdd` Claude Code plugin

- Reads Given/When/Then specs from `specs/` directory
- Generates and runs acceptance tests against the agent's changes
- Two test streams: acceptance tests (behavioral) + unit tests (structural)
- **Only runs if spec exists** — no spec = gate skipped with warning

Output format:
```json
{
  "gate": "atdd",
  "status": "fail",
  "specs_run": 3,
  "specs_passed": 2,
  "specs_failed": 1,
  "failures": [
    {
      "spec": "specs/user-auth.feature",
      "scenario": "Given expired token When refresh Then new token issued",
      "error": "Expected 200, got 401",
      "file": "src/auth/refresh.ts",
      "line": 42
    }
  ]
}
```

### Gate 2: Secret Scanner
Tool: Custom hook (built into dev-loop)

Patterns scanned:
- API keys (AWS, GCP, Azure, Anthropic, OpenAI, etc.)
- Private keys (RSA, EC, Ed25519)
- Passwords in config files
- Connection strings with embedded credentials
- JWT tokens
- `.env` files in diff

Implementation: regex patterns + entropy detection on `git diff` output.

```
src/hooks/secret-scanner/
├── patterns.ts    # Known secret patterns (regex)
├── entropy.ts     # High-entropy string detection
├── scanner.ts     # Run patterns + entropy on diff
└── allowlist.ts   # Known false positives (test fixtures, etc.)
```

### Gate 3: Security Scan (Aikido)
Tool: Aikido CLI

Coverage:
- **SAST** — Static analysis for code vulnerabilities (SQL injection, XSS, path traversal, etc.)
- **SCA** — Dependency vulnerability scanning (known CVEs in packages)
- **DAST** — Dynamic analysis (if test server available)
- **IaC** — Infrastructure-as-code scanning (Terraform, Docker, k8s)
- **Container** — Base image vulnerability scanning

Output: structured findings with CWE classification, severity, file:line, and suggested fix.

### Gate 4: Code Review (CodeRabbit)
Tool: CodeRabbit CLI (`cr review`)

What it catches:
- Race conditions
- Memory leaks
- Logic errors
- Missing error handling at system boundaries
- Performance anti-patterns
- Style/convention violations

Configuration:
```yaml
# .coderabbit.yaml
reviews:
  auto_review:
    enabled: true
  path_filters:
    - "!**/*.test.ts"    # don't review test files (covered by ATDD)
    - "!**/generated/**"  # skip generated code
  language_model: claude-sonnet-4-6
```

Output: review comments with severity (critical, warning, suggestion).

- **Critical findings** → gate FAILS
- **Warnings** → gate passes but warnings attached to PR
- **Suggestions** → attached to PR as suggestions, no gate impact

### Gate 5: Cost Check
Tool: Token proxy data

```json
{
  "gate": "cost",
  "status": "pass",
  "budget_usd": 2.00,
  "spent_usd": 0.87,
  "remaining_usd": 1.13,
  "calls": 12,
  "tokens_input": 45000,
  "tokens_output": 8500
}
```

### MCP Server: `quality-gates`

```
src/mcp/quality-gates/
├── server.ts          # MCP server entry
├── runner.ts          # Sequential gate execution with fail-fast
├── gates/
│   ├── sanity.ts      # Gate 0: compile + test
│   ├── atdd.ts        # Gate 1: acceptance tests
│   ├── secrets.ts     # Gate 2: secret scanner
│   ├── security.ts    # Gate 3: Aikido wrapper
│   ├── review.ts      # Gate 4: CodeRabbit wrapper
│   └── cost.ts        # Gate 5: budget check
├── reporter.ts        # Aggregate gate results into structured report
└── types.ts
```

**Tools exposed:**
- `run_all_gates` — sequential execution, fail-fast
- `run_gate` — run a single gate (for debugging)
- `get_gate_results` — retrieve results for a specific run
- `skip_gate` — mark a gate as skipped (escape hatch)

### OTel Instrumentation
Each gate emits its own span:
```
span: quality_gates.gate_2_secrets
attributes:
  gate.name: secrets
  gate.order: 2
  gate.status: pass
  gate.duration_ms: 340
  gate.findings_count: 0
parent: quality_gates.run_all
```

Aggregate span:
```
span: quality_gates.run_all
attributes:
  gates.total: 6
  gates.passed: 5
  gates.failed: 1
  gates.skipped: 0
  gates.first_failure: security
  gates.total_duration_ms: 12400
parent: runtime.output
```

### Gate Configuration Per Project

```yaml
# config/projects/prompt-bench.yaml
quality_gates:
  sanity:
    enabled: true
    commands: ["npm test", "npm run lint"]
  atdd:
    enabled: false  # no specs yet
  secrets:
    enabled: true
    allowlist: ["tests/fixtures/fake-key.pem"]
  security:
    enabled: true
    severity_threshold: medium  # low findings don't block
  review:
    enabled: true
    block_on: critical  # only critical findings block
  cost:
    enabled: true
    ceiling_usd: 2.00
```

### Open Questions
- [ ] CodeRabbit free tier limits? Unlimited CLI reviews announced but need to verify
- [ ] Aikido pricing for open-source/personal use?
- [ ] Should Gate 4 (review) use CodeRabbit or a self-hosted LLM-as-judge?
- [ ] How to handle flaky gates? (gate passes sometimes, fails sometimes on same code)
- [ ] Should gate results be posted as PR comments or stored separately?
