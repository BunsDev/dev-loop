# ADR-001: Tracer Bullet Development Approach

## Status
Accepted

## Context
We're building a multi-layer developer tooling harness with 6 layers and 15+ tools. The natural instinct is to build horizontally: complete Layer 1, then Layer 2, etc. This approach has two failure modes:

1. **Integration hell** — layers built in isolation don't fit together
2. **Delayed feedback** — you don't know the system works until all layers exist

## Decision
Build vertically using tracer bullets. Each feature is a thin slice that cuts through all six layers end-to-end. The first tracer bullet (TB-1) proves the entire loop works with the simplest possible implementation at each layer.

## Consequences
**Good:**
- Integration tested from day one
- Working end-to-end system exists after TB-1
- Each subsequent TB widens the path, not extending it
- Problems surface early at layer boundaries

**Bad:**
- Each TB requires touching 6+ files across layers
- Some layer implementations are "stub quality" in early TBs
- Can feel slow because you're not "finishing" any single layer

## References
- "The Pragmatic Programmer" by Hunt & Thomas (coined "tracer bullets")
- LangChain's "harness engineering" blog post (iterative improvement pattern)
