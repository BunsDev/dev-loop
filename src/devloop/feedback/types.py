"""Pydantic models for the feedback loop layer."""

from __future__ import annotations

from pydantic import BaseModel, Field

from devloop.gates.types import GateSuiteResult


class RetryPrompt(BaseModel):
    """A constructed retry prompt with failure context for the agent."""

    prompt_text: str = Field(
        description="The full retry prompt including all failure details.",
    )
    failure_count: int = Field(
        default=0,
        ge=0,
        description="Number of gate failures encoded in this prompt.",
    )


class RetryResult(BaseModel):
    """Result of a retry attempt (agent re-spawn + gate re-run)."""

    attempt: int = Field(
        description="Which retry attempt this was (1-indexed).",
    )
    max_retries: int = Field(
        description="Maximum retries allowed for this run.",
    )
    success: bool = Field(
        description="True if all gates passed after this retry.",
    )
    gate_results: GateSuiteResult | None = Field(
        default=None,
        description="Gate suite results from the retry run (None if agent failed to spawn).",
    )
    escalated: bool = Field(
        default=False,
        description="True if retries were exhausted and the issue was escalated to a human.",
    )
    agent_exit_code: int = Field(
        default=-1,
        description="Exit code from the agent process during this retry.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if the retry failed at infrastructure level.",
    )


class EscalationResult(BaseModel):
    """Result of escalating a failed issue to a human."""

    issue_id: str
    success: bool
    status_updated: bool = False
    comment_added: bool = False
    attempts: int = 0
    message: str = ""


class TB1Result(BaseModel):
    """Result of a full TB-1 pipeline run."""

    issue_id: str
    repo_path: str
    success: bool
    phase: str = Field(
        description="Last phase completed (or failed at).",
    )
    worktree_path: str | None = None
    persona: str | None = None
    agent_exit_code: int | None = None
    gate_results: GateSuiteResult | None = None
    retries_used: int = 0
    max_retries: int = 0
    escalated: bool = False
    error: str | None = None
    duration_seconds: float = 0.0


class SecurityFinding(BaseModel):
    """A security finding from Gate 3 with CWE classification."""

    cwe: str | None = None
    severity: str = "critical"
    message: str = ""
    file: str | None = None
    line: int | None = None
    rule: str | None = None
    fixed: bool = False


class TB3Result(BaseModel):
    """Result of a full TB-3 pipeline run (Security-Gate-to-Fix)."""

    issue_id: str
    repo_path: str
    success: bool
    phase: str = Field(
        description="Last phase completed (or failed at).",
    )
    worktree_path: str | None = None
    persona: str | None = None
    retries_used: int = 0
    max_retries: int = 0
    escalated: bool = False
    error: str | None = None
    duration_seconds: float = 0.0
    # TB-3 specific fields
    trace_id: str | None = Field(
        default=None,
        description="Root OTel trace ID for trace verification.",
    )
    attempt_span_ids: list[str] = Field(
        default_factory=list,
        description="Span IDs per attempt for linked trace verification.",
    )
    security_findings: list[SecurityFinding] = Field(
        default_factory=list,
        description="Security findings detected by Gate 3 on initial scan.",
    )
    vulnerability_fixed: bool = Field(
        default=False,
        description="True if the security vulnerability was fixed after retry.",
    )
    cwe_ids: list[str] = Field(
        default_factory=list,
        description="CWE IDs detected (e.g. ['CWE-89'] for SQL injection).",
    )
    vuln_seeded: bool = Field(
        default=False,
        description="Whether vulnerable code was pre-seeded (forced mode).",
    )
    retry_history: list[RetryAttempt] = Field(
        default_factory=list,
        description="Per-attempt summary with gate results and span IDs.",
    )


class RetryAttempt(BaseModel):
    """Summary of a single retry attempt for TB-2 tracking."""

    attempt: int
    agent_exit_code: int = -1
    gates_passed: bool = False
    first_failure: str | None = None
    span_id: str | None = None


class TB2Result(BaseModel):
    """Result of a full TB-2 pipeline run."""

    issue_id: str
    repo_path: str
    success: bool
    phase: str = Field(
        description="Last phase completed (or failed at).",
    )
    worktree_path: str | None = None
    persona: str | None = None
    retries_used: int = 0
    max_retries: int = 0
    escalated: bool = False
    error: str | None = None
    duration_seconds: float = 0.0
    # TB-2 specific fields
    trace_id: str | None = Field(
        default=None,
        description="Root OTel trace ID for trace verification.",
    )
    attempt_span_ids: list[str] = Field(
        default_factory=list,
        description="Span IDs per attempt for linked trace verification.",
    )
    blocked_verified: bool = Field(
        default=False,
        description="True if issue status was verified as 'blocked' after escalation.",
    )
    force_gate_fail_used: bool = Field(
        default=False,
        description="Whether forced gate failure mode was active.",
    )
    retry_history: list[RetryAttempt] = Field(
        default_factory=list,
        description="Per-attempt summary with gate results and span IDs.",
    )
