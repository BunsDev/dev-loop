"""Shared path constants for dev-loop."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

WORKTREE_BASE = Path(
    os.environ.get(
        "DEVLOOP_WORKTREE_DIR",
        os.path.join(tempfile.gettempdir(), "dev-loop", "worktrees"),
    )
)
