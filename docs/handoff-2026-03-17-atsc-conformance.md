# Handoff: ATSC Conformance + Research-Driven Hardening

**Date**: 2026-03-17
**Session**: ATSC spec alignment + Agentix Labs research integration
**Status**: All 8 steps implemented, 287 tests passing, release build clean

---

## What Was Done

Implemented 8 additive, non-breaking improvements to the dev-loop ambient layer daemon, driven by ATSC spec (Agent Telemetry Semantic Conventions v0.1.0) and 10 Agentix Labs blog posts.

### Step 1: Failure Taxonomy (check/mod.rs + hook.rs)
- `CheckResult` now carries `category` (`file_protection`/`command_safety`/`secret_detection`) and `pattern` fields
- `fire_event_to_daemon()` extended with category, pattern, and tool_key params
- tool_key computed before moving tool_input into CheckRequest

### Step 2: ATSC Conformance (otel.rs + server.rs)
- Session root spans emit 12 ATSC Core fields (`atsc.spec_version`, `atsc.span_kind`, `run.id`, etc.) + Session Object (`session.kind`, `session.state`, `session.participant.channel`)
- Check spans emit guardrail.* attributes (`guardrail.name`, `guardrail.action`, `guardrail.triggered`, `guardrail.categories`, `guardrail.policy`)
- `uuid_v4()` helper using getrandom
- `build_handoff_span()` for session continuity events
- Check spans accumulated per-session in `DashMap` and exported alongside session spans at session end
- Cross-trace links (`links` array on root span) when resuming from a previous session handoff
- Token estimate and ambient_mode now included in session spans

### Step 3: Config-Versioned Baselines (config.rs + session.rs)
- `MergedConfig::config_hash()` — SHA-256 of all check engine pattern lists, truncated to 16 hex chars
- Stored in `SessionInfo`, exposed in `/status` response and OTel spans (`x.devloop.config_hash`)
- Same config = same hash, different patterns = different hash

### Step 4: Loop/Retry Detection (check/loop_detect.rs + server.rs)
- New `check/loop_detect.rs` module with `check_loop()` function
- `LoopDetectionConfig` in config.rs (enabled: true, window_secs: 120, threshold: 5)
- Tool call history tracked per-session via `DashMap<String, Vec<(String, Instant)>>`
- Emits `loop_warning` SSE events when same tool_key fires 5+ times in 120s window
- History cleaned up on session end

### Step 5: Handoff Cross-Trace Links (continuity.rs + hook.rs + server.rs)
- `trace_id` and `root_span_id` added to `Handoff` struct (YAML-serialized)
- `get_session_stats()` now returns trace IDs from daemon `/status` response
- `write_session_handoff()` sets trace_id/root_span_id from daemon
- `handle_session_start()` reads recent handoff and sets `previous_trace_id/span_id` on new session
- OTel root span includes `links` array pointing to previous trace

### Step 6: Runtime Kill Switch (cli.rs + server.rs + daemon.rs)
- `dl kill <gate>` — temporarily disables a checkpoint gate (validated against KNOWN_GATES)
- `dl unkill [gate]` — re-enables specific gate or all gates
- `/kill` and `/unkill` POST endpoints on daemon
- `handle_checkpoint()` filters killed gates before running
- `dl status` shows killed_gates list
- `post_to_endpoint()` helper added to daemon.rs (pub)

### Step 7: Alert Rules (config/alerts/rules.yaml)
- `session_burn_rate` — fires when token consumption exceeds 2x 7-day rolling average
- `guardrail_trigger_rate_spike` — fires when block+warn rate exceeds 3x hourly baseline

### Step 8: Prompt Injection Test Cases (tests/tier2/corpus/)
- `prompt_injection_ignore/` — comment injection ("ignore all instructions")
- `prompt_injection_disable_gates/` — HTML comment gate disable attempt
- `prompt_injection_exfil/` — data exfiltration pattern (semgrep target)

---

## Files Changed

| File | Lines | Action |
|------|-------|--------|
| `daemon/src/check/mod.rs` | +104 | category + pattern on CheckResult, 5 new tests |
| `daemon/src/check/loop_detect.rs` | NEW | check_loop(), 4 tests |
| `daemon/src/hook.rs` | +74/-10 | Extended fire_event_to_daemon, tool_key, trace IDs in handoff |
| `daemon/src/config.rs` | +125 | MergedConfig::config_hash(), LoopDetectionConfig, 5 new tests |
| `daemon/src/session.rs` | +16 | config_hash, previous_trace_id/span_id in SessionInfo |
| `daemon/src/otel.rs` | +186 | uuid_v4(), ATSC attrs, build_handoff_span(), cross-trace links, 3 new tests |
| `daemon/src/server.rs` | +256 | check_spans + tool_call_history + killed_gates, /kill /unkill, loop detection |
| `daemon/src/daemon.rs` | +34 | Initialize new state, pub post_to_endpoint() |
| `daemon/src/continuity.rs` | +13 | trace_id/root_span_id on Handoff |
| `daemon/src/cli.rs` | +10 | Kill/Unkill commands |
| `daemon/src/main.rs` | +23 | Kill/Unkill dispatch |
| `config/alerts/rules.yaml` | +37 | burn_rate + guardrail_spike alerts |
| `tests/tier2/corpus/prompt_injection_*/` | NEW | 3 adversarial scenarios |

**Total**: 841 insertions, 37 deletions across 11 modified + 4 new files

---

## Test Results

- **287 tests passing** (93 lib + 190 bin + 4 turmoil integration)
- **20 new tests** added (was 267)
- Release build clean (3 pre-existing warnings only)

---

## Not Committed

All changes are unstaged. Run `git add` + `git commit` when ready.

---

## What's NOT Done (deferred)

- **Feedback-to-corpus promotion** — `promote_to_corpus.py` for `dl feedback missed` → planted-defect scenarios
- **Differential retention** — archive failed sessions before JSONL rotation
- **Near-miss impact estimates** — heuristic damage-prevented annotations
- **Prompt injection in reasoning** — detecting malicious instructions in agent reasoning output

---

## Verification Checklist

- `cargo test` — 287 pass
- `cargo build --release` — clean
- `dl status` — shows config_hash and killed_gates per session
- `dl check '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}'` — result includes `category: "command_safety"`, `pattern` field
- `dl kill sanity && dl checkpoint` — sanity gate skipped
- `dl unkill && dl checkpoint` — all gates restored
- `dl stream` — shows `loop_warning` events when same tool_key fires 5+ times in 120s
- OTel spans include `atsc.spec_version`, `guardrail.*`, `x.devloop.*`
- Handoff YAML contains trace_id; resumed sessions get cross-trace links
