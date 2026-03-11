# ADR-003: OpenObserve for Observability

## Status
Accepted

## Context
Need a unified observability backend for logs, metrics, and traces. Options considered:

| Tool | Type | Pros | Cons |
|------|------|------|------|
| OpenObserve | Self-hosted | 140x cheaper storage, single binary, OTel native, Rust | Newer, smaller community |
| Datadog | SaaS | Best-in-class, huge ecosystem | Expensive at scale, vendor lock-in |
| Grafana + Loki + Tempo | Self-hosted | Mature, huge community | 3 separate systems to manage |
| Elasticsearch + Kibana | Self-hosted | Battle-tested | Resource hungry, complex ops |

## Decision
OpenObserve as the primary observability backend. Single binary deployment via Docker.

## Rationale
- 140x lower storage costs than Elasticsearch — matters for storing every agent trace
- Single binary — no managing 3 separate Grafana components
- Native OTel support — no adapters needed
- SQL query language — familiar, no new query syntax to learn
- PromQL support — can reuse existing Prometheus queries
- RUM (Real User Monitoring) — not needed now but useful if we add a dashboard UI
- Rust-based — performant enough to run alongside everything else on one machine

## Consequences
**Good:**
- One Docker container handles all three pillars
- OTel SDK → OpenObserve with zero adapters
- Low resource footprint on dev machine

**Bad:**
- Smaller community than Grafana stack — fewer tutorials, Stack Overflow answers
- If we outgrow it, migration to Grafana/Datadog requires dashboard recreation
- Some advanced features (alerting, anomaly detection) less mature than Datadog
