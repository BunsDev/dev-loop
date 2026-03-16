# Handoff: Phase 4 — Config System

**Date**: 2026-03-15
**Session**: Implementation (Phase 4 of ambient layer plan)
**Previous**: `handoff-2026-03-15-phase3-hook-integration.md`

---

## What Was Built

Phase 4 deliverable complete: three-layer config merge (built-in → global → per-repo) wired into hooks and check engine.

### Full config schema

Global config at `~/.config/dev-loop/ambient.yaml` now supports:

```yaml
enabled: true
tier1: true
tier2: true
daemon: { socket, pid_file, auto_stop_minutes, log_level }
deny_list: { extra_patterns, remove_patterns }
dangerous_ops: { extra_patterns, allow_patterns }
secrets: { extra_patterns, file_allowlist }
observability: { openobserve_url, openobserve_org, ... }
checkpoint: { gates, skip_review, atdd_required, test_command }
```

### Per-repo config (`.devloop.yaml`)

Placed at repo root (found by walking up from cwd to find `.devloop.yaml` or `.git`):

```yaml
ambient: true
deny_list: { extra_patterns, remove_patterns }
dangerous_ops: { allow_patterns }
secrets: { file_allowlist }
checkpoint: { skip_gates, test_command, atdd_required }
workflow: tracer-bullet
spec_required: true
```

### Merge rules

| Field type | Merge behavior |
|------------|---------------|
| `extra_patterns` | Appended (global + repo) |
| `remove_patterns` | Subtracted from built-in defaults |
| `allow_patterns` | Appended (global + repo) |
| `file_allowlist` | Appended (global + repo) |
| `skip_gates` | Subtracted from active gates list |
| Scalars (bools, strings) | Later layer wins |
| `enabled` | `global.enabled AND repo.ambient` |

### `dl config` command

```
dl config              # dump merged config for cwd
dl config --dir /path  # dump merged config for specified directory
```

Shows header with repo root and config file paths, then YAML of merged result.

### Config-aware check engine

`CheckEngine::from_config(&MergedConfig)` builds deny list, dangerous ops, and secret scanner with all overrides applied. Hooks now use this instead of `CheckEngine::new()`.

### Real-world fix: `*secret*` false positive

The `*secret*` deny pattern blocked writes to `daemon/src/check/secrets.rs`. Fixed by adding `remove_patterns: ["*secret*"]` to dev-loop's `.devloop.yaml`. This is exactly the use case the config system was built for.

---

## Performance

| Operation | Latency |
|-----------|---------|
| Hook with config merge (process startup + load + merge + check) | ~6ms |
| Config load (global + repo) | <1ms |

Binary size: 5.6MB (slightly smaller than Phase 3 due to release optimizations).

---

## Tests

55 tests, all passing (up from 38 in Phase 3):

| Category | Count | New |
|----------|-------|-----|
| Deny list (built-in + from_config) | 10 | +3 |
| Dangerous ops (built-in + from_config) | 11 | +2 |
| Secrets (built-in + from_config) | 11 | +2 |
| Config (schema + merge + repo root) | 14 | +9 |
| Hook | 1 | - |
| Install | 6 | - |
| **Total** | **55** | **+17** |

New tests cover:
- Full global config parsing (all sections)
- Repo config parsing
- Merge: global only, global + repo, repo disables ambient
- `find_repo_root` with `.devloop.yaml`, `.git`, and none
- `load_repo_config` from filesystem
- Backward compat (Phase 3 simple YAML still parses)
- DenyList `from_config` (extra, remove, both)
- DangerousOps `allow_patterns` bypass + `extra_patterns`
- SecretScanner `file_allowlist` + `extra_patterns`

---

## Files Created

| File | Purpose |
|------|---------|
| `/home/musicofhel/dev-loop/.devloop.yaml` | Per-repo config for dev-loop itself |

## Files Modified

| File | Change |
|------|--------|
| `daemon/src/config.rs` | Complete rewrite: full schema (AmbientConfig, RepoConfig, MergedConfig), three-layer merge, `find_repo_root`, `load_repo_config`, `load_merged`, `dump_config`, 14 tests |
| `daemon/src/check/mod.rs` | Added `CheckEngine::from_config(&MergedConfig)` constructor |
| `daemon/src/check/deny_list.rs` | Extracted `BUILTIN_DENY_PATTERNS` const, added `DenyList::from_config(extra, remove)`, 3 tests |
| `daemon/src/check/dangerous_ops.rs` | Added `allow_patterns` field, `DangerousOps::from_config(extra, allow)`, allow bypass in `check()`, 2 tests |
| `daemon/src/check/secrets.rs` | Added `file_allowlist` field, `SecretScanner::from_config(extra, allowlist)`, `is_file_allowed()`, 2 tests |
| `daemon/src/hook.rs` | Rewired to use `load_merged(cwd)` + `CheckEngine::from_config()`, added file allowlist check in `post_tool_use` |
| `daemon/src/cli.rs` | Added `Config { dir: Option<String> }` command |
| `daemon/src/main.rs` | Dispatch for `Config` command |
| `~/.config/dev-loop/ambient.yaml` | Populated with plan's recommended global allow_patterns |

---

## Config Files Deployed

### Global (`~/.config/dev-loop/ambient.yaml`)

Pre-populated with common safe `dangerous_ops.allow_patterns`:
- `rm -rf node_modules`, `rm -rf dist`, `rm -rf build`, `rm -rf .next`
- `rm -rf __pycache__`, `rm -rf .pytest_cache`, `rm -rf .ruff_cache`

### Per-repo (`~/dev-loop/.devloop.yaml`)

- `deny_list.remove_patterns: ["*secret*"]` — prevents false positive on `secrets.rs`
- `dangerous_ops.allow_patterns: ["rm -rf target"]` — allows cargo clean
- `secrets.file_allowlist: ["daemon/src/check/secrets.rs"]` — skip scanning test patterns in source

---

## Source Layout After Phase 4

```
daemon/src/
├── main.rs              # CLI dispatch (14 commands)
├── cli.rs               # Clap: Command + HookCommand + Config
├── daemon.rs            # Start/stop/status/stream
├── server.rs            # Unix socket HTTP server (hyper)
├── sse.rs               # SSE broadcast channel
├── event_log.rs         # JSONL event log writer
├── config.rs            # Full config system: schema, merge, load, dump
├── hook.rs              # Hook handlers (config-aware)
├── install.rs           # settings.json merger
└── check/
    ├── mod.rs           # CheckEngine: new() + from_config()
    ├── deny_list.rs     # 15 built-in patterns + from_config(extra, remove)
    ├── dangerous_ops.rs # 25 built-in patterns + from_config(extra, allow)
    └── secrets.rs       # 16 built-in patterns + from_config(extra, allowlist)
```

---

## Not Implemented (Deferred)

1. **Config caching in daemon** — hooks are separate processes (always load fresh). Daemon server doesn't use config yet. Cache will matter in Phase 5+ when daemon actively runs checks.
2. **Hot-reload via SIGHUP** — `dl config reload` deferred for same reason. Hooks already reload on every invocation.
3. **`dl enable/disable` with full schema save** — currently `enable/disable` writes all fields via `save()`. The full config might get over-written if the user hand-edited it. Consider using a merge-on-save approach if this becomes an issue.

---

## Next: Phase 5 — Session Registration & OTel

1. Session start hook registers with daemon → gets session ID
2. Session end hook flushes traces + summary
3. OTel span emission from hooks
4. Daemon tracks active sessions
