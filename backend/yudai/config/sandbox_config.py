"""Typed sandbox and realtime environment configuration."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Literal

TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}

DEFAULT_SANDBOX_ENV_PASSTHROUGH_KEYS: tuple[str, ...] = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_URL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
    "MSWEA_MODEL_NAME",
    "OPENROUTER_MODEL",
)


def _optional_str(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


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


def _float(name: str, default: float, *, minimum: float = 0.0) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return parsed


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    return parsed or default


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for controller-managed sandbox runtimes."""

    provider: Literal["modal"]
    workspace_path: str
    mswea_config_root: str
    default_org: str
    controller_base_url: str
    controller_internal_ws_secret: str | None
    controller_callback_secret: str | None
    controller_heartbeat_secret: str | None
    heartbeat_interval_seconds: int
    allow_origins: tuple[str, ...]
    modal_sandbox_timeout_seconds: int
    modal_preflight_enabled: bool
    modal_preflight_sandbox_timeout_seconds: int
    modal_preflight_healthcheck_timeout_seconds: float
    modal_preflight_exec_timeout_seconds: int
    liveness_interval_seconds: int
    liveness_timeout_seconds: float
    git_fetch_interval_seconds: int
    tunnel_template: str | None
    git_root: str
    cache_root: str
    artifact_root: str
    command_timeout_seconds: int
    env_passthrough_keys: tuple[str, ...]
    env_passthrough_values: tuple[tuple[str, str], ...]

    @classmethod
    def from_env(cls) -> "SandboxConfig":
        provider = _str("SANDBOX_PROVIDER", "modal").lower()
        if provider != "modal":
            raise ValueError("SANDBOX_PROVIDER must be 'modal'")

        env_passthrough_keys = _csv(
            "SANDBOX_ENV_PASSTHROUGH_KEYS",
            DEFAULT_SANDBOX_ENV_PASSTHROUGH_KEYS,
        )
        env_passthrough_values = tuple(
            (key, value.strip())
            for key in env_passthrough_keys
            if (value := os.getenv(key)) is not None and value.strip()
        )

        controller_internal_ws_secret = _optional_str("CONTROLLER_INTERNAL_WS_SECRET")
        return cls(
            provider="modal",
            workspace_path=_str(
                "REALTIME_WORKSPACE_PATH",
                _str("WORKSPACE_PATH", "/workspace/repo"),
            ),
            mswea_config_root=_str("MSWEA_CONFIG_ROOT", "/app/mswea_mode_configs"),
            default_org=_str("REALTIME_DEFAULT_ORG", "yudai"),
            controller_base_url=_str("CONTROLLER_BASE_URL", "http://localhost:8000"),
            controller_internal_ws_secret=controller_internal_ws_secret,
            controller_callback_secret=(
                _optional_str("CONTROLLER_CALLBACK_SECRET")
                or controller_internal_ws_secret
            ),
            controller_heartbeat_secret=_optional_str("CONTROLLER_HEARTBEAT_SECRET"),
            heartbeat_interval_seconds=_int("SANDBOX_HEARTBEAT_INTERVAL_SECONDS", 10),
            allow_origins=_csv("SANDBOX_ALLOW_ORIGINS", ("https://yudai.app",)),
            modal_sandbox_timeout_seconds=_int("MODAL_SANDBOX_TIMEOUT_SECONDS", 7200),
            modal_preflight_enabled=_bool("MODAL_SANDBOX_PREFLIGHT_ENABLED", True),
            modal_preflight_sandbox_timeout_seconds=_int(
                "MODAL_SANDBOX_PREFLIGHT_SANDBOX_TIMEOUT_SECONDS",
                900,
            ),
            modal_preflight_healthcheck_timeout_seconds=_float(
                "MODAL_SANDBOX_PREFLIGHT_HEALTHCHECK_TIMEOUT_SECONDS",
                60.0,
            ),
            modal_preflight_exec_timeout_seconds=_int(
                "MODAL_SANDBOX_PREFLIGHT_EXEC_TIMEOUT_SECONDS",
                45,
            ),
            liveness_interval_seconds=_int("SANDBOX_LIVENESS_INTERVAL_SECONDS", 10),
            liveness_timeout_seconds=_float("SANDBOX_LIVENESS_TIMEOUT_SECONDS", 3.0),
            git_fetch_interval_seconds=_int("SANDBOX_GIT_FETCH_INTERVAL_SECONDS", 300),
            tunnel_template=_optional_str("SANDBOX_TUNNEL_TEMPLATE"),
            git_root=_str("SANDBOX_GIT_ROOT", "/home/yudai/.cache/repos"),
            cache_root=_str("SANDBOX_CACHE_ROOT", "/home/yudai/.cache"),
            artifact_root=_str("SANDBOX_ARTIFACT_ROOT", "/data/sandbox_artifacts"),
            command_timeout_seconds=_int("SANDBOX_COMMAND_TIMEOUT_SECONDS", 1800),
            env_passthrough_keys=env_passthrough_keys,
            env_passthrough_values=env_passthrough_values,
        )


@lru_cache(maxsize=1)
def get_sandbox_config() -> SandboxConfig:
    return SandboxConfig.from_env()
