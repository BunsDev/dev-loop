# Handoff: Phase 7 — Session Continuity

**Date**: 2026-03-15
**Session**: Implementation (Phase 7 of ambient layer plan)
**Previous**: `handoff-2026-03-15-phase6-tier2-checkpoint.md`

---

## What Was Built

Phase 7 deliverable complete: Session continuity via handoff YAML files, 85% context guard in Stop hook, differentiated SessionStart, and session-end handoff writing.

### Stop Hook (85% Context Guard)

```
Stop hook fires after every assistant turn
  ├─ Read stdin JSON (session_id, cwd, transcript_path)
  ├─ Fast path: recent handoff exists? → skip (silent exit)
  ├─ Discover transcript (from hook JSON or ~/.claude/projects/)
  ├─ Estimate context from file size (stat call, <1ms)
  │   └─ Heuristic: filesize / 7 ≈ estimated tokens
  ├─ Under 85% of 200K? → silent exit (no output)
  └─ Over 85%:
      ├─ Parse transcript for file ops + token counts
      ├─ Query daemon for session stats (checks/blocks/warns)
      ├─ Write handoff YAML to /tmp/dev-loop/sessions/<session-id>.yaml
      └─ Output additionalContext warning about context usage
```

### PreCompact Hook

Manual CLI command (`dl hook pre-compact`) that always writes a handoff YAML regardless of context level. Can be registered as a hook if Claude Code adds a PreCompact event.

### Differentiated SessionStart

```
SessionStart hook fires
  ├─ Register session with daemon (unchanged from Phase 5)
  ├─ Search /tmp/dev-loop/sessions/ for recent handoff matching cwd
  ├─ Found (resume/compact):
  │   └─ Inject full handoff state via additionalContext
  └─ Not found (fresh start):
      └─ One-liner: "dev-loop ambient active. Last session: N checks, N blocks."
```

### Session End Handoff

SessionEnd now writes a final handoff YAML before deregistering with the daemon. Also cleans up handoff files older than 24 hours.

### Handoff YAML Format

```yaml
session_id: abc-123-def
date: 2026-03-15
source: stop_guard  # or pre_compact, session_end
cwd: /home/user/repo
repo_root: /home/user/repo
outcome: partial     # optional: success | partial | fail
files_modified:
  - src/main.rs
  - src/lib.rs
files_created:
  - src/new.rs
ambient_stats:
  checks: 47
  blocked: 1
  warned: 3
token_estimate:
  input_tokens: 100000
  output_tokens: 50000
  total: 150000
  context_pct: 0.75
```

Target: ~400 tokens per handoff (YAML, not markdown — from CC-v3 research).

---

## Performance

| Operation | Latency |
|-----------|---------|
| Stop hook (fast path — no transcript/under threshold) | ~3ms |
| Stop hook (over threshold — writes handoff) | ~50ms |
| Stop hook (idempotent skip — recent handoff exists) | ~3ms |
| PreCompact (always writes handoff) | ~50ms |
| Session start (with handoff injection) | ~8ms |
| Session start (fresh, no handoff) | ~6ms |
| Tier 1 hook (unchanged) | ~6ms |

Binary size: 6.0MB (up from 5.9MB).

---

## Tests

99 tests, all passing (up from 82 in Phase 6):

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
| Checkpoint | 16 | - |
| Continuity | 6 | +6 |
| Transcript | 10 | +10 |
| **Total** | **99** | **+17** |

New tests cover:
- Handoff YAML write/read roundtrip
- Handoff YAML compactness (<2KB)
- Format for injection includes key info
- Empty handoff serializes (skip_serializing_if)
- Handoff path format
- Find recent handoff matching cwd
- Token estimation from file size
- Context threshold check (under/over)
- Transcript parsing with usage tokens
- Transcript parsing with tool_use file ops
- Empty transcript parsing
- Malformed JSONL line handling
- Flush sentinel detection
- Flush sentinel timeout
- Context percentage calculation
- Transcript discovery for missing session

---

## Live Validation

1. **Stop hook (fast path)**: Silent exit, ~3ms — no transcript found
2. **Stop hook (large transcript)**: Context guard triggered at ~166%, handoff written to `/tmp/dev-loop/sessions/test-stop-large.yaml`
3. **Stop hook (idempotent)**: Silent exit — recent handoff exists
4. **PreCompact**: Handoff written, additionalContext returned
5. **SessionStart (resume)**: Detected previous handoff, injected state
6. **SessionStart (fresh)**: One-liner notification with stats
7. **SessionEnd**: Final handoff written, old handoffs cleaned up
8. **Tier 1 hooks (regression)**: Still ~6ms, unchanged

---

## Files Created

| File | Purpose |
|------|---------|
| `daemon/src/continuity.rs` | Handoff YAML struct, read/write, find_recent, format_for_injection, cleanup |
| `daemon/src/transcript.rs` | Transcript JSONL parser, token estimation, flush sentinel, file discovery |

## Files Modified

| File | Change |
|------|--------|
| `daemon/src/cli.rs` | Added `Stop` and `PreCompact` to HookCommand enum |
| `daemon/src/main.rs` | Added `mod continuity; mod transcript;`, dispatch for Stop/PreCompact |
| `daemon/src/hook.rs` | Added `stop()`, `pre_compact()`, `write_session_handoff()`, `get_session_stats()`, `get_from_daemon()`, refactored `request_daemon()`. Modified `session_start()` for differentiated behavior, `session_end()` for handoff writing + cleanup |
| `daemon/src/install.rs` | Added Stop hook to `dl_hook_entries()`, updated install message |

---

## Source Layout After Phase 7

```
daemon/src/
├── main.rs              # CLI dispatch (16 commands)
├── cli.rs               # Clap: Command + HookCommand (6 hook subcommands)
├── daemon.rs            # Start/stop/status/stream (session-aware status)
├── server.rs            # Unix socket HTTP server (session + checkpoint endpoints)
├── sse.rs               # SSE broadcast channel
├── event_log.rs         # JSONL event log writer
├── config.rs            # Full config system: schema, merge, load, dump
├── session.rs           # Session lifecycle: register, deregister, counters
├── otel.rs              # OTLP/HTTP JSON span export
├── checkpoint.rs        # Tier 2: gate suite (semgrep, gitleaks, ATDD, sanity)
├── continuity.rs        # Handoff YAML read/write, session continuity [NEW]
├── transcript.rs        # Transcript JSONL parser, context estimation [NEW]
├── hook.rs              # Hook handlers (session + config + checkpoint + continuity-aware)
├── install.rs           # settings.json merger (6 event types)
└── check/
    ├── mod.rs           # CheckEngine: new() + from_config()
    ├── deny_list.rs     # 15 built-in patterns + from_config(extra, remove)
    ├── dangerous_ops.rs # 25 built-in patterns + from_config(extra, allow)
    └── secrets.rs       # 16 built-in patterns + from_config(extra, allowlist)
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Stop hook as primary context guard | File size heuristic + transcript parsing | Stop fires every turn. File stat is <1ms. Only parse transcript when over threshold. |
| Handoff idempotency | 5-min skip window | Prevents writing duplicate handoffs on every turn when context is high. |
| Transcript discovery | Hook JSON `transcript_path` → fallback to `~/.claude/projects/` scan | Robust to different Claude Code versions providing or not providing the path. |
| Handoff format | YAML (~400 tokens) | Token-efficient, deterministic parsing (from CC-v3 research). |
| Differentiated SessionStart | Find recent handoff by cwd match | Fresh start = one-liner, resume = full state injection. No dependency on CC `source` field. |
| PreCompact as manual command | Not registered as hook event | Claude Code may not support PreCompact event. Can be registered later if added. |

---

## Not Implemented (Deferred to Phase 8)

1. **Outcome tracking grading prompt** — The plan spec calls for an interactive grade prompt on SessionEnd. This would block the session-end hook. Deferred — outcome can be set via a future `dl outcome <session-id> success|partial|fail` command.
2. **OTel outcome attributes** — Session spans don't yet include outcome. Will add when outcome tracking is wired.
3. **Context limit configurability** — Currently hardcoded at 200K tokens. Could add `continuity.context_limit` to config.
4. **Transcript token counting accuracy** — File size heuristic is rough. Full parsing is more accurate but slower. Could cache parsed results by file modification time.
5. **Handoff goal/now/test fields** — The CC-v3 handoff format includes `goal`, `now`, `test` fields that require understanding the session's intent. Would need LLM analysis of transcript.

---

## Next: Phase 8 — External Integrations + Polish

1. Install Entire CLI for session→commit linking
2. `dl dashboard-validate` (SQL query validation)
3. `dl traces --last N` (terminal span viewer)
4. `dl allow-once` override mechanism
5. CLAUDE.md ambient-rules.md generation
6. Performance benchmarks (criterion)
7. Turmoil stress test: concurrent sessions + races
