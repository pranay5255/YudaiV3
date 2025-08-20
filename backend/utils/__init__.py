"""
Utility modules for the YudaiV3 backend.

This package contains utility functions and classes used across the application.
"""

from datetime import datetime, timezone

from .chunking import FileChunker, create_file_chunker


def utc_now() -> datetime:
    """Return the current time in UTC as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


__all__ = ['FileChunker', 'create_file_chunker', 'utc_now']
