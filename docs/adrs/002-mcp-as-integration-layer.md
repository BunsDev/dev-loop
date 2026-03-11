# ADR-002: MCP as the Integration Layer

## Status
Accepted

## Context
Layers need to communicate. Options:
1. Direct function calls (tight coupling)
2. Message queues (Redis, RabbitMQ — heavy infra)
3. HTTP APIs (standard but requires server per layer)
4. MCP servers (each layer exposes tools, any MCP client can call them)

## Decision
Use MCP (Model Context Protocol) servers as the integration boundary between layers. Each layer exposes its capabilities as MCP tools.

## Rationale
- Claude Code and other agents are already MCP clients — zero integration cost
- MCP servers are lightweight (single TypeScript file can be a server)
- Tools are self-documenting (name, description, schema)
- We're building for an agent-driven loop — MCP is the agent's native protocol
- Datadog's MCP server design blog confirms this pattern works at scale

## Consequences
**Good:**
- Any MCP client (Claude Code, Cursor, custom agent) can drive the loop
- Layers are independently deployable and testable
- Adding a new gate = adding a new MCP tool, not changing architecture
- Matches the multi-project model (shared MCP servers, per-project config)

**Bad:**
- MCP adds latency vs direct function calls (acceptable for our use case)
- Debugging MCP communication is harder than debugging function calls
- MCP ecosystem is still maturing — breaking changes possible

## References
- Datadog's "Designing MCP tools for agents" blog post
- Claude Code MCP server documentation
