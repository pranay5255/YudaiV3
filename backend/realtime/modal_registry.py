"""In-memory registry for active Modal sandbox instances."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from .modal_sandbox import RealtimeModalSandbox

logger = logging.getLogger(__name__)


class ModalSandboxRegistry:
    """Thread-safe in-memory mapping from sandbox DB IDs to Modal instances."""

    def __init__(self) -> None:
        self._sandboxes: Dict[str, RealtimeModalSandbox] = {}
        self._lock = asyncio.Lock()

    async def register(self, sandbox_db_id: str, sandbox: RealtimeModalSandbox) -> None:
        async with self._lock:
            self._sandboxes[sandbox_db_id] = sandbox
            logger.info("Registered Modal sandbox: db_id=%s modal_id=%s", sandbox_db_id, sandbox.modal_sandbox_id)

    async def get(self, sandbox_db_id: str) -> Optional[RealtimeModalSandbox]:
        async with self._lock:
            return self._sandboxes.get(sandbox_db_id)

    async def remove(self, sandbox_db_id: str) -> Optional[RealtimeModalSandbox]:
        async with self._lock:
            return self._sandboxes.pop(sandbox_db_id, None)

    async def terminate_and_remove(self, sandbox_db_id: str) -> None:
        sandbox = await self.remove(sandbox_db_id)
        if sandbox:
            await sandbox.terminate()


_registry_singleton: Optional[ModalSandboxRegistry] = None


def get_modal_registry() -> ModalSandboxRegistry:
    global _registry_singleton
    if _registry_singleton is None:
        _registry_singleton = ModalSandboxRegistry()
    return _registry_singleton
