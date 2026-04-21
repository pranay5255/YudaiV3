from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clear_typed_config_caches():
    from yudai.config import get_agent_config, get_model_config, get_sandbox_config

    get_sandbox_config.cache_clear()
    get_model_config.cache_clear()
    get_agent_config.cache_clear()
    yield
    get_sandbox_config.cache_clear()
    get_model_config.cache_clear()
    get_agent_config.cache_clear()
