# ADR-004: OpenFang for Agent Sandboxing

## Status
Proposed (deferred to TB-3)

## Context
Agents run commands, read/write files, and make API calls. Without sandboxing:
- An agent could `rm -rf` the wrong directory
- An agent could read `.env` files and leak secrets via LLM calls
- A prompt injection in a GitHub issue could make the agent exfiltrate data
- A runaway agent could consume unbounded resources

## Decision
Evaluate OpenFang as the agent sandbox layer. For TB-1 and TB-2, use CLAUDE.md rules + worktree isolation as lightweight sandboxing. For TB-3+, integrate OpenFang's WASM sandbox.

## Rationale
- OpenFang provides 16 security layers including prompt injection detection
- Capability-based permissions (scoped tokens, not raw credentials)
- Resource metering (token budget enforcement at the OS level)
- WASM isolation is stronger than process isolation
- MIT licensed, actively developed

## Risks
- OpenFang is new — may not be production-ready
- WASM sandbox may limit what agents can do (file system access, network calls)
- Integration complexity with Claude Code's tool system
- Performance overhead of WASM vs native execution

## Alternatives Considered
- **Docker containers per agent** — heavier, slower to start, but well-understood
- **gVisor/Firecracker** — overkill for our use case
- **CLAUDE.md rules only** — not a real sandbox, just suggestions to the LLM
- **IronClaw** — Rust WASM sandbox with encrypted credential vault, less mature than OpenFang

## Fallback
If OpenFang doesn't work out: Docker container per agent run, with mounted worktree volume and restricted network access. Heavier but guaranteed to work.
