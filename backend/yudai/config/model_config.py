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
    """Configuration for chat, agent, and embedding models."""

    model_name: str
    agent_model_name: str
    supports_thinking: bool
    supports_vision: bool
    api_key: str | None
    api_url: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    embedding_model: str
    hf_home: str

    @classmethod
    def from_env(cls) -> "ModelConfig":
        default_model = _str("OPENROUTER_MODEL", "x-ai/grok-4-fast")
        agent_model = _str("MSWEA_MODEL_NAME", f"openrouter/{default_model}")
        return cls(
            model_name=default_model,
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
            embedding_model=_str("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            hf_home=_str("HF_HOME", "/tmp/huggingface_cache"),
        )


@lru_cache(maxsize=1)
def get_model_config() -> ModelConfig:
    return ModelConfig.from_env()

