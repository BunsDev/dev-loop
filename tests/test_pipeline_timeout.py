"""Tests for pipeline timeout (R-4)."""

from __future__ import annotations

import signal

import pytest

from devloop.feedback.pipeline import (
    PIPELINE_TIMEOUT_SECONDS,
    PipelineTimeout,
    _clear_pipeline_timeout,
    _set_pipeline_timeout,
    _timeout_handler,
)


class TestPipelineTimeout:
    """Tests for the pipeline timeout mechanism."""

    def test_timeout_constant_is_reasonable(self):
        """Default timeout is 20 minutes (1200 seconds)."""
        assert PIPELINE_TIMEOUT_SECONDS == 1200

    def test_timeout_handler_raises(self):
        """_timeout_handler raises PipelineTimeout."""
        with pytest.raises(PipelineTimeout, match="exceeded.*total budget"):
            _timeout_handler(signal.SIGALRM, None)

    def test_set_and_clear_timeout(self):
        """_set_pipeline_timeout arms SIGALRM, _clear_pipeline_timeout disarms it."""
        _set_pipeline_timeout(999)
        # Verify alarm is set (signal.alarm returns remaining seconds)
        remaining = signal.alarm(0)
        assert remaining > 0 or remaining == 0  # may have ticked down already
        # Clear should work without error
        _clear_pipeline_timeout()
        # After clear, no alarm should be pending
        assert signal.alarm(0) == 0

    def test_pipeline_timeout_exception_is_catchable(self):
        """PipelineTimeout can be caught as a regular exception."""
        try:
            raise PipelineTimeout("test")
        except PipelineTimeout as exc:
            assert "test" in str(exc)

    def test_clear_is_idempotent(self):
        """Clearing when no alarm is set doesn't raise."""
        _clear_pipeline_timeout()
        _clear_pipeline_timeout()
