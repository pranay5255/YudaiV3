"""Backward-compat shim — SandboxManager is now in lifecycle.py."""

from .lifecycle import ProbeCallback, SandboxManager  # noqa: F401
