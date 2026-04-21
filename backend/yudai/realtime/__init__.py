"""Realtime sandbox/controller modules.

Keep package imports side-effect free so the sandbox server can import
`realtime.sandbox_routes` without pulling in controller DB dependencies.
"""

__all__: list[str] = []
