# Handoff: Phase 3 — Hook Integration

**Date**: 2026-03-15
**Session**: Implementation (Phase 3 of ambient layer plan)
**Previous**: `handoff-2026-03-15-phase2-check-engine.md`

---

## What Was Built

Phase 3 deliverable complete: `dl install` → open Claude Code session → Write `.env` is blocked by ambient hooks.

### Hook subcommands (`dl hook *`)

```
dl hook pre-tool-use     # PreToolUse: deny list (Write/Edit), dangerous ops (Bash)
dl hook post-tool-use    # PostToolUse: secret detection (Write/Edit)
dl hook session-start    # No-op placeholder (Phase 5+: session registration)
dl hook session-end      # No-op placeholder (Phase 5+: session summary)
```

### Hook protocol (Claude Code ↔ dl)

| Scenario | Exit Code | Output |
|----------|-----------|--------|
| Block (deny list, rm -rf) | 2 | stderr: reason |
| Warn (force push, secrets) | 0 | stdout: `{"hookSpecificOutput":{"permissionDecision":"ask",...}}` |
| Allow | 0 | (silent) |
| Post secret warning | 0 | stdout: `{"hookSpecificOutput":{"additionalContext":"..."}}` |
| Disabled / worktree | 0 | (silent, immediate exit) |

### Safety gates

1. **Enable/disable toggle**: `dl enable` / `dl disable` — writes `~/.config/dev-loop/ambient.yaml`
2. **Worktree detection**: `cwd` starts with `/tmp/dev-loop/worktrees/` → skip all checks
3. **Fail-open**: Parse error on stdin → exit 0 (allow everything)

### Install/uninstall (`dl install` / `dl uninstall`)

- Merges hooks into `~/.claude/settings.json` — PreToolUse (Write|Edit, Bash), PostToolUse (Write|Edit), SessionStart, SessionEnd
- **Preserves existing hooks** (image resize for Read, mcp_maestro screenshot)
- **Idempotent**: running install twice produces same result
- Uninstall removes only entries with `command` starting with `"dl hook"`, preserves everything else
- Empty event arrays cleaned up on uninstall

### Config module (`config.rs`)

```
~/.config/dev-loop/ambient.yaml
```

```yaml
enabled: true
tier1: true
tier2: true
```

- `dl enable` / `dl enable --tier 1` / `dl enable --tier 2`
- `dl disable` (sets `enabled: false`, preserves tier flags)
- No config file = all enabled (secure default)

---

## Performance

| Operation | Latency |
|-----------|---------|
| Hook total (process startup + check) | ~6ms |
| Check engine only | <1ms |
| Disabled/worktree bail | <1ms |

Binary size: 5.7MB (up from 5.2MB — serde_yaml + dirs add ~500KB).

---

## Tests

38 tests, all passing:
- 26 from Phase 2 (deny list, dangerous ops, secrets)
- 5 config tests (default, parse yaml, partial defaults, empty defaults, roundtrip)
- 1 worktree detection test
- 6 install tests (dl hook detection, other hooks ignored, empty install, preserve existing, idempotent, uninstall selective)

---

## Bug Found During Build

**Deadlock from premature install**: Running `dl install` before updating the binary at `~/.local/bin/dl` caused a deadlock — old binary didn't have `hook` subcommand, clap returned exit 2 (= hook block), blocking ALL Write/Edit/Bash tools in Claude Code. **Lesson**: Always update the binary BEFORE installing hooks. The install command should probably check the binary version first (future improvement).

---

## Files Created

| File | Purpose |
|------|---------|
| `daemon/src/hook.rs` | Hook handlers: pre_tool_use, post_tool_use, session_start, session_end |
| `daemon/src/config.rs` | AmbientConfig load/save, enable/disable, is_enabled_tier1/tier2 |
| `daemon/src/install.rs` | Install/uninstall hooks in ~/.claude/settings.json |

## Files Modified

| File | Change |
|------|--------|
| `daemon/Cargo.toml` | Added `serde_yaml = "0.9"`, `dirs = "6"` |
| `daemon/src/cli.rs` | Added `Hook { HookCommand }`, `Install`, `Uninstall`, `Enable`, `Disable` commands |
| `daemon/src/main.rs` | Added `mod config/hook/install`, dispatch for new commands, conditional tracing init |

---

## Hook Registration in settings.json

```json
{
  "PreToolUse": [
    { "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "dl hook pre-tool-use" }] },
    { "matcher": "Bash", "hooks": [{ "type": "command", "command": "dl hook pre-tool-use" }] }
  ],
  "PostToolUse": [
    { "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "dl hook post-tool-use" }] }
  ],
  "SessionStart": [
    { "hooks": [{ "type": "command", "command": "dl hook session-start" }] }
  ],
  "SessionEnd": [
    { "hooks": [{ "type": "command", "command": "dl hook session-end" }] }
  ]
}
```

---

## Source Layout After Phase 3

```
daemon/src/
├── main.rs              # CLI dispatch (13 commands)
├── cli.rs               # Clap: Command + HookCommand enums
├── daemon.rs            # Start/stop/status/stream
├── server.rs            # Unix socket HTTP server (hyper)
├── sse.rs               # SSE broadcast channel
├── event_log.rs         # JSONL event log writer
├── config.rs            # ambient.yaml toggle
├── hook.rs              # Hook handlers (pre/post tool use, session start/end)
├── install.rs           # settings.json merger
└── check/
    ├── mod.rs           # CheckEngine dispatcher
    ├── deny_list.rs     # 15 glob patterns
    ├── dangerous_ops.rs # 25 regex patterns
    └── secrets.rs       # 16 regex patterns
```

---

## Next: Phase 4 — Config System

1. **Global config loading** — `~/.config/dev-loop/ambient.yaml` with full schema (daemon, deny_list, dangerous_ops, secrets, observability, checkpoint sections)
2. **Per-repo config** — `.devloop.yaml` in repo root (extra_patterns, remove_patterns, allow_patterns)
3. **Three-layer merge logic** — built-in defaults → global config → repo config
4. **Config caching in daemon** — keyed by repo root path
5. **Hot-reload via SIGHUP** — `dl config reload`
6. **`dl config`** — dump merged config for debugging
