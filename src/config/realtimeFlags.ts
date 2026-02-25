const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on', 'enabled']);

const parseFlag = (value: string | undefined, fallback: boolean): boolean => {
  if (!value) {
    return fallback;
  }
  return TRUE_VALUES.has(value.trim().toLowerCase());
};

export interface RealtimeFeatureFlags {
  controllerSplitEnabled: boolean;
  tunnelModeEnabled: boolean;
  wsChatEnabled: boolean;
  sseStreamEnabled: boolean;
  controllerProxyEnabled: boolean;
  wsUnifiedEnabled: boolean;
  contractVersion: string;
}

export const realtimeFeatureFlags: RealtimeFeatureFlags = {
  controllerSplitEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_CONTROLLER_SPLIT_ENABLED,
    false
  ),
  tunnelModeEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_TUNNEL_MODE_ENABLED,
    false
  ),
  wsChatEnabled: parseFlag(import.meta.env.VITE_REALTIME_WS_CHAT_ENABLED, false),
  sseStreamEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_SSE_STREAM_ENABLED,
    false
  ),
  controllerProxyEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_CONTROLLER_PROXY_ENABLED,
    false
  ),
  wsUnifiedEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_WS_UNIFIED_ENABLED,
    false
  ),
  contractVersion: (
    import.meta.env.VITE_REALTIME_CONTRACT_VERSION || 'realtime-v1-phase0'
  ).trim(),
};

