"""Feature flags for real-time session rollout phases."""

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Dict

TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUE_VALUES


@dataclass(frozen=True)
class RealtimeFeatureFlags:
    """Phase rollout toggles used by controller and frontend clients."""

    controller_split_enabled: bool
    tunnel_mode_enabled: bool
    ws_chat_enabled: bool
    sse_stream_enabled: bool
    modal_provisioning_enabled: bool
    controller_proxy_enabled: bool
    ws_unified_enabled: bool
    contract_version: str

    @classmethod
    def from_env(cls) -> "RealtimeFeatureFlags":
        contract_version = os.getenv("REALTIME_CONTRACT_VERSION", "realtime-v1-phase0")
        normalized_contract_version = contract_version.strip() or "realtime-v1-phase0"
        return cls(
            controller_split_enabled=_env_bool(
                "REALTIME_CONTROLLER_SPLIT_ENABLED", False
            ),
            tunnel_mode_enabled=_env_bool("REALTIME_TUNNEL_MODE_ENABLED", False),
            ws_chat_enabled=_env_bool("REALTIME_WS_CHAT_ENABLED", False),
            sse_stream_enabled=_env_bool("REALTIME_SSE_STREAM_ENABLED", False),
            modal_provisioning_enabled=_env_bool(
                "REALTIME_MODAL_PROVISIONING_ENABLED", False
            ),
            controller_proxy_enabled=_env_bool(
                "REALTIME_CONTROLLER_PROXY_ENABLED", False
            ),
            ws_unified_enabled=_env_bool("REALTIME_WS_UNIFIED_ENABLED", False),
            contract_version=normalized_contract_version,
        )

    def as_dict(self) -> Dict[str, object]:
        return {
            "controller_split_enabled": self.controller_split_enabled,
            "tunnel_mode_enabled": self.tunnel_mode_enabled,
            "ws_chat_enabled": self.ws_chat_enabled,
            "sse_stream_enabled": self.sse_stream_enabled,
            "modal_provisioning_enabled": self.modal_provisioning_enabled,
            "controller_proxy_enabled": self.controller_proxy_enabled,
            "ws_unified_enabled": self.ws_unified_enabled,
            "contract_version": self.contract_version,
        }


@lru_cache(maxsize=1)
def get_realtime_feature_flags() -> RealtimeFeatureFlags:
    return RealtimeFeatureFlags.from_env()

