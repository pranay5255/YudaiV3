"""Typed model provider configuration."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}


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


def _strip_openrouter_prefix(value: str) -> str:
    return value.removeprefix("openrouter/")


def _as_openrouter_agent_model(value: str) -> str:
    return value if value.startswith("openrouter/") else f"openrouter/{value}"


def _resolve_model_names() -> tuple[str, str]:
    openrouter_model = _optional_str("OPENROUTER_MODEL")
    agent_model = _optional_str("MSWEA_MODEL_NAME")

    if openrouter_model:
        model_name = _strip_openrouter_prefix(openrouter_model)
        return model_name, agent_model or _as_openrouter_agent_model(model_name)

    if agent_model:
        return _strip_openrouter_prefix(agent_model), agent_model

    raise ValueError("OPENROUTER_MODEL or MSWEA_MODEL_NAME must be set")


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


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for chat and agent models."""

    model_name: str
    agent_model_name: str
    supports_thinking: bool
    supports_vision: bool
    api_key: str | None
    api_url: str
    temperature: float
    max_tokens: int
    timeout_seconds: int

    @classmethod
    def from_env(cls) -> "ModelConfig":
        model_name, agent_model = _resolve_model_names()
        return cls(
            model_name=model_name,
            agent_model_name=agent_model,
            supports_thinking=_bool("MODEL_SUPPORTS_THINKING", False),
            supports_vision=_bool("MODEL_SUPPORTS_VISION", False),
            api_key=_optional_str("OPENROUTER_API_KEY"),
            api_url=_str(
                "OPENROUTER_API_URL",
                "https://openrouter.ai/api/v1/chat/completions",
            ),
            temperature=_float("MODEL_TEMPERATURE", 0.6),
            max_tokens=_int("MODEL_MAX_TOKENS", 4000),
            timeout_seconds=_int("MODEL_TIMEOUT_SECONDS", 30),
        )


@lru_cache(maxsize=1)
def get_model_config() -> ModelConfig:
    return ModelConfig.from_env()
