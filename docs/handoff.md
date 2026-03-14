# dev-loop Handoff — 2026-03-13

## Status: TB-5 CODE COMPLETE

TB-1 through TB-6 all implemented. 237 unit tests passing.

### TB-1 (Golden Path) — PASSING
- Bug fix: 94s, all gates passed first try
- Feature add: 245s, failed Gate 0 → succeeded on retry

### TB-2 (Failure-to-Retry) — PASSING
- **Forced mode**: 202s — forced Gate 0 failure → retry with error context → pass
- **Organic mode**: 134s — pre-seeded test trap caught missing edge case → retry → pass
- **Escalation path**: 41s — max_retries=0 + forced fail → issue status verified as "blocked"

### TB-3 (Security-Gate-to-Fix) — PASSING
- **Seeded mode**: 55s — pre-seeded CWE-89 → Gate 3 caught it → agent fixed → clean scan
- Pre-flight gate scan: Gate 3 detected 2 SQL injection findings (B608 CWE-89)
- Agent used parameterized queries on retry, vulnerability_fixed=true

### TB-4 (Runaway-to-Stop) — CODE COMPLETE
- Turn-based control via `--max-turns N` + `--output-format json`
- Per-persona turn budgets in agents.yaml (10-25 turns)
- Usage tracking: num_turns, input_tokens, output_tokens per attempt
- Turn budget decrements across retries (remaining = max - used)
- Escalation comment includes per-attempt usage breakdown table
- `just tb4 <issue_id> <repo_path>` / `just tb4-turns <issue_id> <repo_path> 5`

#### TB-4 Files Changed

| File | What Changed |
|------|-------------|
| `runtime/types.py` | `AgentConfig.max_turns`, `AgentResult.{num_turns, input_tokens, output_tokens}` |
| `runtime/server.py` | `_parse_usage_from_output()`, `--output-format json` + `--max-turns` in `_build_command`, usage on OTel spans |
| `orchestration/types.py` | `PersonaConfig.max_turns_default: int = 15` |
| `orchestration/server.py` | `select_persona()` extracts `max_turns_default` from agents.yaml |
| `config/agents.yaml` | `max_turns_default` per persona (bug-fix:10, feature:25, refactor:20, security-fix:15, docs:10) |
| `feedback/types.py` | `TB4Result`, `UsageBreakdown` |
| `feedback/pipeline.py` | `run_tb4()` — full pipeline with turn budget, 12 phases |
| `feedback/server.py` | `retry_agent()` accepts + passes `max_turns`, returns usage stats; `escalate_to_human()` renders usage table |
| `justfile` | `tb4`, `tb4-turns` commands |
| `tests/test_tb4.py` | 12 tests: types, config, escalation table |
| `tests/test_runtime.py` | 15 tests: `_parse_usage_from_output`, `_build_command`, usage wiring |
| `tests/test_orchestration.py` | 5 tests: `select_persona` returns correct `max_turns_default` per persona |

## Architecture (TB-4 flow)

```
just tb4 <issue_id> <repo_path>
    → run_tb4() in feedback/pipeline.py
        → Phase 1:   poll_ready() — br ready --json
        → Phase 2:   claim_issue() — br update --claim
        → Phase 3:   setup_worktree() — git worktree add
        → Phase 4:   select_persona() — get max_turns_default from persona
        → Phase 5:   init_tracing() — OTel → OpenObserve
        → Phase 6:   start_heartbeat() — background thread
        → Phase 7:   spawn_agent(max_turns=remaining) — agent runs with turn cap
        → Phase 8:   remaining > 0? → run_all_gates()
        → Phase 9:   gates pass → success with usage stats
        → Phase 10:  gates fail → retry with remaining turn budget
        → Phase 11:  turns exhausted or retries exhausted → escalate with usage table
        → Phase 12:  cleanup — stop heartbeat, flush OTel
```

### TB-5 (Cross-Repo Cascade) — CODE COMPLETE
- Changes in source repo matched against `config/dependencies.yaml` watch patterns
- Cascade issue created in beads with `--parent <source_id>` + `cascade,repo:<target>` labels
- Delegates to `run_tb1()` for target repo work — no duplicate logic
- Outcome reported back to source issue via `br comments add`
- "No match" is a success (`cascade_skipped=True`), not a failure
- OTel context propagation: TB-1 spans are children of `tb5.phase.cascade_tb1`
- `just tb5 <source_issue_id> <source_repo_path> <target_repo_path>`

#### TB-5 Files Changed

| File | What Changed |
|------|-------------|
| `feedback/types.py` | `TB5Result` — target_repo_path, target_issue_id, changed_files, matched_watches, dependency_type, cascade_skipped, tb1_result, source_comment_added |
| `feedback/pipeline.py` | 6 helpers (`_load_dependency_map`, `_get_changed_files`, `_match_watches`, `_get_source_issue_details`, `_create_cascade_issue`, `_report_cascade_outcome`) + `run_tb5()` — 8-phase pipeline |
| `justfile` | `tb5` command with 3 args (source_issue, source_repo, target_repo) |
| `tests/test_tb5.py` | 31 tests: types, dependency loading, git diff, glob matching, issue creation, outcome reporting, list response handling |
| `docs/tracer-bullets.md` | TB-5 section updated with actual design |
| `config/dependencies.yaml` | Already existed — prompt-bench→backend, backend→mobile |

## Architecture (TB-5 flow)

```
just tb5 <source_issue_id> <source_repo_path> <target_repo_path>
    → run_tb5() in feedback/pipeline.py
        → Phase 1:   _get_source_issue_details() — br show --format json
        → Phase 2:   _get_changed_files() — git diff main..dl/<id> --name-only
        → Phase 3:   _load_dependency_map() + _match_watches() — fnmatch globs
        → [early return if cascade_skipped]
        → Phase 4:   init_tracing() — OTel → OpenObserve
        → Phase 5:   _create_cascade_issue() — br create --parent --silent
        → Phase 6:   run_tb1(target_issue_id, target_repo_path) — full TB-1
        → Phase 7:   _report_cascade_outcome() — br comments add
        → Phase 8:   cleanup — flush OTel
```

### TB-6 (Session Replay Debug) — CODE COMPLETE
- Agent NDJSON stdout saved to `/tmp/dev-loop/sessions/<session_id>.ndjson`
- Session metadata (issue_id, trace_id, exit_code, gate_failure, suggested_fix) in `.meta.json`
- `_parse_session_events()` parses ALL NDJSON lines (not just `type: result`)
- `_format_session_timeline()` renders human-readable timeline with event types
- `_suggest_claude_md_fix()` — rule-based: gate name → CLAUDE.md suggestion
- `just tb6 <issue_id> <repo_path>` / `just tb6-replay <session_id>`
- TB-6 is TB-2 pattern + 3 new phases: save_session, parse_session, suggest_fix

#### TB-6 Files Changed

| File | What Changed |
|------|-------------|
| `feedback/types.py` | `SessionEvent`, `TB6Result` (session_id, session_path, event_count, event_types, gate_failure, suggested_fix) |
| `feedback/pipeline.py` | 6 helpers (`_generate_session_id`, `_parse_session_events`, `_save_session`, `_load_session`, `_format_session_timeline`, `_suggest_claude_md_fix`) + `run_tb6()` + `replay_session()` |
| `justfile` | `tb6` (2 args) + `tb6-replay` (1 arg) commands |
| `tests/test_tb6.py` | 30 tests: types, NDJSON parsing, save/load, timeline format, fix suggestions, session ID |
| `docs/tracer-bullets.md` | TB-6 section updated with actual design |

## Architecture (TB-6 flow)

```
just tb6 <issue_id> <repo_path>
    → run_tb6() in feedback/pipeline.py
        → Phase 1:   poll + claim (intake)
        → Phase 2:   setup_worktree (orchestration)
        → Phase 3:   select_persona (orchestration)
        → Phase 4:   init_tracing (observability)
        → Phase 5:   start_heartbeat (observability)
        → Phase 6:   spawn_agent → capture NDJSON stdout (runtime)
        → Phase 7:   _save_session() → .ndjson + .meta.json (observability)
        → Phase 8:   run gates (or forced failure)
        → Phase 9:   _parse_session_events() → structured timeline (observability)
        → Phase 10:  retry loop (feedback)
        → Phase 11:  _suggest_claude_md_fix() → rule-based fix (feedback)
        → Phase 12:  cleanup — heartbeat, worktree, OTel flush
```

## What's Next

All 6 tracer bullets implemented. Next: scoring rubric evaluation.

## Key Gotchas
- `br show --format json` returns a JSON array (list), not a dict
- `br create` uses `--labels` (plural), not `--label`; no `--epic` flag, use `--parent`
- Gate 0: uses `git rev-list --count HEAD` for safe lookback (handles short git histories)
- Gate 3 skips gracefully if bandit not installed or project is non-Python
- bandit exit code 1 = issues found (not an error), exit code 2 = actual error
- Pre-seeded vulnerable code is committed in worktree before agent runs
- `retry_agent()` must pass `model` AND `max_turns` params
- `provider.force_flush()` needed after pipeline to ensure spans export
- `kill_agent` validates PID belongs to claude before SIGTERM
- Heartbeat spans are detached from pipeline context (root spans)
- `select_persona()` must extract `max_turns_default` from YAML (not just Pydantic default)
- `--output-format json` is now always on — stdout is NDJSON, not plain text
- `retry_agent()` returns usage stats (`num_turns`, `input_tokens`, `output_tokens`) injected into the result dict
- TB-5 uses `fnmatch` (not `pathlib.match`) — `fnmatch` doesn't treat `/` specially so `src/api/**` matches `src/api/v2/deep/file.py`
- TB-5 `init_tracing()` is called after dependency matching (Phase 4) but the call is idempotent, so the nested `run_tb1()` call is safe
- TB-5 cascade skip is a success (`cascade_skipped=True`), not an error — no issue created, just a comment on source
- TB-5 `_report_cascade_outcome()` must use `--message` flag with `br comments add` (bug fix: was passing message as positional arg)
- TB-5 `_get_source_issue_details()` must handle `br show --format json` returning a list (bug fix: was assuming dict)
- TB-6 session files go to `/tmp/dev-loop/sessions/` — survives reboots on most Linux, but not guaranteed. Move to persistent storage for production.
- TB-6 `_parse_session_events()` skips non-JSON lines (agent may emit plain text alongside NDJSON)
- TB-6 `_suggest_claude_md_fix()` is rule-based, not LLM-based — maps gate name to fix template. Fast + deterministic but limited.
- TB-6 session metadata is re-written after gate analysis (Phase 11) to include gate_failure + suggested_fix
