"""Typed agent orchestration configuration."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Literal

AgentMode = Literal["architect", "tester", "coder"]


def _int(name: str, default: int, *, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return parsed


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    return parsed or default


@dataclass(frozen=True)
class AgentModeConfig:
    mode: AgentMode
    tool_groups: tuple[str, ...]
    timeout_seconds: int
    max_subagents: int


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for the 3-mode agent workflow."""

    architect: AgentModeConfig
    tester: AgentModeConfig
    coder: AgentModeConfig
    probe_timeout_seconds: int
    summary_write_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            architect=AgentModeConfig(
                mode="architect",
                tool_groups=_csv("ARCHITECT_TOOL_GROUPS", ("repo", "github", "shell")),
                timeout_seconds=_int("ARCHITECT_TIMEOUT_SECONDS", 1200),
                max_subagents=_int("ARCHITECT_MAX_SUBAGENTS", 3),
            ),
            tester=AgentModeConfig(
                mode="tester",
                tool_groups=_csv("TESTER_TOOL_GROUPS", ("repo", "github", "shell")),
                timeout_seconds=_int("TESTER_TIMEOUT_SECONDS", 1200),
                max_subagents=_int("TESTER_MAX_SUBAGENTS", 2),
            ),
            coder=AgentModeConfig(
                mode="coder",
                tool_groups=_csv("CODER_TOOL_GROUPS", ("repo", "github", "shell")),
                timeout_seconds=_int("CODER_TIMEOUT_SECONDS", 1800),
                max_subagents=_int("CODER_MAX_SUBAGENTS", 2),
            ),
            probe_timeout_seconds=_int("PROBE_TIMEOUT_SECONDS", 60),
            summary_write_timeout_seconds=_int("SUMMARY_WRITE_TIMEOUT_SECONDS", 120),
        )

    def for_mode(self, mode: str) -> AgentModeConfig:
        if mode == self.architect.mode:
            return self.architect
        if mode == self.tester.mode:
            return self.tester
        if mode == self.coder.mode:
            return self.coder
        raise ValueError(f"Unknown agent mode: {mode}")


@lru_cache(maxsize=1)
def get_agent_config() -> AgentConfig:
    return AgentConfig.from_env()
