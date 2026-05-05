import { API, buildApiUrl } from '../config/api';

export const buildControllerSessionTargetUrl = (
  endpoint: string,
  params: Record<string, string>
): string => buildApiUrl(endpoint, params);

export const buildRealtimeSessionEventsUrl = (sessionId: string): string => (
  buildApiUrl(API.CONTROLLER.SESSION_EVENTS, { sessionId })
);
