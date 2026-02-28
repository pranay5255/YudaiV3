from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Return the current time in UTC as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure a datetime is timezone-aware in UTC.

    SQLite returns naive datetimes (no timezone info), but we need timezone-aware
    datetimes for comparisons and arithmetic with utc_now().

    Args:
        dt: A datetime object (naive or aware) or None

    Returns:
        A timezone-aware datetime in UTC, or None if input was None
    """
    if dt is None:
        return None

    # If already timezone-aware, return as-is
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
        return dt

    # Naive datetime - treat as UTC and make it timezone-aware
    return dt.replace(tzinfo=timezone.utc)
