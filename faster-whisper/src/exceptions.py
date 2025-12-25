from __future__ import annotations


class ShutdownRequested(Exception):
    """Raised when shutdown is requested during transcription to prevent false success."""

    pass
