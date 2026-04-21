"""Cache metadata utilities for repository context management."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheMetadata:
    """Lightweight metadata persisted alongside cached GitIngest context."""

    cache_path: str
    owner: str
    name: str
    session_id: str
    user_id: int
    size: Optional[int] = None
    sha256: Optional[str] = None
    cached_at: Optional[str] = None
    version: int = 2
    source: Optional[str] = "gitingest"

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> Optional["CacheMetadata"]:
        if not payload or not isinstance(payload, dict):
            return None
        try:
            return cls(
                cache_path=payload["cache_path"],
                owner=payload["owner"],
                name=payload["name"],
                session_id=payload.get("session_id", ""),
                user_id=int(payload.get("user_id", 0)),
                size=payload.get("size"),
                sha256=payload.get("sha256"),
                cached_at=payload.get("cached_at"),
                version=int(payload.get("version", 1)),
                source=payload.get("source"),
            )
        except KeyError:
            logger.debug("Cache metadata payload missing required fields: %s", payload)
            return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_path": self.cache_path,
            "owner": self.owner,
            "name": self.name,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "size": self.size,
            "sha256": self.sha256,
            "cached_at": self.cached_at,
            "version": self.version,
            "source": self.source,
        }
