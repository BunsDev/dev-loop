# Handoff: Phase 1 — Daemon Skeleton

**Date**: 2026-03-15
**Session**: Implementation (Phase 1 of ambient layer plan)
**Previous**: `handoff-2026-03-15-ambient-layer-research.md` (plan + research)

---

## What Was Built

Phase 1 deliverable complete: `dl start` → `dl stream` shows live events.

### Rust daemon (`~/dev-loop/daemon/`)

```
daemon/
├── Cargo.toml          # tokio, hyper, clap, chrono, serde, tracing
├── Cargo.lock
└── src/
    ├── main.rs          # CLI entrypoint (clap dispatch + tracing init)
    ├── cli.rs           # Subcommands: start, stop, status, stream
    ├── daemon.rs        # Background fork (_DL_DAEMON env), PID file, SIGTERM/SIGINT, stream client
    ├── server.rs        # Unix socket HTTP server (hyper): /status, /inbox (SSE), /event (POST)
    ├── sse.rs           # Event type + broadcast channel (tokio::broadcast, 100 buffer)
    └── event_log.rs     # Append-only JSONL writer (tokio::mpsc, bounded 1000, try_send backpressure)
```

### Binary installed

- `~/.local/bin/dl` — 3.3MB release binary
- Status check: <1ms
- Runtime files: `/tmp/dev-loop/dl.sock`, `/tmp/dev-loop/dl.pid`, `/tmp/dev-loop/events.jsonl`

### Justfile additions

- `dl-build`, `dl-install`, `dl-test`, `dl-start`, `dl-stop`, `dl-status`

---

## Design Choices Made

| Choice | Rationale |
|--------|-----------|
| Background fork via `_DL_DAEMON` env re-exec | Simpler than daemonize crate; stdio null in child |
| SSE long-poll (30s timeout) | Avoids streaming body complexity; `dl stream` reconnects automatically |
| `#[serde(flatten)]` for Event data | Keeps JSONL output flat without wrapper objects |
| `/event` POST endpoint | Allows external tools to inject events; used for testing now, hooks later |
| SIGTERM + SIGINT handlers | Both clean up PID + socket files |

---

## Bug Fixed During Build

- **Duplicate `type` key in JSONL**: `#[serde(flatten)]` merged incoming JSON's `type` field alongside the struct's `event_type` field. Fixed by stripping `type` from flattened data in `with_data()`.

---

## Verified Working

```bash
dl start          # Forks to background, prints PID
dl status         # Shows running/PID/uptime/socket
POST /event       # Events appear in JSONL log + SSE broadcast
dl stop           # Sends SIGTERM, cleans up files
dl status         # Shows stopped
```

Event log survives daemon restarts (append-only).

---

## Next: Phase 2 — Check Engine

Port from Python to Rust:

1. **Deny list** (`deny_list.py` → `check/deny_list.rs`): 15 glob patterns, match full path + basename + path suffixes
2. **Dangerous ops** (`gates/server.py` Gate 2.5 patterns): regex for `rm -rf`, `DROP TABLE`, `force push`, CI/CD changes, auth file modifications
3. **Secret patterns** (new): regex for API keys, tokens, passwords in file content
4. **`/check` endpoint**: accepts tool_name + tool_input, runs appropriate checks, returns allow/block/warn
5. **Turmoil tests**: concurrent session handling

Reference files for porting:
- `src/devloop/runtime/deny_list.py` — 15 DENIED_PATTERNS, `is_path_denied()` with path suffix matching
- `src/devloop/gates/server.py` — `_DANGEROUS_SQL_PATTERNS`, Gate 2.5 dangerous ops

---

## What's NOT Done

- No `dl hook` subcommands yet (Phase 3)
- No `dl install`/`dl uninstall` (Phase 3)
- No enable/disable toggle (Phase 3)
- No config system (Phase 4)
- No OTel spans (Phase 5)
- No Tier 2 checkpoint (Phase 6)
- `/inbox` SSE is long-poll, not true streaming — adequate for now
