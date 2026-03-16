# Handoff: Phase 2 — Check Engine

**Date**: 2026-03-15
**Session**: Implementation (Phase 2 of ambient layer plan)
**Previous**: `handoff-2026-03-15-phase1-daemon-skeleton.md`

---

## What Was Built

Phase 2 deliverable complete: `dl check '{"tool_name":"Write","tool_input":{"file_path":".env"}}'` → `block`

### Check engine modules (`daemon/src/check/`)

```
check/
├── mod.rs              # CheckEngine dispatcher + CheckRequest/CheckResult/Action types
├── deny_list.rs        # 15 glob patterns ported from deny_list.py, path suffix matching
├── dangerous_ops.rs    # 25 regex patterns (filesystem, git, DB, process, package, CI/CD)
└── secrets.rs          # 16 regex patterns (API keys, tokens, passwords, private keys, conn strings)
```

### Check routing logic

| Tool | Phase | Check | Example |
|------|-------|-------|---------|
| Write/Edit | Pre | deny_list | `.env` → block |
| Write/Edit | Post | secrets | API key in content → warn |
| Bash | Pre | dangerous_ops + commit detection | `rm -rf` → block, `git push --force` → warn |
| Other | Pre | pass-through | → allow |

### Severity levels

- **Block**: Deny list matches, destructive filesystem ops (`rm -rf`, `sudo rm`), SQL destruction (`DROP TABLE`, `TRUNCATE`)
- **Warn**: Git force push/reset, `DELETE FROM`, `kill -9`, `npm publish`, `curl | sh`, secrets in content
- **Allow**: Everything else

### CLI addition

```bash
dl check '{"tool_name":"Write","tool_input":{"file_path":".env"}}'
# Offline check — no daemon needed. Exit code 1 if blocked.
```

### Server addition

- `POST /check` endpoint added to daemon — runs check, broadcasts event via SSE, logs to JSONL

---

## Performance

All checks under the 5ms Tier 1 target:

| Check | Latency |
|-------|---------|
| Deny list (glob) | 2-3 μs |
| Secrets (regex) | ~27 μs |
| Dangerous ops (regex) | ~150-200 μs (cold start, subsequent faster) |

Binary size: 5.2MB (up from 3.3MB, regex engine adds ~2MB).

---

## Tests

26 tests, all passing:
- 7 deny list (dotenv, crypto, credentials, secrets, cloud dirs, auth files, allow normal)
- 6 dangerous ops (rm -rf, force push, reset --hard, DROP TABLE, DELETE FROM, curl|sh, sudo rm, safe commands, commit detection)
- 10 secrets (API key, GitHub PAT, Anthropic key, private key, DB conn string, password, skip comments, skip examples, normal code, redaction)
- 3 implicit integration tests via `dl check` CLI

---

## Bugs Fixed During Build

1. **Rust 2024 edition raw strings**: `r"...\".."` is invalid in edition 2024. All regex patterns switched to `r#"..."#` syntax.

2. **Comment skip false positives**: `--` prefix matched `-----BEGIN PRIVATE KEY-----`. Fixed: only skip `--` lines that don't start with `-----`.

3. **Example skip false positives**: `example` substring matched `db.example.com` in connection strings. Fixed: `is_placeholder()` function checks for `example` not followed by `.` (hostname pattern).

4. **GitHub PAT test**: Test string had 34 chars after `ghp_` instead of 36. Fixed test data.

---

## Ported from Python

| Python source | Rust target | What was ported |
|---------------|-------------|-----------------|
| `src/devloop/runtime/deny_list.py` | `check/deny_list.rs` | 15 DENIED_PATTERNS, `is_path_denied()` with full path + basename + path suffix matching |
| `src/devloop/gates/server.py` (Gate 2.5) | `check/dangerous_ops.rs` | `_DANGEROUS_SQL_PATTERNS` + expanded to cover filesystem, git, process, package, CI/CD ops |
| (new) | `check/secrets.rs` | In-process regex scanner for API keys, tokens, passwords, private keys, connection strings |

---

## Files Modified

| File | Change |
|------|--------|
| `daemon/Cargo.toml` | Added `regex = "1"`, `glob = "0.3"` |
| `daemon/src/main.rs` | Added `mod check`, `Command::Check` dispatch with `run_check()` |
| `daemon/src/cli.rs` | Added `Check { json: String }` subcommand |
| `daemon/src/server.rs` | Added `CheckEngine` to `ServerState`, `POST /check` handler |
| `daemon/src/daemon.rs` | Init `CheckEngine::new()` in daemon startup |

## Files Created

| File | Purpose |
|------|---------|
| `daemon/src/check/mod.rs` | `CheckEngine`, `CheckRequest`, `CheckResult`, `Action`, `CheckPhase` |
| `daemon/src/check/deny_list.rs` | `DenyList` with 15 pre-compiled glob patterns |
| `daemon/src/check/dangerous_ops.rs` | `DangerousOps` with 25 pre-compiled regex patterns + `is_git_commit()` |
| `daemon/src/check/secrets.rs` | `SecretScanner` with 16 pre-compiled regex patterns + false-positive filtering |

---

## Commit detection

`DangerousOps::is_git_commit(command)` returns true for `git commit`, `git commit -m`, `git commit --amend`, etc. The `CheckResult.is_commit` field signals to Phase 3 hooks that Tier 2 checkpoint should be triggered.

---

## Next: Phase 3 — Hook Integration

1. **`dl hook pre-tool-use`** / **`dl hook post-tool-use`** subcommands — read Claude Code hook stdin JSON, connect to daemon `/check`, return exit code + stdout JSON
2. **`dl hook session-start`** / **`dl hook session-end`** — session lifecycle
3. **`dl install`** / **`dl uninstall`** — merge/remove hooks in `~/.claude/settings.json` (preserve existing hooks like image resize)
4. **Enable/disable toggle** — `~/.config/dev-loop/ambient.yaml` with `enabled`, `tier1`, `tier2` flags
5. **Worktree detection** — skip checks if `cwd` starts with `/tmp/dev-loop/worktrees/`

Reference: `~/.claude/settings.json` already has image resize hooks that must be preserved during install/uninstall.
