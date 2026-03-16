# Handoff: Phase 6 — Tier 2 Checkpoint

**Date**: 2026-03-15
**Session**: Implementation (Phase 6 of ambient layer plan)
**Previous**: `handoff-2026-03-15-phase5-session-otel.md`

---

## What Was Built

Phase 6 deliverable complete: Tier 2 checkpoint gates that run before every `git commit`, blocking commits that fail Semgrep SAST or gitleaks secret scanning.

### Checkpoint flow

```
PreToolUse hook detects "git commit" in Bash command
  ├─ Tier 2 enabled? (config check)
  ├─ POST /checkpoint { cwd, session_id } to daemon
  │
  Daemon /checkpoint handler:
  ├─ git diff --cached --name-only (staged files)
  ├─ Load merged config (.devloop.yaml checkpoint section)
  ├─ Run gates sequentially, fail-fast:
  │   ├─ sanity: auto-detect test runner or use test_command from config
  │   ├─ semgrep: semgrep --config auto --json --quiet on staged files
  │   ├─ secrets: git diff --cached | gitleaks detect --pipe
  │   ├─ atdd: spec-before-code check (if atdd_required)
  │   └─ review: (skipped, not configured)
  │
  ├─ All pass → { "passed": true, "trailer": "Dev-Loop-Gate: <sha256>" }
  └─ Any fail → { "passed": false, "first_failure": "semgrep", ... }
  │
Hook continues:
  ├─ Passed → exit 0 + additionalContext with trailer for commit message
  └─ Failed → exit 2 + stderr with failure details (BLOCKS the commit)
```

### Gate suite

| Gate | Tool | What It Catches | Fail-open? |
|------|------|----------------|------------|
| **Sanity** | Auto-detect (cargo test / npm test / pytest) or config | Broken code | Yes (skipped if no runner) |
| **Semgrep** | `semgrep --config auto --json` | SQL injection, XSS, secrets, insecure crypto | Yes (if not installed) |
| **Secrets** | `gitleaks detect --pipe` (fed via git diff --cached) | API keys, credentials, private keys | Yes (if not installed) |
| **ATDD** | Spec file check | Code without specs (if `atdd_required: true`) | N/A (config-gated) |
| **Review** | Placeholder | Future: PR-Agent or Claude review | Always passes |

### Git trailer injection

On checkpoint pass, returns `Dev-Loop-Gate: <hash>` where hash is `sha256(gate_results_json)[0..16]`. Claude can append this to the commit message, creating an auditable chain linking every commit to its gate results.

### Config integration

Checkpoint config from `.devloop.yaml`:
```yaml
checkpoint:
  gates: [sanity, semgrep, secrets, atdd, review]  # which gates to run
  skip_gates: [review]                              # per-repo: skip these
  test_command: "npm test"                          # override auto-detect
  atdd_required: true                               # require spec files
```

### New API endpoint

| Method | Path | Purpose | Latency |
|--------|------|---------|---------|
| POST | `/checkpoint` | Run Tier 2 gate suite | ~5-30s |

### Hook-to-daemon timeout

Checkpoint uses a 120s timeout (vs 500ms for Tier 1 checks) since gates shell out to external tools. Semgrep alone takes ~4s on first run.

---

## Performance

| Operation | Latency |
|-----------|---------|
| Checkpoint (semgrep + gitleaks, clean) | ~5s |
| Checkpoint (semgrep only, finding detected) | ~4s (fail-fast) |
| Checkpoint (no staged files) | <1ms |
| Individual gitleaks scan (piped diff) | ~200ms |
| Tier 1 hook (unchanged) | ~6ms |

Binary size: 5.9MB (up from 5.8MB — sha2 + hex add ~70KB).

---

## Tests

82 tests, all passing (up from 66 in Phase 5):

| Category | Count | New |
|----------|-------|-----|
| Deny list (built-in + from_config) | 10 | - |
| Dangerous ops (built-in + from_config) | 11 | - |
| Secrets (built-in + from_config) | 11 | - |
| Config (schema + merge + repo root) | 14 | - |
| Hook | 1 | - |
| Install | 6 | - |
| Session | 6 | - |
| OTel | 5 | - |
| Checkpoint | 16 | +16 |
| **Total** | **82** | **+16** |

New tests cover:
- Trailer determinism and format
- Empty trailer
- Code file detection (source vs config/docs/tests)
- Spec file detection (.spec.md, .spec.yaml, .feature)
- Semgrep JSON parsing (empty, valid findings)
- Gitleaks JSON parsing (empty, valid findings)
- Test command auto-detection (Cargo, npm, none)
- ATDD gate: skipped when not required
- ATDD gate: fails code without spec
- ATDD gate: passes code with spec
- ATDD gate: passes non-code files
- Checkpoint with no staged files (no git repo)

---

## Live Validation

Tested against `/tmp/checkpoint-test` git repo:

1. **Clean file staged** → checkpoint passed, trailer returned: `Dev-Loop-Gate: 8f2a925532453832`
2. **GitHub token in .env staged** → semgrep caught it, commit blocked with error:
   ```
   .env:1 [ERROR] generic.secrets.security.detected-github-token.detected-github-token: GitHub Token detected
   ```
3. **Hook integration** → `dl hook pre-tool-use` correctly detected `git commit` command, contacted daemon, and blocked/allowed based on checkpoint result

---

## Files Created

| File | Purpose |
|------|---------|
| `daemon/src/checkpoint.rs` | Gate runners (semgrep, gitleaks, ATDD, sanity), result types, trailer generation |

## Files Modified

| File | Change |
|------|--------|
| `daemon/Cargo.toml` | Added `sha2 = "0.10"`, `hex = "0.4"` |
| `daemon/src/main.rs` | Added `mod checkpoint;` |
| `daemon/src/server.rs` | Added `POST /checkpoint` route + `handle_checkpoint()` handler |
| `daemon/src/hook.rs` | Added `CheckpointOutcome` enum, `run_checkpoint_via_daemon()` helper, wired commit detection → checkpoint in `pre_tool_use()` |

---

## Source Layout After Phase 6

```
daemon/src/
├── main.rs              # CLI dispatch (14 commands)
├── cli.rs               # Clap: Command + HookCommand + Config
├── daemon.rs            # Start/stop/status/stream (session-aware status)
├── server.rs            # Unix socket HTTP server (session + checkpoint endpoints)
├── sse.rs               # SSE broadcast channel
├── event_log.rs         # JSONL event log writer
├── config.rs            # Full config system: schema, merge, load, dump
├── session.rs           # Session lifecycle: register, deregister, counters
├── otel.rs              # OTLP/HTTP JSON span export
├── checkpoint.rs        # Tier 2: gate suite (semgrep, gitleaks, ATDD, sanity) [NEW]
├── hook.rs              # Hook handlers (session + config + checkpoint-aware)
├── install.rs           # settings.json merger
└── check/
    ├── mod.rs           # CheckEngine: new() + from_config()
    ├── deny_list.rs     # 15 built-in patterns + from_config(extra, remove)
    ├── dangerous_ops.rs # 25 built-in patterns + from_config(extra, allow)
    └── secrets.rs       # 16 built-in patterns + from_config(extra, allowlist)
```

---

## External Tool Versions

| Tool | Version | Installed |
|------|---------|-----------|
| Semgrep | 1.155.0 | `pip install semgrep` |
| Gitleaks | 8.30.0 | Pre-installed at `~/.local/bin/gitleaks` |

### Gitleaks compatibility note

Gitleaks 8.30.0 does NOT have a `--staged` flag (that's in newer versions). Instead, we use `--pipe` mode: `git diff --cached | gitleaks detect --pipe`. This scans the staged diff content rather than the repo files directly.

---

## Not Implemented (Deferred)

1. **PR-Agent / Claude review gate** — "review" gate exists as a passthrough placeholder. Wire when review integration is needed.
2. **Tracer-bullet enforcement** — Config field `workflow: tracer-bullet` exists in schema but enforcement not wired (checks for test+source in diff).
3. **Per-repo Semgrep rules** — Currently uses `--config auto` (community rules). Could add `semgrep_config` field for custom rule paths.
4. **Checkpoint OTel spans** — Checkpoint events are logged to SSE/JSONL but not yet emitted as OTel spans (the `build_check_span()` from Phase 5 could be wired here).
5. **Checkpoint caching** — Could cache recent checkpoint results by staged diff hash to avoid re-running gates if nothing changed.

---

## Next: Phase 7 — Session Continuity

1. `dl hook pre-compact` → auto-handoff YAML
2. `dl hook stop` → 85% context guard
3. Differentiated SessionStart (startup vs resume/compact)
4. Handoff YAML read/write in `continuity.rs`
5. Transcript parsing with flush sentinel
6. Outcome tracking on SessionEnd
