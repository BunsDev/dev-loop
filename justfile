# dev-loop justfile
# Run `just --list` to see all commands

# Default: show help
default:
    @just --list

# ─── Stack Management ───

# Start all services (OpenObserve, etc.)
stack-up:
    @echo "Starting OpenObserve..."
    docker run -d \
      --name dev-loop-openobserve \
      -p 5080:5080 \
      -v dev-loop-openobserve-data:/data \
      -e ZO_ROOT_USER_EMAIL=admin@dev-loop.local \
      -e ZO_ROOT_USER_PASSWORD=devloop123 \
      public.ecr.aws/zinclabs/openobserve:latest 2>/dev/null || \
      docker start dev-loop-openobserve
    @echo "OpenObserve running at http://localhost:5080"

# Stop all services
stack-down:
    docker stop dev-loop-openobserve 2>/dev/null || true
    @echo "Stack stopped"

# Check service health
stack-health:
    @echo "=== OpenObserve ===" && curl -s http://localhost:5080/healthz && echo
    @echo "=== Linear API ===" && echo "TODO: verify Linear API key"
    @echo "=== Anthropic API ===" && echo "TODO: verify Anthropic API key"

# ─── Tracer Bullets ───

# TB-1: Ticket-to-PR (golden path)
tb1 *ARGS:
    @echo "Running TB-1: Ticket-to-PR"
    @echo "TODO: implement after intent docs are complete"
    @echo "Args: {{ARGS}}"

# TB-2: Failure-to-retry (feedback path)
tb2 *ARGS:
    @echo "Running TB-2: Failure-to-Retry"
    @echo "Requires: TB-1 passing"
    @echo "Args: {{ARGS}}"

# TB-3: Security gate (safety path)
tb3 *ARGS:
    @echo "Running TB-3: Security-Gate-to-Fix"
    @echo "Requires: TB-1 + TB-2 passing"
    @echo "Args: {{ARGS}}"

# TB-4: Cost control (budget path)
tb4 *ARGS:
    @echo "Running TB-4: Cost-Spike-to-Pause"
    @echo "Requires: TB-1 passing"
    @echo "Args: {{ARGS}}"

# TB-5: Cross-repo cascade (multi-project path)
tb5 *ARGS:
    @echo "Running TB-5: Cross-Repo Cascade"
    @echo "Requires: TB-1 passing on 2+ repos"
    @echo "Args: {{ARGS}}"

# TB-6: Session replay (observability path)
tb6 *ARGS:
    @echo "Running TB-6: Session Replay Debug"
    @echo "Requires: TB-2 passing"
    @echo "Args: {{ARGS}}"

# Run all passing tracer bullets
tb-all:
    @echo "Running all tracer bullets..."
    @echo "TODO: run only TBs that have been implemented"

# ─── Scoring ───

# Evaluate all tools against scoring rubric
score:
    @echo "Tool scoring not yet implemented"
    @echo "See docs/scoring-rubric.md for rubric"

# Score a specific tool
score-tool TOOL:
    @echo "Scoring tool: {{TOOL}}"
    @echo "TODO: implement interactive scoring"

# ─── Safety ───

# EMERGENCY: Kill all agents, pause intake, preserve worktrees
emergency-stop:
    @echo "!!! EMERGENCY STOP !!!"
    @echo "Killing all agent processes..."
    -pkill -f "claude" 2>/dev/null || true
    @echo "Stopping intake polling..."
    @echo "TODO: send stop signal to intake MCP server"
    @echo "Marking in-progress tickets as Interrupted..."
    @echo "TODO: Linear API bulk status update"
    @echo "Worktrees preserved for forensics."
    @echo "Run 'just status' to see state. Run 'just recover' to clean up."

# Recover from crashed/interrupted runs
recover:
    @echo "=== Recovery scan ==="
    @echo "Checking for orphaned worktrees..."
    @find /tmp/dev-loop/worktrees -name ".dev-loop-metadata.json" -mmin +60 2>/dev/null || echo "  No worktree directory found"
    @echo "Checking for stuck tickets..."
    @echo "TODO: query Linear for 'In Progress' tickets older than 1 hour"
    @echo "Run 'just worktree-gc' to clean up orphaned worktrees"

# Clean up orphaned worktrees older than 24h
worktree-gc:
    @echo "Scanning for orphaned worktrees..."
    @find /tmp/dev-loop/worktrees -maxdepth 1 -mmin +1440 -type d 2>/dev/null || echo "  No orphans found"
    @echo "TODO: prompt before deletion, check for uncommitted work"

# ─── Utilities ───

# Bypass Linear — run agent directly on a repo
run-direct REPO TASK:
    @echo "Direct run on {{REPO}}: {{TASK}}"
    @echo "TODO: implement direct agent spawn"

# Run TB-1 with mock intake (no Linear required)
tb1-mock FIXTURE="test-fixtures/tickets/tb1-sample.yaml":
    @echo "Running TB-1 with mock intake: {{FIXTURE}}"
    @echo "TODO: load ticket from YAML fixture, skip Linear"

# List all agent sessions
sessions-list *ARGS:
    @echo "TODO: integrate with AgentLens"

# View project status across all test repos
status:
    @echo "=== dev-loop status ==="
    @echo ""
    @echo "Tracer Bullets:"
    @echo "  TB-1 (Ticket-to-PR):      NOT STARTED"
    @echo "  TB-2 (Failure-to-Retry):   NOT STARTED"
    @echo "  TB-3 (Security Gate):      NOT STARTED"
    @echo "  TB-4 (Cost Control):       NOT STARTED"
    @echo "  TB-5 (Cross-Repo):         NOT STARTED"
    @echo "  TB-6 (Session Replay):     NOT STARTED"
    @echo ""
    @echo "Services:"
    @docker inspect -f '{{{{.State.Status}}}}' dev-loop-openobserve 2>/dev/null || echo "  OpenObserve: NOT RUNNING"

# Generate docs table of contents
docs-toc:
    @echo "# dev-loop Documentation"
    @echo ""
    @echo "## Architecture"
    @echo "- [Architecture Overview](docs/architecture.md)"
    @echo "- [Tracer Bullets](docs/tracer-bullets.md)"
    @echo "- [Scoring Rubric](docs/scoring-rubric.md)"
    @echo "- [Test Repos](docs/test-repos.md)"
    @echo ""
    @echo "## Layers"
    @for f in docs/layers/*.md; do echo "- [$$(head -1 $$f | sed 's/# //')]($$f)"; done
    @echo ""
    @echo "## ADRs"
    @for f in docs/adrs/*.md; do echo "- [$$(head -1 $$f | sed 's/# //')]($$f)"; done
