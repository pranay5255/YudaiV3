import { API, buildApiUrl } from '../config/api';

const DEFAULT_ORIGIN = 'http://localhost';

const getOriginFallback = (currentOrigin?: string): string => {
  if (currentOrigin) {
    return currentOrigin;
  }
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return DEFAULT_ORIGIN;
};

const trimTrailingSlash = (value: string): string => value.replace(/\/+$/, '');

const toWebSocketProtocol = (protocol: string): 'ws:' | 'wss:' => {
  switch (protocol) {
    case 'https:':
    case 'wss:':
      return 'wss:';
    case 'http:':
    case 'ws:':
      return 'ws:';
    default:
      throw new Error(`Unsupported WebSocket base protocol: ${protocol}`);
  }
};

const assertNoMixedContentWebSocket = (
  wsProtocol: 'ws:' | 'wss:',
  currentOrigin?: string
): void => {
  const pageProtocol = new URL(getOriginFallback(currentOrigin)).protocol;
  if (pageProtocol === 'https:' && wsProtocol === 'ws:') {
    throw new Error(
      'Insecure WebSocket configuration: an https:// page cannot connect to ws://. Remove VITE_WS_BASE_URL or use https://api.yudai.app / wss://api.yudai.app.'
    );
  }
};

export const buildControllerSessionTargetUrl = (
  endpoint: string,
  params: Record<string, string>
): string => {
  return buildApiUrl(endpoint, params);
};

export const buildControllerUnifiedWsEndpoint = ({
  sessionId,
  controllerWsBaseUrl,
}: {
  sessionId: string;
  controllerWsBaseUrl?: string;
}): string => {
  const rawBase = (controllerWsBaseUrl || '').trim();
  if (!rawBase) {
    return buildApiUrl(API.CONTROLLER.UNIFIED_WS, { sessionId });
  }

  const normalized = trimTrailingSlash(rawBase);
  if (normalized.includes('/controller/sessions/')) {
    return normalized;
  }

  return `${normalized}/controller/sessions/${encodeURIComponent(sessionId)}/ws/unified`;
};

export const buildUnifiedSessionWebSocketUrl = ({
  sessionId,
  sessionToken,
  currentOrigin,
  controllerWsBaseUrl,
}: {
  sessionId: string;
  sessionToken: string;
  currentOrigin?: string;
  controllerWsBaseUrl?: string;
}): string => {
  const controllerBase = buildControllerUnifiedWsEndpoint({
    sessionId,
    controllerWsBaseUrl,
  });
  const parsed = new URL(controllerBase, getOriginFallback(currentOrigin));
  const wsProtocol = toWebSocketProtocol(parsed.protocol);
  assertNoMixedContentWebSocket(wsProtocol, currentOrigin);
  return (
    `${wsProtocol}//${parsed.host}${parsed.pathname}` +
    `?token=${encodeURIComponent(sessionToken)}`
  );
};
