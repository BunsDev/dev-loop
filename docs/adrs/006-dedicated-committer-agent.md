# ADR-006: Dedicated Committer Agent Pattern

## Status
Proposed (evaluate during TB-1)

## Context
In a multi-agent system, who handles git commits? Options:
1. Each coding agent commits its own work
2. A dedicated "committer" agent reviews and commits all work

## Decision
Evaluate the dedicated committer pattern during TB-1. Start with agents committing their own work (simpler), but design the interface so a committer agent can be inserted later.

## Rationale (for dedicated committer)
From Jeffrey Emanuel's workflow pattern:
- Coding agents produce messy, frequent commits ("wip", "fix", "try again")
- A committer agent can squash and rewrite with proper conventional commit messages
- Separation of concerns: coding agent focuses on code, committer focuses on history
- Committer can enforce commit conventions across all agents regardless of persona
- REACT paper (in graph) shows RAG-enhanced commit messages improve quality 102%

## Rationale (for self-committing, TB-1 default)
- Simpler — one less agent to coordinate
- CLAUDE.md rules can enforce commit message quality
- For single-commit changes (most bug fixes), the overhead isn't worth it

## Trigger to Switch
If we observe: >30% of PRs need commit message cleanup after agent runs → implement dedicated committer agent.
