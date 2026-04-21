"""Backward-compat shim — ModalSandboxRegistry is now in modal_sandbox.py."""

from .modal_sandbox import ModalSandboxRegistry, get_modal_registry  # noqa: F401
