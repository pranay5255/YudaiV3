from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current time in UTC as a timezone-aware datetime."""
    return datetime.now(timezone.utc)
