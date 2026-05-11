from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from yudai.config import (  # noqa: E402
    get_agent_config,
    get_model_config,
    get_sandbox_config,
)


@pytest.fixture(autouse=True)
def clear_config_caches():
    get_sandbox_config.cache_clear()
    get_model_config.cache_clear()
    get_agent_config.cache_clear()
    yield
    get_sandbox_config.cache_clear()
    get_model_config.cache_clear()
    get_agent_config.cache_clear()


def test_sandbox_config_coerces_env(monkeypatch):
    monkeypatch.setenv("SANDBOX_PROVIDER", "modal")
    monkeypatch.setenv("REALTIME_WORKSPACE_PATH", "/tmp/workspace")
    monkeypatch.setenv("SANDBOX_LIVENESS_INTERVAL_SECONDS", "15")
    monkeypatch.setenv("SANDBOX_LIVENESS_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("SANDBOX_ENV_PASSTHROUGH_KEYS", "OPENROUTER_API_KEY,MSWEA_MODEL_NAME")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")

    config = get_sandbox_config()

    assert config.provider == "modal"
    assert config.workspace_path == "/tmp/workspace"
    assert config.liveness_interval_seconds == 15
    assert config.liveness_timeout_seconds == 2.5
    assert config.env_passthrough_keys == ("OPENROUTER_API_KEY", "MSWEA_MODEL_NAME")
    assert config.env_passthrough_values == (("OPENROUTER_API_KEY", "secret"),)
    assert config.controller_callback_secret == config.controller_internal_ws_secret


def test_sandbox_config_uses_explicit_callback_secret(monkeypatch):
    monkeypatch.setenv("CONTROLLER_INTERNAL_WS_SECRET", "internal")
    monkeypatch.setenv("CONTROLLER_CALLBACK_SECRET", "callback")

    config = get_sandbox_config()

    assert config.controller_internal_ws_secret == "internal"
    assert config.controller_callback_secret == "callback"


def test_sandbox_config_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("SANDBOX_PROVIDER", "local")

    with pytest.raises(ValueError, match="SANDBOX_PROVIDER"):
        get_sandbox_config()


def test_sandbox_config_uses_sandbox_workspace_env_fallback(monkeypatch):
    monkeypatch.delenv("REALTIME_WORKSPACE_PATH", raising=False)
    monkeypatch.setenv("WORKSPACE_PATH", "/workspace/custom")

    config = get_sandbox_config()

    assert config.workspace_path == "/workspace/custom"


def test_model_config_uses_openrouter_and_agent_defaults(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "x-ai/test-model")
    monkeypatch.delenv("MSWEA_MODEL_NAME", raising=False)
    monkeypatch.setenv("MODEL_SUPPORTS_VISION", "true")

    config = get_model_config()

    assert config.model_name == "x-ai/test-model"
    assert config.agent_model_name == "openrouter/x-ai/test-model"
    assert config.supports_vision is True
    assert config.supports_thinking is False


def test_model_config_can_derive_openrouter_model_from_agent_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setenv("MSWEA_MODEL_NAME", "openrouter/x-ai/agent-model")

    config = get_model_config()

    assert config.model_name == "x-ai/agent-model"
    assert config.agent_model_name == "openrouter/x-ai/agent-model"


def test_model_config_requires_model_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("MSWEA_MODEL_NAME", raising=False)

    with pytest.raises(ValueError, match="OPENROUTER_MODEL or MSWEA_MODEL_NAME"):
        get_model_config()


def test_agent_config_exposes_mode_timeouts(monkeypatch):
    monkeypatch.setenv("ARCHITECT_TIMEOUT_SECONDS", "42")
    monkeypatch.setenv("CODER_MAX_SUBAGENTS", "4")

    config = get_agent_config()

    assert config.architect.timeout_seconds == 42
    assert config.coder.max_subagents == 4
    assert config.for_mode("architect") is config.architect
    with pytest.raises(ValueError, match="Unknown agent mode"):
        config.for_mode("probe")
