import { API, buildApiUrl } from '../config/api';

type RealtimeFlagSubset = {
  controllerProxyEnabled: boolean;
  tunnelModeEnabled: boolean;
};

const DEFAULT_ORIGIN = 'http://localhost';
const ABSOLUTE_HTTP_URL_RE = /^https?:\/\//i;

const getOriginFallback = (currentOrigin?: string): string => {
  if (currentOrigin) {
    return currentOrigin;
  }
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return DEFAULT_ORIGIN;
};

const isAbsoluteHttpUrl = (value: string): boolean => ABSOLUTE_HTTP_URL_RE.test(value);

export const buildControllerProxySessionUrl = (
  resolvedUrl: string,
  currentOrigin?: string
): string | null => {
  const parsed = new URL(resolvedUrl, getOriginFallback(currentOrigin));
  const match = parsed.pathname.match(/^(.*)\/daifu\/sessions\/([^/]+)(\/.*)?$/);
  if (!match) {
    return null;
  }

  const [, apiPrefix, sessionId, rest] = match;
  const proxyPath =
    `${apiPrefix}/controller/proxy/sessions/${sessionId}/sessions/${sessionId}` +
    `${rest || ''}${parsed.search}`;

  return isAbsoluteHttpUrl(resolvedUrl) ? `${parsed.origin}${proxyPath}` : proxyPath;
};

export const buildRealtimeSessionTargetUrl = ({
  endpoint,
  params,
  flags,
  tunnelUrl,
  currentOrigin,
  missingTunnelErrorMessage = 'Sandbox tunnel is unavailable. Please create a new session.',
}: {
  endpoint: string;
  params: Record<string, string>;
  flags: RealtimeFlagSubset;
  tunnelUrl?: string | null;
  currentOrigin?: string;
  missingTunnelErrorMessage?: string;
}): string => {
  const resolved = buildApiUrl(endpoint, params);

  if (flags.controllerProxyEnabled) {
    const proxied = buildControllerProxySessionUrl(resolved, currentOrigin);
    if (proxied) {
      return proxied;
    }
  }

  if (!flags.tunnelModeEnabled) {
    return resolved;
  }

  if (!tunnelUrl) {
    throw new Error(missingTunnelErrorMessage);
  }

  const parsed = new URL(resolved, getOriginFallback(currentOrigin));
  const tunnelPath = parsed.pathname.replace(/^\/(?:api\/)?daifu/, '');
  return `${tunnelUrl.replace(/\/$/, '')}${tunnelPath}${parsed.search}`;
};

export const buildUnifiedSessionWebSocketUrl = ({
  sessionId,
  sessionToken,
  currentOrigin,
  proxyBaseUrl,
}: {
  sessionId: string;
  sessionToken: string;
  currentOrigin?: string;
  proxyBaseUrl?: string;
}): string => {
  const proxyBase = proxyBaseUrl || buildApiUrl(API.CONTROLLER.PROXY, { sessionId });
  const parsed = new URL(proxyBase, getOriginFallback(currentOrigin));
  const wsProtocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
  const basePath = parsed.pathname.replace(/\/$/, '');
  return (
    `${wsProtocol}//${parsed.host}${basePath}/ws/sessions/${sessionId}/ws/unified` +
    `?token=${encodeURIComponent(sessionToken)}`
  );
};
