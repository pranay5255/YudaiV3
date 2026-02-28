const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on', 'enabled']);

const parseFlag = (value: string | undefined, fallback: boolean): boolean => {
  if (!value) {
    return fallback;
  }
  return TRUE_VALUES.has(value.trim().toLowerCase());
};

export interface RealtimeFeatureFlags {
  controllerSplitEnabled: boolean;
  controllerBrokerEnabled: boolean;
  sandboxInternalExecEnabled: boolean;
  modeOrchestratorEnabled: boolean;
  wsChatEnabled: boolean;
  sseStreamEnabled: boolean;
  wsUnifiedEnabled: boolean;
  contractVersion: string;
}

export const realtimeFeatureFlags: RealtimeFeatureFlags = {
  controllerSplitEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_CONTROLLER_SPLIT_ENABLED,
    false
  ),
  controllerBrokerEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_CONTROLLER_BROKER_ENABLED,
    true
  ),
  sandboxInternalExecEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_SANDBOX_INTERNAL_EXEC_ENABLED,
    true
  ),
  modeOrchestratorEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_MODE_ORCHESTRATOR_ENABLED,
    true
  ),
  wsChatEnabled: parseFlag(import.meta.env.VITE_REALTIME_WS_CHAT_ENABLED, false),
  sseStreamEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_SSE_STREAM_ENABLED,
    false
  ),
  wsUnifiedEnabled: parseFlag(
    import.meta.env.VITE_REALTIME_WS_UNIFIED_ENABLED,
    false
  ),
  contractVersion: (
    import.meta.env.VITE_REALTIME_CONTRACT_VERSION ||
    'realtime-v2-controller-broker'
  ).trim(),
};
