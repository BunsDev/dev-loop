# Handoff: Ambient Layer Research & Plan v2

**Date**: 2026-03-15
**Session**: Research + planning session (no code changes)

---

## What Happened This Session

1. **Designed the ambient layer architecture** — transforming dev-loop from a batch pipeline (`just tb1`) into a three-tier system (always-on hooks + checkpoint gates + full pipeline) that wraps every Claude Code session.

2. **Wrote initial plan** → `docs/ambient-layer-plan.md` (v1)

3. **Searched Link Forge** (Neo4j knowledge graph) with ~15 different keyword queries, surfacing 100+ tools/articles/repos across categories: Rust daemons, git hooks, secret scanning, observability, Claude Code extensions, agent harnesses, code quality tools.

4. **Deep-researched 8 projects** via background agents:
   - **AgentLens** — reads Claude's native JSONL, free session replay, no integration needed
   - **Axel** — SSE broadcast + JSONL EventLogger patterns (steal), TCP ports (skip)
   - **Entire CLI** — git trailer for commit→session linking, transcript flush sentinel
   - **dmux** — worktree prune+retry, queued cleanup, orphan detection
   - **Continuous-Claude-v3** — PreCompact handoff, 85% context guard, differentiated SessionStart, YAML format, outcome tracking
   - **Free CodeRabbit alternatives** — Semgrep, PR-Agent, Facebook Infer, MegaLinter, Qlty CLI
   - **TLA+/DST tools** — Turmoil (Rust DST), MadSim, TLA+ toolbox
   - **everything-claude-code** — settings.json hook structure reference

5. **Wrote plan v2** → `docs/ambient-layer-plan.md` incorporating all research findings

---

## What Was Decided

| Decision | Choice |
|----------|--------|
| SAST tool | **Semgrep** replaces bandit (30+ languages vs Python-only) |
| Session replay | **AgentLens** — install alongside, reads Claude JSONL natively |
| Session→git | **Entire CLI** — install alongside, captures sessions on push |
| Daemon IPC | Unix domain sockets (not TCP, validated against Axel) |
| Event streaming | SSE `/inbox` endpoint (from Axel) |
| Audit trail | Append-only JSONL event log with mpsc backpressure (from Axel) |
| Session continuity | YAML handoffs ~400 tokens, PreCompact auto-serialize (from CC-v3) |
| Context guard | 85% Stop hook blocks execution (from CC-v3) |
| Spec enforcement | ATDD at checkpoint — Given/When/Then before code |
| Tracer bullet workflow | Enforce test+src in same commit via `.devloop.yaml` |
| DST testing | **Turmoil** for deterministic async Rust testing |
| Git trailers | `Dev-Loop-Gate: <hash>` on checkpoint pass (from Entire) |
| Worktree lifecycle | Prune+retry, queued cleanup, orphan detection (from dmux) |

---

## Files Created/Modified

| File | Action |
|------|--------|
| `docs/ambient-layer-plan.md` | **CREATED** — full implementation plan (v2, ~900 lines) |
| `docs/handoff-2026-03-15-ambient-layer-research.md` | **CREATED** — this file |

**No code changes were made.** This was a pure research + planning session.

---

## Key Repos to Install Before Implementation

```bash
# Semgrep — multi-language SAST (replaces bandit)
pip install semgrep
# or: brew install semgrep

# AgentLens — session replay (reads Claude JSONL natively)
# Follow: https://github.com/RobertTLange/agentlens

# Entire CLI — session→commit linking
# Follow: https://github.com/entireio/cli

# Turmoil — DST for Rust daemon testing
# Added as dev-dependency in daemon/Cargo.toml
```

---

## Implementation Order (8 phases)

1. **Daemon skeleton** — Unix socket, SSE `/inbox`, JSONL event log, `dl start/stop/status/stream`
2. **Check engine** — deny list, dangerous ops, secrets (all in-process Rust)
3. **Hook integration** — `dl hook pre-tool-use/post-tool-use`, `dl install/uninstall`, toggle
4. **Config system** — 3-layer merge (built-in + global + per-repo `.devloop.yaml`)
5. **OTel + observability** — spans to OpenObserve, ambient dashboard, install AgentLens
6. **Tier 2 checkpoint** — Semgrep, gitleaks, ATDD, tracer-bullet enforcement, git trailers
7. **Session continuity** — PreCompact handoff, 85% context guard, outcome tracking
8. **External integrations + polish** — Entire CLI, dashboard validation, benchmarks, Turmoil tests

---

## What's NOT Done (future sessions)

- No Rust code written yet — plan only
- No `.devloop.yaml` files created in any repo
- No Semgrep rules configured
- No ATDD specs written for any repo
- OpenObserve dashboards still have rendering issues (user reports problems but I can't check visuals)
- Gate 1 (ATDD) still blocked on repos having `specs/` directories
- PR-Agent evaluation deferred to v2
- agent-vault placeholder substitution deferred to v2
- Shannon pentesting agent evaluation deferred to v2
- Headroom context compression deferred to v2

---

## Context for Next Session

The plan at `docs/ambient-layer-plan.md` is comprehensive and ready to execute. Start with Phase 1 (daemon skeleton). The user wants:
- Semi-autonomous coding guardrails everywhere Claude operates
- Transparency (SSE stream, JSONL log, `dl status`)
- Easy on/off toggle (`dl enable/disable`)
- Per-repo customization (`.devloop.yaml`)
- The system should feel like a safety net, not a cage (fail-open, warn severity, allow-once overrides)
